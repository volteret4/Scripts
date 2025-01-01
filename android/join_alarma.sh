#!/usr/bin/env bash
#
# Script Name: join_alarma.sh
# Description: Send a "find me" alarm to device using join api (Tasker).
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#   The script must have an .env file with $VARS in the same folder.
#   Depends on:
#       Join app https://play.google.com/store/apps/details?id=com.joaomgcd.join
#


#carpeta=$(dirname $(readlink "$0"))
carpeta="${HOME}/Scripts/android/.env"
# source "${carpeta}/.env"



export $(awk -F= '{output=output" "$1"="$2} END {print output}' $carpeta)
echo "api $API_KEY"
echo "poco $POCOX3"
echo ""
url="https://joinjoaomgcd.appspot.com/_ah/api/messaging/v1/sendPush?apikey=${API_KEY}&find=true&deviceId=${POCOX3}"
echo $url
echo ""
curl $url