import os
import time
import uuid

import httpretty
from click.testing import CliRunner

from arcsecond import ArcsecondAPI
from arcsecond.api.constants import ARCSECOND_API_URL_DEV
from tests.utils import register_successful_login

has_callback_been_called = False


@httpretty.activate
def test_datafiles_upload_file_threaded_no_callback():
    # Using standard CLI runner to make sure we login successfuly as in other tests.
    runner = CliRunner()
    register_successful_login(runner)

    dataset_uuid = uuid.uuid4()
    httpretty.register_uri(
        httpretty.POST,
        ARCSECOND_API_URL_DEV + '/datasets/' + str(dataset_uuid) + '/datafiles/',
        status=201,
        body='{"result": "OK"}'
    )

    # Go for Python module tests
    datafiles_api = ArcsecondAPI.datafiles(debug=True, dataset=str(dataset_uuid))
    uploader, _ = datafiles_api.create({'file': os.path.abspath(__file__)})
    uploader.start()
    time.sleep(0.1)
    results, error = uploader.finish()

    assert results is not None
    assert error is None


@httpretty.activate
def test_datafiles_upload_file_threaded_with_callback():
    # Using standard CLI runner to make sure we login successfuly as in other tests.
    runner = CliRunner()
    register_successful_login(runner)

    dataset_uuid = uuid.uuid4()
    httpretty.register_uri(
        httpretty.POST,
        ARCSECOND_API_URL_DEV + '/datasets/' + str(dataset_uuid) + '/datafiles/',
        status=201,
        body='{"result": "OK"}'
    )

    def upload_callback(eventName, progress):
        print(eventName, progress, flush=True)
        global has_callback_been_called
        has_callback_been_called = True

    fixtures_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'fixtures')
    # Go for Python module tests
    datafiles_api = ArcsecondAPI.datafiles(debug=True, dataset=str(dataset_uuid))
    payload = {'file': os.path.join(fixtures_folder, 'file1.fits')}
    uploader, _ = datafiles_api.create(payload, callback=upload_callback)
    uploader.start()
    while uploader.is_alive():
        pass
    print(f'is alive? {uploader.is_alive()}', flush=True)
    results, error = uploader.finish()

    assert results is not None
    assert error is None
    assert has_callback_been_called is True
