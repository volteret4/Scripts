#!/bin/bash

# Verificar que los programas necesarios estén instalados
for cmd in xclip qrencode notify-send display; do
    if ! command -v $cmd &> /dev/null; then
        echo "Error: $cmd no está instalado. Por favor instálalo primero."
        echo "Puedes usar: sudo pacman -S xclip qrencode libnotify-bin imagemagick"
        exit 1
    fi
done

# Crear directorio temporal si no existe
TEMP_DIR="$HOME/.qr_temp"
mkdir -p "$TEMP_DIR"

# Obtener la fecha y hora actual para crear un nombre de archivo único
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
QR_FILE="$TEMP_DIR/qr_$TIMESTAMP.png"

# Copiar contenido del portapapeles
CLIPBOARD_CONTENT=$(xclip -selection clipboard -o)

if [ -z "$CLIPBOARD_CONTENT" ]; then
    notify-send "Error" "El portapapeles está vacío" --icon=dialog-error
    exit 1
fi

# Generar código QR
qrencode -o "$QR_FILE" "$CLIPBOARD_CONTENT"

if [ ! -f "$QR_FILE" ]; then
    notify-send "Error" "No se pudo generar el código QR" --icon=dialog-error
    exit 1
fi

# Mostrar notificación
notify-send "QR Generado" "Código QR creado para: ${CLIPBOARD_CONTENT:0:50}..." --icon="$QR_FILE"

# Mostrar la imagen
display "$QR_FILE" &

echo "QR creado en: $QR_FILE"