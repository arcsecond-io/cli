import httpretty
from click.testing import CliRunner
from arcsecond import cli, ArcsecondConnectionError
from arcsecond.api.constants import API_AUTH_PATH_LOGIN, ARCSECOND_API_URL_DEV


@httpretty.activate
def test_login_unknown_credentials():
    runner = CliRunner()
    httpretty.register_uri(
        httpretty.POST,
        ARCSECOND_API_URL_DEV + API_AUTH_PATH_LOGIN,
        status=401,
        body='{"detail": "Unable to log in with provided credentials."}'
    )
    result = runner.invoke(cli.login, ['-d'], input='dummy\ndummy')
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
        result = runner.invoke(cli.login, ['-d'], input=input)
        assert result.exit_code == 0 and not result.exception
        assert 'non_field_errors' in result.output or 'This field may not be blank' in result.output
