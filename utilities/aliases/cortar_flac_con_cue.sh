#!/bin/bash

# Verificar argumentos
if [ $# -ne 2 ]; then
    echo "Uso: $0 archivo.flac archivo.cue"
    exit 1
fi

FLAC_FILE=$1
CUE_FILE=$2

# Verificar que los archivos existen
if [ ! -f "$FLAC_FILE" ]; then
    echo "Error: El archivo FLAC '$FLAC_FILE' no existe."
    exit 1
fi

if [ ! -f "$CUE_FILE" ]; then
    echo "Error: El archivo CUE '$CUE_FILE' no existe."
    exit 1
fi

# Verificar que las herramientas necesarias están instaladas
command -v shnsplit >/dev/null 2>&1 || { echo "Error: 'shnsplit' no está instalado. Instala 'shntool'."; exit 1; }
command -v cuetag.sh >/dev/null 2>&1 || { echo "Error: 'cuetag' no está instalado. Instala 'cuetools'."; exit 1; }
command -v flac >/dev/null 2>&1 || { echo "Error: 'flac' no está instalado. Instala 'flac'."; exit 1; }

# Crear directorio para los archivos cortados
ALBUM_DIR="$(basename "$FLAC_FILE" .flac)_split"
mkdir -p "$ALBUM_DIR"

echo "Cortando el archivo FLAC según el archivo CUE..."

# Cortar el archivo FLAC
shnsplit -f "$CUE_FILE" -t "%n - %t" -d "$ALBUM_DIR" -o flac "$FLAC_FILE"

# Añadir etiquetas a los archivos cortados
cd "$ALBUM_DIR"
cuetag.sh ../"$CUE_FILE" *.flac

echo "Proceso completado. Los archivos cortados están en el directorio '$ALBUM_DIR'."