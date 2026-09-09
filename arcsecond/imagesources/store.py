"""
Registered cameras.

Every camera the proxy serves is registered here first, whatever kind it is:
a webcam plugged into this machine, a camera reached over the network, or an
all-sky camera writing JPEGs to a directory. Registering is what
``arcsecond webcam add`` and ``arcsecond allsky add`` do; ``arcsecond proxy
start`` then serves what it finds here. Nothing is ever registered as a side
effect of starting the proxy.

The file lives next to the CLI's own configuration, in
``~/.config/arcsecond/live-image-sources.json``::

    {
      "version": 2,
      "cameras": {
        "k3f": {"kind": "usb",    "index": 0},
        "p9x": {"kind": "net",    "url": "rtsp://admin:${DOME_PW}@10.0.0.4/s"},
        "r4t": {"kind": "allsky", "path": "/srv/allsky/latest.jpg"},
        "w8n": {"kind": "allsky", "url": "http://sky.local/latest.jpg"}
      }
    }

An all-sky camera carries a path when its software writes to this machine, and
a URL when that software runs elsewhere and publishes the image over HTTP. That
says how the image is fetched, not what kind of camera it is — the same way a
webcam is one kind whether it arrives over a USB cable or over RTSP. A store
holding one is still version 2: an older CLI ignores such an entry rather than
losing it, since it rewrites the entries it does not understand untouched.

Identifiers
-----------
Each camera gets a three-character id — ``k3f``, ``p9x`` — and that id is the
only handle the operator ever types or sees. It is short enough to retype from
memory, and it is *not* positional: unplugging the first of three webcams does
not renumber the other two, which is exactly what made device indices unusable
as names.

The id is derived from what identifies the camera (its device index, its URL,
its path), so registering the same camera twice returns the same id instead of
producing a second entry. Ids never collide: a derived id already taken by a
*different* camera is re-derived until it is free.

Camera URLs are stored **exactly as the operator typed them**, with any
``${VARIABLE}`` left in place. Writing the expanded value would put the
password on disk in plain text, which is the one thing the ``${VARIABLE}``
syntax exists to avoid.

JSON rather than the .ini used elsewhere in the CLI: ConfigParser treats '%' as
an interpolation character, and percent-encoded characters in a camera URL are
perfectly normal — they would come back mangled.
"""

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from arcsecond.api.config import ArcsecondConfig

logger = logging.getLogger(__name__)

FILENAME = "live-image-sources.json"
VERSION = 2

USB = "usb"
NET = "net"
ALLSKY = "allsky"
KINDS = (USB, NET, ALLSKY)

# The kinds `arcsecond webcam` deals with. A network camera is not a category
# of its own — it is a webcam that happens to be reached over the network
# rather than over a USB cable, and it is listed, added and forgotten by the
# same commands.
WEBCAM_KINDS = (USB, NET)

# No 0/O, 1/l/I: an id is meant to be read off a screen and typed back.
ID_ALPHABET = "23456789abcdefghjkmnpqrstuvwxyz"
ID_LENGTH = 3


class SourceStoreError(Exception):
    """The store file exists but cannot be used."""


@dataclass
class Camera:
    """One registered camera.

    Exactly one of ``index`` / ``url`` / ``path`` is set: an index for a USB
    webcam, a path for an all-sky camera writing to this machine, and a URL for
    a network camera or for an all-sky camera reached over HTTP.
    ``url`` is the URL as typed, with any ``${VARIABLE}`` still in place.
    """

    id: str
    kind: str
    label: Optional[str] = None
    index: Optional[int] = None  # usb
    url: Optional[str] = None  # net, and allsky published over HTTP
    path: Optional[str] = None  # allsky writing to this machine
    # What probing learned about a USB camera: width, height, fps. Recorded at
    # registration, when the device is opened anyway, so that listing it later
    # can report them without opening anything. Absent for a camera registered
    # while unplugged, and for the kinds that have no such thing.
    specs: Optional[dict] = None

    @property
    def identity(self) -> tuple:
        """What makes this camera *this* camera, rather than its name.

        Two registrations with the same identity are the same camera, however
        they were typed. This is what keeps ``add`` idempotent, and what
        detection matches a probed device against.
        """
        if self.kind == USB:
            return (USB, self.index)
        if self.kind == NET:
            return (NET, self.url)
        # The same URL registered as an all-sky camera and as a webcam is two
        # registrations, not one: the kind is part of what was asked for, and
        # each is served at its own cadence.
        return (ALLSKY, self.url or self.path)

    @property
    def target(self) -> str:
        """Where the camera is, in one line, safe to print."""
        if self.kind == USB:
            return f"device index {self.index}"
        if self.url:
            from .sources.network import redact_url

            return redact_url(self.url)
        return self.path or ""

    @property
    def display_kind(self) -> str:
        return {USB: "usb", NET: "network", ALLSKY: "all-sky"}.get(self.kind, self.kind)

    @property
    def description(self) -> str:
        """The kind as it reads in a sentence, article included."""
        return {
            USB: "a USB webcam",
            NET: "a network camera",
            ALLSKY: "an all-sky camera",
        }.get(self.kind, f"a {self.kind} camera")

    def to_json(self) -> dict:
        entry: dict = {"kind": self.kind}
        if self.kind == USB:
            entry["index"] = self.index
            if self.specs:
                entry["specs"] = self.specs
        elif self.url:
            entry["url"] = self.url
        else:
            entry["path"] = self.path
        if self.label:
            entry["label"] = self.label
        return entry


