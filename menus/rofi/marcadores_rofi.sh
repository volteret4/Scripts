#!/bin/bash

# Archivo JSON temporal (sustitúyelo por la ruta a tu archivo JSON)
JSON_FILE="$HOME/Scripts/.content/marcadores/bookmarks_filtered.json"

# Función para formatear los elementos para Rofi
format_for_rofi() {
    # Usamos jq para procesar el JSON
    jq -r '.[] | "\(.title) [\(if .tags | length > 0 then .tags | join(", ") else "" end)]|\(.id)|\(.url)|\(if .summary then .summary else "" end)"' "$JSON_FILE" |
    # Procesamos cada línea para crear el formato deseado
    while IFS="|" read -r title_tags id url summary; do
        if [ -n "$summary" ]; then
            echo -e "<b>$title_tags</b>\n    <i><small>$summary</small></i>"
        else
            echo -e "<b>$title_tags</b>"
        fi
    done
}

# Función para abrir la URL seleccionada
open_url() {
    local selection="$1"
    # Extraer el ID del elemento seleccionado
    local id=$(echo "$selection" | grep -o -P '(?<=\[).*(?=\])')
    
    # Buscar la URL correspondiente en el JSON
    local url=$(jq -r ".[] | select(.id == \"$id\") | .url" "$JSON_FILE")
    
    # Abrir la URL (usando xdg-open)
    if [ -n "$url" ]; then
        xdg-open "$url" &
    fi
}

# Mostrar menú Rofi con los elementos formateados
selection=$(format_for_rofi | rofi -dmenu -i -markup-rows -no-custom -fuzzy -width 80 -p "Marcadores" -matching normal)

# Si se seleccionó algo, extraer el ID y abrir la URL
if [ -n "$selection" ]; then
    # Extraer el ID y luego buscar de nuevo en el JSON original
    # Necesitamos volver a comparar con el título completo
    title=$(echo "$selection" | head -n1 | sed 's/<[^>]*>//g')
    
    # Encontrar el ID usando el título
    id=$(jq -r ".[] | select(.title | startswith(\"$(echo "$title" | cut -d'[' -f1 | xargs)\")) | .id" "$JSON_FILE")
    
    # Encontrar y abrir la URL
    url=$(jq -r ".[] | select(.id == \"$id\") | .url" "$JSON_FILE")
    
    if [ -n "$url" ]; then
        xdg-open "$url" &
    fi
fi

