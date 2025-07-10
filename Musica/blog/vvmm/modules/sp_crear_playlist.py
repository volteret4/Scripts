import sys
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import os
import json
from pathlib import Path

# Cargar las variables de entorno desde el archivo .env
load_dotenv()

# Acceder a las variables de entorno
CLIENT_ID = os.getenv('SPOTIFY_CLIENT')
CLIENT_SECRET = os.getenv('SPOTIFY_SECRET')
redirect_uri = os.getenv('SPOTIFY_REDIRECT')
scope = "playlist-modify-public"  # Scope correcto para crear playlists públicas
script_dir = Path(__file__).parent.absolute()
project_root = script_dir.parent
cache_path = project_root / ".content/cache/token_crear.txt"

# Verificación de las variables de entorno
if not CLIENT_ID or not CLIENT_SECRET:
    print("Error: Las variables de entorno SPOTIFY_CLIENT y SPOTIFY_SECRET deben estar configuradas.")
    sys.exit(1)

# Inicializa el cliente de autenticación
sp_oauth = SpotifyOAuth(client_id=CLIENT_ID,
                        client_secret=CLIENT_SECRET,
                        redirect_uri=REDIRECT_URI,
                        scope=scope,
                        cache_path=cache_path,
                        open_browser=False)

# Obtiene el token de acceso de la caché o solicita uno nuevo si no está en la caché o ha caducado
token_info = sp_oauth.get_cached_token()

if not token_info:
    auth_url = sp_oauth.get_authorize_url()
    print(f"Por favor, abre la siguiente URL en tu navegador para autenticarte: {auth_url}")
    
    # Espera a que el usuario ingrese el código de autorización
    response = input("Pega el código de autorización aquí: ")
    
    # Intercambia el código de autorización por un token de acceso
    token_info = sp_oauth.get_cached_token(response)
    
    # Guarda el token de acceso en un archivo
    with open(cache_path, 'w') as token_file:
        json.dump(token_info, token_file)

if token_info:
    access_token = token_info['access_token']
    sp = spotipy.Spotify(auth=access_token)
else:
    print("Error: No se pudo obtener un token de acceso.")
    sys.exit(1)

# Verifica que se haya pasado el nombre de la playlist como argumento
if len(sys.argv) < 2:
    print("Uso: crear_playlist.py <nombre_playlist>")
    sys.exit()

playlist_name = sys.argv[1]

try:
    # Obtén el usuario actual
    user_id = sp.me()['id']

    # Crea la nueva playlist
    new_playlist = sp.user_playlist_create(user=user_id, name=playlist_name, public=True)
    playlist_url = new_playlist['external_urls']['spotify']
#    print(f"Playlist '{new_playlist['name']}' creada con éxito.")
    print(playlist_url)
except spotipy.exceptions.SpotifyException as e:
    print(f"Error al crear la playlist: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Ha ocurrido un error inesperado: {e}")
    sys.exit(1)
