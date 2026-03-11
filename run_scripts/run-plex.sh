#!/bin/sh
#
# This scripts starts the Plex Docker
#
echo "********************************"
echo "* Starting Plex Server Docker  *"
echo "********************************"
echo ""
# The server is being pulled from this location:
# https://hub.docker.com/r/linuxserver/plex
#

docker run -d \
  --name=plex \
  --network=host \
  -e TZ="<timezone>" \
  -e PLEX_CLAIM="<claimToken>" \
  -v <path/to/plex/database>:/config \
  -v <path/to/transcode/temp>:/transcode \
  -v <path/to/media>:/data \
  plexinc/pms-docker
