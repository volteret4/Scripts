#!/usr/bin/env bash
#
# Script Name: nicotine_metadata.sh
# Description: Buscar lo que está sonando en Nicotine+ (Soulseek)
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# Notes:
#   Necesita el plugin ~/.local/share/nicotine/plugins/busqueda_externa activado en Nicotine+.
#   Busca artista + canción (no el álbum) para encontrar remezclas sueltas.
#   Dependencies: - _comun.sh (playerctl)      - nicotine+
#

source "$(dirname "$(readlink -f "$0")")/_comun.sh"
obtener_metadata

buscar_nicotine "${artista} ${cancion}"
