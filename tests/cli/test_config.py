import random
import string

import pytest

from arcsecond.api.config import ArcsecondConfig
from arcsecond.errors import ArcsecondError
from arcsecond.options import State

SECTION = "test"
USERNAME = "cedric"
ACCESS_KEY = "1-2-3"
UPLOAD_KEY = "9-8-7"


def random_string(n=10):
    # https://stackoverflow.com/questions/2257441/random-string-generation-with-upper-case-letters-and-digits-in-python
    return ''.join(random.choice(string.ascii_letters) for _ in range(n))


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
        config.api_server = 'http://dummy.com'
