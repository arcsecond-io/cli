.PHONY: all clean

all: \
  arcsecond-api-linux-amd64.tar \
  arcsecond-api-linux-arm64.tar \
  arcsecond-web-linux-amd64.tar \
  arcsecond-web-linux-arm64.tar \
  arcsecond-redis-linux-amd64.tar \
  arcsecond-redis-linux-arm64.tar \
  arcsecond-postgres-linux-amd64.tar \
  arcsecond-postgres-linux-arm64.tar

# arcsecond-api
arcsecond-api-linux-amd64.tar:
	docker buildx build \
	  --platform linux/amd64 \
	  --output type=tar,dest=$@ \
	  --tag arcsecond-api:linux-amd64 \
	  --file ../arcsecond-back/.docker/Dockerfile \
	  ../arcsecond-back

arcsecond-api-linux-arm64.tar:
	docker buildx build \
	  --platform linux/arm64 \
	  --output type=tar,dest=$@ \
	  --tag arcsecond-api:linux-arm64 \
	  --file ../arcsecond-back/.docker/Dockerfile \
	  ../arcsecond-back

# arcsecond-web
arcsecond-web-linux-amd64.tar:
	docker buildx build \
	  --platform linux/amd64 \
	  --output type=tar,dest=$@ \
	  --tag arcsecond-web:linux-amd64 \
	  --file ../arcsecond-front/.docker/Dockerfile \
	  ../arcsecond-front

arcsecond-web-linux-arm64.tar:
	docker buildx build \
	  --platform linux/arm64 \
	  --output type=tar,dest=$@ \
	  --tag arcsecond-web:linux-arm64 \
	  --file ../arcsecond-front/.docker/Dockerfile \
	  ../arcsecond-front

# arcsecond-redis
arcsecond-redis-linux-amd64.tar:
	docker buildx build \
	  --platform linux/amd64 \
	  --output type=tar,dest=$@ \
	  --tag arcsecond-redis:linux-amd64 \
	  --file .docker/Dockerfile_redis \
	  .

arcsecond-redis-linux-arm64.tar:
	docker buildx build \
	  --platform linux/arm64 \
	  --output type=tar,dest=$@ \
	  --tag arcsecond-redis:linux-arm64 \
	  --file .docker/Dockerfile_redis \
	  .

# arcsecond-postgres
arcsecond-postgres-linux-amd64.tar:
	docker buildx build \
	  --platform linux/amd64 \
	  --output type=tar,dest=$@ \
	  --tag arcsecond-postgres:linux-amd64 \
	  --file .docker/Dockerfile_postgres \
	  .

arcsecond-postgres-linux-arm64.tar:
	docker buildx build \
	  --platform linux/arm64 \
	  --output type=tar,dest=$@ \
	  --tag arcsecond-postgres:linux-arm64 \
	  --file .docker/Dockerfile_postgres \
	  .

clean:
	rm -f *.tar
