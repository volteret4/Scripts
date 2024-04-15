#!/usr/bin/env bash
#
# Script Name: bandcamp.sh 
# Description: Buscar texto seleccionado (copiado automáticamente xclip) en bandcamp.com
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#   Dependencies:
#       Firefox     Thorium-browser  Chromium   xdotool
#

busqueda="$(xclip -o)"
# resultado=$(mktemp)
busqueda=$(echo "${busqueda}" | sed 's/&/and/g' | sed 's/;\|:\|,\|\.\|\[\|\]\|{\|}\|-\|_\|(\|)/\ /g' )

source "${HOME}"/Scripts/snippets/if_firefox_active.sh  # > $resultado

# wait $! #esperar a que acabe el script hijo
# vars=$(cat $resultado)
# printf '\n%s\n' $vars
# echo $strawberry
app_actual=$(xdotool getactivewindow getwindowname)
thorium="Thorium$"
chromium="Chromium"
firefox="Mozilla Firefox"

url="https://bandcamp.com/search?q=${busqueda}"

if [[ "${app}" =~ 'strawberry' ]]
    then
        echo "${cancion}"
        busqueda=$(echo "${artista} ${album}" | sed 's/&/and/g')
        qutebrowser "${url}" &
    elif [[ ${app_actual} =~ ${thorium} ]]; then
        thorium-browser "${url}" &
    elif [[ ${app_actual} =~ ${firefox} ]]; then
        firefox "${url}" &
    elif [[ ${app_actual} =~ ${chromium} ]]; then
        chromium "${url}" &
    else
        echo "${busqueda}"
        qutebrowser --target window "${url}" &
fi
