"""The API pointer: which server every command talks to, and how it moves."""

import pytest

from arcsecond.api.config import (
    API_NAME_ENV_VAR,
    CLI_SECTION,
    DEFAULT_API_NAME,
    ArcsecondConfig,
)
from arcsecond.errors import ArcsecondError
from tests.utils import random_string, save_test_credentials

ADDRESS = "http://example.test:8800"


@pytest.fixture(autouse=True)
def fresh_pointer(monkeypatch):
    monkeypatch.delenv(API_NAME_ENV_VAR, raising=False)
    ArcsecondConfig.write_cli_setting("api", None)
    yield
    ArcsecondConfig.write_cli_setting("api", None)


def _register(address=ADDRESS):
    name = random_string()
    ArcsecondConfig(api_name=name).api_server = address
    return name


def test_the_pointer_is_cloud_until_moved():
    assert ArcsecondConfig.current_api_name() == DEFAULT_API_NAME
    assert ArcsecondConfig().api_name == DEFAULT_API_NAME
    assert ArcsecondConfig().api_server.startswith("https://api.arcsecond.io")


def test_moving_the_pointer_changes_what_every_config_resolves_to():
    name = _register()
    ArcsecondConfig.set_current_api_name(name)
    assert ArcsecondConfig.current_api_name() == name
    assert ArcsecondConfig().api_name == name
    assert ArcsecondConfig().api_server == ADDRESS


def test_the_environment_variable_overrides_for_this_process_only(monkeypatch):
    recorded = _register()
    one_shot = _register("http://cron.test")
    ArcsecondConfig.set_current_api_name(recorded)

    monkeypatch.setenv(API_NAME_ENV_VAR, one_shot)
    assert ArcsecondConfig.current_api_name() == one_shot
    assert ArcsecondConfig().api_server == "http://cron.test"
    assert ArcsecondConfig.is_api_name_overridden()

    # The recorded pointer was not touched.
    assert ArcsecondConfig.read_cli_setting("api") == recorded


def test_an_explicit_api_name_wins_over_the_pointer():
    name = _register()
    other = _register("http://other.test")
    ArcsecondConfig.set_current_api_name(name)
    assert ArcsecondConfig(api_name=other).api_server == "http://other.test"


def test_pointing_at_an_unregistered_name_is_refused():
    with pytest.raises(ArcsecondError, match="not registered|No API server"):
        ArcsecondConfig.set_current_api_name(random_string())
    assert ArcsecondConfig.current_api_name() == DEFAULT_API_NAME


def test_the_cli_section_is_never_read_as_an_api():
    with pytest.raises(ArcsecondError):
        ArcsecondConfig(api_name=CLI_SECTION)
    ArcsecondConfig.write_cli_setting("something", "else")
    assert CLI_SECTION not in ArcsecondConfig.registered_api_names()


def test_registered_names_start_with_cloud_and_list_every_server():
    name = _register()
    names = ArcsecondConfig.registered_api_names()
    assert names[0] == DEFAULT_API_NAME
    assert name in names
    # A section with credentials but no address is not a server.
    bare = random_string()
    save_test_credentials(bare, "cedric")
    assert bare not in ArcsecondConfig.registered_api_names()


def test_removing_a_server_forgets_its_credentials_and_resets_the_pointer():
    name = _register()
    save_test_credentials(name, "cedric")
    ArcsecondConfig(api_name=name).api_server = ADDRESS
    ArcsecondConfig.set_current_api_name(name)

    ArcsecondConfig.remove_api(name)

    assert name not in ArcsecondConfig.registered_api_names()
    assert ArcsecondConfig.current_api_name() == DEFAULT_API_NAME
    assert ArcsecondConfig(api_name=name).is_logged_in is False


def test_cloud_cannot_be_removed_and_unknown_names_are_refused():
    with pytest.raises(ArcsecondError):
        ArcsecondConfig.remove_api(DEFAULT_API_NAME)
    with pytest.raises(ArcsecondError):
        ArcsecondConfig.remove_api(random_string())


def test_the_listing_marks_the_current_server():
    name = _register()
    listing = ArcsecondConfig().all_apis
    assert f" * {DEFAULT_API_NAME}:" in listing
    assert f"   {name}: {ADDRESS}" in listing

    ArcsecondConfig.set_current_api_name(name)
    listing = ArcsecondConfig().all_apis
    assert f" * {name}: {ADDRESS}" in listing
    assert f"   {DEFAULT_API_NAME}:" in listing
