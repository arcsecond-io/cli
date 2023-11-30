import click

from . import __version__
from .api import ArcsecondAPI, ArcsecondError, Config
from .hosting import run_arcsecond, stop_arcsecond, get_arcsecond_status
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
    ArcsecondAPI(state).register(username, email, password1, password2)


@main.command(help='Login to an Arcsecond account.')
@click.option('--username', required=True, nargs=1, prompt=True,
              help='Account username (without @). Primary email address is also allowed.')
@click.option('--password', required=True, nargs=1, prompt=True, hide_input=True,
              help='Account password. It will be transmitted encrypted.')
@basic_options
@pass_state
def login(state, username, password):
    """Login to your personal Arcsecond.io account, and retrieve the associated API key."""
    msg = 'Logging in will fetch and store your full-access API key in ~/config/arcsecond/config.ini. '
    msg += 'Make sure you are on a secure computer.'
    if click.confirm(msg, default=True):
        ArcsecondAPI(state).login(username, password)
    else:
        click.echo('Stopping without logging in.')


@main.command(help='Get or set the API server address (fully qualified domain name).')
@click.argument('name', required=False, nargs=1)
@click.argument('fqdn', required=False, nargs=1)
@pass_state
def api(state, name=None, fqdn=None):
    """Configure the API server address"""
    if name is None:
        name = 'main'
    state.api_name = name
    _api = ArcsecondAPI(state)
    if fqdn is None:
        click.echo(f"name: {name}, fqdn: {_api.get_api_name()}")
    else:
        _api.set_api_name(fqdn)


@main.command(help='Get your complete user profile.')
@basic_options
@pass_state
def me(state):
    """Fetch your complete user profile."""
    username = Config(state.config_section).username or None
    if not username:
        msg = f'Invalid/missing username: {username}. Make sure to login first: $ arcsecond login'
        raise ArcsecondError(msg)
    ArcsecondAPI(state).profiles.read(username)


######################## SELF-HOSTING ##################################################################################

@main.command(name='try', help='Try a full-featured demo of a self-hosted Arcsecond instance.')
@click.option('-s', '--skip-setup', required=False, is_flag=True, help="Skip the setup.")
@pass_state
def do_try(state, skip_setup=False):
    run_arcsecond(state, do_try=True, skip_setup=skip_setup)


@main.command(name='install', help='Install a true self-hosting Arcsecond instance.')
@click.option('-s', '--skip-setup', required=False, is_flag=True, help="Skip the setup.")
@pass_state
def do_install(state, skip_setup=False):
    run_arcsecond(state, do_try=False, skip_setup=skip_setup)


@main.command(name='stop', help='Stop the running self-hosted Arcsecond instance.')
@pass_state
def do_stop(state):
    stop_arcsecond()


@main.command(name='status', help='Stop the running self-hosted Arcsecond instance.')
@pass_state
def do_get_status(state):
    get_arcsecond_status()
