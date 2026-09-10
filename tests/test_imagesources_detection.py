"""Tests for the three-way detection report.

`detect` answers three separate questions and must not blur them: what is here
but unknown, what is known and here, what is known and gone. Each of the three
buckets is asserted on its own, because the old command printed detection and
registration one after the other with no way to tell which was which.
"""

from contextlib import nullcontext
from unittest.mock import patch

import pytest

from arcsecond.imagesources import detection
from arcsecond.imagesources.sources.base import DetectedDevice
from arcsecond.imagesources.store import ALLSKY, NET, USB, WEBCAM_KINDS, Camera


def _usb_device(index, width=1280, height=720, fps=30.0):
    return DetectedDevice(
        kind=USB,
        identity=(USB, index),
        label=f"USB webcam #{index}",
        extra={"index": index, "width": width, "height": height, "fps": fps},
    )


def _report(cameras, kinds=WEBCAM_KINDS, devices=(), **kwargs):
    with patch.object(detection, "_detect_webcams", return_value=list(devices)):
        return detection.report(cameras, kinds, **kwargs)


# ---------------------------------------------------------------------------
# The three buckets
# ---------------------------------------------------------------------------


def test_a_detected_unregistered_webcam_is_new():
    report = _report([], devices=[_usb_device(0)])
    assert [d.identity for d in report.new] == [(USB, 0)]
    assert report.present == []
    assert report.missing == []


def test_a_detected_registered_webcam_is_present():
    camera = Camera(id="abc", kind=USB, index=0)
    report = _report([camera], devices=[_usb_device(0)])
    assert report.new == []
    assert report.present == [camera]
    assert report.missing == []


def test_a_registered_webcam_that_is_not_there_is_missing():
    camera = Camera(id="abc", kind=USB, index=0)
    report = _report([camera], devices=[])
    assert report.new == []
    assert report.present == []
    assert report.missing == [camera]
    assert "not attached" in report.detail["abc"]


def test_the_three_buckets_are_reported_together():
    registered = Camera(id="abc", kind=USB, index=0)
    gone = Camera(id="def", kind=USB, index=9)
    report = _report([registered, gone], devices=[_usb_device(0), _usb_device(1)])
    assert [d.identity for d in report.new] == [(USB, 1)]
    assert report.present == [registered]
    assert report.missing == [gone]


def test_detection_registers_nothing(tmp_path):
    """`detect` probes and reports. Registering is `add`'s job, and only `add`'s."""
    from arcsecond.imagesources import store

    store_file = tmp_path / "s.json"
    _report([], devices=[_usb_device(0)])
    assert store.all_cameras(store_file) == []


def test_a_new_device_reports_its_resolution():
    report = _report([], devices=[_usb_device(0, 1920, 1080, 25.0)])
    assert report.detail[(USB, 0)] == "1920×1080, 25.0 fps"


# ---------------------------------------------------------------------------
# Kinds are kept apart
# ---------------------------------------------------------------------------


def test_webcam_detection_ignores_all_sky_cameras():
    sky = Camera(id="abc", kind=ALLSKY, path="/nowhere.jpg")
    report = _report([sky], kinds=WEBCAM_KINDS, devices=[])
    assert report.is_empty


def test_all_sky_detection_ignores_webcams():
    usb = Camera(id="abc", kind=USB, index=0)
    with patch.object(detection, "detect_allsky", return_value=[]):
        report = detection.report([usb], (ALLSKY,))
    assert report.is_empty


# ---------------------------------------------------------------------------
# Network cameras: never new, but confirmed or reported missing
# ---------------------------------------------------------------------------


def test_a_reachable_network_camera_is_present():
    camera = Camera(id="abc", kind=NET, url="rtsp://cam.local/s")
    with patch.object(detection, "is_reachable", return_value=(True, "answering")):
        report = _report([camera])
    assert report.present == [camera]
    assert report.new == []


def test_an_unreachable_network_camera_is_missing_with_a_reason():
    camera = Camera(id="abc", kind=NET, url="rtsp://cam.local/s")
    with patch.object(detection, "is_reachable", return_value=(False, "no answer")):
        report = _report([camera])
    assert report.missing == [camera]
    assert report.detail["abc"] == "no answer"


