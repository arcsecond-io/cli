"""
Click command groups for the live-image proxy.

Three commands, three jobs, and no overlap between them:

``arcsecond webcam``   the cameras you have — plugged into this machine over
                       USB, or reached over the network. A network camera is
                       not a separate thing to learn: same list, same ``add``,
                       same ``forget``, and the URL is simply what you pass to
                       ``add`` instead of a device index.
``arcsecond allsky``   the same, for all-sky cameras: the JPEG their software
                       keeps up to date, given as a path when that software
                       runs here and as an address when it runs elsewhere.
``arcsecond proxy``    starting and inspecting the one proxy that serves
                       everything registered above.

Each of the two camera groups follows the same four verbs:

    (no verb)   list what is registered. Reads the store, probes nothing, so
                it answers instantly and gives the same answer every time.
    detect      look at the hardware and say how it lines up with the list:
                what is new, what is registered and present, what is
                registered and missing. Probes, and does nothing else —
                detecting never registers anything.
    add         register a camera, which is what makes the proxy serve it.
    forget      the mirror of add.

Registering and starting used to be the same command, so `start` quietly
added cameras and `add` did not exist. They are separate now: `add` never
starts a proxy, and `proxy start` never registers a camera. A camera added
while the proxy is up is handed to it straight away, so neither order of
doing things needs a restart.
"""

import asyncio
import errno
import logging
import os
import signal
import subprocess
import sys
import time
import urllib.request
from string import Template
from typing import Optional
from urllib.parse import urlsplit

import click

from . import detection, runtime, store
from .sources.network import (
    HTTP_SCHEMES,
    RTSP_SCHEMES,
    SUPPORTED_SCHEMES,
    build_network_source,
    redact_url,
)
from .store import ALLSKY, NET, USB, WEBCAM_KINDS, Camera

logger = logging.getLogger(__name__)

DEFAULT_PORT = 8765

# `proxy stop` waits this long for a polite shutdown before insisting. The
# proxy closes its viewers itself and bounds its own wait (see proxy.py), so
# anything past this is stuck rather than busy.
STOP_TIMEOUT = 10.0
_HARD_TIMEOUT = 3.0
_STOP_POLL_INTERVAL = 0.2

# How long `proxy start` waits for the background proxy to answer before
# calling it a failed start and showing what the log says.
START_TIMEOUT = 20.0
_START_POLL_INTERVAL = 0.2

# SIGKILL where there is one. On Windows there is not, and os.kill maps
# SIGTERM onto TerminateProcess, which is already the abrupt one.
_HARD_SIGNAL = getattr(signal, "SIGKILL", signal.SIGTERM)


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


def _fail(message: str, *lines: str):
    click.echo(click.style("Error: ", fg="red") + message)
    for line in lines:
        click.echo(line)
    raise SystemExit(1)


# ---------------------------------------------------------------------------
# Talking to a proxy that is already running
# ---------------------------------------------------------------------------

_CONTACT_TIMEOUT = 2.0  # seconds — it is on this machine, so it answers fast


def _call_proxy(port: int, path: str, method: str = "GET", body=None):
    """One short request to the local proxy. Returns None if it is not there.

    Plain urllib rather than aiohttp: these are single calls with no event loop
    around them, and `forget` must work without the proxy extra installed.
    """
    import json

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


def _proxy_health(port: int):
    """The health payload of one of *our* proxies on this port, or None.

    The payload is checked, not merely the fact that something answered — an
    unrelated service on the same port must not be mistaken for a proxy and
    handed a camera registration, still less signalled.
    """
    answer = _call_proxy(port, "/health")
    if isinstance(answer, dict) and answer.get("status") == "ok":
        return answer
    return None


def _proxy_is_running(port: int) -> bool:
    return _proxy_health(port) is not None


def _running_proxy():
    """``(port, pid)`` for the running proxy, or None. ``pid`` may be None.

    Read from the note the proxy leaves behind when it starts (runtime.py), so
    that `add`, `forget` and `status` do not need a --port typed at them. The
    note is confirmed with a health check before it is believed, and the
    default port is tried as well, so a proxy started before this file existed
    is still found.
    """
    recorded = runtime.read()
    candidates = []
    if recorded:
        candidates.append(recorded["port"])
    if DEFAULT_PORT not in candidates:
        candidates.append(DEFAULT_PORT)
    for port in candidates:
        health = _proxy_health(port)
        if health is None:
            continue
        # The pid comes from the proxy answering on this port, not from the
        # file: a file outlives a proxy that was killed, and by then its pid
        # may belong to some other process entirely. The file is only a
        # fallback, and only when it describes this very port.
        pid = health.get("pid")
        if pid is None and recorded and recorded.get("port") == port:
            pid = recorded.get("pid")
        return port, pid

    # Nothing answered. If a note was left behind, the proxy it describes was
    # killed rather than stopped, so the note is worse than useless — clear it
    # rather than health-checking a dead port on every command from now on.
    if recorded:
        runtime.clear()
    return None


