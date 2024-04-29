#!/usr/bin/env bash
#
# Script Name: google.sh 
# Description: Buscar la canción que está sonando en google.com
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#   Dependencies:
#       Firefox     Thorium-browser      chromium       xdotool
#

# Establecer Variables
deadbeef="$(deadbeef --nowplaying-tf "%artist%")"
strawberry="$(playerctl -p strawberry status)"
player_active="$(playerctl -l | awk 'NR==1')"
playing="$(playerctl -p "${player_active}" status)"


# Buscar reproductor activo
if [[ ${strawberry} =~ 'Playing' ]]
    then
        player_active='strawberry'
    elif [[ -n ${deadbeef} ]]
        then
            player_active='deadbeef'
            artista="$(deadbeef --nowplaying-tf "%artist%")"
            cancion="$(deadbeef --nowplaying-tf "%title%")"
            album="$(deadbeef --nowplaying-tf "%album%")"
    elif [[ ${playing} =~ 'Playing' ]]
        then
            echo "player is ""${player_active}"""
        else
            player_active=$(playerctl -l | awk 'NR==2')
fi


# Obtener metadata del reproductor actual
if [[ $player_active != 'deadbeef' ]]
    then
        artista="$(playerctl -p "${player_active}" metadata xesam:artist)"
        cancion="$(playerctl -p "${player_active}" metadata xesam:title)"
        album="$(playerctl -p "${player_active}" metadata xesam:album)"
fi


# Unir parámetros de búsqueda
busqueda=$(echo "${artista} ${album}" | sed 's/&/and/g')
delimitadores=" -discogs -bandcamp -rateyourmusic -youtube -juno -deezer -fnac -wikipedia -spotify -qobuz -amazon -ebay -beatport -apple -genius -boomkat -tidal"
url="https://www.google.com/search?q=${busqueda}${delimitadores}"

# Variables para poder ver si existe un navegador activo.
app_actual=$(xdotool getactivewindow getwindowname)
thorium="Thorium$"
chromium="Chromium"
firefox="Mozilla Firefox"


# Abrir busqueda en Bandcamp, ya sea en el navegador activo si lo hubiera, o en Qutebrowser.
if [[ ${app_actual} =~ ${thorium} ]]
    then
        thorium-browser "${url}" &
    elif [[ ${app_actual} =~ ${firefox} ]]; then
        firefox "${url}" &
    elif [[ ${app_actual} =~ ${chromium} ]]; then
        chromium "${url}" &
    else
        echo "${busqueda}"
        qutebrowser --target window "${url}"
fi