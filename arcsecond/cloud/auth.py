import click
import httpx

from arcsecond.api import ArcsecondAPI, ArcsecondConfig
from arcsecond.api.config import API_NAME_ENV_VAR, DEFAULT_API_NAME
from arcsecond.errors import ArcsecondError
from arcsecond.options import State, basic_options

pass_state = click.make_pass_decorator(State, ensure=True)


@click.command(short_help="Login to your Arcsecond account.")
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
    help="Your access key (a.k.a. API key). Visit your settings page to copy "
    "and paste it here. One of Access or Upload key must be provided.",
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
    """Login to your Arcsecond account, on the API server the CLI points at.

    You must provide either your Access Key, or your Upload Key.
    By doing so, you choose the level of access you want to store
    on this computer. The Access Key give a full API access to your
    data. The Upload Key gives just enough permissions to upload data.

    Both keys can be retrieved from your personal Settings page on
    https://www.arcsecond.io (or on your own Arcsecond.local).

    Beware that the Key you provide will be stored locally on the file:
    ~/.config/arcsecond/config.ini
    """
    key_name = "access_key" if type == "access" else "upload_key"
    config = ArcsecondConfig.from_state(state)
    _, error = ArcsecondAPI(config).login(username, **{key_name: key})
    if error:
        click.echo(str(error))
        return
    click.echo(
        click.style("Logged in", fg="green")
        + f" as @{username} on '{config.api_name}' ({config.api_server})."
    )


# ---------------------------------------------------------------------------
# `arcsecond api`: the pointer to the server every command talks to
# ---------------------------------------------------------------------------

PROBE_TIMEOUT = 8.0  # seconds


def probe_api_server(address: str):
    """Whether something answers HTTP at ``address``. Returns (ok, detail).

    A reachability check, not a fingerprint: an Arcsecond server answers its
    root with 200, but the point is to refuse a typo or a server that is not
    up yet, and any HTTP answer below 500 proves the address is a live one.
    """
    try:
        response = httpx.get(address, timeout=PROBE_TIMEOUT, follow_redirects=True)
    except httpx.HTTPError as e:
        return False, f"{type(e).__name__}: {e}"
    if response.status_code >= 500:
        return False, f"the server answered {response.status_code}"
    return True, f"answered {response.status_code}"


class _ApiGroup(click.Group):
    """`arcsecond api <name> <address>`, the pre-4.0 way of registering a
    server, still works: two tokens that are not a subcommand mean `add`."""

    def resolve_command(self, ctx, args):
        if args and args[0] not in self.commands and len(args) == 2:
            return super().resolve_command(ctx, ["add", *args])
        return super().resolve_command(ctx, args)


@click.group(cls=_ApiGroup, invoke_without_command=True)
@click.pass_context
def api(ctx):
    """The API server the CLI talks to.

    Every command uses one server: the "cloud" (api.arcsecond.io) by
    default, or any server registered here — typically your own
    Arcsecond.local. Point the CLI at one and it stays pointed there:

    \b
      arcsecond api                          list the servers, * marks the current one
      arcsecond api add local http://localhost:8800
      arcsecond api use local                every command now talks to it
      arcsecond api remove local

    Credentials are kept per server, so `arcsecond login` after `api use`
    logs you in on that server only.

    For a script or a cron job, set ARCSECOND_API=<name> instead: it applies to
    that process alone and leaves the pointer untouched.
    """
    if ctx.invoked_subcommand is None:
        config = ArcsecondConfig()
        click.echo(" • Registered API servers (* = current):")
        click.echo(config.all_apis)
        if ArcsecondConfig.is_api_name_overridden():
            click.echo(
                f"\n   {API_NAME_ENV_VAR} is set, which overrides the recorded pointer "
                "for this process."
            )


@api.command(name="add", help="Register a server under a name.")
@click.argument("name", nargs=1)
@click.argument("address", nargs=1)
def api_add(name, address):
    if name == DEFAULT_API_NAME:
        raise ArcsecondError(
            "You cannot change the server address of the 'cloud' API server."
        )
    config = ArcsecondConfig(api_name=name)
    config.api_server = address
    click.echo(f' • Registered the API "{name}" at "{config.api_server}".')
    if ArcsecondConfig.current_api_name() != name:
        click.echo(f"   Point the CLI at it with:  arcsecond api use {name}")


@api.command(
    name="use",
    help="Point every following command at this server (it must answer).",
)
@click.argument("name", nargs=1)
def api_use(name):
    if name not in ArcsecondConfig.registered_api_names():
        raise ArcsecondError(
            f"No API server is registered under the name '{name}'.\n"
            f"Register it first:  arcsecond api add {name} <address>"
        )
    address = ArcsecondConfig(api_name=name).api_server
    ok, detail = probe_api_server(address)
    if not ok:
        raise ArcsecondError(
            f"'{name}' ({address}) does not answer — {detail}.\n"
            "The pointer was not moved. Start that server, or check the address."
        )
    ArcsecondConfig.set_current_api_name(name)
    click.echo(
        click.style(" • The CLI now points at ", fg="green") + f"'{name}' ({address})."
    )
    if not ArcsecondConfig(api_name=name).is_logged_in:
        click.echo("   You are not logged in there yet:  arcsecond login")


@api.command(name="remove", help="Forget a registered server and its credentials.")
@click.argument("name", nargs=1)
def api_remove(name):
    was_current = ArcsecondConfig.current_api_name() == name
    ArcsecondConfig.remove_api(name)
    click.echo(f' • Removed the API "{name}".')
    if was_current:
        click.echo(f"   The CLI points at '{DEFAULT_API_NAME}' again.")
