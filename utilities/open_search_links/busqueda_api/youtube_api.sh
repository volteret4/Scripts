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

limpio2="$(bash $HOME/Scripts/utilities/aliases/limpia_var.sh "$busqueda")"
echo "limp: $limpio2"

limpio="$(echo $limpio2 | sed 's/ /-/g')"
echo "limpio: $limpio"
notify-send -i "/usr/share/icons/Paper/16x16/status/xfce-battery-critical.png" -t 3000 "${limpio}"

comando="python3 /home/ansible/scripts/blog/vvmm/post/enlaces/youtube-1arg.py "${limpio}""
echo "com: $comando"

url="$(ssh hugo "$comando")"
echo "url $url"

if [[ -z $url ]]; then
    bash $HOME/Scripts/utilities/open_search_links/youtube_search_thorium.sh
else
    thorium-browser "$url" &
fi