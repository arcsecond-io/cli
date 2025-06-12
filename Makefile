ARCH ?= amd64
TAG ?= latest

IMAGE_API = arcsecond-api-linux-$(ARCH)
IMAGE_WEB = arcsecond-web-linux-$(ARCH)
IMAGE_REDIS = arcsecond-redis-linux-$(ARCH)
IMAGE_POSTGRES = arcsecond-postgres-linux-$(ARCH)

IMAGE_API_OCI = arcsecond-api
IMAGE_WEB_OCI = arcsecond-web
IMAGE_REDIS_OCI = arcsecond-redis
IMAGE_POSTGRES_OCI = arcsecond-postgres

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
	docker save $(IMAGE_API):$(TAG) -o tars/$(IMAGE_API)_$(TAG).tar

arcsecond-web-linux:
	docker build --platform linux/$(ARCH) -t $(IMAGE_WEB):$(TAG) -f $(DOCKERFILE_WEB) $(CONTEXT_WEB)
	docker save $(IMAGE_WEB):$(TAG) -o tars/$(IMAGE_WEB)_$(TAG).tar

arcsecond-redis-linux:
	docker build --platform linux/$(ARCH) -t $(IMAGE_REDIS):7.4 -f $(DOCKERFILE_REDIS) .
	docker save $(IMAGE_REDIS):7.4 -o tars/$(IMAGE_REDIS)_7.4.tar

arcsecond-postgres-linux:
	docker build --platform linux/$(ARCH) -t $(IMAGE_POSTGRES):16 -f $(DOCKERFILE_POSTGRES) .
	docker save $(IMAGE_POSTGRES):16 -o tars/$(IMAGE_POSTGRES)_16.tar

arcsecond-api-oci:
	docker buildx build --platform 'linux/amd64,linux/arm64' -o 'type=oci,dest=-' -t $(IMAGE_API_OCI):$(TAG) -f $(DOCKERFILE_API) $(CONTEXT_API) > tars/$(IMAGE_API_OCI)_$(TAG).tar

arcsecond-web-oci:
	docker buildx build --platform 'linux/amd64,linux/arm64' -o 'type=oci,dest=-' -t $(IMAGE_WEB_OCI):$(TAG) -f $(DOCKERFILE_WEB) $(CONTEXT_WEB) > tars/$(IMAGE_WEB_OCI)_$(TAG).tar

arcsecond-redis-oci:
	docker buildx build --platform 'linux/amd64,linux/arm64' -o 'type=oci,dest=-' -t $(IMAGE_REDIS_OCI):$(TAG) -f $(DOCKERFILE_REDIS) . > tars/$(IMAGE_REDIS_OCI)_$(TAG).tar

arcsecond-postgres-oci:
	docker buildx build --platform 'linux/amd64,linux/arm64' -o 'type=oci,dest=-' -t $(IMAGE_POSTGRES_OCI):$(TAG) -f $(DOCKERFILE_POSTGRES) . > tars/$(IMAGE_POSTGRES_OCI)_$(TAG).tar

.PHONY: core aux clean

core: arcsecond-api-linux arcsecond-web-linux

aux: arcsecond-redis-linux arcsecond-postgres-linux

oci: arcsecond-api-oci arcsecond-web-oci arcsecond-redis-oci arcsecond-postgres-oci

clean:
	rm -f arcsecond-*.tar tars/*
