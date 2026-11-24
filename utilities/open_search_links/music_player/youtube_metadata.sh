#!/usr/bin/env bash
#
# Script Name: youtube_metadata.sh
# Description: Buscar lo que está sonando en youtube.com
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# Notes:
#   Pide el vídeo exacto a la API en el servidor hugo (ssh); si no hay resultado abre la búsqueda.
#   Si encuentra el vídeo, la url de la búsqueda queda en el portapapeles (copyq).
#   Dependencies: - _comun.sh (playerctl, xdotool, zen-browser)
#

source "$(dirname "$(readlink -f "$0")")/_comun.sh"
obtener_metadata

busqueda="${artista} ${cancion}"
url="https://www.youtube.com/results?search_query=$(urlencode "${busqueda}")"

url_api="$(ssh -o ConnectTimeout=3 -o BatchMode=yes hugo "python3 /home/ansible/scripts/blog/vvmm/post/enlaces/youtube-1arg.py $(printf '%q' "${busqueda}")" 2>/dev/null)"
if [[ -n "$url_api" ]]; then
    copyq add "${url}" > /dev/null 2>&1
    url="${url_api}"
fi

abrir_url "${url}"
