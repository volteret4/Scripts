#!/usr/bin/env bash
#
# Script Name: orpheus_metadata.sh
# Description: Buscar lo que está sonando en orpheus.network
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# Notes:
#   Hay que tener la sesión iniciada en orpheus.network.
#   Dependencies: - _comun.sh (playerctl, xdotool, zen-browser)
#

source "$(dirname "$(readlink -f "$0")")/_comun.sh"
obtener_metadata

q="$(urlencode "${artista} - ${album}")"
abrir_url "https://orpheus.network/torrents.php?searchstr=${q}"
