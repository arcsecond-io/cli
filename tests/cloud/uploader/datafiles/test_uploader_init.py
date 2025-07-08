import os
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

from arcsecond import DatasetUploadContext
from arcsecond.cloud.uploader.constants import Status, Substatus
from arcsecond.cloud.uploader.datafiles.uploader import DatasetFileUploader


def test_initialization(mock_context, temp_file):
    """Test if the uploader initializes correctly."""
    walking_root = Path(temp_file).parent

    with patch("arcsecond.cloud.uploader.logger.get_logger"):
        uploader = DatasetFileUploader(mock_context, walking_root, temp_file)

        assert uploader._context == mock_context
        assert uploader._walking_root == walking_root
        assert uploader._file_path == temp_file
        assert uploader._file_size == os.path.getsize(temp_file)
        assert uploader._status == [Status.NEW, Substatus.PENDING, None]
