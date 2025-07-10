#!/usr/bin/env python

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import os
import requests
import sys
from pathlib import Path
import argparse
import subprocess

# Cargar las variables de entorno desde el archivo .env
load_dotenv()
home_dir = os.environ["HOME"]

# Definir las rutas
script_dir = Path(__file__).parent.absolute()
project_root = script_dir.parent
cache_path = project_root / ".content/cache/token.txt"
token_script = script_dir / "sp_playlist.py"

# Crear el directorio de portadas si no existe
#Path(covers_dir).mkdir(parents=True, exist_ok=True)

def renovar_token():
    """Ejecuta el script de renovación de token"""
    try:
        print("Renovando token...")
        resultado = subprocess.run(['python3', token_script], capture_output=True, text=True)
        if resultado.returncode == 0:
            print("Token renovado exitosamente")
            return True
        else:
            print("Error al renovar el token:")
            print(resultado.stderr)
            return False
    except Exception as e:
        print(f"Error al ejecutar el script de renovación: {e}")
        return False

def configurar_spotify(intentar_renovar=True):
    """Configura y retorna el cliente de Spotify usando el token existente"""
    CLIENT_ID = os.getenv('SPOTIFY_CLIENT')
    CLIENT_SECRET = os.getenv('SPOTIFY_SECRET')
    redirect_uri = os.getenv('SPOTIFY_REDIRECT')
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
        # Si no hay token válido, intentar renovarlo
        if renovar_token():
            # Intentar obtener el token nuevamente después de la renovación
            return configurar_spotify(intentar_renovar=False)
        else:
            print("No se pudo renovar el token")
            sys.exit(1)

    if not token_info:
        print("No se encontró un token válido")
        sys.exit(1)

    try:
        sp = spotipy.Spotify(auth=token_info['access_token'])
        # Verificar si el token es válido haciendo una petición de prueba
        sp.current_user()  # Esta llamada fallará si el token no es válido
        return sp
    except Exception as e:
        if intentar_renovar:
            print("Token expirado o inválido. Intentando renovar...")
            if renovar_token():
                # Intentar nuevamente con el token renovado
                return configurar_spotify(intentar_renovar=False)
        print("Error al configurar Spotify:", e)
        sys.exit(1)

def buscar_album(sp, artista, album):
    """Busca un álbum específico y retorna su información"""
    try:
        query = f"artist:{artista} album:{album}"
        resultados = sp.search(query, type='album', limit=1)

        if not resultados['albums']['items']:
            print(f"Error: No se encontró el álbum '{album}' de '{artista}'")
            return None

        return resultados['albums']['items'][0]
    except Exception as e:
        print(f"Error al buscar el álbum: {e}")
        # Si el error es por token inválido, intentar renovar
        if "token" in str(e).lower():
            print("Intentando renovar el token y repetir la búsqueda...")
            sp = configurar_spotify()
            return buscar_album(sp, artista, album)
        return None

def descargar_portada(url, artista, album):
    """Descarga la portada del álbum"""
    nombre_archivo = f"{artista}-_-{album}".replace(' ', '-')
    nombre_archivo = "".join(c for c in nombre_archivo if c.isalnum() or c in ('_', '-')).rstrip()
    #ruta_archivo = os.path.join(covers_dir, f"{nombre_archivo}.jpg")
    ruta_archivo = os.path.join("/mnt", "NFS", "blogs", "vvmm", "static", "portadas", f"{nombre_archivo}.jpg")

    response = requests.get(url)
    if response.status_code == 200:
        with open(ruta_archivo, 'wb') as f:
            f.write(response.content)
        print(ruta_archivo)
        return ruta_archivo
    else:
        print(f"Error caratula: Al descargar la portada: {response.status_code}")
        return None

def main():
    # Configurar argumentos de línea de comandos
    parser = argparse.ArgumentParser(description='Descarga la portada de un álbum de Spotify')
    parser.add_argument('artista', help='Nombre del artista')
    parser.add_argument('album', help='Nombre del álbum')
    args = parser.parse_args()

    # Configurar cliente de Spotify con soporte para renovación de token
    sp = configurar_spotify()

    # Buscar el álbum
    album_info = buscar_album(sp, args.artista, args.album)
    if album_info and album_info['images']:
        imagen_url = album_info['images'][0]['url']
        descargar_portada(imagen_url, args.artista, args.album)
    elif album_info:
        print("Error caratula: El álbum no tiene portada disponible")

if __name__ == "__main__":
    main()
