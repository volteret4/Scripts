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
scope = "playlist-read-private"  # Scope correcto para leer playlists privadas
script_dir = Path(__file__).parent.absolute()
project_root = script_dir.parent
cache_path = project_root / ".content/cache/token_private.txt"


# Verificación de las variables de entorno
if not CLIENT_ID or not CLIENT_SECRET:
    print("Error: Las variables de entorno SPOTIFY_CLIENT y SPOTIFY_SECRET deben estar configuradas.")
    sys.exit(1)

# Eliminar el archivo de caché si existe
if os.path.exists(cache_path):
    os.remove(cache_path)

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
    token_info = sp_oauth.get_access_token(response)
    
    # Guarda el token de acceso en un archivo
    with open(cache_path, 'w') as token_file:
        json.dump(token_info, token_file)

# Inicializa el cliente de Spotipy
access_token = token_info['access_token']
sp = spotipy.Spotify(auth=access_token)

# Verifica que se haya pasado el ID de la canción y el ID de la playlist como argumentos
if len(sys.argv) < 3:
    print("Uso: verificar_cancion_en_playlist.py <playlist_id> <track_id>")
    sys.exit()

playlist_id = sys.argv[1]
track_id = sys.argv[2]

# Obtener todas las canciones de la playlist
playlist_tracks = sp.playlist_tracks(playlist_id)

# Verificar si la canción está en la playlist
song_exists = False
for track in playlist_tracks['items']:
    if track['track']['id'] == track_id:
        song_exists = True
        break

if song_exists:
    print(f"La canción con ID '{track_id}' está añadida en la playlist con ID '{playlist_id}'.")
else:
    print(f"La canción con ID '{track_id}' no está añadida en la playlist con ID '{playlist_id}'.")

if song_exists:
    print("duplicado")
else:
    print("nota")