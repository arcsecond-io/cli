import os
from pathlib import Path
from unittest.mock import patch

from arcsecond.cloud.uploader.constants import Status, Substatus
from arcsecond.cloud.uploader.datafiles.uploader import DatasetFileUploader


def test_initialization(mock_file_context, temp_file):
    """Test if the uploader initializes correctly."""
    walking_root = Path(temp_file).parent

    with patch("arcsecond.cloud.uploader.logger.get_logger"):
        uploader = DatasetFileUploader(mock_file_context, temp_file)

        assert uploader._context == mock_file_context
        assert uploader._file_path == temp_file
        assert uploader._file_size == os.path.getsize(temp_file)
        assert uploader.uploaded_file_id is None
        assert uploader.main_status == Status.NEW
        assert uploader.get_full_status_error() == [Status.NEW, Substatus.PENDING, None]
