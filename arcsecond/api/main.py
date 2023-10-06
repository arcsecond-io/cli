# -*- coding: utf-8 -*-

from typing import Optional

import click

from arcsecond.options import State
from .auth import AuthAPIEndPoint
from .config import Config
from .endpoint import APIEndPoint
from .error import ArcsecondNotLoggedInError
from .helpers import get_state

__all__ = ["ArcsecondAPI", ]


class ArcsecondAPI(object):
    def __init__(self, state=None, **kwargs):
        self.__state = get_state(state, **kwargs)
        self.config = Config(self.__state.config_section)
        if not self.config.is_logged_in:
            # Always require to be authenticated (-> one needs it to count API requests)
            raise ArcsecondNotLoggedInError()

        self.profiles = APIEndPoint('profiles', self.__state)
        self.profiles_accesskeys = APIEndPoint('profiles', self.__state, 'apikeys')
        self.profiles_uploadkeys = APIEndPoint('profiles', self.__state, 'uploadkeys')
        self.profiles_sharedkeys = APIEndPoint('profiles', self.__state, 'sharedkeys')

        self.organisations = APIEndPoint('organisations', self.__state)
        self.members = APIEndPoint('members', self.__state)

        self.observingsites = APIEndPoint('observingsites', self.__state)
        self.telescopes = APIEndPoint('telescopes', self.__state)
        self.nightlogs = APIEndPoint('nightlogs', self.__state)
        self.observations = APIEndPoint('observations', self.__state)
        self.calibrations = APIEndPoint('calibrations', self.__state)
        self.datapackages = APIEndPoint('datapackages', self.__state)
        self.datasets = APIEndPoint('datasets', self.__state)
        self.datafiles = APIEndPoint('datafiles', self.__state)

    def register(self, username, email, password1, password2):
        result, error = AuthAPIEndPoint(self.__state).register(username, email, password1, password2)
        if error and self.__state.verbose:
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
                config = Config(get_state(state).config_section)
                config.save(username=username)
        return result, error

    def fetch_access_key(self, state, username, auth_token):
        if state.verbose:
            click.echo('Fetching API Key...')
        # To get API key one must fetch it with Auth token obtained via login.
        endpoint = ProfileAPIKeyAPIEndPoint(state.make_new_silent())
        endpoint.use_headers({'Authorization': 'Token ' + auth_token})
        result, error = endpoint.read(username)
        if error and state.verbose:
            click.echo(click.style(error, fg='red'))
        elif result:
            config = Config(get_state(state).config_section)
            config.save(username=username)
            config.save_access_key(result.get('access_key', '') or result.get('api_key', ''))
            if state.verbose:
                click.echo('Successful API/Access key retrieval.')
        return result, error

    def fetch_upload_key(self, state, username, auth_token):
        if state.verbose:
            click.echo('Fetching Upload Key...')
        # To get API key one must fetch it with Auth token obtained via login.
        endpoint = ProfileUploadKeyAPIEndPoint(state.make_new_silent())
        endpoint.use_headers({'Authorization': 'Token ' + auth_token})
        result, error = endpoint.read(username)
        if error and state.verbose:
            click.echo(click.style(error, fg='red'))
        elif result:
            config = Config(get_state(state).config_section)
            config.save_upload_key(result.get('upload_key', ''))
            if state.verbose:
                click.echo('Successful Upload key retrieval.')
        return result, error

    @classmethod
    def is_logged_in(cls, state: Optional[State] = None) -> bool:
        return Config(get_state(state).config_section).is_logged_in

    @classmethod
    def username(cls, state: Optional[State] = None) -> str:
        return Config(get_state(state).config_section).username

    @classmethod
    def get_api_name(cls, state: Optional[State] = None) -> str:
        return Config(get_state(state).config_section).access_key or ''

    @classmethod
    def set_api_name(cls, address: str, state: Optional[State] = None) -> None:
        config = Config(get_state(state).config_section)
        config.save(api_server=address)

    @classmethod
    def access_key(cls, state: Optional[State] = None) -> str:
        return Config(get_state(state).config_section).access_key

    @classmethod
    def upload_key(cls, state: Optional[State] = None) -> str:
        return Config(get_state(state).config_section).upload_key

    @classmethod
    def clear_api_key(cls, state: Optional[State] = None) -> None:
        Config(get_state(state).config_section).clear_access_key()

    @classmethod
    def clear_upload_key(cls, state: Optional[State] = None) -> None:
        Config(get_state(state).config_section).clear_upload_key()
