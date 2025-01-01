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

app="$(bash "${HOME}"/Scripts/snippets/if_firefox_active.sh)"  # > $resultado

# wait $! #esperar a que acabe el script hijo
# vars=$(cat $resultado)
# printf '\n%s\n' $vars
# echo $strawberry
#app=$(xdotool getactivewindow getwindowname)



url="https://bandcamp.com/search?q=${busqueda}"

if [[ "${app}" =~ "strawberry|DeaDBeef" ]]
    then
        bash $HOME/Scripts/utilities/open_search_links/music_player/bandcamp_metadata.sh
    elif [[ ${app} =~ 'Thorium' ]]; then
        thorium-browser "${url}" &
    elif [[ ${app} =~ 'Firefox' ]]; then
        firefox "${url}" &
    elif [[ ${app} =~ Chromium ]]; then
        chromium "${url}" &
    elif [[ ${app} =~ Floorp ]]; then
        floorp "${url}" &
    else
        echo "${busqueda}"
        qutebrowser --target window "${url}" &
fi
