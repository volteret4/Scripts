#!/bin/bash

# Archivo de entrada con los nombres de los artistas (uno por línea)
ARTISTAS_FILE="$HOME/Scripts/.content/thunderbird_artistas.txt"

# Archivo msgFilterRules.dat donde se agregarán los filtros
MSG_FILTER_RULES="$HOME/Scripts/.content/msgFilterRules.dat"

# Verifica que ambos archivos existan
if [[ ! -f "$ARTISTAS_FILE" ]]; then
    echo "Error: No se encontró el archivo $ARTISTAS_FILE."
    exit 1
fi

if [[ ! -f "$MSG_FILTER_RULES" ]]; then
    echo "Error: No se encontró el archivo $MSG_FILTER_RULES."
    exit 1
fi

# Itera sobre cada línea del archivo de artistas
while IFS= read -r ARTISTA; do
    # Elimina espacios innecesarios
    ARTISTA=$(echo "$ARTISTA" | xargs)
    if [[ -z "$ARTISTA" ]]; then
        continue
    fi

    # Genera la regla
    FILTER_RULE=$(cat <<EOF
name="$ARTISTA"
enabled="yes"
type="17"
action="Move to folder"
actionValue="imap://frodobolson@disroot.org/Musica/Techno/Sellos"
condition="AND (from,is,noreply@bandcamp.com) AND (subject,is,New release from $ARTISTA)"
EOF
)

    # Agrega la regla al archivo msgFilterRules.dat
    echo "$FILTER_RULE" >> "$MSG_FILTER_RULES"
    echo "" >> "$MSG_FILTER_RULES" # Línea en blanco para separar filtros
done < "$ARTISTAS_FILE"

echo "Filtros creados y agregados a $MSG_FILTER_RULES."