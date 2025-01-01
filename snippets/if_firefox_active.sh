#!/usr/bin/env bash
#
# Script Name: if_firefox_active.sh 
# Description: Herramienta usada por otros scripts para comprobar si la ventana activa es una de los navegadores activos.
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO:   AConfigurar playerctl y mpc.  
# Notes:
#requisitos="xdotool deadbeef firefox|floorp|chromium|'thorium browser'"
#
#

# # Comprueba OS
# apt="$(which apt)"
# pacman="$(which pacman)"
# if [[ -z $pacman ]];then
#     pm=apt
# elif [[ -z apt ]];then
#     pm=error
# elif [[ -n $pacman ]];then
#     pm=pacman
# fi

# #  Comprueba requisitos

# # Dividir la cadena de requisitos en un array basado en espacios
# IFS=' ' read -ra REQUISITOS <<< "$requisitos"

# # Iterar sobre cada requisito
# for requisito in "${REQUISITOS[@]}"; do
#     # Verificar si el requisito contiene '|', lo que indica una elección entre varias aplicaciones
#     if [[ $requisito == *'|'* ]]; then
#         # Dividir el requisito en partes usando '|' como separador
#         IFS='|' read -ra OPCIONES <<< "$requisito"
        
#         for opcion in "${OPCIONES[@]}"; do
#              ((intentos++))
#             app_instalada="$(which $opcion)"
#             if [[ -z $app_instalada ]] ;then
#                 echo ""
#                 echo "No tienes $opcion instalado, seguiremos buscando...($intentos de 5)"
#             else
#                 echo ""
#                 echo "$opcion instalada en $app_instalada"
#             fi
#         done
#     else
#         app_instalada="$(which $requisito)"
#         if [[ -z $app_instalada ]] ;then
#             echo ""
#             echo "No tienes $requisito instalado, prueba con $instalar"
#         else
#             echo ""
#             echo "$requisito instalad en $app_instalada"
#         fi
#     fi
# done



busqueda="$(xclip -o)"

applic="$(xdotool getactivewindow getwindowname)"
app="$(echo $applic | awk -F/ '{print $NF}')"
#export "${app?}"
firefox="Mozilla Firefox$"
chromium="Chromium$"
qutebrowser="qutebrowser$"
thorium="Thorium$"
floorp="Floorp$"

deadbeef="DeaDBeeF"
strawberry=""

# Obtener el nombre de la ventana activa
active_window_id=$(xdotool getactivewindow)
active_window_name=$(xdotool getwindowname "$active_window_id")
#export strawberry="$(xdotool getactivewindow getwindowclassname)"

# if [[ ${app} =~ ${firefox}|${chromium}|${floorp}|${thorium} ]]; then
#         wid=$(xdotool search --name "${app}")
#         xdotool windowfocus --sync "${wid}"
#         xdotool key --window "${wid}" ctrl+l
#         xdotool key --window "${wid}" ctrl+c
#         xdotool key --clearmodifiers  --window "${wid}" Escape
# if [[ ${app} =~ ${firefox} ]]; then
#         wid=$(xdotool search --name "Mozilla Firefox$")
#         xdotool windowfocus --sync "${wid}"
#         xdotool key --window "${wid}" ctrl+l
#         xdotool key --window "${wid}" ctrl+c
#         xdotool key --clearmodifiers  --window "${wid}" Escape
#     elif [[ ${app} =~ ${chromium} ]]; then
#         wid=$(xdotool search --name "\- Chromium$")
#         xdotool windowfocus --sync "${wid}"
#         xdotool key --window "${wid}" ctrl+l
#         xdotool key --window "${wid}" ctrl+c
#         #sleep 0.1
#         xdotool key --clearmodifiers --window "${wid}" Escape
#     elif [[ ${app} =~ ${floorp} ]]; then
#         echo "floorp es la acitva"
#         wid=$(xdotool search --name "Floorp$")
#         xdotool windowfocus --sync "${wid}"
#         xdotool key --window "${wid}" ctrl+l
#         xdotool key --window "${wid}" ctrl+c
#         xdotool key --clearmodifiers --window "${wid}" Escape
#     elif [[ ${app} =~ ${thorium} ]]; then
#         wid=$(xdotool search --name "Thorium$")
#         xdotool windowfocus "${wid}"
#         xdotool key --window "${wid}" ctrl+l
#         xdotool key --window "${wid}" ctrl+c
#         xdotool key --clearmodifiers  --window "${wid}" Escape

# Define una lista de aplicaciones y sus nombres de ventana
declare -A browser
browser=(
    ["firefox"]="Mozilla Firefox$"
    ["chromium"]="\\- Chromium$"
    ["floorp"]="Floorp$"
    ["thorium"]="Thorium$"
)

# Itera sobre las aplicaciones
for browser_name in "${!browser[@]}"; do
    if [[ "$active_window_name" =~ ${browser[$browser_name]} ]]; then
        echo "App name: $browser_name"
        # Utilizar el ID de la ventana activa directamente
        wid=$active_window_id
        if [[ -n "$wid" ]]; then
            xdotool windowfocus --sync "${wid}"
            sleep 0.2
            xdotool key --window "${wid}" ctrl+l
            xdotool key --window "${wid}" ctrl+c
            xdotool key --clearmodifiers Escape
        else
            echo "No se encontró la ventana para ${browser_name}"
        fi
        break
    fi
done

if [[ ${app} =~ ${qutebrowser} ]]; then
    echo "qutebrowser es la que esta activa wtf"
    wid=$(xdotool search --name ${qutebrowser})
    xdotool windowfocus --sync "${wid}" 
    xdotool key --window "${wid}" key y
    xdotool key --window "${wid}" key y
elif [[ ${app} =~ ${deadbeef} ]]; then
    # wid=$(xdotool search --name "DeaDBeeF$")
    # xdotool windowfocus --sync "${wid}"
    musica="$(deadbeef --now-playing-tf "%artist - %title (%year - %album)")"
elif [[ ${app} =~ 'strawberry' ]]; then
    #pendiente de corregir
    artista=$(playerctl -p strawberry  metadata xesam:albumArtist)
    cancion=$(playerctl -p strawberry  metadata title)
    album=$(playerctl -p strawberry  metadata album)
    date=$(playerctl -p strawberry  metadata date)
    musica="${artista} - ${cancion} (${date} - ${album})"
else
    echo "other"
fi


# debug time
url="$(xclip -o)"


if [[ -z $musica ]]; then
        echo "${app} ${url}"
        #notify-send -t 100000 "app $app \n url $url"
else
        echo "${app} - $musica"
fi
