"""Tests for network camera sources (``netcam:``).

The async sources are driven with ``asyncio.run`` from ordinary sync tests, so
no pytest-asyncio dependency is needed.
"""

import asyncio
import sys
from unittest.mock import MagicMock, patch

import click
import pytest

from arcsecond.imagesources.commands import (
    _expand_env_vars,
    _parse_netcam_overrides,
)
from arcsecond.imagesources.registry import NetcamOverride, Registry
from arcsecond.imagesources.sources.network import (
    HTTPImageSource,
    RTSPSource,
    build_network_source,
    redact_url,
)

JPEG_A = b"\xff\xd8\xff\xe0 first frame \xff\xd9"
JPEG_B = b"\xff\xd8\xff\xe0 second frame \xff\xd9"

RTSP_URL = "rtsp://admin:hunter2@192.168.1.42:554/stream1"


# ---------------------------------------------------------------------------
# redact_url
# ---------------------------------------------------------------------------


def test_redact_url_hides_the_password():
    assert redact_url(RTSP_URL) == "rtsp://admin:***@192.168.1.42:554/stream1"


def test_redact_url_keeps_the_query_string():
    redacted = redact_url("http://u:p@cam.local/snap.jpg?size=full&n=2")
    assert redacted == "http://u:***@cam.local/snap.jpg?size=full&n=2"


def test_redact_url_leaves_urls_without_credentials_alone():
    url = "http://192.168.1.42/snapshot.jpg"
    assert redact_url(url) == url


def test_redact_url_leaves_a_bare_username_alone():
    assert redact_url("rtsp://admin@cam.local/s") == "rtsp://admin@cam.local/s"


# ---------------------------------------------------------------------------
# Option parsing
# ---------------------------------------------------------------------------


def test_parse_netcam_overrides_reads_id_and_url():
    (override,) = _parse_netcam_overrides(("dome=rtsp://cam.local/stream1",))
    assert override.id == "dome"
    assert override.url == "rtsp://cam.local/stream1"


def test_parse_netcam_overrides_splits_on_the_first_equals_only():
    """A query string keeps its own '=' signs."""
    (override,) = _parse_netcam_overrides(("dome=http://cam.local/s.jpg?size=full",))
    assert override.url == "http://cam.local/s.jpg?size=full"


def test_parse_netcam_overrides_accepts_several_cameras():
    overrides = _parse_netcam_overrides(
        ("dome=rtsp://a.local/s", "roof=http://b.local/s.jpg")
    )
    assert [o.id for o in overrides] == ["dome", "roof"]


@pytest.mark.parametrize("value", ["no-equals-sign", "=rtsp://cam.local/s", "dome="])
def test_parse_netcam_overrides_rejects_malformed_values(value):
    with pytest.raises(click.BadParameter):
        _parse_netcam_overrides((value,))


def test_parse_netcam_overrides_rejects_an_unsupported_scheme():
    with pytest.raises(click.BadParameter, match="must start with"):
        _parse_netcam_overrides(("dome=ftp://cam.local/s",))


def test_parse_netcam_overrides_expands_an_environment_variable(monkeypatch):
    monkeypatch.setenv("DOME_CAM_PW", "hunter2")
    (override,) = _parse_netcam_overrides(
        ("dome=rtsp://admin:${DOME_CAM_PW}@cam.local/s",),
    )
    assert override.url == "rtsp://admin:hunter2@cam.local/s"


def test_parse_netcam_overrides_reports_a_missing_environment_variable(monkeypatch):
    monkeypatch.delenv("DOME_CAM_PW", raising=False)
    with pytest.raises(click.BadParameter, match="DOME_CAM_PW"):
        _parse_netcam_overrides(("dome=rtsp://admin:${DOME_CAM_PW}@cam.local/s",))


def test_parse_netcam_overrides_does_not_echo_the_password(monkeypatch):
    """A rejected URL must not put the password in the error message."""
    monkeypatch.setenv("DOME_CAM_PW", "hunter2")
    with pytest.raises(click.BadParameter) as excinfo:
        _parse_netcam_overrides(("dome=ftp://admin:${DOME_CAM_PW}@cam.local/s",))
    assert "hunter2" not in str(excinfo.value)


def test_expand_env_vars_reports_a_stray_dollar_sign():
    with pytest.raises(click.BadParameter, match=r"\$\$"):
        _expand_env_vars("rtsp://admin:pa$$@cam.local/s".replace("$$", "$"))


