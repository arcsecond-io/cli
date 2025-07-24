import copy
import os
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Generic, TypeVar

from tqdm import tqdm

from .constants import Status, Substatus
from .context import BaseUploadContext
from .errors import (
    UploadRemoteFileError,
    UploadRemoteFileInvalidatedContextError,
)
from .logger import get_logger

ContextT = TypeVar("ContextT", bound=BaseUploadContext)


class UploadFileWithProgress:
    def __init__(self, file_path, chunk_size=8192, display_progress=False):
        self._file = open(file_path, "rb")
        self._chunk_size = chunk_size
        self._total = os.fstat(self._file.fileno()).st_size
        self._display_progress = display_progress
        if display_progress:
            self._progress = tqdm(total=self._total, unit="B", unit_scale=True)

    def read(self, amt=None):
        data = self._file.read(amt or self._chunk_size)
        if self._display_progress:
            self._progress.update(len(data))
            self._progress.refresh()
        return data

    def seek(self, offset, whence=os.SEEK_SET):
        return self._file.seek(offset, whence)

    def tell(self):
        return self._file.tell()

    def close(self):
        self._file.close()
        if self._display_progress:
            self._progress.close()

    def __getattr__(self, name):
        # Delegate all other attributes to the file object
        return getattr(self._file, name)


class BaseFileUploader(Generic[ContextT], ABC):
    """Abstract base class for uploaders"""

    def __init__(
        self,
        context: ContextT,
        file_path: str | Path,
        display_progress=False,
    ):
        self._context = context
        self._file_path = Path(file_path)
        self._display_progress = display_progress

        self._logger = get_logger()
        self._status = [Status.NEW, Substatus.PENDING, None]
        self._started = None
        self._file_size = os.path.getsize(file_path)

        self._uploaded_file = None
        self._cleanup_resources = []

    @property
    def log_prefix(self):
        """Generate a log prefix for this file"""
        return f"File {self._file_path.name}:"

    @property
    def uploaded_file_id(self):
        """Generate a log prefix for this file"""
        return self._uploaded_file.get("id", None) if self._uploaded_file else None

    @property
    def main_status(self):
        return self._status[0]

    def get_full_status_error(self):
        return self._status

    @abstractmethod
    def _prepare_upload(self):
        """Prepare for upload - to be implemented by subclasses"""
        raise NotImplementedError()

    def _get_upload_files(self, **kwargs):
        filename = os.path.basename(self._file_path)
        self._file = UploadFileWithProgress(
            self._file_path, display_progress=self._display_progress
        )
        self._cleanup_resources.append(self._file)
        return {
            "file": (filename, self._file, "application/octet-stream"),
        }

    @abstractmethod
    def _get_upload_data(self, **kwargs) -> dict:
        """Get upload data fields - to be implemented by subclasses"""
        raise NotImplementedError()

    def _perform_upload(self, **kwargs):
        """Common upload implementation"""
        self._logger.info(
            f"{self.log_prefix} Starting uploading to Arcsecond.io ({self._file_size} bytes)"
        )

        self._status = [Status.UPLOADING, Substatus.UPLOADING, None]
        self._started = datetime.now()

        files = self._get_upload_files(**kwargs)
        data = self._get_upload_data(**kwargs)
        self._uploaded_file, error = self._context.upload_api_endpoint.create(
            files=files, json=data
        )

        if not error:
            seconds = (datetime.now() - self._started).total_seconds()
            self._logger.info(
                f"{self.log_prefix} Upload duration is {seconds} seconds."
            )
            return

        if "already exists in dataset" in str(
            error
        ):  # VERY WEAK!!! But solution with HTTP 409 isn't nice either.
            self._status = [Status.SKIPPED, Substatus.ALREADY_SYNCED, None]
        else:
            self._status = [Status.ERROR, Substatus.ERROR, None]
            self._logger.info(
                f"{self.log_prefix} Upload of file {self._file_path} failed."
            )
            raise UploadRemoteFileError(f"{str(error.status)} - {str(error)}")

    def _cleanup(self):
        for resource in self._cleanup_resources:
            try:
                if hasattr(resource, "close") and not getattr(
                    resource, "closed", False
                ):
                    resource.close()
            except Exception as e:
                self._logger.error(f"{self.log_prefix} {str(e)}.")
        self._cleanup_resources = []

    def upload_file(self, **kwargs):
        """Generic upload method that orchestrates the upload process"""
        if self._context.is_validated is False:
            raise UploadRemoteFileInvalidatedContextError()

        self._logger.info(f"{self.log_prefix} Opening upload sequence.")

        # Pre-upload preparation (different for each context type)
        try:
            self._prepare_upload()
        except Exception:
            self._logger.info(
                f"{self.log_prefix} Upload preparation error. Trying again automatically in 1 second."
            )
            # Just try again
            time.sleep(1)
            self._prepare_upload()

        # Perform the actual upload (common to all types)
        kwargs_copy = copy.deepcopy(kwargs)
        try:
            self._perform_upload(**kwargs)
        except UploadRemoteFileError:
            # Just try again
            self._logger.info(
                f"{self.log_prefix} Upload error. Trying again automatically in 1 second."
            )
            time.sleep(1)
            self._perform_upload(**kwargs_copy)
        finally:
            self._cleanup()

        if self._status[0] == Status.SKIPPED:
            self._logger.info(f"{self.log_prefix} Upload skipped.")
        else:
            self._logger.info(f"{self.log_prefix} Upload completed.")
            self._status = [Status.OK, Substatus.DONE, None]

        self._logger.info(f"{self.log_prefix} Closing upload sequence.")

        return self._status
