"""`arcsecond start/stop/restart/status/logs/update`, with compose stubbed."""

import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from arcsecond.api.config import API_NAME_ENV_VAR, ArcsecondConfig
from arcsecond.hosting import lifecycle, local, stack
from arcsecond.imagesources import autostart
from arcsecond.imagesources import commands as cameras


@pytest.fixture
def install(tmp_path, monkeypatch):
    """A fake installation in cwd, a docker that answers, a compose that
    records what it was asked, and a backend that is healthy at once."""
    monkeypatch.delenv(API_NAME_ENV_VAR, raising=False)
    ArcsecondConfig.write_cli_setting("api", None)
    packaged_version = local._compose_version(local.packaged_compose_text())
    (tmp_path / "docker-compose.yml").write_text(
        f"# Version {packaged_version}\nservices: {{}}\n"
    )
    (tmp_path / ".env").write_text("HOSTED_FRONTEND_HOST=\n")
    monkeypatch.chdir(tmp_path)

    calls = []

    def compose_streaming(install, *args, echo=None):
        calls.append(tuple(args))
        if echo:
            echo("progress line")
        return subprocess.CompletedProcess(list(args), 0, stdout="", stderr="")

    monkeypatch.setattr(stack, "ensure_docker", lambda: "2.29.1")
    monkeypatch.setattr(stack, "compose_streaming", compose_streaming)
    monkeypatch.setattr(stack, "wait_for_backend", lambda **k: None)
    monkeypatch.setattr(stack, "services_status", lambda install: [])
    monkeypatch.setattr(cameras, "_running_proxy_port", lambda: None)
    monkeypatch.setattr(autostart, "is_enabled", lambda: False)
    return {"path": tmp_path, "calls": calls}


def _run(command, *args, **kwargs):
    return CliRunner().invoke(command, list(args), **kwargs)


# --- start -------------------------------------------------------------------


def test_start_brings_the_stack_up_and_says_where_it_is(install):
    result = _run(lifecycle.start)
    assert result.exit_code == 0, result.output
    assert install["calls"] == [("up", "-d", "--remove-orphans")]
    assert "Arcsecond.local is up." in result.output
    assert "http://localhost:5555" in result.output
    assert "only works on this machine" in result.output


def test_start_pull_and_recreate_map_onto_compose(install):
    result = _run(lifecycle.start, "--pull", "--recreate")
    assert result.exit_code == 0, result.output
    assert install["calls"] == [
        ("pull",),
        ("up", "-d", "--remove-orphans", "--force-recreate"),
    ]


def test_start_no_wait_does_not_poll_the_backend(install, monkeypatch):
    def never(**kwargs):
        raise AssertionError("waited")

    monkeypatch.setattr(stack, "wait_for_backend", never)
    result = _run(lifecycle.start, "--no-wait")
    assert result.exit_code == 0, result.output
    assert "is up" not in result.output


def test_start_explains_a_known_compose_failure(install, monkeypatch):
    def failing(install, *args, echo=None):
        return subprocess.CompletedProcess(
            list(args),
            1,
            stdout="",
            stderr="Error: ports are not available: 0.0.0.0:5555",
        )

    monkeypatch.setattr(stack, "compose_streaming", failing)
    result = _run(lifecycle.start)
    assert result.exit_code != 0
    assert "docker compose up" in result.output
    assert "5555" in result.output
    assert "netstat" in result.output


def test_start_points_at_the_local_api_once_it_is_registered(install):
    ArcsecondConfig(api_name=local.LOCAL_API_NAME).api_server = local.LOCAL_API_ADDRESS
    result = _run(lifecycle.start)
    assert "arcsecond api use local" in result.output

    ArcsecondConfig.set_current_api_name(local.LOCAL_API_NAME)
    result = _run(lifecycle.start)
    assert "arcsecond api use local" not in result.output
    ArcsecondConfig.write_cli_setting("api", None)


def test_start_shows_the_lan_address_when_one_is_declared(install):
    (install["path"] / ".env").write_text("HOSTED_FRONTEND_HOST=10.0.0.77:5555\n")
    result = _run(lifecycle.start)
    assert "http://10.0.0.77:5555" in result.output
    assert "only works on this machine" not in result.output


@pytest.mark.parametrize(
    "reason, fragment",
    [
        ("missing", "arcsecond status"),
        ("unhealthy", "logs backend"),
        ("timeout", "still be working"),
    ],
)
def test_start_says_why_the_backend_is_not_ready(
    install, monkeypatch, reason, fragment
):
    monkeypatch.setattr(stack, "wait_for_backend", lambda **k: reason)
    result = _run(lifecycle.start)
    assert result.exit_code != 0
    assert fragment in result.output


def test_start_without_an_installation_says_where_it_looked(
    install, monkeypatch, tmp_path
):
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.chdir(empty)
    stack.remember_install_dir(tmp_path / "nowhere")
    result = _run(lifecycle.start)
    assert result.exit_code != 0
    assert "Could not find an Arcsecond.local installation" in result.output
    assert str(empty) in result.output


def test_dir_points_at_another_installation(install, tmp_path, monkeypatch):
    other = tmp_path / "other"
    other.mkdir()
    (other / "docker-compose.yml").write_text("services: {}\n")
    (other / ".env").write_text("")
    monkeypatch.chdir(tmp_path.parent)
    result = _run(lifecycle.start, "--dir", str(other))
    assert result.exit_code == 0, result.output
    assert str(other) in result.output


