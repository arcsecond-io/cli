import subprocess
from pathlib import Path

import click
import docker
from docker.errors import APIError, NotFound

from arcsecond.config import config_file_read_key
from .constants import DOCKER_IMAGE_CONTAINERS_NAMES, DOCKER_NETWORK_NAME
from .images import has_all_arcsecond_docker_images, has_docker_image, is_docker_available, \
    pull_all_arcsecond_docker_images
from .setup import setup_hosting_variables
from .utils import __get_docker_container_status, __perform_container_bookkeeping


def setup_network():
    client = docker.from_env()
    try:
        client.networks.get(DOCKER_NETWORK_NAME)
    except (APIError, NotFound):
        client.networks.create(DOCKER_NETWORK_NAME, driver="bridge")


def run_db_container(restart=True):
    image_name, container_name, service_name = DOCKER_IMAGE_CONTAINERS_NAMES['db']
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


def run_mb_container(restart=True):
    image_name, container_name, service_name = DOCKER_IMAGE_CONTAINERS_NAMES['mb']
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


def run_api_container(restart=True, do_try=True):
    image_name, container_name, service_name = DOCKER_IMAGE_CONTAINERS_NAMES['api']
    __perform_container_bookkeeping(container_name, restart)

    section = 'hosting:try' if do_try else 'hosting'

    env = {
        'SECRET_KEY': config_file_read_key('secret_key', section=section),
        'DJANGO_SETTINGS_MODULE': 'settings.local',
        'RABBITMQ_USER': 'arcsecond_docker',
        'RABBITMQ_PASSWORD': 'arcsecond_docker',
        'RABBITMQ_VHOST': 'arcsecond_docker_vhost',
        'RABBITMQ_SERVER': DOCKER_IMAGE_CONTAINERS_NAMES['mb'][1] + ':5672',
        'EMAIL_HOST': 'ssl0.ovh.net',
        'EMAIL_HOST_PASSWORD': 'dummy',
        'EMAIL_HOST_USER': 'cedric@arcsecond.io',
        'EMAIL_ADMIN': 'cedric@arcsecond.io',
        'ARCSECOND_DATA_STORAGE': ''
    }

    # for key in ['EMAIL_HOST', 'EMAIL_HOST_USER', 'EMAIL_HOST_PASSWORD', 'EMAIL_ADMIN']:
    #     value = config_file_read_key(key.lower(), section=section)
    #     if value[0] == '$':
    #         value = os.environ.get(value[1:], '')
    #     if value.strip() == '':
    #         # raise an error
    #         pass
    #     env.update(**{key: value})

    vol = {
        'arcsecond_api_static_files': {'bind': '/home/app/static', 'mode': 'rw'}
    }

    # port = config_file_read_key('api_port', section=section)
    ports = {
        '8000/tcp': 8000
    }

    cmd = "sh -c 'python manage.py migrate --no-input && " \
          "python manage.py collectstatic --no-input && " \
          f"gunicorn --bind 0.0.0.0:8000 arcsecond.wsgi:application'"

    click.echo(f'Starting {service_name} container (be patient, this one may take a minute or two)...')
    client = docker.from_env()
    client.containers.run(image_name,
                          command=cmd,
                          detach=True,
                          environment=env,
                          name=container_name,
                          network=DOCKER_NETWORK_NAME,
                          ports=ports,
                          remove=True,
                          volumes=vol)

    click.echo(f'Waiting for {service_name} container to start...')
    subprocess.check_call(["wait-for-it", "-q", "-t", "30", "-s", "localhost:8000"])


def run_www_container(restart=True):
    image_name, container_name, service_name = DOCKER_IMAGE_CONTAINERS_NAMES['www']
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


def run_arcsecond(do_try=True, skip_setup=False):
    if not is_docker_available():
        click.echo('You need to install Docker. Visit https://docker.com')
        return
    if not skip_setup:
        setup_hosting_variables(do_try=do_try)
    if not has_all_arcsecond_docker_images():
        pull_all_arcsecond_docker_images()
    setup_network()
    run_db_container(restart=True)
    run_mb_container(restart=True)
    run_api_container(restart=True, do_try=do_try)
    run_www_container(restart=True)


def stop_arcsecond():
    container_names = [cont for (_, cont, _) in DOCKER_IMAGE_CONTAINERS_NAMES.values()]
    for container_name in container_names:
        __perform_container_bookkeeping(container_name, stop=True)


def get_arcsecond_status():
    for image_name, container_name, service_name in DOCKER_IMAGE_CONTAINERS_NAMES.values():
        container_status = __get_docker_container_status(container_name)
        container_status_msg = f'Container status: {container_status}.' if container_status is not None else 'No running container.'
        image_status = has_docker_image(image_name)
        image_status_msg = 'Docker image locally available.' if image_status is True else 'Image not yet pulled.'
        click.echo(f'Service "{service_name}": {image_status_msg} {container_status_msg}')
