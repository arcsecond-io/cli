# -*- coding: utf-8 -*-

import click

from .auth import AuthAPIEndPoint
from .config import ArcsecondConfig
from .endpoint import ArcsecondAPIEndpoint

__all__ = ["ArcsecondAPI", ]


class ArcsecondAPI(object):
    def __init__(self, config: ArcsecondConfig, subdomain: str = ''):
        self.config = config
        self.subdomain = subdomain

        self.profiles = ArcsecondAPIEndpoint(self.config, 'profiles', self.subdomain)
        self.profiles_sharedkeys = ArcsecondAPIEndpoint(self.config,
                                                        'profiles',
                                                        subdomain=self.subdomain,
                                                        subresource='sharedkeys')

        self.organisations = ArcsecondAPIEndpoint(self.config, 'organisations')  # never subdomain here
        self.members = ArcsecondAPIEndpoint(self.config, 'members', self.subdomain)

        self.observingsites = ArcsecondAPIEndpoint(self.config, 'observingsites', self.subdomain)
        self.telescopes = ArcsecondAPIEndpoint(self.config, 'telescopes', self.subdomain)
        self.nightlogs = ArcsecondAPIEndpoint(self.config, 'nightlogs', self.subdomain)
        self.observations = ArcsecondAPIEndpoint(self.config, 'observations', self.subdomain)
        self.calibrations = ArcsecondAPIEndpoint(self.config, 'calibrations', self.subdomain)
        self.datapackages = ArcsecondAPIEndpoint(self.config, 'datapackages', self.subdomain)
        self.datasets = ArcsecondAPIEndpoint(self.config, 'datasets', self.subdomain)
        self.datafiles = ArcsecondAPIEndpoint(self.config, 'datafiles', self.subdomain)

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
        # Save memberships for future use (in Oort for instance).
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
