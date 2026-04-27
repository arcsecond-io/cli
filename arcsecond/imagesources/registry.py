"""
Source resolution and discovery for the proxy.

Webcams are auto-detected by probing OpenCV device indices.
All-sky sources are either auto-discovered at well-known paths or registered
explicitly by the user (``arcsecond allsky add``-style overrides passed at
``run()`` time).
"""

import logging
from dataclasses import dataclass
from typing import Optional

from .sources.base import FrameSource, SourceInfo
from .sources.filewatch import FileWatchSource, detect_allsky
from .sources.opencv import OpenCVWebcamSource, detect_webcams

logger = logging.getLogger(__name__)


@dataclass
class AllskyOverride:
    id: str          # bare id, will be prefixed with "allsky:"
    path: str        # file path or glob
    label: Optional[str] = None


class Registry:
    """Discover and instantiate sources on demand."""

    def __init__(self, allsky_overrides: Optional[list[AllskyOverride]] = None):
        self.allsky_overrides = allsky_overrides or []

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

    def open_source(self, source_id: str) -> FrameSource:
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
