"""
Network camera sources — cameras reached over the network rather than plugged
into the machine running the proxy.

Two transports, chosen from the URL scheme:

    rtsp:// rtsps://   video stream, decoded and re-encoded as JPEG
    http:// https://   JPEG bytes passed through untouched, either a still
                       image fetched repeatedly or an MJPEG stream

An all-sky camera whose software runs on another machine publishes its JPEG
over HTTP, and is fetched by exactly the same code — see ``AllSkyHTTPSource``,
which differs from a webcam only in what it calls itself and how often it asks.

Camera URLs often carry a password. Nothing here ever lets one out: every
place a URL is logged, reported or put in an error message goes through
``redact_url`` first. That matters because the proxy forwards error text
straight to its client (see ``handle_stream`` in proxy.py).
"""

import asyncio
import hashlib
import logging
import os
import socket
from typing import Optional
from urllib.parse import urlsplit, urlunsplit

from . import mdns
from .base import FrameSource, SourceInfo

logger = logging.getLogger(__name__)

RTSP_SCHEMES = ("rtsp", "rtsps")
HTTP_SCHEMES = ("http", "https")
SUPPORTED_SCHEMES = RTSP_SCHEMES + HTTP_SCHEMES

_RTSP_FRAME_INTERVAL = 0.1  # seconds → ~10 fps, same as the USB webcam source
_SNAPSHOT_INTERVAL = 1.0  # seconds — still-image cameras rarely update faster
# All-sky software writes one image every 30-120 seconds, so asking every
# second would be sixty questions for one answer. Kept in step with the
# file-watch source, which polls a local all-sky image at the same cadence.
_ALLSKY_SNAPSHOT_INTERVAL = 5.0  # seconds
_JPEG_QUALITY = 60  # 0-100, only used on the RTSP path
_CONNECT_TIMEOUT = 10.0  # seconds
_READ_TIMEOUT = 30.0  # seconds without a byte before we call the stream dead


