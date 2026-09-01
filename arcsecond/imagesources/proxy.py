"""
Live-image proxy server for the Arcsecond CLI.

Why this exists
---------------
The Arcsecond backend runs inside Docker Desktop (Windows / macOS), which does
not forward USB devices — and may not have access to host filesystem paths
where all-sky software writes images. This small aiohttp server runs
**natively** on the host and exposes:

    GET  /health             → liveness, plus this proxy's pid to a local caller
    GET  /detect             → JSON list of available sources
    WS   /stream/{id}        → continuous JPEG-frame stream (base64-in-JSON)
    POST /sources            → register cameras into the running proxy
    DEL  /sources/{id}       → unregister one

The last two answer only to callers on this same machine, so that the proxy
stays read-only to everyone else on the network. They are what lets a camera
registered or forgotten while the proxy is up take effect immediately, instead
of at the next restart.

A source id is the camera's three-character id — ``k3f`` — exactly as
``arcsecond webcam`` prints it. ``/detect`` lists what is registered without
opening or contacting anything, so one camera being switched off never holds
up the answer for the others.

Network cameras are served by the same proxy even though they are not attached
to the host at all: the proxy connects out to them over the network, so one
proxy covers every camera it can reach. They are not a separate kind on the
wire — ``kind`` is ``webcam`` for both, and ``extra.transport`` says whether it
is reached over ``usb``, ``rtsp`` or ``http``.

The backend reads the ``LIVE_IMAGE_PROXY_URL`` environment variable
(``WEBCAM_PROXY_URL`` is accepted as a deprecated fallback). When set, it
delegates detection and streaming to this proxy.

Started by ``arcsecond proxy start``, which serves every camera registered
with ``arcsecond webcam add`` and ``arcsecond allsky add``. Starting the proxy
never registers anything by itself, and registering never starts it.
"""

import asyncio
import base64
import ipaddress
import json
import logging
import os
from dataclasses import asdict
from typing import Optional

from . import runtime, store
from .registry import Registry

logger = logging.getLogger(__name__)


def _is_loopback(request) -> bool:
    """Whether the request came from this same machine.

    Judged on the peer of the socket only. Headers such as X-Forwarded-For are
    set freely by whoever is calling, so trusting one here would hand the whole
    guard to any stranger on the network.
    """
    remote = request.remote
    if not remote:
        return False
    try:
        return ipaddress.ip_address(remote).is_loopback
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# aiohttp request handlers
# ---------------------------------------------------------------------------


async def handle_health(request):
    """Confirm this is one of our proxies, and say which process it is.

    The pid is what lets `arcsecond proxy stop` signal the right process
    instead of trusting the pid in the runtime file — a file outlives a proxy
    that was killed, and by then the number in it may belong to something else
    entirely. It is told only to callers on this machine: nobody on the
    network needs it, and the point of /health for them is just "yes, alive".
    """
    from aiohttp import web

    answer = {"status": "ok"}
    if _is_loopback(request):
        answer["pid"] = os.getpid()
    return web.json_response(answer)


async def handle_detect(request):
    """List the registered cameras. Nothing is opened or contacted.

    Kept at /detect because that is the path the backend already calls, but it
    no longer probes: what this proxy serves is what was registered, and
    finding out which of them are switched on right now is
    `arcsecond webcam detect`'s job, not something to do on every page load.
    """
    from aiohttp import web

    registry: Registry = request.app["registry"]
    return web.json_response([asdict(i) for i in registry.infos()])


