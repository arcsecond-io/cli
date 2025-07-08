def test_update_metadata_success(uploader):
    """Test successful metadata update."""
    # Mock successful API response
    uploader._api.datafiles.update.return_value = ({"id": "test-file-id"}, None)
    uploader._uploaded_file = {"id": "test-file-id"}

    # Call with explicit parameters
    uploader._update_metadata(is_raw=True, custom_tags=["tag1", "tag2"])

    # Verify API call with correct parameters
    expected_metadata = {"is_raw": True, "custom_tags": ["tag1", "tag2"]}
    uploader._api.datafiles.update.assert_called_once_with(
        "test-file-id", expected_metadata
    )


def test_update_metadata_with_context_values(uploader):
    """Test metadata update using context values."""
    # Mock successful API response
    uploader._api.datafiles.update.return_value = ({"id": "test-file-id"}, None)
    uploader._uploaded_file = {"id": "test-file-id"}

    # Call without explicit parameters, should use context values
    uploader._update_metadata()

    # Verify API call with context values
    expected_metadata = {
        "is_raw": uploader._context.is_raw_data,
        "custom_tags": uploader._context.custom_tags,
    }
    uploader._api.datafiles.update.assert_called_once_with(
        "test-file-id", expected_metadata
    )


def test_update_metadata_missing_uuid(uploader):
    """Test metadata update when file UUID is missing."""
    # Set file UUID to None
    uploader._uploaded_file = None

    # Should log warning but not raise exception
    uploader._update_metadata()

    # Verify API was not called
    uploader._api.datafiles.update.assert_not_called()

    # Verify warning was logged
    uploader._logger.warning.assert_called()
