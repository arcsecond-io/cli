import random
import string
from unittest.mock import patch

from arcsecond import config

SECTION = 'test'
USERNAME = 'cedric'
API_KEY = '1-2-3'
UPLOAD_KEY = '9-8-7'


def test_config_file_path():
    path = config.config_file_path()
    assert path.endswith('.arcsecond.ini')


def test_config_file_is_logged_in_no_file():
    with patch('arcsecond.config.config_file_exists', return_value=False):
        assert config.config_file_is_logged_in(SECTION) is False


def test_config_file_is_logged_in_no_keys():
    with patch('arcsecond.config.config_file_exists', return_value=True):
        config.config_file_clear_section(SECTION)
        assert config.config_file_is_logged_in(SECTION) is False


def test_config_file_is_logged_in_has_api_key():
    config.config_file_save_api_key(API_KEY, USERNAME, SECTION)
    assert config.config_file_is_logged_in(SECTION) is True


def test_config_file_is_logged_in_has_upload_key():
    config.config_file_save_upload_key(UPLOAD_KEY, USERNAME, SECTION)
    assert config.config_file_is_logged_in(SECTION) is True


def test_config_file_is_logged_in_has_api_and_upload_keys():
    config.config_file_save_api_key(API_KEY, USERNAME, SECTION)
    config.config_file_save_upload_key(UPLOAD_KEY, USERNAME, SECTION)
    assert config.config_file_is_logged_in(SECTION) is True


def test_config_write_read_api_key():
    random_key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
    config.config_file_save_api_key(random_key, USERNAME, SECTION)
    assert config.config_file_read_api_key(SECTION) == random_key


def test_config_write_read_upload_key():
    random_key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
    config.config_file_save_upload_key(random_key, USERNAME, SECTION)
    assert config.config_file_read_upload_key(SECTION) == random_key


def test_config_clear_api_key():
    random_key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
    config.config_file_save_api_key(random_key, USERNAME, SECTION)
    assert config.config_file_read_api_key(SECTION) == random_key
    config.config_file_clear_api_key(SECTION)
    assert config.config_file_read_api_key(SECTION) is None


def test_config_clear_upload_key():
    random_key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
    config.config_file_save_upload_key(random_key, USERNAME, SECTION)
    assert config.config_file_read_upload_key(SECTION) == random_key
    config.config_file_clear_upload_key(SECTION)
    assert config.config_file_read_upload_key(SECTION) is None
