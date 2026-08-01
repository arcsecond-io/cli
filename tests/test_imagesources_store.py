"""Tests for remembered cameras, runtime registration, and the loopback guard.

Every test passes an explicit store path — none of them may touch the real
~/.config/arcsecond directory.
"""

import asyncio
import json

import click
import pytest

from arcsecond.imagesources import store
from arcsecond.imagesources.commands import _expand_env_vars, _parse_netcam_overrides
from arcsecond.imagesources.registry import AllskyOverride, NetcamOverride, Registry

RAW_URL = "rtsp://admin:${DOME_CAM_PW}@192.168.1.42:554/stream1"
EXPANDED_URL = "rtsp://admin:hunter2@192.168.1.42:554/stream1"


@pytest.fixture
def store_file(tmp_path):
    return tmp_path / "live-image-sources.json"


# ---------------------------------------------------------------------------
# Reading and writing
# ---------------------------------------------------------------------------


def test_load_returns_empty_kinds_when_nothing_was_ever_registered(store_file):
    assert store.load(store_file) == {"allsky": {}, "netcam": {}}


def test_allsky_registration_round_trips(store_file):
    store.remember_allsky([AllskyOverride(id="roof", path="/srv/sky.jpg")], store_file)
    (restored,) = store.remembered_allsky(store_file)
    assert restored.id == "roof"
    assert restored.path == "/srv/sky.jpg"


def test_registering_the_same_id_replaces_it(store_file):
    store.remember_allsky([AllskyOverride(id="roof", path="/old.jpg")], store_file)
    store.remember_allsky([AllskyOverride(id="roof", path="/new.jpg")], store_file)
    restored = store.remembered_allsky(store_file)
    assert len(restored) == 1
    assert restored[0].path == "/new.jpg"


def test_a_percent_in_a_url_survives_the_round_trip(store_file):
    """ConfigParser would have eaten this — hence JSON."""
    url = "http://cam.local/snap.jpg?token=a%2Fb%25c"
    store.remember_netcams([NetcamOverride(id="dome", url=url)], store_file)
    (restored,) = store.remembered_netcams(lambda u: u, store_file)
    assert restored.url == url


def test_forget_removes_one_registration(store_file):
    store.remember_allsky(
        [
            AllskyOverride(id="roof", path="/a.jpg"),
            AllskyOverride(id="dome", path="/b.jpg"),
        ],
        store_file,
    )
    assert store.forget("allsky", "roof", store_file) is True
    assert [o.id for o in store.remembered_allsky(store_file)] == ["dome"]


def test_forget_is_a_no_op_for_an_unknown_id(store_file):
    assert store.forget("allsky", "nope", store_file) is False


def test_forget_rejects_an_unknown_kind(store_file):
    with pytest.raises(ValueError):
        store.forget("telescope", "roof", store_file)


def test_a_corrupt_file_is_reported_not_swallowed(store_file):
    store_file.write_text("{not json", encoding="utf-8")
    with pytest.raises(store.SourceStoreError, match=str(store_file.name)):
        store.load(store_file)


def test_a_json_file_that_is_not_an_object_is_reported(store_file):
    store_file.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(store.SourceStoreError):
        store.load(store_file)


# ---------------------------------------------------------------------------
# Passwords must never reach the file
# ---------------------------------------------------------------------------


def test_the_stored_url_keeps_the_variable_and_not_the_password(
    store_file, monkeypatch
):
    monkeypatch.setenv("DOME_CAM_PW", "hunter2")
    (override,) = _parse_netcam_overrides((f"dome={RAW_URL}",))

    # What the proxy uses is expanded...
    assert override.url == EXPANDED_URL
    # ...but what reaches the disk is not.
    store.remember_netcams([override], store_file)

    on_disk = store_file.read_text(encoding="utf-8")
    assert "hunter2" not in on_disk
    assert "${DOME_CAM_PW}" in on_disk


def test_a_remembered_camera_is_expanded_again_on_the_way_back(store_file, monkeypatch):
    monkeypatch.setenv("DOME_CAM_PW", "hunter2")
    (override,) = _parse_netcam_overrides((f"dome={RAW_URL}",))
    store.remember_netcams([override], store_file)

    (restored,) = store.remembered_netcams(_expand_env_vars, store_file)
    assert restored.url == EXPANDED_URL
    assert restored.raw_url == RAW_URL


def test_a_camera_whose_variable_is_unset_is_skipped_not_fatal(store_file, monkeypatch):
    monkeypatch.setenv("DOME_CAM_PW", "hunter2")
    (dome,) = _parse_netcam_overrides((f"dome={RAW_URL}",))
    (garden,) = _parse_netcam_overrides(("garden=http://cam.local/s.jpg",))
    store.remember_netcams([dome, garden], store_file)

    # The proxy restarts in a shell that never had the password.
    monkeypatch.delenv("DOME_CAM_PW", raising=False)
    restored = store.remembered_netcams(_expand_env_vars, store_file)

    assert [o.id for o in restored] == ["garden"]


def test_skipping_a_camera_names_the_missing_variable(store_file, monkeypatch, caplog):
    monkeypatch.setenv("DOME_CAM_PW", "hunter2")
    (dome,) = _parse_netcam_overrides((f"dome={RAW_URL}",))
    store.remember_netcams([dome], store_file)
    monkeypatch.delenv("DOME_CAM_PW", raising=False)

    with caplog.at_level("WARNING"):
        store.remembered_netcams(_expand_env_vars, store_file)

    assert "DOME_CAM_PW" in caplog.text


