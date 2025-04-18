import sys

import click

from arcsecond import ArcsecondConfig, ArcsecondAPI
from arcsecond.hosting import docker
from arcsecond.hosting import keygen
from .checks import (
    is_arcsecond_api_reachable,
    is_user_logged_in,
    has_user_verified_email
)
from .constants import BANNER, PREFIX
from .setup import setup_hosting_variables

__version__ = '0.1.0 (Alpha) - Please, send feedback to cedric@arcsecond.io'
warning = '---> ARCSECOND SELF-HOSTING IS IN ALPHA STATE. USE AT YOUR OWN RISK. <---'


def run_arcsecond(state, do_try=True, skip_setup=False):
    click.echo(BANNER)
    click.echo('\n' + PREFIX + __version__)
    click.echo('\n' + PREFIX + warning)
    click.echo("\n" + PREFIX + "Checking prerequisites...")
    if not docker.is_docker_available():
        return
    if sys.platform == 'darwin':
        docker.setup_docker_host_on_macos()
    if not is_arcsecond_api_reachable(state):
        return
    if not is_user_logged_in(state):
        return
    if do_try is False and not has_user_verified_email(state):
        return

    profile, error = ArcsecondAPI(state).fetch_full_profile()
    if error is not None:
        click.echo(str(error))
        return

    config = ArcsecondConfig(state)
    klient = keygen.KeygenClient(config, do_try, profile)
    status, msg = klient.setup_and_validate_license()
    click.echo(PREFIX + msg)
    if status is False:
        return

    if not skip_setup:
        setup_hosting_variables(config, do_try=do_try)
    if not docker.has_all_arcsecond_docker_images():
        docker.pull_all_arcsecond_docker_images()
    docker.setup_network()
    docker.run_db_container(restart=False)
    docker.run_broker_container(restart=False)
    docker.run_api_container(config, restart=False, do_try=do_try)
    docker.run_web_container(restart=True)


def stop_arcsecond():
    click.echo(PREFIX + 'Stopping Arcsecond...')
    if sys.platform == 'darwin':
        docker.setup_docker_host_on_macos()
    docker.stop_all_containers()
    click.echo(PREFIX + 'Arcsecond stopped.')


def print_arcsecond_status():
    click.echo(PREFIX + 'Checking Arcsecond status...')
    click.echo(docker.get_all_containers_status_string())
