"""Tests for the camera store: ids, registering, forgetting, and migration.

Every test passes an explicit store path — none of them may touch the real
~/.config/arcsecond directory.
"""

import json

import pytest

from arcsecond.imagesources import store
from arcsecond.imagesources.store import ALLSKY, NET, USB, Camera

RAW_URL = "rtsp://admin:${DOME_CAM_PW}@192.168.1.42:554/stream1"
EXPANDED_URL = "rtsp://admin:hunter2@192.168.1.42:554/stream1"

# An all-sky camera whose software runs on another machine and publishes the
# image over HTTP. Registered as an all-sky camera, not as a webcam.
RAW_SKY_URL = "http://sky:${SKY_PW}@10.0.0.9/allsky/latest.jpg"
EXPANDED_SKY_URL = "http://sky:hunter2@10.0.0.9/allsky/latest.jpg"


@pytest.fixture
def store_file(tmp_path):
    return tmp_path / "live-image-sources.json"


def _usb(index=0, label=None):
    return Camera(id="", kind=USB, index=index, label=label)


def _net(url=RAW_URL, label=None):
    return Camera(id="", kind=NET, url=url, label=label)


def _allsky(path="/srv/sky.jpg", label=None):
    return Camera(id="", kind=ALLSKY, path=path, label=label)


def _allsky_url(url=RAW_SKY_URL, label=None):
    return Camera(id="", kind=ALLSKY, url=url, label=label)


# ---------------------------------------------------------------------------
# Identifiers
# ---------------------------------------------------------------------------


def test_an_id_is_three_characters_from_an_unambiguous_alphabet(store_file):
    camera, _ = store.add(_usb(0), store_file)
    assert len(camera.id) == store.ID_LENGTH
    assert set(camera.id) <= set(store.ID_ALPHABET)
    # The characters that get misread off a screen are not in the alphabet.
    assert not (set(camera.id) & set("01ilo"))


def test_the_same_camera_always_derives_the_same_id(tmp_path):
    """Two machines, two stores, one camera — the id must not be positional."""
    first, _ = store.add(_net(), tmp_path / "a.json")
    second, _ = store.add(_net(), tmp_path / "b.json")
    assert first.id == second.id


def test_ids_do_not_shift_when_an_earlier_camera_is_forgotten(store_file):
    """The failing of device indices: dropping the first must not renumber."""
    a, _ = store.add(_usb(0), store_file)
    b, _ = store.add(_usb(1), store_file)
    c, _ = store.add(_usb(2), store_file)
    store.forget(a.id, store_file)
    assert {cam.id for cam in store.all_cameras(store_file)} == {b.id, c.id}
    assert store.find(b.id, store_file).index == 1
    assert store.find(c.id, store_file).index == 2


def test_two_cameras_deriving_the_same_id_do_not_collide(store_file, monkeypatch):
    """A collision must give the second camera its own id, not overwrite the first."""
    calls = []

    def one_id_then_another(identity, taken):
        calls.append(identity)
        return "aaa" if "aaa" not in taken else "bbb"

    monkeypatch.setattr(store, "_derive_id", one_id_then_another)
    first, _ = store.add(_usb(0), store_file)
    second, _ = store.add(_usb(1), store_file)
    assert (first.id, second.id) == ("aaa", "bbb")
    assert len(store.all_cameras(store_file)) == 2


# ---------------------------------------------------------------------------
# Registering
# ---------------------------------------------------------------------------


def test_load_returns_nothing_when_nothing_was_ever_registered(store_file):
    assert store.all_cameras(store_file) == []


@pytest.mark.parametrize("camera", [_usb(2), _net(), _allsky(), _allsky_url()])
def test_every_kind_of_camera_round_trips(store_file, camera):
    stored, created = store.add(camera, store_file)
    assert created is True
    (restored,) = store.all_cameras(store_file)
    assert restored == stored


