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
    # Ya existe frontmatter

    # Primero copiamos todo al archivo temporal
    cp "$file_path" "$temp_file"

    # Actualizar o añadir "publicado:"
    if grep -q "^publicado:" "$temp_file"; then
        # Actualizar la fecha existente
        sed -i "s/^publicado:.*/publicado: $current_date/" "$temp_file"
    else
        # Añadir la nueva línea después de la primera línea del frontmatter
        sed -i "1a\\
publicado: $current_date" "$temp_file"
    fi

    # Actualizar o añadir "sticker:"
    if ! grep -q "^sticker:" "$temp_file"; then
        # Añadir el sticker después de la primera línea del frontmatter
        sed -i "1a\\
sticker: emoji//2714-fe0f" "$temp_file"
    fi
else
    # No existe frontmatter, crearlo
    echo "---" > "$temp_file"
    echo 'sticker: emoji//2714-fe0f' >> "$temp_file"
    echo "publicado: $current_date" >> "$temp_file"
    echo "---" >> "$temp_file"
    echo "" >> "$temp_file"
    cat "$file_path" >> "$temp_file"
fi

# Reemplazar el archivo original con el temporal
mv "$temp_file" "$file_path"

echo "Frontmatter actualizado con fecha: $current_date"
