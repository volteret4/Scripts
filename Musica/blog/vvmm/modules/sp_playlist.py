#!/usr/bin/env python3
#
# Script Name: sp_playlist.py
# Description: Actualizar archivo con nombre e id de playlists de spotify
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import os
import sys
from pathlib import Path

# Configuración de rutas
script_dir = Path(__file__).parent.absolute()
project_root = script_dir.parent

# Cargar variables de entorno
env_file = project_root / ".env"
if env_file.exists():
    load_dotenv(env_file)
else:
    print(f"Error: No se encontró .env en {env_file}", file=sys.stderr)
    sys.exit(1)

# Rutas estándar del proyecto
CACHE_DIR = project_root / ".content/cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Variables de entorno
CLIENT_ID = os.getenv('SPOTIFY_CLIENT')
CLIENT_SECRET = os.getenv('SPOTIFY_SECRET')
redirect_uri = os.getenv('SPOTIFY_REDIRECT')

# Verificar credenciales
if not CLIENT_ID or not CLIENT_SECRET:
    print("Error: SPOTIFY_CLIENT y SPOTIFY_SECRET deben estar configurados en .env", file=sys.stderr)
    print("Obtén las credenciales en: https://developer.spotify.com/dashboard/", file=sys.stderr)
    sys.exit(1)

# Scope para leer playlists privadas y colaborativas
scope = "playlist-read-private playlist-read-collaborative"

# Archivos de cache
cache_path = CACHE_DIR / "token.txt"
playlist_file = CACHE_DIR / "playlists.txt"

def validate_credentials():
    """Validar credenciales básicas antes de usar OAuth"""
    if len(CLIENT_ID) < 10 or len(CLIENT_SECRET) < 10:
        print("Error: Las credenciales de Spotify parecen inválidas", file=sys.stderr)
        print("Verifica SPOTIFY_CLIENT y SPOTIFY_SECRET en .env", file=sys.stderr)
        return False
    return True

def setup_spotify_oauth():
    """Configurar OAuth de Spotify con manejo de errores mejorado"""
    if not validate_credentials():
        return None

    try:
        sp_oauth = SpotifyOAuth(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            redirect_uri=redirect_uri,
            scope=scope,
            open_browser=False,
            cache_path=str(cache_path)
        )
        return sp_oauth
    except Exception as e:
        print(f"Error configurando OAuth: {e}", file=sys.stderr)
        return None

def get_valid_token(sp_oauth):
    """Intenta obtener o refrescar el token automáticamente; solo pide código si es estrictamente necesario."""
    token_info = None

    # 1. Intentar cargar desde caché
    token_info = sp_oauth.get_cached_token()

    # 2. Si el token existe pero expiró, sp_oauth.validate_token lo refresca automáticamente
    if token_info:
        if sp_oauth.is_token_expired(token_info):
            print("Refrescando token expirado automáticamente...")
            token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])

        if token_info:
            print("✅ Token válido (recuperado o refrescado).")
            return token_info

    # 3. Solo si lo anterior falla (primera vez o sesión cerrada), pedir intervención humana
    try:
        auth_url = sp_oauth.get_authorize_url()
        print(f"\n[!] SE REQUIERE ACCIÓN MANUAL")
        print(f"🔗 Visita: {auth_url}")

        code = input("\n📋 Pega el código de la URL: ").strip()
        if code:
            return sp_oauth.get_access_token(code, as_dict=True)
    except Exception as e:
        print(f"Error en autorización manual: {e}", file=sys.stderr)

    return None


def get_playlists(sp):
    """Obtener todas las playlists del usuario"""
    try:
        playlists = []
        offset = 0
        limit = 50

        while True:
            results = sp.current_user_playlists(offset=offset, limit=limit)
            playlists.extend(results['items'])

            if len(results['items']) < limit:
                break
            offset += limit

        print(f"✅ Encontradas {len(playlists)} playlists")
        return playlists

    except Exception as e:
        print(f"Error obteniendo playlists: {e}", file=sys.stderr)
        return None

def save_playlists(playlists):
    """Guardar playlists en archivo de texto"""
    try:
        with open(playlist_file, "w", encoding='utf-8') as file:
            for playlist in playlists:
                file.write(f"Nombre: {playlist['name']}\n")
                file.write(f"ID: {playlist['id']}\n")
                file.write("\n")

        print(f"✅ Playlists guardadas en: {playlist_file}")
        return True

    except Exception as e:
        print(f"Error guardando playlists: {e}", file=sys.stderr)
        return False

def main():
    print("🎵 SPOTIFY PLAYLIST UPDATER")
    print("=" * 40)

    # Configurar OAuth
    sp_oauth = setup_spotify_oauth()
    if not sp_oauth:
        sys.exit(1)

    # Obtener token válido
    token_info = get_valid_token(sp_oauth)
    if not token_info:
        print("❌ No se pudo obtener token de acceso", file=sys.stderr)
        sys.exit(1)

    # Inicializar cliente de Spotify
    try:
        access_token = token_info['access_token']
        sp = spotipy.Spotify(auth=access_token)

        # Verificar que el token funciona
        user = sp.current_user()
        print(f"✅ Conectado como: {user.get('display_name', user['id'])}")

    except Exception as e:
        print(f"Error inicializando cliente Spotify: {e}", file=sys.stderr)
        sys.exit(1)

    # Obtener playlists
    playlists = get_playlists(sp)
    if not playlists:
        print("❌ No se pudieron obtener las playlists", file=sys.stderr)
        sys.exit(1)

    # Guardar playlists
    if save_playlists(playlists):
        print("🎉 Proceso completado exitosamente")
    else:
        print("❌ Error guardando playlists", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nProceso interrumpido por el usuario")
        sys.exit(0)
    except Exception as e:
        print(f"Error inesperado: {e}", file=sys.stderr)
        sys.exit(1)
