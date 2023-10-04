import time

import click
import docker
from docker.errors import APIError, NotFound


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
