import os

from arcsecond.cloud.uploader.errors import UploadRemoteFileMetadataError
from arcsecond.cloud.uploader.uploader import BaseFileUploader
from arcsecond.cloud.uploader.utils import get_upload_progress_printer
from .errors import UploadRemoteDatasetPreparationError


class DatasetFileUploader(BaseFileUploader):
    """Uploader for files in a dataset context"""

    def _prepare_upload(self):
        """Prepare dataset for upload"""
        self._logger.info(f'{self.log_prefix} Preparing dataset...')

        # If we have a dataset name, check if it exists, if not create it.
        if not self._context.dataset_uuid:
            dataset_name = self._context.dataset_name
            data = {'name': dataset_name}
            if self._context.telescope_uuid:
                data['telescope'] = self._context.telescope_uuid

            self._logger.info(f'{self.log_prefix} Creating dataset with name {dataset_name}...')
            dataset, error = self._api.datasets.create(data=data)

            if error:
                error_msg = f'Dataset {dataset_name} could not be created: {error}'
                self._logger.error(error_msg)
                raise UploadRemoteDatasetPreparationError(error_msg)

            self._context.update_dataset(dataset)
            self._logger.info(f'{self.log_prefix} Dataset created with UUID {self._context.dataset_uuid}')

    def _get_upload_data(self):
        """Get upload data for dataset files"""
        from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor

        relative_path = self._file_path.relative_to(self._walking_root)
        filename = os.path.basename(self._file_path)

        # Create fields dictionary for MultipartEncoder
        fields = {
            'file': (filename, open(self._file_path, 'rb'), 'application/octet-stream'),
            'dataset': self._context.dataset_uuid,
        }

        # Create MultipartEncoder
        e = MultipartEncoder(fields=fields)

        # Create progress monitor if display_progress is True
        if self._display_progress:
            callback = get_upload_progress_printer(self._file_size)
            # Wrap MultipartEncoder with MultipartEncoderMonitor for progress tracking
            e = MultipartEncoderMonitor(e, callback)

        return e

    def _update_metadata(self, is_raw=None, custom_tags=None):
        """Update file metadata after upload"""
        if not self._uploaded_file_uuid:
            self._logger.warning(f'{self.log_prefix} No UUID found for uploaded file. Skipping metadata update.')
            return

        # Determine final is_raw value
        is_raw_value = is_raw if is_raw is not None else self._context.is_raw_data

        # Determine final custom tags
        final_tags = custom_tags if custom_tags is not None else self._context.custom_tags

        # Build metadata
        metadata = {}
        if is_raw_value is not None:
            metadata['isRaw'] = is_raw_value

        if final_tags:
            metadata['customTags'] = final_tags

        # Update metadata
        if metadata:
            self._logger.info(f'{self.log_prefix} Updating file metadata: {metadata}')
            response, error = self._api.datafiles.update(self._uploaded_file_uuid, metadata)

            if error:
                error_msg = f'Failed to update file metadata: {error}'
                self._logger.error(error_msg)
                raise UploadRemoteFileMetadataError(error_msg)
