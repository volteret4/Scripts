#!/usr/bin/env bash
#
# Script Name: debug.sh
# Description: 
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# Notes:
#   Dependencies:  - dunst 
#
#   El formato es un string de 3 dígitos ("111" por defecto):
#       Primer dígito: 1 para mostrar el botón de VSCodium, 0 para ocultarlo
#       Segundo dígito: 1 para mostrar el botón de carpeta, 0 para ocultarlo
#       Tercer dígito: 1 para mostrar el botón de tareas, 0 para ocultarlo
#
# MODO DE USO:
#
# source debug.sh
# 
# notify_info "Esto muestra todos los botones"                      # Mostrar todos los botones (comportamiento por defecto)
# notify_info "Solo botón de VSCodium" "$0" "Título" "100"          # Mostrar solo el botón de VSCodium
# notify_warning "Sin botón de VSCodium" "$0" "Advertencia" "011"   # Mostrar solo botones de carpeta y tareas
# notify_success "Sin botones" "$0" "Éxito" "000"                   # Sin botones



# Función de notificación mejorada con manejo de acciones
notify_message() {
    local script_path=$(realpath "${3:-$0}")
    local script_name=$(basename "$script_path")
    local urgency="${1:-normal}"
    local message="${2:-Mensaje}"
    local title="${4:-Notificación}"
    local config="${5:-111}"  # Configuración de botones: 1=mostrar, 0=ocultar (codium, carpeta, tarea)
    
    # Almacenar información en un archivo temporal para que el manejador de acciones pueda acceder
    echo "$script_path" > "/tmp/dunst_action_$script_name.source"
    echo "$message" > "/tmp/dunst_action_$script_name.message"
    
    # Determinar color e icono según urgencia
    local bg_color=""
    local icon=""
    
    case "$urgency" in
        "low")
            bg_color="#4CAF50"
            icon="dialog-information"
            ;;
        "normal")
            bg_color= "#c6a5f7"
            icon="dialog-information"
            ;;
        "critical")
            bg_color="#FF5555"
            icon="dialog-error"
            ;;
        *)
            bg_color="#3498DB"
            icon="dialog-information"
            ;;
    esac
    
    # Construir comando dunstify con opciones dinámicas
    local cmd="dunstify -u \"$urgency\" -a \"ScriptMonitor\" -i \"$icon\" -h string:x-dunst-stack-tag:\"$script_name\" -h \"string:bgcolor:$bg_color\""
    
    # Añadir acciones según la configuración
    if [[ "${config:0:1}" == "1" ]]; then
        cmd="$cmd -A \"vscodium_$script_name,Editar con Codium\""
    fi
    
    if [[ "${config:1:1}" == "1" ]]; then
        cmd="$cmd -A \"folder_$script_name,Abrir carpeta\""
    fi
    
    if [[ "${config:2:1}" == "1" ]]; then
        cmd="$cmd -A \"tarea_$script_name,Añadir a tareas\""
    fi
    
    # Completar el comando con título y mensaje
    cmd="$cmd \"$title\" \"$message\""
    
    # Enviar notificación
    export DISPLAY=":0"
    eval "$cmd"
}

# Alias para conveniencia
notify_info() {
    notify_message "normal" "$1" "$2" "${3:-Info}" "${4:-111}"
}

notify_warning() {
    notify_message "normal" "$1" "$2" "${3:-Advertencia}" "${4:-111}"
}

notify_error() {
    notify_message "critical" "$1" "$2" "${3:-ERROR}" "${4:-111}"
}

notify_success() {
    notify_message "low" "$1" "$2" "${3:-Éxito}" "${4:-111}"
}

# Configura el trap para capturar errores
setup_error_trap() {
    trap 'notify_error "$(tail -n 1 /tmp/script_error_$$.log)" "$0"' ERR
    # Redirecciona stderr a un archivo temporal
    exec 2> >(tee /tmp/script_error_$$.log)
}

# Función para limpiar archivos temporales al finalizar
cleanup() {
    rm -f /tmp/script_error_$$.log
}