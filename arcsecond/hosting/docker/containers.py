import subprocess
import sys
from pathlib import Path

import click
import docker
from docker.errors import APIError, NotFound

from .constants import DOCKER_IMAGE_CONTAINERS_NAMES, DOCKER_NETWORK_NAME
from .images import has_docker_image
from .utils import (
    __perform_container_bookkeeping,
    is_docker_container_running,
    setup_docker_host_on_macos,
    __get_docker_container_status
)


def setup_network():
    client = docker.from_env()
    try:
        client.networks.get(DOCKER_NETWORK_NAME)
    except (APIError, NotFound):
        client.networks.create(DOCKER_NETWORK_NAME, driver="bridge")


def run_db_container(restart=True):
    image_name, container_name, service_name = DOCKER_IMAGE_CONTAINERS_NAMES['db']
    if is_docker_container_running(container_name) and not restart:
        return

    __perform_container_bookkeeping(container_name, restart)

    env = {
        'POSTGRES_USER': 'postgres',
        'POSTGRES_PASSWORD': 'postgres',
        'APP_DB_USER': 'arcsecond_docker',
        'APP_DB_PASS': 'arcsecond_docker',
        'APP_DB_NAME': 'arcsecond_docker'
    }

    # undocumented, test must be a string. See
    # https://github.com/docker/docker-py/issues/2529
    # check = {
    #     'test': "CMD pg_isready -q -d postgres -U postgres",
    #     'interval': 1e9 * 1,
    #     'timeout': 1e9 * 30,
    #     'retries': 10,
    #     'start_period': 1e9 * 30
    # }

    ports = {
        '5432/tcp': 5432
    }

    vol = {
        str((Path(__file__).parent / 'postgres').resolve()): {'bind': '/docker-entrypoint-initdb.d/', 'mode': 'ro'},
        'arcsecond_postgres_data': {'bind': '/var/lib/postgresql/data/', 'mode': 'rw'}
    }

    click.echo(f'Starting {service_name}...')
    client = docker.from_env()
    client.containers.run(image_name,
                          detach=True,
                          environment=env,
                          name=container_name,
                          network=DOCKER_NETWORK_NAME,
                          ports=ports,
                          remove=True,
                          volumes=vol)

    click.echo(f'Waiting for {service_name} to start...')
    subprocess.check_call(["wait-for-it", "-q", "-t", "30", "-s", "localhost:5432"])


def run_broker_container(restart=True):
    image_name, container_name, service_name = DOCKER_IMAGE_CONTAINERS_NAMES['broker']
    if is_docker_container_running(container_name) and not restart:
        return

    __perform_container_bookkeeping(container_name, restart)

    env = {
        'RABBITMQ_DEFAULT_USER': 'arcsecond_docker',
        'RABBITMQ_DEFAULT_PASS': 'arcsecond_docker',
        'RABBITMQ_DEFAULT_VHOST': 'arcsecond_docker_vhost',
        'RABBITMQ_NODE_PORT': '5672'
    }

    ports = {
        '5672/tcp': 5672
    }

    click.echo(f'Starting {service_name} container...')
    client = docker.from_env()
    client.containers.run(image_name,
                          detach=True,
                          environment=env,
                          name=container_name,
                          network=DOCKER_NETWORK_NAME,
                          ports=ports,
                          remove=True)

    click.echo(f'Waiting for {service_name} to start...')
    subprocess.check_call(["wait-for-it", "-q", "-t", "30", "-s", "localhost:5672"])


def run_api_container(config, restart=True, do_try=True):
    image_name, container_name, service_name = DOCKER_IMAGE_CONTAINERS_NAMES['api']
    if is_docker_container_running(container_name) and not restart:
        return

    __perform_container_bookkeeping(container_name, restart)

    section = 'hosting:try' if do_try else 'hosting'

    env = {
        'SECRET_KEY': config.read_key('secret_key', section_name=section),
        'DJANGO_SETTINGS_MODULE': 'settings.local',
        'RABBITMQ_USER': 'arcsecond_docker',
        'RABBITMQ_PASSWORD': 'arcsecond_docker',
        'RABBITMQ_VHOST': 'arcsecond_docker_vhost',
        'RABBITMQ_SERVER': DOCKER_IMAGE_CONTAINERS_NAMES['mb'][1] + ':5672',
        'EMAIL_HOST': config.read_key('email_host', section_name=section),
        'EMAIL_HOST_USER': config.read_key('email_host_user', section_name=section),
        'EMAIL_HOST_PASSWORD': config.read_key('email_host_password', section_name=section),
        'EMAIL_ADMIN': config.read_key('email_admin', section_name=section),
        'FIELD_ENCRYPTION_KEY': config.read_key('field_encryption_key', section_name=section),
        # 'ARCSECOND_DATA_STORAGE': ''
    }

    vol = {
        'arcsecond_api_static_files': {'bind': '/home/app/static', 'mode': 'rw'}
    }

    # port = config_file_read_key('api_port', section=section)
    ports = {
        '8080/tcp': 8080
    }

    click.echo(f'Starting {service_name} container (be patient, this one may take a minute or two)...')
    client = docker.from_env()
    client.containers.run(image_name,
                          detach=True,
                          environment=env,
                          name=container_name,
                          network=DOCKER_NETWORK_NAME,
                          ports=ports,
                          remove=True,
                          volumes=vol)

    click.echo(f'Waiting for {service_name} container to start...')
    subprocess.check_call(["wait-for-it", "-q", "-t", "30", "-s", "localhost:8080"])


def run_web_container(restart=True):
    image_name, container_name, service_name = DOCKER_IMAGE_CONTAINERS_NAMES['web']
    if is_docker_container_running(container_name) and not restart:
        return

    __perform_container_bookkeeping(container_name, restart)

    # port = config_file_read_key('api_port', section=section)
    ports = {
        '80/tcp': 3003
    }

    click.echo(f'Starting {service_name}...')
    client = docker.from_env()
    client.containers.run(image_name,
                          detach=True,
                          name=container_name,
                          network=DOCKER_NETWORK_NAME,
                          ports=ports,
                          remove=True)

    click.echo(f'Waiting for {service_name} to start...')
    subprocess.check_call(["wait-for-it", "-q", "-t", "30", "-s", "localhost:3003"])


def stop_all_containers():
    container_names = [cont for (_, cont, _) in DOCKER_IMAGE_CONTAINERS_NAMES.values()]
    for container_name in container_names:
        __perform_container_bookkeeping(container_name, stop=True)


def get_all_containers_status_string() -> str:
    if sys.platform == 'darwin':
        setup_docker_host_on_macos()
    statuses = []
    for image_name, container_name, service_name in DOCKER_IMAGE_CONTAINERS_NAMES.values():
        container_status = __get_docker_container_status(container_name)
        container_status_msg = f'Container status: {container_status}.' \
            if container_status is not None \
            else 'No running container.'
        image_status = has_docker_image(image_name)
        image_status_msg = 'Docker image locally available.' if image_status is True else 'Image not yet pulled.'
        statuses.append(f'Service "{service_name}": {image_status_msg} {container_status_msg}')
    return '\n'.join(statuses)
