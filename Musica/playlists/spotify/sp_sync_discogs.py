#!/usr/bin/env python3
"""
Script para crear playlists de Spotify basadas en colección y wantlist de Discogs
"""

import os
import sys
from dotenv import load_dotenv, dotenv_values
import discogs_client
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import time
from typing import Set, List, Dict, Optional
import logging
import glob
from pathlib import Path

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DiscogsSpotifySync:
    def __init__(self, clear_spotify_cache=False):
        """Inicializa el sincronizador con credenciales del .env o variables de entorno"""

        # Limpiar caché de Spotify si se solicita
        if clear_spotify_cache:
            self.clear_spotify_cache()

        # Configuración de rutas
        script_dir = Path(__file__).parent.absolute()
        project_root = script_dir.parent

        # Cargar variables de entorno SOLO del .env (no del sistema)
        env_file = project_root / ".env"
        if env_file.exists():
            # Opción 1: Usar dotenv_values para cargar solo del archivo
            env_vars = dotenv_values(env_file)

            # Obtener credenciales
            self.discogs_token = env_vars.get('DISCOGS_TOKEN')
            self.spotify_client_id = env_vars.get('SPOTIFY_CLIENT')
            self.spotify_client_secret = env_vars.get('SPOTIFY_SECRET')
            self.spotify_redirect_uri = env_vars.get('SPOTIFY_REDIRECT', 'http://localhost:8888/callback')
            self.discogs_username = env_vars.get('DISCOGS_USERNAME')

            # O alternativamente, Opción 2: usar load_dotenv con override=True
            # load_dotenv(env_file, override=True)
        else:
            print(f"Error: No se encontró .env en {env_file}", file=sys.stderr)
            # Obtener credenciales del entorno
            self.discogs_token = os.getenv('DISCOGS_TOKEN')
            self.spotify_client_id = os.getenv('SPOTIFY_CLIENT')
            self.spotify_client_secret = os.getenv('SPOTIFY_SECRET')
            self.spotify_redirect_uri = os.getenv('SPOTIFY_REDIRECT', 'http://localhost:8888/callback')
            self.discogs_username = os.getenv('DISCOGS_USERNAME')

            # sys.exit(1)

        # Validar credenciales requeridas
        if not all([self.discogs_token, self.spotify_client_id, self.spotify_client_secret, self.discogs_username]):
            missing = []
            if not self.discogs_token: missing.append('DISCOGS_TOKEN')
            if not self.spotify_client_id: missing.append('SPOTIFY_CLIENT_ID')
            if not self.spotify_client_secret: missing.append('SPOTIFY_CLIENT_SECRET')
            if not self.discogs_username: missing.append('DISCOGS_USERNAME')

            raise ValueError(f"Faltan las siguientes variables de entorno: {', '.join(missing)}")

        # Inicializar clientes
        self.discogs = discogs_client.Client('DiscogsSpotifySync/1.0', user_token=self.discogs_token)

        scope = "playlist-modify-public playlist-modify-private"
        self.spotify = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=self.spotify_client_id,
                client_secret=self.spotify_client_secret,
                redirect_uri=self.spotify_redirect_uri,
                scope=scope
            )
        )

        logger.info("Clientes de Discogs y Spotify inicializados correctamente")

    def clear_spotify_cache(self):
        """Elimina archivos de caché de Spotify para permitir nuevo login"""
        logger.info("Buscando y eliminando archivos de caché de Spotify...")

        # Posibles ubicaciones del caché
        home_dir = os.path.expanduser("~")
        cache_patterns = [
            os.path.join(home_dir, ".cache-*"),
            os.path.join(home_dir, ".cache", "*"),
            os.path.join(home_dir, ".spotipy_cache"),
            # En Windows a veces está en AppData
            os.path.join(os.getenv('APPDATA', ''), '.cache-*') if os.name == 'nt' else "",
        ]

        files_deleted = 0
        for pattern in cache_patterns:
            if pattern:  # Skip empty patterns
                for cache_file in glob.glob(pattern):
                    try:
                        if os.path.isfile(cache_file) and ('cache' in os.path.basename(cache_file).lower() or 'spotify' in cache_file.lower()):
                            os.remove(cache_file)
                            logger.info(f"Eliminado archivo de caché: {cache_file}")
                            files_deleted += 1
                    except Exception as e:
                        logger.warning(f"No se pudo eliminar {cache_file}: {e}")

        if files_deleted == 0:
            logger.info("No se encontraron archivos de caché de Spotify para eliminar")
        else:
            logger.info(f"Se eliminaron {files_deleted} archivo(s) de caché")


    def get_album_key(self, artist: str, title: str) -> str:
        """Genera una clave única para identificar álbumes duplicados"""
        # Limpiar y normalizar para evitar duplicados
        artist_clean = artist.lower().strip()
        title_clean = title.lower().strip()
        return f"{artist_clean}|{title_clean}"

    def get_discogs_collection(self) -> Set[str]:
        """Obtiene todos los álbumes de la colección de Discogs"""
        logger.info("Obteniendo colección de Discogs...")
        albums = set()

        try:
            user = self.discogs.user(self.discogs_username)
            collection = user.collection_folders[0].releases  # Folder 0 es "All"

            page = 1
            while True:
                try:
                    releases = collection.page(page)
                    if not releases or len(releases) == 0:
                        logger.info(f"No hay más releases en la página {page}, finalizando")
                        break

                    logger.info(f"Procesando página {page} de la colección ({len(releases)} items)")

                    for collection_item in releases:
                        try:
                            # Los items de colección tienen una estructura específica
                            release = collection_item.release

                            # Obtener artista y título directamente del objeto release
                            if hasattr(release, 'artists') and release.artists:
                                artist = release.artists[0].name
                            else:
                                artist = 'Unknown Artist'

                            if hasattr(release, 'title'):
                                title = release.title
                            else:
                                title = 'Unknown Title'

                            album_key = self.get_album_key(artist, title)
                            albums.add(album_key)
                            logger.debug(f"Colección: {artist} - {title}")

                        except Exception as e:
                            logger.warning(f"Error procesando release de colección: {e}")
                            # Intentar acceso alternativo
                            try:
                                # Si collection_item es directamente el release
                                if hasattr(collection_item, 'artists') and collection_item.artists:
                                    artist = collection_item.artists[0].name
                                    title = collection_item.title
                                    album_key = self.get_album_key(artist, title)
                                    albums.add(album_key)
                                    logger.debug(f"Colección (método alternativo): {artist} - {title}")
                            except Exception as e2:
                                logger.warning(f"Error en método alternativo para colección: {e2}")

                    page += 1
                    time.sleep(1)  # Rate limiting

                except Exception as page_error:
                    if "404" in str(page_error) or "outside of valid range" in str(page_error):
                        logger.info(f"Llegamos al final de la colección en la página {page}")
                        break
                    else:
                        logger.error(f"Error inesperado en página {page}: {page_error}")
                        break

        except Exception as e:
            logger.error(f"Error obteniendo colección: {e}")
            return albums  # Retornar lo que hayamos conseguido hasta ahora

        logger.info(f"Encontrados {len(albums)} álbumes únicos en la colección")
        return albums

    def get_discogs_wantlist(self) -> Set[str]:
        """Obtiene todos los álbumes de la wantlist de Discogs"""
        logger.info("Obteniendo wantlist de Discogs...")
        albums = set()

        try:
            user = self.discogs.user(self.discogs_username)
            wantlist = user.wantlist

            page = 1
            while True:
                try:
                    wants = wantlist.page(page)
                    if not wants or len(wants) == 0:
                        logger.info(f"No hay más wants en la página {page}, finalizando")
                        break

                    logger.info(f"Procesando página {page} de la wantlist ({len(wants)} items)")

                    for want_item in wants:
                        try:
                            # Los WantlistItem tienen el release dentro
                            release = want_item.release

                            # Obtener artista y título directamente del objeto release
                            if hasattr(release, 'artists') and release.artists:
                                artist = release.artists[0].name
                            else:
                                artist = 'Unknown Artist'

                            if hasattr(release, 'title'):
                                title = release.title
                            else:
                                title = 'Unknown Title'

                            album_key = self.get_album_key(artist, title)
                            albums.add(album_key)
                            logger.debug(f"Wantlist: {artist} - {title}")

                        except Exception as e:
                            logger.warning(f"Error procesando want: {e}")
                            # Intentar acceso alternativo
                            try:
                                # Si want_item tiene directamente los atributos
                                if hasattr(want_item, 'artists') and want_item.artists:
                                    artist = want_item.artists[0].name
                                    title = want_item.title
                                    album_key = self.get_album_key(artist, title)
                                    albums.add(album_key)
                                    logger.debug(f"Wantlist (método alternativo): {artist} - {title}")
                            except Exception as e2:
                                logger.warning(f"Error en método alternativo para wantlist: {e2}")

                    page += 1
                    time.sleep(1)  # Rate limiting

                except Exception as page_error:
                    if "404" in str(page_error) or "outside of valid range" in str(page_error):
                        logger.info(f"Llegamos al final de la wantlist en la página {page}")
                        break
                    else:
                        logger.error(f"Error inesperado en página {page}: {page_error}")
                        break

        except Exception as e:
            logger.error(f"Error obteniendo wantlist: {e}")
            return albums  # Retornar lo que hayamos conseguido hasta ahora

        logger.info(f"Encontrados {len(albums)} álbumes únicos en la wantlist")
        return albums

    def search_spotify_album(self, album_key: str) -> List[str]:
        """Busca un álbum en Spotify y retorna los URIs de las canciones"""
        artist, title = album_key.split('|')
        query = f"album:{title} artist:{artist}"

        try:
            results = self.spotify.search(q=query, type='album', limit=1)
            if results['albums']['items']:
                album = results['albums']['items'][0]
                album_id = album['id']

                # Obtener todas las canciones del álbum
                tracks = self.spotify.album_tracks(album_id)
                track_uris = []

                for track in tracks['items']:
                    track_uris.append(track['uri'])

                return track_uris
        except Exception as e:
            logger.warning(f"Error buscando en Spotify '{artist} - {title}': {e}")

        return []

    def create_or_update_playlist(self, name: str, album_keys: Set[str]) -> None:
        """Crea o actualiza una playlist en Spotify"""
        logger.info(f"Procesando playlist: {name}")

        # Obtener usuario actual
        user_id = self.spotify.current_user()['id']

        # Buscar si la playlist ya existe
        playlist_id = None
        playlists = self.spotify.current_user_playlists()
        for playlist in playlists['items']:
            if playlist['name'] == name and playlist['owner']['id'] == user_id:
                playlist_id = playlist['id']
                logger.info(f"Playlist '{name}' encontrada, será actualizada")
                break

        # Crear playlist si no existe
        if not playlist_id:
            playlist = self.spotify.user_playlist_create(
                user_id,
                name,
                public=False,
                description=f"Generada automáticamente desde Discogs - {len(album_keys)} álbumes"
            )
            playlist_id = playlist['id']
            logger.info(f"Playlist '{name}' creada")

        # Limpiar playlist existente
        self.spotify.user_playlist_replace_tracks(user_id, playlist_id, [])

        # Buscar álbumes en Spotify y recopilar todas las canciones
        all_tracks = []
        found_albums = 0
        not_found = []

        for i, album_key in enumerate(album_keys):
            logger.info(f"Buscando álbum {i+1}/{len(album_keys)}: {album_key.replace('|', ' - ')}")

            track_uris = self.search_spotify_album(album_key)
            if track_uris:
                all_tracks.extend(track_uris)
                found_albums += 1
                logger.debug(f"Encontradas {len(track_uris)} canciones del álbum")
            else:
                not_found.append(album_key.replace('|', ' - '))

            time.sleep(0.1)  # Rate limiting

        # Añadir canciones a la playlist (Spotify permite máximo 100 por llamada)
        if all_tracks:
            for i in range(0, len(all_tracks), 100):
                batch = all_tracks[i:i+100]
                try:
                    self.spotify.user_playlist_add_tracks(user_id, playlist_id, batch)
                    logger.info(f"Añadidas {len(batch)} canciones a la playlist")
                except Exception as e:
                    logger.error(f"Error añadiendo batch de canciones: {e}")

        logger.info(f"Playlist '{name}' completada:")
        logger.info(f"  - Álbumes encontrados en Spotify: {found_albums}")
        logger.info(f"  - Canciones totales añadidas: {len(all_tracks)}")
        logger.info(f"  - Álbumes no encontrados: {len(not_found)}")

        if not_found:
            logger.info("Álbumes no encontrados en Spotify:")
            for album in not_found[:10]:  # Mostrar solo los primeros 10
                logger.info(f"  - {album}")
            if len(not_found) > 10:
                logger.info(f"  - ... y {len(not_found) - 10} más")

    def sync_playlists(self):
        """Sincroniza colección y wantlist con playlists de Spotify"""
        logger.info("Iniciando sincronización de playlists...")

        # Obtener datos de Discogs
        collection_albums = self.get_discogs_collection()
        wantlist_albums = self.get_discogs_wantlist()

        if not collection_albums and not wantlist_albums:
            logger.error("No se pudieron obtener datos de Discogs")
            return

        # Crear/actualizar playlists
        if collection_albums:
            logger.info(f"Creando playlist de colección con {len(collection_albums)} álbumes")
            self.create_or_update_playlist("Mi Colección Discogs", collection_albums)
        else:
            logger.warning("No se encontraron álbumes en la colección")

        if wantlist_albums:
            logger.info(f"Creando playlist de wantlist con {len(wantlist_albums)} álbumes")
            self.create_or_update_playlist("Mi Wantlist Discogs", wantlist_albums)
        else:
            logger.warning("No se encontraron álbumes en la wantlist")

        logger.info("Sincronización completada!")

def main():
    """Función principal"""
    import argparse

    parser = argparse.ArgumentParser(description='Sincronizar colección y wantlist de Discogs con playlists de Spotify')
    parser.add_argument('--clear-cache', action='store_true',
                       help='Elimina el caché de Spotify para permitir login con nuevo usuario')

    args = parser.parse_args()

    try:
        syncer = DiscogsSpotifySync(clear_spotify_cache=args.clear_cache)
        syncer.sync_playlists()
    except Exception as e:
        logger.error(f"Error durante la ejecución: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
