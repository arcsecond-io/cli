import json
import os
import uuid

import httpretty
from click.testing import CliRunner

from arcsecond import cli
from arcsecond.api.constants import ARCSECOND_API_URL_DEV
from .utils import register_successful_personal_login, register_successful_organisation_login


@httpretty.activate
def test_organisations_datasets_list():
    """As a SAAO superadmin, I must be able to access the list of datasets."""
    runner = CliRunner()
    register_successful_organisation_login(runner, 'saao', 'superadmin')
    httpretty.register_uri(
        httpretty.GET,
        ARCSECOND_API_URL_DEV + '/saao/datasets/',
        status=200,
        body='[]'
    )

    result = runner.invoke(cli.datasets, ['--organisation', 'saao', '-d'])
    assert result.exit_code == 0 and not result.exception
    data = json.loads(result.output)
    assert len(data) == 0 and isinstance(data, list)

