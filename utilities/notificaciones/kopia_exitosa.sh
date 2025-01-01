#!/bin/bash

# Configuración
NTFY_URL="https://ntfy.pollete.duckdns.org"
TOPIC="Kopia"
TITLE="Exito en la copia de seguridad"
PRIORITY="low"

# Envía notificación a NTFY
curl -X POST "$NTFY_URL/$TOPIC" \
    -H "Title: $TITLE" \
    -H "Priority: $PRIORITY" \
    -d "$MESSAGE"
    
