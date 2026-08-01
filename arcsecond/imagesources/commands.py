"""
Click command groups for the live-image proxy.

``arcsecond webcam start`` serves this machine's USB webcams, plus any cameras
reached over the network (``--netcam``). ``arcsecond allsky start`` serves
all-sky cameras (``--allsky``). ``arcsecond netcam test`` checks one network
camera's address before it is added anywhere.

There is only ever one proxy. Each ``start`` may be run at a different time:
the first one puts the proxy up, and any later one hands its cameras to the
proxy already running and exits, leaving it alone. Registered cameras are
remembered (see store.py), so a machine that reboots comes back with them.
"""

import asyncio
import json
import logging
import os
import urllib.request
from string import Template
from urllib.parse import urlsplit

import click

from . import store
from .registry import AllskyOverride, NetcamOverride
from .sources.filewatch import detect_allsky
from .sources.network import (
    RTSP_SCHEMES,
    SUPPORTED_SCHEMES,
    build_network_source,
    redact_url,
)
from .sources.opencv import detect_webcams

logger = logging.getLogger(__name__)


def _check_aiohttp():
    try:
        import aiohttp  # noqa: F401
    except ImportError:
        click.echo(
            click.style("Error: ", fg="red") + "aiohttp is not installed.\n"
            "Run:  pip install 'arcsecond[webcam]'"
        )
        raise SystemExit(1)


def _check_cv2():
    try:
        import cv2  # noqa: F401
    except ImportError:
        click.echo(
            click.style("Error: ", fg="red")
            + "opencv-python-headless is not installed.\n"
            "Run:  pip install 'arcsecond[webcam]'"
        )
        raise SystemExit(1)


def _parse_allsky_overrides(values: tuple[str, ...]) -> list[AllskyOverride]:
    overrides: list[AllskyOverride] = []
    for v in values:
        if "=" not in v:
            raise click.BadParameter(f"--allsky must be id=path, got {v!r}")
        sid, _, path = v.partition("=")
        sid, path = sid.strip(), path.strip()
        if not sid or not path:
            raise click.BadParameter(f"--allsky must be id=path, got {v!r}")
        overrides.append(AllskyOverride(id=sid, path=path))
    return overrides


def _expand_env_vars(url: str) -> str:
    """Replace ``${VAR}`` in a camera URL with the value from the environment.

    Done here rather than when the camera is first used, so a missing variable
    is reported the moment the command is typed. ``os.path.expandvars`` would
    leave an unset variable in place as plain text and quietly send it as the
    password.
    """
    try:
        return Template(url).substitute(os.environ)
    except KeyError as e:
        raise click.BadParameter(
            f"the environment variable {e.args[0]} used in the camera URL is not set."
        ) from None
    except ValueError:
        raise click.BadParameter(
            "the camera URL contains a stray '$'. Write it as '$$' if it is part "
            "of the password."
        ) from None


def _parse_netcam_overrides(values: tuple[str, ...]) -> list[NetcamOverride]:
    overrides: list[NetcamOverride] = []
    for v in values:
        if "=" not in v:
            raise click.BadParameter(f"--netcam must be id=url, got {v!r}")
        # partition splits on the first '=' only, so a URL query string keeps its.
        sid, _, url = v.partition("=")
        sid, raw_url = sid.strip(), url.strip()
        url = _expand_env_vars(raw_url)
        if not sid or not url:
            raise click.BadParameter(f"--netcam must be id=url, got {v!r}")
        scheme = urlsplit(url).scheme.lower()
        if scheme not in SUPPORTED_SCHEMES:
            raise click.BadParameter(
                f"{redact_url(url)} cannot be used. Camera URLs must start with "
                f"{', '.join(s + '://' for s in SUPPORTED_SCHEMES)}."
            )
        overrides.append(NetcamOverride(id=sid, url=url, raw_url=raw_url))
    return overrides


# ---------------------------------------------------------------------------
# Talking to a proxy that is already running
# ---------------------------------------------------------------------------

_CONTACT_TIMEOUT = 2.0  # seconds — it is on this machine, so it answers fast


