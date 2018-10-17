import httpretty
from arcsecond.api.constants import API_AUTH_PATH_LOGIN, ARCSECOND_API_URL_DEV
from arcsecond import cli

TEST_LOGIN_USERNAME = 'robot1'
TEST_LOGIN_PASSWORD = 'robotpass'
TEST_API_KEY = '935e2b9e24c44581b4ef5f4c8e53213e'


def register_successful_login(runner):
    httpretty.register_uri(
        httpretty.POST,
        ARCSECOND_API_URL_DEV + API_AUTH_PATH_LOGIN,
        status=200,
        body='{ "key": "935e2b9e24c44581b4ef5f4c8e53213e935e2b9e24c44581b4ef5f4c8e53213e" }'
    )
    httpretty.register_uri(
        httpretty.GET,
        ARCSECOND_API_URL_DEV + '/profiles/' + TEST_LOGIN_USERNAME + '/keys/',
        status=200,
        body='{ "api_key": "' + TEST_API_KEY + '" }'
    )
    runner.invoke(cli.login, ['-d'], input=TEST_LOGIN_USERNAME + '\n' + TEST_LOGIN_PASSWORD)