def _running_proxy_port():
    """Just the port of the running proxy, or None."""
    running = _running_proxy()
    return running[0] if running else None


def _tell_proxy_about(camera: Camera) -> bool:
    """Hand a newly registered camera to the proxy, if one is running."""
    port = _running_proxy_port()
    if port is None:
        return False
    usable = store.expanded([camera], _expand_env_vars)
    if not usable:
        return False
    entry = usable[0].to_json()
    entry["id"] = camera.id
    answer = _call_proxy(port, "/sources", method="POST", body={"cameras": [entry]})
    return bool(answer and answer.get("added"))


def _tell_proxy_to_forget(cam_id: str) -> bool:
    port = _running_proxy_port()
    if port is None:
        return False
    answer = _call_proxy(port, f"/sources/{cam_id}", method="DELETE")
    return bool(answer and answer.get("removed"))


# ---------------------------------------------------------------------------
# Printing
# ---------------------------------------------------------------------------


def _print_table(rows: list[tuple], headers: tuple):
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    click.echo(
        "  "
        + click.style(
            "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)).rstrip(),
            bold=True,
        )
    )
    for row in rows:
        click.echo(
            "  "
            + "  ".join(str(c).ljust(widths[i]) for i, c in enumerate(row)).rstrip()
        )


def _list_registered(kinds, noun: str, add_example: str):
    """Print the registered cameras of ``kinds``. Nothing is probed."""
    try:
        cameras = store.cameras_of_kinds(kinds)
    except store.SourceStoreError as e:
        _fail(str(e))

    if not cameras:
        click.echo(f"No {noun} is registered.\n")
        click.echo(f"Register one with:\n\n  {add_example}\n")
        click.echo(
            "Or see what is attached to this machine:  " + _detect_example(kinds)
        )
        return

    click.echo(click.style(f"Registered {noun}s ({len(cameras)}):\n", bold=True))
    _print_table(
        [
            (c.id, c.display_kind, c.target, _describe_specs(c), c.label or "")
            for c in cameras
        ],
        ("ID", "KIND", "CAMERA", "DETAILS", "NAME"),
    )
    click.echo(f"\nForget one with:  {_forget_example(kinds)} <ID>")


def _describe_specs(camera: Camera) -> str:
    """A camera's resolution and frame rate, as recorded when it was added."""
    specs = camera.specs or {}
    width, height, fps = specs.get("width"), specs.get("height"), specs.get("fps")
    if not (width and height):
        return ""
    size = f"{width}×{height}"
    return f"{size}, {fps:.0f} fps" if fps else size


def _detect_example(kinds) -> str:
    return "arcsecond allsky detect" if ALLSKY in kinds else "arcsecond webcam detect"


def _forget_example(kinds) -> str:
    return "arcsecond allsky forget" if ALLSKY in kinds else "arcsecond webcam forget"


def _print_detection(report: detection.DetectionReport, kinds):
    """The three questions detection answers, each answered separately."""
    add_cmd = "arcsecond allsky add" if ALLSKY in kinds else "arcsecond webcam add"

    if report.new:
        click.echo(
            click.style(
                f"Newly detected, not registered ({len(report.new)}):\n", bold=True
            )
        )
        rows = []
        for device in report.new:
            extra = device.extra or {}
            target = (
                str(extra.get("index"))
                if device.kind == USB
                else str(extra.get("path", ""))
            )
            rows.append(
                (target, report.detail.get(device.identity, ""), f"{add_cmd} {target}")
            )
        _print_table(rows, ("CAMERA", "DETAILS", "REGISTER IT WITH"))
        click.echo("")

    if report.present:
        click.echo(
            click.style(f"Registered and present ({len(report.present)}):\n", bold=True)
        )
        _print_table(
            [
                (c.id, c.display_kind, c.target, report.detail.get(c.id, ""))
                for c in report.present
            ],
            ("ID", "KIND", "CAMERA", "DETAILS"),
        )
        click.echo("")

    if report.missing:
        click.echo(
            click.style(
                f"Registered but not found ({len(report.missing)}):\n",
                fg="yellow",
                bold=True,
            )
        )
        _print_table(
            [
                (c.id, c.display_kind, c.target, report.detail.get(c.id, ""))
                for c in report.missing
            ],
            ("ID", "KIND", "CAMERA", "WHY"),
        )
        click.echo(
            "\nThese stay registered — a camera that is switched off is still "
            f"yours. Drop one for good with:  {_forget_example(kinds)} <ID>\n"
        )

    if report.is_empty:
        click.echo(
            "Nothing detected, and nothing registered.\n\n"
            f"Register a camera with:  {add_cmd} <CAMERA>"
        )


# ---------------------------------------------------------------------------
# Registering and forgetting
# ---------------------------------------------------------------------------


