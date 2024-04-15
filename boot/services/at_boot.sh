#!/usr/bin/env bash

carpeta=$(dirname $(readlink "$0"))
source "${carpeta}/.env"

echo "test" >> /home/huan/uptime

text="Arcolinux_On"

curl "https://joinjoaomgcd.appspot.com/_ah/api/messaging/v1/sendPush?apikey=${APIKEY}&text=${text}&deviceId=${POCOX3}"
