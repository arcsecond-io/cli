"""
Remembered cameras.

Cameras registered with ``--allsky`` or ``--netcam`` are written here, so that
a proxy restarted after a reboot comes back with the same cameras instead of
needing every command typed again.

The file lives next to the CLI's own configuration, in
``~/.config/arcsecond/live-image-sources.json``::

    {
      "allsky": {"roof": {"path": "/srv/allsky/latest.jpg"}},
      "netcam": {"dome": {"url": "rtsp://admin:${DOME_CAM_PW}@192.168.1.42/s"}}
    }

Camera URLs are stored **exactly as the operator typed them**, with any
``${VARIABLE}`` left in place. Writing the expanded value would put the
password on disk in plain text, which is the one thing the ``${VARIABLE}``
syntax exists to avoid.

JSON rather than the .ini used elsewhere in the CLI: ConfigParser treats '%' as
an interpolation character, and percent-encoded characters in a camera URL are
perfectly normal — they would come back mangled.

"""

import json
import logging
from pathlib import Path
from typing import Optional

from arcsecond.api.config import ArcsecondConfig

logger = logging.getLogger(__name__)

FILENAME = "live-image-sources.json"

ALLSKY = "allsky"
NETCAM = "netcam"
KINDS = (ALLSKY, NETCAM)


class SourceStoreError(Exception):
    """The store file exists but cannot be used."""


def store_path() -> Path:
    return ArcsecondConfig.dir_path() / FILENAME


def load(path: Optional[Path] = None) -> dict:
    """Return ``{kind: {id: {...}}}``, empty if nothing has been registered."""
    path = path or store_path()
    if not path.exists():
        return {kind: {} for kind in KINDS}

    try:
        raw = json.loads(path.read_text(encoding="utf-8") or "{}")
    except (OSError, ValueError) as e:
        # Say which file and why. Silently starting from scratch would drop
        # every remembered camera without the operator ever being told.
        raise SourceStoreError(f"Cannot read {path}: {e}") from None

    if not isinstance(raw, dict):
        raise SourceStoreError(f"Cannot read {path}: expected a JSON object.")

    return {
        kind: dict(raw.get(kind) or {}) if isinstance(raw.get(kind), dict) else {}
        for kind in KINDS
    }


def save(data: dict, path: Optional[Path] = None) -> None:
    path = path or store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def remember_allsky(entries, path: Optional[Path] = None) -> None:
    """Add or replace all-sky registrations. ``entries`` are AllskyOverride."""
    if not entries:
        return
    data = load(path)
    for entry in entries:
        data[ALLSKY][entry.id] = {"path": entry.path}
    save(data, path)


def remember_netcams(entries, path: Optional[Path] = None) -> None:
    """Add or replace network camera registrations.

    What gets written is ``raw_url`` — the URL as typed, with any
    ``${VARIABLE}`` still in place. See the module docstring for why.
    """
    if not entries:
        return
    data = load(path)
    for entry in entries:
        data[NETCAM][entry.id] = {"url": entry.raw_url or entry.url}
    save(data, path)


def forget(kind: str, source_id: str, path: Optional[Path] = None) -> bool:
    """Drop one registration. Returns False if it was not there."""
    if kind not in KINDS:
        raise ValueError(f"Unknown kind: {kind!r}")
    data = load(path)
    if source_id not in data[kind]:
        return False
    del data[kind][source_id]
    save(data, path)
    return True


def remembered_allsky(path: Optional[Path] = None) -> list:
    """Return stored all-sky registrations as AllskyOverride objects."""
    from .registry import AllskyOverride

    data = load(path)
    return [
        AllskyOverride(id=sid, path=entry["path"])
        for sid, entry in sorted(data[ALLSKY].items())
        if isinstance(entry, dict) and entry.get("path")
    ]


def remembered_netcams(expand, path: Optional[Path] = None) -> list:
    """Return stored network cameras as NetcamOverride objects.

    ``expand`` turns a stored ``${VARIABLE}`` URL into a usable one. A camera
    whose variable is not set in *this* process's environment is dropped with a
    warning naming it, rather than taking the whole proxy down with it — the
    other cameras are still perfectly usable.
    """
    from .registry import NetcamOverride

    data = load(path)
    overrides = []
    for sid, entry in sorted(data[NETCAM].items()):
        if not isinstance(entry, dict) or not entry.get("url"):
            continue
        try:
            url = expand(entry["url"])
        except Exception as e:
            logger.warning(
                "Skipping remembered network camera %r: %s",
                sid,
                getattr(e, "message", None) or e,
            )
            continue
        overrides.append(NetcamOverride(id=sid, url=url, raw_url=entry["url"]))
    return overrides