def _add(camera: Camera, absent_note=None):
    """Register ``camera`` and say what happened.

    ``absent_note`` is only consulted for a camera that was actually just
    registered: telling someone their camera is unplugged is useful the first
    time, and noise when they are simply re-running a line from their history.
    """
    try:
        stored, created = store.add(camera)
    except store.SourceStoreError as e:
        _fail(str(e))

    if not created:
        click.echo(
            f"Already registered as {click.style(stored.id, bold=True)} "
            f"({stored.target}). Nothing changed."
        )
        return

    click.echo(
        click.style("Registered ", fg="green")
        + click.style(stored.id, bold=True)
        + f"  →  {stored.target}"
    )

    note = absent_note() if absent_note is not None else None
    if note:
        click.echo(click.style("Note: ", fg="yellow") + note)
    if _tell_proxy_about(stored):
        click.echo("The proxy is running and is serving it now.")
    else:
        click.echo("Start serving it with:  arcsecond proxy start")


def _forget(cam_id: str, kinds, noun: str):
    """Forget one camera, whatever kind it is.

    The id alone is enough — there is no kind to get right and no prefix to
    strip. A camera of the wrong kind for this command is named rather than
    reported missing, because "no such camera" would be a lie the operator
    could not act on.
    """
    try:
        camera = store.find(cam_id)
    except store.SourceStoreError as e:
        _fail(str(e))

    if camera is None:
        _fail(
            f"no camera is registered as {cam_id!r}.",
            f"\nSee what is registered with:  {'arcsecond allsky' if ALLSKY in kinds else 'arcsecond webcam'}",
        )

    if camera.kind not in kinds:
        other = "arcsecond allsky" if camera.kind == ALLSKY else "arcsecond webcam"
        _fail(
            f"{camera.id} is {camera.description}, not a {noun}.",
            f"\nForget it with:  {other} forget {camera.id}",
        )

    store.forget(camera.id)
    click.echo(
        click.style("Forgotten ", fg="green")
        + click.style(camera.id, bold=True)
        + f"  ({camera.target})"
    )
    if _tell_proxy_to_forget(camera.id):
        click.echo("The running proxy has stopped serving it.")


# ---------------------------------------------------------------------------
# `arcsecond webcam` — cameras, whether attached by USB or reached over IP
# ---------------------------------------------------------------------------


@click.group(
    invoke_without_command=True,
    help=(
        "List your webcams — plugged into this machine, or reached over the "
        "network.\n\n"
        "With no sub-command, prints what is registered and probes nothing. "
        "Use `detect` to look at the hardware, `add` to register a camera and "
        "`forget` to drop one."
    ),
)
@click.pass_context
def webcam(ctx):
    if ctx.invoked_subcommand is None:
        _list_registered(
            WEBCAM_KINDS,
            "webcam",
            "arcsecond webcam add <int>    # or a camera URL for netcams",
        )


@webcam.command(
    name="detect",
    help=(
        "Look for webcams and report how they line up with what is registered: "
        "newly detected, registered and present, registered but not found.\n\n"
        "Registers nothing. Network cameras cannot be discovered — there is no "
        "way to ask a network which of it is a camera — so a registered one is "
        "confirmed by connecting to its address instead."
    ),
)
@click.option(
    "--timeout",
    default=detection.NETWORK_TIMEOUT,
    show_default=True,
    help="Seconds to wait for a network camera to answer.",
)
@click.option(
    "--no-network",
    is_flag=True,
    help="Do not contact network cameras; list them without checking.",
)
def webcam_detect_cmd(timeout, no_network):
    _check_cv2()
    try:
        cameras = store.all_cameras()
    except store.SourceStoreError as e:
        _fail(str(e))
    report = detection.report(
        cameras, WEBCAM_KINDS, timeout=timeout, check_network=not no_network
    )
    _print_detection(report, WEBCAM_KINDS)


@webcam.command(
    name="add",
    help=(
        "Register a webcam, so that the proxy serves it.\n\n"
        "CAMERA is either a device index for a webcam plugged into this machine "
        "(`0`, as printed by `detect`), or the address of a camera on the "
        "network (`rtsp://...`, `http://.../snapshot.jpg`). Write a password as "
        "${VARIABLE} to keep it out of your shell history — only the variable "
        "name is written to disk.\n\n"
        "Prints the camera's id. That id is the only handle you need "
        "afterwards, and it does not change."
    ),
)
@click.argument("camera")
@click.option("--label", default=None, help="A name for yourself, e.g. 'Dome cam'.")
def webcam_add_cmd(camera, label):
    target = camera.strip()

    if target.isdigit():
        index = int(target)
        # One probe, used for both jobs: telling the operator if nothing is
        # there, and recording the camera's resolution while it is open.
        device = _probe_index(index)
        _add(
            Camera(id="", kind=USB, index=index, label=label, specs=_specs(device)),
            absent_note=lambda: None if device else _nothing_at_index(index),
        )
        return

    scheme = urlsplit(target).scheme.lower()
    if not scheme:
        _fail(
            f"{target!r} is neither a device index nor a camera address.",
            "\nPass a device index for a webcam plugged in here:  arcsecond webcam add 0",
            "or an address for one on the network:  arcsecond webcam add rtsp://10.0.0.4/stream1",
            "\nAll-sky cameras are registered by path:  arcsecond allsky add <PATH>",
        )

    # Expanded only to validate it — what gets stored is what was typed.
    expanded = _expand_env_vars(target)
    if urlsplit(expanded).scheme.lower() not in SUPPORTED_SCHEMES:
        _fail(
            f"{redact_url(expanded)} cannot be used.",
            "Camera addresses must start with "
            + ", ".join(s + "://" for s in SUPPORTED_SCHEMES)
            + ".",
        )

    _add(Camera(id="", kind=NET, url=target, label=label))


