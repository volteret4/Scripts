#!/usr/bin/env bash
#
# Script Name: dmenu_dotfiles.sh 
# Description: 
#   1. Buscar con dmenu archivos de configuracion localizados en $dot_path 
#   2. Editarlos con helix en una nueva ventana de tmux
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
#   - Change "find" for a faster option
#   - Change helix to "$editor"
# Notes:
#   Dependencies:
#       helix
#       tmux
#



# important! requires 'ssgen' script

dot_path="$HOME/.dotfiles/"
ssgen_path="$HOME/Scripts/menus/dmenu"

# list only executable non-binay files

list="$(find "${dot_path}" -type f \
    -exec grep -Iq . {} \; -print \
    | sed 's|^'"${dot_path}"/'||' \
    | sort \
    )"

# output list to dmenu

#__1__ select="$(dmenu $prompt $font $colors $lines <<< $list)"
select="$(dmenu -l -i -p 'Elige dotfile: ' <<< "${list}")"
file="$(basename ${select})"

tmux_sesion="$(tmux list-sessions | awk 'NR==1 {print $1}' | sed 's/://')"

comando="helix  ${select}"


#__2__ run 'ssgen' with the selected file name

if [[ -n "${select}" ]]; then
    eval "tmux attach -t $tmux_session ; tmux new-window -n $file"
    tmux send-keys  "$comando" C-m
fi  

exit 0;
