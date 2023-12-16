import json
import os
import subprocess
import time

import click
import docker
from docker.errors import APIError, NotFound

from arcsecond.hosting.constants import PREFIX_SUB, PREFIX


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
    context = subprocess.check_output(['docker', 'context', 'list', '--format', 'json'])
    data = json.loads(context)
    docker_host_list = [x['DockerEndpoint'] for x in data if x['Current']]
    if len(docker_host_list) != 1:
        print(PREFIX_SUB + 'WARN: Unable to find the current Docker host.')
    os.environ['DOCKER_HOST'] = docker_host_list[0]
    click.echo(PREFIX_SUB + '$DOCKER_HOST=' + docker_host_list[0])
