#!/bin/bash

# Directorio de origen
DIRECTORIO="${1:-/${HOME}/Scripts/}"

# Directorio de destino para los hardlinks
DESTINO="${2:-/mnt/Datos/FTP/Wiki/Obsidian/Spaces/Home/Wiki/}"

# Verificar si se proporcionaron los directorios
if [ -z "$DIRECTORIO" ] || [ -z "$DESTINO" ]; then
  echo "Uso: $0 <directorio_origen> <directorio_destino>"
  exit 1
fi

# Verificar si el directorio de origen existe
if [ ! -d "$DIRECTORIO" ]; then
  echo "El directorio de origen '$DIRECTORIO' no existe."
  exit 1
fi

# Verificar si el directorio de destino existe
if [ ! -d "$DESTINO" ]; then
  echo "El directorio de destino '$DESTINO' no existe."
  exit 1
fi

# Crear hardlinks de archivos .sh en el directorio de destino
find "$DIRECTORIO" -type f -name "*.sh" -exec ln {} "$DESTINO" \;

# Crear hardlinks de archivos .py en el directorio de destino
find "$DIRECTORIO" -type f -name "*.py" -exec ln {} "$DESTINO" \;