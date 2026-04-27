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

Source ids look like ``webcam:0`` or ``allsky:roof``. For backward
compatibility, a bare numeric id (``/stream/0``) is treated as ``webcam:0``.

The backend reads the ``LIVE_IMAGE_PROXY_URL`` environment variable
(``WEBCAM_PROXY_URL`` is accepted as a deprecated fallback). When set, it
delegates detection and streaming to this proxy.

Start with:
    arcsecond webcam start          # webcams only (legacy)
    arcsecond imagesources start    # webcams + all-sky
"""

import asyncio
import base64
import json
import logging
from dataclasses import asdict
from typing import Optional

from .registry import AllskyOverride, Registry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# aiohttp request handlers
# ---------------------------------------------------------------------------

async def handle_health(request):
    from aiohttp import web
    return web.json_response({'status': 'ok'})


async def handle_detect(request):
    from aiohttp import web
    registry: Registry = request.app['registry']
    loop = asyncio.get_running_loop()
    infos = await loop.run_in_executor(None, registry.detect)
    return web.json_response([asdict(i) for i in infos])


async def handle_stream(request):
    from aiohttp import web

    registry: Registry = request.app['registry']
    source_id = request.match_info['id']

    ws = web.WebSocketResponse()
    await ws.prepare(request)
    logger.info("Live-image proxy: client connected to stream %s", source_id)

    try:
        source = registry.open_source(source_id)
    except KeyError as e:
        logger.error("Live-image proxy: %s", e)
        await ws.send_str(json.dumps({'type': 'error', 'message': str(e)}))
        await ws.close()
        return ws

    try:
        await source.open()
    except Exception as e:
        logger.error("Live-image proxy: cannot open %s: %s", source_id, e)
        await ws.send_str(json.dumps({'type': 'error', 'message': str(e)}))
        await ws.close()
        return ws

    try:
        while not ws.closed:
            jpeg: Optional[bytes] = await source.read()
            if jpeg is not None:
                b64 = base64.b64encode(jpeg).decode('ascii')
                await ws.send_str(json.dumps({
                    'type': 'frame',
                    'format': 'jpeg/base64',
                    'data': b64,
                }))
            await asyncio.sleep(source.poll_interval)
    except (ConnectionResetError, ConnectionError):
        logger.info("Live-image proxy: client disconnected from %s.", source_id)
    finally:
        await source.close()
        logger.info("Live-image proxy: %s released.", source_id)

    return ws


# ---------------------------------------------------------------------------
# Server entry-point
# ---------------------------------------------------------------------------

def run(
    host: str = '0.0.0.0',
    port: int = 8765,
    allsky_overrides: Optional[list[AllskyOverride]] = None,
):
    """Build and run the aiohttp application (blocking)."""
    from aiohttp import web

    app = web.Application()
    app['registry'] = Registry(allsky_overrides=allsky_overrides)

    app.router.add_get('/health', handle_health)
    app.router.add_get('/detect', handle_detect)
    app.router.add_get('/stream/{id}', handle_stream)

    logger.info("Live-image proxy starting on %s:%d", host, port)
    web.run_app(app, host=host, port=port, print=lambda msg: logger.info(msg))
