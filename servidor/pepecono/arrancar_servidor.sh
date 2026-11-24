#!/usr/bin/env bash
#
# Script Name: arrancar_servidor.sh (pepecono)
# Description: Arranca el servidor de 192.168.1.222 en Proxmox o en Windows desde pepecono (24/7).
#              Lo llaman el atajo de awesomewm (por SSH) y la web del móvil (servidor_web.py).
#              Cada paso sale por stdout y el resultado final se avisa por Telegram.
#              Windows se elige solo para ese arranque: al reiniciarlo vuelve Proxmox.
# Uso:         arrancar_servidor.sh estado
#              arrancar_servidor.sh proxmox|windows [--forzar]
#              Sin --forzar no reinicia un sistema que ya esté encendido (sale con código 3).
#
set -uo pipefail

HOST="192.168.1.222"
PORT_PROXMOX=2288
PORT_WINDOWS=22
WAKE_SCRIPT="$HOME/Scripts/kopia/wake_proxmox.sh"
ENV_FILE="$HOME/Scripts/kopia/.encrypted.env"
REMOTE_CMD="/usr/local/sbin/reboot-to-windows"
LOGIN_TRIES=36
BOOT_TRIES=60
SLEEP_BETWEEN=5
LOCK_FILE="${XDG_RUNTIME_DIR:-/tmp}/arrancar_servidor.lock"
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=8)
EXIT_NEEDS_CONFIRM=3

telegram() {
    [[ -n "${TELEGRAM_BOT_TOKEN:-}" ]] || return 0
    curl -s -m 10 -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d chat_id="${TELEGRAM_CHAT_ID}" --data-urlencode "text=$1" >/dev/null
}

info() {
    echo "$1"
}

done_ok() {
    echo "$1"
    telegram "🖥️ $1"
    exit 0
}

die() {
    echo "ERROR: $1"
    telegram "🚨 Servidor: $1"
    exit 1
}

port_open() {
    nc -z -w3 "$HOST" "$1" 2>/dev/null
}

estado() {
    if port_open "$PORT_PROXMOX"; then
        echo "proxmox"
    elif port_open "$PORT_WINDOWS"; then
        echo "windows"
    else
        echo "apagado"
    fi
}

wait_port() {
    local port="$1" i
    for ((i = 1; i <= BOOT_TRIES; i++)); do
        port_open "$port" && return 0
        sleep "$SLEEP_BETWEEN"
    done
    return 1
}

# El puerto abre antes de que pam_nologin permita entrar a usuarios normales
wait_proxmox_login() {
    local i output
    for ((i = 1; i <= LOGIN_TRIES; i++)); do
        output=$(ssh "${SSH_OPTS[@]}" proxmox true 2>&1) && return 0
        [[ "$output" == *"Permission denied"* ]] && die "Proxmox rechaza la clave SSH de pepecono"
        sleep "$SLEEP_BETWEEN"
    done
    die "Proxmox no acepta SSH"
}

wake_server() {
    local output
    info "Enviando WOL..."
    output=$("$WAKE_SCRIPT") || die "No arranca con WOL: $output"
}

needs_confirm() {
    echo "CONFIRMAR: $1"
    exit "$EXIT_NEEDS_CONFIRM"
}

start_proxmox() {
    local status
    case "$(estado)" in
        proxmox) done_ok "Proxmox ya está encendido" ;;
        windows)
            $FORCE || needs_confirm "Windows encendido: ¿reiniciar en Proxmox?"
            info "Reiniciando Windows..."
            # 255 es normal si el reinicio corta la conexión
            ssh "${SSH_OPTS[@]}" windows 'shutdown /r /t 0' 2>/dev/null
            status=$?
            ((status == 0 || status == 255)) || die "No se ha podido reiniciar Windows (código $status)"
            wait_port "$PORT_PROXMOX" || die "Proxmox no responde tras reiniciar Windows"
            ;;
        apagado) wake_server ;;
    esac
    done_ok "Proxmox ya responde"
}

start_windows() {
    local status
    case "$(estado)" in
        windows) done_ok "Windows ya está encendido" ;;
        # Ya encendido: el reinicio pararía las máquinas virtuales en marcha
        proxmox) $FORCE || needs_confirm "Proxmox encendido: ¿reiniciar en Windows?" ;;
        apagado) wake_server ;;
    esac

    wait_proxmox_login

    info "Reiniciando en Windows..."
    # 255 es normal si el reinicio corta la conexión; otro código es un fallo del script remoto
    ssh "${SSH_OPTS[@]}" proxmox sudo -n "$REMOTE_CMD" 2>/dev/null
    status=$?
    ((status == 0 || status == 255)) || die "El script de Proxmox ha fallado (código $status)"

    wait_port "$PORT_WINDOWS" || die "Windows no responde en el puerto $PORT_WINDOWS; compruébalo en la pantalla del servidor"
    done_ok "Windows ya responde"
}

target="${1:-}"
FORCE=false
[[ "${2:-}" == "--forzar" ]] && FORCE=true

if [[ "$target" == "estado" ]]; then
    estado
    exit 0
fi

[[ "$target" == "proxmox" || "$target" == "windows" ]] || { echo "Uso: $0 estado | proxmox|windows [--forzar]"; exit 2; }

# Sin token, el arranque funciona igual pero no avisa por Telegram
eval "$(sops --decrypt "$ENV_FILE" 2>/dev/null)" || true

# Evita dos arranques a la vez (doble pulsación, o el PC y el móvil a la vez)
exec 9>"$LOCK_FILE"
flock -n 9 || { echo "ERROR: Ya hay un arranque en curso"; exit 1; }

"start_$target"