def redact_url(url: str) -> str:
    """Return ``url`` with any embedded password replaced by ``***``."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return "<unreadable url>"

    if not parts.password:
        return url

    netloc = parts.hostname or ""
    if parts.port:
        netloc = f"{netloc}:{parts.port}"
    if parts.username:
        netloc = f"{parts.username}:***@{netloc}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


class RTSPSource(FrameSource):
    """RTSP video stream, decoded with OpenCV and re-encoded as JPEG."""

    # A camera reached over the network is a webcam like any other, and is
    # listed, added and forgotten by the same commands. Only how it is reached
    # differs, and that is reported as the transport below.
    kind = "webcam"
    poll_interval = _RTSP_FRAME_INTERVAL
    # Shared between viewers. Unlike the HTTP source below there is no
    # per-viewer state — every read returns whatever frame is current — and
    # IP cameras typically refuse more than a handful of RTSP sessions at once.
    shareable = True

    def __init__(self, source_id: str, url: str, label: Optional[str] = None):
        self.id = source_id
        self.url = url
        self.label = label or source_id
        self._cap = None

    async def open(self) -> None:
        import cv2

        # FFmpeg defaults to UDP, which tears badly over Wi-Fi, and to a buffer
        # deep enough to put the preview seconds behind reality. Both have to be
        # in place before the capture is opened. setdefault so an operator who
        # set the variable themselves keeps their choice.
        os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")

        loop = asyncio.get_running_loop()
        self._cap = await loop.run_in_executor(
            None, cv2.VideoCapture, self.url, cv2.CAP_FFMPEG
        )
        if not await loop.run_in_executor(None, self._cap.isOpened):
            await self.close()
            raise RuntimeError(f"Cannot connect to {redact_url(self.url)}")

        await loop.run_in_executor(None, self._cap.set, cv2.CAP_PROP_BUFFERSIZE, 1)

    async def read(self) -> Optional[bytes]:
        import cv2

        loop = asyncio.get_running_loop()

        def _read_and_encode():
            ok, frame = self._cap.read()
            if not ok:
                # Same contract as the webcam source: None means "no new frame",
                # so a failed grab has to raise instead.
                raise RuntimeError(f"Lost the stream from {redact_url(self.url)}")
            ok2, buf = cv2.imencode(
                ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, _JPEG_QUALITY]
            )
            if not ok2:
                raise RuntimeError(f"JPEG encode failed for {redact_url(self.url)}")
            return buf.tobytes()

        return await loop.run_in_executor(None, _read_and_encode)

    async def close(self) -> None:
        if self._cap is None:
            return
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._cap.release)
        self._cap = None

    def info(self) -> SourceInfo:
        return SourceInfo(
            id=self.id,
            kind=self.kind,
            label=self.label,
            extra={"url": redact_url(self.url), "transport": "rtsp"},
        )


class HTTPImageSource(FrameSource):
    """HTTP camera, either a still image or an MJPEG stream.

    Which one it is cannot be told from the URL, so ``open()`` makes one
    request and looks at the content type it gets back.
    """

    kind = "webcam"  # see RTSPSource
    poll_interval = _SNAPSHOT_INTERVAL
    # Not shared. A still-image camera only sends a frame on when the picture
    # has changed since the last one *that viewer* received, so two viewers
    # sharing one instance would make the second miss frames — the same reason
    # the all-sky file source is not shared either.
    shareable = False

    def __init__(self, source_id: str, url: str, label: Optional[str] = None):
        self.id = source_id
        self.url = url
        self.label = label or source_id
        self._session = None
        self._response = None
        self._multipart = None
        self._mode = None
        self._pending: Optional[bytes] = None
        self._etag: Optional[str] = None
        self._last_modified: Optional[str] = None
        self._digest: Optional[bytes] = None
        self._resolver = None

    async def open(self) -> None:
        import aiohttp

        timeout = aiohttp.ClientTimeout(
            total=None, connect=_CONNECT_TIMEOUT, sock_read=_READ_TIMEOUT
        )
        # aiohttp never closes a resolver it was handed, so this one is kept
        # and closed alongside the session.
        self._resolver = _mdns_aware_resolver()
        self._session = aiohttp.ClientSession(
            timeout=timeout,
            connector=aiohttp.TCPConnector(resolver=self._resolver),
        )

        try:
            response = await self._session.get(self.url)
        except Exception as e:
            await self.close()
            raise RuntimeError(
                f"Cannot connect to {redact_url(self.url)}: {e}"
            ) from None

        if response.status != 200:
            status = response.status
            response.release()
            await self.close()
            raise RuntimeError(f"{redact_url(self.url)} answered HTTP {status}")

        content_type = (response.headers.get("Content-Type") or "").lower()

        if content_type.startswith("multipart/"):
            self._mode = "mjpeg"
            self._response = response
            self._multipart = aiohttp.MultipartReader.from_response(response)
            # Frames arrive when the camera sends them, so there is nothing to
            # wait for between reads.
            self.poll_interval = 0.0
        else:
            self._mode = "snapshot"
            # Keep the image this request already returned — it is the first
            # frame, so fetching it a second time would be wasted. Reading the
            # body out in full is also how the connection gets handed back to
            # the pool cleanly.
            self._pending = await response.read()
            self._remember_validators(response)

        logger.info(
            "Live-image proxy: %s is a %s camera.", redact_url(self.url), self._mode
        )

    async def read(self) -> Optional[bytes]:
        if self._mode == "mjpeg":
            return await self._read_mjpeg()
        return await self._read_snapshot()

    async def _read_mjpeg(self) -> Optional[bytes]:
        part = await self._multipart.next()
        if part is None:
            raise RuntimeError(f"{redact_url(self.url)} closed the stream")
        return await part.read(decode=False)

    def _remember_validators(self, response) -> None:
        self._etag = response.headers.get("ETag")
        self._last_modified = response.headers.get("Last-Modified")

    def _is_new(self, data: bytes) -> bool:
        # A camera offering ETag or Last-Modified tells us itself, by answering
        # 304 below. Every other camera gets its images compared, so that an
        # unchanged picture is not sent on over and over.
        if self._etag or self._last_modified:
            return True
        digest = hashlib.sha256(data).digest()
        if digest == self._digest:
            return False
        self._digest = digest
        return True

    async def _read_snapshot(self) -> Optional[bytes]:
        if self._pending is not None:
            data, self._pending = self._pending, None
            return data if self._is_new(data) else None

        headers = {}
        if self._etag:
            headers["If-None-Match"] = self._etag
        if self._last_modified:
            headers["If-Modified-Since"] = self._last_modified

        async with self._session.get(self.url, headers=headers) as response:
            if response.status == 304:
                return None
            if response.status != 200:
                raise RuntimeError(
                    f"{redact_url(self.url)} answered HTTP {response.status}"
                )
            data = await response.read()
            self._remember_validators(response)

        return data if self._is_new(data) else None

    async def close(self) -> None:
        if self._response is not None:
            self._response.release()
            self._response = None
        self._multipart = None
        if self._session is not None:
            await self._session.close()
            self._session = None
        if self._resolver is not None:
            await self._resolver.close()
            self._resolver = None

    def info(self) -> SourceInfo:
        return SourceInfo(
            id=self.id,
            kind=self.kind,
            label=self.label,
            extra={
                "url": redact_url(self.url),
                "transport": urlsplit(self.url).scheme or "http",
            },
        )


async def _resolve_over_mdns(host: str) -> list:
    """``host``'s addresses according to the machine that owns the name."""
    if not mdns.is_mdns_name(host):
        return []
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, mdns.resolve, host)


