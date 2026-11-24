#!/bin/bash

arg="${1}"
fecha="$(date +%d-%m-%Y_%H:%M)"

# Configurar DISPLAY y DBUS para que funcione desde cron
export DISPLAY=:0
export DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u)/bus"

# Obtener las notificaciones de GitHub usando gh
notifications=$(gh api -H "Accept: application/vnd.github+json" /notifications)

# Verificar si hay notificaciones
if echo "$notifications" | grep -q '"unread":true'; then
    # Contar notificaciones no leídas
    unread_count=$(echo "$notifications" | jq '[.[] | select(.unread == true)] | length')

    # Obtener detalles de la primera notificación no leída
    first_notification=$(echo "$notifications" | jq -r '[.[] | select(.unread == true)][0]')

    if [[ $arg =~ 'debug' ]]; then
        echo "Primera notificación: $first_notification"
    fi

    # Extraer información relevante
    title=$(echo "$first_notification" | jq -r '.subject.title')
    type=$(echo "$first_notification" | jq -r '.subject.type')
    repository=$(echo "$first_notification" | jq -r '.repository.full_name')
    reason=$(echo "$first_notification" | jq -r '.reason')
    repo_url=$(echo "$first_notification" | jq -r '.repository.html_url')

    # Construir mensaje con información adicional
    message="📌 $title"
    if [ "$unread_count" -gt 1 ]; then
        message="$message\n\n🔔 Tienes $unread_count notificaciones no leídas"
    fi
    message="$message\n\n💡 Tipo: $type | Razón: $reason"

    # Enviar la notificación (no bloqueante) y quedarnos con su ID
    if [ -n "$DISPLAY" ]; then
        notif_id=$(dunstify -p -u normal -t 15000 \
            "🐙 GitHub: $repository" \
            "$message" \
            -A "open,Abrir Notificaciones" \
            -A "default,Ver Repositorio" \
            -h string:category:github 2>/dev/null)

        # dunstify NUNCA informa qué acción se invocó (solo el motivo de
        # cierre con -w: expirada/descartada/cerrada), así que escuchamos
        # la señal real de D-Bus en segundo plano para saber en qué botón
        # se hizo click y actuar en consecuencia.
        (
            timeout 16 dbus-monitor --session \
                "type='signal',interface='org.freedesktop.Notifications',member='ActionInvoked'" 2>/dev/null \
            | gawk -v target="$notif_id" '
                /member=ActionInvoked/ { state = 1; next }
                state == 1 && /uint32/ {
                    gsub(/[^0-9]/, "", $0)
                    id = $0
                    state = 2
                    next
                }
                state == 2 && /string/ {
                    if (match($0, /"([^"]*)"/, arr) && id == target) {
                        print arr[1]
                        fflush()
                        exit
                    }
                    state = 0
                }
            ' \
            | { read -r action
                case "$action" in
                    open) xdg-open "https://github.com/notifications" ;;
                    default) xdg-open "$repo_url" ;;
                esac
              }
        ) &
    fi

    # Mostrar detalles en la terminal/log
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Nueva notificación: $fecha"
    echo "Título: $title"
    echo "Tipo: $type"
    echo "Repositorio: $repository"
    echo "Razón: $reason"
    echo "Total no leídas: $unread_count"
    echo "URL Repositorio: $repo_url"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
else
    echo "$fecha - No tienes notificaciones nuevas."
fi

if [[ $arg =~ 'debug' ]]; then
    echo "--- DEBUG INFO ---"
    echo "DISPLAY: $DISPLAY"
    echo "DBUS_SESSION_BUS_ADDRESS: $DBUS_SESSION_BUS_ADDRESS"
    echo "USER ID: $(id -u)"
    echo "Notificaciones completas:"
    echo "$notifications" | jq '.'
fi