def _call_proxy(port: int, path: str, method: str = "GET", body=None):
    """One short request to the local proxy. Returns None if it is not there.

    Plain urllib rather than aiohttp: these are single calls with no event loop
    around them, and `forget` should work without the proxy extra installed.
    """
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        headers={"Content-Type": "application/json"} if body is not None else {},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=_CONTACT_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8") or "{}")
    except Exception:
        return None


def _proxy_is_running(port: int) -> bool:
    """Whether one of *our* proxies holds this port.

    The health payload is checked, not merely the fact that something answered —
    an unrelated service on the same port must not be mistaken for a proxy and
    handed a camera registration.
    """
    answer = _call_proxy(port, "/health")
    return isinstance(answer, dict) and answer.get("status") == "ok"


def _register_with_running_proxy(port: int, allsky_overrides, netcam_overrides) -> bool:
    payload = {
        "allsky": [{"id": o.id, "path": o.path} for o in allsky_overrides],
        "netcam": [{"id": o.id, "url": o.url} for o in netcam_overrides],
    }
    answer = _call_proxy(port, "/sources", method="POST", body=payload)
    if answer is None:
        click.echo(
            click.style("Error: ", fg="red")
            + f"a proxy is running on port {port} but would not accept the camera."
        )
        raise SystemExit(1)

    added = answer.get("added") or []
    if added:
        click.echo(
            f"Registered {', '.join(added)} with the proxy already running "
            f"on port {port}. It is available now — the proxy keeps running."
        )
    else:
        click.echo(
            f"The proxy is already running on port {port}. "
            "No new camera was given, so nothing changed."
        )
    return True


# ---------------------------------------------------------------------------
# Starting the proxy
# ---------------------------------------------------------------------------


def _start(host: str, port: int, log_level: str, allsky_overrides, netcam_overrides):
    """Register the given cameras, whether or not a proxy is already running.

    Remembering them first means the cameras come back by themselves after a
    reboot, and means both paths below agree on what is registered.
    """
    store.remember_allsky(allsky_overrides)
    store.remember_netcams(netcam_overrides)

    if _proxy_is_running(port):
        _register_with_running_proxy(port, allsky_overrides, netcam_overrides)
        return

    _run_proxy(host, port, log_level)


def _run_proxy(host: str, port: int, log_level: str):
    _check_aiohttp()

    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    )

    # Everything ever registered, not just what this command was given — this is
    # how a camera added last week is still there after a reboot.
    allsky_overrides = store.remembered_allsky()
    netcam_overrides = store.remembered_netcams(_expand_env_vars)

    remembered = [f"allsky:{o.id}" for o in allsky_overrides]
    remembered += [f"netcam:{o.id}" for o in netcam_overrides]

    click.echo(
        click.style("Arcsecond live-image proxy", bold=True)
        + f" listening on {host}:{port}\n"
        f"  Detection  →  http://{host}:{port}/detect\n"
        f"  Streaming  →  ws://{host}:{port}/stream/{{id}}\n"
    )
    if remembered:
        click.echo("Remembered cameras: " + ", ".join(remembered) + "\n")
    click.echo(
        "Set in your .env file:\n"
        f"  LIVE_IMAGE_PROXY_URL=http://host.docker.internal:{port}\n\n"
        "Press Ctrl-C to stop."
    )

    from .proxy import run

    run(
        host=host,
        port=port,
        allsky_overrides=allsky_overrides,
        netcam_overrides=netcam_overrides,
    )


def _forget(kind: str, source_id: str, port: int):
    """Remove a camera from the store, and from a running proxy if there is one."""
    try:
        forgotten = store.forget(kind, source_id)
    except store.SourceStoreError as e:
        click.echo(click.style("Error: ", fg="red") + str(e))
        raise SystemExit(1)

    if _proxy_is_running(port):
        _call_proxy(port, f"/sources/{kind}:{source_id}", method="DELETE")

    if forgotten:
        click.echo(f"Forgotten: {kind}:{source_id}.")
    else:
        click.echo(f"No camera is registered as {kind}:{source_id}. Nothing to forget.")


