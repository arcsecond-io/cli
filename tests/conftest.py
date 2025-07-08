from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from arcsecond import DatasetFileUploader
from arcsecond.cloud.uploader import DatasetUploadContext


@pytest.fixture
def mock_config():
    """Create a mock ArcsecondConfig."""
    config = MagicMock()
    config.username = "test_user"
    config.upload_key = "test_key"
    return config


@pytest.fixture
def mock_api():
    """Create a mock API with datasets and datafiles endpoints."""
    api = MagicMock()
    api.datasets = MagicMock()
    api.datafiles = MagicMock()
    return api


@pytest.fixture
def mock_context(mock_config, mock_api):
    """Create a mock upload context."""
    context = MagicMock(spec=DatasetUploadContext)
    context.config = mock_config
    context._api = mock_api
    context.is_validated = True
    context.dataset_uuid = "test-dataset-uuid"
    context.dataset_name = "test-dataset"
    context.telescope_uuid = "test-telescope-uuid"
    context.is_raw_data = True
    context.custom_tags = ["test_tag1", "test_tag2"]
    context.api_endpoint = mock_api.datafiles
    return context


@pytest.fixture
def temp_file(tmp_path):
    """Create a temporary test file."""
    file_path = tmp_path / "test_file.txt"
    with open(file_path, "w") as f:
        f.write("Test content")
    return file_path


@pytest.fixture
def uploader(mock_context, temp_file):
    """Create a DatasetFileUploader instance with mocked dependencies."""
    walking_root = Path(temp_file).parent
    with patch("arcsecond.cloud.uploader.logger.get_logger"):
        uploader = DatasetFileUploader(
            mock_context, walking_root, temp_file, display_progress=False
        )
        uploader._logger = MagicMock()
        return uploader
