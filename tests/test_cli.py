import re
from click.testing import CliRunner
from arcsecond import cli, ArcsecondConnectionError


def test_cli_basic():
    runner = CliRunner()
    result = runner.invoke(cli.main)
    assert result.exit_code == 0 and not result.exception
    # Here 'arcsecond' is replaced by 'main' ??
    assert 'Usage: main [OPTIONS] COMMAND [ARGS]' in result.output


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(cli.main, ['-V'])
    assert result.exit_code == 0 and not result.exception
    assert re.match('[0-9].[0-9].[0-9]', result.output)
    result = runner.invoke(cli.main, ['--version'])
    assert result.exit_code == 0 and not result.exception
    assert re.match('[0-9].[0-9].[0-9]', result.output)
    result = runner.invoke(cli.version)
    assert result.exit_code == 0 and not result.exception
    assert re.match('[0-9].[0-9].[0-9]', result.output)


def test_cli_global_help():
    runner = CliRunner()
    result = runner.invoke(cli.main, ['-h'])
    assert result.exit_code == 0 and not result.exception
    assert 'Usage: main [OPTIONS] COMMAND [ARGS]' in result.output
    result = runner.invoke(cli.main, ['--help'])
    assert result.exit_code == 0 and not result.exception
    assert 'Usage: main [OPTIONS] COMMAND [ARGS]' in result.output


def test_no_connection_to_server():
    runner = CliRunner()
    result = runner.invoke(cli.login, ['-d'], input='dummy\ndummy')
    assert result.exit_code != 0
    assert isinstance(result.exception, ArcsecondConnectionError)
