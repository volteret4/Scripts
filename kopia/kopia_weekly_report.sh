#!/usr/bin/env bash
#
# Script Name: kopia_weekly_report.sh
# Description: Comprueba, para cada fuente de snapshot_arcolinux.sh, si hubo
#              un snapshot en cada uno de los últimos 7 días y manda un
#              resumen por Telegram (qué días hubo backup y cuáles no).
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.encrypted.env"

eval "$(sops --decrypt "$ENV_FILE")"

send_telegram() {
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d chat_id="${TELEGRAM_CHAT_ID}" \
        -d parse_mode="HTML" \
        --data-urlencode "text=$1" >/dev/null
}

# Necesitamos leer el repo (en el lxc-docker dentro de proxmox) para poder
# comprobar qué días hubo snapshot. Si no lo despertamos aquí, un proxmox
# apagado haría que todos los días salieran como ❌ por error de lectura,
# no porque falten backups de verdad.
"$SCRIPT_DIR/wake_proxmox.sh" >/dev/null 2>&1
KOPIA_REPO_HOST="192.168.1.89"
KOPIA_REPO_PORT=51515
repo_ready=0
for i in $(seq 1 30); do
    nc -z -w3 "$KOPIA_REPO_HOST" "$KOPIA_REPO_PORT" 2>/dev/null && { repo_ready=1; break; }
    sleep 10
done
if [ "$repo_ready" -ne 1 ]; then
    send_telegram "⚠️ <b>Resumen semanal Kopia</b> ($(uname -n))
No se pudo contactar con el repo ($KOPIA_REPO_HOST:$KOPIA_REPO_PORT) para generar el resumen."
    exit 1
fi

SOURCES=(
    "$HOME/.local/share/chezmoi"
    "$HOME/Scripts"
    "$HOME/.cache/kopia-untracked-staging/pollo"
    "/etc/fstab"
    "/etc/ssh/sshd_config"
)

DAYS=7
TODAY_EPOCH=$(date -d "today 00:00:00" +%s)

MSG="📦 <b>Resumen semanal Kopia</b> ($(uname -n))
"

any_missing=0
for src in "${SOURCES[@]}"; do
    label="$src"
    [ "$src" = "$HOME/.local/share/chezmoi" ] && label="chezmoi"
    [ "$src" = "$HOME/Scripts" ] && label="Scripts"
    [ "$src" = "$HOME/.cache/kopia-untracked-staging/pollo" ] && label="pollo (untracked)"

    days_line=""
    for ((d = DAYS - 1; d >= 0; d--)); do
        day_start=$((TODAY_EPOCH - d * 86400))
        day_end=$((day_start + 86400))
        day_label=$(date -d "@$day_start" +%d/%m)

        count=$(kopia snapshot list "$src" --json 2>/dev/null \
            | jq --argjson start "$day_start" --argjson end "$day_end" \
                '[.[] | (.startTime | sub("\\..*Z$"; "Z") | fromdateiso8601) as $t | select($t >= $start and $t < $end)] | length' 2>/dev/null)
        count="${count:-0}"

        if [ "$count" -gt 0 ]; then
            days_line+="${day_label}:✅ "
        else
            days_line+="${day_label}:❌ "
            any_missing=1
        fi
    done

    MSG+="
<b>${label}</b>
${days_line}"
done

if [ "$any_missing" -eq 1 ]; then
    MSG+="

⚠️ Hay días sin snapshot en al menos una fuente."
else
    MSG+="

✅ Todos los días con backup en todas las fuentes."
fi

send_telegram "$MSG"
