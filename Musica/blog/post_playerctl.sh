#!/usr/bin/env bash
#
# Script Name: mover_mix_playerctl.sh 
# Description: Mover canción sonando actualmente a subcarpeta de la ruta establecida en Mix
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#     Dependencies: deadbeef | strawberry , playerctl, ssh
#

# Obterner tags de la canción en reproducción.
deadbeef="$(deadbeef --nowplaying-tf "%artist%")"

if [ -z "$deadbeef" ]
    then
            
        cancion=$(playerctl -p strawberry metadata title) # obtener titulo de la canción
    else
        album_artist="$(deadbeef --nowplaying-tf "%album artist%")"
        if [[ -z $album_artist ]]
            then
                artista="$(deadbeef --nowplaying-tf "%artist%" | sed 's/ /-/g')"
                album="$(deadbeef --nowplaying-tf "%album%" | sed 's/ /-/g')"
                genre="$(deadbeef --nowplaying-tf "%genre%" | sed 's/ /-/g')"
            else
                artista="$(deadbeef --nowplaying-tf "%album artist%" | sed 's/ /-/g')"
                album="$(deadbeef --nowplaying-tf "%album%" | sed 's/ /-/g')"
                genre="$(deadbeef --nowplaying-tf "%genre%" | sed 's/ /-/g')"
        fi
fi

# Añade a mano los tags para el post si %genre% está vacio.
genre="$(deadbeef --nowplaying-tf "%genre%")"
if [[ -z $genre ]]
    then
        genre="$(zenity --entry --text "TAGS >> $busqueda")"
fi


# Obtén el hash de la clave
ansible="${HOME}/.ssh/ansible"
clave_hash=$(ssh-keygen -lf ${ansible} | awk '{print $2}')

# Comprueba si la clave ya está añadida
if ! ssh-add -l | grep -q "$clave_hash"; then
    # Si no está añadida, añádela
    ssh-add "${ansible}"
fi

# Conecta a hugo y lanza el script para postear el album que está sonando.

ssh hugo "bash /home/ansible/scripts/get-links.sh "${artista}" "${album}" "${genre}""