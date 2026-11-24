#!/usr/bin/env bash
#
# Script Name: subir_a_pepecono.sh
# Description: Copia el código de vvmm al servicio mover_mix de pepecono (repeat-one), que publica
#              los posts desde el móvil (DSub). Sin .env (pepecono tiene el suyo, con sus rutas),
#              ni caché, ni copias.
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# Notes:
#   - Ejecutar tras cambiar main.py, online_info.py o modules/.
#
# Uso: subir_a_pepecono.sh

set -euo pipefail
cd "$(dirname "$0")"
rsync -a --delete \
    --exclude '.env' --exclude '.env_*' --exclude '.content/' --exclude '.cache' --exclude '.github/' \
    --exclude '__pycache__/' --exclude '*.bak*' --exclude 'main.sh' --exclude 'main_updated.py' \
    --exclude 'subir_a_pepecono.sh' \
    ./ pepecono:contenedores/repeat-one/services/mover_mix/vvmm/
echo "vvmm copiado a pepecono"
