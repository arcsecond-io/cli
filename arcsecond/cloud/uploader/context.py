from abc import ABC, abstractmethod

import click

from arcsecond.api.constants import API_AUTH_PATH_VERIFY_PORTAL
from arcsecond.api.endpoint import ArcsecondAPIEndpoint
from arcsecond.api.main import ArcsecondAPI

from .errors import (
    InvalidAstronomerError,
    InvalidOrgMembershipError,
    InvalidWatchOptionsError,
    UnknownOrganisationError,
)


class BaseUploadContext(ABC):
    """Abstract base class for all upload contexts"""

    def __init__(self, config, org_subdomain=None, custom_tags=None):
        self._config = config
        self._subdomain = org_subdomain
        self._custom_tags = custom_tags
        self._is_validated = False

    @property
    def upload_api_endpoint(self):
        raise NotImplementedError()

    @property
    def is_validated(self):
        return self._is_validated

    @property
    def config(self):
        return self._config

    @property
    def subdomain(self):
        return self._subdomain

    @property
    def custom_tags(self):
        return self._custom_tags

    def validate(self):
        """Main validation method that runs all required validations"""
        self._validate_custom_tags(self._custom_tags)
        self._validate_local_astronomer_credentials()

        # Run context-specific validations
        self._validate_context_specific()

        if self._subdomain:
            self._validate_remote_organisation()
            self._validate_astronomer_role_in_remote_organisation()

        self._is_validated = True

    @abstractmethod
    def _validate_context_specific(self):
        """Implement context-specific validations in subclasses"""
        pass

    def _validate_custom_tags(self, tags=None):
        if tags is None:
            return
        if not isinstance(tags, list):
            raise TypeError("custom_tags must be a list")
        if not all(isinstance(t, str) for t in tags):
            raise TypeError("all custom_tags must be strings")
        if any(t.startswith("arcsecond") for t in tags):
            raise TypeError('none of custom_tags must start with "arcsecond"')

    def _validate_local_astronomer_credentials(self):
        username = self._config.username
        if not username:
            raise InvalidAstronomerError("Missing username")

        if not self._config.upload_key and not self._config.access_key:
            raise InvalidWatchOptionsError(
                "Missing upload_key (or access_key). Make sure to login first."
            )

    def _validate_remote_organisation(self):
        click.echo(f" • Fetching details of organisation {self._subdomain}...")
        _, error = ArcsecondAPI(self._config, self._subdomain).organisations.read(
            self._subdomain
        )
        if error is not None:
            raise UnknownOrganisationError(self._subdomain, str(error))

    def _validate_astronomer_role_in_remote_organisation(self):
        click.echo(" • Verifying organisation membership...")
        endpoint = ArcsecondAPIEndpoint(self.config, API_AUTH_PATH_VERIFY_PORTAL)
        _, error = endpoint.create(
            json={
                "username": self._config.username,
                "key": self._config.access_key or self._config.upload_key,
                "organisation": self._subdomain,
            }
        )
        if error:
            raise InvalidOrgMembershipError(self._subdomain)
