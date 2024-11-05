import uuid
from typing import Optional

import click

from arcsecond import ArcsecondAPI, ArcsecondConfig, ArcsecondAPIEndpoint
from arcsecond.api.constants import API_AUTH_PATH_VERIFY_PORTAL
from .errors import (
    UnknownOrganisationError,
    InvalidAstronomerError,
    InvalidWatchOptionsError,
    InvalidOrganisationDatasetError,
    InvalidDatasetError,
    InvalidOrgMembershipError,
    InvalidOrganisationTelescopeError,
    InvalidTelescopeError,
    InvalidTelescopeInDatasetError,
    MissingTelescopeError
)


class UploadContext(object):
    def __init__(self, config: ArcsecondConfig,
                 input_dataset_uuid_or_name: str,
                 input_telescope_uuid: Optional[str] = None,
                 org_subdomain: Optional[str] = None):
        self._config = config
        self._input_dataset_uuid_or_name = str(input_dataset_uuid_or_name)
        # CLI returns a UUID instance if valid UUID, hence the str() call.
        self._input_telescope_uuid = str(input_telescope_uuid) if input_telescope_uuid else None
        self._should_update_dataset_with_telescope = False
        self._subdomain = org_subdomain
        self._dataset = None
        self._telescope = None
        self._organisation = None
        self._api = ArcsecondAPI(config, org_subdomain)

    def validate(self):
        self._validate_local_astronomer_credentials()
        self._validate_input_dataset_uuid_or_name()
        if self._input_telescope_uuid:
            self._validate_input_telescope_uuid()
        # Forcing Telescope validation and association with Dataset.
        self._validate_telescope_in_dataset()
        if self._subdomain:
            self._validate_remote_organisation()
            self._validate_astronomer_role_in_remote_organisation()

    def _validate_local_astronomer_credentials(self):
        username = self._config.username
        if username is None:
            raise InvalidAstronomerError('Missing username')

        upload_key = self._config.upload_key
        if not upload_key:
            raise InvalidWatchOptionsError('Missing upload_key.')

    def _validate_input_dataset_uuid_or_name(self):
        try:
            uuid.UUID(self._input_dataset_uuid_or_name)
        except ValueError:
            click.echo(f" • Looking for a dataset with name {self._input_dataset_uuid_or_name}...")
            datasets_list, error = self._api.datasets.list(**{'name': self._input_dataset_uuid_or_name})
            if len(datasets_list) == 0:
                click.echo(f" • No dataset with name {self._input_dataset_uuid_or_name} found. It will be created.")
                self._dataset = {'name': self._input_dataset_uuid_or_name}
            elif len(datasets_list) == 1:
                click.echo(f" • One dataset with name {self._input_dataset_uuid_or_name}. Data will be appended to it.")
                self._dataset = datasets_list[0]
            else:
                error = f"Multiple datasets with name {self._input_dataset_uuid_or_name} found. Be more specific."
        else:
            click.echo(f" • Fetching details of dataset {self._input_dataset_uuid_or_name}...")
            self._dataset, error = self._api.datasets.read(str(self._input_dataset_uuid_or_name))

        if error is not None:
            if self._subdomain:
                raise InvalidOrganisationDatasetError(str(self._input_dataset_uuid_or_name),
                                                      self._subdomain,
                                                      str(error))
            else:
                raise InvalidDatasetError(str(self._input_dataset_uuid_or_name), str(error))

    def _validate_input_telescope_uuid(self):
        click.echo(f" • Looking for a telescope with UUID {self._input_telescope_uuid}...")
        self._telescope, error = self._api.telescopes.read(self._input_telescope_uuid)

        if error is not None:
            if self._subdomain:
                raise InvalidOrganisationTelescopeError(self._input_telescope_uuid,
                                                        self._subdomain,
                                                        str(error))
            else:
                raise InvalidTelescopeError(str(self._input_telescope_uuid), str(error))

    def _raise_missing_telescope_in_new_dataset(self):
        """The self.dataset_uuid is None, hence we have only a name, hence it is a new Dataset.
        Hence, we need a telescope, but none is provided."""
        error = "For new Datasets, we need a valid Telescope."
        raise MissingTelescopeError(self._input_dataset_uuid_or_name, error)

    def _raise_missing_telescope_in_existing_dataset(self):
        """The self.dataset_uuid is not None, hence we need a Telescope to be attached to it already."""
        error = "For existing Datasets, we need a valid Telescope. "
        error += "Open Dataset page to select a telescope, or provide one here with -t parameter."
        raise MissingTelescopeError(self._input_dataset_uuid_or_name, error)

    def _validate_telescope_in_dataset(self):
        if not self.dataset_uuid and not self.telescope_uuid:
            self._raise_missing_telescope_in_new_dataset()

        elif not self.dataset_uuid and self.telescope_uuid:
            self._should_update_dataset_with_telescope = True
            # We don't have an existing dataset, but we have a valid Telescope. No need to go further.

        elif self.dataset_uuid and not self.telescope_uuid:
            dataset_telescope_uuid = self._dataset.get('telescope', None)
            # If we have already a telescope, this is OK and no need to go further.
            if dataset_telescope_uuid is None:
                self._raise_missing_telescope_in_existing_dataset()

        elif self.dataset_uuid and self.telescope_uuid:
            dataset_telescope_uuid = self._dataset.get('telescope', None)
            if dataset_telescope_uuid is None:
                msg = f" • Dataset '{self.dataset_uuid}' has no attached Telescope yet. "
                msg += f"Telescope with UUID {self.telescope_uuid} will be attached to it upon upload."
                click.echo(msg)
                self._should_update_dataset_with_telescope = True

            elif dataset_telescope_uuid is not None and dataset_telescope_uuid != self.telescope_uuid:
                raise InvalidTelescopeInDatasetError(str(self._input_telescope_uuid),
                                                     dataset_telescope_uuid,
                                                     self.dataset_uuid)

    def _validate_remote_organisation(self):
        click.echo(f" • Fetching details of organisation {self._subdomain}...")
        self._organisation, error = self._api.organisations.read(self._subdomain)
        if error is not None:
            raise UnknownOrganisationError(self._subdomain, str(error))

    def _validate_astronomer_role_in_remote_organisation(self):
        endpoint = ArcsecondAPIEndpoint(self.config, API_AUTH_PATH_VERIFY_PORTAL)
        result, error = endpoint.create({'username': self._config.username,
                                         'key': self._config.access_key or self._config.upload_key,
                                         'organisation': self._subdomain})
        if error:
            raise InvalidOrgMembershipError(self._subdomain)

    @property
    def config(self):
        return self._config

    @property
    def dataset_uuid(self):
        return self._dataset.get('uuid', '')

    @property
    def dataset_name(self):
        return self._dataset.get('name', '')

    @property
    def telescope_uuid(self):
        return self._telescope.get('uuid', '')

    @property
    def telescope(self):
        return self._telescope if self._telescope else None

    @property
    def organisation_subdomain(self):
        return self._organisation.get('subdomain', '') if self._organisation else ''
