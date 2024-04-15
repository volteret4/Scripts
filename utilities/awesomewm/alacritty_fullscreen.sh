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

# Obtiene el ID de la ventana de Alacritty
WINDOW_ID=$(wmctrl -lx | grep Alacritty | cut -d' ' -f1)

# Cambia la ventana a modo de pantalla completa
wmctrl -i -r $WINDOW_ID -b toggle,fullscreen

