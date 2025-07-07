import json

import click
from arcsecond.api import ArcsecondAPI, ArcsecondConfig

from arcsecond.errors import ArcsecondError
from arcsecond.options import State, basic_options

pass_state = click.make_pass_decorator(State, ensure=True)


@click.command(help='Login to your Arcsecond account.')
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


@click.command(help='Get or set the API server address (fully qualified domain name).')
@click.argument('name', required=False, nargs=1)
@click.argument('fqdn', required=False, nargs=1)
@pass_state
def api(state, name=None, fqdn=None):
    """Configure the API server address"""
    if name is None:
        name = 'cloud'
    elif name == 'cloud':
        raise ArcsecondError("You cannot change the FQDN of the 'cloud' API server.")

    # The setter below is normally handled by the option --api, but here, the DX is different,
    # because we manipulate the api and its address itself.
    state.api_name = name
    config = ArcsecondConfig(state)

    if fqdn is None:
        click.echo(f" • name: {name}, fqdn: {config.api_server}")
    else:
        config.api_server = fqdn
        click.echo(f" • Set fqdn: {config.api_server} to API named {name}.")


@click.command(help='Get your complete user profile.')
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
