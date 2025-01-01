#!/usr/bin/env bash
#
# Script Name: alacritty_fullscreen.sh 
# Description: Allow to use fullscreen hotkey with awesomeWM
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#   Needs to configure _____ file.
#  
if [ -n "$ALACRITTY_LOG" ]; then
    
    # Tu lógica para cambiar a pantalla completa en Alacritty
    echo "Ejecutando en Alacritty. Cambiando a pantalla completa."
    # Obtiene el ID de la ventana de Alacritty
    WINDOW_ID=$(wmctrl -lx | grep Alacritty | cut -d' ' -f1)
    
    # Cambia la ventana a modo de pantalla completa
    wmctrl -i -r $WINDOW_ID -b toggle,fullscreen
else
    echo "No se está ejecutando en Alacritty. Se usará F11 normalmente."
    xdotool key --clearmodifiers F11
fi