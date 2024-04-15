#!/usr/bin/env python
#
# Script Name: formato_cmd.py 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#
#



#!/user/bin/env python

import re


texto = """
Este es un ejemplo de texto que contiene comandos:

sudo apt update
apt upgrade

y aquí hay más texto.
"""

# Definir la expresión regular para buscar las líneas con comandos
regex_comando = r"^\s*((sudo\s+)?\S+|-\w\s+\S+)\s*$"

# Separar el texto en líneas y buscar las que contienen comandos
lineas = texto.split("\n")
nuevo_texto = ""
for i in range(len(lineas)):
    if re.search(regex_comando, lineas[i]):
        # Si la línea contiene un comando, agregar delimitadores de código
        nuevo_texto += "```\n" + lineas[i] + "\n```\n"
    else:
        nuevo_texto += lineas[i] + "\n"

print(nuevo_texto)