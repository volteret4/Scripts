#!/usr/bin/env python3
"""
Script para sincronizar loved tracks de Last.fm con una playlist de Spotify
Funciona tanto para crear como para actualizar la playlist
"""

import os
import requests
import time
from dotenv import load_dotenv, dotenv_values
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from urllib.parse import quote
import json
from pathlib import Path

class LastFmSpotifySync:
    def __init__(self):
        # Configuración de rutas
        script_dir = Path(__file__).parent.absolute()
        project_root = script_dir.parent

        # Cargar variables de entorno SOLO del .env (no del sistema)
        env_file = project_root / ".env"
        if env_file.exists():
            # Opción 1: Usar dotenv_values para cargar solo del archivo
            env_vars = dotenv_values(env_file)

            # Obtener credenciales
            self.lastfm_api_key = env_vars.get('LASTFM_API_KEY')
            self.lastfm_username = env_vars.get('LASTFM_USERNAME')
            self.spotify_client_id = env_vars.get('SPOTIFY_CLIENT')
            self.spotify_client_secret = env_vars.get('SPOTIFY_SECRET')
            self.spotify_redirect_uri = env_vars.get('SPOTIFY_REDIRECT', 'http://localhost:8888/callback')


            # O alternativamente, Opción 2: usar load_dotenv con override=True
            # load_dotenv(env_file, override=True)
        else:
            print(f"Error: No se encontró .env en {env_file}", file=sys.stderr)
            # Obtener credenciales del entorno
            self.lastfm_api_key = os.getenv('LASTFM_API_KEY')
            self.lastfm_username = os.getenv('LASTFM_USERNAME')
            self.spotify_client_id = os.getenv('SPOTIFY_CLIENT')
            self.spotify_client_secret = os.getenv('SPOTIFY_SECRET')
            self.spotify_redirect_uri = os.getenv('SPOTIFY_REDIRECT', 'http://localhost:8888/callback')


        # Nombre de la playlist
        self.playlist_name = os.getenv('PLAYLIST_NAME', 'My Last.fm Loved Tracks')

        # Inicializar Spotify
        self.sp = self._init_spotify()
        self.user_id = self.sp.me()['id']

    def _init_spotify(self):
        """Inicializa la conexión con Spotify"""
        scope = "playlist-modify-public playlist-modify-private playlist-read-private"

        sp_oauth = SpotifyOAuth(
            client_id=self.spotify_client_id,
            client_secret=self.spotify_client_secret,
            redirect_uri=self.spotify_redirect_uri,
            scope=scope,
            cache_path=".cache"
        )

        return spotipy.Spotify(auth_manager=sp_oauth)

    def get_loved_tracks_from_lastfm(self):
        """Obtiene todos los loved tracks de Last.fm ordenados por fecha (más reciente primero)"""
        print("🎵 Obteniendo loved tracks de Last.fm...")

        url = "http://ws.audioscrobbler.com/2.0/"
        all_tracks = []
        page = 1
        total_pages = 1

        while page <= total_pages:
            params = {
                'method': 'user.getlovedtracks',
                'user': self.lastfm_username,
                'api_key': self.lastfm_api_key,
                'format': 'json',
                'page': page,
                'limit': 200
            }

            try:
                response = requests.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                if 'lovedtracks' not in data:
                    print("❌ Error: No se pudieron obtener los loved tracks")
                    return []

                tracks = data['lovedtracks']['track']
                if isinstance(tracks, dict):  # Solo hay una canción
                    tracks = [tracks]

                all_tracks.extend(tracks)

                # Actualizar información de paginación
                total_pages = int(data['lovedtracks']['@attr']['totalPages'])
                print(f"📄 Procesando página {page} de {total_pages}")
                page += 1

                # Pequeña pausa para no sobrecargar la API
                time.sleep(0.1)

            except requests.exceptions.RequestException as e:
                print(f"❌ Error al obtener datos de Last.fm: {e}")
                return []
            except KeyError as e:
                print(f"❌ Error en la respuesta de Last.fm: {e}")
                return []

        print(f"✅ Se obtuvieron {len(all_tracks)} loved tracks de Last.fm")
        return all_tracks

    def search_track_on_spotify(self, artist, track):
        """Busca una canción en Spotify"""
        query = f"artist:\"{artist}\" track:\"{track}\""

        try:
            results = self.sp.search(q=query, type='track', limit=1)
            if results['tracks']['items']:
                return results['tracks']['items'][0]['uri']

            # Búsqueda alternativa sin comillas
            query_alt = f"{artist} {track}"
            results = self.sp.search(q=query_alt, type='track', limit=1)
            if results['tracks']['items']:
                return results['tracks']['items'][0]['uri']

        except Exception as e:
            print(f"⚠️  Error buscando '{artist} - {track}': {e}")

        return None

    def find_existing_playlist(self):
        """Busca si ya existe una playlist con el nombre especificado"""
        playlists = self.sp.user_playlists(self.user_id)

        for playlist in playlists['items']:
            if playlist['name'] == self.playlist_name:
                return playlist['id']

        return None

    def create_or_update_playlist(self, spotify_uris):
        """Crea una nueva playlist o actualiza una existente"""
        playlist_id = self.find_existing_playlist()

        if playlist_id:
            print(f"📝 Actualizando playlist existente: {self.playlist_name}")

            # Limpiar la playlist existente
            self.sp.playlist_replace_items(playlist_id, [])

        else:
            print(f"🆕 Creando nueva playlist: {self.playlist_name}")

            # Crear nueva playlist
            playlist = self.sp.user_playlist_create(
                self.user_id,
                self.playlist_name,
                description="Mis loved tracks de Last.fm sincronizados automáticamente"
            )
            playlist_id = playlist['id']

        # Agregar canciones en lotes de 100 (límite de Spotify)
        batch_size = 100
        for i in range(0, len(spotify_uris), batch_size):
            batch = spotify_uris[i:i + batch_size]
            self.sp.playlist_add_items(playlist_id, batch)
            print(f"➕ Agregadas {len(batch)} canciones a la playlist")

        return playlist_id

    def sync_loved_tracks(self):
        """Función principal que sincroniza los loved tracks"""
        print("🚀 Iniciando sincronización de loved tracks...")

        # Verificar credenciales
        if not all([self.lastfm_api_key, self.lastfm_username,
                   self.spotify_client_id, self.spotify_client_secret]):
            print("❌ Error: Faltan credenciales en el archivo .env")
            return False

        # Obtener loved tracks de Last.fm
        loved_tracks = self.get_loved_tracks_from_lastfm()
        if not loved_tracks:
            print("❌ No se pudieron obtener loved tracks")
            return False

        # Buscar canciones en Spotify
        print("🔍 Buscando canciones en Spotify...")
        spotify_uris = []
        not_found = []

        for i, track in enumerate(loved_tracks, 1):
            artist = track['artist']['name']
            song = track['name']

            print(f"🎵 Buscando ({i}/{len(loved_tracks)}): {artist} - {song}")

            spotify_uri = self.search_track_on_spotify(artist, song)

            if spotify_uri:
                spotify_uris.append(spotify_uri)
            else:
                not_found.append(f"{artist} - {song}")

            # Pausa para evitar rate limiting
            time.sleep(0.1)

        print(f"✅ Encontradas {len(spotify_uris)} de {len(loved_tracks)} canciones en Spotify")

        if not_found:
            print(f"⚠️  No se encontraron {len(not_found)} canciones:")
            for track in not_found[:10]:  # Mostrar solo las primeras 10
                print(f"   - {track}")
            if len(not_found) > 10:
                print(f"   ... y {len(not_found) - 10} más")

        # Crear o actualizar playlist
        if spotify_uris:
            playlist_id = self.create_or_update_playlist(spotify_uris)
            playlist_url = f"https://open.spotify.com/playlist/{playlist_id}"
            print(f"🎉 ¡Sincronización completada!")
            print(f"🔗 Playlist: {playlist_url}")
            return True
        else:
            print("❌ No se encontraron canciones para agregar a la playlist")
            return False

def main():
    """Función principal"""
    syncer = LastFmSpotifySync()
    success = syncer.sync_loved_tracks()

    if success:
        print("\n✨ Script ejecutado exitosamente")
    else:
        print("\n💥 El script terminó con errores")

if __name__ == "__main__":
    main()
