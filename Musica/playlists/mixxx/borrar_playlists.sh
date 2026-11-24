#!/usr/bin/env bash
#
# Script Name: borrar_playlists.sh
# Description: Borra las listas de reproducción de Mixxx (las de sesiones temporales).
#              No toca Auto DJ, el historial, las listas bloqueadas ni los cajones.
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# Notes:
#   Uso: borrar_playlists.sh [-y]   (-y: sin pedir confirmación)
#   Mixxx debe estar cerrado. Guarda copia de la base de datos (las 5 últimas).
#   Dependencies: - sqlite3

DB="$HOME/.mixxx/mixxxdb.sqlite"
BACKUP_DIR="$HOME/.mixxx/backups_borrar_playlists"
# hidden=0: listas normales (1 = Auto DJ, 2 = historial); locked=0: no bloqueadas
WHERE="hidden = 0 AND locked = 0"

if pgrep -x mixxx > /dev/null; then
    echo "Mixxx está abierto: ciérralo antes de borrar las listas." >&2
    exit 1
fi

list=$(sqlite3 "$DB" "SELECT name || '  (' || (SELECT count(*) FROM PlaylistTracks WHERE playlist_id = p.id) || ')' FROM Playlists p WHERE $WHERE ORDER BY position")
if [ -z "$list" ]; then
    echo "No hay listas de reproducción que borrar."
    exit 0
fi

echo "$list"
count=$(echo "$list" | wc -l)
if [ "$1" != "-y" ]; then
    read -rp "¿Borrar estas $count listas? [s/N] " answer
    [[ "$answer" == [sS]* ]] || { echo "Cancelado."; exit 0; }
fi

mkdir -p "$BACKUP_DIR"
sqlite3 "$DB" ".backup '$BACKUP_DIR/mixxxdb.$(date +%Y%m%d%H%M%S).sqlite'" || exit 1
ls -1t "$BACKUP_DIR"/mixxxdb.*.sqlite | tail -n +6 | xargs -r rm --

sqlite3 "$DB" "BEGIN; DELETE FROM PlaylistTracks WHERE playlist_id IN (SELECT id FROM Playlists WHERE $WHERE); DELETE FROM Playlists WHERE $WHERE; COMMIT;" && echo "Borradas $count listas. Copia en $BACKUP_DIR"