def test_no_network_says_so_rather_than_guessing():
    camera = Camera(id="abc", kind=NET, url="rtsp://cam.local/s")
    with patch.object(detection, "is_reachable", side_effect=AssertionError("called")):
        report = _report([camera], check_network=False)
    assert report.present == [camera]
    assert report.detail["abc"] == "not contacted"


def test_reachability_never_leaks_the_password():
    url = "rtsp://admin:hunter2@127.0.0.1:1/s"
    reachable, why = detection.is_reachable(url, timeout=0.2)
    assert reachable is False
    assert "hunter2" not in why


def _unresolvable(monkeypatch, answering=()):
    """Make the machine's resolver fail, except for addresses in ``answering``."""
    import socket as socket_module

    def connect(endpoint, timeout=None):
        host, _ = endpoint
        if host in answering:
            return nullcontext()
        raise socket_module.gaierror(-2, "Name or service not known")

    monkeypatch.setattr(detection.socket, "create_connection", connect)


def test_a_name_that_does_not_resolve_says_so(monkeypatch):
    """Distinct from a refused connection: the camera may be perfectly fine."""
    _unresolvable(monkeypatch)
    monkeypatch.setattr(detection, "resolve_over_mdns", lambda host, **k: [])

    reachable, why = detection.is_reachable("http://skykot.local/image.jpg")
    assert reachable is False
    assert why == "skykot.local cannot be resolved"


def test_a_local_name_the_machine_cannot_resolve_is_asked_of_the_network(monkeypatch):
    """What the proxy does when it connects, so `detect` must agree with it."""
    _unresolvable(monkeypatch, answering={"192.168.1.42"})
    monkeypatch.setattr(
        detection, "resolve_over_mdns", lambda host, **k: ["192.168.1.42"]
    )

    reachable, why = detection.is_reachable("http://skykot.local/image.jpg")
    assert reachable is True
    assert why == "answering on 192.168.1.42:80, found over mDNS"


def test_an_address_that_does_not_answer_is_not_the_last_word(monkeypatch):
    """The first address a multi-homed machine gives may be one this network
    cannot reach; the others are still worth trying."""
    _unresolvable(monkeypatch, answering={"192.168.1.97"})
    monkeypatch.setattr(
        detection,
        "resolve_over_mdns",
        lambda host, **k: ["192.168.64.1", "192.168.1.97"],
    )

    reachable, why = detection.is_reachable("http://skykot.local/image.jpg")
    assert reachable is True
    assert "192.168.1.97" in why


def test_a_video_stream_is_not_asked_of_the_network(monkeypatch):
    """FFmpeg opens an RTSP stream with its own resolver, out of our reach —
    so promising it works would be a promise we cannot keep."""
    _unresolvable(monkeypatch, answering={"192.168.1.42"})

    def never(*a, **k):
        raise AssertionError("asked over mDNS")

    monkeypatch.setattr(detection, "resolve_over_mdns", never)

    reachable, why = detection.is_reachable("rtsp://cam.local/stream1")
    assert reachable is False
    assert why == "cam.local cannot be resolved"


def test_an_address_that_cannot_be_read_is_not_contacted():
    reachable, why = detection.is_reachable("http://")
    assert reachable is False
    assert why == "the address cannot be read"


@pytest.mark.parametrize(
    "url,expected",
    [
        ("rtsp://cam.local/s", ("cam.local", 554)),
        ("rtsps://cam.local/s", ("cam.local", 322)),
        ("http://cam.local/snap.jpg", ("cam.local", 80)),
        ("https://cam.local/snap.jpg", ("cam.local", 443)),
        ("rtsp://cam.local:8554/s", ("cam.local", 8554)),
    ],
)
def test_the_port_to_check_is_taken_from_the_url(url, expected):
    assert detection._network_endpoint(url) == expected


# ---------------------------------------------------------------------------
# All-sky cameras
# ---------------------------------------------------------------------------


def test_an_all_sky_camera_at_its_own_path_is_present_not_missing(tmp_path):
    """A camera writing somewhere unusual is not missing — only unusual."""
    image = tmp_path / "latest.jpg"
    image.write_bytes(b"x")
    camera = Camera(id="abc", kind=ALLSKY, path=str(image))
    with patch.object(detection, "detect_allsky", return_value=[]):
        report = detection.report([camera], (ALLSKY,))
    assert report.present == [camera]


