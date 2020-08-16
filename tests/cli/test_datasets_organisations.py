import httpretty
from click.testing import CliRunner
from unittest import TestCase

from arcsecond import cli
from arcsecond.api.error import ArcsecondError
from arcsecond.config import config_file_clear_section

from tests.utils import (register_successful_login,
                         register_successful_login,
                         mock_http_get,
                         mock_http_post)


class DatasetsInOrganisationsTestCase(TestCase):
    def setUp(self):
        config_file_clear_section('debug')
        httpretty.enable()

    def tearDown(self):
        httpretty.disable()

    def test_datasets_list_unlogged(self):
        """As a simple user, I must not be able to access the list of datasets of an organisation."""
        runner = CliRunner()
        register_successful_login(runner)
        result = runner.invoke(cli.datasets, ['--organisation', 'saao', '-d'])
        assert result.exit_code != 0 and isinstance(result.exception, ArcsecondError)

    def test_organisation_GET_datasets_list_logged_but_wrong_organisation(self):
        """No matter role I have, accessing an unknown organisation must fail."""
        runner = CliRunner()
        register_successful_login(runner, 'saao', 'superadmin')
        result = runner.invoke(cli.datasets, ['--organisation', 'dummy', '-d'])
        assert result.exit_code != 0 and isinstance(result.exception, ArcsecondError)

    def test_organisation_GET_datasets_list_valid_role(self):
        """As a SAAO superadmin, I must be able to access the list of datasets."""
        runner = CliRunner()
        register_successful_login(runner, 'saao', 'superadmin')
        mock_http_get('/saao/datasets/', '[]')
        result = runner.invoke(cli.datasets, ['--organisation', 'saao', '-d'])
        assert result.exit_code == 0 and not result.exception

    def test_organisation_POST_datasets_list_valid_superadmin_role(self):
        """As a SAAO superadmin, I must be able to create a dataset."""
        runner = CliRunner()
        register_successful_login(runner, 'saao', 'superadmin')
        mock_http_post('/saao/datasets/', '[]')
        result = runner.invoke(cli.datasets, ['create', '--organisation', 'saao', '-d'])
        assert result.exit_code == 0 and not result.exception

    def test_organisation_POST_datasets_list_valid_admin_role(self):
        """As a SAAO admin, I must be able to create a dataset."""
        runner = CliRunner()
        register_successful_login(runner, 'saao', 'admin')
        mock_http_post('/saao/datasets/', '[]')
        result = runner.invoke(cli.datasets, ['create', '--organisation', 'saao', '-d'])
        assert result.exit_code == 0 and not result.exception

    def test_organisation_POST_datasets_list_valid_member_role(self):
        """As a SAAO member, I must be able to create a dataset."""
        runner = CliRunner()
        register_successful_login(runner, 'saao', 'member')
        mock_http_post('/saao/datasets/', '[]')
        result = runner.invoke(cli.datasets, ['create', '--organisation', 'saao', '-d'])
        assert result.exit_code == 0 and not result.exception

    def test_organisation_POST_datasets_list_invalid_guest_role(self):
        """As a SAAO guest, I must not be able to create a dataset."""
        runner = CliRunner()
        register_successful_login(runner, 'saao', 'guest')
        mock_http_post('/saao/datasets/', '[]')
        result = runner.invoke(cli.datasets, ['create', '--organisation', 'saao', '-d'])
        assert result.exit_code != 0 and isinstance(result.exception, ArcsecondError)
