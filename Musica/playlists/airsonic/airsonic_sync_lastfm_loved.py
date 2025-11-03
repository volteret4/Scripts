#!/usr/bin/env python3
"""
Script para sincronizar loved tracks de Last.fm con una playlist de Airsonic
Funciona tanto para crear como para actualizar la playlist
"""

import os
import requests
import time
from dotenv import load_dotenv, dotenv_values
from urllib.parse import quote
import json
from pathlib import Path
import sys
import logging
from typing import List, Dict, Optional

class LastFmAirsonicSync:
    def __init__(self):
        """Inicializa el sincronizador de Last.fm a Airsonic"""
        # Configuración de rutas
        script_dir = Path(__file__).parent.absolute()

        # Cargar variables de entorno desde .env
        env_file = script_dir / ".env"
        if env_file.exists():
            env_vars = dotenv_values(env_file)

            # Last.fm credentials
            self.lastfm_api_key = env_vars.get('LASTFM_API_KEY')
            self.lastfm_username = env_vars.get('LASTFM_USERNAME')

            # Airsonic credentials
            self.airsonic_url = env_vars.get('AIRSONIC_URL', 'http://localhost:4040')
            self.airsonic_user = env_vars.get('AIRSONIC_USER')
            self.airsonic_password = env_vars.get('AIRSONIC_PASSWORD')
            self.airsonic_api_version = env_vars.get('AIRSONIC_API_VERSION', '1.16.1')
        else:
            print(f"Error: No se encontró .env en {env_file}", file=sys.stderr)
            sys.exit(1)

        # Verificar credenciales
        if not all([self.lastfm_api_key, self.lastfm_username,
                   self.airsonic_user, self.airsonic_password]):
            print("❌ Error: Faltan credenciales en el archivo .env")
            print("\nNecesitas configurar en .env:")
            print("LASTFM_API_KEY=tu_api_key")
            print("LASTFM_USERNAME=tu_usuario")
            print("AIRSONIC_URL=http://localhost:4040")
            print("AIRSONIC_USER=admin")
            print("AIRSONIC_PASSWORD=tu_password")
            sys.exit(1)

        # Configuración de Airsonic
        self.auth_params = {
            'u': self.airsonic_user,
            'p': self.airsonic_password,
            'v': self.airsonic_api_version,
            'c': 'LastFmSync',
            'f': 'json'
        }

        # Nombre de la playlist
        self.playlist_name = os.getenv('LASTFM_PLAYLIST_NAME', '❤️ Last.fm Loved Tracks')

        # Configurar logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(script_dir / 'lastfm_airsonic_sync.log')
            ]
        )
        self.logger = logging.getLogger(__name__)

        # Cache para búsquedas
        self._song_cache = {}
        self._build_song_cache()

        # Verificar conexión con Airsonic
        if not self._test_connection():
            self.logger.error("No se pudo conectar a Airsonic")
            sys.exit(1)

    def _test_connection(self) -> bool:
        """Verifica la conexión con Airsonic"""
        try:
            response = self._make_request('ping')
            if response and response.get('status') == 'ok':
                self.logger.info(f"✅ Conectado a Airsonic: {self.airsonic_url}")
                return True
            else:
                self.logger.error(f"Error en respuesta de Airsonic: {response}")
                return False
        except Exception as e:
            self.logger.error(f"Error conectando a Airsonic: {e}")
            return False

    def _make_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Realiza una petición a la API de Airsonic"""
        try:
            url = f"{self.airsonic_url}/rest/{endpoint}"
            request_params = self.auth_params.copy()
            if params:
                request_params.update(params)

            response = requests.get(url, params=request_params, timeout=30)
            response.raise_for_status()

            data = response.json()

            if 'subsonic-response' in data:
                subsonic_response = data['subsonic-response']
                if subsonic_response.get('status') == 'ok':
                    return subsonic_response
                else:
                    error = subsonic_response.get('error', {})
                    self.logger.error(f"Error de Airsonic: {error.get('message', 'Error desconocido')}")
                    return None

            return None

        except Exception as e:
            self.logger.error(f"Error en petición a {endpoint}: {e}")
            return None

    def _normalize_text(self, text: str) -> str:
        """Normaliza texto para búsqueda"""
        if not text:
            return ""
        return ' '.join(text.lower().strip().split())

    def _build_song_cache(self):
        """Construye cache de todas las canciones en Airsonic"""
        print("🔨 Construyendo cache de canciones de Airsonic...")
        self.logger.info("Construyendo cache de canciones...")

        try:
            response = self._make_request('search3', {'query': '*', 'songCount': 10000})

            if response and 'searchResult3' in response:
                songs = response['searchResult3'].get('song', [])

                for song in songs:
                    # Obtener y validar el ID
                    song_id = song.get('id')
                    if isinstance(song_id, list):
                        song_id = song_id[0] if song_id else None
                    if not song_id:
                        continue
                    song_id = str(song_id)

                    # Normalizar para búsqueda
                    artist = self._normalize_text(song.get('artist', ''))
                    title = self._normalize_text(song.get('title', ''))
                    album = self._normalize_text(song.get('album', ''))

                    # Crear múltiples claves de búsqueda
                    keys = [
                        f"{artist}|{title}",
                        f"{title}|{artist}",
                    ]

                    if album:
                        keys.append(f"{artist}|{title}|{album}")

                    for key in keys:
                        self._song_cache[key] = song_id

                print(f"✅ Cache construido: {len(songs)} canciones")
                self.logger.info(f"Cache construido: {len(songs)} canciones, {len(self._song_cache)} claves")
            else:
                self.logger.warning("No se pudieron obtener canciones de Airsonic")

        except Exception as e:
            self.logger.error(f"Error construyendo cache: {e}")

    def get_loved_tracks_from_lastfm(self) -> List[Dict]:
        """Obtiene todos los loved tracks de Last.fm ordenados por fecha (más reciente primero)"""
        print("🎵 Obteniendo loved tracks de Last.fm...")
        self.logger.info("Obteniendo loved tracks de Last.fm...")

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
                    self.logger.error("No se pudieron obtener los loved tracks")
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
                self.logger.error(f"Error al obtener datos de Last.fm: {e}")
                return []
            except KeyError as e:
                self.logger.error(f"Error en la respuesta de Last.fm: {e}")
                return []

        print(f"✅ Se obtuvieron {len(all_tracks)} loved tracks de Last.fm")
        self.logger.info(f"Se obtuvieron {len(all_tracks)} loved tracks")
        return all_tracks

    def search_track_in_airsonic(self, artist: str, title: str) -> Optional[str]:
        """
        Busca una canción en Airsonic usando cache y API

        Args:
            artist: Nombre del artista
            title: Título de la canción

        Returns:
            ID de la canción en Airsonic o None si no se encuentra
        """
        if not artist and not title:
            return None

        # 1. Búsqueda en cache
        cache_keys = [
            f"{self._normalize_text(artist)}|{self._normalize_text(title)}",
            f"{self._normalize_text(title)}|{self._normalize_text(artist)}"
        ]

        for key in cache_keys:
            if key in self._song_cache:
                cached_id = self._song_cache[key]
                if isinstance(cached_id, list):
                    cached_id = cached_id[0] if cached_id else None
                if cached_id:
                    self.logger.debug(f"✓ Cache hit: {artist} - {title}")
                    return str(cached_id)

        # 2. Búsqueda en API de Airsonic
        search_query = f"{artist} {title}"

        try:
            response = self._make_request('search3', {
                'query': search_query,
                'songCount': 10
            })

            if response and 'searchResult3' in response:
                songs = response['searchResult3'].get('song', [])

                for song in songs:
                    song_artist = song.get('artist', '').lower()
                    song_title = song.get('title', '').lower()
                    song_id = song.get('id')

                    # Validar ID
                    if isinstance(song_id, list):
                        song_id = song_id[0] if song_id else None
                    if not song_id:
                        continue
                    song_id = str(song_id)

                    # Verificación flexible
                    artist_match = artist.lower() in song_artist or song_artist in artist.lower()
                    title_match = title.lower() in song_title or song_title in title.lower()

                    if artist_match and title_match:
                        self.logger.debug(f"✓ API match: {artist} - {title}")
                        # Agregar al cache para futuras búsquedas
                        cache_key = f"{self._normalize_text(artist)}|{self._normalize_text(title)}"
                        self._song_cache[cache_key] = song_id
                        return song_id

                # Si hay resultados pero no coincidencia exacta, tomar el primero
                if songs:
                    song = songs[0]
                    song_id = song.get('id')
                    if isinstance(song_id, list):
                        song_id = song_id[0] if song_id else None
                    if song_id:
                        song_id = str(song_id)
                        self.logger.debug(f"≈ Coincidencia aproximada: {artist} - {title} -> {song.get('artist')} - {song.get('title')}")
                        return song_id

        except Exception as e:
            self.logger.debug(f"Error en búsqueda de Airsonic: {e}")

        self.logger.debug(f"✗ No encontrado: {artist} - {title}")
        return None

    def get_airsonic_playlist(self, name: str) -> Optional[Dict]:
        """Obtiene una playlist de Airsonic por nombre"""
        try:
            response = self._make_request('getPlaylists')
            if response and 'playlists' in response:
                playlists = response['playlists'].get('playlist', [])
                for playlist in playlists:
                    if playlist.get('name') == name:
                        # Obtener detalles completos de la playlist
                        details = self._make_request('getPlaylist', {'id': playlist['id']})
                        if details and 'playlist' in details:
                            return details['playlist']
            return None
        except Exception as e:
            self.logger.error(f"Error obteniendo playlist: {e}")
            return None

    def create_airsonic_playlist(self, name: str, song_ids: List[str]) -> Optional[str]:
        """
        Crea una nueva playlist en Airsonic agregando canciones en lotes.

        Args:
            name: Nombre de la playlist
            song_ids: Lista de IDs de canciones

        Returns:
            ID de la playlist creada o None si falla
        """
        try:
            if not song_ids:
                self.logger.warning("No hay canciones para crear la playlist")
                return None

            # Estrategia 1: Crear playlist con la primera canción
            # Algunas versiones de Airsonic requieren al menos una canción al crear
            first_song = song_ids[0]
            remaining_songs = song_ids[1:]

            params = {
                'name': name,
                'songId': first_song
            }

            response = self._make_request('createPlaylist', params)

            if not response:
                self.logger.error("No se recibió respuesta al crear playlist")
                return None

            # Intentar obtener el ID de la playlist de diferentes maneras
            playlist_id = None

            if 'playlist' in response:
                playlist_id = response['playlist'].get('id')

            # Si no está en la respuesta, buscar la playlist recién creada
            if not playlist_id:
                self.logger.info("Buscando playlist recién creada...")
                time.sleep(0.5)  # Pequeña pausa para que se sincronice
                found_playlist = self.get_airsonic_playlist(name)
                if found_playlist:
                    playlist_id = found_playlist['id']

            if not playlist_id:
                self.logger.error(f"No se pudo obtener el ID de la playlist. Respuesta: {response}")
                return None

            self.logger.info(f"Playlist '{name}' creada con ID: {playlist_id}")

            # Si solo había una canción, ya terminamos
            if not remaining_songs:
                print(f"✓ Playlist creada con 1 canción")
                return playlist_id

            # Agregar canciones restantes en lotes
            batch_size = 100  # Límite razonable para la API
            total_batches = (len(remaining_songs) + batch_size - 1) // batch_size

            print(f"📦 Agregando {len(remaining_songs)} canciones restantes en {total_batches} lotes...")

            for i in range(0, len(remaining_songs), batch_size):
                batch = remaining_songs[i:i + batch_size]
                batch_num = (i // batch_size) + 1

                params = {
                    'playlistId': playlist_id,
                    'songIdToAdd': batch
                }

                response = self._make_request('updatePlaylist', params)

                if response:
                    print(f"  ✓ Lote {batch_num}/{total_batches}: {len(batch)} canciones agregadas")
                    self.logger.info(f"Lote {batch_num}/{total_batches} agregado exitosamente")
                else:
                    self.logger.error(f"Error agregando lote {batch_num}")

                # Pequeña pausa entre lotes
                time.sleep(0.1)

            self.logger.info(f"Playlist '{name}' completada con {len(song_ids)} canciones")
            return playlist_id

        except Exception as e:
            self.logger.error(f"Error creando playlist: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None

    def update_airsonic_playlist(self, playlist_id: str, song_ids: List[str]) -> bool:
        """
        Actualiza una playlist existente reemplazando todas las canciones.
        Elimina las canciones actuales y agrega las nuevas en lotes.

        Args:
            playlist_id: ID de la playlist
            song_ids: Lista de IDs de canciones nuevas

        Returns:
            True si se actualizó correctamente
        """
        try:
            print("🗑️  Limpiando playlist existente...")

            # Obtener canciones actuales
            response = self._make_request('getPlaylist', {'id': playlist_id})
            if response and 'playlist' in response:
                current_entries = response['playlist'].get('entry', [])

                if current_entries:
                    print(f"   Eliminando {len(current_entries)} canciones actuales...")
                    # Eliminar todas las canciones actuales
                    for i in range(len(current_entries)):
                        # Siempre eliminar el índice 0 porque después de cada eliminación, los índices se reajustan
                        self._make_request('updatePlaylist', {
                            'playlistId': playlist_id,
                            'songIndexToRemove': 0
                        })

                        # Mostrar progreso cada 50 canciones
                        if (i + 1) % 50 == 0:
                            print(f"   Eliminadas {i + 1}/{len(current_entries)}...")

                        time.sleep(0.02)

                    print(f"   ✓ Playlist limpiada")

            # Agregar nuevas canciones en lotes
            if song_ids:
                batch_size = 100
                total_batches = (len(song_ids) + batch_size - 1) // batch_size

                print(f"📦 Agregando {len(song_ids)} canciones en {total_batches} lotes...")

                for i in range(0, len(song_ids), batch_size):
                    batch = song_ids[i:i + batch_size]
                    batch_num = (i // batch_size) + 1

                    params = {
                        'playlistId': playlist_id,
                        'songIdToAdd': batch
                    }

                    response = self._make_request('updatePlaylist', params)

                    if response:
                        print(f"  ✓ Lote {batch_num}/{total_batches}: {len(batch)} canciones agregadas")
                        self.logger.info(f"Lote {batch_num}/{total_batches} agregado exitosamente")
                    else:
                        self.logger.error(f"Error agregando lote {batch_num}")

                    time.sleep(0.1)

                self.logger.info(f"Playlist actualizada con {len(song_ids)} canciones")
                return True

            return False

        except Exception as e:
            self.logger.error(f"Error actualizando playlist: {e}")
            return False

    def create_or_update_playlist(self, song_ids: List[str]) -> Optional[str]:
        """Crea una nueva playlist o actualiza una existente"""
        if not song_ids:
            print("❌ No hay canciones para crear/actualizar la playlist")
            return None

        # Buscar si ya existe la playlist
        existing_playlist = self.get_airsonic_playlist(self.playlist_name)

        if existing_playlist:
            print(f"📝 Actualizando playlist existente: {self.playlist_name}")
            self.logger.info(f"Actualizando playlist existente: {self.playlist_name}")

            if self.update_airsonic_playlist(existing_playlist['id'], song_ids):
                return existing_playlist['id']
            else:
                return None
        else:
            print(f"🆕 Creando nueva playlist: {self.playlist_name}")
            self.logger.info(f"Creando nueva playlist: {self.playlist_name}")

            return self.create_airsonic_playlist(self.playlist_name, song_ids)

    def sync_loved_tracks(self) -> bool:
        """Función principal que sincroniza los loved tracks"""
        print("\n" + "="*60)
        print("🚀 SINCRONIZACIÓN DE LOVED TRACKS: LAST.FM -> AIRSONIC")
        print("="*60 + "\n")

        # Obtener loved tracks de Last.fm
        loved_tracks = self.get_loved_tracks_from_lastfm()
        if not loved_tracks:
            print("❌ No se pudieron obtener loved tracks")
            return False

        # Buscar canciones en Airsonic
        print("\n🔍 Buscando canciones en Airsonic...")
        airsonic_song_ids = []
        not_found = []

        for i, track in enumerate(loved_tracks, 1):
            artist = track['artist']['name']
            song = track['name']

            print(f"🎵 Buscando ({i}/{len(loved_tracks)}): {artist} - {song}")

            song_id = self.search_track_in_airsonic(artist, song)

            if song_id:
                airsonic_song_ids.append(song_id)
            else:
                not_found.append(f"{artist} - {song}")

            # Pausa para evitar rate limiting
            time.sleep(0.05)

        # Mostrar resultados de búsqueda
        print("\n" + "="*60)
        print(f"✅ Encontradas {len(airsonic_song_ids)} de {len(loved_tracks)} canciones en Airsonic")
        print(f"📊 Tasa de éxito: {len(airsonic_song_ids)/len(loved_tracks)*100:.1f}%")
        print("="*60)

        if not_found:
            print(f"\n⚠️  No se encontraron {len(not_found)} canciones:")
            for track in not_found[:10]:  # Mostrar solo las primeras 10
                print(f"   - {track}")
            if len(not_found) > 10:
                print(f"   ... y {len(not_found) - 10} más")

        # Crear o actualizar playlist
        if airsonic_song_ids:
            print("\n📝 Creando/actualizando playlist en Airsonic...")
            playlist_id = self.create_or_update_playlist(airsonic_song_ids)

            if playlist_id:
                playlist_url = f"{self.airsonic_url}/index.view?playlistId={playlist_id}"
                print("\n" + "="*60)
                print("🎉 ¡Sincronización completada exitosamente!")
                print(f"📝 Playlist: {self.playlist_name}")
                print(f"🔗 URL: {playlist_url}")
                print(f"🎵 Canciones: {len(airsonic_song_ids)}")
                print("="*60 + "\n")
                return True
            else:
                print("❌ Error al crear/actualizar la playlist")
                return False
        else:
            print("❌ No se encontraron canciones para agregar a la playlist")
            return False

def main():
    """Función principal"""
    try:
        syncer = LastFmAirsonicSync()
        success = syncer.sync_loved_tracks()

        if success:
            print("✨ Script ejecutado exitosamente\n")
            sys.exit(0)
        else:
            print("💥 El script terminó con errores\n")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Proceso interrumpido por el usuario")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
