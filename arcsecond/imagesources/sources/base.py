"""
Abstract live-image source.

A source emits JPEG frames on demand. The proxy polls ``read()`` every
``poll_interval`` seconds and forwards any returned bytes to the WebSocket
client. Returning ``None`` means "no new frame" — used by sources that update
infrequently (e.g. all-sky cameras writing one JPEG per minute).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class SourceInfo:
    """Metadata returned by ``/detect`` for a single source."""
    id: str                       # e.g. "webcam:0", "allsky:roof"
    kind: str                     # "webcam" | "allsky"
    label: str                    # human-readable
    extra: Optional[dict] = None  # kind-specific fields (resolution, path, ...)


class FrameSource(ABC):
    """Pull-based JPEG frame source."""

    id: str
    kind: str
    poll_interval: float

    @abstractmethod
    async def open(self) -> None:
        """Acquire the underlying device / file handle."""

    @abstractmethod
    async def read(self) -> Optional[bytes]:
        """Return the next JPEG frame, or ``None`` if no new frame is available."""

    @abstractmethod
    async def close(self) -> None:
        """Release the underlying device / file handle."""

    def info(self) -> SourceInfo:
        return SourceInfo(id=self.id, kind=self.kind, label=self.id)
