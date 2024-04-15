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

app_actual=$(xdotool getactivewindow getwindowname)
thorium="Thorium$"
chromium="Chromium"
firefox="Mozilla Firefox"

url="https://www.youtube.com/results?search_query=${busq}"

if [[ ${app_actual} =~ ${thorium} ]]
    then
        thorium-browser "${url}" &
    elif [[ ${app_actual} =~ ${firefox} ]]; then
        firefox "${url}" &
    elif [[ ${app_actual} =~ ${chromium} ]]; then
        chromium "${url}" &
    else
        echo "${busqueda}"
        thorium-browser "https://www.youtube.com/results?search_query=${busq}" &
fi
