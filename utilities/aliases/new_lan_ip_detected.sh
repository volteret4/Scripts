#!/usr/bin/env bash

NETWORK="192.168.1.0/24"
KNOWN_FILE="$HOME/.known_hosts_nmap.txt"
TMP_FILE="/tmp/nmap_scan.txt"

# Escaneo rápido
nmap -sn -T5 "$NETWORK" -oG "$TMP_FILE" >/dev/null

# Extraer solo IPs vivas
grep "Up" "$TMP_FILE" | awk '{print $2}' | sort -u > "$TMP_FILE.sorted"

# Si no existe archivo previo, crearlo
if [[ ! -f "$KNOWN_FILE" ]]; then
    cp "$TMP_FILE.sorted" "$KNOWN_FILE"
    echo "Inicializado listado de hosts conocidos."
    exit 0
fi

echo "📡 Nuevos hosts detectados:"
comm -13 "$KNOWN_FILE" "$TMP_FILE.sorted"

# Actualizar lista
cp "$TMP_FILE.sorted" "$KNOWN_FILE"
