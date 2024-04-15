#!/usr/bin/env bash
#
# Script Name: spotify.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#
#

carpeta=$(dirname $(readlink "$0"))
source "${carpeta}/.env"

artist=beatles
song=yesterday
yt_token=


curl --request POST \
  --url https://api.spotify.com/v1/users/pollolpc/playlists \
  --header 'Authorization: Bearer $SPOT_TOKEN' \
  --header 'Content-Type: application/json' \
  --data '{
    "name": "New Playlist",
    "description": "New playlist description",
    "public": false
}'