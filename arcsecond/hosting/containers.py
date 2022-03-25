import docker
from docker.errors import APIError, NotFound


def is_docker_container_running(name: str):
    client = docker.from_env()
    try:
        container = client.containers.get(name)
    except (APIError, NotFound):
        return False
    return container.status == 'status'

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