async def handle_add_sources(request):
    """Register cameras into the running proxy (same machine only).

    This is what lets `arcsecond webcam add` take effect on a proxy that is
    already up, rather than the operator having to restart it.
    """
    from aiohttp import web

    if not _is_loopback(request):
        logger.warning(
            "Live-image proxy: refused a registration from %s.", request.remote
        )
        return web.json_response(
            {"error": "Cameras can only be registered from this machine."}, status=403
        )

    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"error": "Expected a JSON body."}, status=400)

    entries = payload.get("cameras") if isinstance(payload, dict) else None
    if not isinstance(entries, list) or not entries:
        return web.json_response(
            {"error": 'Expected a JSON body of the form {"cameras": [...]}.'},
            status=400,
        )

    cameras = []
    for entry in entries:
        if not isinstance(entry, dict) or not entry.get("id"):
            return web.json_response(
                {"error": f"Malformed registration: {entry!r}"}, status=400
            )
        camera = store.camera_from_json(entry["id"], entry)
        if camera is None:
            return web.json_response(
                {"error": f"Malformed registration: {entry!r}"}, status=400
            )
        cameras.append(camera)

    registry: Registry = request.app["registry"]
    added = registry.add(cameras)
    for source_id in added:
        logger.info("Live-image proxy: %s registered.", source_id)

    return web.json_response({"added": added})


async def handle_remove_source(request):
    """Unregister one camera from the running proxy (same machine only)."""
    from aiohttp import web

    if not _is_loopback(request):
        logger.warning("Live-image proxy: refused a removal from %s.", request.remote)
        return web.json_response(
            {"error": "Cameras can only be removed from this machine."}, status=403
        )

    source_id = (request.match_info["id"] or "").strip()
    if not source_id:
        return web.json_response(
            {"error": "Expected a camera id, such as k3f."}, status=400
        )

    registry: Registry = request.app["registry"]
    removed = registry.remove(source_id)

    if removed:
        logger.info("Live-image proxy: %s removed.", source_id)
    return web.json_response({"removed": removed})


async def _viewer_has_gone(ws, delay: float) -> bool:
    """Pause between frames, and say whether the viewer left during the pause.

    A plain sleep would not notice. Nothing in this handler reads from the
    socket, so a viewer that closed its tab is only discovered when a send
    fails — and a camera that sends only when its picture changes may not send
    again for minutes, or at all overnight. The device would stay open the
    whole time, for nobody.

    Waiting *on the socket* also means shutdown is immediate: closing the
    websocket wakes this up rather than leaving it mid-sleep.
    """
    from aiohttp import WSMsgType

    if delay <= 0:
        # A camera streaming as fast as it can. It sends constantly, so a
        # departed viewer surfaces as a failed send; do not pay for a timeout
        # on every frame.
        await asyncio.sleep(0)
        return False

    try:
        message = await ws.receive(timeout=delay)
    except asyncio.TimeoutError:
        return False  # nothing was said, which is the normal case
    return message.type in (
        WSMsgType.CLOSE,
        WSMsgType.CLOSING,
        WSMsgType.CLOSED,
        WSMsgType.ERROR,
    )


