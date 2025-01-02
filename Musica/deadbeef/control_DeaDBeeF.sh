
#!/usr/bin/env bash
#
# Script Name: control_DeaDBeeF.sh
# Description: Controlar la reproducción
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# TODO: 
# Notes:
#   Dependencies: 
#

comando="${1}"

ventana_activa="$(xdotool getactivewindow getwindowclassname)"
id_activa="$(xdotool search --classname $ventana_activa)"
echo $ventana_activa
echo $id_activa

if [[ $ventana_activa =~ 'Deadbeef' ]]; then
    if [[ -z $comando ]]; then
        echo "Falta comando. Uso correcto: bash $0 next|prev|toggle"
    elif [[ $comando =~ next ]]; then
        deadbeef --next
    elif [[ $comando =~ prev ]]; then
        deadbeef --previous
    elif [[ $comando =~ toggle ]]; then
        deadbeef --toggle-pause
    # elif [[ $comando =~ seekf ]]; then
    #     deadbeef --to
    # elif [[ $comando =~ next ]]; then
    #     deadbeef
    fi
elif [[ -z $ventana_activa ]]; then
    echo "No se ha detectado classname de la ventana activa. Fallo de xdotool"
else
    if [[ $comando =~ next ]]; then
        xdotool windowfocus --sync $id_activa
        xdotool key --window $id_activa "F8"
    elif [[ $comando =~ prev ]]; then
        xdotool windowfocus --sync $id_activa
        xdotool key --window $id_activa "F7"
    elif [[ $comando =~ toggle ]]; then
        xdotool windowfocus --sync $id_activa
        xdotool key --window $id_activa F5
    # elif [[ $comando =~ seekf ]]; then
    #     deadbeef --to
    # elif [[ $comando =~ next ]]; then
    #     deadbeef
    fi
fi



    mpc toggle") end),
     "echo 'cycle pause' | socat - /tmp/mpvsocket" ) end,
    "mpc next") end),
    ("echo playlist-next | socat - /tmp/mpvsocket") end,
    mpc prev") end),
    echo playlist-prev | socat - /tmp/mpvsocket" ) end,
    mpc stop") end),
    echo stop | socat - /tmp/mpvsocket" ) end,
    