def test_registering_the_same_camera_twice_is_a_no_op(store_file):
    first, created_first = store.add(_usb(0), store_file)
    second, created_second = store.add(_usb(0), store_file)
    assert (created_first, created_second) == (True, False)
    assert first.id == second.id
    assert len(store.all_cameras(store_file)) == 1


def test_registering_again_with_a_label_applies_it(store_file):
    store.add(_usb(0), store_file)
    stored, created = store.add(_usb(0, label="Guide cam"), store_file)
    assert created is False
    assert stored.label == "Guide cam"
    assert store.find(stored.id, store_file).label == "Guide cam"


def test_a_percent_in_a_url_survives_the_round_trip(store_file):
    """ConfigParser would have eaten this — hence JSON."""
    url = "http://cam.local/snap.jpg?token=a%2Fb%25c"
    stored, _ = store.add(_net(url), store_file)
    assert store.find(stored.id, store_file).url == url


def test_the_stored_url_keeps_the_variable_and_not_the_password(store_file):
    store.add(_net(RAW_URL), store_file)
    written = store_file.read_text()
    assert "${DOME_CAM_PW}" in written
    assert "hunter2" not in written


# ---------------------------------------------------------------------------
# Finding and forgetting
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("camera", [_usb(0), _net(), _allsky()])
def test_forget_works_for_every_kind_of_camera(store_file, camera):
    """The whole point: a USB webcam was impossible to forget before."""
    stored, _ = store.add(camera, store_file)
    assert store.forget(stored.id, store_file) == stored
    assert store.all_cameras(store_file) == []


def test_forget_takes_the_id_that_was_printed(store_file):
    """The id shown and the id accepted must be the same string."""
    stored, _ = store.add(_net(), store_file)
    assert store.forget(stored.id, store_file) is not None


def test_forget_is_a_no_op_for_an_unknown_id(store_file):
    store.add(_usb(0), store_file)
    assert store.forget("zzz", store_file) is None
    assert len(store.all_cameras(store_file)) == 1


def test_forgetting_one_camera_leaves_the_others(store_file):
    a, _ = store.add(_usb(0), store_file)
    b, _ = store.add(_allsky(), store_file)
    store.forget(a.id, store_file)
    assert [c.id for c in store.all_cameras(store_file)] == [b.id]


def test_an_id_is_found_whatever_its_case(store_file):
    stored, _ = store.add(_usb(0), store_file)
    assert store.find(stored.id.upper(), store_file) == stored


@pytest.mark.parametrize("prefix", ["usb", "webcam", "netcam", "allsky"])
def test_a_prefixed_id_is_tolerated(store_file, prefix):
    """Older screens and scripts printed `netcam:dome`; that must still resolve."""
    stored, _ = store.add(_usb(0), store_file)
    assert store.find(f"{prefix}:{stored.id}", store_file) == stored


def test_an_all_sky_camera_registered_by_address_is_still_an_all_sky_camera(
    store_file,
):
    """The transport says how it is fetched, not what kind of camera it is."""
    stored, _ = store.add(_allsky_url("http://sky.local/latest.jpg"), store_file)
    assert stored.kind == ALLSKY
    assert stored.display_kind == "all-sky"
    assert [c.id for c in store.cameras_of_kinds((ALLSKY,), store_file)] == [stored.id]
    assert store.cameras_of_kinds(store.WEBCAM_KINDS, store_file) == []


def test_one_address_registered_as_both_kinds_is_two_cameras(store_file):
    """Asking for an all-sky camera is not the same as asking for a webcam."""
    url = "http://sky.local/latest.jpg"
    sky, _ = store.add(_allsky_url(url), store_file)
    cam, created = store.add(_net(url), store_file)
    assert created is True
    assert sky.id != cam.id


def test_an_all_sky_address_is_stored_as_an_address_not_a_path(store_file):
    stored, _ = store.add(_allsky_url("http://sky.local/latest.jpg"), store_file)
    entry = json.loads(store_file.read_text())["cameras"][stored.id]
    assert entry == {"kind": "allsky", "url": "http://sky.local/latest.jpg"}


