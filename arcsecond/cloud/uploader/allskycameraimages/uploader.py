import os

from arcsecond.cloud.uploader.errors import UploadRemoteFileMetadataError
from arcsecond.cloud.uploader.uploader import BaseFileUploader

from .context import AllSkyCameraImageUploadContext


class AllSkyCameraImageFileUploader(BaseFileUploader[AllSkyCameraImageUploadContext]):
    """Uploader for image files with camera attachment"""

    def _prepare_upload(self):
        """No specific preparation needed for image uploads"""
        # Camera validation was already done in the context
        pass

    def _get_upload_data_fields(self):
        filename = os.path.basename(self._file_path)
        self._file = open(self._file_path, "rb")
        self._cleanup_resources.append(self._file)
        return {
            "file": (filename, self._file, "application/octet-stream"),
            "camera": self._context.camera_uuid,
        }

    def _update_metadata(self, timestamp=None, custom_tags=None):
        """Update image metadata after upload"""
        if not self.uploaded_file_id:
            self._logger.warning(
                f"{self.log_prefix} No ID found for uploaded file. Skipping metadata update."
            )
            return

        # Determine final timestamp
        final_timestamp = (
            timestamp if timestamp is not None else self._context.timestamp
        )

        # Determine final custom tags
        final_tags = (
            custom_tags if custom_tags is not None else self._context.custom_tags
        )

        # Build metadata
        metadata = {}
        if final_timestamp:
            metadata["timestamp"] = final_timestamp

        if final_tags:
            metadata["customTags"] = final_tags

        # Update metadata
        if metadata:
            self._logger.info(f"{self.log_prefix} Updating image metadata: {metadata}")
            response, error = self._api.datafiles.update(
                self.uploaded_file_id, metadata
            )

            if error:
                error_msg = f"Failed to update image metadata: {error}"
                self._logger.error(error_msg)
                raise UploadRemoteFileMetadataError(error_msg)
