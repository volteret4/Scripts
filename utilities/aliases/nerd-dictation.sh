#! /usr/bin/env bash
#
# Script Name: .sh
# Description: 
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# Notes:
#   Dependencies:  - dunst 
#

# Debug
source "/home/huan/Scripts/utilities/notificaciones/debug/debug.sh"
setup_error_trap

# Python_venv
source "$HOME/Scripts/python_venv/bin/activate"

# Nerd-dictation path
nerd_dictation="$HOME/gits/nerd-dictation/nerd-dictation"

if [[ -z "$NERD_DICTATION" ]]; then
    echo "Activando nerd-dictation"
    notify_success "Arrancando nerd-dictation" "$0" "Éxito" "000"
    $nerd_dictation begin & 
    if [ $? -ne 0 ]; then
        notify_error "Error al arrancar nerd-dictation" "$0" "Error al arrancar nerd-dictation" "100"
        exit 1
    fi
    export NERD_DICTATION="Activado"
elif [[ "$NERD_DICTATION" == "Activado" ]]; then
    echo "Desactivando nerd-dictation"
    notify_success "Desactivando nerd-dictation" "$0" "Éxito" "000"
    $nerd_dictation end &
    if [ $? -ne 0 ]; then
        notify_error "Error al desactivar nerd-dictation" "$0" "Error al desactivar nerd-dictation" "100"
        exit 1
    fi
    export NERD_DICTATION="Desactivado"
elif [[ "$NERD_DICTATION" == "Desactivado" ]]; then
    echo "Activando nerd-dictation"
    notify_success "Activando nerd-dictation" "$0" "Éxito" "000"
    $nerd_dictation begin &
    if [ $? -ne 0 ]; then
        notify_error "Error al activar nerd-dictation" "$0" "Error al activar nerd-dictation" "100"
        exit 1
    fi
    export NERD_DICTATION="Activado"
fi