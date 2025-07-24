from arcsecond.cloud.uploader.uploader import BaseFileUploader
from arcsecond.errors import ArcsecondError

from .context import AllSkyCameraImageUploadContext
from .errors import MissingTimestampError


class AllSkyCameraImageFileUploader(BaseFileUploader[AllSkyCameraImageUploadContext]):
    """Uploader for image files with camera attachment"""

    def _prepare_upload(self):
        """No specific preparation needed for image uploads"""
        # Camera validation was already done in the context
        pass

    def _get_upload_data(self, **kwargs):
        # At that point, timestamp must have been provided (with upload_file(ts)).
        fields = {"camera": self._context.camera_uuid}
        clean_kwargs = {
            k: kwargs[k] for k in ("utc_timestamp", "camera") if k in kwargs
        }
        fields.update(**clean_kwargs)
        return fields

    def upload_file(self, utc_timestamp, **kwargs):
        if utc_timestamp is None:
            raise MissingTimestampError(self._file_path)
        kwargs.update(utc_timestamp=utc_timestamp)
        return super().upload_file(**kwargs)
