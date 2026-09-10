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

A camera registered by address cannot be discovered: there is no protocol to
ask a subnet which of it is a camera, so neither a network camera nor an
all-sky camera published over HTTP is ever *new*. Either can still be confirmed
present or reported missing, and that is done with a plain TCP connection to
the address rather than by pulling a frame. Opening an RTSP
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
from .sources.mdns import resolve as resolve_over_mdns
from .sources.network import HTTP_SCHEMES
from .store import ALLSKY, USB, Camera

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


def is_reachable(url: str, timeout: float = NETWORK_TIMEOUT) -> tuple:
    """``(reachable, why)`` for one camera address.

    Takes the URL rather than the camera because ``add`` asks this about an
    address that is not registered yet, and ``detect`` about one that is.

    Only the address is contacted, and the answer never contains the URL's
    password: the endpoint named here is the host and port alone.
    """
    endpoint = _network_endpoint(url or "")
    if endpoint is None:
        return False, "the address cannot be read"
    host, port = endpoint

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, f"answering on {host}:{port}"
    except socket.gaierror:
        pass
    except OSError as e:
        return False, f"no answer on {host}:{port} ({e.strerror or e})"

    # The machine's resolver has no answer. A `.local` name can still be
    # answered by the machine that owns it, which is exactly what the proxy
    # does when it connects — so the same fallback belongs here, or `detect`
    # would call a camera missing that the proxy serves perfectly well.
    #
    # Only for the addresses the proxy fetches itself: an RTSP stream is
    # opened by FFmpeg, with its own resolver and no way in, so promising that
    # one works would be a promise this cannot keep.
    if urlsplit(url).scheme.lower() not in HTTP_SCHEMES:
        return False, f"{host} cannot be resolved"

    addresses = resolve_over_mdns(host)
    if not addresses:
        # Told apart from a connection that fails: nothing is wrong with the
        # camera, the name simply does not resolve here, and that is a
        # different thing to go and fix.
        return False, f"{host} cannot be resolved"

    # A machine with several interfaces answers with an address for each, and
    # only some of them are reachable from here — the same reason the proxy
    # hands the whole list to aiohttp rather than picking one.
    why = ""
    for address in addresses:
        try:
            with socket.create_connection((address, port), timeout=timeout):
                return True, f"answering on {address}:{port}, found over mDNS"
        except OSError as e:
            why = f"no answer on {address}:{port} ({e.strerror or e})"
    return False, why


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------


def _probe_safely(probe, what: str) -> list:
    """Run one probe. A probe that fails must not take the report down with it.

    A machine without OpenCV, or a directory that cannot be read, should still
    get an answer about everything else — including which of its registered
    cameras are missing.
    """
    try:
        return list(probe())
    except Exception as e:
        logger.warning("%s detection failed: %s", what, e)
        return []


def _probe(kinds) -> list[DetectedDevice]:
    devices: list[DetectedDevice] = []
    if USB in kinds:
        devices.extend(_probe_safely(_detect_webcams, "Webcam"))
    if ALLSKY in kinds:
        devices.extend(_probe_safely(detect_allsky, "All-sky"))
    return devices


def _reachability(cameras: list[Camera], timeout: float) -> dict:
    """``{id: (reachable, why)}``, contacting the cameras concurrently.

    Concurrently because the answer for a camera that is switched off only
    arrives when the connection times out, and doing that one after another
    would make the wait the sum of every camera that is down.
    """
    if not cameras:
        return {}
    with ThreadPoolExecutor(max_workers=min(8, len(cameras))) as pool:
        outcomes = pool.map(lambda c: is_reachable(c.url or "", timeout), cameras)
        return {camera.id: outcome for camera, outcome in zip(cameras, outcomes)}


def _settle_allsky(camera: Camera) -> tuple:
    current = resolve_allsky_path(camera.path or "")
    if not current:
        return False, "no image at that path"
    # Naming the file is only worth the width for a glob, where which file
    # matched is the thing you cannot see already.
    if current != camera.path:
        return True, f"newest match: {current}"
    return True, "an image is there"


def _settle_unmatched(camera: Camera, check_network: bool, reachability: dict) -> tuple:
    """``(present, why)`` for a registered camera no probe accounted for.

    A camera reached over the network was never going to be found by probing,
    and an all-sky camera writing to a path outside the well-known list was not
    either — so neither is missing merely for having gone unprobed.

    Which check applies follows the address, not the kind: an all-sky camera
    registered by URL is confirmed the way every other camera at an address is.
    """
    if camera.url:
        if not check_network:
            return True, "not contacted"
        return reachability[camera.id]
    if camera.kind == ALLSKY:
        return _settle_allsky(camera)
    return False, "not attached to this machine"


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

    result = DetectionReport()
    matched: set = set()

    for device in _probe(kinds):
        camera = by_identity.get(device.identity)
        if camera is None:
            result.new.append(device)
            result.detail[device.identity] = _describe(device)
        else:
            matched.add(camera.id)
            result.present.append(camera)
            result.detail[camera.id] = _describe(device)

    unmatched = [c for c in registered if c.id not in matched]
    reachability = _reachability(
        [c for c in unmatched if c.url and check_network], timeout
    )

    for camera in unmatched:
        present, why = _settle_unmatched(camera, check_network, reachability)
        (result.present if present else result.missing).append(camera)
        result.detail[camera.id] = why

    result.present.sort(key=lambda c: c.id)
    result.missing.sort(key=lambda c: c.id)
    return result


def _detect_webcams():
    # Imported here so that `arcsecond allsky detect` — and every command that
    # only reads the store — works on a machine without OpenCV installed.
    from .sources.opencv import detect_webcams

    return detect_webcams()
