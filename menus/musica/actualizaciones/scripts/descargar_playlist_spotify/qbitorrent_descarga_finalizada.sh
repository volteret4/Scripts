
#!/bin/bash
#
## Verificar que se recibieron los argumentos
if [ "$#" -ne 2 ]; then
    echo "Uso: $0 <ruta> <album>"
    exit 1
fi

ruta=$1
album=$2

# URL del endpoint
url="http://host.docker.internal:8584/download-complete"

# Enviar la solicitud POST con curl
response=$(curl -s -w "%{http_code}" -o /dev/null -X POST "$url" -H "Content-Type: application/json" -d "{\"album\": \"$album\", \"ruta\": \"$ruta\"}")

# Imprimir los datos enviados y el código de estado de la respuesta
echo "{\"album\": \"$album\", \"ruta\": \"$ruta\"}"
echo "Código de estado: $response"
