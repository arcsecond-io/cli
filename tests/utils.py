import json
import random
import string

import respx
from httpx import Response

from arcsecond import ArcsecondConfig
from arcsecond.api.constants import (
    API_AUTH_PATH_VERIFY,
    API_AUTH_PATH_VERIFY_PORTAL,
)

TEST_LOGIN_USERNAME = "robot1"
TEST_API_KEY = "4c4458935e2b9e21b4ef5f4c8e53213e"
TEST_UPLOAD_KEY = "b4ef5f4c8e53213e935e2b9e24c44581"


def random_string(n=10):
    # https://stackoverflow.com/questions/2257441/random-string-generation-with-upper-case-letters-and-digits-in-python
    return ''.join(random.choice(string.ascii_letters) for _ in range(n))


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


def prepare_successful_login(config, org_subdomain=""):
    respx.post(
        "/".join([config.api_server, API_AUTH_PATH_VERIFY]) + "/",
    ).mock(return_value=Response(204))
    if org_subdomain:
        respx.post(
            "/".join([config.api_server, API_AUTH_PATH_VERIFY_PORTAL]) + "/",
        ).mock(return_value=Response(204))


def prepare_upload_files(config, dataset_uuid, telescope_uuid, org_subdomain=""):
    respx.get(
        "/".join(
            [
                part
                for part in [
                config.api_server,
                org_subdomain,
                "datasets",
                dataset_uuid,
            ]
                if part
            ]
        )
        + "/",
    ).mock(return_value=Response(200, json={"uuid": dataset_uuid, "name": "dummy dataset"}))
    respx.get(
        "/".join(
            [
                part
                for part in [
                config.api_server,
                org_subdomain,
                "telescopes",
                telescope_uuid,
            ]
                if part
            ]
        )
        + "/"
    ).mock(return_value=Response(200, json={"uuid": telescope_uuid, "name": "dummy telescope"}))
    if org_subdomain:
        respx.get(
            "/".join([config.api_server, "organisations", org_subdomain]) + "/",
        ).mock(return_value=Response(200, json={"subdomain": org_subdomain, "name": "dummy org"}))


def prepare_upload_allskyimages(config, camera_uuid, org_subdomain=""):
    respx.get(
        "/".join(
            [
                part
                for part in [
                config.api_server,
                org_subdomain,
                "allskycameras",
                camera_uuid
            ]
                if part
            ]
        )
        + "/"
    ).mock(return_value=Response(201, json={"status": "success", "uuid": camera_uuid}))
    if org_subdomain:
        respx.get(
            "/".join([config.api_server, "organisations", org_subdomain]) + "/"
        ).mock(return_value=Response(200, json={"subdomain": org_subdomain, "name": "dummy org"},))


def save_test_credentials(api_name, username, memberships=None):
    config = ArcsecondConfig(api_name=api_name)
    config.save(username=username)
    config.save_access_key(TEST_API_KEY)
    if memberships:
        config.save_memberships(memberships)


def clear_test_credentials(api_name):
    config = ArcsecondConfig(api_name=api_name)
    config.reset()
