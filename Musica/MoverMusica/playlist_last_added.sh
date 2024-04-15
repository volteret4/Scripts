#!/usr/bin/env bash
#
# Script Name: playlist_last_added.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#
#



# Ruta donde se encuentran los archivos de música
ruta="${HOME}/Musica/Arch"

# Lista todos los archivos de la ruta y los ordena por fecha de creación
archivos=$(find "${ruta}" -type f -ctime -7 | sort)

# Variables para almacenar la información de los álbumes y canciones
album_actual=""
canciones_actual=""

# Iteramos por cada archivo de música y creamos la lista de reproducción
for archivo in ${archivos}
do
  # Obtenemos el nombre del álbum y la canción del archivo
  album=$(basename "$(dirname "${archivo}")")
  cancion=$(basename "${archivo}")
  
  # Si es el primer archivo o cambiamos de álbum, añadimos el álbum a la lista
  if [ "$album" != "${album_actual}" ]
  then
    # Si ya habíamos añadido canciones a la lista, añadimos el álbum completo
    if [ -n "${canciones_actual}" ]
    then
      echo "# Álbum: ${album_actual}" >> playlist.m3u
      echo "${canciones_actual}" >> playlist.m3u
    fi
    
    # Inicializamos las variables para el nuevo álbum
    album_actual="${album}"
    canciones_actual=""
  fi
  
  # Añadimos la canción actual al álbum
  canciones_actual="${canciones_actual}\n${cancion}"
done

# Añadimos el último álbum a la lista
echo "# Álbum: ${album_actual}" >> playlist.m3u
echo "${canciones_actual}" >> playlist.m3u
