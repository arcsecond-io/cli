import uuid
import os
import httpretty
import json
from click.testing import CliRunner
from arcsecond import cli, ArcsecondConnectionError
from arcsecond.api.constants import API_AUTH_PATH_LOGIN, ARCSECOND_API_URL_DEV


@httpretty.activate
def test_empty_datasets_list():
    runner = CliRunner()
    httpretty.register_uri(
        httpretty.GET,
        ARCSECOND_API_URL_DEV + '/datasets/',
        status=200,
        body='[]'
    )
    result = runner.invoke(cli.datasets, ['-d'])
    assert result.exit_code == 0 and not result.exception
    data = json.loads(result.output)
    assert len(data) == 0 and isinstance(data, list)


@httpretty.activate
def test_fitsfiles_list_of_datasets():
    runner = CliRunner()
    dataset_uuid = uuid.uuid4()
    httpretty.register_uri(
        httpretty.GET,
        ARCSECOND_API_URL_DEV + '/datasets/' + str(dataset_uuid) + '/fitsfiles/',
        status=200,
        body='[]'
    )
    result = runner.invoke(cli.fitsfiles, [str(dataset_uuid), '-d'])
    assert result.exit_code == 0 and not result.exception
    data = json.loads(result.output)
    assert len(data) == 0 and isinstance(data, list)


@httpretty.activate
def test_fitsfiles_create_with_file():
    runner = CliRunner()
    dataset_uuid = uuid.uuid4()
    httpretty.register_uri(
        httpretty.POST,
        ARCSECOND_API_URL_DEV + '/datasets/' + str(dataset_uuid) + '/fitsfiles/',
        status=201,
        body='{"result": "OK"}'
    )
    result = runner.invoke(cli.fitsfiles, [str(dataset_uuid), 'create', '--file', os.path.abspath(__file__), '-d'])
    assert result.exit_code == 0 and not result.exception
    data = json.loads(result.output)
    assert data['result'] == 'OK'