def _mdns_aware_resolver():
    """An aiohttp resolver that falls back to mDNS for a ``.local`` name.

    The machine's own resolver is asked first and is almost always the end of
    it. Only when it has no answer, and only for a ``.local`` name, is the
    network asked directly — see ``mdns``. A camera registered by such a name
    therefore keeps working when its address changes, which is the whole
    reason for resolving at connect time rather than storing an address.

    Built inside a function because aiohttp is an optional dependency: the CLI
    has to stay importable on a machine that never installed the proxy extra.
    """
    import aiohttp
    from aiohttp.abc import AbstractResolver

    class _MDNSFallbackResolver(AbstractResolver):
        def __init__(self):
            self._default = aiohttp.DefaultResolver()

        async def resolve(self, host, port=0, family=socket.AF_INET):
            try:
                return await self._default.resolve(host, port, family)
            except OSError:
                # Only A records are asked for, so an IPv6-only lookup is not
                # something this can answer.
                if family not in (socket.AF_INET, socket.AF_UNSPEC):
                    raise
                addresses = await _resolve_over_mdns(host)
                if not addresses:
                    raise
                # Every address the machine answered with, in the order it
                # gave them: aiohttp tries them in turn, which is what makes
                # a responder with several interfaces work.
                return [
                    {
                        "hostname": host,
                        "host": address,
                        "port": port,
                        "family": socket.AF_INET,
                        "proto": 0,
                        "flags": socket.AI_NUMERICHOST,
                    }
                    for address in addresses
                ]

        async def close(self) -> None:
            await self._default.close()

    return _MDNSFallbackResolver()


class AllSkyHTTPSource(HTTPImageSource):
    """An all-sky camera that publishes its JPEG over HTTP.

    Fetched exactly like any other HTTP camera — conditional requests, and a
    digest comparison for a server offering neither ETag nor Last-Modified —
    so a sky that has not changed is never sent on twice. What differs is what
    it calls itself and how often it asks: an all-sky camera reached over the
    network is an all-sky camera still, just as a webcam is a webcam whether
    it arrives over USB or over RTSP.
    """

    kind = "allsky"
    poll_interval = _ALLSKY_SNAPSHOT_INTERVAL


def build_allsky_source(
    source_id: str, url: str, label: Optional[str] = None
) -> FrameSource:
    """The source for an all-sky camera registered by address.

    HTTP only. An all-sky camera is registered by the JPEG its software
    publishes, and an RTSP address is a video stream — `arcsecond allsky add`
    turns one away with the command that does take it, so reaching this with
    one would be a bug rather than something an operator typed.
    """
    scheme = urlsplit(url).scheme.lower()
    if scheme not in HTTP_SCHEMES:
        raise KeyError(
            f"{redact_url(url)} cannot be served as an all-sky camera. "
            f"Expected one of: {', '.join(s + '://' for s in HTTP_SCHEMES)}."
        )
    return AllSkyHTTPSource(source_id, url, label)


def build_network_source(
    source_id: str, url: str, label: Optional[str] = None
) -> FrameSource:
    """Return the right source class for ``url``, based on its scheme."""
    scheme = urlsplit(url).scheme.lower()
    if scheme in RTSP_SCHEMES:
        return RTSPSource(source_id, url, label)
    if scheme in HTTP_SCHEMES:
        return HTTPImageSource(source_id, url, label)
    raise KeyError(
        f"{redact_url(url)} uses an unsupported scheme. "
        f"Expected one of: {', '.join(SUPPORTED_SCHEMES)}."
    )
