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
    ArcsecondAPI.login(username, password, state)


@main.command(help='Fetch your complete user profile.')
@open_options
@pass_state
def me(state):
    """Fetch your complete user profile."""
    username = config_file_read_username(state.config_section())
    if not username:
        msg = 'Invalid/missing username: {}. Make sure to login first: $ arcsecond login'.format(username)
        raise ArcsecondError(msg)
    ArcsecondAPI.me(state).read(username)


@main.command(help='Request an object.')
@click.argument('name', required=True, nargs=-1)
@open_options
@pass_state
def objects(state, name):
    """Using the /objects/<object name>/ API endpoint, get the object
    information from the CDS in Strasbourg.

    The NED information, as well as being able to choose the source
    will be implemented in the future.
    """
    ArcsecondAPI.objects(state).read(name)


@main.command(help='Request an exoplanet (in the /exoplanets/<name>/ API endpoint)')
@click.argument('name', required=True, nargs=-1)
@open_options
@pass_state
def exoplanets(state, name):
    ArcsecondAPI.exoplanets(state).read(name)


@main.command(help='Request the list of object finding charts (in the /findingcharts/<name>/ API endpoint)')
@click.argument('name', required=True, nargs=-1)
@open_options
@pass_state
def findingcharts(state, name):
    ArcsecondAPI.findingcharts(state).list(name=name)


@main.command(help='Request the list of observing sites (in the /observingsites/ API endpoint)')
@open_options
@pass_state
def sites(state):
    ArcsecondAPI.observingsites(state).list()


@main.command(help='Request the list of telescopes (in the /telescopes/ API endpoint)')
@open_options
@pass_state
def telescopes(state):
    ArcsecondAPI.telescopes(state).list()


@main.command(help='Request the list of instruments (in the /instruments/ API endpoint)')
@open_options
@pass_state
def instruments(state, name):
    ArcsecondAPI.instruments(state).list()


@main.command(help='Request your own list of observing runs (in the /observingruns/ API endpoint)')
@click.argument('method', required=False, nargs=1, type=MethodChoiceParamType(), default='read')
@click.argument('uuid', required=False, nargs=1, type=click.UUID)
@click.option('--name', required=False, nargs=1, help="The observing run name.")
@organisation_options
@pass_state
def runs(state, method, uuid, **kwargs):
    api = ArcsecondAPI.observingruns(state)
    if method == 'create':
        api.create(kwargs)  # the kwargs dict is the payload!
    elif method == 'read':
        api.read(uuid)  # will handle list if uuid is None
    elif method == 'update':
        api.update(uuid, kwargs)
    elif method == 'delete':
        api.delete(uuid)
    else:
        api.list()


@main.command(help='Request your own list of night logs (in the /nightlogs/ API endpoint)')
@click.argument('method', required=False, nargs=1, type=MethodChoiceParamType(), default='read')
@click.argument('uuid', required=False, nargs=1, type=click.UUID)
@click.option('--name', required=False, nargs=1, help="The log name.")
@organisation_options
@pass_state
def logs(state, method, uuid, **kwargs):
    api = ArcsecondAPI.nightlogs(state)
    if method == 'create':
        api.create(kwargs)  # the kwargs dict is the payload!
    elif method == 'read':
        api.read(uuid)  # will handle list if uuid is None
    elif method == 'update':
        api.update(uuid, kwargs)
    elif method == 'delete':
        api.delete(uuid)
    else:
        api.list()


@main.command(help='Request your own list of observations (in the /observations/ API endpoint)')
@click.argument('method', required=False, nargs=1, type=MethodChoiceParamType(), default='read')
@click.argument('uuid', required=False, nargs=1, type=click.UUID)
@organisation_options
@pass_state
def observations(state, method, uuid, **kwargs):
    api = ArcsecondAPI.observations(state)
    if method == 'create':
        api.create(kwargs)  # the kwargs dict is the payload!
    elif method == 'read':
        api.read(uuid)  # will handle list if uuid is None
    elif method == 'update':
        api.update(uuid, kwargs)
    elif method == 'delete':
        api.delete(uuid)
    else:
        api.list()


@main.command(help='Request your own list of calibrations (in the /calibrations/ API endpoint)')
@click.argument('method', required=False, nargs=1, type=MethodChoiceParamType(), default='read')
@click.argument('uuid', required=False, nargs=1, type=click.UUID)
@organisation_options
@pass_state
def calibrations(state, method, uuid, **kwargs):
    api = ArcsecondAPI.calibrations(state)
    if method == 'create':
        api.create(kwargs)  # the kwargs dict is the payload!
    elif method == 'read':
        api.read(uuid)  # will handle list if uuid is None
    elif method == 'update':
        api.update(uuid, kwargs)
    elif method == 'delete':
        api.delete(uuid)
    else:
        api.list()


