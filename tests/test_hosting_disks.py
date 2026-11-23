"""`arcsecond disks`, and the once-only question `setup` and `update` ask."""

import subprocess

import pytest
from click.testing import CliRunner

from arcsecond.hosting import disks, stack
from arcsecond.hosting.stack import InstallDir


@pytest.fixture
def install(tmp_path, monkeypatch):
    (tmp_path / "docker-compose.yml").write_text("services: {}\n")
    (tmp_path / ".env").write_text("SECRET_KEY=x\n")
    monkeypatch.chdir(tmp_path)
    calls = []

    def compose_streaming(install, *args, echo=None):
        calls.append(tuple(args))
        return subprocess.CompletedProcess(list(args), 0, stdout="", stderr="")

    monkeypatch.setattr(stack, "ensure_docker", lambda: "2.29.1")
    monkeypatch.setattr(stack, "compose_streaming", compose_streaming)
    return {"path": tmp_path, "install": InstallDir(tmp_path), "calls": calls}


def _run(*args, **kwargs):
    return CliRunner().invoke(disks.disks_group, list(args), **kwargs)


def test_add_mounts_the_disk_on_every_storage_service_and_restarts_them(
    install, tmp_path
):
    astro = tmp_path / "Astro Data"
    astro.mkdir()
    result = _run("add", str(astro))
    assert result.exit_code == 0, result.output
    assert disks.read_disks(install["install"]) == {"astro-data": astro.as_posix()}
    text = (tmp_path / disks.DISKS_COMPOSE_FILENAME).read_text()
    for service in disks.DISK_SERVICES:
        assert f"  {service}:" in text
    assert text.count("target: /disks/astro-data") == len(disks.DISK_SERVICES)
    assert install["calls"] == [("up", "-d", "--force-recreate", *disks.DISK_SERVICES)]


def test_names_are_unique_and_paths_round_trip(install, tmp_path):
    first, second = tmp_path / "a" / "data", tmp_path / "b" / "data$1"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    assert disks.add_disk(install["install"], str(first)) == "data"
    assert disks.add_disk(install["install"], str(second)) == "data-1"
    assert disks.add_disk(install["install"], str(first)) == "data"  # already there
    assert disks.read_disks(install["install"]) == {
        "data": first.as_posix(),
        "data-1": second.as_posix(),
    }
    # `$` doubles for compose, and comes back single.
    assert "data$$1" in (tmp_path / disks.DISKS_COMPOSE_FILENAME).read_text()


def test_compose_is_given_the_disks_file(install, tmp_path):
    folder = tmp_path / "disk"
    folder.mkdir()
    assert disks.DISKS_COMPOSE_FILENAME not in " ".join(
        stack.compose_command(install["install"], "ps")
    )
    disks.add_disk(install["install"], str(folder))
    assert str(tmp_path / disks.DISKS_COMPOSE_FILENAME) in stack.compose_command(
        install["install"], "ps"
    )


def test_a_missing_folder_is_refused(install, tmp_path):
    result = _run("add", str(tmp_path / "nope"))
    assert result.exit_code != 0
    assert not (tmp_path / disks.DISKS_COMPOSE_FILENAME).exists()


def test_remove_and_list(install, tmp_path):
    folder = tmp_path / "disk"
    folder.mkdir()
    disks.add_disk(install["install"], str(folder))
    assert "disk" in _run("list").output
    result = _run("remove", "disk", "--no-restart")
    assert result.exit_code == 0, result.output
    assert not (tmp_path / disks.DISKS_COMPOSE_FILENAME).exists()
    assert "No disk yet" in _run("list").output
    assert _run("remove", "disk").exit_code != 0


def test_the_question_is_asked_once(install, tmp_path, monkeypatch):
    monkeypatch.setattr(disks.sys.stdin, "isatty", lambda: True, raising=False)
    folder = tmp_path / "disk"
    folder.mkdir()

    monkeypatch.setattr(disks.click, "confirm", lambda *a, **k: False)
    assert disks.offer_disks(install["install"]) is False
    assert "ARCSECOND_LOCAL_DISKS=no" in (tmp_path / ".env").read_text()
    monkeypatch.setattr(
        disks.click, "confirm", lambda *a, **k: pytest.fail("asked twice")
    )
    assert disks.offer_disks(install["install"]) is False


def test_the_question_adds_the_disks_typed(install, tmp_path, monkeypatch):
    monkeypatch.setattr(disks.sys.stdin, "isatty", lambda: True, raising=False)
    folder = tmp_path / "disk"
    folder.mkdir()
    answers = iter([str(tmp_path / "nope"), str(folder), ""])
    monkeypatch.setattr(disks.click, "confirm", lambda *a, **k: True)
    monkeypatch.setattr(disks.click, "prompt", lambda *a, **k: next(answers))
    assert disks.offer_disks(install["install"]) is True
    assert disks.read_disks(install["install"]) == {"disk": folder.as_posix()}
    # Disks there: not asked again.
    monkeypatch.setattr(
        disks.click, "confirm", lambda *a, **k: pytest.fail("asked twice")
    )
    assert disks.offer_disks(install["install"]) is False


def test_no_question_without_a_terminal(install, monkeypatch):
    monkeypatch.setattr(disks.sys.stdin, "isatty", lambda: False, raising=False)
    monkeypatch.setattr(disks.click, "confirm", lambda *a, **k: pytest.fail("asked"))
    assert disks.offer_disks(install["install"]) is False
