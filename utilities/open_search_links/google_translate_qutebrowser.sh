#!/usr/bin/env bash
#
# Script Name: google_translate_qutebrowser.sh 
# Description: Buscar texto seleccionado (copiado automáticamente xclip) en google translatte en qutebrowser.
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#   Dependencies:
#       Firefox     Thorium-browser      chromium       xdotool
#

traduce="$(clipman read 0)"
qutebrowser "https://translate.google.com/?sl=auto&tl=es&text=${traduce}"