from unittest.mock import MagicMock, patch

import pytest

from arcsecond.cloud.uploader.constants import Status, Substatus
from arcsecond.cloud.uploader.datafiles.errors import (
    UploadRemoteDatasetPreparationError,
)
from arcsecond.cloud.uploader.errors import (
    UploadRemoteFileError,
    UploadRemoteFileInvalidatedContextError,
)


def test_upload_file_skipped(file_uploader):
    """Test upload file process when file is skipped."""
    # Mock all the component methods
    with (
        patch.object(file_uploader, "_prepare_upload") as mock_prepare,
        patch.object(file_uploader, "_perform_upload") as mock_perform,
    ):
        # Simulate skipped file
        file_uploader._status = [Status.SKIPPED, Substatus.ALREADY_SYNCED, None]
        result = file_uploader.upload_file()

        # Verify methods were called (except update)
        mock_prepare.assert_called_once()
        mock_perform.assert_called_once()

        # Verify result
        assert result == [Status.SKIPPED, Substatus.ALREADY_SYNCED, None]


def test_upload_file_invalid_context(file_uploader):
    """Test upload file with invalid context."""
    # Set context as not validated
    file_uploader._context.is_validated = False

    # Should raise exception
    with pytest.raises(UploadRemoteFileInvalidatedContextError):
        file_uploader.upload_file()


def test_perform_upload_already_exists(file_uploader):
    """Test upload of file that already exists."""
    # Mock upload data and API response indicating file already exists
    mock_encoder = MagicMock()
    mock_encoder.content_type = "multipart/form-data"

    error = MagicMock()
    error.__str__.return_value = "already exists in dataset"

    with patch.object(
        file_uploader._context.upload_api_endpoint, "create"
    ) as mock_func:
        mock_func.return_value = (None, error)

        with patch.object(file_uploader, "_get_upload_data", return_value=mock_encoder):
            file_uploader._perform_upload()

        # Verify status was set to SKIPPED
        assert file_uploader._status == [Status.SKIPPED, Substatus.ALREADY_SYNCED, None]


def test_perform_upload_error(file_uploader):
    """Test upload with API error."""
    # Mock upload data and API error
    mock_encoder = MagicMock()
    mock_encoder.content_type = "multipart/form-data"

    error = MagicMock()
    error.__str__.return_value = "API error"
    error.status = 400
    with patch.object(
        file_uploader._context.upload_api_endpoint, "create"
    ) as mock_func:
        mock_func.return_value = (None, error)

        with patch.object(file_uploader, "_get_upload_data", return_value=mock_encoder):
            with pytest.raises(UploadRemoteFileError) as excinfo:
                file_uploader._perform_upload()

        # Verify error message
        assert "API error" in str(excinfo.value)

        # Verify status was set to ERROR
        assert file_uploader._status == [Status.ERROR, Substatus.ERROR, None]


def test_upload_file_retry_on_error(file_uploader):
    """Test that upload retries on error."""
    # Mock methods with side effects
    prepare_mock = MagicMock(
        side_effect=[UploadRemoteDatasetPreparationError("First error"), None]
    )
    perform_mock = MagicMock(side_effect=[UploadRemoteFileError("First error"), None])

    with (
        patch.object(file_uploader, "_prepare_upload", prepare_mock),
        patch.object(file_uploader, "_perform_upload", perform_mock),
        patch("time.sleep"),
    ):
        # Upload should retry each step once
        file_uploader.upload_file()

        # Verify each method was called twice (initial + retry)
        assert prepare_mock.call_count == 2
        assert perform_mock.call_count == 2
