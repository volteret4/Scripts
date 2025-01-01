#!/usr/bin/env bash
#
# Script Name: node-red.sh 
# Description: start node-red and open url. 
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:    Sin uso actual
#   Dependencies:
#       Firefox     Thorium-browser  Chromium   qutebrowser xdotool node-red
#

#busqueda=$(xclip -o)
node-red

url_1="https://nodos.pollete.duckdns.org"

app="$(bash "${HOME}"/Scripts/snippets/if_firefox_active.sh)"  # > $resultado

if [[ "${app}" =~ "strawberry|DeaDBeef" ]]; then
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


