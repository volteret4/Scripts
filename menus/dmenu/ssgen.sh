#!/usr/bin/env bash
#
# Script Name: ssgen.sh 
# Description: _ _ _
# Author: volteret4
# Repository: 
# License: 

# Notes:
#
#



# where to save (or look for) the script
script_path="$HOME/.local/bin"

# the editor of your choice
script_editor="geany"

# check for argument (script name)

script_file="${script_path}/$1"

if [[ -z "$@" ]]; then
    echo -e "\n\nError!\nUsage: ssgen script_name\n\n"
    exit 0;
fi

# if script doesn't exist, create it

if [[ ! -f "${script_file}" ]]; then
    echo '#!/usr/bin/env bash' > "${script_file}"
    chmod +x "${script_file}"
fi

# open script with editor

eval $script_editor "${script_file}"

exit 0