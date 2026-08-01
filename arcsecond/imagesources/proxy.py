"""
Live-image proxy server for the Arcsecond CLI.

Why this exists
---------------
The Arcsecond backend runs inside Docker Desktop (Windows / macOS), which does
not forward USB devices — and may not have access to host filesystem paths
where all-sky software writes images. This small aiohttp server runs
**natively** on the host and exposes:

    GET  /detect             → JSON list of available sources
    WS   /stream/{id}        → continuous JPEG-frame stream (base64-in-JSON)
    POST /sources            → register cameras into the running proxy
    DEL  /sources/{id}       → unregister one

The last two answer only to callers on this same machine, so that the proxy
stays read-only to everyone else on the network. They are what lets each
`arcsecond ... start` command be run separately, at different times, without
the second one trying to bind a port the first already holds.

Source ids look like ``webcam:0``, ``allsky:roof`` or ``netcam:dome``. For
backward compatibility, a bare numeric id (``/stream/0``) is treated as
``webcam:0``.

Network cameras are served by the same proxy even though they are not attached
to the host at all: the proxy connects out to them over the network, so one
proxy covers every camera it can reach.

The backend reads the ``LIVE_IMAGE_PROXY_URL`` environment variable
(``WEBCAM_PROXY_URL`` is accepted as a deprecated fallback). When set, it
delegates detection and streaming to this proxy.

Started by ``arcsecond webcam start`` (USB and network cameras) or
``arcsecond allsky start`` (all-sky cameras). Whichever runs first puts the
proxy up; the other hands its cameras to it and exits.
"""

import asyncio
import base64
import ipaddress
import json
import logging
from dataclasses import asdict
from typing import Optional

from .registry import AllskyOverride, NetcamOverride, Registry

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
    from aiohttp import web

    return web.json_response({"status": "ok"})


async def handle_detect(request):
    from aiohttp import web

    registry: Registry = request.app["registry"]
    loop = asyncio.get_running_loop()
    infos = await loop.run_in_executor(None, registry.detect)
    return web.json_response([asdict(i) for i in infos])


async def handle_add_sources(request):
    """Register cameras into the running proxy (same machine only).

    This is what lets `arcsecond allsky start` join a proxy that `arcsecond
    webcam start` already put on this port, instead of failing to bind it.
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

    try:
        allsky = [
            AllskyOverride(id=e["id"], path=e["path"])
            for e in payload.get("allsky") or []
        ]
        netcam = [
            NetcamOverride(id=e["id"], url=e["url"])
            for e in payload.get("netcam") or []
        ]
    except (KeyError, TypeError) as e:
        return web.json_response({"error": f"Malformed registration: {e}"}, status=400)

    registry: Registry = request.app["registry"]
    added = registry.add_sources(allsky=allsky, netcam=netcam)
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

    source_id = request.match_info["id"]
    kind, _, name = source_id.partition(":")
    if not name:
        return web.json_response(
            {"error": f"Expected an id such as allsky:roof, got {source_id!r}."},
            status=400,
        )

    registry: Registry = request.app["registry"]
    try:
        removed = registry.remove_source(kind, name)
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)

    if removed:
        logger.info("Live-image proxy: %s removed.", source_id)
    return web.json_response({"removed": removed})


async def handle_stream(request):
    from aiohttp import web

    registry: Registry = request.app["registry"]
    source_id = request.match_info["id"]

    ws = web.WebSocketResponse()
    await ws.prepare(request)

    try:
        acquired = await registry.acquire(source_id)
    except KeyError as e:
        logger.error("Live-image proxy: %s", e)
        await ws.send_str(json.dumps({"type": "error", "message": str(e)}))
        await ws.close()
        return ws
    except Exception as e:
        logger.error("Live-image proxy: cannot open %s: %s", source_id, e)
        await ws.send_str(json.dumps({"type": "error", "message": str(e)}))
        await ws.close()
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
            await asyncio.sleep(acquired.poll_interval)
    except (ConnectionResetError, ConnectionError):
        pass
    finally:
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


def run(
    host: str = "0.0.0.0",
    port: int = 8765,
    allsky_overrides: Optional[list[AllskyOverride]] = None,
    netcam_overrides: Optional[list[NetcamOverride]] = None,
):
    """Build and run the aiohttp application (blocking)."""
    from aiohttp import web

    app = web.Application()
    app["registry"] = Registry(
        allsky_overrides=allsky_overrides, netcam_overrides=netcam_overrides
    )

    app.router.add_get("/health", handle_health)
    app.router.add_get("/detect", handle_detect)
    app.router.add_get("/stream/{id}", handle_stream)
    app.router.add_post("/sources", handle_add_sources)
    app.router.add_delete("/sources/{id}", handle_remove_source)

    logger.info("Live-image proxy starting on %s:%d", host, port)
    web.run_app(app, host=host, port=port, print=lambda msg: logger.info(msg))
