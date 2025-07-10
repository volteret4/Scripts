#!/usr/bin/env python
#
# Script Name: musicbrainz.py
# Description: Obtener link de musicbrainz del album poasado como argumento.
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# TODO: intentarlo con la api
# Notes:
#   Dependencies:   - python3 con los paquetes: requests
#

import requests
import sys

def buscar_album(artist, album):
    # URL base de la API de MusicBrainz
    base_url = "https://musicbrainz.org/ws/2/"
    # Parámetros de búsqueda
    params = {
        "query": f'artist:"{artist}" AND release:"{album}"',
        "fmt": "json"
    }
    # Realizar la solicitud GET a la API
    response = requests.get(base_url + "release/", params=params)
    # Verificar si la solicitud fue exitosa
    if response.status_code == 200:
        # Obtener el resultado en formato JSON
        result = response.json()
        # Verificar si se encontraron resultados
        if "releases" in result and len(result["releases"]) > 0:
            # Obtener el ID del primer álbum encontrado
            album_id = result["releases"][0]["id"]
            # Construir la URL del álbum
            album_url = f"https://musicbrainz.org/release/{album_id}"
            return album_url
    return None

# Ejemplo de uso
if __name__ == "__main__":
    artist = sys.argv[1]
    album = sys.argv[2]

    url_album = buscar_album(artist, album)
    if url_album:
        print(url_album)
#    else:
#        print("No se encontró el álbum.")
