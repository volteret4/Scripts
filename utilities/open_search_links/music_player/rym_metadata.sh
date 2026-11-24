#!/usr/bin/env bash
#
# Script Name: rym_metadata.sh
# Description: Buscar lo que está sonando en rateyourmusic.com
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# Notes:
#   Dependencies: - _comun.sh (playerctl, xdotool, zen-browser)
#

source "$(dirname "$(readlink -f "$0")")/_comun.sh"
obtener_metadata

q="$(urlencode "${artista} - ${album}")"
abrir_url "https://rateyourmusic.com/search?searchterm=${q}&searchtype=l"
