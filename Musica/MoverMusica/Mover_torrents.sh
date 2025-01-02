#!/bin/bash

# Directorio a vigilar
WATCH_DIR="/home/huan/Descargas"

LOG_FILE="/home/huan/Scripts/.content/logs/mover_torrents.log"
SSH_KEY="/home/huan/.ssh/dietpi"

TRACKER_DIR="dietpi@192.168.1.202:/mnt/5TB/torrents_backup/watch_torrents"
TRACKER_DIR_OLIMPO="dietpi@192.168.1.202:/mnt/dietpi_userdata/NFS/Pelis/watchfolder"

# Función para procesar archivos torrent
process_torrent() {
    local torrent_file="$1"
    
    # Leer tracker del archivo .torrent usando awk y grep
    #tracker=$(grep -a 'announce' "$torrent_file" | awk -F ' ' '{print $1}' | tr -d '\r')
    tracker=$(strings "$torrent_file" | grep -o 'http[s]*://[^"]*' | grep 'announce')

    # Clasificar por tracker
    if [[ "$tracker" =~ "opsfet" ]]; then
        dest_dir="$TRACKER_DIR"
        notify-send "Torrent Orpheus" -t 5000 "$torrent_file"
    elif [[ "$tracker" =~ "rutracker" ]]; then
        dest_dir="$TRACKER_DIR"
        notify-send "Torrent rutracker" -t 5000 "$torrent_file"
    elif [[ "$tracker" =~ "olimpo" ]]; then
        dest_dir="$TRACKER_DIR_OLIMPO"
        notify-send "Torrent HD-Olimpo" -t 5000 "$torrent_file"
    else
        notify-send "error al mover el torrent" -u critical -t 5000 "no parece detectar el tracker"
    fi

    # Crear directorio si no existe
    #mkdir -p "$dest_dir"

    # Mover archivo
    rsync -avzh -e "ssh -i $SSH_KEY" "$torrent_file" "$dest_dir/"
    echo "$(date): Movido $torrent_file a $dest_dir" >> "$LOG_FILE"
}

# Vigilar el directorio en tiempo real
inotifywait -m "$WATCH_DIR" -e create --format '%w%f' | while read new_file
do
    # Procesar solo archivos .torrent
    if [[ "$new_file" == *.torrent ]]; then
        sleep 2
        process_torrent "$new_file"
    fi
done
