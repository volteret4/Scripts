#!/bin/bash

# CONFIGURACIÓN GLOBAL

INTERFAZ_WAKE="wakeonlan"
ESPERA=60

MAC_PROXMOX="74:56:3C:5D:E6:1D"
DEBIAN_MAC="30:65:ec:a8:9b:37"

# Configuración de ntfy
NTFY_URL="https://ntfy.pollete.duckdns.org"
NTFY_TOPIC="Kopia"
notificar() {
    local mensaje="$1"
    curl -s -d "$mensaje" "$NTFY_URL/$NTFY_TOPIC" >/dev/null
}


$INTERFAZ_WAKE $MAC_PROXMOX
$INTERFAZ_WAKE $DEBIAN_MAC

notificar "Kopia iniciada"