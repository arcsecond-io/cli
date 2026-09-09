"""Tests for cameras reached over the network.

These are webcams like any other — same commands, same store, same ``kind`` on
the wire — and only the transport differs. That is asserted here rather than
assumed, because it is the whole reason the separate ``netcam`` group is gone.

The async sources are driven with ``asyncio.run`` from ordinary sync tests, so
no pytest-asyncio dependency is needed.
"""

import asyncio
import sys
from unittest.mock import MagicMock, patch

import click
import pytest

from arcsecond.imagesources.commands import _expand_env_vars
from arcsecond.imagesources.registry import Registry, build_source
from arcsecond.imagesources.sources.network import (
    AllSkyHTTPSource,
    HTTPImageSource,
    RTSPSource,
    redact_url,
)
from arcsecond.imagesources.store import ALLSKY, NET, USB, Camera

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
# Environment variables in camera URLs
# ---------------------------------------------------------------------------


def test_expand_env_vars_fills_in_a_variable(monkeypatch):
    monkeypatch.setenv("DOME_CAM_PW", "hunter2")
    assert _expand_env_vars("rtsp://a:${DOME_CAM_PW}@c/s") == "rtsp://a:hunter2@c/s"


def test_expand_env_vars_reports_a_missing_variable(monkeypatch):
    monkeypatch.delenv("DOME_CAM_PW", raising=False)
    with pytest.raises(click.BadParameter, match="DOME_CAM_PW"):
        _expand_env_vars("rtsp://a:${DOME_CAM_PW}@c/s")


def test_expand_env_vars_does_not_echo_the_password(monkeypatch):
    monkeypatch.setenv("DOME_CAM_PW", "hunter2")
    with pytest.raises(click.BadParameter) as e:
        _expand_env_vars("rtsp://a:${DOME_CAM_PW}@c/s${MISSING}")
    assert "hunter2" not in str(e.value)


def test_expand_env_vars_reports_a_stray_dollar_sign():
    with pytest.raises(click.BadParameter, match=r"\$\$"):
        _expand_env_vars("rtsp://admin:pa$$@cam.local/s".replace("$$", "$"))


# ---------------------------------------------------------------------------
# A network camera is a webcam
# ---------------------------------------------------------------------------


def _netcam(url=RTSP_URL, cam_id="abc"):
    return Camera(id=cam_id, kind=NET, url=url)


@pytest.mark.parametrize("url", ["rtsp://cam.local/s", "http://cam.local/snap.jpg"])
def test_a_network_camera_reports_the_same_kind_as_a_usb_one(url):
    """`kind` says what it is; `extra.transport` says how it is reached."""
    from arcsecond.imagesources.sources.opencv import OpenCVWebcamSource

    over_the_network = build_source(_netcam(url)).info()
    over_usb = OpenCVWebcamSource(0, source_id="xyz").info()

    assert over_the_network.kind == over_usb.kind == "webcam"
    assert over_the_network.extra["transport"] != over_usb.extra["transport"]


def test_the_registry_lists_a_registered_network_camera():
    registry = Registry(cameras=[_netcam(cam_id="abc")])
    (info,) = registry.infos()
    assert info.id == "abc"
    assert info.extra["url"] == "rtsp://admin:***@192.168.1.42:554/stream1"


def test_the_registry_never_reports_a_password_to_the_backend():
    """/detect output goes to the backend — it must not carry credentials."""
    registry = Registry(cameras=[_netcam()])
    assert "hunter2" not in str(registry.infos())


def test_listing_contacts_nothing():
    """A camera that is switched off must not hold the list up for the others."""
    registry = Registry(cameras=[_netcam(url="rtsp://192.0.2.1/s")])
    with patch.object(RTSPSource, "open", side_effect=AssertionError("opened!")):
        assert len(registry.infos()) == 1


def test_the_registry_builds_a_registered_network_camera():
    registry = Registry(cameras=[_netcam(url="rtsp://cam.local/s", cam_id="abc")])
    source = registry._build("abc")
    assert isinstance(source, RTSPSource)
    assert source.url == "rtsp://cam.local/s"


def test_the_registry_rejects_an_unregistered_camera():
    with pytest.raises(KeyError, match="abc"):
        Registry()._build("abc")


# ---------------------------------------------------------------------------
# All-sky cameras reached over the network
# ---------------------------------------------------------------------------

SKY_URL = "http://sky.local/allsky/latest.jpg"


def _sky_over_http(url=SKY_URL, cam_id="sky"):
    return Camera(id=cam_id, kind=ALLSKY, url=url)


def test_an_all_sky_camera_over_http_is_announced_as_an_all_sky_camera():
    """The backend must see the same kind wherever the image is fetched from."""
    from arcsecond.imagesources.sources.filewatch import FileWatchSource

    over_http = build_source(_sky_over_http()).info()
    on_disk = FileWatchSource("sky", "/srv/allsky/latest.jpg").info()

    assert over_http.kind == on_disk.kind == "allsky"
    assert over_http.extra["transport"] == "http"
    assert on_disk.extra["transport"] == "file"


def test_the_same_address_is_an_all_sky_camera_or_a_webcam_as_registered():
    assert build_source(_sky_over_http()).info().kind == "allsky"
    assert build_source(_netcam(url=SKY_URL)).info().kind == "webcam"


def test_an_all_sky_camera_over_http_is_polled_at_its_own_cadence():
    """One image every 30-120 seconds: asking every second buys nothing."""
    sky = build_source(_sky_over_http())
    webcam = build_source(_netcam(url=SKY_URL))
    assert isinstance(sky, AllSkyHTTPSource)
    assert sky.poll_interval > webcam.poll_interval


def test_the_registry_builds_an_all_sky_camera_from_its_address():
    registry = Registry(cameras=[_sky_over_http(cam_id="sky")])
    source = registry._build("sky")
    assert isinstance(source, AllSkyHTTPSource)
    assert source.url == SKY_URL


def test_the_registry_builds_an_all_sky_camera_from_its_path(tmp_path):
    from arcsecond.imagesources.sources.filewatch import FileWatchSource

    image = tmp_path / "latest.jpg"
    registry = Registry(cameras=[Camera(id="sky", kind=ALLSKY, path=str(image))])
    assert isinstance(registry._build("sky"), FileWatchSource)


def test_an_all_sky_address_never_reports_its_password():
    registry = Registry(
        cameras=[_sky_over_http(url="http://sky:hunter2@10.0.0.9/latest.jpg")]
    )
    assert "hunter2" not in str(registry.infos())


def test_a_video_stream_is_not_an_all_sky_camera():
    """`allsky add` turns one away; reaching the registry with one is a bug."""
    with pytest.raises(KeyError, match="http"):
        build_source(_sky_over_http(url="rtsp://sky.local/stream1"))


def test_a_usb_and_a_network_camera_live_in_one_registry():
    """One proxy, one id space — whatever the camera is plugged into."""
    from arcsecond.imagesources.sources.opencv import OpenCVWebcamSource

    registry = Registry(
        cameras=[_netcam(cam_id="abc"), Camera(id="xyz", kind=USB, index=0)]
    )
    assert isinstance(registry._build("abc"), RTSPSource)
    assert isinstance(registry._build("xyz"), OpenCVWebcamSource)


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
