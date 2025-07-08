import os

from arcsecond.cloud.uploader.errors import UploadRemoteFileMetadataError
from arcsecond.cloud.uploader.uploader import BaseFileUploader
from arcsecond.cloud.uploader.utils import get_upload_progress_printer
from .context import AllSkyCameraImageUploadContext


class AllSkyCameraImageFileUploader(BaseFileUploader[AllSkyCameraImageUploadContext]):
    """Uploader for image files with camera attachment"""

    def _prepare_upload(self):
        """No specific preparation needed for image uploads"""
        # Camera validation was already done in the context
        pass

    def _get_upload_data(self):
        """Get upload data for image files"""
        from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor

        filename = os.path.basename(self._file_path)

        # Create fields dictionary for MultipartEncoder
        fields = {
            "file": (filename, open(self._file_path, "rb"), "application/octet-stream"),
            "camera": self._context.camera_uuid,
        }

        # Create MultipartEncoder
        e = MultipartEncoder(fields=fields)

        # Create progress monitor if display_progress is True
        if self._display_progress:
            callback = get_upload_progress_printer(self._file_size)
            # Wrap MultipartEncoder with MultipartEncoderMonitor for progress tracking
            e = MultipartEncoderMonitor(e, callback)

        return e

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
