#!/bin/bash

# Función para mostrar cómo usar el script
usage() {
    echo "Uso: $0 artist album [musicbrainz_url]"
    exit 1
}

# Función para descargar la portada del álbum
download_cover_art() {
    local mbid=$1
    local cover_art_url="http://coverartarchive.org/release/$mbid/front-1200"
    local cover_file="$HOME/hugo/web/vvmm/links/portada/image.jpeg"
    
    # Descargar la imagen
    echo "Descargando portada del álbum...$cover_art_url"
    curl -L -o "$cover_file" "$cover_art_url"

    if [ $? -eq 0 ]; then
        echo "Portada descargada exitosamente como image.jpeg"
    else
        echo "Error al descargar la portada"
    fi
}

# Obtener el MBID del álbum usando la API de MusicBrainz
get_mbid() {
    local artist=$1
    local album=$2

    echo "Buscando MBID para $artist - $album..."
    query=$(echo "artist:$artist release:$album" | sed 's/ /%20/g')
    mbid=$(curl -s "https://musicbrainz.org/ws/2/release/?query=$query&fmt=json" | jq -r '.releases[0].id')

    if [ -z "$mbid" ] || [ "$mbid" == "null" ]; then
        echo "No se encontró el álbum en MusicBrainz"
        exit 1
    fi

    echo "$mbid"
}

# Comprobar los argumentos
if [ $# -eq 2 ]; then
    artist=$1
    album=$2
    
    cover_file="$HOME/hugo/web/vvmm/links/portada/image.jpeg"
    rm $cover_file
    
    mbid=$(get_mbid "$artist" "$album")
    download_cover_art "$mbid"

elif [ $# -eq 3 ]; then
    artist=$1
    album=$2
    musicbrainz_url=$3

    # Extraer el MBID de la URL de MusicBrainz
    mbid=$(echo "$musicbrainz_url" | grep -oP '[a-f0-9-]{36}')

    if [ -z "$mbid" ]; then
        echo "URL de MusicBrainz no válida"
        exit 1
    fi

    download_cover_art "$mbid"

else
    usage
fi