#!/usr/bin/env python3
#
# Script Name: info_releases_discogs.py
# Description: Obtener info de discogs para el MASTERID del album pasado como argumento.
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:

# Notes:
#   Dependencies: python3, requests
#   Requiere 2 argumentos, release_id y nombre del archivo de salida
#       ejemplo de release id: 31065680 de https://www.discogs.com/release/31065680-Somos-La-Herencia-Dolo
#

import json
import requests
import sys
import os 
from pathlib import Path

home_dir = os.environ["HOME"]
script_dir = Path(__file__).parent.absolute()
file_info = script_dir / "discogs_info_extra.txt"

# https://www.discogs.com/release/12950315-Folamour-Ordinary-Drugs   test me!!

def obtener_datos_release_discogs(release_id):
    # URL de la API de Discogs para obtener información de un release por su ID
    url = f'https://api.discogs.com/releases/{release_id}'
    
    # Realizar la solicitud GET a la API de Discogs
    response = requests.get(url)
    
    # Verificar si la solicitud fue exitosa (código de estado 200)
    if response.status_code == 200:
        # Devolver los datos del release en formato JSON
        return response.json()
    else:
        # Si la solicitud no fue exitosa, imprimir el mensaje de error y devolver None
        print(f"Error al obtener datos del release (Código de estado: {response.status_code})")
        return None

# Obtener el ID del release como argumento de la línea de comandos o cualquier otra fuente
release_id = sys.argv[1]
#output_file_path = sys.argv[2]
# Obtener los datos del release de Discogs
release_data = obtener_datos_release_discogs(release_id)

# Verificar si se obtuvieron los datos del release correctamente
if release_data:
    # Abrir el archivo en modo de agregado y escribir los datos
    with open(file_info, 'w') as output_file:
        # Obtener datos que pueden estar repetidos
        country = release_data.get('country')
        if country:
            output_file.write(f"**Pais:** {country}\n\n")
            
        # Check if community rating exists
        if 'community' in release_data and 'rating' in release_data['community']:
            rating = release_data['community']['rating'].get('average')
            count = release_data['community']['rating'].get('count')
            if rating:
                output_file.write(f"**Votos:** Media de {rating} con {count} votos\n\n")

        # Check if labels exist
        if 'labels' in release_data and len(release_data['labels']) > 0:
            label = release_data['labels'][0].get('name')
            if label:
                output_file.write(f"**Sello:** {label}\n\n")
        
        # Obtener datos de companies (etiquetas) - check if exists
        if 'companies' in release_data:
            companies = release_data['companies']
            num_companies = len(companies)
            for i in range(num_companies):
                label_type = companies[i].get('entity_type_name')
                label_name = companies[i].get('name')
                if label_name:
                    output_file.write(f"**{label_type}:** {label_name}\n\n")

        # Obtener datos de extraartists - check if exists first
        if 'extraartists' in release_data:
            extra_artists = release_data['extraartists']
            num_extra_artists = len(extra_artists)
            for i in range(num_extra_artists):
                extra_artist_name = extra_artists[i].get('name')
                extra_artist_role = extra_artists[i].get('role')
                if extra_artist_name:
                    # Extraer el primer nombre y el rol del colaborador
                    output_file.write(f"**{extra_artist_role}** - {extra_artist_name}\n\n")
        
        # añade un ultimo salto de linea para mantener formato en el .md final
        output_file.write("\n\n")
else:
    print("No se pudieron obtener los datos del release de Discogs.")