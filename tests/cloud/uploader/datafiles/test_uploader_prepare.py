from unittest.mock import patch

import pytest

from arcsecond.cloud.uploader.datafiles.errors import (
    UploadRemoteDatasetPreparationError,
)


def test_prepare_upload_with_existing_dataset(file_uploader):
    """Test prepare upload when dataset UUID exists."""
    # If dataset_uuid exists, _prepare_upload should not create a new dataset
    with patch.object(
        file_uploader._context.upload_api_endpoint, "create"
    ) as mock_func:
        file_uploader._context.dataset_uuid = "existing-uuid"
        file_uploader._prepare_upload()
        # Verify no API calls were made
        mock_func.assert_not_called()


def test_prepare_upload_with_new_dataset(file_uploader):
    """Test prepare upload when dataset needs to be created."""
    # Mock dataset UUID as empty to force dataset creation
    file_uploader._context.dataset_uuid = ""
    mock_dataset = {
        "uuid": "new-dataset-uuid",
        "name": file_uploader._context.dataset_name,
    }

    with (
        patch("arcsecond.api.endpoint.ArcsecondAPIEndpoint.create") as mock_func_create,
        patch("arcsecond.api.endpoint.ArcsecondAPIEndpoint.update") as mock_func_update,
    ):
        mock_func_create.return_value = (mock_dataset, None)

        file_uploader._prepare_upload()

        # Verify API call was made with correct parameters
        expected_data = {
            "name": file_uploader._context.dataset_name,
            "telescope": file_uploader._context.telescope_uuid,
        }
        mock_func_create.assert_called_once_with(json=expected_data)
        mock_func_update.assert_not_called()


def test_prepare_upload_with_error(file_uploader):
    """Test prepare upload when API returns an error."""
    # Mock dataset UUID as empty to force dataset creation
    file_uploader._context.dataset_uuid = ""

    with (
        patch("arcsecond.api.endpoint.ArcsecondAPIEndpoint.create") as mock_func_create,
        patch("arcsecond.api.endpoint.ArcsecondAPIEndpoint.update") as mock_func_update,
    ):
        error_message = "API error"
        mock_func_create.return_value = (None, error_message)

        # Test that the error is properly raised
        with pytest.raises(UploadRemoteDatasetPreparationError) as excinfo:
            file_uploader._prepare_upload()

        assert (
            f"Dataset {file_uploader._context.dataset_name} could not be created"
            in str(excinfo.value)
        )
