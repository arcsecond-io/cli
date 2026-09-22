"""Finding the installation and driving compose — without Docker present."""

import subprocess
from pathlib import Path

import pytest

from arcsecond.errors import ArcsecondError
from arcsecond.hosting import stack


def _make_install(path: Path, env: str = "") -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "docker-compose.yml").write_text("# Version 6.4\nservices: {}\n")
    (path / ".env").write_text(env)
    return path


# --- where the installation is ----------------------------------------------


def test_the_current_folder_is_found_first(tmp_path, monkeypatch):
    here = _make_install(tmp_path / "here")
    monkeypatch.chdir(here)
    assert stack.resolve_install_dir().path == here.resolve()


def test_the_remembered_folder_is_used_when_the_current_one_is_not_an_install(
    tmp_path, monkeypatch
):
    remembered = _make_install(tmp_path / "obs")
    monkeypatch.chdir(tmp_path)  # holds no compose file
    stack.remember_install_dir(remembered)
    assert stack.resolve_install_dir().path == remembered.resolve()


def test_dir_is_explicit_and_must_hold_an_install(tmp_path, monkeypatch):
    elsewhere = _make_install(tmp_path / "elsewhere")
    monkeypatch.chdir(_make_install(tmp_path / "here"))
    assert stack.resolve_install_dir(str(elsewhere)).path == elsewhere.resolve()

    with pytest.raises(ArcsecondError, match="arcsecond setup"):
        stack.resolve_install_dir(str(tmp_path / "nowhere"))


