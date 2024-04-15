#!/usr/bin/env bash
#
# Script Name: rym.sh 
# Description: Buscar texto seleccionado (copiado automáticamente xclip) en rateyourmusic.com
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

app_actual=$(xdotool getactivewindow getwindowname)
thorium="Thorium$"
chromium="Chromium"
firefox="Mozilla Firefox"
url="https://rateyourmusic.com/search?searchterm=${busqueda}"

if [[ ${app_actual} =~ ${thorium} ]]
    then
        thorium-browser "${url}" &
    elif [[ ${app_actual} =~ ${firefox} ]]; then
        firefox "${url}" &
    elif [[ ${app_actual} =~ ${chromium} ]]; then
        chromium "${url}" &
    else
        echo "${busqueda}"
        qutebrowser --target window "${url}"
fi