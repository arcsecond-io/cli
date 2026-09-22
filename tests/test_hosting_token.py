"""`arcsecond token`: the token goes over a pipe, never into argv."""

import json
import subprocess

import pytest
from click.testing import CliRunner

from arcsecond import cli
from arcsecond.hosting import local, stack, token


@pytest.fixture
def docker(monkeypatch, tmp_path):
    monkeypatch.setattr(stack, "ensure_docker", lambda: "2.29")
    monkeypatch.setattr(token, "docker_config_path", lambda: tmp_path / "config.json")
    calls = []

    def fake_run(cmd, input=None, **kwargs):
        calls.append((cmd, input))
        ok = (input or "").strip() == "ghp_good" or cmd[1] == "logout"
        return subprocess.CompletedProcess(
            cmd,
            0 if ok else 1,
            stdout="Login Succeeded\n" if ok else "",
            stderr="" if ok else "Error response from daemon: denied",
        )

    monkeypatch.setattr(token.subprocess, "run", fake_run)
    return calls


def _invoke(*args, **kwargs):
    return CliRunner().invoke(cli.main, list(args), **kwargs)


def test_set_asks_without_echo_and_pipes_the_token(docker):
    result = _invoke("token", "set", input="ghp_good\n")
    assert result.exit_code == 0, result.output
    assert "Token accepted" in result.output
    assert "ghp_good" not in result.output
    cmd, piped = docker[0]
    assert cmd == [
        "docker",
        "login",
        token.REGISTRY,
        "-u",
        token.REGISTRY_USER,
        "--password-stdin",
    ]
    assert piped == "ghp_good\n"
    assert not any("ghp_good" in part for part in cmd)


def test_stdin_is_for_scripts_and_there_is_no_token_option(docker):
    assert _invoke("token", "set", "--stdin", input="ghp_good\n").exit_code == 0
    refused = _invoke("token", "set", "--token", "x")
    assert refused.exit_code != 0 and "No such option" in refused.output


def test_a_refused_token_is_explained_without_docker_words(docker):
    result = _invoke("token", "set", input="ghp_bad\n")
    assert result.exit_code == 1
    assert "refused" in result.output and "team@arcsecond.io" in result.output
    assert "registry" not in result.output.lower()


def test_chevrons_and_empty_input_never_reach_docker(docker):
    assert "placeholder" in _invoke("token", "set", input="<ghp_good>\n").output
    assert _invoke("token", "set", "--stdin", input="\n").exit_code == 1
    assert docker == []


def test_forget(docker):
    result = _invoke("token", "forget")
    assert result.exit_code == 0, result.output
    assert docker[0][0] == ["docker", "logout", token.REGISTRY]


def test_status_reads_dockers_config(docker, tmp_path):
    result = _invoke("token")
    assert result.exit_code == 1 and "no token yet" in result.output
    (tmp_path / "config.json").write_text(
        json.dumps({"auths": {"ghcr.io": {}}, "credsStore": "desktop"})
    )
    result = _invoke("token")
    assert result.exit_code == 0 and "has the token" in result.output


def test_has_token_asks_the_credential_store_when_the_config_lists_nothing(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(token, "docker_config_path", lambda: tmp_path / "config.json")
    (tmp_path / "config.json").write_text(json.dumps({"credsStore": "desktop"}))
    asked = []

    def fake_run(cmd, input=None, **kwargs):
        asked.append((cmd, input))
        return subprocess.CompletedProcess(
            cmd, 0, stdout=json.dumps({"Username": "arcsecond-io", "Secret": "x"})
        )

    monkeypatch.setattr(token.subprocess, "run", fake_run)
    assert token.has_token() is True
    assert (
        asked[0][0] == ["docker-credential-desktop", "get"]
        and asked[0][1] == "https://ghcr.io\n"
    )


def test_start_points_at_the_token_when_the_pull_is_denied():
    assert "arcsecond token set" in stack.explain_compose_failure(
        "pull access denied for ghcr.io/arcsecond-io/arcsecond-api"
    )


# --- setup asks for it -----------------------------------------------------------


@pytest.fixture
def setup_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(local, "_get_random_secret_key", lambda: "s")
    monkeypatch.setattr(local, "_get_encryption_key", lambda: "e")
    monkeypatch.setattr(local, "_get_random_postgres_password", lambda: "p")
    monkeypatch.setattr(local, "prompt_shared_data_path", lambda: "/tmp/shared")
    monkeypatch.setattr(local, "_stdin_is_interactive", lambda: True)
    monkeypatch.setattr(stack, "ensure_docker", lambda: "2.29")
    stored = []
    monkeypatch.setattr(token, "store_token", lambda t: stored.append(t))
    return stored


def test_setup_asks_for_the_token_when_the_machine_has_none(setup_env, monkeypatch):
    monkeypatch.setattr(token, "has_token", lambda: False)
    result = CliRunner().invoke(local.setup, ["--without-alerts"], input="ghp_new\n")
    assert result.exit_code == 0, result.output
    assert "Access token from Arcsecond" in result.output
    assert setup_env == ["ghp_new"]


def test_setup_does_not_ask_again_when_the_machine_has_one(setup_env, monkeypatch):
    monkeypatch.setattr(token, "has_token", lambda: True)
    result = CliRunner().invoke(local.setup, ["--without-alerts"])
    assert result.exit_code == 0, result.output
    assert "Access token" not in result.output and setup_env == []


def test_setup_lets_the_token_wait(setup_env, monkeypatch):
    monkeypatch.setattr(token, "has_token", lambda: False)
    result = CliRunner().invoke(local.setup, ["--without-alerts"], input="\n")
    assert result.exit_code == 0, result.output
    assert "arcsecond token set" in result.output and setup_env == []


def test_setup_without_docker_says_what_to_do_later(setup_env, monkeypatch):
    def down():
        raise local.ArcsecondError("no docker")

    monkeypatch.setattr(stack, "ensure_docker", down)
    result = CliRunner().invoke(local.setup, ["--without-alerts"])
    assert result.exit_code == 0, result.output
    assert "arcsecond token set" in result.output
