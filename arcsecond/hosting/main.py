import sys

import click

from arcsecond.hosting import docker
from arcsecond.hosting import keygen
from .constants import BANNER, PREFIX
from .checks import (
    fetch_user_profile,
    is_arcsecond_api_reachable,
    is_user_logged_in,
    has_user_verified_email
)
from .setup import setup_hosting_variables

__version__ = '0.1.0 (Alpha) - Please, send feedback to cedric@arcsecond.io'


def run_arcsecond(state, do_try=True, skip_setup=False):
    click.echo(BANNER)
    click.echo('\n' + PREFIX + __version__)
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

    # config = Config(state)
    klient = keygen.KeygenClient(state, do_try)
    profile = fetch_user_profile(state)
    klient.create_user(profile)
    klient.create_license()

    return

    if not skip_setup:
        setup_hosting_variables(config, do_try=do_try)
    if not docker.has_all_arcsecond_docker_images():
        docker.pull_all_arcsecond_docker_images()
    docker.setup_network()
    docker.run_db_container(restart=False)
    docker.run_mb_container(restart=False)
    docker.run_api_container(config, restart=False, do_try=do_try)
    docker.run_www_container(restart=True)


def stop_arcsecond():
    if sys.platform == 'darwin':
        docker.setup_docker_host_on_macos()
    docker.stop_all_containers()


def print_arcsecond_status():
    click.echo(docker.get_all_containers_status_string())
