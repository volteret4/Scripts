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

if [ -z "${titulo}" ]
    then
        exit 1
    else
        vdirsyncer sync &
fi

contenido=$(copyq clipboard)

anio=$(date +%Y)


fecha=$(zenity --calendar \
    --title="Discos" \
    --text="Elige una fecha")

fecha=$(echo "${fecha}" | sed 's/\//./g')
fecha="${fecha%??}${anio}"
echo "${fecha}"

ans=$?
if [ $ans -eq 0 ]
then
    khal new -a discos "${fecha}" "${titulo}":::"${contenido}"
    #zenity --info --text='creado nuevo evento'
else
    zenity --info --text='por tabaco'
fi

sleep 10

vdirsyncer sync
