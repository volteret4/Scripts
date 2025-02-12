#!/bin/bash

API_KEY="jJU3XqsLUakUaixMXC4ikfrFxMtWKLsY"
FOLDER_ID="johxm-xegyy"
HOST="http://127.0.0.1:8384"

# Iniciar Obsidian
obsidian &

# Pausar la carpeta en Syncthing
sleep 60
syncthing cli config folders "$FOLDER_ID" paused set true
syncthing cli restart
echo "Carpeta $FOLDER_ID pausada."


# Esperar a que Obsidian termine
while pgrep -f "/usr/lib/obsidian/app.asar" >/dev/null; do
    sleep 60
done

# Reanudar la carpeta en Syncthing
syncthing cli config folders "$FOLDER_ID" paused set false
syncthing cli restart
echo "Carpeta $FOLDER_ID reanudada."
