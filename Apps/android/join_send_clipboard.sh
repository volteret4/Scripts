#!/usr/bin/env bash
#
# Script Name: join_send_clipboard.sh
# Description: Send copyq clipboard to device using join api (Taske)
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:
#   The script must have an .env file with $VARS in the same folder.
#   Depends on app:
#       copyq 
#       Join app [https://play.google.com/store/apps/details?id=com.joaomgcd.join]
#

carpeta=$(dirname $(readlink "$0"))
source "${carpeta}/.env"

clipboard="$(copyq read 0)"
clipboard="${clipboard// /%20/}"

curl "https://joinjoaomgcd.appspot.com/_ah/api/messaging/v1/sendPush?apikey=${APIKEY}&clipboard=${clipboard}&deviceId=${POCOF6}"
notify-send 'Clipboard enviado a' 'Poco F6' -t 10000
