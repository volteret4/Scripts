#!/usr/bin/env python
#
# Script Name: sync_todo_caldav.py 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:
#
#



#!/usr/bin/env python3

import subprocess
import re

# Rutas de los archivos
caldav = "/mnt/Datos/FTP/Wiki/todotxt/todo/t_caldav.txt"
todo_done = "/mnt/Datos/FTP/Wiki/todotxt/todo/t_todo.txt"

# Comando para obtener la lista desde CalDAV (reemplaza esto con tu comando real)
comando_caldav = "todo list"

# Ejecutar el comando y redirigir la salida al archivo caldav.txt
with open(caldav, 'w') as caldav_file:
    subprocess.run(comando_caldav, stdout=caldav_file, shell=True)

# Leer el contenido de CalDAV
with open(caldav, 'r') as caldav_file:
    lineas_caldav = caldav_file.readlines()

# Leer el contenido de todo_done
with open(todo_done, 'r') as todo_done_file:
    lineas_todo = todo_done_file.readlines()

# Inicializar contador
coincidencias = 0

# Iterar sobre las líneas de todo_done y buscar títulos en CalDAV
for linea_todo in lineas_todo:
    # Extraer título utilizando una expresión regular
    match = re.search(r'(\S+)', linea_todo)
    if match:
        titulo_todo = match.group(1).strip()

        # Buscar el título en las líneas de CalDAV
        for linea_caldav in lineas_caldav:
            if titulo_todo in linea_caldav:
                # Incrementar contador de coincidencias
                coincidencias += 1

                # Imprimir mensaje de coincidencia
                print(f"Coincidencia en la línea de CalDAV: {linea_caldav.strip()}")
                print(f"Título: {titulo_todo}")

                # Formatear el comando
                comando_todo = ["todo", "new", f"{titulo_todo}"]
                subprocess.run(comando_todo)
                print(f"Se envió el comando: {comando_todo}")

# Imprimir recuento final
print(f"\nRecuento final:\nCoincidencias: {coincidencias}")