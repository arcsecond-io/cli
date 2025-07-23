from unittest.mock import MagicMock, mock_open, patch

from arcsecond.cloud.uploader import DatasetFileUploader, DatasetUploadContext
from arcsecond.cloud.uploader.constants import Status, Substatus


def test_get_upload_data(uploader, temp_file):
    """Test the creation of upload data."""
    # Mock the MultipartEncoder
    mock_encoder = MagicMock()
    mock_monitor = MagicMock()

    with (
        patch("requests_toolbelt.MultipartEncoder", return_value=mock_encoder),
        patch("requests_toolbelt.MultipartEncoderMonitor", return_value=mock_monitor),
        patch("arcsecond.cloud.uploader.utils.get_upload_progress_printer"),
        patch("builtins.open", mock_open(read_data="test data")),
    ):
        # Without progress display
        uploader._display_progress = False
        result = uploader._get_upload_data()
        assert result == mock_encoder

        # With progress display
        uploader._display_progress = True
        result = uploader._get_upload_data()
        assert result == mock_monitor


def test_perform_upload_success(uploader):
    """Test successful file upload."""
    # Mock upload data and successful API response
    mock_encoder = MagicMock()
    mock_encoder.content_type = "multipart/form-data"

    mock_datafile = {"id": "new-file-id"}
    uploader._api.datafiles.create.return_value = (mock_datafile, None)

    with patch.object(uploader, "_get_upload_data", return_value=mock_encoder):
        uploader._perform_upload()

    # Verify API call
    uploader._api.datafiles.create.assert_called_once_with(
        data=mock_encoder, headers={"Content-Type": "multipart/form-data"}
    )

    # Verify status and file ID
    assert uploader.uploaded_file_id == "new-file-id"
    assert uploader.main_status == Status.UPLOADING


def test_upload_file_complete_process(uploader):
    """Test the complete upload file process."""
    # Mock all the component methods
    with (
        patch.object(uploader, "_prepare_upload") as mock_prepare,
        patch.object(uploader, "_perform_upload") as mock_perform,
        patch.object(uploader, "_update_metadata") as mock_update,
    ):
        # Successful upload
        uploader._status = [Status.UPLOADING, Substatus.UPLOADING, None]
        result = uploader.upload_file(is_raw=True, custom_tags=["tag1"])

        # Verify all methods were called
        mock_prepare.assert_called_once()
        mock_perform.assert_called_once()
        mock_update.assert_called_once_with(is_raw=True, custom_tags=["tag1"])

        # Verify result
        assert result == [Status.UPLOADING, Substatus.UPLOADING, None]


def test_dataset_file_uploader_integration(mock_config, temp_file):
    """Integration test for DatasetFileUploader."""
    # Create a real context with mocked API
    mock_api = MagicMock()
    mock_api.datasets.create.return_value = (
        {"uuid": "new-dataset-uuid", "name": "test-dataset"},
        None,
    )
    mock_api.datafiles.create.return_value = ({"id": "new-file-id"}, None)
    mock_api.datafiles.update.return_value = ({"id": "new-file-id"}, None)

    # Create a patched context class
    with patch("arcsecond.api.main.ArcsecondAPI", return_value=mock_api):
        context = DatasetUploadContext(
            mock_config,
            input_dataset_uuid_or_name="test-dataset",
            input_telescope_uuid="test-telescope-uuid",
            is_raw_data=True,
            custom_tags=["test_tag"],
        )

        # Mock context validation
        with patch.object(context, "validate"):
            context._is_validated = True
            context._api = mock_api

            with (
                patch("arcsecond.cloud.uploader.logger.get_logger"),
                patch("requests_toolbelt.MultipartEncoder"),
                patch("requests_toolbelt.MultipartEncoderMonitor"),
                patch("builtins.open", mock_open(read_data="test data")),
            ):
                uploader = DatasetFileUploader(
                    context, temp_file, display_progress=False
                )
                uploader._logger = MagicMock()

                # Execute the upload
                status, substatus, error = uploader.upload_file()

                # Verify successful upload
                assert status == Status.UPLOADING

                # Verify API calls
                if not context.dataset_uuid:
                    mock_api.datasets.create.assert_called()

                mock_api.datafiles.create.assert_called()
                mock_api.datafiles.update.assert_called()
