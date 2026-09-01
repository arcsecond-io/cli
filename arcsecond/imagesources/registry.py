"""
The cameras the proxy is serving, and how to open one.

The registry holds exactly what was registered with ``arcsecond webcam add``
and ``arcsecond allsky add`` — nothing more. It never probes for hardware on
its own: discovery is what ``arcsecond webcam detect`` is for, and it is a
thing the operator asks for, not a thing that happens behind their back while
a client is waiting for a list.

A source is addressed by the camera's three-character id (``k3f``), the same
id the CLI prints. There is no second, prefixed form of the id — the two used
to disagree, and every ``forget`` typed from what the screen showed failed
because of it.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

from .sources.base import FrameSource, SourceInfo
from .sources.filewatch import FileWatchSource
from .sources.network import build_network_source
from .sources.opencv import OpenCVWebcamSource
from .store import ALLSKY, NET, USB, Camera

logger = logging.getLogger(__name__)


def build_source(camera: Camera) -> FrameSource:
    """The right :class:`FrameSource` for ``camera``.

    ``camera.url`` must already have had its ``${VARIABLE}`` expanded — see
    ``store.expanded``.
    """
    if camera.kind == USB:
        return OpenCVWebcamSource(
            camera.index,
            source_id=camera.id,
            label=camera.label,
            specs=camera.specs,
        )
    if camera.kind == NET:
        return build_network_source(camera.id, camera.url, camera.label)
    if camera.kind == ALLSKY:
        return FileWatchSource(camera.id, camera.path, camera.label)
    raise KeyError(f"Unknown camera kind: {camera.kind!r}")


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
    """Hold the registered cameras, and instantiate them on demand.

    Sources marked ``shareable=True`` (e.g. OpenCV webcams, which can only be
    opened once on Windows/DirectShow) are reference-counted: the first
    ``acquire()`` opens the underlying device, subsequent acquires return the
    same instance, and the device is closed only when the last holder
    releases. Non-shareable sources (file-watch all-sky) get a fresh instance
    per acquire so each consumer keeps its own per-reader state.
    """

    def __init__(self, cameras: Optional[list[Camera]] = None):
        self._cameras: dict[str, Camera] = {c.id: c for c in cameras or []}
        self._shared: dict[str, _SharedEntry] = {}
        self._lock = asyncio.Lock()

    @property
    def cameras(self) -> list[Camera]:
        return list(self._cameras.values())

    def add(self, cameras: list[Camera]) -> list[str]:
        """Register cameras into a running proxy. Returns the ids added.

        An id that is already registered is replaced. The dict is rebuilt and
        assigned whole rather than mutated in place: ``infos`` and ``_build``
        read it without holding the lock, and would otherwise be able to see it
        mid-update.
        """
        if not cameras:
            return []
        merged = dict(self._cameras)
        for camera in cameras:
            merged[camera.id] = camera
        self._cameras = merged
        return [c.id for c in cameras]

    def remove(self, cam_id: str) -> bool:
        """Unregister one camera. Returns False if it was not registered.

        Any viewer already streaming it keeps its own handle and is left alone;
        it simply cannot be acquired again.
        """
        if cam_id not in self._cameras:
            return False
        merged = dict(self._cameras)
        del merged[cam_id]
        self._cameras = merged
        return True

    def infos(self) -> list[SourceInfo]:
        """What this proxy is serving. Nothing is opened or contacted.

        A camera that is off, unplugged or unreachable is still listed: finding
        that out would mean opening every device on every call, and would hold
        the answer up for every client whenever one camera was down.
        """
        infos: list[SourceInfo] = []
        for camera in self._cameras.values():
            try:
                infos.append(build_source(camera).info())
            except KeyError as e:
                logger.warning("Skipping camera %r: %s", camera.id, e)
        return infos

    def _build(self, source_id: str) -> FrameSource:
        camera = self._cameras.get(source_id)
        if camera is None:
            raise KeyError(f"No camera is registered as {source_id!r}")
        return build_source(camera)

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
