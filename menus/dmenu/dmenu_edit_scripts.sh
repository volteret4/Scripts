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

list="$(find "${script_path}" -type f -executable \
    -exec grep -Iq . {} \; -print \
    | sed 's|^'"${script_path}"/'||' \
    | sort \
    )"

# output list to dmenu

#select="$(dmenu $prompt $font $colors $lines <<< $list)"
select="$(dmenu -l -i -p 'Edita Script: ' <<< "${list}")"
file="$(basename ${select})"

tmux_sesion="$(tmux list-sessions | awk 'NR==1 {print $1}' | sed 's/://')"

comando="helix  ${script_path}/${select}"


# run 'ssgen' with the selected file name

if [[ -n "${select}" ]]; then
    eval "tmux attach -t $tmux_session ; tmux new-window -n $file"
    tmux send-keys  "$comando" C-m
fi

exit 0;
