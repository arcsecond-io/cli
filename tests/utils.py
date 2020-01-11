import json

import httpretty

from arcsecond import cli
from arcsecond.api.constants import API_AUTH_PATH_LOGIN, ARCSECOND_API_URL_DEV
from arcsecond.config import (config_file_clear_section,
                              config_file_save_api_key,
                              config_file_save_organisation_membership)

TEST_LOGIN_USERNAME = 'robot1'
TEST_LOGIN_PASSWORD = 'robotpass'
TEST_API_KEY = '935e2b9e24c44581b4ef5f4c8e53213e'


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


def register_successful_personal_login(runner):
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


def register_successful_organisation_login(runner, subdomain, role):
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
    httpretty.register_uri(
        httpretty.GET,
        ARCSECOND_API_URL_DEV + '/profiles/' + TEST_LOGIN_USERNAME + '/',
        status=200,
        body=make_profile_json(subdomain, role)
    )
    runner.invoke(cli.login, ['--organisation', subdomain, '-d'],
                  input=TEST_LOGIN_USERNAME + '\n' + TEST_LOGIN_PASSWORD)


def save_test_credentials(username, memberships=None):
    if memberships is None:
        memberships = dict()
    config_file_save_api_key(TEST_API_KEY, username, section='test')
    for k, v in memberships.items():
        config_file_save_organisation_membership(k, v, 'test')


def clear_test_credentials():
    config_file_clear_section('test')


def mock_url_path(method, path, body='', query='', status=200):
    path = path + '/' if path[-1] != '/' else path
    httpretty.register_uri(method, ARCSECOND_API_URL_DEV + path + query, status=status, body=body)


def mock_http_get(path, body='{}', status=200):
    mock_url_path(httpretty.GET, path, body, status=status)


def mock_http_post(path, body='{}', status=200):
    mock_url_path(httpretty.POST, path, body, status=status)
