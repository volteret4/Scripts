#!/usr/bin/env bash
#
# Script Name: nerd-dictation.sh
# Description: Toggle nerd-dictation on/off with persistent notifications
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# Notes:
#   Dependencies: - dunst/notify-send
#                 - nerd-dictation


# Debug
source "/home/huan/Scripts/utilities/notificaciones/debug/debug.sh"
setup_error_trap

# Python_venv
source "$HOME/Scripts/python_venv/bin/activate"

# Nerd-dictation path
nerd_dictation="$HOME/gits/nerd-dictation/nerd-dictation"

# Estado persistente
STATE_FILE="/tmp/nerd-dictation-state"
NOTIFICATION_ID_FILE="/tmp/nerd-dictation-notification-id"

# Función para activar nerd-dictation
activate_nerd_dictation() {
    echo "Activando nerd-dictation"

    # Iniciar nerd-dictation
    $nerd_dictation begin &
    local pid=$!

    # Esperar un poco para verificar que se inició correctamente
    sleep 1

    if kill -0 $pid 2>/dev/null; then
        # Guardar estado
        echo "ACTIVO" > "$STATE_FILE"

        # Mostrar notificación persistente
        local notification_id=$(notify-send \
            --icon="audio-input-microphone" \
            --urgency=normal \
            --hint=int:transient:0 \
            --print-id \
            "Nerd-dictation ACTIVO" \
            "Dictado por voz habilitado")

        # Guardar ID de notificación
        echo "$notification_id" > "$NOTIFICATION_ID_FILE"

        notify_success "Nerd-dictation activado correctamente" "$0" "Éxito" "000"
    else
        notify_error "Error al arrancar nerd-dictation" "$0" "Error al arrancar nerd-dictation" "100"
        exit 1
    fi
}

# Función para desactivar nerd-dictation
deactivate_nerd_dictation() {
    echo "Desactivando nerd-dictation"

    # Terminar nerd-dictation
    $nerd_dictation end

    if [ $? -eq 0 ]; then
        # Eliminar estado
        rm -f "$STATE_FILE"

        # Eliminar notificación persistente si existe
        if [ -f "$NOTIFICATION_ID_FILE" ]; then
            local notification_id=$(cat "$NOTIFICATION_ID_FILE")
            notify-send --close="$notification_id" 2>/dev/null
            rm -f "$NOTIFICATION_ID_FILE"
        fi

        # Mostrar notificación temporal de desactivación
        notify-send \
            --icon="audio-input-microphone-muted" \
            --urgency=normal \
            --expire-time=3000 \
            "Nerd-dictation DESACTIVADO" \
            "Dictado por voz deshabilitado"

        notify_success "Nerd-dictation desactivado correctamente" "$0" "Éxito" "000"
    else
        notify_error "Error al desactivar nerd-dictation" "$0" "Error al desactivar nerd-dictation" "100"
        exit 1
    fi
}

# Verificar estado actual
if [ -f "$STATE_FILE" ] && [ "$(cat "$STATE_FILE")" == "ACTIVO" ]; then
    # Verificar si realmente está corriendo
    if pgrep -f "nerd-dictation.*begin" > /dev/null; then
        echo "Nerd-dictation está activo, desactivando..."
        deactivate_nerd_dictation
    else
        # El archivo de estado existe pero el proceso no está corriendo
        echo "Estado inconsistente detectado, limpiando..."
        rm -f "$STATE_FILE" "$NOTIFICATION_ID_FILE"
        activate_nerd_dictation
    fi
else
    # No está activo, activar
    activate_nerd_dictation
fi
