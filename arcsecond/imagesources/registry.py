"""
Source resolution and discovery for the proxy.

Webcams are auto-detected by probing OpenCV device indices.
All-sky sources are either auto-discovered at well-known paths or registered
explicitly by the user (``arcsecond allsky add``-style overrides passed at
``run()`` time).
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

from .sources.base import FrameSource, SourceInfo
from .sources.filewatch import FileWatchSource, detect_allsky
from .sources.opencv import OpenCVWebcamSource, detect_webcams

logger = logging.getLogger(__name__)


@dataclass
class AllskyOverride:
    id: str  # bare id, will be prefixed with "allsky:"
    path: str  # file path or glob
    label: Optional[str] = None


@dataclass
class _SharedEntry:
    source: FrameSource
    refcount: int = 0
    read_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class AcquiredSource:
    """Handle returned by ``Registry.acquire()``.

    Wraps a :class:`FrameSource` plus the bookkeeping needed to read frames
    safely (serializing concurrent reads on shared sources) and to release
    the underlying device when the last holder is done.
    """

    def __init__(
        self, registry: "Registry", source_id: str, source: FrameSource, refcount: int
    ):
        self._registry = registry
        self.source_id = source_id
        self.source = source
        self.refcount = refcount

    @property
    def poll_interval(self) -> float:
        return self.source.poll_interval

    async def read(self) -> Optional[bytes]:
        return await self._registry._read(self.source_id, self.source)

    async def release(self) -> int:
        return await self._registry._release(self.source_id, self.source)


class Registry:
    """Discover and instantiate sources on demand.

    Sources marked ``shareable=True`` (e.g. OpenCV webcams, which can only be
    opened once on Windows/DirectShow) are reference-counted: the first
    ``acquire()`` opens the underlying device, subsequent acquires return the
    same instance, and the device is closed only when the last holder
    releases. Non-shareable sources (file-watch all-sky) get a fresh instance
    per acquire so each consumer keeps its own per-reader state.
    """

    def __init__(self, allsky_overrides: Optional[list[AllskyOverride]] = None):
        self.allsky_overrides = allsky_overrides or []
        self._shared: dict[str, _SharedEntry] = {}
        self._lock = asyncio.Lock()

    def detect(self) -> list[SourceInfo]:
        infos: list[SourceInfo] = []
        try:
            infos.extend(detect_webcams())
        except Exception as e:
            logger.warning("Webcam detection failed: %s", e)

        if self.allsky_overrides:
            for o in self.allsky_overrides:
                src = FileWatchSource(f"allsky:{o.id}", o.path, o.label)
                infos.append(src.info())
        else:
            infos.extend(detect_allsky())

        return infos

    def _build(self, source_id: str) -> FrameSource:
        # Backward-compat: bare numeric ids → webcam.
        if source_id.isdigit():
            return OpenCVWebcamSource(int(source_id))

        kind, _, name = source_id.partition(":")
        if not name:
            raise KeyError(f"Unknown source id: {source_id!r}")

        if kind == "webcam":
            return OpenCVWebcamSource(int(name))

        if kind == "allsky":
            for o in self.allsky_overrides:
                if o.id == name:
                    return FileWatchSource(source_id, o.path, o.label)
            for info in detect_allsky():
                if info.id == source_id:
                    return FileWatchSource(source_id, info.extra["path"], info.label)
            raise KeyError(f"No all-sky source registered as {source_id!r}")

        raise KeyError(f"Unknown source kind: {kind!r}")

    async def acquire(self, source_id: str) -> AcquiredSource:
        candidate = self._build(source_id)

        if not candidate.shareable:
            await candidate.open()
            return AcquiredSource(self, source_id, candidate, refcount=1)

        async with self._lock:
            entry = self._shared.get(source_id)
            if entry is None:
                await candidate.open()
                entry = _SharedEntry(source=candidate)
                self._shared[source_id] = entry
                logger.info("Live-image proxy: %s opened.", source_id)
            entry.refcount += 1
            return AcquiredSource(
                self, source_id, entry.source, refcount=entry.refcount
            )

    async def _read(self, source_id: str, source: FrameSource) -> Optional[bytes]:
        if not source.shareable:
            return await source.read()
        entry = self._shared.get(source_id)
        if entry is None:
            return None
        async with entry.read_lock:
            return await entry.source.read()

    async def _release(self, source_id: str, source: FrameSource) -> int:
        if not source.shareable:
            await source.close()
            return 0

        async with self._lock:
            entry = self._shared.get(source_id)
            if entry is None:
                return 0
            entry.refcount -= 1
            if entry.refcount > 0:
                return entry.refcount
            del self._shared[source_id]
        try:
            await entry.source.close()
        finally:
            logger.info("Live-image proxy: %s released.", source_id)
        return 0