# ---------------------------------------------------------------------------
# Scheme dispatch
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("url", ["rtsp://cam.local/s", "rtsps://cam.local/s"])
def test_build_network_source_picks_rtsp(url):
    assert isinstance(build_network_source("netcam:dome", url), RTSPSource)


@pytest.mark.parametrize("url", ["http://cam.local/s.jpg", "https://cam.local/s.jpg"])
def test_build_network_source_picks_http(url):
    assert isinstance(build_network_source("netcam:dome", url), HTTPImageSource)


def test_build_network_source_rejects_an_unsupported_scheme():
    with pytest.raises(KeyError):
        build_network_source("netcam:dome", "ftp://cam.local/s")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_registry_lists_registered_network_cameras():
    registry = Registry(netcam_overrides=[NetcamOverride(id="dome", url=RTSP_URL)])
    with (
        patch("arcsecond.imagesources.registry.detect_webcams", return_value=[]),
        patch("arcsecond.imagesources.registry.detect_allsky", return_value=[]),
    ):
        infos = registry.detect()

    assert [i.id for i in infos] == ["netcam:dome"]
    assert infos[0].kind == "netcam"
    assert infos[0].extra["url"] == "rtsp://admin:***@192.168.1.42:554/stream1"


def test_registry_never_reports_a_password_to_the_backend():
    """/detect output goes to the backend — it must not carry credentials."""
    registry = Registry(netcam_overrides=[NetcamOverride(id="dome", url=RTSP_URL)])
    with (
        patch("arcsecond.imagesources.registry.detect_webcams", return_value=[]),
        patch("arcsecond.imagesources.registry.detect_allsky", return_value=[]),
    ):
        infos = registry.detect()

    assert "hunter2" not in str(infos)


def test_registry_builds_a_registered_network_camera():
    registry = Registry(
        netcam_overrides=[NetcamOverride(id="dome", url="rtsp://cam.local/s")]
    )
    source = registry._build("netcam:dome")
    assert isinstance(source, RTSPSource)
    assert source.url == "rtsp://cam.local/s"


def test_registry_rejects_an_unregistered_network_camera():
    registry = Registry(netcam_overrides=[])
    with pytest.raises(KeyError, match="netcam:dome"):
        registry._build("netcam:dome")


# ---------------------------------------------------------------------------
# HTTP cameras, against a real local server
# ---------------------------------------------------------------------------


async def _start_server(handler):
    from aiohttp import web

    app = web.Application()
    app.router.add_get("/cam", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]
    return runner, f"http://127.0.0.1:{port}/cam"


def _run_against(handler, body):
    """Serve ``handler`` locally, then run ``body(url)`` against it."""

    async def _main():
        runner, url = await _start_server(handler)
        try:
            return await body(url)
        finally:
            await runner.cleanup()

    return asyncio.run(_main())


def test_http_snapshot_camera_returns_the_image_then_nothing_until_it_changes():
    from aiohttp import web

    # open() keeps the image it fetches, so it becomes the first read; the
    # other two entries answer the two reads after that.
    served = [JPEG_A, JPEG_A, JPEG_B]

    async def handler(request):
        return web.Response(body=served.pop(0), content_type="image/jpeg")

    async def body(url):
        source = HTTPImageSource("netcam:dome", url)
        await source.open()
        try:
            return [await source.read() for _ in range(3)]
        finally:
            await source.close()

    assert _run_against(handler, body) == [JPEG_A, None, JPEG_B]


def test_http_snapshot_camera_honours_an_etag():
    from aiohttp import web

    async def handler(request):
        if request.headers.get("If-None-Match") == '"v1"':
            return web.Response(status=304)
        return web.Response(
            body=JPEG_A, content_type="image/jpeg", headers={"ETag": '"v1"'}
        )

    async def body(url):
        source = HTTPImageSource("netcam:dome", url)
        await source.open()
        try:
            return [await source.read(), await source.read()]
        finally:
            await source.close()

    assert _run_against(handler, body) == [JPEG_A, None]


def test_http_mjpeg_camera_yields_each_frame():
    from aiohttp import web

    async def handler(request):
        response = web.StreamResponse(
            headers={"Content-Type": "multipart/x-mixed-replace; boundary=FRAME"}
        )
        await response.prepare(request)
        for payload in (JPEG_A, JPEG_B):
            await response.write(
                b"--FRAME\r\nContent-Type: image/jpeg\r\n"
                b"Content-Length: " + str(len(payload)).encode() + b"\r\n\r\n"
            )
            await response.write(payload + b"\r\n")
        await response.write(b"--FRAME--\r\n")
        await response.write_eof()
        return response

    async def body(url):
        source = HTTPImageSource("netcam:dome", url)
        await source.open()
        try:
            assert source._mode == "mjpeg"
            return [await source.read(), await source.read()]
        finally:
            await source.close()

    assert _run_against(handler, body) == [JPEG_A, JPEG_B]


