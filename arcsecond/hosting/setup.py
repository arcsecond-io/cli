import base64
import os
import re
import secrets

import click

from arcsecond import ArcsecondConfig

email_regex = re.compile(r'([A-Za-z0-9]+[.-_])*[A-Za-z0-9]+@[A-Za-z0-9-]+(\.[A-Z|a-z]{2,})+')


def _get_random_secret_key():
    # No '%' to avoid interpolation surprises
    chars = 'abcdefghijklmnopqrstuvwxyz0123456789!@#$^&*(-_=+)'
    return ''.join(secrets.choice(chars) for i in range(50))


def _validate_value_base(value):
    if len(value.strip()) < 3:
        raise click.BadParameter("Value must be at least 3 characters long.")
    return value.strip()


def _validate_subdomain(value):
    value = _validate_value_base(value).lower()
    if not re.match(r'[a-z\-_]{3,}', value):
        raise click.BadParameter("Value must be a correct subdomain (no special characters except - or _)")
    return value


def _validate_email_host_item(value):
    value = _validate_value_base(value)
    if value[0] == '$':
        value = os.environ[value[1:]].lower()
        click.echo('Value: ' + value)
    return value


def __validate_email_host(value):
    value = _validate_email_host_item(value)
    if not re.match(r'[a-z\-_]{1,}(\.[a-z\-_]{1,})?', value):
        raise click.BadParameter("Value must be a correct email host name (no http://, only the hostname).")
    return value


def _validate_email_admin(value):
    value = _validate_value_base(value)
    if not re.fullmatch(email_regex, value):
        raise click.BadParameter("Value must be a correct email address.")
    return value


def setup_hosting_variables(config: ArcsecondConfig, do_try=True):
    click.echo("\nWelcome to the setup of self-hosting Arcsecond.")
    section = 'hosting:try' if do_try else 'hosting'

    # Django SECRET_KEY variable.
    if config.read_key('secret_key', section) is None:
        secret_key = _get_random_secret_key()
        config.save(secret_key=secret_key, section=section)
    if config.read_key('field_encryption_key', section) is None:
        field_encryption_key = base64.urlsafe_b64encode(os.urandom(32)).decode('utf8')
        config.save(field_encryption_key=field_encryption_key, section=section)

    click.echo("Note that you will need a recent version of Docker running on this machine for Arcsecond to run.")
    click.echo("A connexion to Internet is also required.")

    click.echo("\nPlease answer the following questions to setup your local installation.")
    click.echo(f"Answers will be stored in {str(config.file_path)}. Keep this file safely and private.")
    click.echo("To update an installation, simply re-run the \"try\" command.")
    if do_try:
        click.echo("A valid Arcsecond.io account is required for trying Arcsecond.")
        click.echo("Please, use the command `arcsecond login` or `arcsecond register` if needed.")
    else:
        # check credentials
        pass

    click.echo("")
    click.echo("If you intend to create and use an Observatory Portal, Arcsecond requires a subdomain.")
    subdomain = click.prompt("Choose an organisation subdomain for your portal",
                             value_proc=_validate_subdomain)
    config.save(org_subdomain=subdomain, section=section)

    # port = click.prompt("Choose an address port number for your API server", type=click.INT, default='8000')
    # config_file_save_key_value('api_port', port, section=section)
    current_value = config.read_key('email_host', section)
    msg = "Provide the email host address. Start your answer with $ to provide an env variable name."
    email_host = click.prompt(msg,
                              value_proc=__validate_email_host,
                              default=current_value or '$EMAIL_HOST')
    config.save(email_host=email_host, section=section)

    msg = "Provide the email host username. Start your answer with $ to provide an env variable name."
    current_value = config.read_key('email_host_user', section)
    email_host_user = click.prompt(msg,
                                   value_proc=_validate_email_host_item,
                                   default=current_value or '$EMAIL_HOST_USER')
    config.save(email_host_user=email_host_user, section=section)

    msg = "Provide the email host password. Start your answer with $ to provide an env variable name."
    current_value = config.read_key('email_host_password', section)
    email_host_password = click.prompt(msg,
                                       value_proc=_validate_email_host_item,
                                       default=current_value or '$EMAIL_HOST_PASSWORD')
    config.save(email_host_password=email_host_password, section=section)

    msg = "Provide the email address of the administrator. Start your answer with $ to provide an env variable name."
    current_value = config.read_key('email_admin', section)
    email_admin = click.prompt(msg,
                               value_proc=_validate_email_admin,
                               default=current_value or '$EMAIL_ADMIN')
    config.save(email_admin=email_admin, section=section)

    msg = "Provide the path of the default storage space. "
    msg += "Arcsecond requires anyway some storage for images and database.\n"
    msg += "Later, you will be able to provide external storages too in the running Arcsecond itself."
    current_value = config.read_key('media_root', section)
    media_root = click.prompt(msg, type=click.STRING, default=current_value or '$HOME/arcsecond')
    config.save(media_root=media_root, section=section)
