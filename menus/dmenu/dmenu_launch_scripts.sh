#!/usr/bin/env bash
#
# Script Name: dmenu_launch_scripts.sh 
# Description:Buscar scripts localizados en $script_path con dmenu y lanzarlos en un terminal_
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
#   - Change "find" for a faster option.
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

list="$(find "${script_path}" -type f -executable \
    -exec grep -Iq . {} \; -print \
    | sed 's|^'"${script_path}"/'||' \
    | sort \
    )"

# output list to dmenu

#select="$(dmenu $prompt $font $colors $lines <<< $list)"
select="$(dmenu -l -i -p 'Lanza Script: ' <<< "${list}")"

# run 'ssgen' with the selected file name

if [[ ! -z "${select}" ]]; then
    ruta="$(find "${script_path}" -iname "${select}")"
    eval "termite -e  ${script_path}/${select} --hold"
fi

exit 0;
