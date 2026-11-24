#!/usr/bin/env bash
#
# Script Name: arrancar_servidor.sh
# Description: Pregunta qué arrancar en el servidor (P: Proxmox, W: Windows) y se lo pide a pepecono,
#              que es quien lo arranca (está 24/7; el móvil usa su web en http://192.168.1.133:8781).
#              Desde una terminal pregunta ahí; sin terminal (atajo de awesomewm) usa un popup de rofi.
#              Windows se elige solo para ese arranque: al reiniciarlo vuelve Proxmox.
# Uso:         arrancar_servidor.sh [proxmox|windows]
#
set -uo pipefail

PEPECONO="pepecono"
REMOTE_SCRIPT="Scripts/servidor/arrancar_servidor.sh"
EXIT_NEEDS_CONFIRM=3
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=8)

has_tty() {
    [[ -t 0 ]]
}

info() {
    echo "$1"
    has_tty || notify-send -a "Servidor" "Servidor" "$1"
}

die() {
    echo "ERROR: $1" >&2
    has_tty || notify-send -a "Servidor" -u critical "Servidor" "$1"
    exit 1
}

# Con -auto-select basta una tecla: cada opción tiene una inicial que no aparece en la otra
popup() {
    local prompt="$1"
    shift
    printf '%s\n' "$@" | rofi -dmenu -i -auto-select -no-custom -l "$#" -p "$prompt" 2>/dev/null
}

ask_target() {
    local answer
    if has_tty; then
        read -r -n 1 -p "¿Qué arrancar? [P]roxmox / [W]indows: " answer
        echo
    else
        answer=$(popup "Arrancar servidor" "Proxmox" "Windows")
    fi
    case "${answer,,}" in
        p*) echo "proxmox" ;;
        w*) echo "windows" ;;
    esac
}

confirm() {
    local answer
    if has_tty; then
        read -r -p "$1 [s/N] " answer
    else
        answer=$(popup "$1" "Si" "No")
    fi
    [[ "${answer,,}" == s* ]]
}

# Ejecuta el script de pepecono y muestra cada paso como aviso.
# Deja el código de salida en $exit_code y la pregunta pendiente (si la hay) en $question.
run_remote() {
    local line
    exit_code=255
    question=""
    while IFS= read -r line; do
        case "$line" in
            __STATUS__*) exit_code="${line#__STATUS__ }" ;;
            CONFIRMAR:*) question="${line#CONFIRMAR: }" ;;
            ERROR:*) die "${line#ERROR: }" ;;
            *) info "$line" ;;
        esac
    done < <(ssh "${SSH_OPTS[@]}" "$PEPECONO" "$REMOTE_SCRIPT" "$@" 2>&1; echo "__STATUS__ $?")
}

target="${1:-$(ask_target)}"
[[ -z "$target" ]] && { echo "Cancelado"; exit 0; }
[[ "$target" == "proxmox" || "$target" == "windows" ]] || die "Destino no válido: $target (usa proxmox o windows)"

info "Pidiendo a pepecono que arranque $target..."
run_remote "$target"

if [[ "$exit_code" == "$EXIT_NEEDS_CONFIRM" ]]; then
    confirm "$question" || { echo "Cancelado"; exit 0; }
    run_remote "$target" --forzar
fi

case "$exit_code" in
    0) ;;
    255) die "No se puede conectar con pepecono por SSH" ;;
    *) die "pepecono no ha podido arrancar $target (código $exit_code)" ;;
esac
