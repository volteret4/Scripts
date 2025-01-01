#!/bin/bash


arg="${1}"
fecha="$(date +%d-%m-%Y_%H:%m)"

# Obtener las notificaciones de GitHub usando gh
notifications=$(gh api -H "Accept: application/vnd.github+json" /notifications)

# Verificar si hay notificaciones
if echo "$notifications" | grep -q '"unread":true'; then
    # Obtener el ID de la primera notificación no leída
    notification_id=$(echo "$notifications" | jq -r '.[] | select(.unread == true) | .id' | head -n 1)

    # Obtener detalles de la notificación
    notification_details=$(gh api -H "Accept: application/vnd.github+json" /notifications/$notification_id)
    if [[ $arg =~ 'debug' ]]; then
        echo "N $notification_details"
    fi
    
    # Extraer información relevante
    title=$(echo "$notification_details" | jq -r '.subject.title')
    url=$(echo "$notification_details" | jq -r '.subject.url')
    repository=$(echo "$notification_details" | jq -r '.repository.full_name')

    # Enviar la notificación
    dunstify -u normal -t 10000 "GitHub Notification" "$title" \
    -A "open,Open GitHub Notifications" -h string:category:github

    # Mostrar detalles en la terminal
    echo "Nueva notificación: $fecha"
    echo "Título: $title"
    echo "URL: $url"
    echo "Repositorio: $repository"
else
    echo "$fecha No tienes notificaciones nuevas."
fi

if [[ $arg =~ 'debug' ]]; then
    echo "TAIL cron_log.txt"
    tail "$HOME/cron_log.txt"
fi
