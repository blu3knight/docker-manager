#!/bin/sh
#
# This scripts starts the Plex Docker
#
echo "************************************"
echo "* Starting Sonarr Server Docker    *"
echo "************************************"
echo ""
# The server is being pulled from this location:
# https://hub.docker.com/r/linuxserver/sonarr
#
#  -v /data/docker/sonarr:/data \

docker run -d \
  --name=sonarr \
  -e PUID=1000 \
  -e PGID=1000 \
  -e TZ=America/New_York \
  -p 8989:8989 \
  -v /sonarr/sonarr-conf:/config \
  -v /sonarr/tv:/tv \
  -v /sonarr/download:/download \
  --restart unless-stopped \
  ghcr.io/linuxserver/sonarr:latest
