import pytest

from arcsecond.cloud.uploader.datafiles.errors import (
    UploadRemoteDatasetPreparationError,
)


def test_prepare_upload_with_existing_dataset(file_uploader):
    """Test prepare upload when dataset UUID exists."""
    # If dataset_uuid exists, _prepare_upload should not create a new dataset
    file_uploader._context.dataset_uuid = "existing-uuid"
    file_uploader._prepare_upload()
    # Verify no API calls were made
    file_uploader._api.datasets.create.assert_not_called()


def test_prepare_upload_with_new_dataset(file_uploader):
    """Test prepare upload when dataset needs to be created."""
    # Mock dataset UUID as empty to force dataset creation
    file_uploader._context.dataset_uuid = ""

    # Mock successful dataset creation
    mock_dataset = {"uuid": "new-dataset-uuid", "name": file_uploader._context.dataset_name}
    file_uploader._api.datasets.create.return_value = (mock_dataset, None)

    file_uploader._prepare_upload()

    # Verify API call was made with correct parameters
    expected_data = {
        "name": file_uploader._context.dataset_name,
        "telescope": file_uploader._context.telescope_uuid,
    }
    file_uploader._api.datasets.create.assert_called_once_with(data=expected_data)

    # Verify context was updated with new dataset
    file_uploader._context.update_dataset.assert_called_once_with(mock_dataset)


def test_prepare_upload_with_error(file_uploader):
    """Test prepare upload when API returns an error."""
    # Mock dataset UUID as empty to force dataset creation
    file_uploader._context.dataset_uuid = ""

    # Mock API error
    error_message = "API error"
    file_uploader._api.datasets.create.return_value = (None, error_message)

    # Test that the error is properly raised
    with pytest.raises(UploadRemoteDatasetPreparationError) as excinfo:
        file_uploader._prepare_upload()

    assert f"Dataset {file_uploader._context.dataset_name} could not be created" in str(
        excinfo.value
    )
