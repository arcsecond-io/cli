import pytest

from arcsecond.cloud.uploader.datafiles.errors import UploadRemoteDatasetPreparationError


def test_prepare_upload_with_existing_dataset(uploader):
    """Test prepare upload when dataset UUID exists."""
    # If dataset_uuid exists, _prepare_upload should not create a new dataset
    uploader._context.dataset_uuid = "existing-uuid"
    uploader._prepare_upload()
    # Verify no API calls were made
    uploader._api.datasets.create.assert_not_called()


def test_prepare_upload_with_new_dataset(uploader):
    """Test prepare upload when dataset needs to be created."""
    # Mock dataset UUID as empty to force dataset creation
    uploader._context.dataset_uuid = ""

    # Mock successful dataset creation
    mock_dataset = {"uuid": "new-dataset-uuid", "name": uploader._context.dataset_name}
    uploader._api.datasets.create.return_value = (mock_dataset, None)

    uploader._prepare_upload()

    # Verify API call was made with correct parameters
    expected_data = {
        'name': uploader._context.dataset_name,
        'telescope': uploader._context.telescope_uuid
    }
    uploader._api.datasets.create.assert_called_once_with(data=expected_data)

    # Verify context was updated with new dataset
    uploader._context.update_dataset.assert_called_once_with(mock_dataset)


def test_prepare_upload_with_error(uploader):
    """Test prepare upload when API returns an error."""
    # Mock dataset UUID as empty to force dataset creation
    uploader._context.dataset_uuid = ""

    # Mock API error
    error_message = "API error"
    uploader._api.datasets.create.return_value = (None, error_message)

    # Test that the error is properly raised
    with pytest.raises(UploadRemoteDatasetPreparationError) as excinfo:
        uploader._prepare_upload()

    assert f"Dataset {uploader._context.dataset_name} could not be created" in str(excinfo.value)
