#!/bin/bash

source /home/huan/Scripts/utilities/notificaciones/.env

URL="http://192.168.1.191:8123/api/states/sensor.termometro_cueva_temperatura"

# Obtener el valor del sensor (temperatura)
TEMPERATURE="$(curl -s -X GET "$URL" -H "Content-Type: application/json; charset=utf-8" -H "Authorization: Bearer $TOKEN_HASS" | jq -r '.state')"

# Imprimir la temperatura
echo "$TEMPERATURE°C   "