#!/usr/bin/env bash
#
# Script Name: google_metadata.sh
# Description: Buscar lo que está sonando en google.com
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# Notes:
#   Excluye las webs que ya tienen su propio script.
#   Dependencies: - _comun.sh (playerctl, xdotool, zen-browser)
#

source "$(dirname "$(readlink -f "$0")")/_comun.sh"
obtener_metadata

excluir="-discogs -bandcamp -rateyourmusic -youtube -juno -deezer -fnac -wikipedia -spotify -qobuz -amazon -ebay -beatport -apple -genius -boomkat -tidal"
q="$(urlencode "${artista} ${album} ${excluir}")"
abrir_url "https://www.google.com/search?q=${q}"
