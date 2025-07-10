#!/usr/bin/env python
#
# Script Name: sp_playlist.py
# Description:  Actualiza archivo con listado de playlist actuales en spotify
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:

# Notes:
#   Dependencies:  - python3, spotyapi,
#                  - cuenta en spotify api
#

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import os
from pathlib import Path

# Cargar las variables de entorno desde el archivo .env
load_dotenv()
home_dir = os.environ["HOME"]

# Acceder a las variables de entorno.
CLIENT_ID = os.getenv('SPOTIFY_CLIENT')
CLIENT_SECRET = os.getenv('SPOTIFY_SECRET')
redirect_uri = os.getenv('SPOTIFY_REDIRECT')
scope = "playlist-read-private"
browser = False
script_dir = Path(__file__).parent.absolute()
project_root = script_dir.parent
cache_path = project_root / ".content/cache/token.txt"
playlist_path = project_root / ".content/cache/playlists.txt"
output_path = project_root / ".content/cache/playlists.md"

# Inicializa el cliente de autenticación
sp_oauth = SpotifyOAuth(CLIENT_ID, CLIENT_SECRET, redirect_uri, scope, browser, cache_path)

# Obtiene el token de acceso de la caché o solicita uno nuevo si no está en la caché o ha caducado
token_info = sp_oauth.get_cached_token()

# Si obtienes un token de acceso, inicializa el cliente de Spotify
if token_info:
    access_token = token_info['access_token']
    sp = spotipy.Spotify(auth=access_token)

    # Función para leer el archivo de texto
    def read_playlists(file_path):
        playlists = []
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for i in range(0, len(lines), 3):
                name = lines[i].strip().replace('Nombre: ', '')
                id_ = lines[i+1].strip().replace('ID: ', '')
                playlists.append((name, id_))
        return playlists

    # Función para obtener la descripción de una playlist
    def get_playlist_description(playlist_id):
        playlist = sp.playlist(playlist_id)
        return playlist['description'], playlist['external_urls']['spotify']

    # Función para escribir el archivo Markdown
    def write_markdown(file_path, playlists):
        with open(file_path, 'w', encoding='utf-8') as f:
            for name, id_ in playlists:
                description, url = get_playlist_description(id_)
                if description:
                    descripcion = description[3:]
                    f.write(f"[{name}]({url}) {descripcion}\n\n")
                else:
                    f.write(f"[{name}]({url})\n\n")

    # Leer playlists del archivo de entrada
    playlists = read_playlists(playlist_path)

    # Escribir las playlists en el archivo de salida en formato Markdown
    write_markdown(output_path, playlists)

# Actualiza el token de acceso si es necesario
if sp_oauth.is_token_expired(token_info):
    token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
    access_token = token_info['access_token']
    sp = spotipy.Spotify(auth=access_token)

    # Guarda el nuevo token en la caché
    sp_oauth._save_token_info(token_info)