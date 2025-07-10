#!/usr/bin/env bash
#
# Script Name: debug_scripts.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:    Requieres a ntffy server
#
#

# Obtener la información necesaria
nombre_script=$(basename "$0")
path_script=$(readlink -f "$0")
hostname=$(hostname)
ip_local=$(hostname -I)
syslog=$(tail -n 1 /var/log/syslog)  # Cambia esto según dónde estén los logs de errores

# Obtener el mensaje de error de la señal ERR
error="Error al ejecutar el script: $(trap -p ERR | cut -d "'" -f 2)"

# Preparar el mensaje para enviar
mensaje="**Nombre del script:** $nombre_script
**Path del script:** $path_script
**Hostname del servidor:** $hostname
**IP local:** $ip_local
**Error del syslog:** $syslog
**Error del script:** $error"
echo $mensaje
curl -H "Markdown: yes" -H "Title: Ticketmaster" -H "Priority: min" -H "Tags: loudspeaker" -d "$mensaje" https://ntfy.pollete.duckdns.org/scripts
