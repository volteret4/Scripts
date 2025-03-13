#!/bin/bash

# Configuración
DOMAIN="*.pollete.duckdns.org"  # Reemplaza con tu dominio
#EMAIL="frodobolson@disroot.org"  # Email para Let's Encrypt
#CERT_DIR="$HOME/scripts/.content/certificados"
LOG_FILE="$HOME/scripts/.content/logs/cron/letsencrypt-manual-renew.log"
TEMP_CERT_DIR="/tmp/npm-certs"
CONTAINER_NAME="nginx-proxy-manager-nginx-1"  # Nombre de tu contenedor

# Notificaciones
telegram_script="$HOME/scripts/utilidades/notificaciones/telegram/telegram_notify.sh"


# Fecha actual para el log
echo "== Proceso iniciado el $(date) ==" >> $LOG_FILE

# Crear directorio temporal si no existe
mkdir -p $TEMP_CERT_DIR

# 1. Buscar y extraer certificados actuales del contenedor
echo "Extrayendo certificados del contenedor $CONTAINER_NAME..." >> $LOG_FILE

# Determinar la ruta exacta dentro del contenedor (puede variar según la configuración)
CERT_PATH=$(docker exec $CONTAINER_NAME find /data/letsencrypt -name "$DOMAIN" | grep -v 'archive\|renewal' | head -1)

if [ -z "$CERT_PATH" ]; then
    echo "No se encontró el certificado para $DOMAIN en el contenedor" >> $LOG_FILE
    "$telegram_script" "❌ No se pudo encontrar el certificado para $DOMAIN en Nginx Proxy Manager"
    exit 1
fi

echo "Certificado encontrado en: $CERT_PATH" >> $LOG_FILE

# Extraer archivos de certificado
docker cp $CONTAINER_NAME:$CERT_PATH/fullchain.pem $TEMP_CERT_DIR/
docker cp $CONTAINER_NAME:$CERT_PATH/privkey.pem $TEMP_CERT_DIR/

if [ $? -ne 0 ]; then
    echo "Error al extraer los certificados" >> $LOG_FILE
    "$telegram_script" "❌ Error al extraer los certificados de $DOMAIN desde el contenedor"
    exit 1
fi

# 2. Renovar certificados usando certbot en modo standalone
echo "Renovando certificados para $DOMAIN..." >> $LOG_FILE

# Detener temporalmente el contenedor para liberar el puerto 80
docker stop $CONTAINER_NAME >> $LOG_FILE 2>&1

# Renovar certificado
certbot certonly --standalone --non-interactive --agree-tos --email your@email.com -d $DOMAIN >> $LOG_FILE 2>&1
RENEW_RESULT=$?

if [ $RENEW_RESULT -eq 0 ]; then
    echo "Certificados renovados exitosamente" >> $LOG_FILE
    
    # Copiar los nuevos certificados al directorio temporal
    cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem $TEMP_CERT_DIR/
    cp /etc/letsencrypt/live/$DOMAIN/privkey.pem $TEMP_CERT_DIR/
    
    # Obtener fecha de expiración del nuevo certificado
    EXPIRY_DATE=$(openssl x509 -in $TEMP_CERT_DIR/fullchain.pem -noout -enddate | cut -d= -f2)
    
    # 3. Copiar de vuelta al contenedor
    docker cp $TEMP_CERT_DIR/fullchain.pem $CONTAINER_NAME:$CERT_PATH/
    docker cp $TEMP_CERT_DIR/privkey.pem $CONTAINER_NAME:$CERT_PATH/
    
    if [ $? -eq 0 ]; then
        echo "Certificados copiados de vuelta al contenedor" >> $LOG_FILE
        /usr/local/bin/telegram-notify.sh "✅ Certificados para $DOMAIN renovados y actualizados en Nginx Proxy Manager. Expiran: $EXPIRY_DATE"
    else
        echo "Error al copiar los certificados al contenedor" >> $LOG_FILE
        /usr/local/bin/telegram-notify.sh "⚠️ Certificados renovados pero hubo un error al actualizarlos en el contenedor"
    fi
else
    echo "Error al renovar los certificados" >> $LOG_FILE
    /usr/local/bin/telegram-notify.sh "❌ Error al renovar los certificados para $DOMAIN"
fi

# Reiniciar el contenedor
docker start $CONTAINER_NAME >> $LOG_FILE 2>&1

# Limpiar archivos temporales
rm -rf $TEMP_CERT_DIR

echo "== Proceso finalizado el $(date) ==" >> $LOG_FILE
echo "" >> $LOG_FILE

