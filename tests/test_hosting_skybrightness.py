from pathlib import Path

import httpx
import pytest

from arcsecond.hosting import skybrightness


@pytest.fixture
def env(tmp_path):
    shared = tmp_path / "shared"
    shared.mkdir()
    path = tmp_path / ".env"
    path.write_text(f'SHARED_DATA_PATH="{shared}"\n', encoding="utf-8")
    return path, shared


def _fake_download(monkeypatch, calls):
    def download(target, url=skybrightness.MAP_URL):
        calls.append(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"map")

    monkeypatch.setattr(skybrightness, "download", download)


def test_yes_downloads_under_the_shared_folder_and_records_the_backend_path(
    env, monkeypatch, capsys
):
    path, shared = env
    calls = []
    _fake_download(monkeypatch, calls)

    skybrightness.offer(path, flag=True)

    assert calls == [shared / "skybrightness" / "skyglow_2024.tif"]
    assert (
        "SKY_BRIGHTNESS_GEOTIFF_PATH=/data/skybrightness/skyglow_2024.tif"
        in path.read_text()
    )
    assert "No outside lookup" in capsys.readouterr().out


def test_no_is_recorded_as_an_empty_path_and_downloads_nothing(env, monkeypatch):
    path, _ = env
    calls = []
    _fake_download(monkeypatch, calls)

    skybrightness.offer(path, flag=False)

    assert calls == []
    assert "SKY_BRIGHTNESS_GEOTIFF_PATH=\n" in path.read_text()


def test_an_answer_already_given_is_not_asked_again(env, monkeypatch):
    path, _ = env
    path.write_text(path.read_text() + "SKY_BRIGHTNESS_GEOTIFF_PATH=\n")
    monkeypatch.setattr(
        skybrightness.click, "confirm", lambda *a, **k: pytest.fail("asked again")
    )

    skybrightness.offer(path, interactive=True)


def test_a_flag_overrules_the_recorded_answer(env, monkeypatch):
    path, _ = env
    path.write_text(path.read_text() + "SKY_BRIGHTNESS_GEOTIFF_PATH=\n")
    calls = []
    _fake_download(monkeypatch, calls)

    skybrightness.offer(path, flag=True)

    assert len(calls) == 1
    assert "SKY_BRIGHTNESS_GEOTIFF_PATH=/data/" in path.read_text()


def test_without_a_terminal_nothing_is_decided(env, monkeypatch, capsys):
    path, _ = env
    calls = []
    _fake_download(monkeypatch, calls)

    skybrightness.offer(path, interactive=False)

    assert calls == []
    assert "SKY_BRIGHTNESS_GEOTIFF_PATH" not in path.read_text()
    assert "--with-sky-map" in capsys.readouterr().out


def test_a_failed_download_records_nothing_so_the_offer_comes_back(
    env, monkeypatch, capsys
):
    path, _ = env

    def download(target, url=skybrightness.MAP_URL):
        raise httpx.ConnectError("no route")

    monkeypatch.setattr(skybrightness, "download", download)

    skybrightness.offer(path, flag=True)

    assert "SKY_BRIGHTNESS_GEOTIFF_PATH" not in path.read_text()
    assert "could not be downloaded" in capsys.readouterr().out


def test_a_copy_already_there_is_kept_and_not_fetched_again(env, monkeypatch):
    path, shared = env
    target = shared / skybrightness.RELATIVE_PATH
    target.parent.mkdir(parents=True)
    target.write_bytes(b"map")
    monkeypatch.setattr(
        skybrightness, "download", lambda *a, **k: pytest.fail("fetched again")
    )

    skybrightness.offer(path, flag=True)

    assert "SKY_BRIGHTNESS_GEOTIFF_PATH=/data/" in Path(path).read_text()
