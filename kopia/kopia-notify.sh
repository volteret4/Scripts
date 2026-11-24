#!/usr/bin/env bash
#
# Script Name: kopia-notify.sh
# Description: Ejecuta un comando y notifica el resultado (éxito/fallo) por Telegram
# Uso: kopia-notify.sh "<nombre-tarea>" -- <comando> [args...]
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.encrypted.env"

TASK_NAME="${1:?Uso: kopia-notify.sh <nombre-tarea> -- <comando> [args...]}"
shift
[ "${1:-}" = "--" ] && shift

eval "$(sops --decrypt "$ENV_FILE")"

# send_telegram <texto> [silencioso: true|false]
send_telegram() {
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d chat_id="${TELEGRAM_CHAT_ID}" \
        -d parse_mode="HTML" \
        -d disable_notification="${2:-false}" \
        --data-urlencode "text=$1" >/dev/null
}
# Icono del lanzador: si hay error se manda solo antes del detalle, y
# Telegram lo pinta en grande.
ICONO="${KOPIA_NOTIFY_ICONO:-💾}"

HOST="$(uname -n)"
LOG_FILE="$(mktemp)"
trap 'rm -f "$LOG_FILE"' EXIT

STATUS_DIR="$HOME/.cache/kopia-status"
mkdir -p "$STATUS_DIR"
TASK_SLUG="$(echo "$TASK_NAME" | tr -c 'A-Za-z0-9' '_' | tr -s '_' | sed 's/^_//;s/_$//')"

START=$(date +%s)
"$@" >"$LOG_FILE" 2>&1
STATUS=$?
DURATION=$(( $(date +%s) - START ))
FINISHED_AT="$(date -Iseconds)"

cp "$LOG_FILE" "$STATUS_DIR/$TASK_SLUG.log"
cat > "$STATUS_DIR/$TASK_SLUG.json" <<JSON_EOF
{"task":"$TASK_NAME","host":"$HOST","exit_code":$STATUS,"duration_s":$DURATION,"finished_at":"$FINISHED_AT"}
JSON_EOF

if [ "$STATUS" -eq 0 ]; then
    send_telegram "${ICONO} ✅ <b>${TASK_NAME}</b> (${HOST}) — OK en ${DURATION}s" true
else
    TAIL="$(tail -c 800 "$LOG_FILE" | sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g')"
    send_telegram "${ICONO}"
    send_telegram "${ICONO} 🚨 <b>${TASK_NAME}</b> (${HOST}) — FALLÓ (exit ${STATUS}) tras ${DURATION}s
<pre>${TAIL}</pre>" true
fi

exit "$STATUS"
