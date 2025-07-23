import pytest

from arcsecond.api.config import ArcsecondConfig
from arcsecond.errors import ArcsecondError
from arcsecond.options import State
from tests.utils import random_string, save_test_credentials

USERNAME = "cedric"
ACCESS_KEY = "1-2-3"
UPLOAD_KEY = "9-8-7"


def test_config_file_path():
    assert str(ArcsecondConfig.file_path()).endswith("arcsecond/config.ini")


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