def _probe_index(index: int):
    """The device at ``index`` right now, or None.

    Returns None rather than raising when OpenCV is missing or the probe
    fails: not knowing what is plugged in is a reason to say less, not a
    reason to refuse to register a camera.
    """
    try:
        from .sources.opencv import detect_webcams

        for device in detect_webcams():
            if device.identity == ("usb", index):
                return device
    except Exception:
        return None
    return None


def _specs(device) -> Optional[dict]:
    """Resolution and frame rate, as measured while the device was open.

    Recorded so that listing a camera can report them without opening it —
    `/detect` must stay answerable when a camera is busy or unplugged.
    """
    if device is None:
        return None
    extra = device.extra or {}
    specs = {
        "width": extra.get("width"),
        "height": extra.get("height"),
        "fps": extra.get("fps"),
    }
    kept = {k: v for k, v in specs.items() if v}
    return kept or None


def _nothing_at_index(index: int) -> str:
    """Said when a camera is registered while nothing is plugged in at its index.

    It is registered either way: a webcam that is unplugged right now is still
    a camera the operator owns, and refusing would mean re-typing the command
    later. Saying nothing would let a typo sit unnoticed until the proxy failed
    to open it.
    """
    return (
        f"nothing is at device index {index} right now. It stays registered — "
        "plug it in, then re-run this command to record its resolution."
    )


@webcam.command(
    name="forget",
    help=(
        "Stop remembering a webcam. Give the id printed by `arcsecond webcam`, "
        "e.g. `k3f`.\n\n"
        "Works for every kind of webcam, whether it is plugged in here or "
        "reached over the network. If the proxy is running, it stops serving "
        "the camera straight away."
    ),
)
@click.argument("camera_id")
def webcam_forget_cmd(camera_id):
    _forget(camera_id, WEBCAM_KINDS, "webcam")


@webcam.command(
    name="test",
    help=(
        "Pull one image from a camera and report what came back.\n\n"
        "CAMERA is the id of a registered camera, or an address you have not "
        "registered yet — so an address can be checked before it is added, and "
        "a registered camera can be checked without retyping its address."
    ),
)
@click.argument("camera")
@click.option(
    "--timeout",
    default=15.0,
    show_default=True,
    help="Seconds to wait for a first image.",
)
def webcam_test_cmd(camera, timeout):
    registered = store.find(camera)

    if registered is not None and registered.kind == USB:
        _test_usb(registered)
        return

    # Every camera registered by address is tested the same way, whether it is
    # a network camera or an all-sky camera published over HTTP.
    if registered is not None and registered.url:
        _test_url(_expand_env_vars(registered.url), timeout, suggest=False)
        return

    if registered is not None:
        _fail(
            f"{registered.id} is an all-sky camera writing to this machine.",
            f"\nIt reads images from {registered.target} — check that path directly.",
        )

    typed = camera.strip()
    if typed.isdigit():
        _test_usb(Camera(id=typed, kind=USB, index=int(typed)))
        return

    if not urlsplit(typed).scheme:
        _fail(
            f"no camera is registered as {typed!r}, and it is not an address.",
            "\nSee what is registered with:  arcsecond webcam",
        )

    _test_url(_expand_env_vars(typed), timeout, suggest=True, typed=typed)


def _test_usb(camera: Camera):
    _check_cv2()
    from .sources.opencv import OpenCVWebcamSource

    click.echo(f"Opening device index {camera.index} ...")

    async def _probe():
        source = OpenCVWebcamSource(camera.index)
        await source.open()
        try:
            return await source.read()
        finally:
            await source.close()

    try:
        frame = asyncio.run(_probe())
    except Exception as e:
        _fail(str(e))

    if not frame:
        _fail(f"device index {camera.index} opened, but sent no image.")

    click.echo(
        click.style("Success. ", fg="green")
        + f"Received an image of {len(frame) / 1024:.0f} kB."
    )


def _require_reachable_scheme(url: str):
    """Refuse an address we cannot speak, and check the extra it will need."""
    scheme = urlsplit(url).scheme.lower()
    if scheme not in SUPPORTED_SCHEMES:
        raise click.BadParameter(
            f"{redact_url(url)} cannot be used. Camera addresses must start with "
            f"{', '.join(s + '://' for s in SUPPORTED_SCHEMES)}."
        )
    if scheme in RTSP_SCHEMES:
        _check_cv2()
    else:
        _check_aiohttp()