def test_an_all_sky_address_never_shows_its_password(store_file):
    stored, _ = store.add(_allsky_url(EXPANDED_SKY_URL), store_file)
    assert "hunter2" not in stored.target
    assert "***" in stored.target


def test_cameras_of_kinds_keeps_the_two_groups_apart(store_file):
    usb, _ = store.add(_usb(0), store_file)
    net, _ = store.add(_net(), store_file)
    sky, _ = store.add(_allsky(), store_file)

    webcams = store.cameras_of_kinds(store.WEBCAM_KINDS, store_file)
    assert {c.id for c in webcams} == {usb.id, net.id}
    assert [c.id for c in store.cameras_of_kinds((ALLSKY,), store_file)] == [sky.id]


# ---------------------------------------------------------------------------
# Environment variables in camera URLs
# ---------------------------------------------------------------------------


def test_a_registered_camera_is_expanded_again_on_the_way_back(store_file):
    stored, _ = store.add(_net(RAW_URL), store_file)
    (usable,) = store.expanded([stored], lambda u: EXPANDED_URL)
    assert usable.url == EXPANDED_URL
    assert usable.id == stored.id


def test_an_all_sky_address_is_expanded_like_any_other(store_file):
    """A password in an all-sky address is kept out of the file the same way."""
    stored, _ = store.add(_allsky_url(RAW_SKY_URL), store_file)
    assert "${SKY_PW}" in store_file.read_text()

    (usable,) = store.expanded([stored], lambda u: EXPANDED_SKY_URL)
    assert usable.url == EXPANDED_SKY_URL
    assert usable.kind == ALLSKY


def test_a_camera_whose_variable_is_unset_is_skipped_not_fatal(store_file):
    def explode(url):
        raise KeyError("DOME_CAM_PW")

    net, _ = store.add(_net(RAW_URL), store_file)
    usb, _ = store.add(_usb(0), store_file)

    usable = store.expanded(store.all_cameras(store_file), explode)
    assert [c.id for c in usable] == [usb.id]


def test_skipping_a_camera_names_it(store_file, caplog):
    def explode(url):
        raise KeyError("DOME_CAM_PW")

    stored, _ = store.add(_net(RAW_URL), store_file)
    with caplog.at_level("WARNING"):
        store.expanded([stored], explode)
    assert stored.id in caplog.text


# ---------------------------------------------------------------------------
# Reading a damaged or older file
# ---------------------------------------------------------------------------


def test_a_corrupt_file_is_reported_not_swallowed(store_file):
    store_file.write_text("{not json")
    with pytest.raises(store.SourceStoreError):
        store.load(store_file)


def test_a_json_file_that_is_not_an_object_is_reported(store_file):
    store_file.write_text("[1, 2, 3]")
    with pytest.raises(store.SourceStoreError):
        store.load(store_file)


def test_an_entry_missing_its_details_is_skipped_not_fatal(store_file):
    store_file.write_text(
        json.dumps(
            {
                "version": 2,
                "cameras": {
                    "aaa": {"kind": "net"},  # no url
                    "bbb": {"kind": "usb", "index": 0},
                },
            }
        )
    )
    assert [c.id for c in store.all_cameras(store_file)] == ["bbb"]


def test_the_store_file_is_written_as_readable_json(store_file):
    stored, _ = store.add(_allsky("/a.jpg"), store_file)
    written = json.loads(store_file.read_text())
    assert written["version"] == 2
    assert written["cameras"][stored.id]["path"] == "/a.jpg"


# ---------------------------------------------------------------------------
# Migration from the layout that grouped cameras by kind
# ---------------------------------------------------------------------------


V1 = {
    "allsky": {"roof": {"path": "/srv/allsky/latest.jpg"}},
    "netcam": {"dome": {"url": RAW_URL}},
}


def test_cameras_registered_with_the_old_cli_are_not_lost(store_file):
    store_file.write_text(json.dumps(V1))
    cameras = store.all_cameras(store_file)
    assert {c.kind for c in cameras} == {NET, ALLSKY}
    assert {c.target for c in cameras} == {
        "rtsp://admin:***@192.168.1.42:554/stream1",
        "/srv/allsky/latest.jpg",
    }


