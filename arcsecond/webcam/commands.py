"""
Click command group: ``arcsecond webcam``

Sub-commands
------------
detect      Scan for attached webcams and print a summary table.
start       Start the native webcam proxy server so Docker containers can
            reach USB webcams on this host via host.docker.internal.
"""

import json
import logging

import click

logger = logging.getLogger(__name__)


@click.group(help="Manage the native webcam proxy for Docker containers.")
def webcam():
    pass


@webcam.command(name='detect', help="Scan for locally attached webcams and print their details.")
def detect_cmd():
    try:
        import cv2  # noqa: F401
    except ImportError:
        click.echo(
            click.style("Error: ", fg='red') +
            "opencv-python-headless is not installed.\n"
            "Run:  pip install opencv-python-headless"
        )
        raise SystemExit(1)

    from arcsecond.webcam.proxy import _detect_webcams_sync
    webcams = _detect_webcams_sync()

    if not webcams:
        click.echo("No webcams detected.")
        return

    click.echo(f"Found {len(webcams)} webcam(s):\n")
    for w in webcams:
        click.echo(
            f"  index={w.index}  {w.width}×{w.height}  {w.fps:.1f} fps"
        )


@webcam.command(name='start', help=(
    "Start the webcam proxy server.\n\n"
    "The proxy exposes two endpoints that the Arcsecond backend container can "
    "reach via host.docker.internal:\n\n"
    "  GET  /detect              — list attached webcams (JSON)\n\n"
    "  WS   /stream/{index}      — JPEG frame stream\n\n"
    "Set WEBCAM_PROXY_URL=http://host.docker.internal:<PORT> in your .env file "
    "so the backend knows where to find the proxy."
))
@click.option('--port', default=8765, show_default=True, help="TCP port to listen on.")
@click.option('--host', default='0.0.0.0', show_default=True, help="Interface to bind.")
@click.option('--log-level', default='INFO', show_default=True,
              type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR'], case_sensitive=False),
              help="Logging verbosity.")
def start_cmd(port, host, log_level):
    try:
        import aiohttp  # noqa: F401
    except ImportError:
        click.echo(
            click.style("Error: ", fg='red') +
            "aiohttp is not installed.\n"
            "Run:  pip install aiohttp"
        )
        raise SystemExit(1)

    try:
        import cv2  # noqa: F401
    except ImportError:
        click.echo(
            click.style("Error: ", fg='red') +
            "opencv-python-headless is not installed.\n"
            "Run:  pip install opencv-python-headless"
        )
        raise SystemExit(1)

    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s  %(levelname)-8s  %(name)s  %(message)s',
    )

    click.echo(
        click.style("Arcsecond webcam proxy", bold=True) +
        f" listening on {host}:{port}\n"
        f"  Detection  →  http://{host}:{port}/detect\n"
        f"  Streaming  →  ws://{host}:{port}/stream/{{index}}\n\n"
        "Set in your .env file:\n"
        f"  WEBCAM_PROXY_URL=http://host.docker.internal:{port}\n\n"
        "Press Ctrl-C to stop."
    )

    from arcsecond.webcam.proxy import run
    run(host=host, port=port)
