# -*- coding: utf-8 -*-

import click

from .config import ArcsecondConfig
from .constants import API_AUTH_PATH_VERIFY
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

    def login(self, username, access_key=None, upload_key=None):
        assert access_key or upload_key
        assert not (access_key and upload_key)

        endpoint = ArcsecondAPIEndpoint(self.config, API_AUTH_PATH_VERIFY)
        result, error = endpoint.create({'username': username, 'key': access_key or upload_key})
        if error:
            click.echo(click.style(error, fg='red'))
            return None, error

        key_name = 'access_key' if access_key else 'upload_key'
        key_value = access_key if access_key else upload_key
        self.config.save(**{key_name: key_value, 'username': username})

        if self.config.verbose:
            click.echo('Login successful (Access Key has been saved).')

        return True, None
