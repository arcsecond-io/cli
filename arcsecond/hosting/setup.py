import secrets
import click

from pygments import highlight
from pygments.lexers import PythonLexer
from pygments.formatters import TerminalFormatter


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

    # port = click.prompt("Choose an address port number for your API server", type=click.INT, default='8000')
    # config_file_save_key_value('api_port', port, section=section)

    msg = "Provide the email host address. Start your answer with $ to provide an env variable name."
    email_host = click.prompt(msg, type=click.STRING)
    config_file_save_key_value('email_host', email_host, section=section)

    msg = "Provide the email host username. Start your answer with $ to provide an env variable name."
    email_host_user = click.prompt(msg, type=click.STRING)
    config_file_save_key_value('email_host_user', email_host_user, section=section)

    msg = "Provide the email host password. Start your answer with $ to provide an env variable name."
    email_host_password = click.prompt(msg, type=click.STRING)
    config_file_save_key_value('email_host_password', email_host_password, section=section)

    msg = "Provide the email address of the administrator (to receive error messages). Start your answer with $ to provide an env variable name."
    email_admin = click.prompt(msg, type=click.STRING)
    config_file_save_key_value('email_admin', email_admin, section=section)
