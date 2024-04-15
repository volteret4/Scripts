#!/usr/bin/env bash
#
# Script Name: auto_identify.sh 
# Description: Secuencia de hotkeys para usar Autoidentify de Comic Tagger cuando falla Autotag
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#
#

# Función para enviar las pulsaciones de teclas
function send_keys {
    sleep 1
    xdotool key ctrl+i
    sleep 3
    xdotool key Return
    sleep 1
    xdotool key ctrl+s
    sleep 0.5
    xdotool key Return
    sleep 1
    xdotool key --clearmodifiers Down
    sleep 2
}

# Bucle principal
while true; do
    send_keys
done
