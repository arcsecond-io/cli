# -*- coding: utf-8 -*-

import click

from .auth import AuthAPIEndpoint
from .config import ArcsecondConfig
from .endpoint import ArcsecondAPIEndpoint

__all__ = ["ArcsecondAPI", ]


class ArcsecondAPI(object):
    def __init__(self, config: ArcsecondConfig, subdomain: str = ''):
        self.config = config
        self.subdomain = subdomain

        self.profiles = ArcsecondAPIEndpoint(self.config, 'profiles', self.subdomain)

        self.sharedkeys = ArcsecondAPIEndpoint(self.config, 'profiles', subresource='sharedkeys')
        self.private_observingsites = ArcsecondAPIEndpoint(self.config, 'profiles', subresource='observingsites')
        self.private_telescopes = ArcsecondAPIEndpoint(self.config, 'profiles', subresource='telescopes')

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
        # never subdomain here
        result, error = AuthAPIEndpoint(self.config, 'auth') \
            .register(username, email, password1, password2)

        if error and self.config.verbose:
            click.echo(click.style(error, fg='red'))

        return result, error

    def login(self, username, password, **kwargs):
        # never subdomain here
        result, error = AuthAPIEndpoint(self.config, 'auth') \
            .login(username, password)

        if error:
            click.echo(click.style(error, fg='red'))
            return

        auth_token = result['token']
        profile, profile_error = self.profiles.read(username, headers={'Authorization': 'Token ' + auth_token})
        if profile_error:
            click.echo(click.style(profile_error, fg='red'))
            return

        # Update username with that of returned profile in case we logged in with email address.
        self.config.save(username=profile.get('username', username))
        # Save memberships for future use (in Oort for instance).
        self.config.save_memberships(profile.get('memberships'))

        subresource = 'uploadkey' if kwargs.get('upload_key', False) else 'apikey'
        endpoint = ArcsecondAPIEndpoint(self.config, 'profiles', subresource=subresource)  # never subdomain here
        key_data, key_error = endpoint.read(self.config.username, headers={'Authorization': 'Token ' + auth_token})
        if key_error:
            click.echo(click.style(key_error, fg='red'))

        key_name = 'upload_key' if kwargs.get('upload_key', False) else 'access_key'
        key_value_name = 'upload_key' if kwargs.get('upload_key', False) else 'api_key'  # will change to access_key
        self.config.save(**{key_name: key_data.get(key_value_name, '')})

        if self.config.verbose:
            click.echo(f'Successful {key_name} key retrieval.')
