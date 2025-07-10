#!/usr/bin/env bash
#
# Script Name: playing_metadata_info.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:
#
#

POSITION=$(echo '{ "command": ["get_property_string", "time-pos"] }' | socat - /tmp/mpvsocket | jq .data | tr '"' ' ' | cut -d'.' -f 1)

REMAINING=$(echo '{ "command": ["get_property_string", "time-remaining"] }' | socat - /tmp/mpvsocket | jq .data | tr '"' ' ' | cut -d'.' -f 1)

METADATA=$(echo '{ "command": ["get_property", "filtered-metadata"] }' | socat - /tmp/mpvsocket | jq ".data.Artist, .data.Album, .data.Title")

echo $METADATA
#printf '%d:%02d:%02d' $(($POSITION/3600)) $(($POSITION%3600/60)) $(($POSITION%60))
#printf ' %d:%02d:%02d\n' $(($REMAINING/3600)) $(($REMAINING%3600/60)) $(($REMAINING%60))