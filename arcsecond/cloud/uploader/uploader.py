import os
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from .constants import Status, Substatus
from .errors import (
    UploadRemoteFileError,
    UploadRemoteFileInvalidatedContextError,
    UploadRemoteFileMetadataError
)
from .logger import get_logger


class BaseFileUploader(ABC):
    """Abstract base class for file uploaders"""

    def __init__(self, context, walking_root, file_path, display_progress=False):
        self._context = context
        self._walking_root = Path(walking_root)
        self._file_path = Path(file_path)
        self._display_progress = display_progress

        self._logger = get_logger()
        self._status = [Status.NEW, Substatus.PENDING, None]
        self._started = None
        self._file_size = os.path.getsize(file_path)

    @property
    def log_prefix(self):
        """Generate a log prefix for this file"""
        return f'File {self._file_path.name}:'

    def upload_file(self, **kwargs):
        """Generic upload method that orchestrates the upload process"""
        if self._context.is_validated is False:
            raise UploadRemoteFileInvalidatedContextError()

        self._logger.info(f'{self.log_prefix} Opening upload sequence.')

        # Pre-upload preparation (different for each context type)
        try:
            self._prepare_upload()
        except Exception:
            # Just try again
            time.sleep(1)
            self._prepare_upload()

        # Perform the actual upload (common to all types)
        try:
            self._perform_upload()
        except UploadRemoteFileError:
            # Just try again
            time.sleep(1)
            self._perform_upload()

        # Update metadata if upload successful
        if self._status[0] == Status.SKIPPED:
            self._logger.info(f'{self.log_prefix} Upload skipped.')
        else:
            self._logger.info(f'{self.log_prefix} Upload done.')

            try:
                self._update_metadata(**kwargs)
            except UploadRemoteFileMetadataError:
                # Just try again
                time.sleep(1)
                self._update_metadata(**kwargs)

        self._logger.info(f'{self.log_prefix} Closing upload sequence.')

        return self._status

    def _perform_upload(self):
        """Common upload implementation"""
        self._logger.info(f'{self.log_prefix} Starting uploading to Arcsecond.io ({self._file_size} bytes)')

        self._status = [Status.UPLOADING, Substatus.UPLOADING, None]
        self._started = datetime.now()

        data = self._get_upload_data()
        headers = {"Content-Type": data.content_type}
        _, error = self._context.api_endpoint.create(data=data, headers=headers)

        if not error:
            seconds = (datetime.now() - self._started).total_seconds()
            self._logger.info(f'{self.log_prefix} Upload duration is {seconds} seconds.')
            return

        if 'already exists in dataset' in str(error):  # VERY WEAK!!! But solution with HTTP 409 isn't nice either.
            self._status = [Status.SKIPPED, Substatus.ALREADY_SYNCED, None]
        else:
            self._status = [Status.ERROR, Substatus.ERROR, None]
            self._logger.info(f'{self.log_prefix} Upload of file {self._file_path} failed.')
            raise UploadRemoteFileError(f"{str(error.status)} - {str(error)}")

    @abstractmethod
    def _prepare_upload(self):
        """Prepare for upload - to be implemented by subclasses"""
        raise NotImplementedError()

    @abstractmethod
    def _update_metadata(self, **kwargs):
        """Update metadata after upload - to be implemented by subclasses"""
        raise NotImplementedError()

    @abstractmethod
    def _get_upload_data(self):
        """Get upload data - to be implemented by subclasses"""
        raise NotImplementedError()
