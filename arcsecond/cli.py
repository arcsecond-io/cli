import click

from .api import API
from .config import config_file_read_username
from .options import AliasedGroup, State, basic_options, open_options

__version__ = '0.3.0'

pass_state = click.make_pass_decorator(State, ensure=True)


@click.group(cls=AliasedGroup, invoke_without_command=True)
@click.option('-v', '--version', is_flag=True, help="Show the CLI version and exit.")
@click.pass_context
def main(ctx, version=False):
    if ctx.invoked_subcommand is None and version:
        click.echo(__version__)


@main.command(help='Request object(s) information (in the /objects/<name>/ API endpoint)')
@click.argument('name', required=True, nargs=-1)
@open_options
@pass_state
def objects(state, name):
    API(state).read(API.ENDPOINT_OBJECTS, name)


@main.command(help='Request exoplanet(s) information (in the /exoplanets/<name>/ API endpoint)')
@click.argument('name', required=True, nargs=-1)
@open_options
@pass_state
def exoplanets(state, name):
    API(state).read(API.ENDPOINT_EXOPLANETS, name)


@main.command(help='Request object(s) finding charts (in the /findingcharts/<name>/ API endpoint)')
@click.argument('name', required=True, nargs=-1)
@open_options
@pass_state
def findingcharts(state, name):
    API(state).read(API.ENDPOINT_FINDINGCHARTS, name)


@main.command(help='Request user profile(s) information (in the /profiles/<username>/ API endpoint)')
@click.argument('username', required=True, nargs=-1)
@open_options
@pass_state
def profiles(state, username):
    API(state).read(API.ENDPOINT_PROFILE, username)


@main.command(help='Login to your personnal Arcsecond.io account, and retrieve the API key.')
@click.option('--username', required=True, nargs=1, prompt=True)
@click.option('--password', required=True, nargs=1, prompt=True, hide_input=True)
@basic_options
@pass_state
def login(state, username, password):
    API(state).login(username, password)


@main.command(help='Request your user profile.')
@open_options
@pass_state
def me(state):
    API(state).read(API.ENDPOINT_ME, config_file_read_username(state.debug))
