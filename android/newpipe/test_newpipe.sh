#!/usr/bin/env bash
#
# Script Name: test_newpipe.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO:     ALL
# Notes:    NEWPIPE
#
#




# Dirección URL del video que se va a agregar a la lista de reproducción
video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Título del video que se va a agregar a la lista de reproducción
video_title="Never Gonna Give You Up"

# Nombre de la lista de reproducción donde se va a agregar el video
playlist_name="Mi lista de reproducción"

# ID de la lista de reproducción donde se va a agregar el video (se obtiene al crear la lista en la aplicación NewPipe)
playlist_id="1"

# Dirección del archivo de la base de datos de NewPipe en el dispositivo Android
database_path="/data/data/org.schabi.newpipe/databases/newpipe.db"

# Copiar la base de datos de NewPipe del dispositivo Android al sistema operativo local
adb pull $database_path

# Abrir la base de datos de NewPipe en modo lectura/escritura
sqlite3 newpipe.db << EOF

# Añadir el video a la tabla de videos de la base de datos

INSERT INTO streaming_video_service(service_id, url, title, duration)
VALUES (1, "$video_url", "$video_title", 0);

# Obtener el ID del video que se acaba de agregar
SELECT id FROM streaming_video_service WHERE url="$video_url";

# Añadir el video a la lista de reproducción de la tabla de playlists de la base de datos
INSERT INTO playlist_remote_id(service_id, url, name, thumbnail_url, video_count, playlist_id)
VALUES (1, "$playlist_name", "$playlist_name", "", 0, "$playlist_id");

EOF


# pollo https://github.com/nikp123/SoundCloud-NewPipe-Import/blob/master/import_soundcloud.sh

stream_pos=$(sqlite3 "$filename" "SELECT max(uid) FROM streams")
playlist_pos=$(sqlite3 "$filename" "SELECT max(uid) FROM playlists")

# To insert a stream
#sqlite3 $filename "INSERT INTO streams VALUES ($stream_pos, 1, \"$stream_url\", \"$stream_title\", \"AUDIO_STREAM\", $duration_in_seconds, \"$author\", \"$thumbnail_url\")"
#sqlite3 $filename "INSERT INTO playlists VALUES ($playlist_pos, \"$playlist_title\", \"$playlist_thumbnail\")
#sqlite3 $filename "INSERT INTO playlist_stream_join VALUES ($playlist_pos, $stream_pos, $position_in_the_playlist)"

# playlist_id  stream_id  join_index










# Copiar la base de datos de NewPipe modificada al dispositivo Android
adb push newpipe.db $database_path

# Eliminar la copia local de la base de datos de NewPipe
rm newpipe.db
