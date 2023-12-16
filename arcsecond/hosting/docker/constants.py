# Note that container names are resolved as-is in a bridge custom network.

DOCKER_IMAGE_CONTAINERS_NAMES = {
    'www': ('arcsecond-www:latest', 'arcsecond-www', 'Webapp'),
    'api': ('arcsecond-api:latest', 'arcsecond-api', 'APIs'),
    'tq': ('arcsecond-api:latest', 'arcsecond-tq', 'Task Queue'),
    'bt': ('arcsecond-api:latest', 'arcsecond-bt', 'Beat'),
    'db': ('postgres:14', 'arcsecond-db', 'Database'),  # database
    'mb': ('rabbitmq:3.9', 'arcsecond-mb', 'Message Broker'),  # message broker
}

DOCKER_NETWORK_NAME = 'arcsecond-net'
