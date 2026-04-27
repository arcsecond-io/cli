"""
Click command groups: ``arcsecond webcam`` and ``arcsecond allsky``.

Both groups talk to the same proxy. ``webcam`` is kept for backward
compatibility; ``allsky`` is the new entry point for fisheye / all-sky
cameras whose driver software writes JPEGs to disk.
"""

import logging

import click

from .registry import AllskyOverride
from .sources.filewatch import detect_allsky
from .sources.opencv import detect_webcams

logger = logging.getLogger(__name__)


def _check_aiohttp():
    try:
        import aiohttp  # noqa: F401
    except ImportError:
        click.echo(
            click.style("Error: ", fg='red') +
            "aiohttp is not installed.\n"
            "Run:  pip install 'arcsecond[webcam]'"
        )
        raise SystemExit(1)


def _check_cv2():
    try:
        import cv2  # noqa: F401
    except ImportError:
        click.echo(
            click.style("Error: ", fg='red') +
            "opencv-python-headless is not installed.\n"
            "Run:  pip install 'arcsecond[webcam]'"
        )
        raise SystemExit(1)


def _parse_allsky_overrides(values: tuple[str, ...]) -> list[AllskyOverride]:
    overrides: list[AllskyOverride] = []
    for v in values:
        if '=' not in v:
            raise click.BadParameter(f"--allsky must be id=path, got {v!r}")
        sid, _, path = v.partition('=')
        sid, path = sid.strip(), path.strip()
        if not sid or not path:
            raise click.BadParameter(f"--allsky must be id=path, got {v!r}")
        overrides.append(AllskyOverride(id=sid, path=path))
    return overrides


def _run_proxy(host: str, port: int, log_level: str, allsky_overrides):
    _check_aiohttp()

    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s  %(levelname)-8s  %(name)s  %(message)s',
    )

    click.echo(
        click.style("Arcsecond live-image proxy", bold=True) +
        f" listening on {host}:{port}\n"
        f"  Detection  →  http://{host}:{port}/detect\n"
        f"  Streaming  →  ws://{host}:{port}/stream/{{id}}\n\n"
        "Set in your .env file:\n"
        f"  LIVE_IMAGE_PROXY_URL=http://host.docker.internal:{port}\n\n"
        "Press Ctrl-C to stop."
    )

    from .proxy import run
    run(host=host, port=port, allsky_overrides=allsky_overrides)


# ---------------------------------------------------------------------------
# Shared options
# ---------------------------------------------------------------------------

_start_options = [
    click.option('--port', default=8765, show_default=True, help="TCP port to listen on."),
    click.option('--host', default='0.0.0.0', show_default=True, help="Interface to bind."),
    click.option('--log-level', default='INFO', show_default=True,
                 type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR'], case_sensitive=False),
                 help="Logging verbosity."),
    click.option('--allsky', 'allsky', multiple=True, metavar='ID=PATH',
                 help="Register an all-sky source. PATH may be a file or a glob. "
                      "Repeat for multiple cameras. If omitted, well-known paths "
                      "are auto-discovered."),
]


def _add_options(options):
    def _wrap(fn):
        for opt in reversed(options):
            fn = opt(fn)
        return fn
    return _wrap


# ---------------------------------------------------------------------------
# `arcsecond webcam` group  (kept for backward compatibility)
# ---------------------------------------------------------------------------

@click.group(help="Manage the native live-image proxy (USB webcams + all-sky).")
def webcam():
    pass


@webcam.command(name='detect', help="Scan for locally attached webcams and print their details.")
def webcam_detect_cmd():
    _check_cv2()
    cams = detect_webcams()
    if not cams:
        click.echo("No webcams detected.")
        return
    click.echo(f"Found {len(cams)} webcam(s):\n")
    for c in cams:
        e = c.extra or {}
        click.echo(f"  {c.id}  {e.get('width')}×{e.get('height')}  {e.get('fps', 0):.1f} fps")


@webcam.command(name='start', help=(
    "Start the live-image proxy server.\n\n"
    "Exposes:\n\n"
    "  GET  /detect              — list available sources (JSON)\n\n"
    "  WS   /stream/{id}         — JPEG frame stream\n\n"
    "Source ids are e.g. webcam:0, allsky:roof. Bare numeric ids "
    "(/stream/0) are accepted for backward compatibility.\n\n"
    "Set LIVE_IMAGE_PROXY_URL=http://host.docker.internal:<PORT> in your "
    ".env so the backend can reach the proxy."
))
@_add_options(_start_options)
def webcam_start_cmd(port, host, log_level, allsky):
    overrides = _parse_allsky_overrides(allsky)
    _run_proxy(host, port, log_level, overrides)


# ---------------------------------------------------------------------------
# `arcsecond allsky` group  (new)
# ---------------------------------------------------------------------------

@click.group(help="Manage all-sky camera image sources.")
def allsky():
    pass


@allsky.command(name='detect', help=(
    "Auto-discover all-sky sources at well-known paths "
    "(Thomas Jacquin's allsky, indi-allsky)."
))
def allsky_detect_cmd():
    found = detect_allsky()
    if not found:
        click.echo("No all-sky sources discovered at well-known paths.")
        click.echo("\nIf your software writes images elsewhere, register a custom path with:\n")
        click.echo("  arcsecond allsky start --allsky <id>=<path-to-jpeg-or-glob>")
        return
    click.echo(f"Found {len(found)} all-sky source(s):\n")
    for s in found:
        click.echo(f"  {s.id}  →  {(s.extra or {}).get('path')}")


@allsky.command(name='start', help=(
    "Start the live-image proxy server (same proxy as `arcsecond webcam start`).\n\n"
    "Use --allsky id=path to register custom all-sky paths in addition to "
    "auto-discovered ones."
))
@_add_options(_start_options)
def allsky_start_cmd(port, host, log_level, allsky):
    overrides = _parse_allsky_overrides(allsky)
    _run_proxy(host, port, log_level, overrides)
