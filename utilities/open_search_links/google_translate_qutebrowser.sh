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

# Leer portapapeles desde CopyQ
traduce=$(copyq read 0)

# ABRIR EN EL NAVEGADOR ACTUAL O qutebrowser

url="https://translate.google.com/?sl=auto&tl=es&text=${traduce}"
app="$(bash "${HOME}/Scripts/snippets/if_firefox_active.sh")"  # obtener app activa

if [[ ${app} =~ 'zen' ]]; then
    zen-browser "${url}" &
elif [[ ${app} =~ 'Thorium' ]]; then
    thorium-browser "${url}" &
elif [[ ${app} =~ 'Firefox' ]]; then
    firefox "${url}" &
elif [[ ${app} =~ 'Chromium' ]]; then
    chromium "${url}" &
elif [[ ${app} =~ "Floorp" ]]; then
    floorp "${url}" &
else
    echo "${url}"
    qutebrowser --target window "${url}" &
fi
