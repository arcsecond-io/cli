from typing import Union

import click
import httpx

from arcsecond import ArcsecondAPI, ArcsecondConfig

from .constants import PREFIX, PREFIX_SUB, PREFIX_SUB_FAIL


def is_arcsecond_api_reachable(state) -> bool:
    api_server = ArcsecondConfig.from_state(state).api_server
    click.echo(PREFIX + "Check if Arcsecond is reachable...")
    try:
        response = httpx.get(api_server)
    except httpx.exceptions.ConnectionError as e:
        click.echo(PREFIX_SUB_FAIL + str(e))
        click.echo(
            PREFIX_SUB_FAIL
            + "Arcsecond API is not reachable. Try again in a few minutes?"
        )
        return False
    if response.status_code >= 300:
        click.echo(
            PREFIX_SUB_FAIL + "{}: {}".format(response.status_code, response.text)
        )
        click.echo(
            PREFIX_SUB_FAIL
            + "Arcsecond API is not returning a valid status. Try again in a few minutes?"
        )
        return False
    click.echo(PREFIX_SUB + "Host " + api_server + " is reachable.")
    return True


def is_user_logged_in(state) -> bool:
    click.echo(PREFIX + "Check if user is logged in with the CLI.")
    if not ArcsecondAPI.is_logged_in(state):
        click.echo(PREFIX_SUB_FAIL + "You need to log in.")
        click.echo(
            PREFIX_SUB_FAIL
            + "Use `arcsecond login` (or `arcsecond register` first, if needed)."
        )
        return False
    click.echo(
        PREFIX_SUB
        + 'Logged in with username "@'
        + ArcsecondAPI.get_username(state)
        + '"'
    )
    return True


def has_user_verified_email(state) -> bool:
    click.echo(PREFIX + "Check if user email address is verified.")
    profile, error = ArcsecondAPI(state).fetch_full_profile()
    if profile and not error:
        result = bool(profile.get("is_verified", False))
        email = profile.get("email", "?")
        if result is True:
            click.echo(PREFIX_SUB + f"Email {email} is verified.")
            return True
        else:
            click.echo(
                PREFIX_SUB_FAIL
                + f"Email {email} must be verified before full Arcsecond installation."
            )
            click.echo(
                PREFIX_SUB_FAIL
                + f"Visit https://www.arcsecond.io/@{profile.get('username')}#emails"
            )
            return False
    click.echo(PREFIX_SUB_FAIL + str(error))
    return False


def fetch_profile_email(state) -> Union[tuple[None, str], tuple[dict, None]]:
    click.echo(
        PREFIX + "Fetching your email from the cloud, to register your license..."
    )
    state.api_name = "cloud"
    email_dict, error = ArcsecondAPI(ArcsecondConfig.from_state(state)).fetch_email()
    if error is not None:
        click.echo(PREFIX_SUB_FAIL + str(error))
        return None, str(error)
    else:
        user, full_hostname = email_dict.get("email", "?").split("@")
        masked_user = user[0] + (len(user) - 2) * "*" + user[-1]
        extension = full_hostname.split(".")[-1]
        hostname = ".".join(full_hostname.split(".")[:-1])
        mask_hostname = hostname[0] + (len(hostname) - 2) * "*" + hostname[-1]
        masked_email = masked_user + "@" + mask_hostname + "." + extension
        click.echo(PREFIX_SUB + f"Profile fetched, and email {masked_email} found.")
        return email_dict.get("email", "?"), None
