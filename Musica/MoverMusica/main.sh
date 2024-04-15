#!/usr/bin/env bash
#
# Script Name: main.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#
#



# Verificar si se proporciona la carpeta de origen y destino como argumentos
if [ "$#" -ne 2 ]; then
    echo "Uso: $0 <carpeta_origen> <carpeta_destino>"
    exit 1
fi

venv="/home/pi/pyhton_venv/spotify"
carpeta_origen="$1"
carpeta_destino="$2"

# Verificar si la carpeta_origen existe
if [ ! -d "$carpeta_origen" ]; then
    echo "La carpeta_origen no existe."
    exit 1
fi

# Copiar el contenido con sudo y reemplazar los archivos existentes
sudo cp -r -f "$carpeta_origen"/* "$carpeta_destino"

# Cambiar el propietario de los archivos a pi:pi
sudo chown -R pi:pi "$carpeta_destino"

echo "Proceso de copia de playlists completado."

python3 ${venv}/playlist_actuales_spotify.py

# Iterar sobre cada archivo en la carpeta_origen
for archivo in "$carpeta_origen"/*; do
    if [ -f "$archivo" ]; then
        # Obtener el nombre del archivo sin la ruta
        nombre_archivo=$(basename "$archivo")

        # Actualiza playlists
        python3 ${venv}/playlist_actuales_spotify.py

        # Verificar si el nombre del archivo existe en el texto de la playlist
        if ! grep -q "^$nombre_archivo -" <<< "$(cat ${venv}/playlist_actuales_id.txt)"; then
            echo "El nombre del archivo '$nombre_archivo' no es una playlist."
            python3 crear_playlist_spotify.py ${archivo}
        else
            # Copiar la segunda parte (después del guion) a la variable playlist
            playlist=$(grep "^$nombre_archivo -" <<< "$texto_formato_playlist" | cut -d' ' -f3-)

            # Imprimir el resultado
            echo "Nombre del archivo: $nombre_archivo"
            echo "Playlist: $playlist"
            
            # Sincronizar playlist
            echo "Procesando archivo: $archivo"
            python3 sinc_spotify.py ${archivo}
        fi
    else
        echo "El nombre del archivo '$archivo' no es una playlist."
    fi
done