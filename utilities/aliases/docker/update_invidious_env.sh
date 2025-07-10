# Ejecutar el contenedor y capturar la salida
OUTPUT=$(docker run quay.io/invidious/youtube-trusted-session-generator)

# Extraer los valores usando grep y sed o awk
VISITOR_DATA=$(echo "$OUTPUT" | grep 'visitor_data:' | sed 's/.*visitor_data: *//')
PO_TOKEN=$(echo "$OUTPUT" | grep 'po_token:' | sed 's/.*po_token: *//')

# Verifica que se hayan extraído correctamente
if [[ -z "$VISITOR_DATA" || -z "$PO_TOKEN" ]]; then
    echo "Error: No se pudieron extraer los datos correctamente."
    exit 1
fi

# hmac
hmac="$(openssl rand -base64 21)"

# Guardarlos en un archivo .env
cat <<EOF > "$HOME"/contenedores/invidious/.env
VISITOR_DATA=$VISITOR_DATA
PO_TOKEN=$PO_TOKEN
HMAC=$hmac
EOF

echo ".env generado correctamente:"
cat .env
