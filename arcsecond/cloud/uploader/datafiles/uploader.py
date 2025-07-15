import os

from arcsecond.cloud.uploader.errors import UploadRemoteFileMetadataError
from arcsecond.cloud.uploader.uploader import BaseFileUploader
from arcsecond.cloud.uploader.utils import get_upload_progress_printer
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
            dataset, error = self._context._api.datasets.create(data=data)

            if error:
                error_msg = f"Dataset {dataset_name} could not be created: {error}"
                self._logger.error(error_msg)
                raise UploadRemoteDatasetPreparationError(error_msg)

            self._context.update_dataset(dataset)
            self._logger.info(
                f"{self.log_prefix} Dataset created with UUID {self._context.dataset_uuid}"
            )

    def _get_upload_data_fields(self):
        filename = os.path.basename(self._file_path)
        # auto_cleanup_file = AutoCleanupFile(self._file_path)
        return {
            "file": (filename, open(self._file_path, "rb"), "application/octet-stream"),
            "dataset": self._context.dataset_uuid,
        }

    def _update_metadata(self, is_raw=None, custom_tags=None):
        """Update file metadata after upload"""
        if not self.uploaded_file_id:
            error_msg = f"{self.log_prefix} No ID found for uploaded file. Skipping metadata update."
            self._logger.error(error_msg)
            raise UploadRemoteFileMetadataError(error_msg)

        # Determine final is_raw value
        is_raw_value = is_raw if is_raw is not None else self._context.is_raw_data

        # Determine final custom tags
        final_tags = (
            custom_tags if custom_tags is not None else self._context.custom_tags
        )

        # Build metadata
        metadata = {}
        if is_raw_value is not None:
            metadata["is_raw"] = is_raw_value

        if final_tags:
            metadata["custom_tags"] = final_tags

        # Update metadata
        if metadata:
            self._logger.info(f"{self.log_prefix} Updating file metadata: {metadata}")
            response, error = self._api.datafiles.update(
                self.uploaded_file_id, metadata
            )

            if error:
                error_msg = f"{self.log_prefix} Failed to update file metadata: {error}"
                self._logger.error(error_msg)
                raise UploadRemoteFileMetadataError(error_msg)
