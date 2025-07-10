#!/usr/bin/env python3
#
# Script Name: info_master_discogs.py
# Description: Obtener información de Discogs para el MASTERID del álbum pasado como argumento.
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:

# Notes:
#   Dependencies: python3, requests
#

import json
import requests
import sys

def obtener_datos_master_discogs(master_id):
    # URL de la API de Discogs para obtener información de un master por su ID
    url = f'https://api.discogs.com/masters/{master_id}'
    
    # Realizar la solicitud GET a la API de Discogs
    response = requests.get(url)
    
    # Verificar si la solicitud fue exitosa (código de estado 200)
    if response.status_code == 200:
        # Devolver los datos del master en formato JSON
        return response.json()
    else:
        # Si la solicitud no fue exitosa, imprimir el mensaje de error y devolver None
        print(f"Error al obtener datos del master (Código de estado: {response.status_code})")
        return None

# Obtener el ID del master como argumento de la línea de comandos
master_id = sys.argv[1]
output_file_path = sys.argv[2]

# Obtener los datos del master de Discogs
master_data = obtener_datos_master_discogs(master_id)

# Verificar si se obtuvieron los datos del master correctamente
if master_data:
    # Abrir el archivo en modo de agregado y escribir los datos
    with open(output_file_path, 'a') as output_file:
        # Ejemplo de cómo acceder a ciertos campos del JSON del master
        title = master_data['title']
        year = master_data['year']
        genres = ', '.join(master_data['genres'])
        
        # Escribir los datos en el archivo de salida
        output_file.write(f"**Título:** {title}\n\n")
        output_file.write(f"**Año:** {year}\n\n")
        output_file.write(f"**Géneros:** {genres}\n\n")
        
        # Puedes continuar extrayendo más datos según sea necesario
        
        # Añadir un salto de línea al final para mantener el formato en el archivo .md final
        output_file.write("\n\n")
else:
    print("No se pudieron obtener los datos del master de Discogs.")