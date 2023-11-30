# -*- coding: utf-8 -*-

from typing import Optional

import click

from arcsecond.options import State
from .auth import AuthAPIEndPoint
from .config import Config
from .endpoint import APIEndPoint

__all__ = ["ArcsecondAPI", ]


class ArcsecondAPI(object):
    def __init__(self, state=None):
        self.config = Config(state)

        self.profiles = APIEndPoint('profiles', self.config)
        self.profiles_accesskeys = APIEndPoint('profiles', self.config, 'apikeys')
        self.profiles_uploadkeys = APIEndPoint('profiles', self.config, 'uploadkeys')
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
        result, error = AuthAPIEndPoint(self.config).register(username, email, password1, password2)
        if error and self.config.verbose:
            click.echo(click.style(error, fg='red'))
        return result, error

    def login(self, username, password, state=None, **kwargs):
        state = get_state(state, **kwargs)
        result, error = AuthAPIEndPoint(state).login(username, password)
        if error and state.verbose:
            click.echo(click.style(error, fg='red'))
        elif result:
            auth_token = result['token']
            self.profiles.use_headers({'Authorization': 'Token ' + auth_token})
            profile, profile_error = self.profiles.read(username)
            if error:
                click.echo(click.style(profile_error, fg='red'))
            else:
                # Update username with that of returned profile in case we logged in with email address.
                username = profile.get('username', username)
                self.config.save(username=username)
        return result, error

    def fetch_access_key(self):
        if self.config.verbose:
            click.echo('Fetching API Key...')
        result, error = self.profiles_accesskeys.read(self.config.username)
        if error and self.config.verbose:
            click.echo(click.style(error, fg='red'))
        elif result:
            self.config.save(username=self.config.username)
            self.config.save_access_key(result.get('access_key', '') or result.get('api_key', ''))
            if self.config.verbose:
                click.echo('Successful API/Access key retrieval.')
        return result, error

    def fetch_upload_key(self):
        if self.config.verbose:
            click.echo('Fetching Upload Key...')
        result, error = self.profiles_uploadkeys.read(self.config.username)
        if error and self.config.verbose:
            click.echo(click.style(error, fg='red'))
        elif result:
            self.config.save(username=self.config.username)
            self.config.save_upload_key(result.get('upload_key', ''))
            if self.config.verbose:
                click.echo('Successful Upload key retrieval.')
        return result, error

    def fetch_full_profile(self):
        return self.profiles.read(self.config.username)

    @classmethod
    def is_logged_in(cls, state: Optional[State] = None) -> bool:
        return Config(state or State()).is_logged_in

    @classmethod
    def username(cls, state: Optional[State] = None) -> str:
        return Config(state or State()).username

    @classmethod
    def get_api_name(cls, state: Optional[State] = None) -> str:
        return Config(state or State()).api_server or ''

    @classmethod
    def set_api_name(cls, address: str, state: Optional[State] = None) -> None:
        config = Config(state or State())
        config.save(api_server=address)

    @classmethod
    def access_key(cls, state: Optional[State] = None) -> str:
        return Config(state or State()).access_key

    @classmethod
    def upload_key(cls, state: Optional[State] = None) -> str:
        return Config(state or State()).upload_key

    @classmethod
    def clear_access_key(cls, state: Optional[State] = None) -> None:
        Config(state or State()).clear_access_key()

    @classmethod
    def clear_upload_key(cls, state: Optional[State] = None) -> None:
        Config(state or State()).clear_upload_key()
