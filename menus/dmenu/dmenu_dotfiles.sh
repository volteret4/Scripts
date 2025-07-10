#!/usr/bin/env bash
#
# Script Name: dmenu_dotfiles.sh 
# Description: 
#   1. Buscar con dmenu archivos de configuracion localizados en $dot_path 
#   2. Editarlos con helix en una nueva ventana de tmux
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 

#   
# Notes:
#   Dependencies:
#       helix
#       tmux
#



# important! requires 'ssgen' script

dot_path="$HOME/.dotfiles/"
ssgen_path="$HOME/Scripts/menus/dmenu"

# list only executable non-binay files

list="$(fd . "${dot_path}" -t f \
    | sed "s|.*/||" \
    | sort
)"


# output list to dmenu

#__1__ select="$(dmenu $prompt $font $colors $lines <<< $list)"
select="$(dmenu -l -i -p 'Elige dotfile: ' <<< "${list}")"
file="$(basename ${select})"
path="$(fd "$select" "$dot_path" | sed 's/^\.//' )" #path del script seleccionado
file="$(basename ${select})"

# Verificar si hay sesiones activas
if ! tmux ls &>/dev/null; then
    kitty -e sh -c 'byobu -f ~/.byobu/.tmux.conf' &
    sleep 0.5  # Esperar un poco para que tmux se inicie
fi

# Esperar a que tmux esté disponible y obtener la primera sesión
for i in {1..5}; do
    tmux_sesion="$(tmux list-sessions 2>/dev/null | awk 'NR==1 {print $1}' | sed 's/://')"
    if [[ -n $tmux_sesion ]]; then
        break
    fi
    sleep 1
done

#tmux_sesion="$(tmux list-sessions | awk 'NR==1 {print $1}' | sed 's/://')"

comando="helix ${path}"


#__2__ run 'ssgen' with the selected file name

if [[ -n "${select}" ]]; then
    eval "tmux attach -t $tmux_session ; tmux new-window -n $file"
    tmux send-keys  "$comando" C-m
fi  

exit 0;
