import click

from .api import ArcsecondAPI, ArcsecondError
from .config import config_file_read_username
from .options import AliasedGroup, State, MethodChoiceParamType, basic_options, open_options

__version__ = '0.3.5'

pass_state = click.make_pass_decorator(State, ensure=True)


@click.group(cls=AliasedGroup, invoke_without_command=True)
@click.option('-v', '--version', is_flag=True, help="Show the CLI version and exit.")
@click.pass_context
def main(ctx, version=False):
    if ctx.invoked_subcommand is None and version:
        click.echo(__version__)


@main.command(help='Register for a free personnal Arcsecond.io account, and retrieve the API key.')
@click.option('--username', required=True, nargs=1, prompt=True)
@click.option('--email', required=True, nargs=1, prompt=True)
@click.option('--password1', required=True, nargs=1, prompt=True, hide_input=True)
@click.option('--password2', required=True, nargs=1, prompt=True, hide_input=True)
@basic_options
@pass_state
def register(state, username, email, password1, password2):
    ArcsecondAPI(state).register(username, email, password1, password2)


@main.command(help='Login to your personnal Arcsecond.io account, and retrieve the API key.')
@click.option('--username', required=True, nargs=1, prompt=True)
@click.option('--password', required=True, nargs=1, prompt=True, hide_input=True)
@basic_options
@pass_state
def login(state, username, password):
    ArcsecondAPI(state).login(username, password)


@main.command(help='Request your user profile.')
@open_options
@pass_state
def me(state):
    username = config_file_read_username(state.debug)
    if not username: raise ArcsecondError(
        'Invalid/missing username: {}. Make sure to login first: $ arcsecond login'.format(username))
    ArcsecondAPI(state).read(ArcsecondAPI.ENDPOINT_ME, username)


@main.command(help='Request any user profile (in the /profiles/<username>/ API endpoint)')
@click.argument('username', required=True, nargs=-1)
@open_options
@pass_state
def profiles(state, username):
    ArcsecondAPI(state).read(ArcsecondAPI.ENDPOINT_PROFILE, username)


@main.command(help='Request object (in the /objects/<name>/ API endpoint)')
@click.argument('name', required=True, nargs=-1)
@open_options
@pass_state
def objects(state, name):
    ArcsecondAPI(state).read(ArcsecondAPI.ENDPOINT_OBJECTS, name)


@main.command(help='Request exoplanet (in the /exoplanets/<name>/ API endpoint)')
@click.argument('name', required=True, nargs=-1)
@open_options
@pass_state
def exoplanets(state, name):
    ArcsecondAPI(state).read(ArcsecondAPI.ENDPOINT_EXOPLANETS, name)


@main.command(help='Request the list of object finding charts (in the /findingcharts/<name>/ API endpoint)')
@click.argument('name', required=True, nargs=-1)
@open_options
@pass_state
def findingcharts(state, name):
    ArcsecondAPI(state).read(ArcsecondAPI.ENDPOINT_FINDINGCHARTS, name)


@main.command(help='Play with the of observing activities (in the /activities/ API endpoint)')
@click.argument('method', required=False, nargs=1, type=MethodChoiceParamType(), default='read')
@click.argument('pk', required=False, nargs=1)
@click.option('--title', required=False, nargs=1)
@click.option('--content', required=False, nargs=1)
@click.option('--observing_site', required=False, nargs=1)
@click.option('--telescope', required=False, nargs=1)
@click.option('--instrument', required=False, nargs=1)
@click.option('--target', required=False, nargs=1)
@click.option('--organisation', required=False, nargs=1)
@click.option('--collaboration', required=False, nargs=1)
@open_options
@pass_state
def activities(state, method, pk, **kwargs):
    if method == 'read' and pk is None:
        ArcsecondAPI(state).list(ArcsecondAPI.ENDPOINT_ACTIVITIES)
    elif method == 'read' and pk is not None:
        ArcsecondAPI(state).read(ArcsecondAPI.ENDPOINT_ACTIVITIES, pk)
    elif method == 'create':
        ArcsecondAPI(state).create(ArcsecondAPI.ENDPOINT_ACTIVITIES, kwargs)
    elif method == 'update':
        ArcsecondAPI(state).update(ArcsecondAPI.ENDPOINT_ACTIVITIES, pk, kwargs)
    elif method == 'delete':
        ArcsecondAPI(state).delete(ArcsecondAPI.ENDPOINT_ACTIVITIES, pk)
