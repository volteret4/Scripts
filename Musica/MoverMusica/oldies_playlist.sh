#!/bin/bash

# Directorios
MIX_DIR="/mnt/windows/Mix"
OLD_DIR="$MIX_DIR/.old"
PLAYLISTS_DIR="$MIX_DIR/.playlists"

# Crear el directorio .old si no existe
mkdir -p "$OLD_DIR"

# Función para leer archivos desde un .m3u
leer_m3u() {
    local archivo_m3u="$1"
    grep -v '^#' "$archivo_m3u" | sed '/^$/d' # Ignorar comentarios y líneas vacías
}

# Función para actualizar las rutas en las playlists de .playlists
actualizar_playlists() {
    local archivo="$1"
    local nueva_ruta="$2"
    for playlist in "$PLAYLISTS_DIR"/*.m3u; do
        if grep -q "$archivo" "$playlist"; then
            echo "Actualizando referencia en $playlist"
            sed -i "s|$archivo|$nueva_ruta|g" "$playlist"
        fi
    done
}

# Recorrer las carpetas en /Mix (excluyendo .old y .playlists)
for carpeta in "$MIX_DIR"/*; do
    if [[ -d "$carpeta" && "$(basename "$carpeta")" != ".old" && "$(basename "$carpeta")" != ".playlists" ]]; then
        genre=$(basename "$carpeta")
        archivo_m3u="$MIX_DIR/$genre.m3u"
        
        # Verificar si existe la playlist con el mismo nombre que la carpeta
        if [[ -f "$archivo_m3u" ]]; then
            archivos_playlist=$(leer_m3u "$archivo_m3u")
            
            # Crear el subdirectorio en .old si no existe
            mkdir -p "$OLD_DIR/$genre"
            
            # Recorrer los archivos en la carpeta
            for archivo in "$carpeta"/*; do
                archivo_base=$(basename "$archivo")
                
                # Verificar si el archivo está en la playlist
                if ! echo "$archivos_playlist" | grep -q "$archivo_base"; then
                    # Mover el archivo a .old/$genre
                    nueva_ruta="$OLD_DIR/$genre/$archivo_base"
                    mv "$archivo" "$nueva_ruta"
                    echo "Moviendo $archivo_base a $OLD_DIR/$genre/"
                    
                    # Actualizar referencias en playlists de .playlists
                    actualizar_playlists "$archivo_base" "$nueva_ruta"
                fi
            done
        else
            echo "No se encontró la playlist para el género: $genre"
        fi
    fi
done

