from unittest.mock import patch, MagicMock

import pytest

from arcsecond.cloud.uploader.constants import Status, Substatus
from arcsecond.cloud.uploader.datafiles.errors import UploadRemoteDatasetPreparationError
from arcsecond.cloud.uploader.errors import (
    UploadRemoteFileInvalidatedContextError,
    UploadRemoteFileError,
    UploadRemoteFileMetadataError
)


def test_upload_file_skipped(uploader):
    """Test upload file process when file is skipped."""
    # Mock all the component methods
    with patch.object(uploader, '_prepare_upload') as mock_prepare, \
            patch.object(uploader, '_perform_upload') as mock_perform, \
            patch.object(uploader, '_update_metadata') as mock_update:
        # Simulate skipped file
        uploader._status = [Status.SKIPPED, Substatus.ALREADY_SYNCED, None]
        result = uploader.upload_file()

        # Verify methods were called (except update)
        mock_prepare.assert_called_once()
        mock_perform.assert_called_once()
        mock_update.assert_not_called()

        # Verify result
        assert result == [Status.SKIPPED, Substatus.ALREADY_SYNCED, None]


def test_upload_file_invalid_context(uploader):
    """Test upload file with invalid context."""
    # Set context as not validated
    uploader._context.is_validated = False

    # Should raise exception
    with pytest.raises(UploadRemoteFileInvalidatedContextError):
        uploader.upload_file()


def test_perform_upload_already_exists(uploader):
    """Test upload of file that already exists."""
    # Mock upload data and API response indicating file already exists
    mock_encoder = MagicMock()
    mock_encoder.content_type = "multipart/form-data"

    error = MagicMock()
    error.__str__.return_value = "already exists in dataset"
    uploader._api.datafiles.create.return_value = (None, error)

    with patch.object(uploader, '_get_upload_data', return_value=mock_encoder):
        uploader._perform_upload()

    # Verify status was set to SKIPPED
    assert uploader._status == [Status.SKIPPED, Substatus.ALREADY_SYNCED, None]


def test_perform_upload_error(uploader):
    """Test upload with API error."""
    # Mock upload data and API error
    mock_encoder = MagicMock()
    mock_encoder.content_type = "multipart/form-data"

    error = MagicMock()
    error.__str__.return_value = "API error"
    error.status = 400
    uploader._api.datafiles.create.return_value = (None, error)

    with patch.object(uploader, '_get_upload_data', return_value=mock_encoder):
        with pytest.raises(UploadRemoteFileError) as excinfo:
            uploader._perform_upload()

    # Verify error message
    assert "API error" in str(excinfo.value)

    # Verify status was set to ERROR
    assert uploader._status == [Status.ERROR, Substatus.ERROR, None]


def test_upload_file_retry_on_error(uploader):
    """Test that upload retries on error."""
    # Mock methods with side effects
    prepare_mock = MagicMock(side_effect=[UploadRemoteDatasetPreparationError("First error"), None])
    perform_mock = MagicMock(side_effect=[UploadRemoteFileError("First error"), None])
    update_mock = MagicMock(side_effect=[UploadRemoteFileMetadataError("First error"), None])

    with patch.object(uploader, '_prepare_upload', prepare_mock), \
            patch.object(uploader, '_perform_upload', perform_mock), \
            patch.object(uploader, '_update_metadata', update_mock), \
            patch('time.sleep'):
        # Upload should retry each step once
        uploader.upload_file()

        # Verify each method was called twice (initial + retry)
        assert prepare_mock.call_count == 2
        assert perform_mock.call_count == 2
        assert update_mock.call_count == 2


def test_update_metadata_error(uploader):
    """Test metadata update with API error."""
    # Mock API error
    error = "API error"
    uploader._api.datafiles.update.return_value = (None, error)
    uploader._uploaded_file = {'id': 12345}

    # Test that the error is properly raised
    with pytest.raises(UploadRemoteFileMetadataError) as excinfo:
        uploader._update_metadata()

    assert "Failed to update file metadata" in str(excinfo.value)
