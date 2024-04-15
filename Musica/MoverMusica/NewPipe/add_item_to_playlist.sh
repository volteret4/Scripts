#!/usr/bin/env bash
#
# Script Name: add_item_to_playlist.sh 
# Description: add video to playlist.
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO:         All. WIP
# Notes:        Necestia tener conectado un android usando adb.
#
#


##### OBTENER VARIABLES #####

# Dirección del archivo de la base de datos de NewPipe en el dispositivo Android
database_path="/data/data/org.schabi.newpipe/databases/newpipe.db"

# Copiar la base de datos de NewPipe del dispositivo Android al sistema operativo local

adb pull $database_path

database="newpipe.db"


        # Elegir playlist

playlist_title=$(zenity --info --title "Elige playlist de New Pipe"\
    text "Cual de estas playlists"\
    extra-button="# Techno"\
    extra-button="# Deep"\
    extra-button="# Awakenings"\
    extra-button="r/ketamine"\
    extra-button="# Disco"\
    extra-button="Entrevistas"\
    extra-button="Sesiones"\
    )


        # STREAMS

#bash ~/Scripts/snippets/if_firefox_active.sh
#stream_url=$(xclip -o)
stream_url="https://www.youtube.com/watch?v=rCZkp023MdY"


stream_title=$(yt-dlp --skip-download --print filename -o "%(title)s" ${stream_url})
duration_in_seconds=$(yt-dlp --skip-download --print filename -o "%(duration)s" ${stream_url})
author=$(yt-dlp --skip-download --print filename -o "%(channel)s" ${stream_url})
thumbnail_url=$(yt-dlp --skip-download --print thumbnails_table ${stream_url} | awk 'NR==2{print $4}')


        # PLAYLISTS

playlist_thumbnail="$(sqlite3 ${database} "SELECT thumbnail_url FROM playlists WHERE name='${playlist_title}';")"


        # playlist_stream_join

playlist_pos=$(sqlite3 ${database} "SELECT uid FROM playlists WHERE name='${playlist_title}';")

stream_pos_1=$(sqlite3 ${database} "SELECT uid FROM streams;")      # obtener último índice
stream_pos=$(($stream_pos_1+1))     # indexar al final

last_id_1=$(sqlite3 "{$1}" "SELECT max(join_index) FROM playlist_stream_join WHERE playlist_id=${playlist_id}")     # obtener último índice
last_id=$(("$last_id_1"+1))         # indexar al final


# Elefir tipo de stream segun url a añadir

youtube="^https://(youtube.com|youtu.be)"

if [[ ${stream_url} =~ ${youtube} ]]
    then
        stream_type="VIDEO_STREAM"
        stream_service="0"
    else
        stream_type="AUDIO_STREAM"
        stream_service="4"
fi


# To insert a stream
sqlite3 $database "INSERT INTO streams VALUES ($stream_pos, $stream_service, \"$stream_url\", \"$stream_title\", \"$stream_type\", $duration_in_seconds, \"$author\", \"$thumbnail_url\")"
sqlite3 $database "INSERT INTO playlists VALUES ($playlist_pos, \"$playlist_title\", \"$playlist_thumbnail\")"
sqlite3 $database "INSERT INTO playlist_stream_join VALUES ($playlist_pos, $stream_pos, $position_in_the_playlist)"


# Copiar la base de datos de NewPipe modificada al dispositivo Android
# adb push newpipe.db $database_path


# Eliminar la copia local de la base de datos de NewPipe
#rm newpipe.db