def test_http_camera_reports_an_error_status_without_the_password():
    from aiohttp import web

    async def handler(request):
        return web.Response(status=401)

    async def body(url):
        # Splice credentials into the URL the local server is listening on.
        with_password = url.replace("http://", "http://admin:hunter2@")
        source = HTTPImageSource("netcam:dome", with_password)
        with pytest.raises(RuntimeError) as excinfo:
            await source.open()
        return str(excinfo.value)

    message = _run_against(handler, body)
    assert "401" in message
    assert "hunter2" not in message


# ---------------------------------------------------------------------------
# RTSP cameras, with OpenCV mocked out
# ---------------------------------------------------------------------------


def _fake_cv2():
    cv2 = MagicMock()
    cv2.CAP_FFMPEG = 1900
    cv2.CAP_PROP_BUFFERSIZE = 38
    cv2.IMWRITE_JPEG_QUALITY = 1
    buffer = MagicMock()
    buffer.tobytes.return_value = JPEG_A
    cv2.imencode.return_value = (True, buffer)
    cv2.VideoCapture.return_value.isOpened.return_value = True
    cv2.VideoCapture.return_value.read.return_value = (True, "raw-frame")
    return cv2


def test_rtsp_source_opens_over_tcp_with_a_shallow_buffer(monkeypatch):
    monkeypatch.delenv("OPENCV_FFMPEG_CAPTURE_OPTIONS", raising=False)
    cv2 = _fake_cv2()

    async def body():
        source = RTSPSource("netcam:dome", RTSP_URL)
        await source.open()
        await source.close()

    with patch.dict(sys.modules, {"cv2": cv2}):
        asyncio.run(body())

    import os

    assert os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] == "rtsp_transport;tcp"
    cv2.VideoCapture.assert_called_once_with(RTSP_URL, cv2.CAP_FFMPEG)
    cv2.VideoCapture.return_value.set.assert_called_once_with(
        cv2.CAP_PROP_BUFFERSIZE, 1
    )


def test_rtsp_source_keeps_an_operator_set_transport(monkeypatch):
    monkeypatch.setenv("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;udp")
    cv2 = _fake_cv2()

    async def body():
        source = RTSPSource("netcam:dome", RTSP_URL)
        await source.open()
        await source.close()

    with patch.dict(sys.modules, {"cv2": cv2}):
        asyncio.run(body())

    import os

    assert os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] == "rtsp_transport;udp"


def test_rtsp_source_returns_an_encoded_frame():
    cv2 = _fake_cv2()

    async def body():
        source = RTSPSource("netcam:dome", RTSP_URL)
        await source.open()
        try:
            return await source.read()
        finally:
            await source.close()

    with patch.dict(sys.modules, {"cv2": cv2}):
        assert asyncio.run(body()) == JPEG_A


def test_rtsp_source_raises_without_the_password_when_it_cannot_connect():
    cv2 = _fake_cv2()
    cv2.VideoCapture.return_value.isOpened.return_value = False

    async def body():
        source = RTSPSource("netcam:dome", RTSP_URL)
        with pytest.raises(RuntimeError) as excinfo:
            await source.open()
        return str(excinfo.value)

    with patch.dict(sys.modules, {"cv2": cv2}):
        message = asyncio.run(body())

    assert "192.168.1.42" in message
    assert "hunter2" not in message


def test_rtsp_source_raises_without_the_password_when_a_frame_is_lost():
    cv2 = _fake_cv2()
    cv2.VideoCapture.return_value.read.return_value = (False, None)

    async def body():
        source = RTSPSource("netcam:dome", RTSP_URL)
        await source.open()
        try:
            with pytest.raises(RuntimeError) as excinfo:
                await source.read()
            return str(excinfo.value)
        finally:
            await source.close()

    with patch.dict(sys.modules, {"cv2": cv2}):
        assert "hunter2" not in asyncio.run(body())


# ---------------------------------------------------------------------------
# Sharing rules
# ---------------------------------------------------------------------------


def test_rtsp_is_shared_but_http_is_not():
    """RTSP sessions are scarce; HTTP sources keep per-viewer state."""
    assert RTSPSource("netcam:a", "rtsp://cam.local/s").shareable is True
    assert HTTPImageSource("netcam:b", "http://cam.local/s.jpg").shareable is False
