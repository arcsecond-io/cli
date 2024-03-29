import httpretty

from arcsecond import ArcsecondAPI, ArcsecondConfig
from arcsecond.api.constants import ARCSECOND_API_URL_DEV
from arcsecond.options import State
from tests.utils import (
    TEST_API_KEY,
    TEST_LOGIN_USERNAME,
    TEST_UPLOAD_KEY,
    clear_test_credentials,
    prepare_successful_login
)


@httpretty.activate
def test_login_basic():
    clear_test_credentials()
    config = ArcsecondConfig(State(api_name='test'))
    config.api_server = ARCSECOND_API_URL_DEV
    assert config.access_key == ''
    prepare_successful_login()
    ArcsecondAPI(config).login(TEST_LOGIN_USERNAME, access_key=TEST_API_KEY)
    assert config.access_key == TEST_API_KEY
    assert config.upload_key == ''


@httpretty.activate
def test_login_upload_key():
    clear_test_credentials()
    config = ArcsecondConfig(State(api_name='test'))
    config.api_server = ARCSECOND_API_URL_DEV
    prepare_successful_login()
    ArcsecondAPI(config).login(username=TEST_LOGIN_USERNAME, upload_key=TEST_UPLOAD_KEY)
    assert config.access_key == ''
    assert config.upload_key == TEST_UPLOAD_KEY
