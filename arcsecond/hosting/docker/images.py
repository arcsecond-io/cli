import click
import docker
from docker.errors import APIError, ImageNotFound

from .constants import DOCKER_IMAGE_CONTAINERS_NAMES


def has_docker_image(full_name):
    name, tag = full_name.split(':')
    click.echo(f'Checking for Docker image {name}:{tag}...')
    client = docker.from_env()
    try:
        client.images.get(f'{name}:{tag}')
    except ImageNotFound:
        return False
    except APIError:
        # Print log
        return False
    else:
        return True


def update_docker_image(full_name: str):
    name, tag = full_name.split(':')
    client = docker.from_env()
    click.echo(f'Pulling Docker image {name}:{tag}...')
    try:
        client.images.pull(name, tag=tag)
        return True
    except APIError:
        # Print log
        return False


def has_all_arcsecond_docker_images():
    image_names = set([im for (im, _, _) in DOCKER_IMAGE_CONTAINERS_NAMES.values()])
    return all([has_docker_image(name) for name in image_names])


def pull_all_arcsecond_docker_images():
    image_names = set([im for (im, _, _) in DOCKER_IMAGE_CONTAINERS_NAMES.values()])
    for image_name in image_names:
        update_docker_image(image_name)
