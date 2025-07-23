from arcsecond.api import ArcsecondAPIEndpoint
from arcsecond.cloud.uploader.uploader import BaseFileUploader

from .context import DatasetUploadContext
from .errors import UploadRemoteDatasetPreparationError


class DatasetFileUploader(BaseFileUploader[DatasetUploadContext]):
    """Uploader for files in a dataset context"""

    def _prepare_upload(self):
        """Prepare dataset for upload"""
        self._logger.info(f"{self.log_prefix} Preparing dataset...")

        # If we have a dataset name, check if it exists, if not create it.
        if not self._context.dataset_uuid:
            dataset_name = self._context.dataset_name
            data = {"name": dataset_name}
            if self._context.telescope_uuid:
                data["telescope"] = self._context.telescope_uuid

            self._logger.info(
                f"{self.log_prefix} Creating dataset with name {dataset_name}..."
            )
            endpoint = ArcsecondAPIEndpoint(
                self._context.config, "datasets", self._context.subdomain
            )
            dataset, error = endpoint.create(json=data)

            if error:
                error_msg = f"Dataset {dataset_name} could not be created: {error}"
                self._logger.error(error_msg)
                raise UploadRemoteDatasetPreparationError(error_msg)

            self._context.update_dataset(dataset)
            self._logger.info(
                f"{self.log_prefix} Dataset created with UUID {self._context.dataset_uuid}"
            )

    def _get_upload_data(self, **kwargs):
        fields = {
            "dataset": self._context.dataset_uuid,
            "is_raw": str(self._context.is_raw_data),
        }
        if self._context.custom_tags and len(self._context.custom_tags) > 0:
            raw_tags = (
                self._context.custom_tags
                if isinstance(self._context.custom_tags, list)
                else self._context.custom_tags.split(",")
            )
            tags = [t.strip() for t in raw_tags if len(t.strip()) > 0]
            fields["tags"] = ",".join(tags)
        clean_kwargs = {
            k: kwargs[k] for k in ("is_raw", "tags", "dataset") if k in kwargs
        }
        if "tags" in clean_kwargs and not clean_kwargs["tags"]:
            # Tags must really be provided only when non-blank/null/empty
            del clean_kwargs["tags"]
        fields.update(**clean_kwargs)
        return fields
