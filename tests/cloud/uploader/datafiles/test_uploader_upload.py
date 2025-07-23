from unittest.mock import patch

from arcsecond.cloud.uploader.constants import Status, Substatus


def test_get_upload_data(file_uploader, temp_file):
    """Test the creation of upload data."""
    result = file_uploader._get_upload_data()
    assert isinstance(result, dict)
    assert "dataset" in result
    assert "is_raw" in result
    assert "tags" not in result
    assert result["is_raw"] == "True"  # yes, it is stringified for MultipartEncoder


def test_get_upload_data_with_raw_false(file_uploader, temp_file):
    """Test the creation of upload data."""
    file_uploader._context.is_raw_data = False
    result = file_uploader._get_upload_data()
    assert isinstance(result, dict)
    assert "dataset" in result
    assert "is_raw" in result
    assert "tags" not in result
    assert result["is_raw"] == "False"  # yes, it is stringified for MultipartEncoder


def test_get_upload_data_with_custom_tags_array(file_uploader, temp_file):
    """Test the creation of upload data."""
    file_uploader._context.custom_tags = ["t1", "t2", "t4"]
    result = file_uploader._get_upload_data()
    assert isinstance(result, dict)
    assert "dataset" in result
    assert "is_raw" in result
    assert "tags" in result
    assert result["tags"] == "t1,t2,t4"  # yes, it is stringified for MultipartEncoder


def test_get_upload_data_with_custom_tags_string(file_uploader, temp_file):
    """Test the creation of upload data."""
    file_uploader._context.custom_tags = "t0, t5, t6"
    result = file_uploader._get_upload_data()
    assert isinstance(result, dict)
    assert "dataset" in result
    assert "is_raw" in result
    assert "tags" in result
    assert result["tags"] == "t0,t5,t6"  # yes, it is stringified for MultipartEncoder


def test_upload_file_complete_process(file_uploader):
    """Test the complete upload file process."""
    # Mock all the component methods
    with (
        patch.object(file_uploader, "_prepare_upload") as mock_prepare,
        patch.object(file_uploader, "_perform_upload") as mock_perform,
    ):
        result = file_uploader.upload_file(is_raw=True, custom_tags=["tag1"])

        mock_prepare.assert_called_once()
        mock_perform.assert_called_once()

        assert result == [Status.OK, Substatus.DONE, None]
