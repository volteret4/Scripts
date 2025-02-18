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




#zen-browser " https://www.wordpress.com &

busqueda=$(deadbeef --nowplaying-tf "%artist%-%album%")
copyq add "${busqueda}"


#zen-browser https://www.google.com/search?tbm=isch&q="${busqueda}" & #busqueda de portada
zen-browser https://www.discogs.com/search/?q="${busqueda}" &
zen-browser https://rateyourmusic.com/search?searchterm="${busqueda}" &
zen-browser https://www.last.fm/search?q="${busqueda}"
zen-browser https://en.wikipedia.org/w/index.php?search="${busqueda}"
zen-browser https://bandcamp.com/search?q="${busqueda}" &



sello="${busqueda} label"

zen-browser https://www.google.com/search?q="${sello}" &



ra="site:ra.co ${busqueda}"

zen-browser https://www.google.com/search?q="${ra}" &






bbtt="${busqueda} banbantonton"

zen-browser https://www.google.com/search?q="${bbtt}" &