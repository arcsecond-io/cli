import httpretty

from arcsecond import ArcsecondAPI
from config import config_file_read_api_key, config_file_read_upload_key
from tests.utils import TEST_API_KEY, TEST_LOGIN_PASSWORD, TEST_LOGIN_USERNAME, TEST_UPLOAD_KEY, clear_test_credentials, \
    prepare_successful_login


@httpretty.activate
def test_login_basic():
    clear_test_credentials()
    assert config_file_read_api_key('test') is None
    prepare_successful_login()
    ArcsecondAPI.login(TEST_LOGIN_USERNAME, TEST_LOGIN_PASSWORD, debug=True, test=True)
    assert config_file_read_api_key('test') is None
    assert config_file_read_upload_key('test') is None


@httpretty.activate
def test_login_apikey():
    clear_test_credentials()
    assert config_file_read_api_key('test') is None
    prepare_successful_login()
    ArcsecondAPI.login(TEST_LOGIN_USERNAME, TEST_LOGIN_PASSWORD, api_key=True, debug=True, test=True)
    assert config_file_read_api_key('test') == TEST_API_KEY
    assert config_file_read_upload_key('test') is None


@httpretty.activate
def test_login_uploadkey():
    clear_test_credentials()
    assert config_file_read_api_key('test') is None
    prepare_successful_login()
    ArcsecondAPI.login(TEST_LOGIN_USERNAME, TEST_LOGIN_PASSWORD, upload_key=True, debug=True, test=True)
    assert config_file_read_api_key('test') is None
    assert config_file_read_upload_key('test') == TEST_UPLOAD_KEY


@httpretty.activate
def test_login_both_apikey_uploadkey():
    clear_test_credentials()
    assert config_file_read_api_key('test') is None
    prepare_successful_login()
    ArcsecondAPI.login(TEST_LOGIN_USERNAME, TEST_LOGIN_PASSWORD, api_key=True, upload_key=True, debug=True, test=True)
    assert config_file_read_api_key('test') == TEST_API_KEY
    assert config_file_read_upload_key('test') == TEST_UPLOAD_KEY
