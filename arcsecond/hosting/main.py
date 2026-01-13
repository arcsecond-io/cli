import sys

import click

from arcsecond.api import ArcsecondConfig
from arcsecond.hosting import docker
from arcsecond.options import State, basic_options

from .checks import fetch_profile_email, is_user_logged_in
from .constants import BANNER, PREFIX, PREFIX_SUB, PREFIX_SUB_FAIL
from .keygen import KeygenClient

__version__ = "6.1.0 - Please, send feedback to cedric@arcsecond.io"
warning = (
    "---> ARCSECOND.LOCAL (SELF-HOSTING) IS IN ALPHA STATE. USE AT YOUR OWN RISK. <---"
)

pass_state = click.make_pass_decorator(State, ensure=True)

#
# @click.command(help="Install a self-hosted Arcsecond system.")
# @click.option(
#     "--do_try", required=False, nargs=1, prompt=False, default=True, type=click.BOOL
# )
# @click.option(
#     "--skip_setup",
#     required=False,
#     nargs=1,
#     prompt=False,
#     default=False,
#     type=click.BOOL,
# )
# @basic_options
# @pass_state
# def install(state, skip_setup=False):
#     click.echo(BANNER)
#     click.echo("\n" + PREFIX + __version__)
#     click.echo("\n" + PREFIX + warning)
#     click.echo("\n" + PREFIX + "Checking prerequisites...")
#     if not docker.is_docker_available():
#         return
#     if sys.platform == "darwin":
#         docker.setup_docker_host_on_macos()
#     if not is_user_logged_in(state):
#         return
#
#     email, error = fetch_profile_email(state)
#     if error is not None:
#         return
#
#     config = ArcsecondConfig.from_state(state)
#     klient = KeygenClient(config, email)
#     click.echo(PREFIX + "Setting up your license...")
#     is_license_ok, msg = klient.setup_and_validate_license()
#     if is_license_ok:
#         click.echo(PREFIX_SUB + msg)
#     else:
#         click.echo(PREFIX_SUB_FAIL + msg)

    # if not skip_setup:
    #     setup_hosting_variables(config, do_try=do_try)
    # if not docker.has_all_arcsecond_docker_images():
    #     docker.pull_all_arcsecond_docker_images()
    #
    # docker.setup_network()
    # docker.run_db_container(restart=False)
    # docker.run_broker_container(restart=False)
    # docker.run_api_container(config, restart=False, do_try=do_try)
    # docker.run_web_container(restart=True)

#
# def stop():
#     click.echo(PREFIX + "Stopping Arcsecond...")
#     if sys.platform == "darwin":
#         docker.setup_docker_host_on_macos()
#     docker.stop_all_containers()
#     click.echo(PREFIX + "Arcsecond stopped.")
#
#
# def status():
#     click.echo(PREFIX + "Checking Arcsecond status...")
#     click.echo(docker.get_all_containers_status_string())