def test_the_error_says_where_it_looked(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    stack.remember_install_dir(tmp_path / "gone")
    with pytest.raises(ArcsecondError) as excinfo:
        stack.resolve_install_dir()
    message = str(excinfo.value)
    assert str(tmp_path) in message
    assert "gone" in message
    assert "--dir" in message


def test_read_env_reads_the_installations_own_file(tmp_path):
    install = stack.InstallDir(
        _make_install(tmp_path, env='HOSTED_FRONTEND_HOST="10.0.0.77:5555"\n')
    )
    assert install.read_env("HOSTED_FRONTEND_HOST") == "10.0.0.77:5555"
    assert install.read_env("MISSING") is None


# --- reaching docker ---------------------------------------------------------


class _Result:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_docker_missing_from_path_is_said_plainly(monkeypatch):
    monkeypatch.setattr(stack.shutil, "which", lambda name: None)
    with pytest.raises(ArcsecondError, match="not installed"):
        stack.ensure_docker()


@pytest.mark.parametrize(
    "stderr, expected",
    [
        (
            "permission denied while trying to connect to the Docker daemon socket",
            stack.DOCKER_PERMISSION,
        ),
        (
            "Cannot connect to the Docker daemon. Is the docker daemon running?",
            stack.DOCKER_NOT_RUNNING,
        ),
    ],
)
def test_a_failing_docker_info_is_explained(monkeypatch, stderr, expected):
    monkeypatch.setattr(stack.shutil, "which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr(
        stack, "_run", lambda cmd, timeout=None, **k: _Result(1, stderr=stderr)
    )
    with pytest.raises(ArcsecondError) as excinfo:
        stack.ensure_docker()
    assert str(excinfo.value) == expected


def test_a_hanging_docker_is_not_waited_on_forever(monkeypatch):
    monkeypatch.setattr(stack.shutil, "which", lambda name: "/usr/bin/docker")

    def hang(cmd, timeout=None, **k):
        raise subprocess.TimeoutExpired(cmd, timeout)

    monkeypatch.setattr(stack, "_run", hang)
    with pytest.raises(ArcsecondError, match="still starting"):
        stack.ensure_docker()


def test_compose_v2_missing_is_told_apart_from_docker_missing(monkeypatch):
    monkeypatch.setattr(stack.shutil, "which", lambda name: "/usr/bin/docker")

    def run(cmd, timeout=None, **k):
        if cmd[:2] == ["docker", "info"]:
            return _Result(0, stdout="27.0\n")
        return _Result(1, stderr="unknown command compose")

    monkeypatch.setattr(stack, "_run", run)
    with pytest.raises(ArcsecondError, match="docker compose"):
        stack.ensure_docker()


def test_ensure_docker_returns_the_compose_version(monkeypatch):
    monkeypatch.setattr(stack.shutil, "which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr(
        stack, "_run", lambda cmd, timeout=None, **k: _Result(0, stdout="2.29.1\n")
    )
    assert stack.ensure_docker() == "2.29.1"


# --- compose itself ----------------------------------------------------------


def test_compose_commands_pin_the_project_directory_and_file(tmp_path):
    install = stack.InstallDir(_make_install(tmp_path))
    cmd = stack.compose_command(install, "up", "-d")
    assert cmd[:2] == ["docker", "compose"]
    assert cmd[cmd.index("--project-directory") + 1] == str(install.path)
    assert cmd[cmd.index("-f") + 1] == str(install.compose_path)
    assert cmd[-2:] == ["up", "-d"]


def test_ps_json_is_parsed_in_both_shapes_compose_has_used():
    as_array = '[{"Service": "backend", "State": "running"}]'
    as_lines = '{"Service": "backend", "State": "running"}\n{"Service": "web", "State": "exited"}\n'
    assert stack._parse_json_lines(as_array) == [
        {"Service": "backend", "State": "running"}
    ]
    assert [i["Service"] for i in stack._parse_json_lines(as_lines)] == [
        "backend",
        "web",
    ]
    assert stack._parse_json_lines("") == []
    assert stack._parse_json_lines("not json") == []


@pytest.mark.parametrize(
    "stderr, fragment",
    [
        (
            "Error response from daemon: ports are not available: exposing port TCP 0.0.0.0:5555",
            "5555",
        ),
        (
            "permission denied while trying to connect to the Docker daemon socket",
            "docker group",
        ),
        (
            "Cannot connect to the Docker daemon at unix:///var/run/docker.sock",
            "Docker Desktop",
        ),
        ("no such service: alerts", "arcsecond status"),
        (
            'Conflict. The container name "/arcsecond-db" is already in use by container "7552f"',
            "docker rm -f",
        ),
        (
            "Error response from daemon: pull access denied for ghcr.io/arcsecond-io/api",
            "arcsecond token set",
        ),
    ],
)
def test_known_compose_failures_are_explained(stderr, fragment):
    explanation = stack.explain_compose_failure(stderr)
    assert explanation is not None
    assert fragment in explanation


def test_an_unknown_compose_failure_shows_what_docker_said():
    assert stack.explain_compose_failure("something novel") is None
    with pytest.raises(ArcsecondError) as excinfo:
        stack.raise_compose_failure(
            "docker compose up", _Result(1, stderr="something novel")
        )
    message = str(excinfo.value)
    assert "docker compose up" in message
    assert "something novel" in message


# --- waiting for the backend -------------------------------------------------


def _states(monkeypatch, sequence):
    remaining = list(sequence)

    def container_state(name):
        assert name == stack.API_CONTAINER
        return remaining.pop(0) if len(remaining) > 1 else remaining[0]

    monkeypatch.setattr(stack, "container_state", container_state)


def test_wait_returns_none_once_the_healthcheck_passes(monkeypatch):
    _states(monkeypatch, [(True, "starting"), (True, "starting"), (True, "healthy")])
    ticks = []
    reason = stack.wait_for_backend(
        timeout=60,
        poll=1,
        tick=lambda: ticks.append(1),
        clock=lambda: 0,
        sleep=lambda s: None,
    )
    assert reason is None
    assert len(ticks) == 2


def test_wait_reports_a_missing_or_unhealthy_container(monkeypatch):
    _states(monkeypatch, [(None, None)])
    assert (
        stack.wait_for_backend(timeout=5, poll=1, clock=lambda: 0, sleep=lambda s: None)
        == "missing"
    )
    _states(monkeypatch, [(True, "unhealthy")])
    assert (
        stack.wait_for_backend(timeout=5, poll=1, clock=lambda: 0, sleep=lambda s: None)
        == "unhealthy"
    )


def test_wait_gives_up_at_the_deadline(monkeypatch):
    _states(monkeypatch, [(True, "starting")])
    now = [0.0]

    def clock():
        return now[0]

    def sleep(seconds):
        now[0] += seconds

    assert (
        stack.wait_for_backend(timeout=10, poll=3, clock=clock, sleep=sleep)
        == "timeout"
    )


# --- addresses ---------------------------------------------------------------


def test_addresses_are_localhost_plus_the_declared_lan_host(tmp_path):
    only_here = stack.InstallDir(
        _make_install(tmp_path / "a", env="HOSTED_FRONTEND_HOST=\n")
    )
    assert stack.frontend_addresses(only_here) == ["http://localhost:5555"]

    declared = stack.InstallDir(
        _make_install(tmp_path / "b", env="HOSTED_FRONTEND_HOST=10.0.0.77:5555\n")
    )
    assert stack.frontend_addresses(declared) == [
        "http://localhost:5555",
        "http://10.0.0.77:5555",
    ]

    same = stack.InstallDir(
        _make_install(tmp_path / "c", env="HOSTED_FRONTEND_HOST=localhost:5555\n")
    )
    assert stack.frontend_addresses(same) == ["http://localhost:5555"]

    tls = stack.InstallDir(
        _make_install(
            tmp_path / "d",
            env="HOSTED_FRONTEND_HOST=obs.example.com\nHOSTED_FRONTEND_SCHEME=https\n",
        )
    )
    assert stack.frontend_addresses(tls)[1] == "https://obs.example.com"