def _grab_one_frame(url: str, timeout: float):
    """Connect, wait for a first image, and hand it back. Fails loudly."""

    async def _probe():
        source = build_network_source("test", url)
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
        return asyncio.run(asyncio.wait_for(_probe(), timeout + 5.0))
    except asyncio.TimeoutError:
        _fail(
            f"no image after {timeout:.0f} seconds. The address may be wrong, "
            "or the camera may be sending a format we cannot read."
        )
    except Exception as e:
        _fail(str(e))


def _test_url(url: str, timeout: float, suggest: bool, typed: str = ""):
    _require_reachable_scheme(url)
    click.echo(f"Connecting to {redact_url(url)} ...")

    frame = _grab_one_frame(url, timeout)
    if not frame:
        _fail(f"connected, but no image arrived within {timeout:.0f} seconds.")

    message = (
        click.style("Success. ", fg="green")
        + f"Received an image of {len(frame) / 1024:.0f} kB."
    )
    if suggest:
        # Suggest back exactly what was typed when a ${VARIABLE} was used, so
        # the line can be copied and will work. Only a password typed in the
        # clear is hidden — repeating that one on screen is the one real leak.
        safe = typed if typed != url else redact_url(url)
        message += f"\n\nRegister this camera with:\n\n  arcsecond webcam add '{safe}'"
    click.echo(message)


# ---------------------------------------------------------------------------
# `arcsecond allsky`
# ---------------------------------------------------------------------------


@click.group(
    invoke_without_command=True,
    help=(
        "List your all-sky cameras.\n\n"
        "With no sub-command, prints what is registered and probes nothing. "
        "Use `detect` to look at well-known locations, `add` to register a "
        "camera and `forget` to drop one."
    ),
)
@click.pass_context
def allsky(ctx):
    if ctx.invoked_subcommand is None:
        _list_registered(
            (ALLSKY,), "all-sky camera", "arcsecond allsky add /srv/allsky/latest.jpg"
        )


@allsky.command(
    name="detect",
    help=(
        "Look for all-sky cameras at well-known paths (Thomas Jacquin's allsky, "
        "indi-allsky) and report how they line up with what is registered.\n\n"
        "Registers nothing. A registered camera writing somewhere else is "
        "confirmed by looking at its own path, so it is not reported missing "
        "merely for being somewhere unusual."
    ),
)
def allsky_detect_cmd():
    try:
        cameras = store.all_cameras()
    except store.SourceStoreError as e:
        _fail(str(e))
    _print_detection(detection.report(cameras, (ALLSKY,)), (ALLSKY,))


@allsky.command(
    name="add",
    help=(
        "Register an all-sky camera, so that the proxy serves it.\n\n"
        "TARGET is the JPEG your all-sky software keeps up to date. Give a path "
        "when that software runs on this machine — a fixed file, a symlink, or "
        "a glob, in which case the newest matching file wins — or an "
        "`http://...` address when it runs on another machine and publishes "
        "the image. Write a password as ${VARIABLE} to keep it out of your "
        "shell history: only the variable name is written to disk.\n\n"
        "Prints the camera's id. That id is the only handle you need "
        "afterwards, and it does not change."
    ),
)
@click.argument("target")
@click.option("--label", default=None, help="A name for yourself, e.g. 'Roof'.")
def allsky_add_cmd(target, label):
    target = target.strip()
    if not target:
        _fail("give the path or address of the JPEG your all-sky software writes.")

    scheme = urlsplit(target).scheme.lower()

    if scheme in RTSP_SCHEMES:
        _fail(
            "an all-sky camera is registered by the JPEG it publishes, not by a "
            "video stream.",
            "\nA camera sending video is a webcam:  "
            f"arcsecond webcam add '{target}'",
        )

    if scheme in HTTP_SCHEMES:
        # Expanded only to validate it — what is stored is what was typed, so a
        # password stays a variable name on disk. Doing it here is what makes an
        # unset variable a complaint about the line just typed, rather than a
        # camera quietly missing from the next `proxy start`.
        _expand_env_vars(target)
        _add(Camera(id="", kind=ALLSKY, url=target, label=label))
        return

    # A single letter is a Windows drive, not a scheme: `C:\allsky\latest.jpg`
    # is a path and must stay one. Anything longer was meant as an address, and
    # registering it as a filename would only fail later, out of sight.
    if len(scheme) > 1:
        _fail(
            f"{target!r} is not a path, and {scheme}:// is not an address the "
            "proxy can read.",
            "\nAn all-sky camera is registered by path:  "
            "arcsecond allsky add /srv/allsky/latest.jpg",
            "or by address:  arcsecond allsky add http://sky.local/latest.jpg",
        )

    # Registered whether or not the file is there yet: all-sky software often
    # writes its first image only at dusk, and refusing until then would mean
    # coming back to retype this.
    def _absent_note():
        if detection.resolve_allsky_path(target) is not None:
            return None
        return (
            f"no image at {target} right now. It stays registered — the proxy "
            "will serve it as soon as one appears."
        )

    _add(Camera(id="", kind=ALLSKY, path=target, label=label), absent_note=_absent_note)