# ---------------------------------------------------------------------------
# Shared options
# ---------------------------------------------------------------------------

_server_options = [
    click.option(
        "--port", default=8765, show_default=True, help="TCP port to listen on."
    ),
    click.option(
        "--host", default="0.0.0.0", show_default=True, help="Interface to bind."
    ),
    click.option(
        "--log-level",
        default="INFO",
        show_default=True,
        type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
        help="Logging verbosity.",
    ),
]

_port_option = click.option(
    "--port", default=8765, show_default=True, help="Port the proxy runs on."
)


def _add_options(options):
    def _wrap(fn):
        for opt in reversed(options):
            fn = opt(fn)
        return fn

    return _wrap


# ---------------------------------------------------------------------------
# `arcsecond webcam` group — USB webcams and network cameras
# ---------------------------------------------------------------------------


@click.group(help="Manage USB webcams and cameras reached over the network.")
def webcam():
    pass


@webcam.command(
    name="detect",
    help="List the webcams attached to this machine, and any remembered network cameras.",
)
def webcam_detect_cmd():
    _check_cv2()
    cams = detect_webcams()
    if cams:
        click.echo(f"Found {len(cams)} webcam(s) attached to this machine:\n")
        for c in cams:
            e = c.extra or {}
            click.echo(
                f"  {c.id}  {e.get('width')}×{e.get('height')}  "
                f"{e.get('fps', 0):.1f} fps"
            )
    else:
        click.echo("No webcams attached to this machine.")

    remembered = store.remembered_netcams(_expand_env_vars)
    if remembered:
        click.echo(f"\nRemembered network cameras ({len(remembered)}):\n")
        for o in remembered:
            click.echo(f"  netcam:{o.id}  →  {redact_url(o.url)}")
        click.echo("\nRemove one with:  arcsecond webcam forget <id>")


@webcam.command(
    name="start",
    help=(
        "Start the live-image proxy, serving this machine's webcams.\n\n"
        "Add cameras reached over the network with --netcam id=url, once per "
        "camera. Registered cameras are remembered, so they come back on their "
        "own after a reboot.\n\n"
        "If the proxy is already running, the camera is added to it and this "
        "command exits — the running proxy is left alone.\n\n"
        "Set LIVE_IMAGE_PROXY_URL=http://host.docker.internal:<PORT> in your "
        ".env so Arcsecond.local can reach the proxy."
    ),
)
@_add_options(_server_options)
@click.option(
    "--netcam",
    "netcam",
    multiple=True,
    metavar="ID=URL",
    help="Add a camera reached over the network. URL is the address from the "
    "camera's manual, e.g. rtsp://... or http://.../snapshot.jpg. Repeat for "
    "several cameras. Write a password as ${VARIABLE} to keep it out of the "
    "command line.",
)
def webcam_start_cmd(port, host, log_level, netcam):
    _start(host, port, log_level, [], _parse_netcam_overrides(netcam))


@webcam.command(
    name="forget",
    help="Stop remembering a network camera. Give its id, e.g. `dome`.",
)
@click.argument("source_id")
@_port_option
def webcam_forget_cmd(source_id, port):
    _forget("netcam", source_id, port)


# ---------------------------------------------------------------------------
# `arcsecond allsky` group  (new)
# ---------------------------------------------------------------------------


@click.group(help="Manage all-sky camera image sources.")
def allsky():
    pass


@allsky.command(
    name="detect",
    help=(
        "Look for all-sky cameras at well-known paths (Thomas Jacquin's allsky, "
        "indi-allsky), and list any remembered ones."
    ),
)
def allsky_detect_cmd():
    found = detect_allsky()
    if found:
        click.echo(f"Found {len(found)} all-sky camera(s) at well-known paths:\n")
        for s in found:
            click.echo(f"  {s.id}  →  {(s.extra or {}).get('path')}")
    else:
        click.echo("No all-sky cameras found at well-known paths.")

    remembered = store.remembered_allsky()
    if remembered:
        click.echo(f"\nRemembered all-sky cameras ({len(remembered)}):\n")
        for o in remembered:
            click.echo(f"  allsky:{o.id}  →  {o.path}")
        click.echo("\nRemove one with:  arcsecond allsky forget <id>")
    elif not found:
        click.echo(
            "\nIf your software writes images elsewhere, add that path with:\n\n"
            "  arcsecond allsky start --allsky <id>=<path-to-jpeg-or-glob>"
        )


