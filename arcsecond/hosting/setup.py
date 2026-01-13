import click

from arcsecond import ArcsecondConfig
from .utils import _get_random_secret_key, _get_encryption_key


def setup_hosting_variables(config: ArcsecondConfig, do_try=True):
    click.echo("\nWelcome to the setup of self-hosting Arcsecond.")

    # Django SECRET_KEY variable.
    if config.read_key("secret_key") is None:
        secret_key = _get_random_secret_key()
        config.save(secret_key=secret_key)
    if config.read_key("field_encryption_key") is None:
        field_encryption_key = _get_encryption_key()
        config.save(field_encryption_key=field_encryption_key)

    click.echo(
        "Note that you will need a recent version of Docker running on this machine for Arcsecond to run."
    )
    click.echo("A connexion to Internet is also required.")

    # click.echo("\nPlease answer the following questions to setup your local installation.")
    # click.echo(f"Answers will be stored in {str(config.file_path)}. Keep this file safely and private.")
    # click.echo("To update an installation, simply re-run the \"try\" command.")
    # if do_try:
    #     click.echo("A valid Arcsecond.io account is required for trying Arcsecond.")
    #     click.echo("Please, use the command `arcsecond login` or `arcsecond register` if needed.")
    # else:
    #     # check credentials
    #     pass
    #
    # click.echo("")
    # click.echo("If you intend to create and use an Observatory Portal, Arcsecond requires a subdomain.")
    # subdomain = click.prompt("Choose an organisation subdomain for your portal",
    #                          value_proc=_validate_subdomain)
    # config.save(org_subdomain=subdomain)
    #
    # # port = click.prompt("Choose an address port number for your API server", type=click.INT, default='8000')
    # # config_file_save_key_value('api_port', port)
    # current_value = config.read_key('email_host')
    # msg = "Provide the email host address. Start your answer with $ to provide an env variable name."
    # email_host = click.prompt(msg,
    #                           value_proc=__validate_email_host,
    #                           default=current_value or '$EMAIL_HOST')
    # config.save(email_host=email_host)
    #
    # msg = "Provide the email host username. Start your answer with $ to provide an env variable name."
    # current_value = config.read_key('email_host_user')
    # email_host_user = click.prompt(msg,
    #                                value_proc=_validate_email_host_item,
    #                                default=current_value or '$EMAIL_HOST_USER')
    # config.save(email_host_user=email_host_user)
    #
    # msg = "Provide the email host password. Start your answer with $ to provide an env variable name."
    # current_value = config.read_key('email_host_password')
    # email_host_password = click.prompt(msg,
    #                                    value_proc=_validate_email_host_item,
    #                                    default=current_value or '$EMAIL_HOST_PASSWORD')
    # config.save(email_host_password=email_host_password)
    #
    # msg = "Provide the email address of the administrator. Start your answer with $ to provide an env variable name."
    # current_value = config.read_key('email_admin')
    # email_admin = click.prompt(msg,
    #                            value_proc=_validate_email_admin,
    #                            default=current_value or '$EMAIL_ADMIN')
    # config.save(email_admin=email_admin)
    #
    # msg = "Provide the path of the default storage space. "
    # msg += "Arcsecond requires anyway some storage for images and database.\n"
    # msg += "Later, you will be able to provide external storages too in the running Arcsecond itself."
    # current_value = config.read_key('media_root')
    # media_root = click.prompt(msg, type=click.STRING, default=current_value or '$HOME/arcsecond')
    # config.save(media_root=media_root)
