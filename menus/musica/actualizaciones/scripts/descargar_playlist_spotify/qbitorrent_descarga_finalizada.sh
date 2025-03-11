#!/bin/bash
# Verificar que se recibieron los argumentos
if [ "$#" -ne 2 ]; then
    echo "Uso: $0 <ruta> <album>"
    exit 1
fi

ruta=$1
album=$2
timestamp=$(date "+%Y-%m-%d %H:%M:%S")
logfile="/config/qbitorrent_scripts.log"


# Test simple de conectividad - agregar al inicio del script
echo "[$timestamp] Verificando conectividad con el servidor..." >> $logfile
ping_test=$(ping -c 1 host.docker.internal 2>&1)
echo "[$timestamp] Resultado ping: $ping_test" >> $logfile

curl_test=$(curl -s -o /dev/null -w "%{http_code}" "http://host.docker.internal:8584/status" 2>&1)
echo "[$timestamp] Test de endpoint /status: $curl_test" >> $logfile

# Script para notificar a un servidor Python cuando qBittorrent termina una descarga


# URL del servidor Python en el host
url="http://host.docker.internal:8584/download-complete"

# Datos a enviar
payload="{\"album\": \"$album\", \"ruta\": \"$ruta\"}"

echo "[$timestamp] Enviando notificación: $payload" >> $logfile

# Capturar la respuesta completa de curl
full_response=$(curl -v -X POST "$url" \
  -H "Content-Type: application/json" \
  -d "$payload" 2>&1)

status_code=$?

# Guardar la respuesta en el log
echo "[$timestamp] Respuesta de curl (status: $status_code):" >> $logfile
echo "$full_response" >> $logfile
echo "----------------------------------------" >> $logfile

# También mostrar en la consola para depuración
echo "Payload enviado: $payload"
echo "Código de estado de curl: $status_code"
echo "Para ver detalles completos, revisa: $logfile"

exit 0