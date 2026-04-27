"""
File-watch source — for all-sky cameras.

All-sky software (Thomas Jacquin's allsky, indi-allsky, ...) writes a JPEG to
disk every 30-120 seconds, usually keeping a stable "latest image" path
(symlink or fixed filename). This source returns the file's bytes whenever its
mtime changes, and ``None`` otherwise. The proxy stays dumb — no decoding,
stretching or re-encoding.
"""

import asyncio
import glob
import logging
from pathlib import Path
from typing import Optional

from .base import FrameSource, SourceInfo

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 5.0  # seconds — image cadence is much slower; this is fine

# Common locations to probe at startup. First match wins per software.
ALLSKY_DISCOVERY_PATHS: list[Path] = [
    # Thomas Jacquin's allsky (https://github.com/AllskyTeam/allsky)
    Path.home() / "allsky" / "tmp" / "image.jpg",
    Path("/var/www/html/allsky/current/tmp/image.jpg"),
    # indi-allsky (https://github.com/aaronwmorris/indi-allsky)
    Path("/var/lib/indi-allsky/images/latest.jpg"),
    Path.home() / "indi-allsky" / "latest.jpg",
]


class FileWatchSource(FrameSource):
    """Emit a frame whenever a file's mtime changes.

    ``path`` may be a fixed file (or symlink), or a glob — in the latter case
    the newest matching file by mtime wins.
    """

    kind = "allsky"
    poll_interval = _POLL_INTERVAL

    def __init__(self, source_id: str, path: str, label: Optional[str] = None):
        self.id = source_id
        self.path = path
        self.label = label or source_id
        self._is_glob = any(ch in path for ch in "*?[")
        self._last_mtime: Optional[float] = None
        self._last_path: Optional[Path] = None

    async def open(self) -> None:
        # Nothing to acquire — file is read on each poll.
        return

    async def close(self) -> None:
        return

    def _resolve_current(self) -> Optional[Path]:
        if self._is_glob:
            matches = glob.glob(self.path)
            if not matches:
                return None
            return Path(max(matches, key=lambda p: Path(p).stat().st_mtime))
        p = Path(self.path)
        return p if p.exists() else None

    async def read(self) -> Optional[bytes]:
        loop = asyncio.get_running_loop()

        def _read_if_changed():
            current = self._resolve_current()
            if current is None:
                return None
            mtime = current.stat().st_mtime
            if current == self._last_path and mtime == self._last_mtime:
                return None
            data = current.read_bytes()
            self._last_path = current
            self._last_mtime = mtime
            return data

        return await loop.run_in_executor(None, _read_if_changed)

    def info(self) -> SourceInfo:
        return SourceInfo(
            id=self.id,
            kind=self.kind,
            label=self.label,
            extra={"path": self.path},
        )


def detect_allsky() -> list[SourceInfo]:
    """Probe well-known all-sky JPEG locations and return any that exist."""
    found: list[SourceInfo] = []
    for path in ALLSKY_DISCOVERY_PATHS:
        if path.exists():
            sid = f"allsky:{path.parent.parent.name or 'default'}"
            # Disambiguate if multiple discoveries hit the same id.
            base = sid
            n = 1
            while any(s.id == sid for s in found):
                n += 1
                sid = f"{base}-{n}"
            found.append(SourceInfo(
                id=sid,
                kind="allsky",
                label=f"All-sky camera ({path})",
                extra={"path": str(path)},
            ))
            logger.debug("Discovered all-sky source at %s", path)
    return found
