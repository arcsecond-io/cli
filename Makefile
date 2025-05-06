ARCH ?= amd64
TAG ?= latest

IMAGE_API = arcsecond-api-linux-$(ARCH)
IMAGE_WEB = arcsecond-web-linux-$(ARCH)
IMAGE_REDIS = arcsecond-redis-linux-$(ARCH)
IMAGE_POSTGRES = arcsecond-postgres-linux-$(ARCH)

# Paths
DOCKERFILE_API = ../arcsecond-back/.docker/Dockerfile
CONTEXT_API = ../arcsecond-back

DOCKERFILE_WEB = ../arcsecond-front/.docker/Dockerfile
CONTEXT_WEB = ../arcsecond-front

DOCKERFILE_REDIS = ./.docker/Dockerfile_redis
DOCKERFILE_POSTGRES = ./.docker/Dockerfile_postgres

# Build and save each image

arcsecond-api-linux:
	docker build --platform linux/$(ARCH) -t $(IMAGE_API):$(TAG) -f $(DOCKERFILE_API) $(CONTEXT_API)
	docker save $(IMAGE_API):$(TAG) -o $(IMAGE_API)_$(TAG).tar

arcsecond-web-linux:
	docker build --platform linux/$(ARCH) -t $(IMAGE_WEB):$(TAG) -f $(DOCKERFILE_WEB) $(CONTEXT_WEB)
	docker save $(IMAGE_WEB):$(TAG) -o $(IMAGE_WEB)_$(TAG).tar

arcsecond-redis-linux:
	docker build --platform linux/$(ARCH) -t $(IMAGE_REDIS):7.4 -f $(DOCKERFILE_REDIS) .
	docker save $(IMAGE_REDIS):7.4 -o $(IMAGE_REDIS)_7.4.tar

arcsecond-postgres-linux:
	docker build --platform linux/$(ARCH) -t $(IMAGE_POSTGRES):16 -f $(DOCKERFILE_POSTGRES) .
	docker save $(IMAGE_POSTGRES):16 -o $(IMAGE_POSTGRES)_16.tar

.PHONY: all clean

all: arcsecond-api-linux arcsecond-web-linux arcsecond-redis-linux arcsecond-postgres-linux

clean:
	rm -f arcsecond-*.tar
