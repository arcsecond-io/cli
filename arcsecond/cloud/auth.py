import json

import click

from arcsecond.api import ArcsecondAPI, ArcsecondConfig
from arcsecond.errors import ArcsecondError
from arcsecond.options import State, basic_options

pass_state = click.make_pass_decorator(State, ensure=True)


@click.command(help="Login to your Arcsecond account.")
@click.option(
    "--username",
    required=True,
    nargs=1,
    prompt=True,
    help="Account username (without @). Primary email address is also allowed.",
)
@click.option(
    "--type",
    required=True,
    type=click.Choice(["access", "upload"], case_sensitive=False),
    prompt=True,
    help="Your access key (a.k.a. API key). Visit your settings page to copy and paste it here. One of Access or Upload key must be provided.",
)
@click.option(
    "--key",
    required=True,
    nargs=1,
    prompt=True,
    help="Your upload key. Visit your settings page to copy and paste it here. One of Access or Upload key must be provided.",
)
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
    key_name = "access_key" if type == "access" else "upload_key"
    config = ArcsecondConfig.from_state(state)
    _, error = ArcsecondAPI(config).login(username, **{key_name: key})
    if error:
        click.echo(str(error))


@click.command()
@click.argument("name", required=False, nargs=1)
@click.argument("fqdn", required=False, nargs=1)
@pass_state
def api(state, name=None, fqdn=None):
    """List or configure the API server address.

    By default, the Arcsecond CLI is using the "cloud" master server. But you can
    here configure other servers, by typing:

    $ arcsecond api <name> <fully qualified server address>

    Once registered, you can then use all commands with the 'api' option to tell the
    module where to point. For instance:

    $ arcsecond login --api test

    To list all registered servers, simply type:

    $ arcsecond api
    """

    if name is not None and fqdn is None:
        raise ArcsecondError(
            f"You must provide a fully-qualified domain name server for the api '{name}'."
        )

    if name == "cloud" and fqdn is not None:
        raise ArcsecondError(
            "You cannot change the server address of the 'cloud' API server."
        )

    # The setter below is normally handled by the option --api, but here, the DX is different,
    # because we manipulate the api and its address itself.
    state.api_name = name
    config = ArcsecondConfig.from_state(state)

    if fqdn is None:
        click.echo(" • All registered API servers:")
        click.echo(config.all_apis)
    else:
        config.api_server = fqdn
        click.echo(
            f' • Registering the API "{name}" with the server address "{config.api_server}".'
        )


@click.command(help="Get your complete user profile.")
@basic_options
@pass_state
def me(state):
    """Fetch your complete user profile."""
    username = ArcsecondConfig.from_state(state).username or None
    if not username:
        msg = f"Invalid/missing username: {username}. Make sure to login first: $ arcsecond login"
        raise ArcsecondError(msg)
    response, error = ArcsecondAPI(ArcsecondConfig.from_state(state)).profiles.read(
        username
    )
    if error:
        click.echo(str(error))
    else:
        click.echo(json.dumps(response, indent=2))
