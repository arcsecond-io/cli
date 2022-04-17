import click

from . import __version__
from .api import ArcsecondAPI, ArcsecondError
from .config import config_file_read_username
from .hosting import run_arcsecond, stop_arcsecond, get_arcsecond_status
from .options import (
    MethodChoiceParamType,
    State,
    basic_options,
    organisation_options
)

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


######################## PERSONAL ACCOUNT ##############################################################################

@main.command(short_help='Register a free Arcsecond.io account.')
@click.option('--username', required=True, nargs=1, prompt=True)
@click.option('--email', required=True, nargs=1, prompt=True)
@click.option('--password1', required=True, nargs=1, prompt=True, hide_input=True)
@click.option('--password2', required=True, nargs=1, prompt=True, hide_input=True)
@basic_options
@pass_state
def register(state, username, email, password1, password2):
    """Register for a free personal Arcsecond.io account, and retrieve the associated API key."""
    ArcsecondAPI.register(username, email, password1, password2, state)


@main.command(help='Login to an Arcsecond account.')
@click.option('--username', required=True, nargs=1, prompt=True,
              help='Account username (without @). Primary email address is also allowed.')
@click.option('--password', required=True, nargs=1, prompt=True, hide_input=True,
              help='Account password. It will be transmitted encrypted.')
@click.option('--organisation', required=False,
              help='An organisation subdomain. If provided, shared keys will also be fetched.')
@basic_options
@pass_state
def login(state, username, password, organisation=None):
    """Login to your personal Arcsecond.io account, and retrieve the associated API key."""
    msg = 'Logging in will fetch and store your full-access API key in ~/config/arcsecond/config.ini. '
    msg += 'Make sure you are on a secured computer.'
    if click.confirm(msg, default=True):
        ArcsecondAPI.login(username, password, state, organisation, api_key=True)
    else:
        click.echo('Stopping without logging in.')


@main.command(help='Configure the API server address.')
@click.argument('name', required=False, nargs=1)
@click.argument('address', required=False, nargs=1)
@pass_state
def api(state, name=None, address=None):
    """Configure the API server address"""
    if name is None:
        name = 'main'
    state.api_name = name
    if address is None:
        print(ArcsecondAPI.get_api_name(state))
    else:
        ArcsecondAPI.set_api_name(address, state)


@main.command(help='Get your complete user profile.')
@basic_options
@pass_state
def me(state):
    """Fetch your complete user profile."""
    username = config_file_read_username(state.config_section)
    if not username:
        msg = f'Invalid/missing username: {username}. Make sure to login first: $ arcsecond login'
        raise ArcsecondError(msg)
    ArcsecondAPI.me(state).read(username)


######################## SELF-HOSTING ##################################################################################

@main.command(name='try', help='Try a full-featured demo of a self-hosted Arcsecond instance.')
@click.option('-s', '--skip-setup', required=False, is_flag=True, help="Skip the setup.")
@pass_state
def do_try(state, skip_setup=False):
    run_arcsecond(do_try=True, skip_setup=skip_setup)


@main.command(name='install', help='Install a true self-hosting Arcsecond instance.')
@click.option('-s', '--skip-setup', required=False, is_flag=True, help="Skip the setup.")
@pass_state
def do_install(state, skip_setup=False):
    run_arcsecond(do_try=False, skip_setup=skip_setup)


@main.command(name='stop', help='Stop the running self-hosted Arcsecond instance.')
@pass_state
def do_stop(state):
    stop_arcsecond()


@main.command(name='status', help='Stop the running self-hosted Arcsecond instance.')
@pass_state
def do_get_status(state):
    get_arcsecond_status()


######################## ORGANISATION MANAGEMENT #######################################################################

@main.command(help='Request the list of organisations, or the details of one if a subdomain is provided.')
@click.argument('organisation', required=False, nargs=1)
@basic_options
@pass_state
def organisations(state, organisation):
    api = ArcsecondAPI.organisations(state)
    if organisation:
        api.read(organisation)
    else:
        api.list()


@main.command(help='Request the list of members of an organisation.')
@click.argument('organisation', required=True, nargs=1)
@basic_options
@pass_state
def members(state, organisation):
    ArcsecondAPI.members(state, organisation=organisation).list()


@main.command(help='Request the list of upload keys of an organisation.')
@click.argument('organisation', required=True, nargs=1)
@basic_options
@pass_state
def uploadkeys(state, organisation):
    ArcsecondAPI.uploadkeys(state, organisation=organisation).list()

