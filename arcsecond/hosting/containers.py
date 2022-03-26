import time
from pathlib import Path

import click
import docker
from docker.errors import APIError, NotFound

from .constants import DOCKER_IMAGE_NAMES


def is_docker_container_running(name: str):
    client = docker.from_env()
    try:
        container = client.containers.get(name)
    except (APIError, NotFound):
        return False
    return container.status == 'running'


def run_db_container(restart=True):
    container_name = 'arcsecond-db'
    client = docker.from_env()

    if restart is True and is_docker_container_running(container_name):
        container = client.containers.get(container_name)
        container.stop()
        time.sleep(1)

    env = {
        'POSTGRES_USER': 'postgres',
        'POSTGRES_PASSWORD': 'postgres',
        'APP_DB_USER': 'arcsecond_docker',
        'APP_DB_PASS': 'arcsecond_docker',
        'APP_DB_NAME': 'arcsecond_docker'
    }

    check = {
        'test': ["CMD", "pg_isready", "-q", "-d", "postgres", "-U", "postgres"],
        'timeout': '45s',
        'interval': '10s',
        'retries': 10
    }

    ports = {
        '5432/tcp': 5432
    }

    vol = {
        str((Path(__file__).parent / 'postgres').resolve()): {'bind': '/docker-entrypoint-initdb.d/', 'mode': 'ro'},
        'arcsecond_postgres_data': {'bind': '/var/lib/postgresql/data/', 'mode': 'rw'}
    }

    click.echo(f'Starting Database container...')
    client.containers.run(DOCKER_IMAGE_NAMES[-1],
                          detach=True,
                          environment=env,
                          name=container_name,
                          ports=ports,
                          remove=True,
                          volumes=vol)

#
# def are_all_arcsecond_docker_containers_running():
#     return all([is_docker_container_running(name) for name in DOCKER_CONTAINER_NAMES])
#
#
# def run_all_arcsecond_docker_images(tag: str = 'latest'):
#     client = docker.from_env()
#     for index, name in enumerate(DOCKER_CONTAINER_NAMES):
#         if is_docker_container_running(name):
#             container = client.containers.get(name)
#             click.echo(f'Stopping running container {name}...')
#             container.stop()
#             click.echo(f'Pruning stopped container {name} to reclaim disk space...')
#             client.containers.prune({'name': name})
#         else:
#             click.echo(f'Starting container {name}...')
#             client.containers.run(DOCKER_IMAGE_NAMES[index], detach=True)
