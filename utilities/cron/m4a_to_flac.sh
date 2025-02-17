#!/bin/bash

# Directorio temporal para conversión local
TEMP_DIR="/tmp/m4a_to_flac"

# Crear el directorio si no existe
mkdir -p "$TEMP_DIR"

# Buscar todos los archivos .m4a en el NFS
find "${1}" -type f -name "*.m4a" | while read -r file; do
    # Obtener nombre de archivo y directorio base
    base_name="$(basename "$file" .m4a)"
    dir_name="$(dirname "$file")"

    # Copiar archivo localmente
    temp_file="$TEMP_DIR/$base_name.m4a"
    cp "$file" "$temp_file"

    # Verificar si la copia fue exitosa
    if [ ! -f "$temp_file" ]; then
        echo "Error copiando $file a $TEMP_DIR"
        continue
    fi

    # Convertir a FLAC manteniendo metadatos
    temp_flac="$TEMP_DIR/$base_name.flac"
    if ffmpeg -nostdin -i "$temp_file" -c:a flac -map_metadata 0 "$temp_flac"; then
        echo "Conversión exitosa: $file → $temp_flac"

        # Mover el archivo convertido de vuelta al NFS
        mv "$temp_flac" "$dir_name/"

        # Verificar si la conversión y el movimiento fueron exitosos antes de eliminar el original
        if [ -f "$dir_name/$base_name.flac" ]; then
            rm "$file"
            echo "Archivo original eliminado: $file"
        else
            echo "Error moviendo el archivo convertido. No se eliminó el original."
        fi
    else
        echo "Error en la conversión: $file"
    fi

    # Limpiar archivos temporales
    rm -f "$temp_file"
done
