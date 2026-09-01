"""
Looking for cameras, and saying how what was found relates to what is known.

``detect`` used to mean two things at once — probe the hardware, *and* print
the registered cameras — with no way to tell from the output which was which.
Here the two are kept apart and then explicitly matched up, so that the answer
to "is my camera going to work?" is on the screen rather than inferred:

  * **new**      — found by probing, not registered. Nothing serves it yet.
  * **present**  — registered, and confirmed to be there right now.
  * **missing**  — registered, but not there: unplugged, switched off, moved.

A camera is matched to a probe result on its *identity* (device index, URL,
path), never on its id — an id is a name given at registration, and a device
nobody has registered yet does not have one.

Network cameras cannot be discovered: there is no protocol to ask a subnet
which of it is a camera, so a network camera is never *new*. It can still be
confirmed present or reported missing, and that is done with a plain TCP
connection to the address rather than by pulling a frame. Opening an RTSP
stream to decide takes seconds per camera and can wake hardware that would
rather be left alone; ``arcsecond webcam test`` is there for when the question
really is "does this send me a picture?".
"""

import logging
import socket
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from glob import glob
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

from .sources.base import DetectedDevice
from .sources.filewatch import detect_allsky
from .store import ALLSKY, NET, USB, Camera

logger = logging.getLogger(__name__)

# Seconds to wait for a network camera to accept a connection. Short: this is
# a reachability check on a local network, not a retry policy.
NETWORK_TIMEOUT = 2.0

_DEFAULT_PORTS = {"rtsp": 554, "rtsps": 322, "http": 80, "https": 443}


@dataclass
class DetectionReport:
    new: list[DetectedDevice] = field(default_factory=list)
    present: list[Camera] = field(default_factory=list)
    missing: list[Camera] = field(default_factory=list)
    # id or identity → one line of explanation, e.g. "1280×720, 30.0 fps" or
    # "no answer on 10.0.0.4:554".
    detail: dict = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        return not (self.new or self.present or self.missing)


# ---------------------------------------------------------------------------
# Probing
# ---------------------------------------------------------------------------


def _describe(device: DetectedDevice) -> str:
    extra = device.extra or {}
    if device.kind == USB:
        width, height = extra.get("width"), extra.get("height")
        fps = extra.get("fps") or 0
        size = f"{width}×{height}" if width and height else "unknown size"
        return f"{size}, {fps:.1f} fps" if fps else size
    return str(extra.get("path", ""))


def resolve_allsky_path(path: str) -> Optional[str]:
    """The file a registered all-sky camera is currently writing, if any."""
    if any(ch in path for ch in "*?["):
        matches = glob(path)
        if not matches:
            return None
        return max(matches, key=lambda p: Path(p).stat().st_mtime)
    return path if Path(path).exists() else None


def _network_endpoint(url: str) -> Optional[tuple]:
    parts = urlsplit(url)
    host = parts.hostname
    if not host:
        return None
    port = parts.port or _DEFAULT_PORTS.get(parts.scheme.lower())
    if not port:
        return None
    return (host, port)


def _is_reachable(camera: Camera, timeout: float) -> tuple:
    """``(reachable, why)`` for one network camera.

    Only the address is contacted, and the answer never contains the URL's
    password: ``Camera.target`` is redacted, and the endpoint printed here is
    the host and port alone.
    """
    endpoint = _network_endpoint(camera.url or "")
    if endpoint is None:
        return False, "the address cannot be read"
    host, port = endpoint
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, f"answering on {host}:{port}"
    except OSError as e:
        return False, f"no answer on {host}:{port} ({e.strerror or e})"


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------


def report(
    cameras: list[Camera],
    kinds,
    timeout: float = NETWORK_TIMEOUT,
    check_network: bool = True,
) -> DetectionReport:
    """Probe for ``kinds`` of camera and match the result against ``cameras``.

    ``cameras`` is what the store holds; only those of the requested kinds are
    considered, so ``arcsecond webcam detect`` never reports on an all-sky
    camera and vice versa.
    """
    registered = [c for c in cameras if c.kind in kinds]
    by_identity = {c.identity: c for c in registered}

    devices: list[DetectedDevice] = []
    if USB in kinds:
        try:
            devices.extend(_detect_webcams())
        except Exception as e:
            logger.warning("Webcam detection failed: %s", e)
    if ALLSKY in kinds:
        try:
            devices.extend(detect_allsky())
        except Exception as e:
            logger.warning("All-sky detection failed: %s", e)

    result = DetectionReport()
    matched: set = set()

    for device in devices:
        camera = by_identity.get(device.identity)
        if camera is None:
            result.new.append(device)
            result.detail[device.identity] = _describe(device)
        else:
            matched.add(camera.id)
            result.present.append(camera)
            result.detail[camera.id] = _describe(device)

    # Everything registered that no probe accounted for. A network camera was
    # never going to be found by probing, and an all-sky camera writing to a
    # path outside the well-known list was not either — both are settled here,
    # rather than being reported missing for the wrong reason.
    unmatched = [c for c in registered if c.id not in matched]

    to_check = [c for c in unmatched if c.kind == NET and check_network]
    reachability = {}
    if to_check:
        with ThreadPoolExecutor(max_workers=min(8, len(to_check))) as pool:
            for camera, outcome in zip(
                to_check, pool.map(lambda c: _is_reachable(c, timeout), to_check)
            ):
                reachability[camera.id] = outcome

    for camera in unmatched:
        if camera.kind == NET:
            if not check_network:
                result.present.append(camera)
                result.detail[camera.id] = "not contacted"
                continue
            reachable, why = reachability[camera.id]
            (result.present if reachable else result.missing).append(camera)
            result.detail[camera.id] = why
        elif camera.kind == ALLSKY:
            current = resolve_allsky_path(camera.path or "")
            if current:
                result.present.append(camera)
                # Naming the file is only worth the width for a glob, where
                # which file matched is the thing you cannot see already.
                result.detail[camera.id] = (
                    f"newest match: {current}"
                    if current != camera.path
                    else "an image is there"
                )
            else:
                result.missing.append(camera)
                result.detail[camera.id] = "no image at that path"
        else:
            result.missing.append(camera)
            result.detail[camera.id] = "not attached to this machine"

    result.present.sort(key=lambda c: c.id)
    result.missing.sort(key=lambda c: c.id)
    return result


def _detect_webcams():
    # Imported here so that `arcsecond allsky detect` — and every command that
    # only reads the store — works on a machine without OpenCV installed.
    from .sources.opencv import detect_webcams

    return detect_webcams()