def test_an_all_sky_camera_with_no_image_is_missing(tmp_path):
    camera = Camera(id="abc", kind=ALLSKY, path=str(tmp_path / "nope.jpg"))
    with patch.object(detection, "detect_allsky", return_value=[]):
        report = detection.report([camera], (ALLSKY,))
    assert report.missing == [camera]
    assert report.detail["abc"] == "no image at that path"


def test_a_glob_reports_which_file_matched(tmp_path):
    (tmp_path / "a.jpg").write_bytes(b"x")
    camera = Camera(id="abc", kind=ALLSKY, path=str(tmp_path / "*.jpg"))
    with patch.object(detection, "detect_allsky", return_value=[]):
        report = detection.report([camera], (ALLSKY,))
    assert report.present == [camera]
    assert report.detail["abc"].endswith("a.jpg")


def test_a_detected_all_sky_camera_that_is_registered_is_not_reported_twice(tmp_path):
    image = tmp_path / "latest.jpg"
    image.write_bytes(b"x")
    camera = Camera(id="abc", kind=ALLSKY, path=str(image))
    device = DetectedDevice(
        kind=ALLSKY,
        identity=(ALLSKY, str(image)),
        label="All-sky",
        extra={"path": str(image)},
    )
    with patch.object(detection, "detect_allsky", return_value=[device]):
        report = detection.report([camera], (ALLSKY,))
    assert report.present == [camera]
    assert report.new == []
    assert report.missing == []


def test_an_all_sky_camera_at_an_address_is_confirmed_by_contacting_it():
    """It has no path to look at, so it is settled the way any address is."""
    camera = Camera(id="abc", kind=ALLSKY, url="http://sky.local/latest.jpg")
    with patch.object(detection, "is_reachable", return_value=(True, "answering")):
        with patch.object(detection, "detect_allsky", return_value=[]):
            report = detection.report([camera], (ALLSKY,))
    assert report.present == [camera]
    assert report.new == []


def test_an_all_sky_camera_at_an_address_that_is_down_is_missing():
    camera = Camera(id="abc", kind=ALLSKY, url="http://sky.local/latest.jpg")
    with patch.object(detection, "is_reachable", return_value=(False, "no answer")):
        with patch.object(detection, "detect_allsky", return_value=[]):
            report = detection.report([camera], (ALLSKY,))
    assert report.missing == [camera]
    assert report.detail["abc"] == "no answer"


def test_an_all_sky_address_is_never_looked_for_on_this_disk():
    """The old check called a URL a missing file — the wrong answer entirely."""
    camera = Camera(id="abc", kind=ALLSKY, url="http://sky.local/latest.jpg")
    with patch.object(detection, "resolve_allsky_path") as looked_at_disk:
        with patch.object(detection, "is_reachable", return_value=(True, "answering")):
            with patch.object(detection, "detect_allsky", return_value=[]):
                detection.report([camera], (ALLSKY,))
    looked_at_disk.assert_not_called()


# ---------------------------------------------------------------------------
# Probing the well-known locations
# ---------------------------------------------------------------------------


def test_an_image_at_a_well_known_location_is_detected(tmp_path, monkeypatch):
    from arcsecond.imagesources.sources import filewatch

    image = tmp_path / "image.jpg"
    image.write_bytes(b"x")
    monkeypatch.setattr(filewatch, "ALLSKY_DISCOVERY_PATHS", [image])

    (device,) = filewatch.detect_allsky()
    assert device.identity == (ALLSKY, str(image))
    assert device.extra["path"] == str(image)


def test_a_well_known_location_with_nothing_at_it_is_not_reported(
    tmp_path, monkeypatch
):
    """Probing reports what is there — an empty list is an answer, not a fault."""
    from arcsecond.imagesources.sources import filewatch

    monkeypatch.setattr(
        filewatch, "ALLSKY_DISCOVERY_PATHS", [tmp_path / "nothing-here.jpg"]
    )
    assert filewatch.detect_allsky() == []


# ---------------------------------------------------------------------------
# Probing must never take the report down
# ---------------------------------------------------------------------------


def test_a_probe_that_explodes_does_not_lose_the_registered_cameras():
    camera = Camera(id="abc", kind=USB, index=0)
    with patch.object(detection, "_detect_webcams", side_effect=OSError("no cv2")):
        report = detection.report([camera], WEBCAM_KINDS, check_network=False)
    assert report.missing == [camera]
