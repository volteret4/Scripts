#!/bin/bash

# Usamos 'set -a' para que todas las variables definidas en el env se exporten automáticamente
set -a
eval "$(sops --decrypt .encrypted.env)"
set +a

# Configuración de Telegram
BOT_TOKEN="$TELEGRAM_BOT_TOKEN"
CHAT_ID="$TELEGRAM_CHAT_ID"
LOG_FILE="/var/log/telegram-notify.log"

# Función para enviar mensajes a Telegram
send_telegram_message() {
    MESSAGE="📜 Arco: $1"

    curl -s -X POST "https://api.telegram.org/bot$BOT_TOKEN/sendMessage" \
         -d chat_id="$CHAT_ID" \
         -d text="$MESSAGE" \
         -d parse_mode="HTML"

    notify-send "Telegram Notification" "$MESSAGE"
    # if [ $? -eq 0 ]; then
    #     echo "Mensaje enviado correctamente: $1" >> $LOG_FILE
    # else
    #     echo "Error al enviar mensaje: $1" >> $LOG_FILE
    # fi
}

# Verificar si se proporcionó un mensaje
if [ -z "$1" ]; then
    echo "Uso: $0 \"Mensaje a enviar\"" >> $LOG_FILE
    exit 1
fi

# Enviar el mensaje
send_telegram_message "$1"
