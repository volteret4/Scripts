#!/usr/bin/env bash
#
# Script Name: youtube_en_mpv.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:
#
#



"${HOME}"/Scripts/tareas/if_firefox_active.sh

url="$(xclip -o)"
youtube="^https://www.youtube.com/watch*"

modificado=$(date -r "${HOME}"/Scripts/mpv/playlist | awk '{print $2 $3}')
fecha=$(date | awk '{print $2 $3}')

if [[ $modificado =~ $fecha ]]
        then
                echo "test"
                if [[ ${url} =~ $youtube ]] # Función regex
                        then
                                echo "${url} de yt"
                                notify-send -t 4000 "Añadido ${url}"
                                echo "${url}" >> "${HOME}"/Scripts/mpv/playlist
                                xclip -sel clip < /dev/null
                        else
                                notify-send -t 3000 "${url}"
                        fi
        else
                "$(date -r "${HOME}"/Scripts/mpv/playlist)" >> "${HOME}"/Scripts/mpv/playlist_bak
                cat "${HOME}/Scripts/mpv/playlist" >> "${HOME}"/Scripts/mpv/playlist_bak
                rm -rf "${HOME}/"Scripts/mpv/playlist
                touch "${HOME}/"Scripts/mpv/playlist
fi