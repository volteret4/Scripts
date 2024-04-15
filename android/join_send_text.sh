#!/usr/bin/env bash
#
# Script Name: join_send_text.sh
# Description: Send text to device using join api (Tasker)
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#   The script must have an .env file with $VARS in the same folder.
#   Depends on
#       Join app https://play.google.com/store/apps/details?id=com.joaomgcd.join
#

carpeta=$(dirname $(readlink "$0"))
source "${carpeta}/.env"

text="$(xclip -o)"
text="${text//%20/ /}"


curl "https://joinjoaomgcd.appspot.com/_ah/api/messaging/v1/sendPush?apikey=${APIKEY}&text=${text}&deviceId=${POCOX3}"
notify-send 'Texto enviado a' 'Poco X3 NFC' -t 10000
