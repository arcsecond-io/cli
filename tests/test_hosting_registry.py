"""`arcsecond registry login`: the token goes over a pipe, never into argv."""

import subprocess

import pytest
from click.testing import CliRunner

from arcsecond import cli
from arcsecond.hosting import registry, stack


@pytest.fixture
def docker(monkeypatch):
    monkeypatch.setattr(stack, "ensure_docker", lambda: "2.29")
    calls = []

    def fake_run(cmd, input=None, **kwargs):
        calls.append((cmd, input))
        rc = 0 if (input or "").strip() == "ghp_good" or cmd[1] == "logout" else 1
        return subprocess.CompletedProcess(
            cmd,
            rc,
            stdout="Login Succeeded\n" if rc == 0 else "",
            stderr="" if rc == 0 else "Error response from daemon: denied",
        )

    monkeypatch.setattr(registry.subprocess, "run", fake_run)
    return calls


def test_login_asks_without_echo_and_pipes_the_token(docker):
    result = CliRunner().invoke(cli.main, ["registry", "login"], input="ghp_good\n")
    assert result.exit_code == 0, result.output
    assert "Logged in" in result.output
    assert "ghp_good" not in result.output  # hidden prompt: never echoed
    cmd, token = docker[0]
    assert cmd == [
        "docker",
        "login",
        registry.REGISTRY,
        "-u",
        registry.REGISTRY_USER,
        "--password-stdin",
    ]
    assert token == "ghp_good\n"
    assert not any("ghp_good" in part for part in cmd)


def test_token_stdin_is_for_scripts(docker):
    result = CliRunner().invoke(
        cli.main, ["registry", "login", "--token-stdin"], input="ghp_good\n"
    )
    assert result.exit_code == 0, result.output
    assert docker[0][1] == "ghp_good\n"


def test_there_is_no_token_option():
    result = CliRunner().invoke(cli.main, ["registry", "login", "--token", "x"])
    assert result.exit_code != 0
    assert "No such option" in result.output


def test_a_refused_token_is_explained(docker):
    result = CliRunner().invoke(cli.main, ["registry", "login"], input="ghp_bad\n")
    assert result.exit_code == 1
    assert "Docker refused the login" in result.output
    assert "denied" in result.output


def test_chevrons_around_the_token_are_caught(docker):
    result = CliRunner().invoke(cli.main, ["registry", "login"], input="<ghp_good>\n")
    assert result.exit_code == 1
    assert "placeholder" in result.output
    assert docker == []  # never reached docker


def test_an_empty_token_is_refused(docker):
    result = CliRunner().invoke(
        cli.main, ["registry", "login", "--token-stdin"], input="\n"
    )
    assert result.exit_code == 1 and docker == []


def test_logout(docker):
    result = CliRunner().invoke(cli.main, ["registry", "logout"])
    assert result.exit_code == 0, result.output
    assert docker[0][0] == ["docker", "logout", registry.REGISTRY]


def test_start_points_at_registry_login_when_the_pull_is_denied():
    assert "arcsecond registry login" in stack.explain_compose_failure(
        "pull access denied for ghcr.io/arcsecond-io/arcsecond-api"
    )
