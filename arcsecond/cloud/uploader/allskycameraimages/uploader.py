import os

from arcsecond.cloud.uploader.uploader import BaseFileUploader
from arcsecond.errors import ArcsecondError
from .context import AllSkyCameraImageUploadContext


class AllSkyCameraImageFileUploader(BaseFileUploader[AllSkyCameraImageUploadContext]):
    """Uploader for image files with camera attachment"""

    def _prepare_upload(self):
        """No specific preparation needed for image uploads"""
        # Camera validation was already done in the context
        pass

    def _get_upload_data_fields(self, **kwargs):
        filename = os.path.basename(self._file_path)
        self._file = open(self._file_path, "rb")
        self._cleanup_resources.append(self._file)
        fields = {
            "file": (filename, self._file, "application/octet-stream"),
            "camera": self._context.camera_uuid
        }
        clean_kwargs = {k: kwargs[k] for k in ('timestamp', 'camera') if k in kwargs}
        fields.update(**clean_kwargs)
        if 'timestamp' not in clean_kwargs:
            raise ArcsecondError('Missing timestamp.')
        return fields

    def upload_file(self, timestamp, **kwargs):
        if timestamp is None:
            raise ArcsecondError("Missing timestamp for image.")
        kwargs.update(timestamp=timestamp)
        super().upload_file(**kwargs)