# --- stop / restart ----------------------------------------------------------


def test_stop_stops_and_never_removes_volumes(install):
    result = _run(lifecycle.stop)
    assert result.exit_code == 0, result.output
    assert install["calls"] == [("stop",)]

    install["calls"].clear()
    result = _run(lifecycle.stop, "--down")
    assert install["calls"] == [("down",)]
    assert not any("-v" in call or "--volumes" in call for call in install["calls"])


def test_restart_recreates_the_named_services(install):
    result = _run(lifecycle.restart, "backend", "worker")
    assert result.exit_code == 0, result.output
    assert install["calls"] == [("up", "-d", "--force-recreate", "backend", "worker")]
    assert "is up" in result.output  # backend was among them: waited for it


def test_restart_of_a_side_service_does_not_wait_for_the_backend(install, monkeypatch):
    monkeypatch.setattr(stack, "wait_for_backend", lambda **k: pytest.fail("waited"))
    result = _run(lifecycle.restart, "alerts")
    assert result.exit_code == 0, result.output
    assert "Done." in result.output


def test_restart_without_names_recreates_everything(install):
    result = _run(lifecycle.restart)
    assert result.exit_code == 0, result.output
    assert install["calls"] == [("up", "-d", "--force-recreate")]


# --- status ------------------------------------------------------------------


def test_status_lists_containers_and_says_the_template_is_current(install, monkeypatch):
    monkeypatch.setattr(
        stack,
        "services_status",
        lambda install: [
            {
                "Service": "web",
                "State": "running",
                "Health": "",
                "Image": "ghcr.io/x/web:1",
            },
            {
                "Service": "backend",
                "State": "running",
                "Health": "healthy",
                "Image": "ghcr.io/x/api:1",
            },
            {
                "Service": "worker",
                "State": "exited",
                "Health": "",
                "Image": "ghcr.io/x/api:1",
            },
        ],
    )
    result = _run(lifecycle.status)
    assert result.exit_code == 0, result.output
    assert "(current)" in result.output
    assert (
        result.output.index("backend")
        < result.output.index("web")
        < result.output.index("worker")
    )
    assert "exited" in result.output
    assert "Live-image proxy: not running" in result.output
    assert "http://localhost:5555" in result.output


def test_status_flags_an_outdated_compose_file(install):
    (install["path"] / "docker-compose.yml").write_text("# Version 1.0\nservices: {}\n")
    result = _run(lifecycle.status)
    assert "arcsecond update" in result.output


def test_status_without_docker_still_describes_the_installation(install, monkeypatch):
    def unavailable():
        raise lifecycle.ArcsecondError(stack.DOCKER_NOT_RUNNING)

    monkeypatch.setattr(stack, "ensure_docker", unavailable)
    result = _run(lifecycle.status)
    assert result.exit_code == 0, result.output
    assert "unavailable" in result.output
    assert "Docker Desktop" in result.output
    assert str(install["path"]) in result.output


def test_status_mentions_the_proxy_and_its_autostart(install, monkeypatch):
    monkeypatch.setattr(cameras, "_running_proxy_port", lambda: 8765)
    monkeypatch.setattr(autostart, "is_enabled", lambda: True)
    result = _run(lifecycle.status)
    assert "running on port 8765" in result.output
    assert "when you log in" in result.output


# --- logs --------------------------------------------------------------------


def test_logs_passes_service_tail_and_follow_through(install, monkeypatch):
    seen = {}

    def run(cmd, **kwargs):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(lifecycle.subprocess, "run", run)
    result = _run(lifecycle.logs, "backend", "-f", "--tail", "50")
    assert result.exit_code == 0, result.output
    cmd = seen["cmd"]
    assert cmd[cmd.index("--tail") + 1] == "50"
    assert "--follow" in cmd
    assert cmd[-1] == "backend"


def test_logs_default_shows_recent_lines_of_everything(install, monkeypatch):
    seen = {}
    monkeypatch.setattr(
        lifecycle.subprocess,
        "run",
        lambda cmd, **k: seen.setdefault("cmd", cmd)
        and subprocess.CompletedProcess(cmd, 0),
    )
    _run(lifecycle.logs)
    assert seen["cmd"][-2:] == ["--tail", "200"]


# --- update ------------------------------------------------------------------


def test_update_refreshes_the_files_then_pulls_and_restarts(install, monkeypatch):
    written = {}
    monkeypatch.setattr(
        lifecycle,
        "write_env_file",
        lambda directory=None: written.setdefault("env", directory),
    )
    monkeypatch.setattr(
        lifecycle,
        "write_docker_compose_file",
        lambda enabled_services, removed_services, directory=None: written.setdefault(
            "compose", directory
        ),
    )
    monkeypatch.setattr(
        lifecycle,
        "_resolve_optional_services",
        lambda env_path, flags: (set(), set(), []),
    )

    result = _run(lifecycle.update)
    assert result.exit_code == 0, result.output
    assert written == {"env": Path(install["path"]), "compose": Path(install["path"])}
    assert install["calls"] == [("pull",), ("up", "-d", "--remove-orphans")]
    assert "is up" in result.output


# --- the surface ------------------------------------------------------------


def test_the_lifecycle_commands_are_mounted():
    from arcsecond import cli

    listing = CliRunner().invoke(cli.main, ["--help"]).output
    for command in ("start", "stop", "restart", "status", "logs", "update"):
        assert f"  {command} " in listing, command
    assert "netcam" not in cli.main.commands
