#!/usr/bin/env bash
#
# Script Name: crear_tiddler.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:
#
#



# Comprobar si la ventana activa pertenece a uno de estos navegadores.

var=$(xdotool getactivewindow getwindowname)
firefox="Mozilla Firefox$"
chromium="\- Chromium$"
thorium="Thorium$"
# En dicho caso copiar URL al portapapeles.

if [[ $var =~ $firefox ]]
    then
                wid=$(xdotool search --name "Mozilla Firefox$")
                xdotool windowfocus $wid
                sleep 0.2
                xdotool key ctrl+l
                xdotool key ctrl+c
                xdotool key Escape
    elif [[ $var =~ $chromium ]]
        then
                wid=$(xdotool search --name "\- Chromium$")
                xdotool windowfocus $wid
                sleep 0.2
                xdotool key ctrl+l
                xdotool key ctrl+c
                xdotool key Escape
    elif [[ $var =~ $thorium ]]
        then
                wid=$(xdotool search --name "\- Chromium$")
                xdotool windowfocus $wid
                sleep 0.2
                xdotool key ctrl+l
                xdotool key ctrl+c
                xdotool key Escape
fi

# Crear Variable con URL y borrar portapapeles.

url=$(copyq read 0)
printf $(copyq read 0)
copyq remove 0
sleep 0.5

# Crear nuevas variables para título y contenido.

titulo=$(copyq read 1)
content=$(copyq read 0 )

# Dar formato correcto al tiddler.

titulo=$(sed 's/ /%20/g' <<< $titulo)

contenido="<<<
${url}
<<<
${content}"

printf "TITULO: $titulo\nCONTENIDO\n${contenido}"

# Elegir TAG.

tag=$(zenity --info --title "tw"\
    --text "¿En donde quieres guardar el tiddler? T: $titulo C: $contenido"\
    --extra-button "Linux"\
    --extra-button "AHK"\
    --extra-button "Docker"\
    --extra-button "Tasker"\
    --extra-button "Raspberry"\
    --extra-button "Tiddlywiki"\
    --extra-button "Vim"\
    --extra-button "NixOS"\
    --extra-button "ArchLinux"\
    --ok-label "paso"\
)

# Enviar nuevo elemento a Tiddlywiki

curl -X PUT -i "http://192.168.1.166:8080/recipes/default/tiddlers/$titulo" -H "X-Requested-With: TiddlyWiki" --data "$(jq -nc --arg tags "$tag" --arg text "${contenido}" '{ $tags, $text }')"
