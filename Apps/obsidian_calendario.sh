#!/usr/bin/env bash
#
# Script Name: crear_ics.sh
# Description: Crea archivos .ics de los calendarios de radicale y los dispone temporalmente en un servidor local para obsidian.
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# TODO: 
# Notes:
#   Dependencies:  - python3, 
#

# 1. Obtener variables
source "$(dirname "$0")/.env"

# 2. Obtener calendarios en formato ics
# Calendario
curl -u "${RADICALE_USER}":"${RADICALE_PW}" "${RADICALE_URL}/af5d8449-887b-278d-fbc9-7ba3b05012e4/" >> "${RUTA_TEMPORAL}/calendario.ics"
# Diario
curl -u "${RADICALE_USER}":"${RADICALE_PW}" "${RADICALE_URL}/25c56f48-f2c2-df82-b219-114ea9654071/" >> "${RUTA_TEMPORAL}/diario.ics"
# discos
curl -u "${RADICALE_USER}":"${RADICALE_PW}" "${RADICALE_URL}/d1573ec1-e837-6918-1dfe-bc0b6c04681d/" >> "${RUTA_TEMPORAL}/discos.ics"
# Eventos
curl -u "${RADICALE_USER}":"${RADICALE_PW}" "${RADICALE_URL}/f6ae8fa8-de75-262e-8ff3-2d1382df18e4/" >> "${RUTA_TEMPORAL}/eventos.ics"
# Personal
curl -u "${RADICALE_USER}":"${RADICALE_PW}" "${RADICALE_URL}/957abe1a-c92b-11ee-b607-44af28cddad9/" >> "${RUTA_TEMPORAL}/personal.ics"
# Tareas
curl -u "${RADICALE_USER}":"${RADICALE_PW}" "${RADICALE_URL}/7c44de6e-69ac-8496-f46d-d6753c9eab1f/" >> "${RUTA_TEMPORAL}/tareas.ics"
# Turnos
curl -u "${RADICALE_USER}":"${RADICALE_PW}" "${RADICALE_URL}/987a0de8-661b-c19d-41c1-4bd065bc29e0/" >> "${RUTA_TEMPORAL}/turnos.ics"


# 3. Lanzar servidor para los archivos ics.
python3 -m http.server 8000 --bind 0.0.0.0 --directory "${RUTA_TEMPORAL}" &
SERVER_PID=$!  # Captura el PID del servidor
echo "Servidor lanzado con PID: $SERVER_PID"


# 4. Lanzar Obsidian y desvincularlo del terminal
obsidian &
OBSIDIAN_PID=$!  # Captura el PID de Obsidian
#disown $OBSIDIAN_PID  # Desvincula específicamente Obsidian
echo "Obsidian lanzado con PID: $OBSIDIAN_PID"


# 4. Esperar un tiempo para que Obsidian procese los archivos .ics
WAIT_TIME=300  # Cambia este valor según el tiempo necesario
echo "Esperando $WAIT_TIME segundos para que Obsidian procese los archivos..."
sleep $WAIT_TIME


# 5. Detener el servidor
kill $SERVER_PID
echo "Servidor detenido."