import sys
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import os
from pathlib import Path

# Cargar las variables de entorno desde el archivo .env
load_dotenv()

# Acceder a las variables de entorno
CLIENT_ID = os.getenv('SPOTIFY_CLIENT')
CLIENT_SECRET = os.getenv('SPOTIFY_SECRET')
redirect_uri = os.getenv('SPOTIFY_REDIRECT')
scope = "playlist-modify-public playlist-modify-private"  # Incluye scopes necesarios para modificar playlists
script_dir = Path(__file__).parent.absolute()
project_root = script_dir.parent
cache_path = project_root / ".content/cache/token_crear.txt"

# Verifica que se hayan pasado el ID de la canción y el ID de la playlist como argumentos
if len(sys.argv) < 3:
    print("Uso: añadir_cancion.py <track_id> <playlist_id>")
    sys.exit(1)

track_id = sys.argv[1]
playlist_id = sys.argv[2]

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

# Verifica si el token ha expirado y lo actualiza si es necesario
if not token_info or sp_oauth.is_token_expired(token_info):
    try:
        if token_info:
            token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
        else:
            auth_url = sp_oauth.get_authorize_url()
            print(f"Visita la siguiente URL para autorizar la aplicación:\n{auth_url}")
            code = input("Ingresa el código que recibiste después de autorizar: ")
            token_info = sp_oauth.get_access_token(code)
    except Exception as e:
        print(f"Error al obtener o refrescar el token de acceso: {e}")
        sys.exit(1)

# Inicializa el cliente de Spotify con el token de acceso
access_token = token_info['access_token']
sp = spotipy.Spotify(auth=access_token)

try:
    # Añadir la canción a la playlist
    sp.playlist_add_items(playlist_id, [track_id])
    print(f"Canción con ID '{track_id}' añadida a la playlist con ID '{playlist_id}' con éxito.")
    print(f"https://open.spotify.com/playlist/{playlist_id}")
except spotipy.exceptions.SpotifyException as e:
    print(f"Error al añadir la canción a la playlist: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Ha ocurrido un error inesperado: {e}")
    sys.exit(1)1