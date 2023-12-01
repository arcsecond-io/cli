import sys

import click

from arcsecond import Config
from .checks import (
    is_docker_available,
    setup_docker_host_on_macos,
    is_arcsecond_api_reachable,
    is_user_logged_in,
    has_user_verified_email
)
from .constants import DOCKER_IMAGE_CONTAINERS_NAMES, BANNER, PREFIX
from .containers import (
    setup_network,
    run_db_container,
    run_api_container,
    run_www_container,
    run_mb_container
)
from .images import (
    has_all_arcsecond_docker_images,
    has_docker_image,
    pull_all_arcsecond_docker_images,
)
from .setup import setup_hosting_variables
from .utils import __get_docker_container_status, __perform_container_bookkeeping


def run_arcsecond(state, do_try=True, skip_setup=False):
    click.echo(BANNER)
    click.echo("\n" + PREFIX + "Checking prerequisites...")
    if not is_docker_available():
        return
    if sys.platform == 'darwin':
        setup_docker_host_on_macos()
    if not is_arcsecond_api_reachable():
        return
    if not is_user_logged_in(state):
        return
    config = Config(state)
    if do_try is False and not has_user_verified_email(state):
        return
    # LICENSING...
    if not skip_setup:
        setup_hosting_variables(config, do_try=do_try)
    if not has_all_arcsecond_docker_images():
        pull_all_arcsecond_docker_images()
    setup_network()
    run_db_container(restart=False)
    run_mb_container(restart=False)
    run_api_container(config, restart=False, do_try=do_try)
    run_www_container(restart=True)


def stop_arcsecond():
    if sys.platform == 'darwin':
        setup_docker_host_on_macos()
    container_names = [cont for (_, cont, _) in DOCKER_IMAGE_CONTAINERS_NAMES.values()]
    for container_name in container_names:
        __perform_container_bookkeeping(container_name, stop=True)


def get_arcsecond_status():
    if sys.platform == 'darwin':
        setup_docker_host_on_macos()
    for image_name, container_name, service_name in DOCKER_IMAGE_CONTAINERS_NAMES.values():
        container_status = __get_docker_container_status(container_name)
        container_status_msg = f'Container status: {container_status}.' \
            if container_status is not None \
            else 'No running container.'
        image_status = has_docker_image(image_name)
        image_status_msg = 'Docker image locally available.' if image_status is True else 'Image not yet pulled.'
        click.echo(f'Service "{service_name}": {image_status_msg} {container_status_msg}')
