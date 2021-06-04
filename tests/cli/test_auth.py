import sys

import httpretty
from click.testing import CliRunner

from arcsecond import cli, config
from arcsecond.api.constants import API_AUTH_PATH_LOGIN, ARCSECOND_API_URL_DEV
from tests.utils import TEST_LOGIN_PASSWORD, TEST_LOGIN_USERNAME, prepare_successful_login

python_version = sys.version_info.major


@httpretty.activate
def test_login_unknown_credentials():
    runner = CliRunner()
    httpretty.register_uri(
        httpretty.POST,
        ARCSECOND_API_URL_DEV + API_AUTH_PATH_LOGIN,
        status=401,
        body='{"detail": "Unable to log in with provided credentials."}'
    )
    result = runner.invoke(cli.login, ['--debug', '--test'], input='dummy\ndummy')
    assert result.exit_code == 0 and not result.exception
    assert 'Unable to log in with provided credentials.' in result.output


@httpretty.activate
def test_login_invalid_parameters():
    runner = CliRunner()
    httpretty.register_uri(
        httpretty.POST,
        ARCSECOND_API_URL_DEV + API_AUTH_PATH_LOGIN,
        status=401,
        body='{"detail": "This field may not be blank."}'
    )
    for input in [' \n ', ' \ndummy', 'dummy\n ']:
        result = runner.invoke(cli.login, ['--debug', '--test'], input=input)
        assert result.exit_code == 0 and not result.exception
        assert 'non_field_errors' in result.output or 'This field may not be blank' in result.output


@httpretty.activate
def test_login_valid_parameters_with_confirmation():
    config.config_file_clear_api_key('test')
    assert config.config_file_read_api_key('test') is None
    runner = CliRunner(echo_stdin=True)
    prepare_successful_login()
    result = runner.invoke(cli.login,
                           ['--debug', '--test'],
                           input=TEST_LOGIN_USERNAME + '\n' + TEST_LOGIN_PASSWORD + '\nY')
    assert result.exit_code == 0 and not result.exception
    assert config.config_file_read_api_key('test') is not None


@httpretty.activate
def test_login_valid_parameters_without_confirmation():
    config.config_file_clear_api_key('test')
    assert config.config_file_read_api_key('test') is None
    runner = CliRunner(echo_stdin=True)
    prepare_successful_login()
    result = runner.invoke(cli.login,
                           ['--debug', '--test'],
                           input=TEST_LOGIN_USERNAME + '\n' + TEST_LOGIN_PASSWORD + '\nN')
    assert result.exit_code == 0 and not result.exception
    assert config.config_file_read_api_key('test') is None


def test_register_refuse_agreement(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr('builtins.input', lambda x: "")
    result = runner.invoke(cli.register, ['--debug', '--test'], input='test\ntest@test.com\ntest1\ntest1')
    assert result.exit_code != 0 and result.exception

# I can't find a way to use httpretyy.activate and monkeypatch at the same time.
# @httpretty.activate
# def test_register_agree_on_agreement(monkeypatch):
#     runner = CliRunner()
#     httpretty.register_uri(
#         httpretty.POST,
#         ARCSECOND_API_URL_DEV + API_AUTH_PATH_REGISTER,
#         status=201,
#         body='{"key": "dummy_api_key."}'
#     )
#     monkeypatch.setattr('builtins.input', lambda x: "y")
#     result = runner.invoke(cli.register, ['--debug', '--test'], input='test16\ntest@test.com\ntest1\ntest1')
#     assert result.exit_code == 0 and not result.exception
