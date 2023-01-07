import click

from . import __version__
from .api import ArcsecondAPI, ArcsecondError
from .config import config_file_read_username
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


@main.command(short_help='Register a free Arcsecond account.')
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


@main.command(help='Get the list of observing sites (in the /observingsites/ API endpoint)')
@basic_options
@pass_state
def observingsites(state):
    ArcsecondAPI.observingsites(state).list()


@main.command(help='Get the list of telescopes (in the /telescopes/ API endpoint)')
@basic_options
@pass_state
def telescopes(state):
    ArcsecondAPI.telescopes(state).list()


@main.command(help='Get the list of organisations, or the details of one if a subdomain is provided.')
@click.argument('organisation', required=False, nargs=1)
@basic_options
@pass_state
def organisations(state, organisation):
    api = ArcsecondAPI.organisations(state)
    if organisation:
        api.read(organisation)
    else:
        api.list()


@main.command(help='Get the list of members of an organisation.')
@click.argument('organisation', required=True, nargs=1)
@basic_options
@pass_state
def members(state, organisation):
    ArcsecondAPI.members(state, organisation=organisation).list()


@main.command(help='Get the list of upload keys of an organisation.')
@click.argument('organisation', required=True, nargs=1)
@basic_options
@pass_state
def uploadkeys(state, organisation):
    ArcsecondAPI.uploadkeys(state, organisation=organisation).list()

# @main.command(help='Access and modify the observing activities (in the /activities/ API endpoint)')
# @click.argument('method', required=False, nargs=1, type=MethodChoiceParamType(), default='read')
# @click.argument('pk', required=False, nargs=1)
# @click.option('--title', required=False, nargs=1, help="The activity title. Optional.")
# @click.option('--content', required=False, nargs=1, help="The activity content body. Optional.")
# @click.option('--observing_site', required=False, nargs=1, help="The observing site UUID. Optional.")
# @click.option('--telescope', required=False, nargs=1, help="The telescope UUID. Optional.")
# @click.option('--instrument', required=False, nargs=1, help="The instrument UUID. Optional.")
# @click.option('--target_name', required=False, nargs=1, help="The target name. Optional")
# @click.option('--coordinates',
#               required=False,
#               nargs=1,
#               help="The target coordinates. Optional. Decimal degrees, format: coordinates=RA,Dec")
# @click.option('--organisation', required=False, nargs=1, help="Your organisation acronym (for organisations). Optional")
# @click.option('--collaboration', required=False, nargs=1, help="Your collaboration acronym. Optional")
# @basic_options
# @pass_state
# def activities(state, method, pk, **kwargs):
#     api = ArcsecondAPI.activities(state)
#     if method == 'create':
#         kwargs.update(coordinates=make_coords_dict(kwargs))
#         api.create(kwargs)  # the kwargs dict is the payload!
#     elif method == 'read':
#         api.read(pk)  # will handle list if pk is None
#     elif method == 'update':
#         api.update(pk, kwargs)
#     elif method == 'delete':
#         api.delete(pk)
#     else:
#         api.list()
