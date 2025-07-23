import respx

from arcsecond import ArcsecondAPI, ArcsecondConfig
from arcsecond.api.constants import ARCSECOND_API_URL_DEV
from tests.utils import (
    TEST_API_KEY,
    TEST_LOGIN_USERNAME,
    TEST_UPLOAD_KEY,
    prepare_successful_login,
    random_string,
)


@respx.mock
def test_login_basic():
    random_api_name = random_string()
    config = ArcsecondConfig(api_name=random_api_name)
    config.api_server = ARCSECOND_API_URL_DEV
    assert config.access_key == ""
    prepare_successful_login(config)
    ArcsecondAPI(config).login(TEST_LOGIN_USERNAME, access_key=TEST_API_KEY)
    assert config.access_key == TEST_API_KEY
    assert config.upload_key == ""


@respx.mock
def test_login_upload_key():
    random_api_name = random_string()
    config = ArcsecondConfig(api_name=random_api_name)
    config.api_server = ARCSECOND_API_URL_DEV
    prepare_successful_login(config)
    ArcsecondAPI(config).login(username=TEST_LOGIN_USERNAME, upload_key=TEST_UPLOAD_KEY)
    assert config.access_key == ""
    assert config.upload_key == TEST_UPLOAD_KEY
