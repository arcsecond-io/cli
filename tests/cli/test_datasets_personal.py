import json
import os
import uuid

import httpretty
import pytest
from click.testing import CliRunner

from arcsecond import cli
from arcsecond.api.constants import ARCSECOND_API_URL_DEV
from tests.utils import make_successful_login


@pytest.mark.skip
@httpretty.activate
def test_empty_datasets_list():
    runner = CliRunner()
    make_successful_login(runner)

    httpretty.register_uri(
        httpretty.GET,
        ARCSECOND_API_URL_DEV + '/datasets/',
        status=200,
        body='[]'
    )
    result = runner.invoke(cli.datasets, ['--api', 'test'])
    assert result.exit_code == 0 and not result.exception
    data = json.loads(result.output)
    assert len(data) == 0 and isinstance(data, list)


@pytest.mark.skip
@httpretty.activate
def test_datafiles_list_of_datasets():
    runner = CliRunner()
    make_successful_login(runner)

    dataset_uuid = uuid.uuid4()
    httpretty.register_uri(
        httpretty.GET,
        ARCSECOND_API_URL_DEV + '/datasets/' + str(dataset_uuid) + '/datafiles/',
        status=200,
        body='[]'
    )
    result = runner.invoke(cli.datafiles, [str(dataset_uuid), '--api', 'test'])
    assert result.exit_code == 0 and not result.exception
    data = json.loads(result.output)
    assert len(data) == 0 and isinstance(data, list)


@pytest.mark.skip
@httpretty.activate
def test_datafiles_create_with_file():
    runner = CliRunner()
    make_successful_login(runner)

    dataset_uuid = uuid.uuid4()
    httpretty.register_uri(
        httpretty.POST,
        ARCSECOND_API_URL_DEV + '/datasets/' + str(dataset_uuid) + '/datafiles/',
        status=201,
        body='{"result": "OK"}'
    )
    result = runner.invoke(cli.datafiles,
                           [str(dataset_uuid), 'create', '--file', os.path.abspath(__file__), '--api', 'test'])
    assert result.exit_code == 0 and not result.exception
    data = json.loads(result.output)
    assert data['result'] == 'OK'
