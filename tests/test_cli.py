import re
import pytest
from click.testing import CliRunner
from arcsecond import cli


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


def test_login_unknown_credentials(runner):
    result = runner.invoke(cli.login, ['-d'], input='dummy\ndummy')
    assert result.exit_code == 0 and not result.exception
    assert 'Unable to log in with provided credentials.' in result.output


def test_login_invalid_parameters(runner):
    for input in [' \n ', ' \ndummy', 'dummy\n ']:
        result = runner.invoke(cli.login, ['-d'], input=input)
        assert result.exit_code == 0 and not result.exception
        assert 'non_field_errors' in result.output or 'This field may not be blank' in result.output
