#!/bin/bash

# Verifica que se proporcionen dos argumentos
if [ "$#" -ne 2 ]; then
    echo "Uso: $0 FOLDER DESTINO"
    exit 1
fi

FOLDER="$1"
DESTINO="$2"

# Función para procesar archivos
procesar_archivo() {
    local archivo="$1"
    local subcarpeta
    local archivo_destino

    nombre_archivo=$(basename "$archivo")
    subcarpeta=$(dirname "$archivo" | sed "s|^${FOLDER}|${DESTINO}|")

    # Crear la ruta de destino manteniendo la estructura de directorios
    mkdir -p "$subcarpeta"

    if [[ "$archivo" == *.flac ]]; then
        # Extraer metadata del archivo .flac
        title=$(metaflac --show-tag=TITLE "$archivo" | sed 's/.*=//')
        artist=$(metaflac --show-tag=ARTIST "$archivo" | sed 's/.*=//')
        album=$(metaflac --show-tag=ALBUM "$archivo" | sed 's/.*=//')
        genre=$(metaflac --show-tag=GENRE "$archivo" | sed 's/.*=//')
        bpm=$(metaflac --show-tag=BPM "$archivo" | sed 's/.*=//')
        comment=$(metaflac --show-tag=COMMENT "$archivo" | sed 's/.*=//')
        # Convertir archivo .flac a .mp3 con metadata
        archivo_destino="${subcarpeta}"/"${nombre_archivo%.*}.mp3"
        ffmpeg -n -i "$archivo" -acodec libmp3lame -b:a 320k \
            -metadata title="$title" -metadata artist="$artist" -metadata album="$album" \
            -metadata genre="$genre" -metadata bpm="$bpm" -metadata commentdu="$comment \
            "$archivo_destino"
    elif [[ "$archivo" == *.mp3 ]]; then
        # Copiar archivo .mp3
        archivo_destino="${subcarpeta}"/"${nombre_archivo}"
        cp "$archivo" "$archivo_destino"
    fi
}

export -f procesar_archivo
export FOLDER
export DESTINO

# Encuentra y procesa todos los archivos .flac y .mp3 en FOLDER y sus subcarpetas
find "$FOLDER" -type f \( -name "*.flac" -o -name "*.mp3" \) -exec bash -c 'procesar_archivo "$0"' {} \;

echo "Conversión y copia completadas."