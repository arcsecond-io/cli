"""
OpenCV-backed webcam source.

Wraps ``cv2.VideoCapture`` and re-encodes each grabbed frame as JPEG.
Designed for USB webcams attached to the host running the proxy.
"""

import asyncio
import logging
import sys
from typing import Optional

from .base import FrameSource, SourceInfo

logger = logging.getLogger(__name__)

_FRAME_INTERVAL = 0.1  # seconds  → ~10 fps
_JPEG_QUALITY = 60  # 0-100
_MAX_PROBE = 10  # device indices to probe during detection


def _capture_backend():
    """The OpenCV backend to open device *indices* with, for this platform.

    Never ``CAP_ANY``. Left to choose for itself, OpenCV walks its backend list
    and — on a machine with no camera at that index — ends up at FFMPEG, which
    interprets an integer index by asking libavdevice to enumerate DirectShow
    devices. That path is slow, cannot work, and prints a wall of
    ``Could not enumerate audio only devices`` to stderr for every index probed.

    Pinning the platform's native backend also keeps index numbering stable:
    detection and ``open()`` must agree on what device index 1 means, and each
    backend enumerates in its own order.
    """
    import cv2

    if sys.platform == "win32":
        return cv2.CAP_DSHOW
    if sys.platform == "darwin":
        return cv2.CAP_AVFOUNDATION
    return cv2.CAP_V4L2


class OpenCVWebcamSource(FrameSource):
    kind = "webcam"
    poll_interval = _FRAME_INTERVAL
    shareable = True  # USB webcams can only be opened once at a time.

    def __init__(self, index: int):
        self.index = index
        self.id = f"webcam:{index}"
        self._cap = None

    async def open(self) -> None:
        import cv2  # noqa: F401

        loop = asyncio.get_running_loop()
        backend = _capture_backend()
        self._cap = await loop.run_in_executor(
            None, cv2.VideoCapture, self.index, backend
        )
        if not await loop.run_in_executor(None, self._cap.isOpened):
            raise RuntimeError(f"Cannot open webcam at device index {self.index}.")

    async def read(self) -> Optional[bytes]:
        import cv2

        loop = asyncio.get_running_loop()

        def _read_and_encode():
            ok, frame = self._cap.read()
            if not ok:
                # Raise rather than return None: per FrameSource contract, None
                # means "no new frame available". A failed grab indicates the
                # device is unhealthy (unplugged, claimed by another process,
                # DirectShow contention, ...) and the proxy needs to know.
                raise RuntimeError(f"cap.read() failed for webcam index {self.index}")
            ok2, buf = cv2.imencode(
                ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, _JPEG_QUALITY]
            )
            if not ok2:
                raise RuntimeError(f"JPEG encode failed for webcam index {self.index}")
            return buf.tobytes()

        return await loop.run_in_executor(None, _read_and_encode)

    async def close(self) -> None:
        if self._cap is None:
            return
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._cap.release)
        self._cap = None

    def info(self) -> SourceInfo:
        # Width/height/fps are only known once opened. Detection re-opens
        # briefly to populate them; for already-known sources we just expose id.
        return SourceInfo(id=self.id, kind=self.kind, label=f"USB webcam #{self.index}")


def detect_webcams(max_index: int = _MAX_PROBE) -> list[SourceInfo]:
    """Blocking probe of device indices 0..max_index-1."""
    import cv2

    backend = _capture_backend()
    found: list[SourceInfo] = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i, backend)
        if not cap.isOpened():
            cap.release()
            continue
        info = SourceInfo(
            id=f"webcam:{i}",
            kind="webcam",
            label=f"USB webcam #{i}",
            extra={
                "index": i,
                "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                "fps": cap.get(cv2.CAP_PROP_FPS),
            },
        )
        cap.release()
        found.append(info)
        logger.debug("Detected webcam at index %d", i)
    return found
