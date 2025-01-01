#!/usr/bin/env bash
#
# Script Name: busca_x_youtube.sh 
# Description: Buscar texto seleccionado (copiado automáticamente xclip) en youtube.com
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#   Dependencies:
#       Firefox     Thorium-browser      chromium       xdotool
#

busq=$(zenity --entry --title "Qué vas a buscar en YouTube")

app="$(bash "${HOME}"/Scripts/snippets/if_firefox_active.sh)"  # > $resultado



url="https://www.youtube.com/results?search_query=${busq}"

if [[ ${app} =~ 'Thorium' ]]
    then
        thorium-browser "${url}" &
    elif [[ ${app} =~ 'Firefox' ]]; then
        firefox "${url}" &
    elif [[ ${app} =~ 'Chromium' ]]; then
        chromium "${url}" &
    elif [[ ${app} =~ 'Floorp' ]]; then
        floorp "${url}" &
    else
        echo "${busqueda}"
        qutebrowser "https://www.youtube.com/results?search_query=${busq}" &
fi
