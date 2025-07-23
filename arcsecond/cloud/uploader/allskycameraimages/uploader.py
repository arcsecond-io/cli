import os

from arcsecond.cloud.uploader.uploader import BaseFileUploader
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
            "camera": self._context.camera_uuid,
            "timestamp": self._context.timestamp,
        }
        if self._context.custom_tags:
            fields["tags"] = ",".join(self._context.custom_tags or [])  # will be split back in backend
        clean_kwargs = {k: kwargs[k] for k in ('timestamp', 'camera')}
        if 'tags' in clean_kwargs and not clean_kwargs['tags']:
            # Tags must really be provided only when non-blank/null/empty
            del clean_kwargs['tags']
        fields.update(**clean_kwargs)
        return fields
