import secrets

import click

from arcsecond.config import config_file_path, config_file_read_key, config_file_save_key_value


def _get_random_secret_key():
    # No '%' to avoid interpolation surprises
    chars = 'abcdefghijklmnopqrstuvwxyz0123456789!@#$^&*(-_=+)'
    return ''.join(secrets.choice(chars) for i in range(50))


def setup_hosting_variables(do_try=True):
    click.echo("\nWelcome to the setup of self-hosting Arcsecond.")
    section = 'hosting:try' if do_try else 'hosting'

    # Django SECRET_KEY variable.
    if config_file_read_key('secret_key', section=section) is None:
        secret_key = _get_random_secret_key()
        config_file_save_key_value('secret_key', secret_key, section=section)

    click.echo("Note that you will need Docker installed on this machine for Arcsecond to run.")
    click.echo("A connexion to Internet is also required.")

    click.echo("\nPlease answer the following questions to setup your local installation.")
    click.echo(f"Answers will be stored in {str(config_file_path())}. Keep this file safely and private.")
    if do_try:
        click.echo("A valid Arcsecond.io account is not required for trying Arcsecond.")
    else:
        # check credentials
        pass

    click.echo("")
    subdomain = click.prompt("Choose an organisation subdomain for your portal", type=click.STRING)
    config_file_save_key_value('org_subdomain', subdomain, section=section)
