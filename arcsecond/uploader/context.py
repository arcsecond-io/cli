import uuid

import click

from arcsecond import ArcsecondAPI, ArcsecondConfig
from .errors import (
    UnknownOrganisationError,
    InvalidAstronomerError,
    InvalidWatchOptionsError,
    InvalidOrganisationDatasetError,
    InvalidDatasetError,
    InvalidOrgMembershipError
)


class Context(object):
    def __init__(self, config: ArcsecondConfig, dataset_uuid_or_name: str, subdomain: str):
        self._config = config
        self._dataset_uuid_or_name = dataset_uuid_or_name
        self._subdomain = subdomain
        self._dataset = None
        self._organisation = None
        self._api = ArcsecondAPI(config, subdomain)

    def validate(self):
        self._validate_local_astronomer_credentials()
        self._validate_dataset_uuid()
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

    def _validate_dataset_uuid(self):
        try:
            uuid.UUID(self._dataset_uuid_or_name)
        except ValueError:
            click.echo(f" • Looking for a dataset with name {self._dataset_uuid_or_name}...")
            datasets_list, error = self._api.datasets.list(**{'name': self._dataset_uuid_or_name})
            if len(datasets_list) == 0:
                click.echo(f" • No dataset with name {self._dataset_uuid_or_name} found. It will be created.")
                self._dataset = {'name': self._dataset_uuid_or_name}
            elif len(datasets_list) == 1:
                click.echo(f" • One dataset with name {self._dataset_uuid_or_name}. Data will be appended to it.")
                self._dataset = datasets_list[0]
            else:
                error = f"Multiple datasets with name {self._dataset_uuid_or_name} found. Be more specific."
        else:
            click.echo(f" • Fetching details of dataset {self._dataset_uuid_or_name}...")
            self._dataset, error = self._api.datasets.read(str(self._dataset_uuid_or_name))

        if error is not None:
            if self._subdomain:
                raise InvalidOrganisationDatasetError(str(self._dataset_uuid_or_name),
                                                      self._subdomain,
                                                      str(error))
            else:
                raise InvalidDatasetError(str(self._dataset_uuid_or_name), str(error))

    def _validate_remote_organisation(self):
        click.echo(f" • Fetching details of organisation {self._subdomain}...")
        self._organisation, error = self._api.organisations.read(self._subdomain)
        if error is not None:
            raise UnknownOrganisationError(self._subdomain, str(error))

    def _validate_astronomer_role_in_remote_organisation(self):
        role = self._config.read_key(self._subdomain)
        if not role or role not in ['member', 'admin', 'superadmin']:
            raise InvalidOrgMembershipError(self._subdomain)

    def update_dataset(self, dataset: dict):
        assert dataset != None
        self._dataset = dataset

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
    def organisation_subdomain(self):
        return self._organisation.get('subdomain', '') if self._organisation else ''

    # def __print_organisation_telescopes(org_subdomain: str, api: str = 'main'):
    #     click.echo(f" • Here is a list of existing telescopes for organisation '{org_subdomain}':")
    #     kwargs = build_endpoint_kwargs(api, org_subdomain)
    #     telescope_list, error = ArcsecondAPI.telescopes(**kwargs).list()
    #     for telescope in telescope_list:
    #         s = f" 🔭 {telescope['name']}"
    #         if telescope.get('alias', ''):
    #             s += f" a.k.a. {telescope['alias']}"
    #         s += f" ({telescope['uuid']})"
    #         click.echo(s)
