#!/bin/bash

# Configuración
NTFY_URL="https://ntfy.pollete.duckdns.org"
TOPIC="Kopia"
TITLE="Error en la copia de seguridad"
PRIORITY="high"

# Envía notificación a NTFY
curl -X POST "$NTFY_URL/$TOPIC" \
    -H "Title: $TITLE" \
    -H "Priority: $PRIORITY" \
    -d "$MESSAGE"
    