def test_the_name_invented_under_the_old_cli_is_kept_as_a_label(store_file):
    store_file.write_text(json.dumps(V1))
    assert {c.label for c in store.all_cameras(store_file)} == {"roof", "dome"}


def test_a_migrated_camera_can_be_forgotten(store_file):
    """Under the old layout this was the failing case."""
    store_file.write_text(json.dumps(V1))
    for camera in store.all_cameras(store_file):
        assert store.forget(camera.id, store_file) is not None
    assert store.all_cameras(store_file) == []


def test_migration_is_written_back_so_ids_stay_put(store_file):
    store_file.write_text(json.dumps(V1))
    before = [c.id for c in store.all_cameras(store_file)]
    assert json.loads(store_file.read_text())["version"] == 2
    assert [c.id for c in store.all_cameras(store_file)] == before


def test_migration_does_not_expand_the_password(store_file):
    store_file.write_text(json.dumps(V1))
    store.all_cameras(store_file)
    assert "${DOME_CAM_PW}" in store_file.read_text()


# ---------------------------------------------------------------------------
# What probing learned about a USB camera
#
# Resolution and frame rate can only be measured by opening the device, and
# `/detect` must stay answerable while a camera is busy or unplugged. So they
# are measured once, at registration, and read back from the store afterwards.
# ---------------------------------------------------------------------------


SPECS = {"width": 1280, "height": 720, "fps": 30.0}


def test_a_usb_camera_remembers_what_probing_measured(store_file):
    stored, _ = store.add(Camera(id="", kind=USB, index=0, specs=SPECS), store_file)
    assert store.find(stored.id, store_file).specs == SPECS


def test_specs_survive_the_round_trip_to_disk(store_file):
    store.add(Camera(id="", kind=USB, index=0, specs=SPECS), store_file)
    written = json.loads(store_file.read_text())
    assert written["cameras"][store.all_cameras(store_file)[0].id]["specs"] == SPECS


def test_a_camera_registered_while_unplugged_simply_has_none(store_file):
    stored, _ = store.add(_usb(0), store_file)
    assert store.find(stored.id, store_file).specs is None


def test_re_registering_records_specs_measured_the_second_time(store_file):
    """Plugging the camera in and re-running `add` is how they get filled in."""
    first, _ = store.add(_usb(0), store_file)
    second, created = store.add(
        Camera(id="", kind=USB, index=0, specs=SPECS), store_file
    )
    assert created is False
    assert second.id == first.id
    assert store.find(first.id, store_file).specs == SPECS


def test_re_registering_without_specs_does_not_wipe_the_recorded_ones(store_file):
    """A re-run on a machine without OpenCV must not lose what was measured."""
    stored, _ = store.add(Camera(id="", kind=USB, index=0, specs=SPECS), store_file)
    store.add(_usb(0), store_file)
    assert store.find(stored.id, store_file).specs == SPECS


def test_specs_are_not_part_of_what_identifies_a_camera(store_file):
    """A camera switched to another mode is the same camera, not a new one."""
    first, _ = store.add(Camera(id="", kind=USB, index=0, specs=SPECS), store_file)
    other = dict(SPECS, width=640, height=480)
    second, created = store.add(
        Camera(id="", kind=USB, index=0, specs=other), store_file
    )
    assert (created, second.id) == (False, first.id)
    assert len(store.all_cameras(store_file)) == 1
    assert store.find(first.id, store_file).specs == other


def test_a_malformed_specs_entry_is_ignored_rather_than_fatal(store_file):
    store_file.write_text(
        json.dumps(
            {
                "version": 2,
                "cameras": {"aaa": {"kind": "usb", "index": 0, "specs": "1280x720"}},
            }
        )
    )
    (camera,) = store.all_cameras(store_file)
    assert camera.specs is None
