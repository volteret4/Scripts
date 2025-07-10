#!/usr/bin/env bash
#
# Script Name: buscar_album_desde_firefox.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:
#
#


var=$(xwininfo -id $(xdotool getactivewindow) | head -n2 | sed 's/^[^"]*"\([^"]*\)"/\1/') # Detectar ventana activa
regex="Firefox$" # Busqueda regex


if [[ $var =~ $regex ]] # Función regex
        then
                wid=$(xdotool search --name "Mozilla Firefox")  # busca la ventana (pid) "Mozilla Firefox"
                xdotool windowfocus $wid                        # focus en $wid
                sleep 0.2                                       # no funciona sin el retraso
                xdotool key "ctrl+l"                            # simula la pulsación de las teclas:
                xdotool key "ctrl+c"                            # ...
                #zenity --info \                                # test con diálogo de texto
                #    --text="pollo"
        else
                xdotool key "ctrl + c"                          # simula "ctrl + c"
                #zenity --info \
                #    --text="ERROR"
fi

chromium --profile-directory="Profile 4" https://www.wordpress.com &

busqueda=$(xclip -o)

chromium --profile-directory="Profile 4" https://www.google.com/search?tbm=isch&q="$busqueda" & #busqueda de portada
chromium --profile-directory="Profile 4" https://www.discogs.com/search/?q="$busqueda" &
chromium --profile-directory="Profile 4" https://rateyourmusic.com/search?searchterm="$busqueda" &
chromium --profile-directory="Profile 4" https://www.last.fm/search?q="$busqueda"
chromium --profile-directory="Profile 4" https://en.wikipedia.org/w/index.php?search="$busqueda"
chromium --profile-directory="Profile 4" https://bandcamp.com/search?q="$busqueda" &



sello="$busqueda label"

chromium --profile-directory="Profile 4" https://www.google.com/search?q="$sello" &



ra="site:ra.co $busqueda"

chromium --profile-directory="Profile 4"  https://www.google.com/search?q="$ra" &



bbtt="$busqueda banbantonton"

chromium --profile-directory="Profile 4"  https://www.google.com/search?q="$bbtt" &