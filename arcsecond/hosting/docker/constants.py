# Note that container names are resolved as-is in a bridge custom network.

DOCKER_IMAGE_CONTAINERS_NAMES = {
    'web': ('arcsecond-web:latest', 'arcsecond-www', 'Webapp frontend'),
    'api': ('arcsecond-api:latest', 'arcsecond-api', 'APIs backend'),
    'worker': ('arcsecond-api:latest', 'arcsecond-worker', 'Background task worker'),
    'beat': ('arcsecond-api:latest', 'arcsecond-beat', 'Background task beat'),
    'db': ('postgres:16', 'arcsecond-db', 'Database'),
    'broker': ('redis:7.4', 'arcsecond-broker', 'Message Broker')
}

DOCKER_NETWORK_NAME = 'arcsecond-net'
