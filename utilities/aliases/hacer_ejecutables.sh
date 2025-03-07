#!/usr/bin/env bash

# Función para ejecutar scripts en una carpeta
cambiar_permisos() {
    carpeta="$1"
    while IFS= read -r archivo; do
        if [ -x "$archivo" ]; then
            echo "Haciendo script ejecutable: $archivo"
            chmod u+x "$archivo"
        fi
    done < <(find "$carpeta" -type f)
}

# Ruta de la carpeta raíz
carpeta_raiz="$1"

# Llama a la función para recorrer todas las subcarpetas y ejecutar scripts
find "$carpeta_raiz" -type d -exec bash -c 'cambiar_permisos "$0"' {} \;
