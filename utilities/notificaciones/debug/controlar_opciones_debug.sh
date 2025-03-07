#!/usr/bin/env bash

# Extrae la acción
ACTION="$1"
ACTION_TYPE="${ACTION%_*}"    # Todo antes del último guion bajo
SCRIPT_NAME="${ACTION#*_}"    # Todo después del último guion bajo

# Recupera la información almacenada
SOURCE_FILE=$(cat "/tmp/dunst_action_$SCRIPT_NAME.source" 2>/dev/null)
MESSAGE=$(cat "/tmp/dunst_action_$SCRIPT_NAME.message" 2>/dev/null)

if [ -z "$SOURCE_FILE" ]; then
    notify-send "Error" "No se pudo encontrar el archivo de origen para la acción"
    exit 1
fi

case "$ACTION_TYPE" in
    "vscodium")
        codium "$SOURCE_FILE"
        ;;
    "folder")
        script_dir=$(dirname "$SOURCE_FILE")
        xdg-open "$script_dir"
        ;;
    "tarea")
        $HOME/ruta/a/tu/script_tareas.sh "$SCRIPT_NAME: $MESSAGE"
        ;;
    *)
        notify-send "Error" "Acción desconocida: $ACTION_TYPE"
        ;;
esac

# Limpiar archivos temporales (opcional)
# rm -f "/tmp/dunst_action_$SCRIPT_NAME.source" "/tmp/dunst_action_$SCRIPT_NAME.message"