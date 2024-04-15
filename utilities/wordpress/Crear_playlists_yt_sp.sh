#!/usr/bin/env bash
#
# Script Name: Crear_playlists_yt_sp.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#
#

carpeta=$(dirname $(readlink "$0"))
source "${carpeta}/.env"

# Crea un formulario Zenity con diez campos de entrada
form=$(zenity --forms --title="Formulario de ejemplo" \
    --text="Introduce artista_cancion" \
    --add-entry="nombre_playlist" \
    --add-entry="descripcion_playlist" \
    --add-entry="song1" \
    --add-entry="song2" \
    --add-entry="song3" \
    --add-entry="song4" \
    --add-entry="song5" \
    --add-entry="song6" \
    --add-entry="song7" \
    --add-entry="song8" \
    --add-entry="song9" \
    --add-entry="song0")

# Guarda los valores de los campos de entrada en variables
title=$(echo $form | awk -F '|' '{print $1}')
descripcion=$(echo $form | awk -F '|' '{print $2}')
cancion1=$(echo $form | awk -F '|' '{print $3}')
cancion2=$(echo $form | awk -F '|' '{print $4}')
cancion3=$(echo $form | awk -F '|' '{print $5}')
cancion4=$(echo $form | awk -F '|' '{print $6}')
cancion5=$(echo $form | awk -F '|' '{print $7}')
cancion6=$(echo $form | awk -F '|' '{print $8}')
cancion7=$(echo $form | awk -F '|' '{print $9}')
cancion8=$(echo $form | awk -F '|' '{print $10}')
cancion9=$(echo $form | awk -F '|' '{print $11}')
cancion10=$(echo $form | awk -F '|' '{print $12}')

# Crea una lista de canciones y agrega solo las canciones no vacías
canciones=()
if [[ ! -z "$cancion1" ]]; then
    canciones+=("$cancion1")
fi
if [[ ! -z "$cancion2" ]]; then
    canciones+=("$cancion2")
fi
if [[ ! -z "$cancion3" ]]; then
    canciones+=("$cancion3")
fi
if [[ ! -z "$cancion4" ]]; then
    canciones+=("$cancion4")
fi
if [[ ! -z "$cancion5" ]]; then
    canciones+=("$cancion5")
fi
if [[ ! -z "$cancion6" ]]; then
    canciones+=("$cancion6")
fi
if [[ ! -z "$cancion7" ]]; then
    canciones+=("$cancion7")
fi
if [[ ! -z "$cancion8" ]]; then
    canciones+=("$cancion8")
fi
if [[ ! -z "$cancion9" ]]; then
    canciones+=("$cancion9")
fi
if [[ ! -z "$cancion10" ]]; then
    canciones+=("$cancion10")
fi

# Concatena las canciones en una sola variable con saltos de línea
canciones=""
for cancion in "${canciones[@]}"; do
    canciones="$canciones$cancion\n"
done

# Escribe las canciones en un archivo solo si hay canciones en la lista
if [[ ! -z "$canciones" ]]; then
    echo -e "$canciones" > canciones.txt
fi

cat canciones.txt

# Establece las variables de entorno para la autenticación de Spotify
export SPOTIPY_REDIRECT_URI=http://127.0.0.1:8899

source "${HOME}"/Documentos/python_envs/spotify/spotify/bin/activate

python3 "${HOME}"/Documentos/python_envs/spotify/spotify/spotify_playlist.py "$title" "$descripcion"