@allsky.command(
    name="forget",
    help=(
        "Stop remembering an all-sky camera. Give the id printed by "
        "`arcsecond allsky`, e.g. `r4t`.\n\n"
        "If the proxy is running, it stops serving the camera straight away."
    ),
)
@click.argument("camera_id")
def allsky_forget_cmd(camera_id):
    _forget(camera_id, (ALLSKY,), "all-sky camera")


# ---------------------------------------------------------------------------
# `arcsecond proxy`
# ---------------------------------------------------------------------------


@click.group(help="Start and inspect the proxy that serves your cameras.")
def proxy():
    pass


@proxy.command(
    name="start",
    help=(
        "Serve every registered camera — webcams, network cameras and all-sky "
        "cameras alike — over one proxy.\n\n"
        "Starts in the background and gives you your prompt back; stop it with "
        "`arcsecond proxy stop` from anywhere. Use --foreground to run it in "
        "this terminal and watch it instead.\n\n"
        "Registers nothing: run `arcsecond webcam add` or `arcsecond allsky "
        "add` first. Cameras added while it runs are picked up without a "
        "restart.\n\n"
        "Set LIVE_IMAGE_PROXY_URL=http://host.docker.internal:<PORT> in your "
        ".env so Arcsecond.local can reach the proxy."
    ),
)
@click.option(
    "--port", default=DEFAULT_PORT, show_default=True, help="TCP port to listen on."
)
@click.option("--host", default="0.0.0.0", show_default=True, help="Interface to bind.")
@click.option(
    "--log-level",
    default="INFO",
    show_default=True,
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    help="Logging verbosity.",
)
@click.option(
    "--foreground",
    is_flag=True,
    help="Run in this terminal and keep it, printing as it goes, instead of "
    "starting in the background. Ctrl-C stops it.",
)
@click.option(
    "--no-banner",
    is_flag=True,
    hidden=True,
    help="Skip the startup summary. Used when this process is the background "
    "proxy: its parent has already printed the summary to the terminal, and "
    "repeating it into the log buries whatever goes wrong next.",
)
def proxy_start_cmd(port, host, log_level, foreground, no_banner):
    _check_aiohttp()

    running = _running_proxy_port()
    if running is not None:
        _fail(
            f"a proxy is already running on port {running}.",
            "\nIt is already serving every registered camera, and picks up new "
            "ones by itself. To move it to another port:  arcsecond proxy stop",
        )

    try:
        cameras = store.expanded(store.all_cameras(), _expand_env_vars)
    except store.SourceStoreError as e:
        _fail(str(e))

    if foreground:
        _run_in_this_terminal(host, port, log_level, cameras, banner=not no_banner)
    else:
        _run_detached(host, port, log_level, cameras)


def _describe_cameras(cameras):
    if cameras:
        click.echo(f"Serving {len(cameras)} camera(s):\n")
        _print_table(
            [(c.id, c.display_kind, c.target, c.label or "") for c in cameras],
            ("ID", "KIND", "CAMERA", "NAME"),
        )
        click.echo("")
    else:
        click.echo(
            click.style(
                "No camera is registered — nothing to serve yet.\n", fg="yellow"
            )
            + "Register one and the proxy will pick it up without a restart:\n\n"
            "  arcsecond webcam add 0\n"
            "  arcsecond allsky add /srv/allsky/latest.jpg\n"
        )


def _run_in_this_terminal(host, port, log_level, cameras, banner=True):
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    )

    if banner:
        click.echo(
            click.style("Arcsecond live-image proxy", bold=True)
            + f" listening on {host}:{port}\n"
            f"  Camera list  →  http://{host}:{port}/detect\n"
            f"  Streaming    →  ws://{host}:{port}/stream/{{id}}\n"
        )
        _describe_cameras(cameras)
        click.echo(
            "Set in your .env file:\n"
            f"  LIVE_IMAGE_PROXY_URL=http://host.docker.internal:{port}\n\n"
            "Press Ctrl-C to stop, or from any other terminal:  "
            "arcsecond proxy stop"
        )

    from .proxy import run

    try:
        run(host=host, port=port, cameras=cameras)
    except OSError as e:
        # Almost always the port being taken. Said plainly here rather than as
        # a traceback, because this is also what a detached proxy writes to its
        # log — and that log is what `proxy start` shows when it cannot come up.
        if e.errno == errno.EADDRINUSE:
            _fail(
                f"port {port} is already taken by something else on this machine.",
                f"\nStart the proxy on another port:  arcsecond proxy start "
                f"--port {port + 1}",
            )
        _fail(f"the proxy could not listen on {host}:{port}: {e}")


