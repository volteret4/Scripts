import os
import sys
import re
import argparse
import requests
import json
from urllib.parse import quote

# Configuración de APIs y autenticación
LASTFM_API_KEY = kwargs.get('LASTFM_API_KEY')
SPOTIFY_CLIENT_ID = kwargs.get('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = kwargs.get('SPOTIFY_CLIENT_SECRET')
BLUESKY_USERNAME = kwargs.get('BLUESKY_USERNAME')
BLUESKY_PASSWORD = kwargs.get('BLUESKY_PASSWORD')

def clean_artist_name(artist):
    # Eliminar cualquier parte "featuring", "feat." etc.
    patterns = [
        r'\s+feat\.?\s+.*',  # "feat" o "feat." seguido de espacios
        r'\s+featuring\s+.*',  # "featuring" seguido de espacios
        r'\s+with\s+.*',      # "with" seguido de espacios
    ]
    
    for pattern in patterns:
        artist = re.sub(pattern, '', artist, flags=re.IGNORECASE)
    
    # Eliminar espacios extra
    artist = artist.strip()
    return artist

def follow_on_lastfm(artist):
    if not LASTFM_API_KEY:
        print(f"⚠️ No se puede seguir a {artist} en LastFM: API_KEY no configurada")
        return False
    
    # URL codificada para el nombre del artista
    encoded_artist = quote(artist)
    
    # Endpoint para buscar el artista
    search_url = f"http://ws.audioscrobbler.com/2.0/?method=artist.getinfo&artist={encoded_artist}&api_key={LASTFM_API_KEY}&format=json"
    
    try:
        response = requests.get(search_url)
        data = response.json()
        
        # Verificar si se encontró el artista
        if 'artist' in data:
            artist_name = data['artist']['name']
            print(f"✅ Encontrado en LastFM: {artist_name}")
            
            # Nota: LastFM no tiene una API para seguir artistas directamente
            # Tendríamos que usar web scraping o autenticación OAuth para esto
            print(f"🔗 Página del artista: {data['artist']['url']}")
            return True
        else:
            print(f"❌ No se encontró a {artist} en LastFM")
            return False
            
    except Exception as e:
        print(f"❌ Error al buscar {artist} en LastFM: {str(e)}")
        return False

def get_spotify_token():
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        return None
        
    auth_url = "https://accounts.spotify.com/api/token"
    auth_response = requests.post(auth_url, {
        'grant_type': 'client_credentials',
        'client_id': SPOTIFY_CLIENT_ID,
        'client_secret': SPOTIFY_CLIENT_SECRET,
    })
    
    if auth_response.status_code != 200:
        print("❌ Error de autenticación con Spotify")
        return None
        
    auth_data = auth_response.json()
    return auth_data['access_token']

def follow_on_spotify(artist):
    token = get_spotify_token()
    if not token:
        print(f"⚠️ No se puede seguir a {artist} en Spotify: Credenciales no configuradas")
        return False
    
    # Buscar artista en Spotify
    headers = {
        'Authorization': f'Bearer {token}'
    }
    search_url = f"https://api.spotify.com/v1/search?q={quote(artist)}&type=artist&limit=1"
    
    try:
        response = requests.get(search_url, headers=headers)
        data = response.json()
        
        if 'artists' in data and data['artists']['items']:
            artist_data = data['artists']['items'][0]
            print(f"✅ Encontrado en Spotify: {artist_data['name']}")
            print(f"🔗 Perfil: https://open.spotify.com/artist/{artist_data['id']}")
            
            # Nota: Para seguir al artista, necesitaríamos autenticación de usuario
            # con OAuth y scope user-follow-modify
            return True
        else:
            print(f"❌ No se encontró a {artist} en Spotify")
            return False
    
    except Exception as e:
        print(f"❌ Error al buscar {artist} en Spotify: {str(e)}")
        return False

def authenticate_bluesky():
    if not BLUESKY_USERNAME or not BLUESKY_PASSWORD:
        return None
        
    try:
        # API de autenticación de Bluesky
        auth_url = "https://bsky.social/xrpc/com.atproto.server.createSession"
        auth_data = {
            "identifier": BLUESKY_USERNAME,
            "password": BLUESKY_PASSWORD
        }
        
        response = requests.post(auth_url, json=auth_data)
        if response.status_code != 200:
            print("❌ Error de autenticación con Bluesky")
            return None
            
        return response.json()
    except Exception as e:
        print(f"❌ Error al autenticar en Bluesky: {str(e)}")
        return None

def follow_on_bluesky(artist):
    auth_data = authenticate_bluesky()
    if not auth_data:
        print(f"⚠️ No se puede buscar a {artist} en Bluesky: Credenciales no configuradas")
        return False
    
    # Buscar usuarios con ese nombre en Bluesky
    try:
        search_url = "https://bsky.social/xrpc/app.bsky.actor.searchActors"
        headers = {
            "Authorization": f"Bearer {auth_data['accessJwt']}"
        }
        params = {
            "term": artist,
            "limit": 5
        }
        
        response = requests.get(search_url, headers=headers, params=params)
        data = response.json()
        
        if 'actors' in data and data['actors']:
            print(f"✅ Posibles coincidencias en Bluesky para {artist}:")
            for i, actor in enumerate(data['actors'], 1):
                print(f"  {i}. @{actor['handle']} - {actor.get('displayName', 'Sin nombre')}")
            
            # Para seguir necesitaríamos implementar el endpoint follow
            # app.bsky.graph.follow con los detalles del usuario a seguir
            return True
        else:
            print(f"❌ No se encontraron coincidencias para {artist} en Bluesky")
            return False
    
    except Exception as e:
        print(f"❌ Error al buscar {artist} en Bluesky: {str(e)}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Seguir artistas en diferentes plataformas')
    parser.add_argument('file', help='Archivo con lista de artistas')
    parser.add_argument('-l', '--lastfm', action='store_true', help='Seguir en LastFM')
    parser.add_argument('-s', '--spotify', action='store_true', help='Seguir en Spotify')
    parser.add_argument('-b', '--bluesky', action='store_true', help='Seguir en Bluesky')
    parser.add_argument('-k', '--lastfm_api_key', help='Api de lastfm')
    parser.add_argument('-c', '--spotify_client_id', help='Client ID de Spotify')
    parser.add_argument('-t', '--spotify_client_secret', help='Secret de Spotify')
    parser.add_argument('-y', '--bluesky_username', help='Usuario de Bluesky')
    parser.add_argument('-w', '--bluesky_password', help='Contraseña de Bluesky')
    




    args = parser.parse_args()
    
    # Verificar si al menos una plataforma está habilitada
    if not (args.lastfm or args.spotify or args.bluesky):
        print("⚠️ Debes seleccionar al menos una plataforma con -l, -s o -b")
        sys.exit(1)
    
    try:
        with open(args.file, 'r', encoding='utf-8') as f:
            artists = [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"❌ Error al leer el archivo {args.file}: {str(e)}")
        sys.exit(1)
    
    print(f"📋 Procesando {len(artists)} artistas...")
    
    for artist in artists:
        clean_name = clean_artist_name(artist)
        print(f"\n🎵 Artista: {clean_name} (original: {artist})")
        
        if args.lastfm:
            print("-- LastFM --")
            follow_on_lastfm(clean_name)
        
        if args.spotify:
            print("-- Spotify --")
            follow_on_spotify(clean_name)
        
        if args.bluesky:
            print("-- Bluesky --")
            follow_on_bluesky(clean_name)
    
    print("\n✨ Proceso completado")

if __name__ == "__main__":
    main()