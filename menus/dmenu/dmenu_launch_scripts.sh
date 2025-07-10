#!/usr/bin/env bash
#
# Script Name: dmenu_launch_scripts.sh 
# Description:Buscar scripts localizados en $script_path con dmenu y lanzarlos en un terminal_
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 

#   - Change "fd" for a faster option.
#   - Change termite
# Notes:
#   Dependencies:
#       termite
#       dmenu
#       ssgen
#

# important! requires 'ssgen' script

script_path="$HOME/Scripts"                 # CHANGE!!
ssgen_path="$HOME/Scripts/menus/dmenu"      # CHANTE!!

# list only executable non-binay files

list="$(fd . "${script_path}" -t x \
    | sed "s|.*/||" \
    | sort
)"

# output list to dmenu

#select="$(dmenu $prompt $font $colors $lines <<< $list)"
select="$(dmenu -l -i -p 'Lanza Script: ' <<< "${list}")"

# run 'ssgen' with the selected file name

if [[ ! -z "${select}" ]]; then
    ruta="$(fd "${script_path}" -i "${select}")"
    eval "termite -e  ${script_path}/${select} --hold"
fi

exit 0;