def _run_detached(host, port, log_level, cameras):
    """Launch the proxy in the background and give the terminal back.

    The proxy is a service the Arcsecond containers talk to, not something to
    sit and watch, so it should no more own a terminal than the database does.
    Handing the prompt straight back is also what makes `stop` and `status`
    mean anything: a proxy you can only end with Ctrl-C in one particular
    window is not really stoppable from anywhere else.

    It is started as a fresh `python -m arcsecond.cli proxy start
    --foreground`, on this very interpreter, rather than forked — fork has no
    Windows equivalent, and this way the background proxy is running exactly
    the code the command that launched it was running.
    """
    log_file = runtime.log_path()
    command = [
        sys.executable,
        "-m",
        "arcsecond.cli",
        "proxy",
        "start",
        "--foreground",
        "--no-banner",
        "--host",
        str(host),
        "--port",
        str(port),
        "--log-level",
        log_level,
    ]

    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handle = open(log_file, "ab")
    except OSError as e:
        _fail(
            f"cannot write the proxy's log at {log_file}: {e}",
            "\nRun it in this terminal instead:  arcsecond proxy start --foreground",
        )

    # The environment is inherited, which is what carries the ${VARIABLE} a
    # camera password was written as. A proxy started from a shell that never
    # set it would drop that camera and say so in the log.
    extra = {}
    if sys.platform == "win32":
        extra["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
    else:
        # Its own session, so closing the terminal — or Ctrl-C in it — does not
        # take the proxy down with it.
        extra["start_new_session"] = True

    with handle:
        handle.write(f"\n=== proxy starting on {host}:{port} ===\n".encode("utf-8"))
        handle.flush()
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=handle,
                stderr=handle,
                **extra,
            )
        except OSError as e:
            _fail(f"could not start the proxy: {e}")

    if not _wait_until_answering(port, process, START_TIMEOUT):
        _report_failed_start(port, process, log_file)

    click.echo(
        click.style("The proxy is running", fg="green")
        + f" on {host}:{port}  (pid {process.pid})\n"
    )
    _describe_cameras(cameras)
    click.echo(
        "Set in your .env file:\n"
        f"  LIVE_IMAGE_PROXY_URL=http://host.docker.internal:{port}\n\n"
        f"  Log   →  {log_file}\n"
        "  Stop  →  arcsecond proxy stop"
    )


