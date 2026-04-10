"""
Webcam proxy server for the Arcsecond CLI.

Why this exists
---------------
The Arcsecond backend runs inside Docker Desktop (Windows / macOS), which does not
forward USB devices to the container.  This small aiohttp server runs **natively**
on the dome PC (where it has direct USB access) and exposes two endpoints that the
backend container can reach via ``host.docker.internal``:

    GET  /detect             → JSON list of attached webcams (index, resolution, fps)
    WS   /stream/{index}     → continuous JPEG-frame stream (same protocol as the
                               backend WebSocket consumer → browser)

The backend reads the ``WEBCAM_PROXY_URL`` environment variable.  When it is set it
delegates detection and streaming to this proxy instead of calling OpenCV directly.

Start with:
    arcsecond webcam start [--port 8765] [--host 0.0.0.0]
"""

import asyncio
import base64
import json
import logging
from dataclasses import asdict, dataclass

logger = logging.getLogger(__name__)

_FRAME_INTERVAL = 0.1   # seconds  → ~10 fps
_JPEG_QUALITY   = 60    # 0-100
_MAX_PROBE      = 10    # device indices to probe during detection


# ---------------------------------------------------------------------------
# Webcam detection
# ---------------------------------------------------------------------------

@dataclass
class WebcamInfo:
    index: int
    width: int
    height: int
    fps: float


def _detect_webcams_sync(max_index: int = _MAX_PROBE) -> list[WebcamInfo]:
    """Blocking scan — run this inside an executor."""
    import cv2
    found: list[WebcamInfo] = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i)
        if not cap.isOpened():
            cap.release()
            continue
        found.append(WebcamInfo(
            index=i,
            width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            fps=cap.get(cv2.CAP_PROP_FPS),
        ))
        cap.release()
        logger.debug("Detected webcam at index %d", i)
    return found


# ---------------------------------------------------------------------------
# aiohttp request handlers
# ---------------------------------------------------------------------------

async def handle_health(request):
    """GET /health — simple liveness check."""
    from aiohttp import web
    return web.json_response({'status': 'ok'})


async def handle_detect(request):
    """GET /detect — return JSON list of attached webcams."""
    from aiohttp import web
    loop = asyncio.get_event_loop()
    webcams = await loop.run_in_executor(None, _detect_webcams_sync)
    return web.json_response([asdict(w) for w in webcams])


async def handle_stream(request):
    """WS /stream/{index} — stream JPEG frames to the caller."""
    import cv2
    from aiohttp import web

    index = int(request.match_info['index'])
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    logger.info("Webcam proxy: client connected to stream for device index %d", index)

    loop = asyncio.get_event_loop()
    cap: cv2.VideoCapture = await loop.run_in_executor(None, cv2.VideoCapture, index)

    if not await loop.run_in_executor(None, cap.isOpened):
        logger.error("Webcam proxy: cannot open device index %d", index)
        await ws.send_str(json.dumps({'type': 'error', 'message': f'Cannot open webcam at device index {index}.'}))
        await ws.close()
        return ws

    def _read_and_encode():
        ok, frame = cap.read()
        if not ok:
            return None
        ok2, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, _JPEG_QUALITY])
        if not ok2:
            return None
        return base64.b64encode(buf.tobytes()).decode('ascii')

    try:
        while not ws.closed:
            b64 = await loop.run_in_executor(None, _read_and_encode)
            if b64 is None:
                logger.warning("Webcam proxy: cap.read() failed for device %d, stopping.", index)
                break
            await ws.send_str(json.dumps({'type': 'frame', 'format': 'jpeg/base64', 'data': b64}))
            await asyncio.sleep(_FRAME_INTERVAL)
    finally:
        await loop.run_in_executor(None, cap.release)
        logger.info("Webcam proxy: device %d released.", index)

    return ws


# ---------------------------------------------------------------------------
# Server entry-point
# ---------------------------------------------------------------------------

def run(host: str = '0.0.0.0', port: int = 8765):
    """Build and run the aiohttp application (blocking)."""
    from aiohttp import web

    app = web.Application()
    app.router.add_get('/health', handle_health)
    app.router.add_get('/detect', handle_detect)
    app.router.add_get('/stream/{index}', handle_stream)

    logger.info("Webcam proxy starting on %s:%d", host, port)
    web.run_app(app, host=host, port=port, print=lambda msg: logger.info(msg))
