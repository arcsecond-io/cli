# -*- coding: utf-8 -*-

from typing import Optional

import click

from arcsecond.options import State
from .auth import AuthAPIEndPoint
from .config import Config
from .endpoint import APIEndPoint

__all__ = ["ArcsecondAPI", ]


class ArcsecondAPI(object):
    def __init__(self, config: Config):
        self.config = config

        self.profiles = APIEndPoint('profiles', self.config)
        self.profiles_sharedkeys = APIEndPoint('profiles', self.config, 'sharedkeys')

        self.organisations = APIEndPoint('organisations', self.config)
        self.members = APIEndPoint('members', self.config)

        self.observingsites = APIEndPoint('observingsites', self.config)
        self.telescopes = APIEndPoint('telescopes', self.config)
        self.nightlogs = APIEndPoint('nightlogs', self.config)
        self.observations = APIEndPoint('observations', self.config)
        self.calibrations = APIEndPoint('calibrations', self.config)
        self.datapackages = APIEndPoint('datapackages', self.config)
        self.datasets = APIEndPoint('datasets', self.config)
        self.datafiles = APIEndPoint('datafiles', self.config)

    def register(self, username, email, password1, password2):
        result, error = AuthAPIEndPoint('auth', self.config).register(username, email, password1, password2)
        if error and self.config.verbose:
            click.echo(click.style(error, fg='red'))
        return result, error

    def login(self, username, password, **kwargs):
        result, error = AuthAPIEndPoint('auth', self.config).login(username, password)
        if error:
            click.echo(click.style(error, fg='red'))
            return

        auth_token = result['token']
        self.profiles.use_headers({'Authorization': 'Token ' + auth_token})
        profile, profile_error = self.profiles.read(username)
        if profile_error:
            click.echo(click.style(profile_error, fg='red'))
            return

        # Update username with that of returned profile in case we logged in with email address.
        self.config.save(username=profile.get('username', username))
        # Save memberships for furture use.
        self.config.save_memberships(profile.get('memberships'))

        endpoint = APIEndPoint('profiles', self.config, 'uploadkey' if kwargs.get('upload_key', False) else 'apikey')
        endpoint.use_headers({'Authorization': 'Token ' + auth_token})

        key_data, key_error = endpoint.read(self.config.username)
        if key_error:
            click.echo(click.style(key_error, fg='red'))

        key_name = 'upload_key' if kwargs.get('upload_key', False) else 'access_key'
        key_value_name = 'upload_key' if kwargs.get('upload_key', False) else 'api_key'  # will change to access_key
        self.config.save(**{key_name: key_data.get(key_value_name, '')})

        if self.config.verbose:
            click.echo(f'Successful {key_name} key retrieval.')

    def fetch_full_profile(self):
        return self.profiles.read(self.config.username)

    @classmethod
    def is_logged_in(cls, state: Optional[State] = None) -> bool:
        return Config(state).is_logged_in

    @classmethod
    def get_username(cls, state: Optional[State] = None) -> str:
        return Config(state).username

    @classmethod
    def get_api_name(cls, state: Optional[State] = None) -> str:
        return Config(state).api_server or ''

    @classmethod
    def set_api_name(cls, address: str, state: Optional[State] = None) -> None:
        Config(state).save(api_server=address)

    @classmethod
    def get_access_key(cls, state: Optional[State] = None) -> str:
        return Config(state).access_key

    @classmethod
    def get_upload_key(cls, state: Optional[State] = None) -> str:
        return Config(state).upload_key

    @classmethod
    def clear_access_key(cls, state: Optional[State] = None) -> None:
        Config(state).clear_access_key()

    @classmethod
    def clear_upload_key(cls, state: Optional[State] = None) -> None:
        Config(state).clear_upload_key()