def _wait_until_answering(port: int, process, timeout: float) -> bool:
    """Wait for the background proxy to come up, or to fall over trying."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _proxy_is_running(port):
            return True
        if process.poll() is not None:
            return False  # it exited; the log will say why
        time.sleep(_START_POLL_INTERVAL)
    return _proxy_is_running(port)


def _report_failed_start(port: int, process, log_file):
    """Say why the background proxy did not come up, using its own last words.

    Without this the failure would be silent — the proxy writes to a log file
    nobody has been told to look at yet, and the command that launched it would
    otherwise just report success.
    """
    process.poll()
    try:
        tail = log_file.read_text(encoding="utf-8", errors="replace").strip()
        tail = "\n".join(tail.splitlines()[-12:])
    except OSError:
        tail = ""

    if process.returncode is None:
        process.kill()
        reason = f"it did not answer on port {port} within {START_TIMEOUT:.0f}s."
    else:
        reason = f"it stopped immediately (exit code {process.returncode})."

    lines = [f"\nThe last of its log ({log_file}):\n", tail] if tail else []
    lines.append(
        "\nTo watch it start in this terminal instead:  "
        "arcsecond proxy start --foreground"
    )
    _fail("the proxy would not start: " + reason, *lines)


@proxy.command(
    name="status",
    help="Say whether the proxy is running, and what it is serving.",
)
def proxy_status_cmd():
    port = _running_proxy_port()
    if port is None:
        click.echo("The proxy is not running.\n\nStart it with:  arcsecond proxy start")
        return

    click.echo(
        click.style("The proxy is running", fg="green")
        + f" on port {port}  (http://127.0.0.1:{port}/detect)\n"
    )

    served = _call_proxy(port, "/detect")
    if not isinstance(served, list):
        click.echo("It would not say what it is serving.")
        return

    if not served:
        click.echo(
            "It is serving no camera.\n\n"
            "Register one and it will be picked up straight away:\n"
            "  arcsecond webcam add 0"
        )
    else:
        click.echo(f"Serving {len(served)} camera(s):\n")
        _print_table(
            [
                (
                    item.get("id", ""),
                    (item.get("extra") or {}).get("transport", item.get("kind", "")),
                    (item.get("extra") or {}).get("url")
                    or (item.get("extra") or {}).get("path")
                    or f"device index {(item.get('extra') or {}).get('index')}",
                    item.get("label", ""),
                )
                for item in served
            ],
            ("ID", "TRANSPORT", "CAMERA", "NAME"),
        )

    click.echo("\nStop it with:  arcsecond proxy stop")


@proxy.command(
    name="stop",
    help=(
        "Stop the running proxy.\n\n"
        "The mirror of `start`, and it works from any terminal — the proxy "
        "records where it is when it starts, so there is nothing to remember "
        "and no port to type. Registered cameras are untouched: this stops "
        "serving them, `forget` is what drops one."
    ),
)
@click.option(
    "--timeout",
    default=STOP_TIMEOUT,
    show_default=True,
    help="Seconds to wait for it to shut down before insisting.",
)
def proxy_stop_cmd(timeout):
    running = _running_proxy()
    if running is None:
        click.echo("The proxy is not running. Nothing to stop.")
        return

    port, pid = running
    if pid is None:
        _fail(
            f"a proxy is answering on port {port}, but would not say which "
            "process it is.",
            "\nIt is from an older version of this CLI, which cannot be stopped "
            "from here. Press Ctrl-C in the terminal it is running in.",
        )

    click.echo(f"Stopping the proxy on port {port} (pid {pid}) ...")

    # Asked to leave first. The proxy closes its viewers' connections and
    # releases every camera on the way out; killing it outright would leave a
    # USB device open until the OS got round to it.
    if not _signal_proxy(pid, signal.SIGTERM):
        return

    if _wait_for_exit(port, pid, timeout):
        click.echo(click.style("Stopped.", fg="green"))
        return

    click.echo(
        click.style("It did not stop when asked. ", fg="yellow")
        + f"Ending it now (pid {pid})."
    )
    if not _signal_proxy(pid, _HARD_SIGNAL):
        return

    if _wait_for_exit(port, pid, _HARD_TIMEOUT):
        click.echo(click.style("Stopped.", fg="green"))
        runtime.clear()
        return

    _fail(
        f"the proxy on port {port} is still answering.",
        f"\nIts process is {pid}. Something is holding it open that this "
        "command cannot clear.",
    )


def _signal_proxy(pid: int, sig) -> bool:
    """Signal the proxy. False, having said why, if it could not be reached."""
    try:
        os.kill(pid, sig)
        return True
    except ProcessLookupError:
        # Gone between the health check and now. That is the outcome asked for.
        click.echo(click.style("Stopped.", fg="green"))
        runtime.clear()
        return False
    except PermissionError:
        _fail(
            f"not allowed to stop process {pid}.",
            "\nIt is running as another user. Stop it from the terminal it was "
            "started in.",
        )
    except OSError as e:
        _fail(f"could not stop process {pid}: {e}")


def _has_exited(port: int, pid: int) -> bool:
    """Whether the proxy process has actually finished.

    Not "has it stopped answering": aiohttp closes the listening socket as the
    *first* step of shutting down, so the port goes quiet while the proxy is
    still winding down and still holding its cameras open. Reporting success
    there would hand back a machine whose webcam is not free yet.
    """
    if sys.platform == "win32":
        # On Windows os.kill terminates a process rather than testing for one,
        # even with signal 0, so the proxy's own goodbye is used instead: it
        # removes its runtime note on the way out.
        return runtime.read() is None and not _proxy_is_running(port)

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        # It exists; it just is not ours to signal.
        return False
    return False


def _wait_for_exit(port: int, pid: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while True:
        if _has_exited(port, pid):
            runtime.clear()
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(_STOP_POLL_INTERVAL)


# ---------------------------------------------------------------------------
# What used to be here
#
# `start` used to live on both camera groups and quietly registered cameras as
# a side effect, and network cameras had a group of their own. Both are gone.
# They are answered rather than left to Click's "No such command", because the
# whole point of the change is that the old shape was hard to guess at.
# ---------------------------------------------------------------------------

_UNPROCESSED = {"ignore_unknown_options": True, "allow_extra_args": True}


def _moved(*lines: str):
    for line in lines:
        click.echo(line)
    raise SystemExit(1)


@webcam.command(name="start", hidden=True, context_settings=_UNPROCESSED)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def webcam_start_removed(args):
    _moved(
        click.style("Error: ", fg="red")
        + "`arcsecond webcam start` has been split in two.",
        "\nRegistering a camera and starting the proxy are separate now:",
        "\n  arcsecond webcam add 0                        # a webcam plugged in here",
        "  arcsecond webcam add rtsp://10.0.0.4/stream1  # one on the network",
        "  arcsecond proxy start                         # serve everything registered",
        "\nSee what you already have with:  arcsecond webcam",
    )


@allsky.command(name="start", hidden=True, context_settings=_UNPROCESSED)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def allsky_start_removed(args):
    _moved(
        click.style("Error: ", fg="red")
        + "`arcsecond allsky start` has been split in two.",
        "\nRegistering a camera and starting the proxy are separate now:",
        "\n  arcsecond allsky add /srv/allsky/latest.jpg  # the JPEG it keeps updated",
        "  arcsecond proxy start                        # serve everything registered",
        "\nSee what you already have with:  arcsecond allsky",
    )


@click.command(name="netcam", hidden=True, context_settings=_UNPROCESSED)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def netcam(args):
    _moved(
        click.style("Error: ", fg="red")
        + "`arcsecond netcam` is gone. A camera reached over the network is a "
        "webcam.",
        "\nThe same commands cover both:",
        "\n  arcsecond webcam                               # list them all",
        "  arcsecond webcam test rtsp://10.0.0.4/stream1  # check an address",
        "  arcsecond webcam add  rtsp://10.0.0.4/stream1  # register it",
        "  arcsecond webcam forget <ID>",
    )
