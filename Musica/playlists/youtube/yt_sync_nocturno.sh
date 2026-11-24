#!/bin/bash
# Sincroniza todas las playlists de Mix con YouTube una hora antes de que se renueve la cuota
# (cron a las 23:00 America/Los_Angeles) para gastar lo que quede del día. Avisa por Telegram.
# Mix llega por syncthing; el estado y el token de YouTube están en ~/.config/yt_sync/.
cd "$(dirname "$0")"
set -a
eval "$(sops --decrypt /home/pepe/Scripts/utilities/notificaciones/telegram/monitor_basico/.encrypted.env)"
set +a
export YT_SYNC_MIX=/mnt/NFS/moode/Mixxx
echo "=== $(date '+%F %T')" >> yt_sync.log
/home/pepe/Scripts/python_venv/bin/python yt_sync_mixxx.py --publish --no-auth --telegram >> yt_sync.log 2>&1
