#!/usr/bin/env bash
#
# Script Name: wake_proxmox.sh
# Description: Envía WOL a proxmox con reintentos hasta confirmar que responde por SSH
#
set -uo pipefail

MAC_PROXMOX="74:56:3C:5D:E6:1D"
HOST_CHECK="192.168.1.222"
PORT_CHECK=2288
MAX_TRIES=45
SLEEP_BETWEEN=20

if nc -z -w3 "$HOST_CHECK" "$PORT_CHECK" 2>/dev/null; then
    echo "ALREADY_UP"
    exit 0
fi

for i in $(seq 1 "$MAX_TRIES"); do
    wakeonlan "$MAC_PROXMOX" >/dev/null
    if nc -z -w3 "$HOST_CHECK" "$PORT_CHECK" 2>/dev/null; then
        echo "WOKEN_BY_US tras intento $i ($((i * SLEEP_BETWEEN))s)"
        exit 0
    fi
    sleep "$SLEEP_BETWEEN"
done

echo "FAILED tras $MAX_TRIES intentos ($((MAX_TRIES * SLEEP_BETWEEN))s) de WOL"
exit 1
