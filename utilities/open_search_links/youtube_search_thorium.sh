#!/usr/bin/env bash
#
# Script Name: yt_playlist_api.sh
# Description: Obtener enlace de youtube para el album pasado como argumento y abrirlo en thorium browser
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# TODO: 
# Notes:
#   Dependencies: xclip
#

busqueda="$(xclip -o)"
echo "busq: $busqueda"

limpio="$(bash $HOME/Scripts/utilities/aliases/limpia_var.sh "$busqueda")"
echo "limp: $limpio"

url="https://www.youtube.com/results?search_query=${limpio}"

notify-send -u critical -i "/usr/share/icons/Paper/16x16/status/xfce-battery-critical.png" -t 3000 "${limpio}"

thorium-browser "$url" &