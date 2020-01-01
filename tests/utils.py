import json

import httpretty
from arcsecond.api.constants import API_AUTH_PATH_LOGIN, ARCSECOND_API_URL_DEV
from arcsecond import cli

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
