#!/bin/bash

# Obtener la fecha actual en formato ISO
current_date=$(date +"%Y-%m-%d")

# Archivo actual (usando la variable de Obsidian)
file_path="${1}"

# Verificar si el archivo existe
if [ ! -f "$file_path" ]; then
    echo "Error: El archivo no existe"
    exit 1
fi

# Crear archivo temporal
temp_file=$(mktemp)

# Verificar si ya existe frontmatter
if head -n 1 "$file_path" | grep -q "^---$"; then
    # Ya existe frontmatter, buscar si ya existe la línea "publicado:"
    if grep -q "^publicado:" "$file_path"; then
        # Actualizar la fecha existente
        sed "s/^publicado:.*/publicado: $current_date/" "$file_path" > "$temp_file"
    else
        # Añadir la nueva línea después de la primera línea del frontmatter
        sed "1a\\
publicado: $current_date" "$file_path" > "$temp_file"
    fi
else
    # No existe frontmatter, crearlo
    echo "---" > "$temp_file"
    echo "publicado: $current_date" >> "$temp_file"
    echo "---" >> "$temp_file"
    echo "" >> "$temp_file"
    cat "$file_path" >> "$temp_file"
fi

# Reemplazar el archivo original con el temporal
mv "$temp_file" "$file_path"

echo "Frontmatter actualizado con fecha: $current_date"