async def handle_stream(request):
    from aiohttp import web

    registry: Registry = request.app["registry"]
    source_id = request.match_info["id"]

    ws = web.WebSocketResponse()
    await ws.prepare(request)

    # Registered so that shutdown can close it. Without this the loop below
    # runs until the viewer goes away, and aiohttp waits for the handler to
    # return before exiting — so a proxy with someone watching would sit
    # through Ctrl-C and `proxy stop` alike.
    request.app["websockets"].add(ws)

    try:
        acquired = await registry.acquire(source_id)
    except KeyError as e:
        # e.args[0] rather than str(e): KeyError's str() wraps the message in
        # its own quotes, and this text is shown to whoever is watching.
        message = e.args[0] if e.args else "Unknown camera"
        logger.error("Live-image proxy: %s", message)
        await ws.send_str(json.dumps({"type": "error", "message": message}))
        await ws.close()
        request.app["websockets"].discard(ws)
        return ws
    except Exception as e:
        logger.error("Live-image proxy: cannot open %s: %s", source_id, e)
        await ws.send_str(json.dumps({"type": "error", "message": str(e)}))
        await ws.close()
        request.app["websockets"].discard(ws)
        return ws

    logger.info(
        "Live-image proxy: client connected to stream %s (refcount=%d)",
        source_id,
        acquired.refcount,
    )

    # Tolerate a few transient read failures before giving up. ~2 s at the
    # source's poll rate covers most one-off DirectShow hiccups.
    max_consecutive_failures = max(1, int(2.0 / max(acquired.poll_interval, 0.01)))
    consecutive_failures = 0

    try:
        while not ws.closed:
            try:
                jpeg: Optional[bytes] = await acquired.read()
            except Exception as e:
                consecutive_failures += 1
                if consecutive_failures >= max_consecutive_failures:
                    msg = f"frame read failed for {source_id}: {e}"
                    logger.warning(
                        "Live-image proxy: %s (after %d attempts)",
                        msg,
                        consecutive_failures,
                    )
                    await ws.send_str(json.dumps({"type": "error", "message": msg}))
                    break
                await asyncio.sleep(acquired.poll_interval)
                continue

            consecutive_failures = 0
            if jpeg is not None:
                b64 = base64.b64encode(jpeg).decode("ascii")
                await ws.send_str(
                    json.dumps(
                        {
                            "type": "frame",
                            "format": "jpeg/base64",
                            "data": b64,
                        }
                    )
                )
            if await _viewer_has_gone(ws, acquired.poll_interval):
                break
    except (ConnectionResetError, ConnectionError):
        pass
    finally:
        request.app["websockets"].discard(ws)
        remaining = await acquired.release()
        logger.info(
            "Live-image proxy: client disconnected from %s (refcount=%d).",
            source_id,
            remaining,
        )

    return ws


# ---------------------------------------------------------------------------
# Server entry-point
# ---------------------------------------------------------------------------


# How long to wait for viewers to go away once shutdown has begun. They are
# asked to leave first (see _close_websockets), so this is only a backstop —
# but it has to be short, because it is what an operator waits through after
# pressing Ctrl-C or running `arcsecond proxy stop`.
SHUTDOWN_TIMEOUT = 5.0


async def _close_websockets(app):
    """Send every viewer away, so their handlers return and the proxy can exit.

    aiohttp waits for in-flight handlers before it finishes shutting down, and
    a streaming handler loops until its socket closes. Nothing closes it on its
    own, so without this the proxy would ignore Ctrl-C for as long as somebody
    was watching.
    """
    from aiohttp import WSCloseCode

    for ws in set(app["websockets"]):
        await ws.close(code=WSCloseCode.GOING_AWAY, message=b"proxy shutting down")


def build_app(cameras: Optional[list] = None):
    """The configured aiohttp application, wired but not running."""
    from aiohttp import web

    app = web.Application()
    app["registry"] = Registry(cameras=cameras)
    app["websockets"] = set()
    app.on_shutdown.append(_close_websockets)

    app.router.add_get("/health", handle_health)
    app.router.add_get("/detect", handle_detect)
    app.router.add_get("/stream/{id}", handle_stream)
    app.router.add_post("/sources", handle_add_sources)
    app.router.add_delete("/sources/{id}", handle_remove_source)
    return app


def run(
    host: str = "0.0.0.0",
    port: int = 8765,
    cameras: Optional[list] = None,
):
    """Build and run the aiohttp application (blocking)."""
    from aiohttp import web

    app = build_app(cameras)

    logger.info("Live-image proxy starting on %s:%d", host, port)
    # Recorded so that `add`, `forget` and `proxy status` can find this proxy
    # without the operator having to remember the port. Cleared on the way out,
    # and never trusted without a health check — see runtime.py.
    runtime.write(host, port)
    try:
        web.run_app(
            app,
            host=host,
            port=port,
            shutdown_timeout=SHUTDOWN_TIMEOUT,
            print=lambda msg: logger.info(msg),
        )
    finally:
        runtime.clear()
