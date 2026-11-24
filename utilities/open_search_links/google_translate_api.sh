#!/usr/bin/env bash
#
# Script Name: google_translate_qutebrowser.sh
# Description: Buscar texto seleccionado (copiado automáticamente xclip) en google translatte en qutebrowser.
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# Notes:
#   Dependencies:
#       Firefox     Thorium-browser      chromium       xdotool
#


#
# API
#

# Idioma destino (cámbialo si quieres)
TARGET_LANG="es"

# Leer portapapeles desde CopyQ
TEXT=$(copyq read 0)

# Evitar ejecutar si está vacío
if [ -z "$TEXT" ]; then
    dunstify "Traducción" "Portapapeles vacío"
    exit 1
fi

# Traducir
TRANSLATED=$(trans -b :$TARGET_LANG "$TEXT")

# Mostrar notificación
dunstify "Traducción" "$TRANSLATED"
copyq add "$TRANSLATED"
