#!/usr/bin/env bash
#
# Script Name: youtube.sh 
# Description: Buscar texto seleccionado (copiado automáticamente xclip) en youtube.com
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#   Dependencies:
#       Firefox     Thorium-browser      chromium       xdotool
#
busqueda="$(xclip -o)"
busqueda=${busqueda//&/and/}

url="https://www.youtube.com/results?search_query=${busqueda}"

comando="python3 /home/ansible/scripts/blog/vvmm/post/enlaces/youtube-1arg.py "${busqueda}""
echo "com: $comando"
url_api="$(ssh hugo "$comando")"
echo "url $url_api"

if [[ -z $url_api ]]; then
    echo "no se encontró nada en la api"
else
    copyq add ${url}
    url="${url_api}"
    echo "cambiando a url de la api. guardada la anterior en el portapapeles"
fi


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