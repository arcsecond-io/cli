"""The installation's own Tomorrow.io key.

The backend asks Tomorrow.io for each observing site's current conditions
once an hour, and for the forecast the web app shows. The key is the
observatory's own: Arcsecond's is not shipped with the images, and an
installation without one simply has no forecast (the safety strip says so
for any condition only the forecast could have fed). A free key carries
about twenty sites at the hourly beat.

`arcsecond setup` asks for it while the TOMORROW_IO_API_KEY line of .env is
empty, the way it asks for the access token: an empty answer is "later", not
"never", since nothing is lost by asking again.
"""

import click

from .utils import _read_env_value, _set_env_value

ENV_KEY = "TOMORROW_IO_API_KEY"
SIGN_UP_URL = "https://www.tomorrow.io/weather-api/"

ENV_COMMENT = (
    "# Your own Tomorrow.io API key (optional — the weather forecast and the"
    f" safety conditions it feeds). A free key is enough: {SIGN_UP_URL}"
)

LATER = "arcsecond setup --tomorrow-io-key <your key>  &&  arcsecond restart"


def has_key(env_path) -> bool:
    return bool((_read_env_value(ENV_KEY, env_path) or "").strip())


def offer(env_path, key=None, interactive=True) -> None:
    """Record ``key`` (--tomorrow-io-key) when given; otherwise ask while
    none is recorded and there is a terminal to ask on."""
    if key is not None:
        key = key.strip()
        _set_env_value(env_path, ENV_KEY, key)
        if key:
            click.echo("Tomorrow.io key recorded. The weather forecast starts with the next  arcsecond restart.")
        else:
            click.echo("Tomorrow.io key removed: this installation has no weather forecast.")
        return

    if has_key(env_path) or not interactive:
        return

    click.echo(
        "\nThe weather forecast comes from Tomorrow.io, with a key of your own "
        f"(a free one is enough: {SIGN_UP_URL})."
    )
    entered = click.prompt(
        "Tomorrow.io API key (nothing is shown while you type; leave it empty to do this later)",
        hide_input=True,
        default="",
        show_default=False,
    ).strip()
    if entered:
        _set_env_value(env_path, ENV_KEY, entered)
        click.echo(click.style("Tomorrow.io key recorded.", fg="green"))


def next_step(env_path):
    """The line `setup` ends with when there is still no key, or None."""
    if has_key(env_path):
        return None
    return (
        "No Tomorrow.io key yet, so no weather forecast. With a key of your own "
        f"({SIGN_UP_URL}):  {LATER}"
    )
