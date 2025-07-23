from unittest.mock import MagicMock, patch

import pytest

from arcsecond import DatasetFileUploader
from arcsecond.cloud.uploader import DatasetUploadContext
from tests.utils import random_string


@pytest.fixture
def mock_config():
    """Create a mock ArcsecondConfig."""
    config = MagicMock()
    config.username = "test_user"
    config.upload_key = "test_key"
    config.api_name = random_string()
    config.api_server = "http://mock.example.com"
    config.access_key = None  # very important, because access_key takes precedence on upload_key in headers setting.
    config.upload_key = '1234567890'
    return config


@pytest.fixture
def mock_file_context(mock_config):
    """Create a mock upload context."""
    context = MagicMock(spec=DatasetUploadContext)
    context.config = mock_config
    context.is_validated = True
    context.dataset_uuid = "test-dataset-uuid"
    context.dataset_name = "test-dataset"
    context.telescope_uuid = "test-telescope-uuid"
    context.is_raw_data = True
    context.custom_tags = ["test_tag1", "test_tag2"]
    return context


@pytest.fixture
def temp_file(tmp_path):
    """Create a temporary test file."""
    file_path = tmp_path / "test_file.txt"
    with open(file_path, "w") as f:
        f.write("Test content")
    return file_path


@pytest.fixture
def file_uploader(mock_file_context, temp_file):
    """Create a DatasetFileUploader instance with mocked dependencies."""
    with patch("arcsecond.cloud.uploader.logger.get_logger"):
        uploader = DatasetFileUploader(
            mock_file_context, temp_file, display_progress=False
        )
        uploader._logger = MagicMock()
        return uploader
