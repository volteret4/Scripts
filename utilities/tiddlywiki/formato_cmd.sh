#!/usr/bin/env bash
#
# Script Name: formato_cmd.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#
#



texto=$(cat <<EOF
Este es un ejemplo de texto que contiene comandos:

sudo apt update
$ apt upgrade

y aquí hay más texto.
EOF
)

regex_comando="^\s*\\$\ |^sudo\ "

# Reemplazar los caracteres de retorno de carro por saltos de línea
texto=$(echo "$texto" | tr '\r' '\n')

# Separar el texto en líneas y buscar las que contienen comandos
while read -r linea; do
    if [[ $linea =~ $regex_comando ]]; then
        # Si la línea contiene un comando, agregar delimitadores de código
        echo -e "\n\`\`\` \n $linea \n \`\`\`"
    else
        echo "$linea" >> ""
    fi
done <<< "$texto"