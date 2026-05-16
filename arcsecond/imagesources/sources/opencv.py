"""
OpenCV-backed webcam source.

Wraps ``cv2.VideoCapture`` and re-encodes each grabbed frame as JPEG.
Designed for USB webcams attached to the host running the proxy.
"""

import asyncio
import logging
from typing import Optional

from .base import FrameSource, SourceInfo

logger = logging.getLogger(__name__)

_FRAME_INTERVAL = 0.1  # seconds  → ~10 fps
_JPEG_QUALITY = 60  # 0-100
_MAX_PROBE = 10  # device indices to probe during detection


class OpenCVWebcamSource(FrameSource):
    kind = "webcam"
    poll_interval = _FRAME_INTERVAL
    shareable = True  # USB webcams can only be opened once at a time.

    def __init__(self, index: int):
        self.index = index
        self.id = f"webcam:{index}"
        self._cap = None

    async def open(self) -> None:
        import cv2

        loop = asyncio.get_running_loop()
        self._cap = await loop.run_in_executor(None, cv2.VideoCapture, self.index)
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

    found: list[SourceInfo] = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i)
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
