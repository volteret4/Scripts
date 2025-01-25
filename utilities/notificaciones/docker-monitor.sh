#!/bin/bash

# Cargar token y chat_id desde .env
source /home/huan/Scripts/utilities/notificaciones/.env

# Función simple para enviar mensaje a Telegram
send_telegram() {
    curl -s "https://api.telegram.org/bot$TOKEN/sendMessage" \
        -d "chat_id=$CHAT_ID" \
        -d "text=$1"
}

echo "Iniciando monitoreo de Docker..."

# Monitorear eventos de Docker
docker events --filter 'type=container' --format '{{.Action}} {{.Actor.Attributes.name}}' | while read event container; do
    case "$event" in
        "start")
            send_telegram "🟢 Contenedor $container iniciado en Arco"
            notify-send "$contaniner iniciado"
            ;;
        "die")
            send_telegram "🔴 Contenedor $container detenido inesperadamente en Arco"
            notify-send -u critical "$container detenido de repronto"
            ;;
        "stop")
            send_telegram "🔴 Contenedor $container detenido en Arco"
            notify-send -u critical "$container detenido"
            ;;
    esac
done