def test_expand_env_vars_is_what_reports_the_missing_variable(monkeypatch):
    monkeypatch.delenv("DOME_CAM_PW", raising=False)
    with pytest.raises(click.BadParameter, match="DOME_CAM_PW"):
        _expand_env_vars(RAW_URL)


# ---------------------------------------------------------------------------
# Registering into a running proxy
# ---------------------------------------------------------------------------


def test_registry_adds_cameras_at_runtime():
    registry = Registry()
    added = registry.add_sources(
        allsky=[AllskyOverride(id="roof", path="/a.jpg")],
        netcam=[NetcamOverride(id="dome", url="rtsp://cam.local/s")],
    )
    assert sorted(added) == ["allsky:roof", "netcam:dome"]
    # Streamable straight away, with no restart.
    assert registry._build("netcam:dome").url == "rtsp://cam.local/s"
    assert registry._build("allsky:roof").path == "/a.jpg"


def test_adding_an_existing_id_replaces_it():
    registry = Registry(
        netcam_overrides=[NetcamOverride(id="dome", url="rtsp://old/s")]
    )
    registry.add_sources(netcam=[NetcamOverride(id="dome", url="rtsp://new/s")])
    assert len(registry.netcam_overrides) == 1
    assert registry._build("netcam:dome").url == "rtsp://new/s"


def test_removing_a_camera_makes_it_unacquirable():
    registry = Registry(netcam_overrides=[NetcamOverride(id="dome", url="rtsp://c/s")])
    assert registry.remove_source("netcam", "dome") is True
    with pytest.raises(KeyError):
        registry._build("netcam:dome")


def test_removing_an_unregistered_camera_reports_false():
    assert Registry().remove_source("netcam", "nope") is False


def test_removing_an_unknown_kind_raises():
    with pytest.raises(ValueError):
        Registry().remove_source("telescope", "dome")


# ---------------------------------------------------------------------------
# The loopback guard on /sources
# ---------------------------------------------------------------------------


def _proxy_app():
    from aiohttp import web

    from arcsecond.imagesources import proxy as proxy_mod

    app = web.Application()
    app["registry"] = Registry()
    app.router.add_post("/sources", proxy_mod.handle_add_sources)
    app.router.add_delete("/sources/{id}", proxy_mod.handle_remove_source)
    return app


def _run_against_proxy(body):
    from aiohttp import web

    async def _main():
        app = _proxy_app()
        runner = web.AppRunner(app)
        await runner.setup()
        await web.TCPSite(runner, "127.0.0.1", 0).start()
        port = runner.addresses[0][1]
        try:
            return await body(f"http://127.0.0.1:{port}", app["registry"])
        finally:
            await runner.cleanup()

    return asyncio.run(_main())


def test_a_loopback_caller_may_register():
    import aiohttp

    async def body(base, registry):
        async with aiohttp.ClientSession() as s:
            async with s.post(
                f"{base}/sources",
                json={"netcam": [{"id": "dome", "url": "rtsp://cam.local/s"}]},
            ) as r:
                return r.status, await r.json(), len(registry.netcam_overrides)

    status, payload, count = _run_against_proxy(body)
    assert status == 200
    assert payload["added"] == ["netcam:dome"]
    assert count == 1


def test_a_forged_forwarded_header_does_not_grant_access(monkeypatch):
    """The guard must read the socket peer, never a header the caller controls."""
    from arcsecond.imagesources.proxy import _is_loopback

    class FakeRequest:
        remote = "203.0.113.9"
        headers = {"X-Forwarded-For": "127.0.0.1", "X-Real-IP": "127.0.0.1"}

    assert _is_loopback(FakeRequest()) is False


@pytest.mark.parametrize("remote", ["127.0.0.1", "::1"])
def test_loopback_addresses_are_recognised(remote):
    from arcsecond.imagesources.proxy import _is_loopback

    class FakeRequest:
        headers = {}

    request = FakeRequest()
    request.remote = remote
    assert _is_loopback(request) is True


@pytest.mark.parametrize("remote", ["203.0.113.9", "10.0.0.4", None, "not-an-ip"])
def test_non_loopback_addresses_are_refused(remote):
    from arcsecond.imagesources.proxy import _is_loopback

    class FakeRequest:
        headers = {}

    request = FakeRequest()
    request.remote = remote
    assert _is_loopback(request) is False


def test_a_malformed_registration_is_rejected():
    import aiohttp

    async def body(base, registry):
        async with aiohttp.ClientSession() as s:
            async with s.post(
                f"{base}/sources", json={"netcam": [{"id": "dome"}]}
            ) as r:
                return r.status, len(registry.netcam_overrides)

    status, count = _run_against_proxy(body)
    assert status == 400
    assert count == 0


def test_a_camera_can_be_removed_over_the_endpoint():
    import aiohttp

    async def body(base, registry):
        async with aiohttp.ClientSession() as s:
            await s.post(
                f"{base}/sources",
                json={"netcam": [{"id": "dome", "url": "rtsp://cam.local/s"}]},
            )
            async with s.delete(f"{base}/sources/netcam:dome") as r:
                return r.status, await r.json(), len(registry.netcam_overrides)

    status, payload, count = _run_against_proxy(body)
    assert status == 200
    assert payload["removed"] is True
    assert count == 0


def test_removing_with_a_bare_id_is_rejected():
    import aiohttp

    async def body(base, registry):
        async with aiohttp.ClientSession() as s:
            async with s.delete(f"{base}/sources/dome") as r:
                return r.status

    assert _run_against_proxy(body) == 400


def test_the_store_file_is_written_as_readable_json(store_file):
    store.remember_allsky([AllskyOverride(id="roof", path="/a.jpg")], store_file)
    assert json.loads(store_file.read_text())["allsky"]["roof"]["path"] == "/a.jpg"
