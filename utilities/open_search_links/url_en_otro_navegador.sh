#!/usr/bin/env bash
#
# Script Name: url_en_otro_navegador.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#
#

# Obtener el nombre de la ventana activa
window_name=$(xdotool getactivewindow getwindowname)

# Verificar si el nombre de la ventana activa corresponde a un navegador
if [[ "$window_name" == *"Mozilla Firefox"* ]]; then
    browser="firefox"
elif [[ "$window_name" == *"Chromium"* ]]; then
    browser="chromium"
else
    echo "La ventana activa no corresponde a un navegador."
    exit 1
fi

# Obtener la ID de la ventana activa y la ID de la pestaña activa
window_id=$(xdotool getactivewindow)
tab_id=$(xdotool search --onlyvisible --pid $(xdotool getwindowpid $window_id) --class "chromium|firefox" | tail -n1)

# Obtener la URL de la pestaña activa
if [[ "$tab_id" != "" ]]; then
    # Simular la pulsación de teclas para seleccionar la barra de direcciones y copiar su contenido
    xdotool windowfocus $tab_id
    sleep 0.1
    xdotool key "ctrl+l"
    xdotool key "ctrl+c"

    # Obtener el contenido del portapapeles y asignarlo a la variable url
    url=$(xclip -o)
else
    echo "No se encontró ninguna pestaña activa."
    exit 1
fi

# Abrir la URL en el otro navegador
if [[ "$browser" == "firefox" ]]; then
    other_browser="chromium"
else
    other_browser="firefox"
fi

if [[ "$other_browser" == "firefox" ]]; then
    firefox "$url" &
else
	chromium "$url" &
fi
