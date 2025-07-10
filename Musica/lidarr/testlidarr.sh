#!/usr/bin/env bash
#
# Script Name: testlidarr.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:
#
#
carpeta=$(dirname $(readlink "$0"))
source "${carpeta}/.env"


artista="rolling stones"
json=$(curl "http://192.168.1.166:8686/api/v1/artist/lookup?apikey=${API}&term=${artista}")
echo ${json} | jq .
