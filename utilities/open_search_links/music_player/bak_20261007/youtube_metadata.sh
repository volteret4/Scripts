#!/usr/bin/env bash
#
# Script Name: google.sh 
# Description: Buscar la canción que está sonando en youtube.com
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:
#   Dependencies:
#       Firefox     Thorium-browser      chromium       xdotool
#


# Establecer Variables
deadbeef="$(deadbeef --nowplaying-tf "%artist%")"
strawberry=$(playerctl -p strawberry status)
player_active=$(playerctl -l | awk 'NR==1')
playing=$(playerctl -p "${player_active}" status)

if [[ ${strawberry} =~ 'Playing' ]]
    then
        player_active='strawberry'
    elif [[ -n ${deadbeef} ]]
        then
            artista="$(deadbeef --nowplaying-tf "%artist%")"
            cancion="$(deadbeef --nowplaying-tf "%title%")"
            album="$(deadbeef --nowplaying-tf "%album%")"
    elif [[ ${playing} =~ 'Playing' ]]
        then
            echo "player is ""${player_active}"""
        else
            player_active=$(playerctl -l | awk 'NR==2')
fi

app_actual=$(xdotool getactivewindow getwindowname)
thorium="Thorium$"
chromium="Chromium"
firefox="Mozilla Firefox"
floorp="Floorp"

# Obtener metadata del reproductor actual

# Obtener metadata del reproductor actual
if [[ -z $deadbeef ]] ; then
    artista=$(playerctl -p "${player_active}" metadata xesam:artist)
    cancion=$(playerctl -p "${player_active}" metadata xesam:title)
    album=$(playerctl -p "${player_active}" metadata xesam:album)
fi

busqueda=$(echo "${artista} ${cancion}" | sed 's/&/and/g')

url="https://www.youtube.com/results?search_query=${busqueda}"


comando="python3 /home/ansible/scripts/blog/vvmm/post/enlaces/youtube-1arg.py "${busqueda}""
echo "com: $comando"
url_api="$(ssh hugo "$comando")"
echo "url $url_api"

if [[ -z $url_api ]]; then
    echo "no se encontró nada en la api"
else
    copyq add ${url}
    url="${url_api}"
    echo "cambiando a url de la api. guardada la anterior en el portapapeles"
fi

# Abrir busqueda en wikipedia

if [[ ${app_actual} =~ ${thorium} ]]
    then
        thorium-browser "${url}" &
    elif [[ ${app_actual} =~ ${floorp} ]]; then
        floorp "${url}" &
    elif [[ ${app_actual} =~ ${firefox} ]]; then
        firefox "${url}" &
    elif [[ ${app_actual} =~ ${chromium} ]]; then
        chromium "${url}" &
    else
        echo "${busqueda}"
        qutebrowser --target window "${url}"
fi