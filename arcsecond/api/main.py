# -*- coding: utf-8 -*-
from typing import Optional

import click

from arcsecond.options import State

from .config import ArcsecondConfig
from .constants import API_AUTH_PATH_VERIFY
from .endpoint import ArcsecondAPIEndpoint

__all__ = [
    "ArcsecondAPI",
]


class ArcsecondAPI(object):
    def __init__(self, config: ArcsecondConfig, subdomain: str = ""):

        self.config = config
        self.subdomain = subdomain

        self.profiles = ArcsecondAPIEndpoint(self.config, "profiles", self.subdomain)

        self.organisations = ArcsecondAPIEndpoint(
            self.config, "organisations"
        )  # never subdomain here
        self.members = ArcsecondAPIEndpoint(self.config, "members", self.subdomain)

        self.observingsites = ArcsecondAPIEndpoint(
            self.config, "observingsites", self.subdomain
        )
        self.telescopes = ArcsecondAPIEndpoint(
            self.config, "telescopes", self.subdomain
        )
        self.nightlogs = ArcsecondAPIEndpoint(self.config, "nightlogs", self.subdomain)
        self.observations = ArcsecondAPIEndpoint(
            self.config, "observations", self.subdomain
        )
        self.calibrations = ArcsecondAPIEndpoint(
            self.config, "calibrations", self.subdomain
        )

        self.datapackages = ArcsecondAPIEndpoint(
            self.config, "datapackages", self.subdomain
        )
        self.datasets = ArcsecondAPIEndpoint(self.config, "datasets", self.subdomain)
        self.datafiles = ArcsecondAPIEndpoint(self.config, "datafiles", self.subdomain)

        self.allskycameras = ArcsecondAPIEndpoint(
            self.config, "allskycameras", self.subdomain
        )

    def login(self, username, access_key=None, upload_key=None):
        assert access_key or upload_key
        assert not (access_key and upload_key)

        endpoint = ArcsecondAPIEndpoint(self.config, API_AUTH_PATH_VERIFY)
        _, error = endpoint.create(
            json={"username": username, "key": access_key or upload_key}
        )
        if error:
            click.echo(click.style(error, fg="red"))
            return None, error

        key_name = "access_key" if access_key else "upload_key"
        key_value = access_key if access_key else upload_key
        self.config.save(**{key_name: key_value, "username": username})

        if self.config.verbose:
            click.echo("Login successful (Access Key has been saved).")

        return True, None

    def fetch_email(self):
        return self.email.read(self.config.username)

    def fetch_full_profile(self):
        return self.profiles.read(self.config.username)

    @classmethod
    def is_logged_in(cls, state: Optional[State] = None) -> bool:
        return ArcsecondConfig.from_state(state).is_logged_in

    @classmethod
    def get_username(cls, state: Optional[State] = None) -> str:
        return ArcsecondConfig.from_state(state).username
