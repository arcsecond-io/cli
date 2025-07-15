import json

import responses

from arcsecond import ArcsecondConfig
from arcsecond.api.constants import (
    API_AUTH_PATH_VERIFY,
    API_AUTH_PATH_VERIFY_PORTAL,
    ARCSECOND_API_URL_DEV,
)
from arcsecond.options import State

TEST_LOGIN_USERNAME = "robot1"
TEST_API_KEY = "4c4458935e2b9e21b4ef5f4c8e53213e"
TEST_UPLOAD_KEY = "b4ef5f4c8e53213e935e2b9e24c44581"


def make_profile(subdomain, role):
    return {
        "pk": 1,
        "first_name": "robot1",
        "last_name": "robot1",
        "username": "robot1",
        "email": "robot1@arcsecond.io",
        "membership_date": "2019-10-01T06:08:24.063186Z",
        "memberships": [
            {
                "pk": 1,
                "date_joined": "2019-10-02",
                "role": role,
                "organisation": {"pk": 1, "name": "Org Name", "subdomain": subdomain},
            }
        ],
    }


def make_profile_json(subdomain, role):
    return json.dumps(make_profile(subdomain, role))


def prepare_successful_login(org_subdomain=""):
    config = ArcsecondConfig(State(api_name="test"))
    config.api_server = ARCSECOND_API_URL_DEV
    responses.post(
        "/".join([ARCSECOND_API_URL_DEV, API_AUTH_PATH_VERIFY]) + "/",
        status=204,
    )
    if org_subdomain:
        responses.post(
            "/".join([ARCSECOND_API_URL_DEV, API_AUTH_PATH_VERIFY_PORTAL]) + "/",
            status=204,
        )


def prepare_upload_files(dataset_uuid, telescope_uuid, org_subdomain=""):
    responses.get(
        "/".join(
            [
                part
                for part in [
                    ARCSECOND_API_URL_DEV,
                    org_subdomain,
                    "datasets",
                    dataset_uuid,
                ]
                if part
            ]
        )
        + "/",
        status=200,
        json={"uuid": dataset_uuid, "name": "dummy dataset"},
    )
    responses.get(
        "/".join(
            [
                part
                for part in [
                    ARCSECOND_API_URL_DEV,
                    org_subdomain,
                    "telescopes",
                    telescope_uuid,
                ]
                if part
            ]
        )
        + "/",
        status=200,
        json={"uuid": telescope_uuid, "name": "dummy telescope"},
    )
    if org_subdomain:
        responses.get(
            "/".join([ARCSECOND_API_URL_DEV, "organisations", org_subdomain]) + "/",
            status=200,
            json={"subdomain": org_subdomain, "name": "dummy org"},
        )


def prepare_upload_allskyimage(camera_uuid, org_subdomain=""):
    responses.get(
        "/".join(
            [
                part
                for part in [
                    ARCSECOND_API_URL_DEV,
                    org_subdomain,
                    "allskycameras",
                    camera_uuid,
                ]
                if part
            ]
        )
        + "/",
        status=201,
        json={"status": "success", "uuid": camera_uuid},
    )
    if org_subdomain:
        responses.get(
            "/".join([ARCSECOND_API_URL_DEV, "organisations", org_subdomain]) + "/",
            status=200,
            json={"subdomain": org_subdomain, "name": "dummy org"},
        )


def save_test_credentials(username, memberships=None):
    config = ArcsecondConfig(State(api_name="test"))
    config.save(username=username)
    config.save_access_key(TEST_API_KEY)
    if memberships:
        config.save_memberships(memberships)


def clear_test_credentials():
    config = ArcsecondConfig(State(api_name="test"))
    config.reset()


def mock_url_path(method, path, body="", query="", status=200):
    responses.add(
        responses.Response(
            method=method,
            url="/".join([ARCSECOND_API_URL_DEV, path]) + query,
            status=status,
            body=body,
            match_querystring=True,
        )
    )


def mock_http_get(path, body="{}", status=200):
    mock_url_path("GET", path, body, status=status)


def mock_http_post(path, body="{}", status=201):
    mock_url_path("POST", path, body, status=status)


def mock_http_patch(path, body="{}", status=200):
    mock_url_path("PATCH", path, body, status=status)
