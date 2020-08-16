import httpretty
from click.testing import CliRunner
from unittest import TestCase

from arcsecond import cli, ArcsecondAPI
from arcsecond.api.error import ArcsecondError
from arcsecond.config import config_file_clear_section, config_file_save_api_key, \
    config_file_save_organisation_membership

from tests.utils import (register_successful_login,
                         register_successful_login,
                         mock_http_get,
                         mock_http_post,
                         mock_url_path)


class NightLogsInOrganisationsTestCase(TestCase):
    def setUp(self):
        config_file_clear_section('debug')
        httpretty.enable()

    def tearDown(self):
        httpretty.disable()

    def test_nightlogs_list_unlogged(self):
        """As a simple user, I must not be able to access the list of nightlogs of an organisation."""
        runner = CliRunner()
        register_successful_login(runner)
        result = runner.invoke(cli.logs, ['--organisation', 'saao', '-d'])
        assert result.exit_code != 0 and isinstance(result.exception, ArcsecondError)

    def test_organisation_GET_nightlogs_list_logged_but_wrong_organisation(self):
        """No matter role I have, accessing an unknown organisation must fail."""
        runner = CliRunner()
        register_successful_login(runner, 'saao', 'superadmin')
        result = runner.invoke(cli.logs, ['--organisation', 'dummy', '-d'])
        assert result.exit_code != 0 and isinstance(result.exception, ArcsecondError)

    def test_organisation_GET_nightlogs_list_valid_role(self):
        """As a SAAO superadmin, I must be able to access the list of nightlogs."""
        runner = CliRunner()
        register_successful_login(runner, 'saao', 'superadmin')
        mock_http_get('/saao/nightlogs/', '[]')
        result = runner.invoke(cli.logs, ['--organisation', 'saao', '-d'])
        assert result.exit_code == 0 and not result.exception

    def test_organisation_POST_nightlogs_list_valid_superadmin_role(self):
        """As a SAAO superadmin, I must be able to create a nightlog."""
        runner = CliRunner()
        register_successful_login(runner, 'saao', 'superadmin')
        mock_http_post('/saao/nightlogs/', '[]')
        result = runner.invoke(cli.logs, ['create', '--organisation', 'saao', '-d'])
        assert result.exit_code == 0 and not result.exception

    def test_organisation_POST_nightlogs_list_valid_admin_role(self):
        """As a SAAO admin, I must be able to create a nightlog."""
        runner = CliRunner()
        register_successful_login(runner, 'saao', 'admin')
        mock_http_post('/saao/nightlogs/', '[]')
        result = runner.invoke(cli.logs, ['create', '--organisation', 'saao', '-d'])
        assert result.exit_code == 0 and not result.exception

    def test_organisation_POST_nightlogs_list_valid_member_role(self):
        """As a SAAO member, I must be able to create a nightlog."""
        runner = CliRunner()
        register_successful_login(runner, 'saao', 'member')
        mock_http_post('/saao/nightlogs/', '[]')
        result = runner.invoke(cli.logs, ['create', '--organisation', 'saao', '-d'])
        assert result.exit_code == 0 and not result.exception

    def test_organisation_POST_nightlogs_list_invalid_guest_role(self):
        """As a SAAO guest, I must not be able to create a nightlog."""
        runner = CliRunner()
        register_successful_login(runner, 'saao', 'guest')
        mock_http_post('/saao/nightlogs/', '[]')
        result = runner.invoke(cli.logs, ['create', '--organisation', 'saao', '-d'])
        assert result.exit_code != 0 and isinstance(result.exception, ArcsecondError)


class NightLogsInOrganisationsModuleTestCase(TestCase):
    def setUp(self):
        config_file_clear_section('debug')
        config_file_save_api_key('11223344556677889900', 'cedric', section='test')
        config_file_save_organisation_membership('saao', 'superadmin', section='test')
        httpretty.enable()

    def tearDown(self):
        httpretty.disable()

    def test_organisation_GET_nightlogs_filtered_list_valid_member_role(self):
        """As a simple user, I must not be able to access the list of nightlogs of an organisation."""
        api = ArcsecondAPI.nightlogs(debug=True, test=True, organisation='saao')
        mock_url_path(httpretty.GET, '/saao/nightlogs/', query='', body='[{uuid: "112233", name:"dummy"}]', status=200)
        mock_url_path(httpretty.GET, '/saao/nightlogs/', query='?date=2020-03-28', body='[]', status=200)
        logs, error = api.list(date='2020-03-28')
        assert logs == []
        assert error is None
