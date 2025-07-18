#!/bin/bash

echo $GITHUB_TOKEN | docker login ghcr.io -u seamex --password-stdin
docker build -t ghcr.io/seamex/acr-exporter:0.1.0 .
docker push ghcr.io/seamex/acr-exporter:0.1.0

docker buildx create --name multiarch-builder --use
docker buildx inspect --bootstrap


docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t ghcr.io/seamex/acr-exporter:0.1.0 \
  --push .

docker buildx imagetools inspect ghcr.io/seamex/acr-exporter:0.1.0


echo $GITHUB_TOKEN | helm registry login ghcr.io --username seamex --password-stdin
helm package .
helm push  acr-exporter-0.1.0.tgz oci://ghcr.io/seamex/acr-exporter