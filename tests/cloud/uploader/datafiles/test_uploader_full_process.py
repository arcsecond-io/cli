import random
import shutil
import tempfile
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import respx
from httpx import Response

from arcsecond import (
    DatasetFileUploader,
    DatasetUploadContext,
)
from arcsecond.cloud.uploader.constants import Status, Substatus
from tests.utils import (
    prepare_successful_login,
    prepare_upload_files,
    random_string,
)


@pytest.fixture
def mock_config():
    """Create a mock ArcsecondConfig."""
    config = MagicMock()
    config.username = "test_user"
    config.upload_key = "test_key"
    config.api_name = random_string()
    config.api_server = "http://mock.example.com"
    config.access_key = None  # very important, because access_key takes precedence on upload_key in headers setting.
    config.upload_key = "1234567890"
    return config


@respx.mock
def test_full_upload_process_datafiles(mock_config):
    dataset_uuid = str(uuid.uuid4())
    telescope_uuid = str(uuid.uuid4())
    org_subdomain = "test-portal"

    prepare_successful_login(mock_config, org_subdomain)
    prepare_upload_files(mock_config, dataset_uuid, telescope_uuid, org_subdomain)

    respx.get(
        "/".join([mock_config.api_server, org_subdomain, "datasets", dataset_uuid])
        + "/"
    ).mock(Response(201, json={"name": "dummy", "uuid": dataset_uuid}))

    datafile_id = random.randint(1, 1000)
    respx.post(
        "/".join([mock_config.api_server, org_subdomain, "datafiles"]) + "/"
    ).mock(Response(201, json={"status": "success", "id": datafile_id}))

    context = DatasetUploadContext(
        mock_config,
        input_dataset_uuid_or_name=dataset_uuid,
        input_telescope_uuid=telescope_uuid,
        is_raw_data=True,
        org_subdomain=org_subdomain,
    )

    context.validate()  # important step to perform before uploading.
    fixtures_dir = Path(__file__).parent.parent.parent.parent / "fixtures"
    fixture_files = list(fixtures_dir.glob("*.fits"))

    for fixture_file in fixture_files:
        # Create a temporary directory and copy the fixture file there
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / fixture_file.name
            shutil.copy(fixture_file, temp_path)

            # Use the actual file for uploading
            uploader = DatasetFileUploader(
                context, str(temp_path), display_progress=False
            )

            status, substatus, error = uploader.upload_file()
            assert status.value == Status.OK.value
            assert substatus.value == Substatus.DONE.value
            assert error is None