@main.command(help='Access and modify the observing activities (in the /activities/ API endpoint)')
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
    api = ArcsecondAPI.activities(state)
    if method == 'create':
        kwargs.update(coordinates=make_coords_dict(kwargs))
        api.create(kwargs)  # the kwargs dict is the payload!
    elif method == 'read':
        api.read(pk)  # will handle list if pk is None
    elif method == 'update':
        api.update(pk, kwargs)
    elif method == 'delete':
        api.delete(pk)
    else:
        api.list()


@main.command(help='Access and modify your own datasets (in the /datasets/ API endpoint)')
@click.argument('method', required=False, nargs=1, type=MethodChoiceParamType(), default='read')
@click.argument('uuid', required=False, nargs=1, type=click.UUID)
@click.option('--name', required=False, nargs=1, help="The dataset name.")
@organisation_options
@pass_state
def datasets(state, method, uuid, **kwargs):
    api = ArcsecondAPI.datasets(state)
    if method == 'create':
        api.create(kwargs)  # the kwargs dict is the payload!
    elif method == 'read':
        api.read(uuid)  # will handle list if uuid is None
    elif method == 'update':
        api.update(uuid, kwargs)
    elif method == 'delete':
        api.delete(uuid)
    else:
        api.list()


@main.command(help='Access and modify your own data files')
@click.argument('dataset', required=True, nargs=1)
@click.argument('method', required=False, nargs=1, type=MethodChoiceParamType(), default='read')
@click.argument('pk', required=False, nargs=1)
@click.option('--file', required=False, nargs=1,
              help="The path to the data file to upload. Can be zipped with gzip or bzip2.")
@click.option('--instrument', required=False, nargs=1, help="The UUID of the instrument.")
@organisation_options
@pass_state
def datafiles(state, dataset, method, pk, **kwargs):
    """Requests the list of data files associated with a given dataset.

    The UUID of the datasets must be provided. See arcsecond datasets to list all datasets (private).

    When the method is either 'create' or 'update', a file can be uploaded, with the --file option.
    """
    if state.organisation:
        # If organisation is provided as argument, don't put in payload too!
        kwargs.pop('organisation')
    api = ArcsecondAPI.datafiles(state=state, dataset=dataset)
    if method == 'create':
        api.create(kwargs)  # the kwargs dict is the payload!
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
    ArcsecondAPI.satellites(state).read(catalogue_number)


@main.command(help='Read telegrams (ATel)')
@click.argument('identifier', required=False, nargs=1)
@basic_options
@pass_state
def telegrams(state, identifier):
    """Request the list of telegrams from ATel, or the details of one (in the /telegrams/ATel/ API endpoint).

    The other sources of telegrams will be added in the future.
    """
    # If catalogue_number is None, ArcsecondAPI fallback to .list()
    ArcsecondAPI.telegrams(state).read(identifier)


@main.command(help='Read catalogues (standard stars)')
@click.argument('identifier', required=False, nargs=1)
@click.option('--rows', default=None, is_flag=True, nargs=1)
@basic_options
@pass_state
def catalogues(state, identifier, rows):
    """Request the list of identifier or the details of one (in the /catalogues/ API endpoint).
    """

    api = ArcsecondAPI.catalogues(state)
    if identifier:
        identifier = identifier + '/rows' if rows else identifier
        api.read(identifier)
    else:
        api.list()


@main.command(help='Request the list of standard stars (in the /standardstars/ API endpoint)')
@click.argument('around', required=True, nargs=1)
@click.argument('count', required=False, nargs=1, type=int)
@open_options
@pass_state
def standardstars(state, around, count=5):
    """Request the list of standard stars around a given position in the sky.

    Provided coordinates must have the following format: "RA_in_decimal_degrees,Dec_in_decimal_degrees"

    Coordinates are assumed to be Equatorial, with epoch J2000.
    """
    ArcsecondAPI.standardstars(state).list()


@main.command(help='Request the list of organisations, or the details of one if a subdomain is provided.')
@click.argument('subdomain', required=False, nargs=1)
@open_options
@pass_state
def organisations(state, subdomain):
    api = ArcsecondAPI.organisations(state)
    if subdomain:
        api.read(subdomain)
    else:
        api.list()


@main.command(help='Request the list of members of an organisation.')
@click.argument('subdomain', required=True, nargs=1)
@open_options
@pass_state
def members(state, subdomain):
    ArcsecondAPI.members(state, organisation=subdomain).list()


@main.command(help='Request the list of upload keys of an organisation.')
@click.argument('subdomain', required=True, nargs=1)
@open_options
@pass_state
def uploadkeys(state, subdomain):
    ArcsecondAPI.uploadkeys(state, organisation=subdomain).list()
