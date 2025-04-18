import click
import requests

from arcsecond import ArcsecondAPI, ArcsecondConfig
from .constants import PREFIX_SUB, PREFIX, PREFIX_SUB_FAIL


def is_arcsecond_api_reachable(state) -> bool:
    api_server = ArcsecondConfig(state).api_server
    click.echo(PREFIX + 'Check if Arcsecond is reachable...')
    try:
        response = requests.get(api_server)
    except requests.exceptions.ConnectionError as e:
        click.echo(PREFIX_SUB_FAIL + str(e))
        click.echo(PREFIX_SUB_FAIL + 'Arcsecond API is not reachable. Try again in a few minutes?')
        return False
    if response.status_code >= 300:
        click.echo(PREFIX_SUB_FAIL + '{}: {}'.format(response.status_code, response.text))
        click.echo(PREFIX_SUB_FAIL + 'Arcsecond API is not returning a valid status. Try again in a few minutes?')
        return False
    click.echo(PREFIX_SUB + 'Host ' + api_server + ' is reachable.')
    return True


def is_user_logged_in(state) -> bool:
    click.echo(PREFIX + 'Check if user is logged in with the CLI.')
    if not ArcsecondAPI.is_logged_in(state):
        click.echo(PREFIX_SUB_FAIL + 'You need to log in.')
        click.echo(PREFIX_SUB_FAIL + 'Use `arcsecond login` (or `arcsecond register` first, if needed).')
        return False
    click.echo(PREFIX_SUB + 'Logged in with username \"@' + ArcsecondAPI.username(state) + "\"")
    return True


def has_user_verified_email(state) -> bool:
    click.echo(PREFIX + 'Check if user email address is verified.')
    profile, error = ArcsecondAPI(state).fetch_full_profile()
    if profile and not error:
        result = bool(profile.get('is_verified', False))
        email = profile.get('email', '?')
        if result is True:
            click.echo(PREFIX_SUB + f'Email {email} is verified.')
            return True
        else:
            click.echo(PREFIX_SUB_FAIL + f"Email {email} must be verified before full Arcsecond installation.")
            click.echo(PREFIX_SUB_FAIL + f"Visit https://www.arcsecond.io/@{profile.get('username')}#emails")
            return False
    click.echo(PREFIX_SUB_FAIL + str(error))
    return False
