import click

from . import __version__
from .api import ArcsecondAPI, ArcsecondError
from .api.helpers import make_coords_dict
from .config import config_file_read_username
from .options import MethodChoiceParamType, State, basic_options, open_options, organisation_options

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


@main.command(help='Login to a personal Arcsecond.io account')
@click.option('--username', required=True, nargs=1, prompt=True)
@click.option('--password', required=True, nargs=1, prompt=True, hide_input=True)
@click.option('--organisation', required=False, help='organisation subdomain')
@basic_options
@pass_state
def login(state, username, password, organisation=None):
    """Login to your personal Arcsecond.io account, and retrieve the associated API key."""
    ArcsecondAPI.login(username, password, organisation, state)


@main.command(help='Fetch your complete user profile.')
@open_options
@pass_state
def me(state):
    """Fetch your complete user profile."""
    username = config_file_read_username(state.debug)
    if not username:
        msg = 'Invalid/missing username: {}. Make sure to login first: $ arcsecond login'.format(username)
        raise ArcsecondError(msg)
    ArcsecondAPI(ArcsecondAPI.ENDPOINT_ME, state).read(username)


@main.command(help='List the existing profiles.')
@click.argument('username', required=False, nargs=-1)
@open_options
@pass_state
def profiles(state, username):
    """List the existing user profiles.

    Only public information is provided: username, first and last name, and
    the membership_date.

    Results are paginated.
    """
    ArcsecondAPI(ArcsecondAPI.ENDPOINT_PROFILES, state).read(username)


@main.command(help='Get an object.')
@click.argument('name', required=True, nargs=-1)
@open_options
@pass_state
def objects(state, name):
    """Using the /objects/<object name>/ API endpoint, get the object
    information from the CDS in Strasbourg.

    The NED information, as well as being able to choose the source
    will be implemented in the future.
    """
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


@main.command(help='Request the list of observing sites (in the /observingsites/ API endpoint)')
@open_options
@pass_state
def sites(state):
    ArcsecondAPI(ArcsecondAPI.ENDPOINT_OBSERVINGSITES, state).list()


@main.command(help='Request the list of telescopes (in the /telescopes/ API endpoint)')
@open_options
@pass_state
def telescopes(state):
    ArcsecondAPI(ArcsecondAPI.ENDPOINT_TELESCOPES, state).list()


@main.command(help='Request the list of instruments (in the /instruments/ API endpoint)')
@open_options
@pass_state
def instruments(state, name):
    ArcsecondAPI(ArcsecondAPI.ENDPOINT_INSTRUMENTS, state).list()


@main.command(help='Request the list of observing runs (in the /observingruns/ API endpoint)')
@open_options
@pass_state
def runs(state):
    ArcsecondAPI(ArcsecondAPI.ENDPOINT_OBSERVINGRUNS, state).list()


@main.command(help='Request the list of telescopes (in the /nightlogs/ API endpoint)')
@open_options
@pass_state
def logs(state):
    ArcsecondAPI(ArcsecondAPI.ENDPOINT_NIGHTLOGS, state).list()


@main.command(help='Play with the observing activities (in the /activities/ API endpoint)')
@click.argument('method', required=False, nargs=1, type=MethodChoiceParamType(), default='read')
@click.argument('pk', required=False, nargs=1)
@click.option('--title', required=False, nargs=1, help="The activity title. Optional.")
@click.option('--content', required=False, nargs=1, help="The activity content body. Optional.")
@click.option('--observing_site', required=False, nargs=1, help="The observing site UUID. Optional.")
@click.option('--telescope', required=False, nargs=1, help="The telescope UUID. Optional.")
@click.option('--instrument', required=False, nargs=1, help="The instrument UUID. Optional.")
@click.option('--target_name', required=False, nargs=1, help="The target name. Optional")
@click.option('--coordinates',
              required=False,
              nargs=1,
              help="The target coordinates. Optional. Decimal degrees, format: coordinates=RA,Dec")
@click.option('--organisation', required=False, nargs=1, help="Your organisation acronym (for organisations). Optional")
@click.option('--collaboration', required=False, nargs=1, help="Your collaboration acronym. Optional")
@open_options
@pass_state
def activities(state, method, pk, **kwargs):
    api = ArcsecondAPI(ArcsecondAPI.ENDPOINT_ACTIVITIES, state)
    if method == 'create':
        kwargs.update(coordinates=make_coords_dict(kwargs))
        api.create(kwargs)
    elif method == 'read':
        api.read(pk)  # will handle list if pk is None
    elif method == 'update':
        api.update(pk, kwargs)
    elif method == 'delete':
        api.delete(pk)
    else:
        api.list()


@main.command(help='Play with the datasets (in the /datasets/ API endpoint)')
@click.argument('method', required=False, nargs=1, type=MethodChoiceParamType(), default='read')
@click.argument('uuid', required=False, nargs=1)
@click.option('--name', required=False, nargs=1, help="The dataset name.")
@organisation_options
@pass_state
def datasets(state, method, uuid, **kwargs):
    api = ArcsecondAPI(ArcsecondAPI.ENDPOINT_DATASETS, state)
    if method == 'create':
        api.create(kwargs)
    elif method == 'read':
        api.read(uuid)  # will handle list if pk is None
    elif method == 'update':
        api.update(uuid, kwargs)
    elif method == 'delete':
        api.delete(uuid)
    else:
        api.list()


@main.command(help='Read and write FITS files')
@click.argument('dataset', required=True, nargs=1)
@click.argument('method', required=False, nargs=1, type=MethodChoiceParamType(), default='read')
@click.argument('pk', required=False, nargs=1)
@click.option('--file', required=False, nargs=1, help="The FITS file to upload.")
@organisation_options
@pass_state
def fitsfiles(state, dataset, method, pk, **kwargs):
    """Requests the list of FITS files associated with a given dataset.

    The UUID of the datasets must be provided. See arcsecond datasets to list all datasets (private).

    When the method is either 'create' or 'update', a file can be uploaded, with the --file option.
    """
    if state.organisation:
        # If organisation is provided as argument, don't put in payload too!
        kwargs.pop('organisation')
    api = ArcsecondAPI(ArcsecondAPI.ENDPOINT_FITSFILES, state=state, dataset=dataset)
    if method == 'create':
        api.create(kwargs)
    elif method == 'read':
        api.read(pk)  # will handle list if pk is None
    elif method == 'update':
        api.update(pk, kwargs)
    elif method == 'delete':
        api.delete(pk)
    else:
        api.list()


@main.command(help='Read satellites')
@click.argument('catalogue_number', required=False, nargs=1)
@basic_options
@pass_state
def satellites(state, catalogue_number):
    """Request the list of satellites, or the details of one (in the /satellites/ API endpoint).

    If a catalogue_number is provided, only the info of that specific satellite is returned.
    If not, the wole list of available satellites is returned.

    Data is extracted from celestrak.com.
    """
    # If catalogue_number is None, ArcsecondAPI fallback to .list()
    ArcsecondAPI(ArcsecondAPI.ENDPOINT_SATELLITES, state).read(catalogue_number)


@main.command(help='Read telegrams (ATel)')
@click.argument('identifier', required=False, nargs=1)
@basic_options
@pass_state
def telegrams(state, identifier):
    """Request the list of telegrams from ATel, or the details of one (in the /telegrams/ATel/ API endpoint).

    The other sources of telegrams will be added in the future.
    """
    # If catalogue_number is None, ArcsecondAPI fallback to .list()
    ArcsecondAPI(ArcsecondAPI.ENDPOINT_TELEGRAMS_ATEL, state).read(identifier)