def camera_from_json(cam_id: str, entry: dict) -> Optional[Camera]:
    if not isinstance(entry, dict):
        return None
    kind = entry.get("kind")
    if kind not in KINDS:
        return None
    label = entry.get("label") or None
    if kind == USB:
        index = entry.get("index")
        if not isinstance(index, int):
            return None
        specs = entry.get("specs")
        return Camera(
            id=cam_id,
            kind=USB,
            index=index,
            label=label,
            specs=specs if isinstance(specs, dict) else None,
        )
    if kind == NET:
        url = entry.get("url")
        if not url:
            return None
        return Camera(id=cam_id, kind=NET, url=url, label=label)
    url = entry.get("url")
    if url:
        return Camera(id=cam_id, kind=ALLSKY, url=url, label=label)
    path = entry.get("path")
    if not path:
        return None
    return Camera(id=cam_id, kind=ALLSKY, path=path, label=label)


# ---------------------------------------------------------------------------
# Identifiers
# ---------------------------------------------------------------------------


def _derive_id(identity: tuple, taken: set) -> str:
    """A free three-character id for ``identity``.

    Derived rather than drawn at random so that registering the same camera
    twice lands on the same id, and so that ids survive a store rebuilt from
    an older file without being renumbered.
    """
    seed = "\x00".join(str(part) for part in identity)
    salt = 0
    while True:
        digest = hashlib.sha256(f"{seed}\x00{salt}".encode("utf-8")).digest()
        number = int.from_bytes(digest[:8], "big")
        cam_id = ""
        for _ in range(ID_LENGTH):
            number, remainder = divmod(number, len(ID_ALPHABET))
            cam_id += ID_ALPHABET[remainder]
        if cam_id not in taken:
            return cam_id
        salt += 1


# ---------------------------------------------------------------------------
# Reading and writing
# ---------------------------------------------------------------------------


def store_path() -> Path:
    return ArcsecondConfig.dir_path() / FILENAME


def _migrate_v1(raw: dict) -> dict:
    """Convert the first store layout, which grouped cameras by kind.

    That layout keyed each camera on a name the operator invented, and printed
    it back prefixed (``netcam:dome``) — the mismatch that made ``forget``
    unusable. The invented name is kept as the camera's label, so nothing the
    operator wrote is lost, and a real id is derived for it.
    """
    cameras: dict = {}
    taken: set = set()

    for old_id, entry in sorted((raw.get("allsky") or {}).items()):
        if not isinstance(entry, dict) or not entry.get("path"):
            continue
        camera = Camera(id="", kind=ALLSKY, path=entry["path"], label=old_id)
        cam_id = _derive_id(camera.identity, taken)
        taken.add(cam_id)
        cameras[cam_id] = Camera(
            id=cam_id, kind=ALLSKY, path=entry["path"], label=old_id
        ).to_json()

    for old_id, entry in sorted((raw.get("netcam") or {}).items()):
        if not isinstance(entry, dict) or not entry.get("url"):
            continue
        camera = Camera(id="", kind=NET, url=entry["url"], label=old_id)
        cam_id = _derive_id(camera.identity, taken)
        taken.add(cam_id)
        cameras[cam_id] = Camera(
            id=cam_id, kind=NET, url=entry["url"], label=old_id
        ).to_json()

    return {"version": VERSION, "cameras": cameras}


def load(path: Optional[Path] = None) -> dict:
    """Return ``{"version": 2, "cameras": {id: {...}}}``.

    A store written by an older CLI is converted and written back, so that the
    ids it hands out stay the same from one command to the next.
    """
    path = path or store_path()
    if not path.exists():
        return {"version": VERSION, "cameras": {}}

    try:
        raw = json.loads(path.read_text(encoding="utf-8") or "{}")
    except (OSError, ValueError) as e:
        # Say which file and why. Silently starting from scratch would drop
        # every registered camera without the operator ever being told.
        raise SourceStoreError(f"Cannot read {path}: {e}") from None

    if not isinstance(raw, dict):
        raise SourceStoreError(f"Cannot read {path}: expected a JSON object.")

    if raw.get("version") == VERSION:
        cameras = raw.get("cameras")
        return {
            "version": VERSION,
            "cameras": dict(cameras) if isinstance(cameras, dict) else {},
        }

    data = _migrate_v1(raw)
    try:
        save(data, path)
    except OSError as e:
        # Usable now, just not remembered in the new shape. Worth saying,
        # because the derived ids would otherwise be re-derived every time.
        logger.warning("Could not rewrite %s in the new layout: %s", path, e)
    return data


