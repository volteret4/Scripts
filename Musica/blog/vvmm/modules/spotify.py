#!/usr/bin/env python3
#
# Script Name: spotify.py
# Description: Obtener link de spotify para el album pasado como argumento.
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:

# Notes:
#   Dependencies:   - python3, requests, dotenv
#                   - .env file
#
#   Requiere dos argumentos artista y album
#
#!/usr/bin/env python3

import requests
import sys
import os
from pathlib import Path
import subprocess
import json
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# Cargar las variables de entorno desde el archivo .env
load_dotenv()
home_dir = os.environ["HOME"]

# Definir las rutas
script_dir = Path(__file__).parent.absolute()
project_root = script_dir.parent
cache_path = project_root / ".content/cache/token.txt"
token_script = script_dir / "sp_playlist.py"


def renovar_token():
    """Ejecuta el script de renovación de token"""
    try:
        print("Renovando token...", file=sys.stderr)
        resultado = subprocess.run(['python3', token_script], capture_output=True, text=True)
        if resultado.returncode == 0:
            return True
        return False
    except Exception as e:
        print(f"Error al ejecutar el script de renovación: {e}", file=sys.stderr)
        return False

def configurar_spotify(intentar_renovar=True):
    """Configura y retorna el cliente de Spotify usando el token existente"""
    CLIENT_ID = os.getenv('SPOTIFY_CLIENT')
    CLIENT_SECRET = os.getenv('SPOTIFY_SECRET')
    redirect_uri = 'http://127.0.0.1:8090'
    scope = "playlist-read-private playlist-read-collaborative"

    sp_oauth = SpotifyOAuth(
        CLIENT_ID, 
        CLIENT_SECRET, 
        redirect_uri, 
        scope=scope, 
        open_browser=False, 
        cache_path=cache_path
    )

    token_info = sp_oauth.get_cached_token()
    
    if not token_info and intentar_renovar:
        if renovar_token():
            return configurar_spotify(intentar_renovar=False)
        sys.exit(1)
    
    if not token_info:
        sys.exit(1)

    try:
        sp = spotipy.Spotify(auth=token_info['access_token'])
        sp.current_user()  # Verificar si el token es válido
        return sp
    except Exception as e:
        if intentar_renovar:
            if renovar_token():
                return configurar_spotify(intentar_renovar=False)
        sys.exit(1)

def buscar_album(sp, artista, album):
    """Busca un álbum específico y retorna su URL"""
    try:
        query = f"artist:{artista} album:{album}"
        resultados = sp.search(query, type='album', limit=1)
        
        if resultados['albums']['items']:
            return resultados['albums']['items'][0]['external_urls']['spotify']
        return None
        
    except Exception as e:
        if "token" in str(e).lower():
            sp = configurar_spotify()
            return buscar_album(sp, artista, album)
        return None

def main():
    # Verificar argumentos
    if len(sys.argv) != 3:
        print("Uso: python spotify.py <artista> <álbum>", file=sys.stderr)
        sys.exit(1)

    artist_name = sys.argv[1]
    album_name = sys.argv[2]

    # Configurar cliente de Spotify con soporte para renovación de token
    sp = configurar_spotify()

    # Buscar el álbum
    album_url = buscar_album(sp, artist_name, album_name)
    
    # Solo imprimir la URL si se encuentra (sin mensajes adicionales)
    if album_url:
        print(album_url)

if __name__ == "__main__":
    main()