@allsky.command(
    name="start",
    help=(
        "Start the live-image proxy, serving your all-sky cameras.\n\n"
        "Cameras at well-known paths are found on their own. Add others with "
        "--allsky id=path, once per camera; the path may be a file or a glob. "
        "They are remembered, so they come back on their own after a reboot.\n\n"
        "If the proxy is already running, the camera is added to it and this "
        "command exits — the running proxy is left alone."
    ),
)
@_add_options(_server_options)
@click.option(
    "--allsky",
    "allsky",
    multiple=True,
    metavar="ID=PATH",
    help="Add an all-sky camera. PATH may be a file or a glob. Repeat for "
    "several cameras.",
)
def allsky_start_cmd(port, host, log_level, allsky):
    _start(host, port, log_level, _parse_allsky_overrides(allsky), [])


@allsky.command(
    name="forget",
    help="Stop remembering an all-sky camera. Give its id, e.g. `roof`.",
)
@click.argument("source_id")
@_port_option
def allsky_forget_cmd(source_id, port):
    _forget("allsky", source_id, port)


# ---------------------------------------------------------------------------
# `arcsecond netcam` group
# ---------------------------------------------------------------------------


@click.group(help="Manage cameras reached over the network.")
def netcam():
    pass


@netcam.command(
    name="test",
    help=(
        "Connect to a network camera once, report what it sends, and exit.\n\n"
        "Use this to check an address and password before adding the camera to "
        "`--netcam`. Write a password as ${VARIABLE} to keep it out of your "
        "command history."
    ),
)
@click.argument("url")
@click.option(
    "--timeout",
    default=15.0,
    show_default=True,
    help="Seconds to wait for a first image.",
)
def netcam_test_cmd(url, timeout):
    typed_url = url
    url = _expand_env_vars(url)
    scheme = urlsplit(url).scheme.lower()
    if scheme not in SUPPORTED_SCHEMES:
        raise click.BadParameter(
            f"{redact_url(url)} cannot be used. Camera URLs must start with "
            f"{', '.join(s + '://' for s in SUPPORTED_SCHEMES)}."
        )

    if scheme in RTSP_SCHEMES:
        _check_cv2()
    else:
        _check_aiohttp()

    click.echo(f"Connecting to {redact_url(url)} ...")

    async def _probe():
        source = build_network_source("netcam:test", url)
        await source.open()
        try:
            deadline = asyncio.get_running_loop().time() + timeout
            while asyncio.get_running_loop().time() < deadline:
                frame = await source.read()
                if frame:
                    return frame
                await asyncio.sleep(source.poll_interval)
            return None
        finally:
            await source.close()

    try:
        frame = asyncio.run(asyncio.wait_for(_probe(), timeout + 5.0))
    except asyncio.TimeoutError:
        click.echo(
            click.style("Failed: ", fg="red")
            + f"no image after {timeout:.0f} seconds. The address may be wrong, "
            "or the camera may be sending a format we cannot read."
        )
        raise SystemExit(1)
    except Exception as e:
        click.echo(click.style("Failed: ", fg="red") + str(e))
        raise SystemExit(1)

    if not frame:
        click.echo(
            click.style("Failed: ", fg="red")
            + f"connected, but no image arrived within {timeout:.0f} seconds."
        )
        raise SystemExit(1)

    # Suggest back exactly what was typed when a ${VARIABLE} was used, so the
    # line can be copied and will work. Only a password typed in the clear is
    # hidden — and repeating that one on screen would be the one real leak here.
    suggested = typed_url if typed_url != url else redact_url(url)

    click.echo(
        click.style("Success. ", fg="green")
        + f"Received an image of {len(frame) / 1024:.0f} kB.\n\n"
        "Add this camera to the proxy with:\n\n"
        f"  arcsecond webcam start --netcam mycam='{suggested}'"
    )
