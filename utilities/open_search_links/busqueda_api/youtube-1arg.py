#!/usr/bin/env python3
#
# Script Name: youtube-1arg.py
# Description: Buscar video o playlist en YouTube API con el nombre del artista + disco
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:

# Notes:
#   Dependencies:   - python3, requests, dotenv
#                   - YouTube API key
#
import requests
import sys
import os
from dotenv import load_dotenv
import urllib.parse

# Cargar las variables de entorno desde el archivo .env
load_dotenv()

# Acceder a las variables de entorno
API_KEY = os.getenv('YOUTUBE_API_KEY')
BASE_URL = "https://www.googleapis.com/youtube/v3"

def search_youtube(query, max_results=1):
    """
    Busca en YouTube usando la API v3
    """
    search_url = f"{BASE_URL}/search"

    params = {
        'part': 'snippet',
        'q': query,
        'key': API_KEY,
        'maxResults': max_results,
        'type': 'video,playlist',
        'order': 'relevance'
    }

    try:
        response = requests.get(search_url, params=params)
        response.raise_for_status()

        data = response.json()

        if 'items' in data and len(data['items']) > 0:
            first_result = data['items'][0]

            # Determinar si es video o playlist
            if first_result['id']['kind'] == 'youtube#video':
                video_id = first_result['id']['videoId']
                url = f"https://www.youtube.com/watch?v={video_id}"
            elif first_result['id']['kind'] == 'youtube#playlist':
                playlist_id = first_result['id']['playlistId']
                url = f"https://www.youtube.com/playlist?list={playlist_id}"
            else:
                return None

            return url
        else:
            return None

    except requests.exceptions.RequestException as e:
        print(f"Error al hacer la solicitud a la API de YouTube: {e}", file=sys.stderr)
        return None
    except KeyError as e:
        print(f"Error al procesar la respuesta de la API: {e}", file=sys.stderr)
        return None

def main():
    if len(sys.argv) < 2:
        print("Uso: python youtube-1arg.py <artista-disco>", file=sys.stderr)
        sys.exit(1)

    # Verificar que existe la API key
    if not API_KEY:
        print("Error: No se encontró YOUTUBE_API_KEY en las variables de entorno", file=sys.stderr)
        sys.exit(1)

    # El argumento viene con guiones, convertir a espacios para la búsqueda
    search_query = sys.argv[1].replace('-', ' ')

    # Buscar en YouTube
    result_url = search_youtube(search_query)

    if result_url:
        print(result_url)
    else:
        # Si no se encuentra nada, no imprimir nada (el script bash manejará esto)
        pass

if __name__ == "__main__":
    main()
