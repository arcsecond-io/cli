import json
import os
import uuid

import httpretty
from click.testing import CliRunner

from arcsecond import cli
from arcsecond.api.constants import ARCSECOND_API_URL_DEV
from tests.utils import register_successful_login


@httpretty.activate
def test_empty_datasets_list():
    runner = CliRunner()
    register_successful_login(runner)

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
def test_datafiles_list_of_datasets():
    runner = CliRunner()
    register_successful_login(runner)

    dataset_uuid = uuid.uuid4()
    httpretty.register_uri(
        httpretty.GET,
        ARCSECOND_API_URL_DEV + '/datasets/' + str(dataset_uuid) + '/datafiles/',
        status=200,
        body='[]'
    )
    result = runner.invoke(cli.datafiles, [str(dataset_uuid), '-d'])
    assert result.exit_code == 0 and not result.exception
    data = json.loads(result.output)
    assert len(data) == 0 and isinstance(data, list)


@httpretty.activate
def test_datafiles_create_with_file():
    runner = CliRunner()
    register_successful_login(runner)

    dataset_uuid = uuid.uuid4()
    httpretty.register_uri(
        httpretty.POST,
        ARCSECOND_API_URL_DEV + '/datasets/' + str(dataset_uuid) + '/datafiles/',
        status=201,
        body='{"result": "OK"}'
    )
    result = runner.invoke(cli.datafiles, [str(dataset_uuid), 'create', '--file', os.path.abspath(__file__), '-d'])
    assert result.exit_code == 0 and not result.exception
    data = json.loads(result.output)
    assert data['result'] == 'OK'
