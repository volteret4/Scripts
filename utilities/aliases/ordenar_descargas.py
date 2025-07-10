#!/usr/bin/env python
#
# Script Name: ordenar_descargas.py 
# Description: order 
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:
#
#

import os
import shutil
import datetime



folder = '${HOME}/Descargas' # CHANGE!! 

# Obtener la lista de files en la carpeta
files = os.listdir(folder)

# Recorrer la lista de files y copiarlos a la carpeta "antiguas"
for archivo in files:
    ruta_archivo = os.path.join(folder, archivo)
    if os.path.isfile(ruta_archivo):
        # Obtener la fecha de creación del archivo
        fecha_creacion = os.path.getctime(ruta_archivo)
        anio = datetime.datetime.fromtimestamp(fecha_creacion).strftime('%Y')
        mes = datetime.datetime.fromtimestamp(fecha_creacion).strftime('%m')

        # Calcular la fecha actual y la fecha límite de exclusión
        fecha_actual = datetime.datetime.now()
        fecha_limite = fecha_actual - datetime.timedelta(days=60)

        # Si el archivo se creó antes de la fecha límite, copiarlo a la carpeta "antiguas"
        if fecha_creacion < fecha_limite.timestamp():
            # Crear la carpeta "antiguas/año" si no existe
            folder_antiguas = os.path.join(folder, "antiguas", anio)
            if not os.path.exists(folder_antiguas):
                os.makedirs(folder_antiguas)

            # Copiar el archivo a la carpeta "antiguas/año"
            shutil.copy(ruta_archivo, folder_antiguas)

            # Separar el archivo en una subcarpeta según su extensión
            extension = os.path.splitext(ruta_archivo)[1][1:]
            folder_extension = os.path.join(folder_antiguas, extension)
            if not os.path.exists(folder_extension):
                os.makedirs(folder_extension)
            shutil.move(ruta_archivo, os.path.join(folder_extension, archivo))
