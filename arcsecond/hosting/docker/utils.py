import json
import os
import subprocess
import time

import click
import docker
from docker.errors import APIError, NotFound

from arcsecond.hosting.constants import PREFIX_SUB, PREFIX
from arcsecond.hosting.constants import PREFIX_SUB, PREFIX_SUB_FAIL


def is_docker_available() -> bool:
    try:
        subprocess.check_output(['docker', 'ps'])
    except subprocess.CalledProcessError as e:
        click.echo(PREFIX_SUB_FAIL + str(e))
        click.echo(PREFIX_SUB_FAIL + 'You must install Docker. See https://docs.docker.com/desktop/')
        return False
    else:
        click.echo(PREFIX_SUB + 'Docker is installed and running.')
        return True

def __get_docker_container_status(name: str):
    client = docker.from_env()
    try:
        container = client.containers.get(name)
    except (APIError, NotFound):
        return None
    return container.status


def is_docker_container_running(name: str):
    return __get_docker_container_status(name) == 'running'


def is_docker_container_exited(name: str):
    return __get_docker_container_status(name) == 'exited'


def __perform_container_bookkeeping(container_name: str, stop: bool):
    client = docker.from_env()

    if is_docker_container_exited(container_name):
        client.containers.get(container_name).remove()
        time.sleep(1)

    if stop is True and is_docker_container_running(container_name) is True:
        click.echo(f'Stopping currently running container "{container_name}"...')
        container = client.containers.get(container_name)
        container.stop()
        time.sleep(1)


def setup_docker_host_on_macos() -> None:
    click.echo(PREFIX + 'Setup of $DOCKER_HOST on macOS.')
    context = subprocess.check_output(['docker', 'context', 'inspect', 'desktop-linux'])
    data = json.loads(context)
    try:
        docker_host = data[0]['Endpoints']['docker']['Host']
    except (KeyError, IndexError):
        click.echo(PREFIX_SUB + 'WARN: Unable to find the current Docker host.')
    else:
        os.environ['DOCKER_HOST'] = docker_host
        click.echo(PREFIX_SUB + '$DOCKER_HOST=' + docker_host)
