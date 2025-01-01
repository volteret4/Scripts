#!/usr/bin/env bash
#
# Script Name: google.sh 
# Description: Buscar texto seleccionado (copiado automáticamente xclip) en google.com
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
url="https://www.google.com/search?q=${busqueda}"

app="$(bash "${HOME}"/Scripts/snippets/if_firefox_active.sh)"  # > $resultado

if [[ "${app}" =~ "strawberry|DeaDBeef" ]]
    then
        bash $HOME/Scripts/utilities/open_search_links/music_player/google_metadata.sh
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

