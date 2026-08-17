"""Tests for the OpenCV webcam source (``webcam:``).

The point of most of these is the capture *backend*. Device indices must never
be opened with ``CAP_ANY``: OpenCV then falls through its backend list to
FFMPEG, which tries to enumerate DirectShow devices, floods stderr and cannot
succeed. Detection and ``open()`` must also agree on the backend, or they would
not agree on what device index 1 refers to.
"""

import asyncio
import sys
from unittest.mock import MagicMock, patch

from arcsecond.imagesources.sources.opencv import (
    OpenCVWebcamSource,
    _capture_backend,
    detect_webcams,
)


def _fake_cv2():
    cv2 = MagicMock()
    cv2.CAP_ANY = 0
    cv2.CAP_DSHOW = 700
    cv2.CAP_AVFOUNDATION = 1200
    cv2.CAP_V4L2 = 200
    cv2.CAP_PROP_FRAME_WIDTH = 3
    cv2.CAP_PROP_FRAME_HEIGHT = 4
    cv2.CAP_PROP_FPS = 5
    cv2.IMWRITE_JPEG_QUALITY = 1
    cv2.VideoCapture.return_value.isOpened.return_value = True
    cv2.VideoCapture.return_value.get.return_value = 0
    return cv2


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------


def test_capture_backend_is_dshow_on_windows():
    cv2 = _fake_cv2()
    with patch.dict(sys.modules, {"cv2": cv2}), patch.object(sys, "platform", "win32"):
        assert _capture_backend() == cv2.CAP_DSHOW


def test_capture_backend_is_avfoundation_on_macos():
    cv2 = _fake_cv2()
    with patch.dict(sys.modules, {"cv2": cv2}), patch.object(sys, "platform", "darwin"):
        assert _capture_backend() == cv2.CAP_AVFOUNDATION


def test_capture_backend_is_v4l2_on_linux():
    cv2 = _fake_cv2()
    with patch.dict(sys.modules, {"cv2": cv2}), patch.object(sys, "platform", "linux"):
        assert _capture_backend() == cv2.CAP_V4L2


def test_capture_backend_is_never_cap_any():
    cv2 = _fake_cv2()
    for platform in ("win32", "darwin", "linux", "freebsd14"):
        with (
            patch.dict(sys.modules, {"cv2": cv2}),
            patch.object(sys, "platform", platform),
        ):
            assert _capture_backend() != cv2.CAP_ANY


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def test_detect_webcams_pins_the_backend_on_every_probe():
    cv2 = _fake_cv2()
    with patch.dict(sys.modules, {"cv2": cv2}), patch.object(sys, "platform", "win32"):
        detect_webcams(max_index=3)

    assert cv2.VideoCapture.call_count == 3
    for i, call in enumerate(cv2.VideoCapture.call_args_list):
        assert call.args == (i, cv2.CAP_DSHOW)


def test_detect_webcams_reports_every_open_index():
    cv2 = _fake_cv2()
    with patch.dict(sys.modules, {"cv2": cv2}), patch.object(sys, "platform", "linux"):
        found = detect_webcams(max_index=2)

    assert [i.id for i in found] == ["webcam:0", "webcam:1"]
    assert all(i.kind == "webcam" for i in found)
    assert [i.extra["index"] for i in found] == [0, 1]


def test_detect_webcams_skips_indices_that_do_not_open():
    cv2 = _fake_cv2()
    cv2.VideoCapture.return_value.isOpened.side_effect = [False, True, False]

    with patch.dict(sys.modules, {"cv2": cv2}), patch.object(sys, "platform", "linux"):
        found = detect_webcams(max_index=3)

    assert [i.id for i in found] == ["webcam:1"]
    # Every probe is released, including the ones that never opened.
    assert cv2.VideoCapture.return_value.release.call_count == 3


def test_detect_webcams_finds_nothing_when_no_device_opens():
    cv2 = _fake_cv2()
    cv2.VideoCapture.return_value.isOpened.return_value = False

    with patch.dict(sys.modules, {"cv2": cv2}), patch.object(sys, "platform", "win32"):
        assert detect_webcams(max_index=4) == []


# ---------------------------------------------------------------------------
# Opening a source
# ---------------------------------------------------------------------------


def test_open_uses_the_same_backend_as_detection():
    cv2 = _fake_cv2()
    source = OpenCVWebcamSource(2)

    with patch.dict(sys.modules, {"cv2": cv2}), patch.object(sys, "platform", "win32"):
        asyncio.run(source.open())

    cv2.VideoCapture.assert_called_once_with(2, cv2.CAP_DSHOW)


def test_open_raises_when_the_device_will_not_open():
    cv2 = _fake_cv2()
    cv2.VideoCapture.return_value.isOpened.return_value = False
    source = OpenCVWebcamSource(0)

    with patch.dict(sys.modules, {"cv2": cv2}), patch.object(sys, "platform", "linux"):
        try:
            asyncio.run(source.open())
        except RuntimeError as e:
            assert "device index 0" in str(e)
        else:
            raise AssertionError("expected open() to raise")
