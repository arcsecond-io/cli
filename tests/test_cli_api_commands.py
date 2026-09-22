"""`arcsecond api ...` and the 4.0 command surface."""

import pytest
from click.testing import CliRunner

from arcsecond import cli
from arcsecond.api.config import API_NAME_ENV_VAR, DEFAULT_API_NAME, ArcsecondConfig
from arcsecond.cloud import auth
from tests.utils import random_string

ADDRESS = "http://obs.test:8800"


@pytest.fixture(autouse=True)
def fresh_pointer(monkeypatch):
    monkeypatch.delenv(API_NAME_ENV_VAR, raising=False)
    ArcsecondConfig.write_cli_setting("api", None)
    yield
    ArcsecondConfig.write_cli_setting("api", None)


@pytest.fixture
def answering(monkeypatch):
    monkeypatch.setattr(
        auth, "probe_api_server", lambda address: (True, "answered 200")
    )


@pytest.fixture
def silent(monkeypatch):
    monkeypatch.setattr(
        auth, "probe_api_server", lambda address: (False, "ConnectError: refused")
    )


def _invoke(*args, **kwargs):
    return CliRunner().invoke(cli.main, list(args), **kwargs)


def test_add_then_use_points_the_cli_at_the_server(answering):
    name = random_string()
    added = _invoke("api", "add", name, ADDRESS)
    assert added.exit_code == 0, added.output
    assert f'Registered the API "{name}"' in added.output
    assert f"arcsecond api use {name}" in added.output
    assert ArcsecondConfig.current_api_name() == DEFAULT_API_NAME

    used = _invoke("api", "use", name)
    assert used.exit_code == 0, used.output
    assert "now points at" in used.output
    assert "not logged in there yet" in used.output
    assert ArcsecondConfig.current_api_name() == name


def test_use_refuses_a_server_that_does_not_answer_and_leaves_the_pointer(silent):
    name = random_string()
    _invoke("api", "add", name, ADDRESS)
    result = _invoke("api", "use", name)
    assert result.exit_code != 0
    assert "does not answer" in result.output
    assert "was not moved" in result.output
    assert ArcsecondConfig.current_api_name() == DEFAULT_API_NAME


def test_use_refuses_an_unregistered_name(answering):
    result = _invoke("api", "use", random_string())
    assert result.exit_code != 0
    assert "Register it first" in result.output


def test_the_two_token_form_still_registers_a_server():
    name = random_string()
    result = _invoke("api", name, ADDRESS)
    assert result.exit_code == 0, result.output
    assert name in ArcsecondConfig.registered_api_names()


def test_the_cloud_address_cannot_be_changed():
    result = _invoke("api", "add", DEFAULT_API_NAME, ADDRESS)
    assert result.exit_code != 0


def test_listing_marks_the_current_server_and_mentions_the_override(
    monkeypatch, answering
):
    name = random_string()
    _invoke("api", "add", name, ADDRESS)
    _invoke("api", "use", name)
    listing = _invoke("api")
    assert f" * {name}: {ADDRESS}" in listing.output
    assert API_NAME_ENV_VAR not in listing.output

    monkeypatch.setenv(API_NAME_ENV_VAR, DEFAULT_API_NAME)
    listing = _invoke("api")
    assert f" * {DEFAULT_API_NAME}:" in listing.output
    assert API_NAME_ENV_VAR in listing.output


def test_remove_resets_the_pointer_when_it_was_aimed_there(answering):
    name = random_string()
    _invoke("api", "add", name, ADDRESS)
    _invoke("api", "use", name)
    result = _invoke("api", "remove", name)
    assert result.exit_code == 0, result.output
    assert f"points at '{DEFAULT_API_NAME}' again" in result.output
    assert ArcsecondConfig.current_api_name() == DEFAULT_API_NAME


def test_login_reports_the_server_it_logged_in_on(monkeypatch):
    class FakeAPI:
        def __init__(self, config):
            self.config = config

        def login(self, username, **kwargs):
            return True, None

    monkeypatch.setattr(auth, "ArcsecondAPI", FakeAPI)
    result = _invoke("login", input="steve\naccess\n123\n")
    assert result.exit_code == 0, result.output
    assert "Logged in" in result.output
    assert f"'{DEFAULT_API_NAME}'" in result.output


# --- the command surface itself -------------------------------------------


def test_me_is_gone():
    result = _invoke("me")
    assert result.exit_code != 0
    assert "No such command" in result.output


def test_the_api_option_is_gone_from_every_command():
    for command in ("login", "datasets", "telescopes", "setup", "upload"):
        result = _invoke(command, "--api", "local")
        assert result.exit_code != 0, command
        assert "No such option" in result.output and "--api" in result.output, command


def test_upload_is_the_name_and_upload_data_keeps_working():
    assert "upload" in cli.main.commands
    assert cli.main.commands["upload-data"].hidden is True
    listing = _invoke("--help").output
    assert "  upload " in listing
    assert "upload-data" not in listing
    # Same parameters underneath, so the two cannot drift apart.
    assert cli.main.commands["upload-data"].params is cli.main.commands["upload"].params
