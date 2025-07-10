#!/usr/bin/env python
#
# Script Name: lastfm.sh
# Description: Obtener link de lastfm del album poasado como argumento.
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:

# Notes:
#   Dependencies:   - python3 con los paquetes: requests
#                   - api accounts for: lastfm
#                   - .env file


# Configuración
# carpeta=$(dirname $(readlink "$0"))
# source "${carpeta}/.env"source $HOME/Scripts/Scriptsblog/vvmm/post/enlaces/.env

ARTIST="${1}"
ALBUM="${2}"
LASTFM_APIKEY="$(cat $HOME/Scripts/Musica/blog/vvmm/.env_lastfm)"

# Verifica que los parámetros no estén vacíos
if [ -z "$ARTIST" ] || [ -z "$ALBUM" ]; then
    echo "Por favor, proporciona un nombre de artista y álbum."
    exit 1
elif [ -z "LASTFM_APIKEY" ]; then
    echo "Error con la api de Lastfm"
    exit 1
fi


# URL de la API de Last.fm para obtener información del álbum
API_URL="http://ws.audioscrobbler.com/2.0/?method=album.getinfo&album=$ALBUM&artist=$ARTIST&api_key=$LASTFM_APIKEY&format=json"

# Realiza la solicitud a la API de Last.fm
response=$(curl -s "$API_URL")

# Verifica si la respuesta contiene un error
if echo "$response" | grep -q "error"; then
#    echo "l buscar el álbum en Last.fm: $response"
    exit 1
fi

# Procesa la respuesta JSON para obtener la URL del álbum
album_url=$(echo "$response" | jq -r '.album.url')

# Imprime la URL del álbum
echo "$album_url"
