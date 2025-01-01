#!/usr/bin/env bash
#
# Script Name: dmenu_edit_scripts.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
#   Change helix for "$editor"
# Notes:
#   Dependencies:
#       ssgen
#       helix
#       tmux
#



# important! requires 'ssgen' script

script_path="$HOME/Scripts"                 # CHANGE!!
ssgen_path="$HOME/Scripts/menus/dmenu"      # CHANGE!!

# dmenu theming
#. $HOME/.local/bin/dmenu-theming

#prompt="-p Script:"

# list only executable non-binay files

list="$(fd . "${script_path}" -t x \
    | sed "s|.*/||" \
    | sort
)"

# output list to dmenu

#select="$(dmenu $prompt $font $colors $lines <<< $list)"
select="$(dmenu -l -i -p 'Edita Script: ' <<< "${list}")"
path="$(fd "$select" "$script_path" | sed 's/^\.//' )" #path del script seleccionado
file="$(basename ${select})"

# Verificar si hay sesiones activas
if ! tmux ls &>/dev/null; then
    kitty -e sh -c 'byobu -f ~/.byobu/.tmux.conf' &
    #sleep 2  # Esperar un poco para que tmux se inicie
fi

# Esperar a que tmux esté disponible y obtener la primera sesión
for i in {1..5}; do
    tmux_sesion="$(tmux list-sessions 2>/dev/null | awk 'NR==1 {print $1}' | sed 's/://')"
    if [[ -n $tmux_sesion ]]; then
        break
    fi
    sleep 0.2
done

#tmux_sesion="$(tmux list-sessions | awk 'NR==1 {print $1}' | sed 's/://')"

#notify-send "t-sess $tmux_sesion ."
comando="helix ${path}"


# run 'ssgen' with the selected file name

if [[ -n "${select}" ]]; then
    eval "tmux attach -t $tmux_sesion ; tmux new-window -n $file"
    tmux send-keys  "$comando" C-m
fi

exit 0;
