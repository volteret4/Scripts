#!/usr/bin/env bash
#
# Script Name: mover_mix_playerctl.sh 
# Description: Mover canción sonando actualmente a subcarpeta de la ruta establecida en Mix
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:
#     La idea de este script es poder tener en una carpeta aparte una selección de música con otro criterio (género por ej.)
#

# Carpeta de destino en que se resultadorá la canción actual.
carpeta="$1"
# Por si quieres añadir una carpeta
if [[ $carpeta =~ otra ]]; then
    carpeta="$2"
fi
destino="/media/4f7622e9-975f-4331-b2ce-5dda87ae6a7e/syncthing/mix/${carpeta}"
mkdir "${destino}"

# Obtener metadata y path.
archivo="$(mpc -f %file% | awk 'NR==1')"
filename="$(basename "${archivo}")"
album="$(mpc -f %album% | awk 'NR==1')"
artista="$(mpc -f %album_artist% | awk 'NR==1')"
cancion="$(mpc -f %name% | awk 'NR==1')"

if [[ -z $artista ]]; then              # Por si album_artist está vacio
    artista="$(mpc -f %artist% | awk 'NR==1')"  
fi


# Errores 
if [[ -z $archivo ]]; then              # Por si album_artist está vacio
    echo "Error, no hay path" ; exit 0
fi

dup=$(find ${carpeta} -iname "${artista} ${cancion}*")  # O ya existe una copia.
if [[ -n $dup ]]; then
    echo "duplicado en ${dup}" ; exit 0
fi


# Renombrar PATH de moode a real.
file="$(echo $archivo | sed 's/USB/\/media/')"

# Copia la cancion a syncthing.
cp "${file}" "${destino}"
resultado="${destino}/$filename"

# Renombra el archivo final.
tagutil -Yp clear:comment "${resultado}"
#tagutil -Yp add:comment="${comentario}" $resultado
tagutil -Yp rename:"%artist - %title [%date - %album]" "${resultado}"