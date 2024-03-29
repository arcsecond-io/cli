import json

import click

from . import __version__
from .api import ArcsecondAPI, ArcsecondError, ArcsecondConfig
from .options import State, basic_options

pass_state = click.make_pass_decorator(State, ensure=True)

VERSION_HELP_STRING = "Show the CLI version and exit."


@click.group(invoke_without_command=True)
@click.option('--version', is_flag=True, help=VERSION_HELP_STRING)
@click.option('-V', is_flag=True, help=VERSION_HELP_STRING)
@click.option('-h', is_flag=True, help="Show this message and exit.")
@click.pass_context
def main(ctx, version=False, v=False, h=False):
    if version or v:
        click.echo(__version__)
    elif ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command(help=VERSION_HELP_STRING)
def version():
    click.echo(__version__)


@main.command(help='Login to your Arcsecond account.')
@click.option('--username', required=True, nargs=1, prompt=True,
              help='Account username (without @). Primary email address is also allowed.')
@click.option('--access_key', required=True, nargs=1, prompt=True, hide_input=True,
              help='Your access key (a.k.a. API key). Visit your settings page to copy and paste it here.')
@basic_options
@pass_state
def login(state, username, access_key):
    """Login to your personal Arcsecond.io account, and retrieve the associated API key."""
    result, error = ArcsecondAPI(ArcsecondConfig(state)).login(username, access_key=access_key)
    if error:
        click.echo(str(error))


@main.command(help='Get or set the API server address (fully qualified domain name).')
@click.argument('name', required=False, nargs=1)
@click.argument('fqdn', required=False, nargs=1)
@pass_state
def api(state, name=None, fqdn=None):
    """Configure the API server address"""
    if name is None:
        name = 'main'
    # The setter below is normally handled by the option --api, but here, the DX is different,
    # because we manipulated the api and its address itself.
    state.api_name = name
    config = ArcsecondConfig(state)
    if fqdn is None:
        click.echo(f"name: {name}, fqdn: {config.api_server}")
    else:
        config.api_server = fqdn
        click.echo(f"Set fqdn: {config.api_server} to API named {name}.")


@main.command(help='Get your complete user profile.')
@basic_options
@pass_state
def me(state):
    """Fetch your complete user profile."""
    username = ArcsecondConfig(state).username or None
    if not username:
        msg = f'Invalid/missing username: {username}. Make sure to login first: $ arcsecond login'
        raise ArcsecondError(msg)
    response, error = ArcsecondAPI(ArcsecondConfig(state)).profiles.read(username)
    if error:
        click.echo(str(error))
    else:
        click.echo(json.dumps(response, indent=2))
