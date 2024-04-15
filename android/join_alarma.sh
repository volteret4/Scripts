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


carpeta=$(dirname $(readlink "$0"))
source "${carpeta}/.env"

curl "https://joinjoaomgcd.appspot.com/_ah/api/messaging/v1/sendPush?apikey=${APIKEY}&find=true&deviceId=${POCOX3}"