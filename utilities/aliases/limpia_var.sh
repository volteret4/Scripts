
#!/usr/bin/env bash
#
# Script Name: limpia_var.sh
# Description: sanea string eliminando todos los carácteres no alfanuméricos.
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# TODO: 
# Notes:
#   Dependencies: python3, requests
#
sanitize_string() {
    local input="$1"
    # Eliminar puntos, guiones y guiones bajos
    sanitized=$(echo "$input" | sed 's/&/and/g' | tr -cd '[:alnum:]- ')
    echo "$sanitized"
}

sanitized_artist_name=$(sanitize_string "$1")

echo "$sanitized_artist_name"