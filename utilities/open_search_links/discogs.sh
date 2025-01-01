#!/usr/bin/env bash
#
# Script Name: discogs.sh 
# Description: Buscar texto seleccionado (copiado automáticamente xclip) en discogs.com
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#   Dependencies:
#       Firefox     Thorium-browser      chromium       xdotool
#
busqueda="$(xclip -o)"
busqueda="${busqueda//&/and/}"

url="https://www.discogs.com/search/?q=${busqueda}"

app=$(xdotool getactivewindow getwindowname)


if [[ "${app}" =~ 'strawberry' ]]
    then
        bash $HOME/Scripts/utilities/open_search_links/music_player/discogs_metadata.sh
    elif [[ ${app} =~ 'Thorium' ]]; then
        thorium-browser "${url}" &
    elif [[ ${app} =~ 'Firefox' ]]; then
        firefox "${url}" &
    elif [[ ${app} =~ 'Chromium' ]]; then
        chromium "${url}" &
    elif [[ ${app} =~ 'Floorp' ]]; then
        floorp "${url}" &
    else
        echo "${busqueda}"
        qutebrowser --target window "${url}" &
fi