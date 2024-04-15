#!/usr/bin/env bash
#
# Script Name: orpheus.sh 
# Description: Buscar texto seleccionado (copiado automáticamente xclip) en orpheus.network.
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:    Need to be logged at orphus.network to work.
#   Dependencies:
#       Firefox     Thorium-browser      chromium       xdotool
#

busqueda="$(xclip -o)"
busqueda="$(echo "${busqueda}" | sed 's/&/and/g' | sed 's/;\|:\|,\|\.\|\[\|\]\|{\|}\|-\|_\|(\|)/\ /g' )"
if [ "$(echo "$busqueda" | wc -l)" -eq 2 ]; then
	busqueda="$(echo "$busqueda" | sed '2s/^by//; s/\n/ /g')"
fi
url="https://orpheus.network/torrents.php?searchstr=${busqueda}"

app_actual=$(xdotool getactivewindow getwindowname)
thorium="Thorium$"
chromium="Chromium"
firefox="Mozilla Firefox"

if [[ ${app_actual} =~ ${thorium} ]]
    then
        thorium-browser "${url}" &
    elif [[ ${app_actual} =~ ${firefox} ]]; then
        firefox "${url}" &
    elif [[ ${app_actual} =~ ${chromium} ]]; then
        chromium "${url}" &
    else
        echo "${busqueda}"
        qutebrowser --target window "${url}" &
fi
