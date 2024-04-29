#!/bin/bash

# Directorio en el que buscar
DIRECTORIO="/mnt/Datos/FTP/Wiki/Obsidian"

# Buscar archivos .md y pasarlos a fzf para búsqueda fuzzy
ARCHIVO=$(find "$DIRECTORIO" -type f -name "*.md" | fzf)

# Mostrar el contenido del archivo seleccionado
if [ -n "$ARCHIVO" ]; then
    vscodium "$ARCHIVO"
fi