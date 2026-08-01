import re

from click.testing import CliRunner

from arcsecond import cli
from tests.utils import random_string

# Click renders the usage line slightly differently across versions: a group
# that may be invoked without a subcommand prints COMMAND in 8.1 and [COMMAND]
# from 8.2 on. Match either, so a click upgrade does not fail the suite over
# punctuation.
USAGE_LINE = re.compile(r"Usage: main \[OPTIONS\] \[?COMMAND\]? \[ARGS\]")


def test_cli_basic():
    runner = CliRunner()
    result = runner.invoke(cli.main)
    assert result.exit_code == 0 and not result.exception
    # Here 'arcsecond' is replaced by 'main' ??
    assert USAGE_LINE.search(result.output)


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(cli.main, ["-V"])
    assert result.exit_code == 0 and not result.exception
    assert re.match(r"\d+\.\d+\.\d+", result.output)
    result = runner.invoke(cli.main, ["--version"])
    assert result.exit_code == 0 and not result.exception
    assert re.match(r"\d+\.\d+\.\d+", result.output)
    result = runner.invoke(cli.version)
    assert result.exit_code == 0 and not result.exception
    assert re.match(r"\d+\.\d+\.\d+", result.output)


def test_cli_global_help():
    runner = CliRunner()
    result = runner.invoke(cli.main, ["-h"])
    assert result.exit_code == 0 and not result.exception
    assert USAGE_LINE.search(result.output)
    result = runner.invoke(cli.main, ["--help"])
    assert result.exit_code == 0 and not result.exception
    assert USAGE_LINE.search(result.output)


def test_cli_api_read():
    runner = CliRunner()
    result = runner.invoke(cli.api)
    assert result.exit_code == 0 and not result.exception
    assert "All registered API servers:" in result.output


def test_cli_api_write_error():
    runner = CliRunner()
    result = runner.invoke(cli.api, ["dummy"])
    assert result.exit_code != 0 and result.exception


def test_cli_api_write_valid():
    runner = CliRunner()
    random_api_name = random_string()
    address = "http://example.com"
    result = runner.invoke(cli.api, [random_api_name, address])
    assert result.exit_code == 0 and not result.exception
    result = runner.invoke(cli.api)
    assert f"{random_api_name}: {address}" in result.output and not result.exception


def test_cli_login_access_key():
    runner = CliRunner()
    result = runner.invoke(cli.login, input="steve\naccess\n123")
    assert result.exit_code == 0 and not result.exception


def test_cli_login_upload_key():
    runner = CliRunner()
    result = runner.invoke(cli.login, input="steve\nupload\n123")
    assert result.exit_code == 0 and not result.exception
