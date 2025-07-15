import random
import shutil
import tempfile
import uuid
from pathlib import Path

import responses

from api.constants import ARCSECOND_API_URL_DEV
from arcsecond import ArcsecondConfig, DatasetUploadContext, DatasetFileUploader
from arcsecond.cloud.uploader.constants import Substatus, Status
from arcsecond.options import State
from tests.utils import prepare_successful_login, prepare_upload_files


@responses.activate
def test_full_upload_process(tmpdir):
    dataset_uuid = str(uuid.uuid4())
    telescope_uuid = str(uuid.uuid4())
    org_subdomain = 'test-portal'

    config = ArcsecondConfig(State(api_name="test"))
    config.api_server = ARCSECOND_API_URL_DEV

    prepare_successful_login(org_subdomain)
    prepare_upload_files(dataset_uuid, telescope_uuid, org_subdomain)

    # file upload
    datafile_id = random.randint(1, 1000)
    responses.post(
        "/".join([ARCSECOND_API_URL_DEV, org_subdomain, 'datafiles']) + "/",
        status=201,
        json={"status": "success", "id": datafile_id}
    )
    # update metadata
    responses.patch(
        "/".join([ARCSECOND_API_URL_DEV, org_subdomain, 'datafiles', str(datafile_id)]) + "/",
        status=200,
        json={"id": datafile_id}
    )

    state = State(is_using_cli=False, verbose=False, api_name='cloud')
    config = {
        'cloud': {
            'username': 'dummy',
            'upload_key': '1234',
            'api_server': ARCSECOND_API_URL_DEV
        }
    }

    config = ArcsecondConfig(state, config)  # it will read your config file.

    context = DatasetUploadContext(
        config,
        input_dataset_uuid_or_name=dataset_uuid,
        input_telescope_uuid=telescope_uuid,
        is_raw_data=True,
        org_subdomain=org_subdomain
    )

    context.validate()  # important step to perform before uploading.
    fixtures_dir = Path(__file__).parent.parent.parent.parent / "fixtures"
    fixture_files = list(fixtures_dir.glob('*.fits'))

    for fixture_file in fixture_files:
        # Create a temporary directory and copy the fixture file there
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / fixture_file.name
            shutil.copy(fixture_file, temp_path)

            # Use the actual file for uploading
            uploader = DatasetFileUploader(
                context,
                str(temp_dir),
                str(temp_path),
                display_progress=False
            )

            status, substatus, error = uploader.upload_file()
            assert status.value == Status.OK.value
            assert substatus.value == Substatus.DONE.value
            assert error is None
