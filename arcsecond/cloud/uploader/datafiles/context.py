import uuid

import click

from arcsecond.api import ArcsecondAPIEndpoint
from arcsecond.cloud.uploader.context import BaseUploadContext

from .errors import (
    InvalidDatasetError,
    InvalidOrganisationDatasetError,
    InvalidOrganisationTelescopeError,
    InvalidTelescopeError,
    InvalidTelescopeInDatasetError,
    MissingTelescopeError,
)


class DatasetUploadContext(BaseUploadContext):
    """Upload context for dataset-based uploads (original functionality)"""

    def __init__(
        self,
        config,
        input_dataset_uuid_or_name,
        input_telescope_uuid=None,
        org_subdomain=None,
        is_raw_data=True,
        custom_tags=None,
    ):
        super().__init__(config, org_subdomain, custom_tags)
        # CLI returns a UUID instance if valid UUID, hence the str() call.
        self._input_dataset_uuid_or_name = str(input_dataset_uuid_or_name)
        self._input_telescope_uuid = (
            str(input_telescope_uuid) if input_telescope_uuid else None
        )
        self._should_update_dataset_with_telescope = False
        self._is_raw_data = True if is_raw_data is None else is_raw_data
        self._dataset = None
        self._telescope = None

    @property
    def upload_api_endpoint(self):
        return ArcsecondAPIEndpoint(self.config, "datafiles", self.subdomain)

    def _validate_input_dataset_uuid_or_name(self):
        endpoint = ArcsecondAPIEndpoint(self.config, "datasets", self.subdomain)
        try:
            uuid.UUID(self._input_dataset_uuid_or_name)
        except ValueError:
            click.echo(
                f" • Looking for a dataset with name {self._input_dataset_uuid_or_name}..."
            )
            datasets_list, error = endpoint.list(
                **{"name": self._input_dataset_uuid_or_name}
            )
            if len(datasets_list) == 0:
                click.echo(
                    f" • No dataset with name {self._input_dataset_uuid_or_name} found. It will be created."
                )
                self._dataset = {"name": self._input_dataset_uuid_or_name}
            elif len(datasets_list) == 1:
                click.echo(
                    f" • One dataset with name {self._input_dataset_uuid_or_name}. Data will be appended to it."
                )
                self._dataset = datasets_list[0]
            else:
                error = f"Multiple datasets with name {self._input_dataset_uuid_or_name} found. Be more specific."
        else:
            click.echo(
                f" • Fetching details of dataset {self._input_dataset_uuid_or_name}..."
            )
            self._dataset, error = endpoint.read(str(self._input_dataset_uuid_or_name))

        if error is not None:
            if self._subdomain:
                raise InvalidOrganisationDatasetError(
                    str(self._input_dataset_uuid_or_name), self._subdomain, str(error)
                )
            else:
                raise InvalidDatasetError(
                    str(self._input_dataset_uuid_or_name), str(error)
                )

    def _validate_input_telescope_uuid(self):
        click.echo(
            f" • Looking for a telescope with UUID {self._input_telescope_uuid}..."
        )
        endpoint = ArcsecondAPIEndpoint(self.config, "telescopes", self.subdomain)
        self._telescope, error = endpoint.read(self._input_telescope_uuid)

        if error is not None:
            if self._subdomain:
                raise InvalidOrganisationTelescopeError(
                    self._input_telescope_uuid, self._subdomain, str(error)
                )
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
            dataset_telescope_uuid = self._dataset.get("telescope", None)
            # If we have already a telescope, this is OK and no need to go further.
            if dataset_telescope_uuid is None:
                self._raise_missing_telescope_in_existing_dataset()

        elif self.dataset_uuid and self.telescope_uuid:
            dataset_telescope_uuid = self._dataset.get("telescope", None)
            if dataset_telescope_uuid is None:
                msg = (
                    f" • Dataset '{self.dataset_uuid}' has no attached Telescope yet. "
                )
                click.echo(msg)
                self._should_update_dataset_with_telescope = True

            elif (
                dataset_telescope_uuid is not None
                and dataset_telescope_uuid != self.telescope_uuid
            ):
                raise InvalidTelescopeInDatasetError(
                    str(self._input_telescope_uuid),
                    dataset_telescope_uuid,
                    self.dataset_uuid,
                )

    def _validate_context_specific(self):
        """Run validations specific to dataset uploads"""
        self._validate_input_dataset_uuid_or_name()
        if self._input_telescope_uuid:
            self._validate_input_telescope_uuid()
        # Forcing Telescope validation and association with Dataset.
        self._validate_telescope_in_dataset()

    @property
    def dataset_uuid(self):
        return self._dataset.get("uuid", "") if self._dataset else ""

    @property
    def dataset_name(self):
        return self._dataset.get("name", "") if self._dataset else ""

    def update_dataset(self, dataset):
        self._dataset = dataset

    @property
    def telescope_uuid(self):
        return (
            self._telescope.get("uuid", "")
            if self._telescope
            else self._input_telescope_uuid
        )

    @property
    def telescope(self):
        return self._telescope if self._telescope else None

    @property
    def is_raw_data(self):
        return self._is_raw_data
