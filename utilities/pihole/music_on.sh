#!/usr/bin/env bash
#
# Script Name: music_on.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#
#

# Dirección IP o nombre de host de tu servidor Pi-hole
PIHOLE_HOST="192.168.1.166"

# Calcular la marca de tiempo de hace  5 minutos
time=$(date -d "-1 minutes" +%s)

# Convertir la marca de tiempo a un formato legible por la API de Pi-hole
START_TIME=$(date -d @$time -u +"%Y-%m-%d %H:%M:%S")

# Endpoint de la API de Pi-hole para obtener consultas
API_ENDPOINT="/admin/api.php"

# Parámetros de la API para filtrar consultas a YouTube
API_PARAMETERS="?getAllQueries&start=$time&auth=$AUTH"


# Realizar la solicitud a la API de Pi-hole
curl -s "http://$PIHOLE_HOST$API_ENDPOINT$API_PARAMETERS"
