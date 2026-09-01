from pathlib import Path

import pytest

from arcsecond.api.config import CONFIG_DIR_ENV_VAR, ArcsecondConfig
from arcsecond.errors import ArcsecondError
from arcsecond.options import State
from tests.utils import random_string, save_test_credentials

USERNAME = "cedric"
ACCESS_KEY = "1-2-3"
UPLOAD_KEY = "9-8-7"


def test_config_file_path():
    assert ArcsecondConfig.file_path() == ArcsecondConfig.dir_path() / "config.ini"


# ---------------------------------------------------------------------------
# Where the configuration lives
# ---------------------------------------------------------------------------


def _home(monkeypatch, path):
    """Point Path.home() somewhere else, on either platform."""
    monkeypatch.setenv("HOME", str(path))
    monkeypatch.setenv("USERPROFILE", str(path))


def test_the_config_lives_under_the_home_directory_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv(CONFIG_DIR_ENV_VAR, raising=False)
    _home(monkeypatch, tmp_path)
    assert ArcsecondConfig.dir_path() == tmp_path / ".config" / "arcsecond"
    assert ArcsecondConfig.is_dir_path_overridden() is False


def test_the_config_directory_can_be_moved_elsewhere(monkeypatch, tmp_path):
    """What keeps a container, a second profile — and this suite — apart."""
    monkeypatch.setenv(CONFIG_DIR_ENV_VAR, str(tmp_path / "elsewhere"))
    assert ArcsecondConfig.dir_path() == tmp_path / "elsewhere"
    assert ArcsecondConfig.is_dir_path_overridden() is True


def test_a_blank_override_is_treated_as_no_override(monkeypatch, tmp_path):
    """An unset variable often arrives as an empty string, not as nothing."""
    _home(monkeypatch, tmp_path)
    monkeypatch.setenv(CONFIG_DIR_ENV_VAR, "   ")
    assert ArcsecondConfig.dir_path() == tmp_path / ".config" / "arcsecond"
    assert ArcsecondConfig.is_dir_path_overridden() is False


def test_an_override_is_expanded_like_a_shell_would(monkeypatch, tmp_path):
    _home(monkeypatch, tmp_path)
    monkeypatch.setenv(CONFIG_DIR_ENV_VAR, "~/somewhere")
    assert ArcsecondConfig.dir_path() == tmp_path / "somewhere"


def test_writing_the_config_creates_the_directory_it_needs(monkeypatch, tmp_path):
    monkeypatch.setenv(CONFIG_DIR_ENV_VAR, str(tmp_path / "brand" / "new"))
    assert ArcsecondConfig.file_path().exists()


# ---------------------------------------------------------------------------
# The one-time move of the pre-0.9 ~/.arcsecond.ini
# ---------------------------------------------------------------------------


def test_an_old_config_is_still_moved_into_place(monkeypatch, tmp_path):
    monkeypatch.delenv(CONFIG_DIR_ENV_VAR, raising=False)
    _home(monkeypatch, tmp_path)
    legacy = tmp_path / ".arcsecond.ini"
    legacy.write_text("[cloud]\nusername = cedric\n")

    moved = ArcsecondConfig.file_path()

    assert legacy.exists() is False
    assert "cedric" in moved.read_text()


def test_an_old_config_is_left_alone_when_the_directory_is_overridden(
    monkeypatch, tmp_path
):
    """Otherwise a test run would carry the developer's own file into a temp
    directory and delete it from their home."""
    _home(monkeypatch, tmp_path)
    legacy = tmp_path / ".arcsecond.ini"
    legacy.write_text("[cloud]\nusername = cedric\n")
    monkeypatch.setenv(CONFIG_DIR_ENV_VAR, str(tmp_path / "elsewhere"))

    created = ArcsecondConfig.file_path()

    assert legacy.exists() is True
    assert legacy.read_text() == "[cloud]\nusername = cedric\n"
    assert created.read_text() == ""


# ---------------------------------------------------------------------------
# The suite must not write into whoever is running it
# ---------------------------------------------------------------------------


def test_this_suite_is_not_writing_to_the_real_configuration():
    """A canary for the autouse fixture in conftest.py.

    Tests below save real-looking credentials. If the isolation is ever removed
    they would go to the developer's own config file and stay there, which is
    the state this test exists to keep from coming back.
    """
    assert ArcsecondConfig.is_dir_path_overridden() is True
    assert Path.home() not in ArcsecondConfig.dir_path().parents


def test_config_file_is_logged_in_no_file():
    random_api_name = random_string()
    config = ArcsecondConfig(api_name=random_api_name)
    config.reset()
    assert config.is_logged_in is False


def test_config_api_server():
    random_api_name = random_string()
    config = ArcsecondConfig(api_name=random_api_name)
    assert config.api_server == ""
    config.api_server = "http://localhost/dummy:8989"
    assert config.api_server == "http://localhost/dummy:8989"


def test_config_api_server_from_state():
    random_api_name = random_string()
    config = ArcsecondConfig.from_state(State(api_name=random_api_name))
    assert config.api_name == random_api_name
    assert config.api_server == ""
    config.api_server = "http://localhost/dummy:8989"
    assert config.api_server == "http://localhost/dummy:8989"


def test_config_memberships():
    random_api_name = random_string()
    config = ArcsecondConfig(api_name=random_api_name)
    assert config.memberships == {}
    ms = [
        {"organisation": "oma", "role": "superadmin"},
        {"organisation": "arcsecond", "role": "member"},
    ]
    config.save_memberships(ms)
    assert config.memberships == {"oma": "superadmin", "arcsecond": "member"}


def test_config_access_key():
    random_api_name = random_string()
    config = ArcsecondConfig(api_name=random_api_name)
    assert config.access_key == ""
    config.save_access_key("1234")
    assert config.access_key == "1234"


def test_config_upload_key():
    random_api_name = random_string()
    config = ArcsecondConfig(api_name=random_api_name)
    assert config.upload_key == ""
    config.save_upload_key("1234")
    assert config.upload_key == "1234"


def test_config_change_master_api_server():
    with pytest.raises(ArcsecondError):
        config = ArcsecondConfig()
        config.api_server = "http://dummy.com"


def test_default_empty_state():
    random_api_name = random_string()
    assert ArcsecondConfig(api_name=random_api_name).is_logged_in is False
    assert ArcsecondConfig(api_name=random_api_name).username == ""
    assert ArcsecondConfig(api_name=random_api_name).memberships == {}


def test_default_logged_in_state():
    random_api_name = random_string()
    save_test_credentials(random_api_name, "cedric")
    assert ArcsecondConfig(api_name=random_api_name).is_logged_in is True
    assert ArcsecondConfig(api_name=random_api_name).username == "cedric"
    assert ArcsecondConfig(api_name=random_api_name).memberships == {}


def test_default_logged_in_with_membership_state():
    random_api_name = random_string()
    save_test_credentials(
        random_api_name, "cedric", [{"organisation": "saao", "role": "superadmin"}]
    )
    assert ArcsecondConfig(api_name=random_api_name).is_logged_in is True
    assert ArcsecondConfig(api_name=random_api_name).username == "cedric"
    assert ArcsecondConfig(api_name=random_api_name).memberships == {
        "saao": "superadmin"
    }
