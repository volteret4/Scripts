#!/usr/bin/env python3
#
# Script Name: discogs.py
# Description: Obtener info de discogs para el album pasado como argumento.
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:

# Notes:
#   Dependencies:   - python3, requests, dotenv
#                   - api accout discogs
#
import requests
import sys
import subprocess
from dotenv import load_dotenv
import os
from pathlib import Path

# Cargar las variables de entorno desde el archivo .env
load_dotenv()
home_dir = os.environ["HOME"]

# Acceder a las variables de entorno
TOKEN = os.getenv('DISCOGS_TOKEN')
# Define la URL base de la API de Discogs y tu TOKEN de autenticación
BASE_URL = "https://api.discogs.com"


def get_master_release_id(artist_name, album_name):

    # Construye la URL para buscar el álbum por artista y nombre de álbum
    search_url = f"{BASE_URL}/database/search?q={artist_name} {album_name}&type=master&token={TOKEN}"

    try:
        # Realiza la solicitud GET a la API de Discogs
        response = requests.get(search_url)
        response.raise_for_status()  # Lanza una excepción si hay un error en la solicitud

        # Analiza la respuesta JSON
        data = response.json()

        # Comprueba si se encontraron resultados
        if data['pagination']['items'] == 0:
#            print("No se encontraron resultados para el álbum especificado.")
            return None

        # Obtiene el ID del master release del primer resultado
        master_release_id = data['results'][0]['id']

        return master_release_id

    except requests.exceptions.RequestException as e:
        print("Error al hacer la solicitud a la API de Discogs:", e)
        return None


def get_artist_id(artist_name):
    search_url = f"{BASE_URL}/database/search?q={artist_name}&type=artist&token={TOKEN}"
    try:
        response = requests.get(search_url)
        response.raise_for_status()
        data = response.json()
        if data['pagination']['items'] > 0:
            return data['results'][0]['id'], None  # Retorna (artist_id, None) cuando encuentra el artista
        else:
            return None, f"No se encontró ningún artista con el nombre '{artist_name}'."
    except requests.exceptions.RequestException as e:
        return None, f"Error al hacer la solicitud a la API de Discogs: {e}"

def save_artist_releases(artist_name, output_path):
    artist_id, error_message = get_artist_id(artist_name)
    if artist_id is None:
        print(error_message)
        return
    
    page = 1
    releases = []
    while True:
        releases_url = f"{BASE_URL}/artists/{artist_id}/releases?token={TOKEN}&page={page}&per_page=100"
        try:
            response = requests.get(releases_url)
            response.raise_for_status()
            data = response.json()
            if 'releases' in data:
                releases.extend(data['releases'])
                if len(data['releases']) < 99:  # If less than 100 releases, this is the last page
                    break
                page += 1
            else:
                break
        except requests.exceptions.RequestException as e:
            print("Error al hacer la solicitud a la API de Discogs:", e)
            break

    # Guarda los releases del artista en el archivo especificado
    with open(output_path, "w") as file:
        file.write("Listado de releases del artista:\n")
        for release in releases:
            title = release.get('title', 'Desconocido')
            year = release.get('year', 'Desconocido')
            resource_url = release.get('resource_url', 'Desconocido')
            file.write(f"{title} - {year} - {resource_url}\n")


if __name__ == "__main__":
    # Verifica que se pasen los argumentos correctos
    if len(sys.argv) != 3:
        print("Uso: python discogs_api.py <artista> <álbum>")
        sys.exit(1)

    # Obtén los argumentos del artista y el álbum de la línea de comandos
    artist_name = sys.argv[1]
    album_name = sys.argv[2]
    output_path = "/mnt/NFS/blogs/vvmm/releases.txt"
    # Obtiene el ID del master release del álbum especificado
    master_release_id = get_master_release_id(artist_name, album_name)

    if master_release_id:
        print(master_release_id)
        save_artist_releases(artist_name, output_path)
    else:
        save_artist_releases(artist_name, output_path)
        print("bash_script")
#        subprocess.run(["./releases_discogs.sh", album_name])