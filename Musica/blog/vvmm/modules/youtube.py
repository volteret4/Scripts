#!/usr/bin/env python3
#
# Script Name: youtube.py
# Description: Obtener link de playlist de youtube para el album pasado como argumento.
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:

# Notes:
#   Dependencies:   - python3, requests, dotenv
#                   - .env file
#
from googleapiclient.discovery import build
import sys
from dotenv import load_dotenv
import os

# Cargar las variables de entorno desde el archivo .env
load_dotenv()

# Acceder a las variables de entorno
YT_TOKEN = os.getenv('YT_TOKEN')

def buscar_playlist(artist, album, YT_TOKEN):
    youtube = build('youtube', 'v3', developerKey=YT_TOKEN)

    # Realizar la búsqueda de videos relacionados con el artista y el álbum
    search_response = youtube.search().list(
        q=f'{artist} {album} playlist',
        part='id',
        maxResults=5
    ).execute()

    # Obtener el ID de la playlist si se encuentra
    for item in search_response['items']:
        if item['id']['kind'] == 'youtube#playlist':
            playlist_id = item['id']['playlistId']
            return f'https://www.youtube.com/playlist?list={playlist_id}'

    return None

# Ejemplo de uso
if __name__ == "__main__":
    artist = sys.argv[1]
    album = sys.argv[2]

    url_playlist = buscar_playlist(artist, album, YT_TOKEN)
    if url_playlist:
        print(url_playlist)
#    else:
#      print("No se encontró ninguna playlist.")
