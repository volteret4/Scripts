#!/usr/bin/env bash
#
# Script Name: crear_evento_caldav.sh 
# Description: Añadir evento en caldav de radicale (IP Local: 192.168.1.)
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#
#

# script_name=$(basename "$0")
# bash "${HOME}/Scripts/utilities/recuento_scripts.sh ${script_name}"

titulo=$(zenity --entry --text 'Titulo del evento')
titulo="$(echo $titulo | tr -d '\n' | tr -d '\r' )"
if [ -z "${titulo}" ]
    then
        exit 1
    else
        vdirsyncer sync &
fi

contenido="$(copyq clipboard | tr -d '\n' | tr -d '\r' )"

#anio=$(date +%Y)


fecha=$(zenity --calendar \
    --title="Discos" \
    --text="Elige una fecha")

fecha=$(echo "${fecha}" | sed 's/\//./g')
fecha="${fecha%.*}.20${fecha##*.}"
#fecha="${fecha%??}${anio}"
echo "${fecha}"

ans=$?
if [ $ans -eq 0 ]
then
    khal new -a discos "${fecha}" "${titulo}":::"${contenido}"
    #zenity --info --text='creado nuevo evento'
else
    zenity --info --text='por tabaco'
fi

sleep 2

vdirsyncer sync

status=$?

# Verifica si hubo un error
if [ $status -ne 0 ]; then
    notify-send -t 10 "Error en vdirsyncer" "Se produjo un error al sincronizar: código $status"
else
    notify-send "Sincronización exitosa" "La sincronización se completó sin errores."
fi
