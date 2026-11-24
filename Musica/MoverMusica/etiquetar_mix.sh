#!/usr/bin/env bash
#
# Script Name: etiquetar_mix.sh
# Description: Pasa el etiquetador (BPM si falta y ReplayGain) por canciones de Mix en este PC, antes
#              de que syncthing las lleve a pepecono, que solo recibe y no podría devolver los tags.
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# Notes:
#   - Usa la imagen repeat-one-etiquetador traída de pepecono, sin copia del código. Para actualizarla:
#     ssh pepecono docker save repeat-one-etiquetador:latest | docker load
#   - ESCRIBIR=false solo genera informe, con Mix en solo lectura. Se cambia al validar la primera tanda.
#   - El etiquetador conserva la fecha del archivo y a veces también el tamaño; syncthing no vería
#     el cambio, así que tras escribir se adelanta la fecha 1 s.
#   - Sin red: esta orden no consulta nada de internet.
#
# Uso: etiquetar_mix.sh RUTA...

ESCRIBIR=false

IMAGE=repeat-one-etiquetador:latest
MIX_ROOT=${MIX_ROOT:-/mnt/windows/Mix}
DATA=${ETIQUETADOR_DATA:-$HOME/.local/state/etiquetador}

[ "$#" -gt 0 ] || { echo "Uso: $0 RUTA..." >&2; exit 2; }
mkdir -p "$DATA" || exit 1

mount_mode=ro
write_flag=()
if [ "${ESCRIBIR_FORZADO:-$ESCRIBIR}" = true ]; then
    mount_mode=rw
    write_flag=(--write)
fi

docker run --rm --network none --user "$(id -u):$(id -g)" \
    -e LOOSE_ROOTS="$MIX_ROOT" -e TEMP_ROOTS= -e INBOX_ROOTS= \
    -v "$DATA:/data" -v "$MIX_ROOT:$MIX_ROOT:$mount_mode" \
    "$IMAGE" mix "${write_flag[@]}" "$@"
status=$?

if [ "$mount_mode" = rw ]; then
    for path in "$@"; do
        [ -f "$path" ] && touch -r "$path" -d '+1 second' "$path"
    done
fi

if [ "$status" -ne 0 ]; then
    notify-send -u critical -- "Etiquetador" "Ha fallado alguna canción (código $status). Registro en $DATA/etiquetar.log" 2>/dev/null
fi
exit "$status"
