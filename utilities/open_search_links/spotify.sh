#!/usr/bin/env bash
#
# Script Name: spotify.sh 
# Description: Buscar texto seleccionado (copiado automáticamente xclip) en spotify web.
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#   Dependencies:
#       Firefox     Thorium-browser      chromium       xdotool
#
#

busqueda="$(xclip -o)"
busqueda="$(echo "${busqueda}" | sed 's/&/and/g' | sed 's/;\|:\|,\|\.\|\[\|\]\|{\|}\|-\|_\|(\|)/\ /g' )"
if [ "$(echo "$busqueda" | wc -l)" -eq 2 ]; then
	busqueda="$(echo "$busqueda" | sed '2s/^by//; s/\n/ /g')"
fi
url="https://open.spotify.com/search/${busqueda}"

app="$(bash "${HOME}"/Scripts/snippets/if_firefox_active.sh)"  # > $resultado

if [[ "${app}" =~ "strawberry|DeaDBeef" ]]; then
        bash $HOME/Scripts/utilities/open_search_links/music_player/spotify_metadata.sh
    elif [[ ${app} =~ 'Thorium' ]]; then
        thorium-browser "${url}" &
    elif [[ ${app} =~ 'Firefox' ]]; then
        firefox "${url}" &
    elif [[ ${app} =~ 'Chromium' ]]; then
        chromium "${url}" &
    elif [[ ${app} =~ 'floorp' ]]; then
        spotify "${url}" &
    else
        echo "${busqueda}"
        qutebrowser --target window "${url}" &
fi
