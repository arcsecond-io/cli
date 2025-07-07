# Note that container names are resolved as-is in a bridge custom network.

DOCKER_IMAGE_CONTAINERS_NAMES = {
    'web': ('arcsecond-local-web:latest', 'arcsecond-www', 'Webapp frontend'),
    'api': ('arcsecond-local-api:latest', 'arcsecond-api', 'APIs backend'),
    'worker': ('arcsecond-local-api:latest', 'arcsecond-worker', 'Background task worker'),
    'beat': ('arcsecond-local-api:latest', 'arcsecond-beat', 'Background task beat'),
    'db': ('arcsecond-local-postgres:1.0.0', 'arcsecond-db', 'Database'),
    'broker': ('arcsecond-local-redis:1.0.0', 'arcsecond-broker', 'Message Broker')
}

DOCKER_NETWORK_NAME = 'arcsecond-net'
