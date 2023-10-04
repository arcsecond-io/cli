import json

import httpretty

from arcsecond import cli
from arcsecond.api.constants import API_AUTH_PATH_LOGIN, ARCSECOND_API_URL_DEV
from arcsecond.config import (config_file_clear_section,
                              config_file_save_api_key,
                              config_file_save_api_server,
                              config_file_save_organisation_membership)

TEST_LOGIN_USERNAME = 'robot1'
TEST_LOGIN_PASSWORD = 'robotpass'
TEST_API_KEY = '4c4458935e2b9e21b4ef5f4c8e53213e'
TEST_UPLOAD_KEY = 'b4ef5f4c8e53213e935e2b9e24c44581'


def make_profile(subdomain, role):
    return {
        "pk": 1,
        "first_name": 'robot1',
        "last_name": 'robot1',
        "username": "robot1",
        "email": "robot1@arcsecond.io",
        "membership_date": "2019-10-01T06:08:24.063186Z",
        "memberships": [
            {
                "pk": 1,
                "date_joined": "2019-10-02",
                "role": role,
                "organisation": {
                    "pk": 1,
                    "name": "Org Name",
                    "subdomain": subdomain
                }
            }
        ]
    }


def make_profile_json(subdomain, role):
    return json.dumps(make_profile(subdomain, role))


def prepare_successful_login(subdomain='robotland', role='member'):
    config_file_save_api_server(ARCSECOND_API_URL_DEV, section='test')
    httpretty.register_uri(
        httpretty.POST,
        ARCSECOND_API_URL_DEV + API_AUTH_PATH_LOGIN,
        status=200,
        body='{ "token": "935e2b9e24c44581b4ef5f4c8e53213e" }'
    )
    httpretty.register_uri(
        httpretty.GET,
        ARCSECOND_API_URL_DEV + '/profiles/' + TEST_LOGIN_USERNAME + '/',
        status=200,
        body=make_profile_json(subdomain, role)
    )
    httpretty.register_uri(
        httpretty.GET,
        ARCSECOND_API_URL_DEV + '/profiles/' + TEST_LOGIN_USERNAME + '/apikey/',
        status=200,
        body='{ "access_key": "' + TEST_API_KEY + '" }'
    )
    httpretty.register_uri(
        httpretty.GET,
        ARCSECOND_API_URL_DEV + '/profiles/' + TEST_LOGIN_USERNAME + '/uploadkey/',
        status=200,
        body='{ "upload_key": "' + TEST_UPLOAD_KEY + '" }'
    )


def make_successful_login(runner, subdomain='robotland', role='member'):
    prepare_successful_login(subdomain, role)
    result = runner.invoke(cli.login, ['--api', 'test'], input=TEST_LOGIN_USERNAME + '\n' + TEST_LOGIN_PASSWORD + '\nY')
    assert result.exit_code == 0


def save_test_credentials(username, memberships=None):
    if memberships is None:
        memberships = dict()
    config_file_save_api_key(TEST_API_KEY, username, section='test')
    for k, v in memberships.items():
        config_file_save_organisation_membership(k, v, 'test')


def clear_test_credentials():
    config_file_clear_section('test')
    config_file_save_api_server(ARCSECOND_API_URL_DEV, section='test')


def mock_url_path(method, path, body='', query='', status=200):
    path = path + '/' if path[-1] != '/' else path
    httpretty.register_uri(method,
                           ARCSECOND_API_URL_DEV + path + query,
                           status=status,
                           body=body,
                           match_querystring=True)


def mock_http_get(path, body='{}', status=200):
    mock_url_path(httpretty.GET, path, body, status=status)


def mock_http_post(path, body='{}', status=200):
    mock_url_path(httpretty.POST, path, body, status=status)
