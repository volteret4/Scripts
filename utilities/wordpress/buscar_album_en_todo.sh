#!/usr/bin/env bash
#
# Script Name: buscar_album_en_todo.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#
#




chromium --profile-directory="Profile 4" https://www.wordpress.com &

artist=$(playerctl -p strawberry metadata xesam:albumArtist)
album=$(playerctl -p strawberry metadata album)
busqueda="${artist} ${album}"

sleep 0.2

chromium --profile-directory="Profile 4" https://www.google.com/search?tbm=isch&q="${busqueda}" & #busqueda de portada
chromium --profile-directory="Profile 4" https://www.discogs.com/search/?q="${busqueda}" &
chromium --profile-directory="Profile 4" https://rateyourmusic.com/search?searchterm="${busqueda}" &
chromium --profile-directory="Profile 4" https://www.last.fm/search?q="${busqueda}"
chromium --profile-directory="Profile 4" https://en.wikipedia.org/w/index.php?search="${busqueda}"
chromium --profile-directory="Profile 4" https://bandcamp.com/search?q="${busqueda}" &



sello="${busqueda} label"

chromium --profile-directory="Profile 4" https://www.google.com/search?q="${sello}" &



ra="site:ra.co ${busqueda}"

chromium --profile-directory="Profile 4"  https://www.google.com/search?q="${ra}" &



bbtt="${busqueda} banbantonton"

chromium --profile-directory="Profile 4"  https://www.google.com/search?q="${bbtt}" &