import json

import click

from . import __version__
from .api import ArcsecondAPI, ArcsecondConfig
from .options import State, basic_options
from .uploader.context import UploadContext
from .uploader.errors import ArcsecondError
from .uploader.utils import display_command_summary
from .uploader.walker import walk_folder_and_upload

pass_state = click.make_pass_decorator(State, ensure=True)

VERSION_HELP_STRING = "Show the CLI version and exit."


@click.group(invoke_without_command=True)
@click.option('--version', is_flag=True, help=VERSION_HELP_STRING)
@click.option('-V', is_flag=True, help=VERSION_HELP_STRING)
@click.option('-h', is_flag=True, help="Show this message and exit.")
@click.pass_context
def main(ctx, version=False, v=False, h=False):
    if version or v:
        click.echo(__version__.__version__)
    elif ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command(help=VERSION_HELP_STRING)
def version():
    click.echo(__version__.__version__)


@main.command(help='Login to your Arcsecond account.')
@click.option('--username', required=True, nargs=1, prompt=True,
              help='Account username (without @). Primary email address is also allowed.')
@click.option('--type', required=True, type=click.Choice(['access', 'upload'], case_sensitive=False), prompt=True,
              help='Your access key (a.k.a. API key). Visit your settings page to copy and paste it here. One of Access or Upload key must be provided.')
@click.option('--key', required=True, nargs=1, prompt=True,
              help='Your upload key. Visit your settings page to copy and paste it here. One of Access or Upload key must be provided.')
@basic_options
@pass_state
def login(state, username, type, key):
    """Login to your personal Arcsecond.io account.

    You must provide either your Access Key, or your Upload Key.
    By doing so, you choose the level of access you want to store
    on this computer. The Access Key give a full API access to your
    data. The Upload Key gives just enough permissions to upload data.

    Both keys can be retrieved from your personal Settings page on
    https://www.arcsecond.io

    Beware that the Key you provide will be stored locally on the file:
    ~/.config/arcsecond/config.ini
    """
    key_name = 'access_key' if type == 'access' else 'upload_key'
    config = ArcsecondConfig(state)
    _, error = ArcsecondAPI(config).login(username, **{key_name: key})
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
    # because we manipulate the api and its address itself.
    state.api_name = name
    config = ArcsecondConfig(state)

    if fqdn is None:
        click.echo(f" • name: {name}, fqdn: {config.api_server}")
    else:
        config.api_server = fqdn
        click.echo(f" • Set fqdn: {config.api_server} to API named {name}.")


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


@main.command(help="Display the list of (portal) datasets.")
@click.option('-p', '--portal',
              required=False, nargs=1,
              help="The portal subdomain, if uploading for an Observatory Portal.")
@basic_options
@pass_state
def datasets(state, portal=None):
    org_subdomain = portal or ''
    if org_subdomain:
        click.echo(f" • Fetching datasets for portal '{org_subdomain}'...")
    else:
        click.echo(" • Fetching datasets...")

    dataset_list, error = ArcsecondAPI(ArcsecondConfig(state)).datasets.list()
    if error is not None:
        raise ArcsecondError(str(error))

    if isinstance(dataset_list, dict) and 'results' in dataset_list.keys():
        dataset_list = dataset_list['results']

    click.echo(f" • Found {len(dataset_list)} dataset{'s' if len(dataset_list) > 1 else ''}.")
    for dataset_dict in dataset_list:
        s = f" 💾 \"{dataset_dict['name']}\" "
        s += f"(uuid: {dataset_dict['uuid']}) "
        # s += f"[ObservingSite UUID: {telescope_dict['observing_site']}]"
        click.echo(s)


@main.command(help='Upload the content of a folder.')
@click.argument('folder', required=True, nargs=1)
@click.option('-d', '--dataset',
              required=True, nargs=1, type=click.STRING,
              help="The UUID or name of the dataset to put data in. If new, it will be created.")
@click.option('-t', '--telescope',
              required=False, nargs=1, type=click.UUID,
              help="The telescope UUID, to be attached to the dataset.")
@click.option('-p', '--portal',
              required=False, nargs=1, type=click.STRING,
              help="The portal subdomain, if uploading for an Observatory Portal.")
@basic_options
@pass_state
def upload(state, folder, dataset=None, telescope=None, portal=None):
    """
    Upload the content of a folder.

    You will be prompted for confirmation before the whole walking process actually
    start.

    Every DataFile must belong to a Dataset. If you provide a Dataset UUID, Oort will
    append files to the dataset. If you provide a Dataset *name*, Oort will try to find
    an existing Dataset with that name. If none could be found, Oort will create one,
    and put files in it.

    You can use `arcsecond datasets [OPTIONS]` to get a list of your existing datasets
    (with their UUID).

    Arcsecond will then start walking through the folder tree and uploads regular files
    (hidden and empty files will be skipped).
    """
    config = ArcsecondConfig(state)
    context = UploadContext(config, dataset_uuid_or_name=dataset, telescope_uuid=telescope, org_subdomain=portal)
    context.validate()

    display_command_summary(context, [folder, ])
    ok = input('\n   ----> OK? (Press Enter) ')
    if ok.strip() == '':
        walk_folder_and_upload(context, folder)
