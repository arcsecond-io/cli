import json
import os
import subprocess

import click

from arcsecond.hosting.constants import PREFIX_SUB, PREFIX, PREFIX_SUB_FAIL


def setup_docker_host_on_macos() -> None:
    click.echo(PREFIX + 'Setup of $DOCKER_HOST on macOS...')
    context = subprocess.check_output(['docker', 'context', 'list', '--format', 'json'])
    data = json.loads(context)
    docker_host_list = [x['DockerEndpoint'] for x in data if x['Current']]
    if len(docker_host_list) != 1:
        click.echo(PREFIX_SUB + 'WARN: Unable to find the current Docker host.')
    os.environ['DOCKER_HOST'] = docker_host_list[0]
    click.echo(PREFIX_SUB + '$DOCKER_HOST=' + docker_host_list[0])


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
