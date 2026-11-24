#!/usr/bin/env python3
"""
Crea una playlist en Spotify a partir de un .txt con canciones en formato "artista - cancion"
Uso: sp_create_playlist_from_txt.py <archivo.txt> <nombre_playlist> [--publica] [--descripcion "..."]
"""

import os
import sys
import time
import argparse
from pathlib import Path

from sopsdotenv import load_sops_env
import spotipy
from spotipy.oauth2 import SpotifyOAuth


def load_credentials():
    load_sops_env()
    return {
        'client_id': os.getenv('SPOTIFY_CLIENT'),
        'client_secret': os.getenv('SPOTIFY_SECRET'),
        'redirect_uri': os.getenv('SPOTIFY_REDIRECT', 'http://localhost:8888/callback'),
    }


def init_spotify(creds):
    scope = "playlist-modify-public playlist-modify-private playlist-read-private"
    sp_oauth = SpotifyOAuth(
        client_id=creds['client_id'],
        client_secret=creds['client_secret'],
        redirect_uri=creds['redirect_uri'],
        scope=scope,
        cache_path=str(Path(__file__).parent / ".cache"),
    )
    return spotipy.Spotify(auth_manager=sp_oauth)


def read_songs(txt_path):
    songs = []
    with open(txt_path, encoding='utf-8') as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith('#'):
                continue
            if ' - ' not in linea:
                print(f"  [ignorada] formato no reconocido: {linea!r}")
                continue
            artist, _, title = linea.partition(' - ')
            songs.append((artist.strip(), title.strip()))
    return songs


def search_track(sp, artist, title):
    # Búsqueda exacta primero
    query = f'artist:"{artist}" track:"{title}"'
    results = sp.search(q=query, type='track', limit=1)
    items = results['tracks']['items']
    if items:
        return items[0]['uri']

    # Fallback sin comillas
    query_alt = f"{artist} {title}"
    results = sp.search(q=query_alt, type='track', limit=1)
    items = results['tracks']['items']
    if items:
        return items[0]['uri']

    return None


def create_playlist(sp, name, description, public):
    user_id = sp.me()['id']
    playlist = sp.user_playlist_create(
        user=user_id,
        name=name,
        public=public,
        description=description,
    )
    return playlist['id'], playlist['external_urls']['spotify']


def add_tracks_in_batches(sp, playlist_id, uris, batch_size=100):
    for i in range(0, len(uris), batch_size):
        sp.playlist_add_items(playlist_id, uris[i:i + batch_size])
        time.sleep(0.2)


def main():
    parser = argparse.ArgumentParser(description='Crea una playlist de Spotify desde un .txt')
    parser.add_argument('txt', help='Archivo .txt con canciones (una por línea, formato "artista - cancion")')
    parser.add_argument('nombre', help='Nombre de la playlist a crear')
    parser.add_argument('--descripcion', default='', help='Descripción de la playlist')
    parser.add_argument('--publica', action='store_true', help='Crear la playlist como pública (por defecto privada)')
    args = parser.parse_args()

    txt_path = Path(args.txt)
    if not txt_path.exists():
        print(f"Error: no se encontró el archivo {txt_path}", file=sys.stderr)
        sys.exit(1)

    creds = load_credentials()
    if not creds['client_id'] or not creds['client_secret']:
        print("Error: credenciales de Spotify no encontradas en el entorno", file=sys.stderr)
        sys.exit(1)

    print("Conectando con Spotify...")
    sp = init_spotify(creds)

    print(f"Leyendo canciones de {txt_path}...")
    songs = read_songs(txt_path)
    if not songs:
        print("Error: no se encontraron canciones en el archivo", file=sys.stderr)
        sys.exit(1)
    print(f"  {len(songs)} canciones leídas")

    print("Buscando canciones en Spotify...")
    uris = []
    not_found = []
    for artist, title in songs:
        uri = search_track(sp, artist, title)
        if uri:
            uris.append(uri)
            print(f"  [ok] {artist} - {title}")
        else:
            not_found.append(f"{artist} - {title}")
            print(f"  [no encontrada] {artist} - {title}")
        time.sleep(0.1)

    if not uris:
        print("No se encontró ninguna canción en Spotify. Abortando.", file=sys.stderr)
        sys.exit(1)

    print(f"\nCreando playlist '{args.nombre}'...")
    playlist_id, playlist_url = create_playlist(sp, args.nombre, args.descripcion, args.publica)
    add_tracks_in_batches(sp, playlist_id, uris)

    print(f"\nPlaylist creada con {len(uris)} canciones.")
    if not_found:
        print(f"No encontradas ({len(not_found)}):")
        for s in not_found:
            print(f"  - {s}")
    print(f"\nURL: {playlist_url}")


if __name__ == '__main__':
    main()
