import click

from .api import ArcsecondAPI, ArcsecondError
from .config import config_file_read_username
from .options import AliasedGroup, State, MethodChoiceParamType, basic_options, open_options

pass_state = click.make_pass_decorator(State, ensure=True)


@click.group(cls=AliasedGroup, invoke_without_command=True)
@click.option('-v', '--version', is_flag=True, help="Show the CLI version and exit.")
@click.pass_context
def main(ctx, version=False):
    if ctx.invoked_subcommand is None and version:
        from .__version__ import __version__
        click.echo(__version__)


@main.command(help='Register for a free personnal Arcsecond.io account, and retrieve the API key.')
@click.option('--username', required=True, nargs=1, prompt=True)
@click.option('--email', required=True, nargs=1, prompt=True)
@click.option('--password1', required=True, nargs=1, prompt=True, hide_input=True)
@click.option('--password2', required=True, nargs=1, prompt=True, hide_input=True)
@basic_options
@pass_state
def register(state, username, email, password1, password2):
    ArcsecondAPI(state=state).register(username, email, password1, password2)


@main.command(help='Login to your personnal Arcsecond.io account, and retrieve the API key.')
@click.option('--username', required=True, nargs=1, prompt=True)
@click.option('--password', required=True, nargs=1, prompt=True, hide_input=True)
@basic_options
@pass_state
def login(state, username, password):
    ArcsecondAPI(state=state).login(username, password)


@main.command(help='Request your user profile.')
@open_options
@pass_state
def me(state):
    username = config_file_read_username(state.debug)
    if not username: raise ArcsecondError(
        'Invalid/missing username: {}. Make sure to login first: $ arcsecond login'.format(username))
    ArcsecondAPI(ArcsecondAPI.ENDPOINT_ME, state).read(username)


@main.command(help='Request any user profile (in the /profiles/<username>/ API endpoint)')
@click.argument('username', required=True, nargs=-1)
@open_options
@pass_state
def profiles(state, username):
    ArcsecondAPI(ArcsecondAPI.ENDPOINT_PROFILEstate).read(username)


@main.command(help='Request object (in the /objects/<name>/ API endpoint)')
@click.argument('name', required=True, nargs=-1)
@open_options
@pass_state
def objects(state, name):
    ArcsecondAPI(ArcsecondAPI.ENDPOINT_OBJECTS, state).read(name)


@main.command(help='Request exoplanet (in the /exoplanets/<name>/ API endpoint)')
@click.argument('name', required=True, nargs=-1)
@open_options
@pass_state
def exoplanets(state, name):
    ArcsecondAPI(ArcsecondAPI.ENDPOINT_EXOPLANETS, state).read(name)


@main.command(help='Request the list of object finding charts (in the /findingcharts/<name>/ API endpoint)')
@click.argument('name', required=True, nargs=-1)
@open_options
@pass_state
def findingcharts(state, name):
    ArcsecondAPI(ArcsecondAPI.ENDPOINT_FINDINGCHARTS, state).list(name)


@main.command(help='Request the list of instruments (in the /instruments/ API endpoint)')
@open_options
@pass_state
def sites(state, name):
    ArcsecondAPI(ArcsecondAPI.ENDPOINT_OBSERVINGSITES, state).list()


@main.command(help='Request the list of instruments (in the /instruments/ API endpoint)')
@open_options
@pass_state
def instruments(state, name):
    ArcsecondAPI(ArcsecondAPI.ENDPOINT_INSTRUMENTS, state).list()


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
    api = ArcsecondAPI(ArcsecondAPI.ENDPOINT_ACTIVITIES, state)
    if method == 'create':
        api.create(kwargs)
    elif method == 'read':
        api.read(pk)  # will handle list if pk is None
    elif method == 'update':
        api.update(pk, kwargs)
    elif method == 'delete':
        api.delete(pk)
