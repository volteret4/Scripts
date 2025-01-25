#!/usr/bin/env bash

# Define el directorio donde están tus archivos Markdown
SEARCH_DIR="/mnt/windows/FTP/wiki/Obsidian/"

busq="$1"
if [[ -z $busq ]]; then busq=".+"; fi

# Realiza la búsqueda fuzzy con ripgrep
search_results=$(rg --heading --line-number --json --glob '*.md' "$busq" "$SEARCH_DIR" | jq -r '
    select(.type == "match") |
    "\(.data.path.text | sub("'"$SEARCH_DIR"'/?"; "")):\(.data.line_number): \(.data.lines.text)"
')

# Filtrar resultados para eliminar líneas vacías
search_results=$(echo "$search_results" | sed '/^$/d')

# Si no se encuentran coincidencias, muestra un mensaje y termina el script
if [ -z "$search_results" ]; then
    echo "No se encontraron coincidencias."
    exit 1
fi

# Filtrar para mostrar solo la primera coincidencia de cada archivo
search_results=$(echo "$search_results" | awk -F: '!seen[$1]++')

# Formatear los resultados para rofi
formatted_results=$(echo "$search_results" | awk -F: '{print $1}')

# Usa rofi para mostrar los resultados y permitir al usuario seleccionar uno
selected=$(echo "$formatted_results" | rofi -dmenu -i -p "Selecciona un archivo")

# Si el usuario no selecciona nada, termina el script
if [ -z "$selected" ]; then
    exit 1
fi

# Extrae la ruta del archivo del resultado seleccionado
file_path="$SEARCH_DIR/$selected"

# Verifica que el archivo exista
if [ ! -f "$file_path" ]; then
    echo "El archivo seleccionado no existe."
    exit 1
fi

# Muestra el contenido completo del archivo la primera vez
view_content=$(cat "$file_path")
selected_content=$(echo "$view_content" | rofi -dmenu -i -p "Edita el contenido")

# Si el usuario no selecciona nada, salimos del script
if [ -z "$selected_content" ]; then
    exit 0
fi

# Copia el contenido seleccionado a copyq (y opcionalmente a xclip)
echo "$selected_content" | copyq add -
echo "$selected_content" | xclip

# Ahora, si se desea buscar con contexto, mostrar el contenido del archivo con contexto adicional
busq=$(echo "$view_content" | rofi -dmenu -i -p "Busca un término")

# Si el usuario no introduce nada, no hacemos nada más
if [ -z "$busq" ]; then
    exit 0
fi

# Obtiene la línea de coincidencia para la visualización del contexto
search_results=$(rg --heading --line-number --json --glob '*.md' "$busq" "$file_path" | jq -r '
    select(.type == "match") |
    "\(.data.path.text | sub("'"$SEARCH_DIR"'/?"; "")):\(.data.line_number): \(.data.lines.text)"
')

# Filtrar para eliminar líneas vacías
search_results=$(echo "$search_results" | sed '/^$/d')

# Si no se encuentran coincidencias, muestra un mensaje y termina el script
if [ -z "$search_results" ]; then
    echo "No se encontraron coincidencias."
    exit 1
fi

# Extrae la línea de coincidencia
match_line=$(echo "$search_results" | awk -F: '{print $2}')

# Define el número de líneas de contexto
context_lines=3

# Extrae el contenido del archivo con el contexto adicional alrededor de la coincidencia
context=$(awk -v line=$match_line -v context=$context_lines 'NR>=line-context && NR<=line+context {print NR ": " $0}' "$file_path")

# Crea un archivo temporal para la edición
temp_file=$(mktemp)
echo "$context" > "$temp_file"

# Usa rofi en modo extendido para mostrar el contenido del archivo con contexto
selected_line=$(rofi -dmenu -i -p "Selecciona una línea para copiar (Enter) o abrir el archivo (Shift+Enter)" -mesg "Presiona Enter para copiar a copyq o Shift+Enter para abrir el archivo en Geany" < "$temp_file")

# Verifica si se hizo una selección
if [ -n "$selected_line" ]; then
    # Copia la línea seleccionada a copyq (y opcionalmente a xclip)
    echo "$selected_line" | copyq add -
    echo "$selected_line" | xclip -selection clipboard
    # Comprueba si se presionó Shift+Enter
    if [[ $(xprop -root _NET_ACTIVE_WINDOW) =~ "_NET_WM_NAME(CUTF8_STRING) = \"rofi\"" ]]; then
        # Si se presionó Shift+Enter, abre el archivo en geany
        geany "$file_path"
    fi
fi

# Limpia el archivo temporal
rm "$temp_file"