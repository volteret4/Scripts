#!/usr/bin/env bash
#
# Script Name: escuchar.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#
#


# Diálogo para elegir qué género escuchar
genero=$(zenity --info --title "Elige género:"\
        --text "¿Qué te apetece escuchar?"\
        --extra-button "Ambient"\
        --extra-button "Deep"\
        --extra-button "Keet"\
        --extra-button "Jazz"\
        --extra-button "Mix"\
        --extra-button "Funk & Soul"\
        --extra-button "Disco"\
        --extra-button "Awakenings"\
        --ok-label "Recien cosechado"\
        )

# Extraer archivo historial de copyq

copyq eval -- "tab('Escuchado'); for(i=size(); i>0; --i) print(str(read(i-1)) + '\n');" >> /mnt/A26A-AAE7/FTP/Markor/TODO/escuchado.m3u
awk '!seen[$0]++' /mnt/A26A-AAE7/FTP/Markor/TODO/escuchado.m3u


# Elegir entre música recopilada y catalogada por género, o la recien cosechada.
if [ -z "${genero}" ]
        then
                fecha_cosecha=$(date | awk '{print $2 $3}')
                copyq eval -- "tab('URLs'); for(i=size(); i>0; --i) print(str(read(i-1)) + '\n');" > /mnt/A26A-AAE7/FTP/Markor/TODO/cosecha_"${fecha_cosecha}".m3u
                genero=cosecha_${fecha_cosecha}
                grep -vxFf /mnt/A26A-AAE7/FTP/Markor/TODO/escuchado.m3u /mnt/A26A-AAE7/FTP/Markor/TODO/"${genero}".m3u > test1.tmp && mv test1.tmp /mnt/A26A-AAE7/FTP/Markor/TODO/"${genero}".m3u
                "${HOME}"/Scripts/mpv/vlc_playlist_file.sh /mnt/A26A-AAE7/FTP/Markor/TODO/"${genero}".m3u
        else
                cat /mnt/A26A-AAE7/FTP/Markor/TODO/todo.txt | grep -i "${genero}" "${1}" | awk '{print $2}' | grep "http" "${1}" > /mnt/A26A-AAE7/FTP/Markor/TODO/"${genero}".m3u
                "${HOME}"/Scripts/mpv/vlc_playlist_file.sh /mnt/A26A-AAE7/FTP/Markor/TODO/"${genero}".m3u
fi

# Test
echo "${genero}"