def save(data: dict, path: Optional[Path] = None) -> None:
    path = path or store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Querying
# ---------------------------------------------------------------------------


def all_cameras(path: Optional[Path] = None) -> list[Camera]:
    """Every registered camera, in a stable order: by kind, then by id."""
    data = load(path)
    cameras = []
    for cam_id, entry in data["cameras"].items():
        camera = camera_from_json(cam_id, entry)
        if camera is not None:
            cameras.append(camera)
    return sorted(cameras, key=lambda c: (KINDS.index(c.kind), c.id))


def cameras_of_kinds(kinds, path: Optional[Path] = None) -> list[Camera]:
    return [c for c in all_cameras(path) if c.kind in kinds]


def find(cam_id: str, path: Optional[Path] = None) -> Optional[Camera]:
    """The camera registered under ``cam_id``, or None.

    Ids are matched case-insensitively, and a leading ``usb:`` / ``net:`` /
    ``allsky:`` is tolerated: the proxy's own source ids used to carry one, and
    an operator copying from an older screen or script should not be told the
    camera does not exist.
    """
    wanted = (cam_id or "").strip().lower()
    if ":" in wanted:
        prefix, _, rest = wanted.partition(":")
        if prefix in KINDS or prefix in ("webcam", "netcam"):
            wanted = rest
    for camera in all_cameras(path):
        if camera.id == wanted:
            return camera
    return None


def find_by_identity(identity: tuple, path: Optional[Path] = None) -> Optional[Camera]:
    for camera in all_cameras(path):
        if camera.identity == identity:
            return camera
    return None


# ---------------------------------------------------------------------------
# Registering and forgetting
# ---------------------------------------------------------------------------


def add(camera: Camera, path: Optional[Path] = None) -> tuple[Camera, bool]:
    """Register ``camera``. Returns ``(stored, created)``.

    ``created`` is False when this exact camera was already registered — the
    call is then a no-op that hands back the existing id, so that re-running an
    ``add`` from shell history does not build up duplicates. A label given the
    second time is applied.
    """
    data = load(path)
    stored = {
        cid: camera_from_json(cid, entry) for cid, entry in data["cameras"].items()
    }
    stored = {cid: cam for cid, cam in stored.items() if cam is not None}

    for existing in stored.values():
        if existing.identity == camera.identity:
            # Re-registering the same camera is how its label and its measured
            # resolution get refreshed — a camera that was unplugged the first
            # time, or that has been set to a different mode since.
            changed = False
            if camera.label and camera.label != existing.label:
                existing.label = camera.label
                changed = True
            if camera.specs and camera.specs != existing.specs:
                existing.specs = camera.specs
                changed = True
            if changed:
                data["cameras"][existing.id] = existing.to_json()
                save(data, path)
            return existing, False

    cam_id = _derive_id(camera.identity, set(stored.keys()))
    camera.id = cam_id
    data["cameras"][cam_id] = camera.to_json()
    save(data, path)
    return camera, True


def forget(cam_id: str, path: Optional[Path] = None) -> Optional[Camera]:
    """Drop one registration, whatever kind it is. Returns it, or None.

    One function for all three kinds, keyed on the id alone. The caller does
    not have to know — or guess — whether the camera it is forgetting is a USB
    webcam, a network camera or an all-sky camera, which is what made the
    previous ``forget`` impossible to use for anything but a network camera.
    """
    camera = find(cam_id, path)
    if camera is None:
        return None
    data = load(path)
    data["cameras"].pop(camera.id, None)
    save(data, path)
    return camera


# ---------------------------------------------------------------------------
# Environment variables in camera URLs
# ---------------------------------------------------------------------------


def expanded(cameras: list[Camera], expand) -> list[Camera]:
    """Return ``cameras`` with every ``${VARIABLE}`` in a URL filled in.

    A camera whose variable is not set in *this* process's environment is
    dropped with a warning naming it, rather than taking the whole proxy down
    with it — the other cameras are still perfectly usable.
    """
    usable = []
    for camera in cameras:
        # Keyed on the URL rather than on the kind: an all-sky camera reached
        # over HTTP may carry a password in its address just as a network
        # camera does, and it is stored the same way — unexpanded.
        if not camera.url:
            usable.append(camera)
            continue
        try:
            url = expand(camera.url)
        except Exception as e:
            logger.warning(
                "Skipping camera %r: %s",
                camera.id,
                getattr(e, "message", None) or e,
            )
            continue
        usable.append(
            Camera(
                id=camera.id,
                kind=camera.kind,
                url=url,
                label=camera.label,
            )
        )
    return usable
