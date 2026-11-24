#!/usr/bin/env bash
#
# Script Name: spotify_metadata.sh
# Description: Buscar lo que está sonando en open.spotify.com
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# Notes:
#   Dependencies: - _comun.sh (playerctl, xdotool, zen-browser)
#

source "$(dirname "$(readlink -f "$0")")/_comun.sh"
obtener_metadata

q="$(urlencode "${artista} ${album}" | sed 's/+/%20/g')"
abrir_url "https://open.spotify.com/search/${q}"
