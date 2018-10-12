import re
import pytest
import httpretty
from click.testing import CliRunner
from arcsecond import cli, ArcsecondConnectionError
from arcsecond.api._constants import (API_AUTH_PATH_LOGIN,
                                      ARCSECOND_API_URL_DEV,
                                      ARCSECOND_API_URL_PROD)


@pytest.fixture
def runner():
    return CliRunner()


def test_cli_basic(runner):
    result = runner.invoke(cli.main)
    assert result.exit_code == 0 and not result.exception
    # Here 'arcsecond' is replaced by 'main' ??
    assert 'Usage: main [OPTIONS] COMMAND [ARGS]' in result.output


def test_cli_version(runner):
    result = runner.invoke(cli.main, ['-V'])
    assert result.exit_code == 0 and not result.exception
    assert re.match('[0-9].[0-9].[0-9]', result.output)
    result = runner.invoke(cli.main, ['--version'])
    assert result.exit_code == 0 and not result.exception
    assert re.match('[0-9].[0-9].[0-9]', result.output)
    result = runner.invoke(cli.version)
    assert result.exit_code == 0 and not result.exception
    assert re.match('[0-9].[0-9].[0-9]', result.output)


def test_login_no_server(runner):
    result = runner.invoke(cli.login, ['-d'], input='dummy\ndummy')
    assert result.exit_code != 0
    assert isinstance(result.exception, ArcsecondConnectionError)


@httpretty.activate
def test_login_unknown_credentials(runner):
    httpretty.register_uri(
        httpretty.POST,
        ARCSECOND_API_URL_DEV + API_AUTH_PATH_LOGIN,
        status=401,
        body='{"detail": "Unable to log in with provided credentials."}'
    )
    httpretty.register_uri(
        httpretty.POST,
        ARCSECOND_API_URL_PROD + API_AUTH_PATH_LOGIN,
        status=401,
        body='{"detail": "Unable to log in with provided credentials."}'
    )
    result1 = runner.invoke(cli.login, ['-d'], input='dummy\ndummy')
    result2 = runner.invoke(cli.login, input='dummy\ndummy')
    assert result1.exit_code == 0 and not result1.exception
    assert result2.exit_code == 0 and not result2.exception
    assert 'Unable to log in with provided credentials.' in result1.output
    assert 'Unable to log in with provided credentials.' in result2.output


@httpretty.activate
def test_login_invalid_parameters(runner):
    httpretty.register_uri(
        httpretty.POST,
        ARCSECOND_API_URL_DEV + API_AUTH_PATH_LOGIN,
        status=401,
        body='{"detail": "This field may not be blank."}'
    )
    for input in [' \n ', ' \ndummy', 'dummy\n ']:
        result = runner.invoke(cli.login, ['-d'], input=input)
        assert result.exit_code == 0 and not result.exception
        assert 'non_field_errors' in result.output or 'This field may not be blank' in result.output
