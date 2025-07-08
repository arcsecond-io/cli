import json

import responses

from arcsecond import cli, ArcsecondConfig
from arcsecond.api.constants import API_AUTH_PATH_VERIFY, ARCSECOND_API_URL_DEV
from arcsecond.options import State

TEST_LOGIN_USERNAME = 'robot1'
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
    config = ArcsecondConfig(State(api_name='test'))
    config.api_server = ARCSECOND_API_URL_DEV
    responses.post(
        '/'.join([ARCSECOND_API_URL_DEV, API_AUTH_PATH_VERIFY]) + '/',
        status=204,
    )


def make_successful_login(runner, subdomain='robotland', role='member'):
    prepare_successful_login(subdomain, role)
    result = runner.invoke(cli.login, ['--api', 'test'], input=TEST_LOGIN_USERNAME + '\n' + TEST_API_KEY + '\n\nY')
    assert result.exit_code == 0


def save_test_credentials(username, memberships=None):
    config = ArcsecondConfig(State(api_name='test'))
    config.save(username=username)
    config.save_access_key(TEST_API_KEY)
    if memberships:
        config.save_memberships(memberships)


def clear_test_credentials():
    config = ArcsecondConfig(State(api_name='test'))
    config.reset()


def mock_url_path(method, path, body='', query='', status=200):
    responses.add(
        responses.Response(
            method=method,
            url='/'.join([ARCSECOND_API_URL_DEV, path]) + query,
            status=status,
            body=body,
            match_querystring=True)
    )


def mock_http_get(path, body='{}', status=200):
    mock_url_path("GET", path, body, status=status)


def mock_http_post(path, body='{}', status=200):
    mock_url_path("POST", path, body, status=status)
