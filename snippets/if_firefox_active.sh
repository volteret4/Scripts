#!/usr/bin/env bash
#
# Script Name: if_firefox_active.sh 
# Description: Herramienta usada por otros scripts para comprobar si la ventana activa es una de los navegadores activos.
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#
#



app=$(xdotool getactivewindow getwindowname)
export "${app?}"
firefox="Mozilla Firefox$"
chromium="\- Chromium$"
qutebrowser="qutebrowser$"
#export strawberry="$(xdotool getactivewindow getwindowclassname)"
sleep 0.2

if [[ ${app} =~ ${firefox} ]]
                then
                        echo "firefox"
                        wid=$(xdotool search --name "Mozilla Firefox$")
                        xdotool windowfocus "${wid}"
                        sleep 0.2
                        xdotool key ctrl+l
                        xdotool key ctrl+c
                        xdotool key Escape
        elif [[ ${app} =~ ${chromium} ]]
                then
                        echo "chromium"
                        wid=$(xdotool search --name "\- Chromium$")
                        xdotool windowfocus "${wid}"
                        sleep 0.2
                        xdotool key ctrl+l
                        xdotool key ctrl+c
                        xdotool key Escape
        elif [[ ${app} =~ ${qutebrowser} ]]
                then
                        echo "qutebrowser"
                        wid=$(xdotool search --name ${qutebrowser})
                        xdotool windowfocus "${wid}"
                        xdotool key y
                        xdotool key y
        elif [[ ${app} =~ 'strawberry' ]]
                then
                        echo "strawberry"
                        artista=$(playerctl -p strawberry  metadata xesam:albumArtist)
                        cancion=$(playerctl -p strawberry  metadata title)
                        album=$(playerctl -p strawberry  metadata album)
                        printf '\n%s\n' "${artista}" "${album}" "${cancion}"
                else
                        echo "other"
fi
"$(xclip -o)"