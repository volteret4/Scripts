#!/usr/bin/env bash
#
# Script Name: recuento_scripts.sh 
# Description: Contar el numero de veces que se lanza un script
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:
#
#

#Nombre del script
script_name="${1}"

# Nombre del archivo temporal para almacenar el recuento

COUNTER_FILE="/tmp/counter_${script_name}"

echo "$(date +%Y-%m-%d) - ${script_name} ejecutado" >> "${COUNTER_FILE}"
