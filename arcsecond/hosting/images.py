import subprocess

import click
import docker
from docker.errors import APIError, ImageNotFound

from .constants import DOCKER_IMAGE_NAMES


def is_docker_available() -> bool:
    try:
        subprocess.check_output(['docker', 'ps'])
    except subprocess.CalledProcessError as e:
        print(str(e))
        return False
    else:
        click.echo('Docker is installed. OK.')
        return True


def has_docker_image(name: str, tag: str = 'latest'):
    client = docker.from_env()
    if ':' in name:
        name, tag = name.split(':')
    try:
        client.images.get(f'{name}:{tag}')
    except ImageNotFound:
        return False
    except APIError:
        # Print log
        return False
    else:
        click.echo(f'Docker image {name}:{tag} is available. OK.')
        return True


def update_docker_image(name: str, tag: str = 'latest'):
    client = docker.from_env()
    if ':' in name:
        name, tag = name.split(':')
    try:
        click.echo(f'Pulling Docker image {name}:{tag}...')
        client.images.pull(name, tag=tag)
    except APIError:
        # Print log
        return False


def has_all_arcsecond_docker_images(tag: str = 'latest'):
    return all([has_docker_image(name, tag) for name in DOCKER_IMAGE_NAMES])


def pull_all_arcsecond_docker_images(tag: str = 'latest'):
    for image_name in DOCKER_IMAGE_NAMES:
        update_docker_image(image_name, tag)
