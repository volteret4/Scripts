#!/usr/bin/env bash
#
# Script Name: sync_todo_caldav.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:    Requiere a caldav server (radicale?)
#
#



# Rutas de los archivos
caldav="/mnt/Datos/FTP/Wiki/todotxt/todo/t_caldav.txt"
todo_done="/mnt/Datos/FTP/Wiki/todotxt/todo/t_done.txt"

# Comando para obtener la lista desde CalDAV (reemplaza esto con tu comando real)
comando_caldav="todo list"

# Ejecutar el comando y redirigir la salida al archivo caldav.txt
$comando_caldav > $caldav

# Inicializar contador
coincidencias=0

# Iterar sobre las líneas de todo_done y buscar títulos en CalDAV
while IFS= read -r linea_todo_done; do
    # Eliminar la fecha del inicio de la línea
    titulo_todo=$(echo "$linea_todo_done" | sed -E 's/^[0-9]{4}-[0-9]{2}-[0-9]{2} (.*)/\1/')
    echo "1. tt: $titulo_todo"
    # Eliminar desde el primer @ hasta el final de la línea
    titulo_todo=$(echo "$titulo_todo" | sed -E 's/@.*$//')
    echo "2. tt: ${titulo_todo}"
    # Buscar el título en las líneas de CalDAV
    while IFS= read -r linea_caldav; do
        if [[ $linea_caldav == *"$titulo_todo"* ]]; then
            # Incrementar contador de coincidencias
            coincidencias=$((coincidencias + 1))

            # Imprimir mensaje de coincidencia
            echo "Coincidencia en la línea de CalDAV: $linea_caldav"
            echo "Título: $titulo_todo"

            # Formatear el comando
            comando_todo=("todo" "new" "$titulo_todo")
            # "${comando_todo[@]}"
            echo "Se envió el comando: ${comando_todo[@]}"
        fi
    done < "$caldav"
done < "$todo_done"

# Imprimir recuento final
echo -e "\nRecuento final:\nCoincidencias: $coincidencias"