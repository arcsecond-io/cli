import json
import os
import subprocess

import click
import requests

from arcsecond import ArcsecondAPI
from .constants import PREFIX_SUB, PREFIX


def setup_docker_host_on_macos() -> None:
    click.echo(PREFIX + 'Setup of $DOCKER_HOST on macOS.')
    context = subprocess.check_output(['docker', 'context', 'list', '--format', 'json'])
    data = json.loads(context)
    docker_host_list = [x['DockerEndpoint'] for x in data if x['Current']]
    if len(docker_host_list) != 1:
        print(PREFIX_SUB + 'WARN: Unable to find the current Docker host.')
    os.environ['DOCKER_HOST'] = docker_host_list[0]
    click.echo(PREFIX_SUB + '$DOCKER_HOST=' + docker_host_list[0])


def is_docker_available() -> bool:
    try:
        subprocess.check_output(['docker', 'ps'])
    except subprocess.CalledProcessError as e:
        click.echo(PREFIX_SUB + str(e))
        click.echo(PREFIX_SUB + 'You must install Docker. See https://docs.docker.com/desktop/')
        return False
    else:
        click.echo(PREFIX_SUB + 'Docker is installed and running.')
        return True


def is_arcsecond_api_reachable() -> bool:
    click.echo(PREFIX + 'Check if Arcsecond is reachable in the cloud.')
    response = requests.get('https://api.arcsecond.io')
    if response.status_code >= 300:
        click.echo(PREFIX_SUB + 'Arcsecond cloud API is not reachable. Try again in a few minutes?')
        return False
    click.echo(PREFIX_SUB + 'Host https://api.arcsecond.io is reachable.')
    return True


def is_user_logged_in(state) -> bool:
    click.echo(PREFIX + 'Check if user is logged in with the CLI.')
    if not ArcsecondAPI.is_logged_in(state):
        click.echo(PREFIX_SUB + 'You need to log in.')
        click.echo(PREFIX_SUB + 'Use `arcsecond login` (or `arcsecond register` if needed first).')
        return False
    click.echo(PREFIX_SUB + 'Logged in with username \"@' + ArcsecondAPI.username() + "\"")
    return True


def has_user_verified_email(state) -> bool:
    click.echo(PREFIX + 'Check if user email address is verified.')
    profile, error = ArcsecondAPI(state, verbose=True).fetch_full_profile()
    print(profile)
    return False
