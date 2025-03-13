#!/bin/bash

# Configuración de Telegram
BOT_TOKEN="tu_token_de_bot"
CHAT_ID="tu_chat_id"
LOG_FILE="/var/log/telegram-notify.log"

# Función para enviar mensajes a Telegram
send_telegram_message() {
    MESSAGE="$1"
    
    echo "Enviando mensaje a Telegram: $MESSAGE" >> $LOG_FILE
    
    curl -s -X POST "https://api.telegram.org/bot$BOT_TOKEN/sendMessage" \
         -d chat_id="$CHAT_ID" \
         -d text="$MESSAGE" \
         -d parse_mode="HTML" >> $LOG_FILE 2>&1
    
    if [ $? -eq 0 ]; then
        echo "Mensaje enviado correctamente" >> $LOG_FILE
    else
        echo "Error al enviar mensaje" >> $LOG_FILE
    fi
}

# Verificar si se proporcionó un mensaje
if [ -z "$1" ]; then
    echo "Uso: $0 \"Mensaje a enviar\"" >> $LOG_FILE
    exit 1
fi

# Enviar el mensaje
send_telegram_message "$1"