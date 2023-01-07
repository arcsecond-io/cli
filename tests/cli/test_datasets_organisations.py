from unittest import TestCase

import httpretty
import pytest
from click.testing import CliRunner

from arcsecond import cli
from arcsecond.api.error import ArcsecondError
from arcsecond.config import config_file_clear_section
from tests.utils import make_successful_login, mock_http_get, mock_http_post


@pytest.mark.skip
class DatasetsInOrganisationsTestCase(TestCase):
    def setUp(self):
        config_file_clear_section('test')
        httpretty.enable()

    def tearDown(self):
        httpretty.disable()

    def test_datasets_list_unlogged(self):
        """As a simple user, I must not be able to access the list of datasets of an organisation."""
        runner = CliRunner()
        make_successful_login(runner)
        result = runner.invoke(cli.datasets, ['--organisation', 'saao', '--api', 'test'])
        assert result.exit_code != 0 and isinstance(result.exception, ArcsecondError)

    def test_organisation_GET_datasets_list_logged_but_wrong_organisation(self):
        """No matter role I have, accessing an unknown organisation must fail."""
        runner = CliRunner()
        make_successful_login(runner, 'saao', 'superadmin')
        result = runner.invoke(cli.datasets, ['--organisation', 'dummy', '--api', 'test'])
        assert result.exit_code != 0 and isinstance(result.exception, ArcsecondError)

    def test_organisation_GET_datasets_list_valid_role(self):
        """As a SAAO member, I must be able to access the list of datasets."""
        runner = CliRunner()
        make_successful_login(runner, 'saao', 'member')
        mock_http_get('/saao/datasets/', '[]')
        result = runner.invoke(cli.datasets, ['--organisation', 'saao', '--api', 'test'])
        assert result.exit_code == 0 and not result.exception

    def test_organisation_POST_datasets_list_valid_member_role(self):
        """As a SAAO superadmin, I must be able to create a dataset."""
        runner = CliRunner()
        make_successful_login(runner, 'saao', 'member')
        mock_http_post('/saao/datasets/', '[]')
        result = runner.invoke(cli.datasets, ['create', '--organisation', 'saao', '--api', 'test'])
        assert result.exit_code == 0 and not result.exception
