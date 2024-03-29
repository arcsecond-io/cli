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

        if kwargs.get('api_key', False) or kwargs.get('access_key', False):
            endpoint = ArcsecondAPIEndpoint(self.config, 'profiles', subresource='apikey')  # never subdomain here
            key_data, key_error = endpoint.read(self.config.username, headers={'Authorization': 'Token ' + auth_token})
            if key_error:
                click.echo(click.style(key_error, fg='red'))
                return

            self.config.save(**{'api_key': key_data.get('api_key', '') or key_data.get('access_key', '')})
            self.config.save(**{'access_key': key_data.get('api_key', '') or key_data.get('access_key', '')})
            if self.config.verbose:
                click.echo(f'Successful access_key retrieval.')

        if kwargs.get('upload_key', False):
            endpoint = ArcsecondAPIEndpoint(self.config, 'profiles', subresource='uploadkey')  # never subdomain here
            key_data, key_error = endpoint.read(self.config.username, headers={'Authorization': 'Token ' + auth_token})
            if key_error:
                click.echo(click.style(key_error, fg='red'))
                return

            self.config.save(**{'upload_key': key_data.get('upload_key', '')})
            if self.config.verbose:
                click.echo(f'Successful upload_key retrieval.')
