#!/bin/bash
# Imprime la temperatura del sensor de Home Assistant (solo el número).
# Sale con código 1 y sin imprimir nada si HA no responde o el sensor no
# tiene un valor numérico ("unavailable", "unknown"…).

source /home/huan/Scripts/utilities/notificaciones/.env

URL="http://192.168.1.191:8123/api/states/sensor.termometro_cueva_temperatura"

# Obtener el valor del sensor (temperatura)
TEMPERATURE="$(curl -s -m 5 -X GET "$URL" -H "Content-Type: application/json; charset=utf-8" -H "Authorization: Bearer $TOKEN_HASS" | jq -r '.state' 2>/dev/null)"

[[ "$TEMPERATURE" =~ ^-?[0-9]+([.][0-9]+)?$ ]] || exit 1
echo "$TEMPERATURE"
