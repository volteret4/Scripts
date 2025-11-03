#!/usr/bin/env python3
"""
Script para crear una playlist de Spotify con toda la música de una base de datos SQLite
"""

import os
import sys
import sqlite3
from dotenv import load_dotenv, dotenv_values
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import time
from typing import List, Dict, Optional, Tuple
import logging
import glob
import argparse
from datetime import datetime
import unicodedata
import re
from pathlib import Path

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SQLiteSpotifyPlaylist:
    def __init__(self, db_path: str, clear_spotify_cache=False):
        """Inicializa el generador de playlist con credenciales y conexión a BD"""

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
            self.spotify_client_id = env_vars.get('SPOTIFY_CLIENT')
            self.spotify_client_secret = env_vars.get('SPOTIFY_SECRET')
            self.spotify_redirect_uri = env_vars.get('SPOTIFY_REDIRECT', 'http://localhost:8888/callback')


            # O alternativamente, Opción 2: usar load_dotenv con override=True
            # load_dotenv(env_file, override=True)
        else:
            print(f"Error: No se encontró .env en {env_file}", file=sys.stderr)
            # Obtener credenciales del entorno
            self.spotify_client_id = os.getenv('SPOTIFY_CLIENT')
            self.spotify_client_secret = os.getenv('SPOTIFY_SECRET')
            self.spotify_redirect_uri = os.getenv('SPOTIFY_REDIRECT', 'http://localhost:8888/callback')


        # Validar credenciales requeridas
        if not all([self.spotify_client_id, self.spotify_client_secret]):
            missing = []
            if not self.spotify_client_id: missing.append('SPOTIFY_CLIENT_ID')
            if not self.spotify_client_secret: missing.append('SPOTIFY_CLIENT_SECRET')
            raise ValueError(f"Faltan las siguientes variables de entorno: {', '.join(missing)}")

        # Conectar a la base de datos
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"No se encontró la base de datos en: {db_path}")

        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row  # Para acceder a columnas por nombre

        # Inicializar cliente de Spotify
        scope = "playlist-modify-public playlist-modify-private"
        self.spotify = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=self.spotify_client_id,
                client_secret=self.spotify_client_secret,
                redirect_uri=self.spotify_redirect_uri,
                scope=scope
            )
        )

        logger.info("Cliente de Spotify inicializado correctamente")
        logger.info(f"Conectado a la base de datos: {db_path}")

    def clear_spotify_cache(self):
        """Elimina archivos de caché de Spotify para permitir nuevo login"""
        logger.info("Buscando y eliminando archivos de caché de Spotify...")

        home_dir = os.path.expanduser("~")
        cache_patterns = [
            os.path.join(home_dir, ".cache-*"),
            os.path.join(home_dir, ".cache", "*"),
            os.path.join(home_dir, ".spotipy_cache"),
            os.path.join(os.getenv('APPDATA', ''), '.cache-*') if os.name == 'nt' else "",
        ]

        files_deleted = 0
        for pattern in cache_patterns:
            if pattern:
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

    def get_database_stats(self) -> Dict[str, int]:
        """Obtiene estadísticas de la base de datos"""
        try:
            cursor = self.conn.cursor()
            stats = {}

            # Contar artistas
            cursor.execute("SELECT COUNT(*) FROM artists")
            stats['artists'] = cursor.fetchone()[0]

            # Contar álbumes
            cursor.execute("SELECT COUNT(*) FROM albums")
            stats['albums'] = cursor.fetchone()[0]

            # Contar canciones
            cursor.execute("SELECT COUNT(*) FROM songs")
            stats['songs'] = cursor.fetchone()[0]

            # Canciones con información completa
            cursor.execute("""
                SELECT COUNT(*) FROM songs
                WHERE title IS NOT NULL
                AND artist IS NOT NULL
                AND title != ''
                AND artist != ''
            """)
            stats['songs_with_complete_info'] = cursor.fetchone()[0]

            return stats
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {e}")
            return {}

    def get_songs_from_database(self, limit: Optional[int] = None, filter_origen: Optional[str] = None) -> List[Dict]:
        """Obtiene canciones de la base de datos incluyendo enlaces de Spotify existentes"""
        try:
            cursor = self.conn.cursor()

            # Primero, verificar qué tablas y campos existen realmente
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            logger.debug(f"Tablas disponibles: {tables}")

            # Verificar si existe la tabla song_links
            has_song_links = 'song_links' in tables

            if has_song_links:
                # Verificar estructura de song_links
                cursor.execute("PRAGMA table_info(song_links)")
                song_links_cols = [row[1] for row in cursor.fetchall()]
                logger.debug(f"Columnas en song_links: {song_links_cols}")

            # Verificar estructura de albums
            cursor.execute("PRAGMA table_info(albums)")
            albums_cols = [row[1] for row in cursor.fetchall()]
            logger.debug(f"Columnas en albums: {albums_cols}")

            # Construir query adaptativa basada en las columnas disponibles
            if has_song_links and 'spotify_url' in song_links_cols:
                query = """
                    SELECT
                        s.id,
                        s.title,
                        s.artist,
                        s.album,
                        s.genre,
                        s.date as year,
                        s.duration,
                        s.origen,
                        a.name as album_artist_name,
                        -- Enlaces de Spotify de la canción
                        sl.spotify_url as song_spotify_url,
                        sl.spotify_id as song_spotify_id,
                        -- Enlaces de Spotify del álbum
                        al.spotify_url as album_spotify_url,
                        al.spotify_id as album_spotify_id,
                        -- Enlaces de Spotify del artista
                        ar.spotify_url as artist_spotify_url
                    FROM songs s
                    LEFT JOIN albums al ON s.album = al.name
                    LEFT JOIN artists ar ON al.artist_id = ar.id OR s.artist = ar.name
                    LEFT JOIN song_links sl ON s.id = sl.song_id
                    WHERE s.title IS NOT NULL
                    AND s.artist IS NOT NULL
                    AND s.title != ''
                    AND s.artist != ''
                """
            else:
                # Query simplificada si no hay song_links o no tiene los campos esperados
                logger.warning("Tabla song_links no encontrada o sin campos de Spotify esperados")
                query = """
                    SELECT
                        s.id,
                        s.title,
                        s.artist,
                        s.album,
                        s.genre,
                        s.date as year,
                        s.duration,
                        s.origen,
                        a.name as album_artist_name,
                        -- Solo enlaces del álbum si existen
                        al.spotify_url as album_spotify_url,
                        al.spotify_id as album_spotify_id,
                        -- Solo enlaces del artista si existen
                        ar.spotify_url as artist_spotify_url
                    FROM songs s
                    LEFT JOIN albums al ON s.album = al.name
                    LEFT JOIN artists ar ON al.artist_id = ar.id OR s.artist = ar.name
                    WHERE s.title IS NOT NULL
                    AND s.artist IS NOT NULL
                    AND s.title != ''
                    AND s.artist != ''
                """

            params = []

            # Filtrar por origen si se especifica
            if filter_origen:
                query += " AND s.origen = ?"
                params.append(filter_origen)

            # Ordenar por artista y álbum
            query += " ORDER BY s.artist, s.album, s.track_number"

            # Aplicar límite si se especifica
            if limit:
                query += " LIMIT ?"
                params.append(limit)

            cursor.execute(query, params)
            results = cursor.fetchall()

            songs = []
            songs_with_spotify_links = 0
            albums_with_spotify_links = 0
            artists_with_spotify_links = 0

            for row in results:
                song = {
                    'id': row['id'],
                    'title': row['title'],
                    'artist': row['artist'],
                    'album': row['album'] or 'Unknown Album',
                    'genre': row['genre'],
                    'year': row['year'],
                    'duration': row['duration'],
                    'origen': row['origen'],
                    'album_artist': row['album_artist_name'] or row['artist'],
                    # Enlaces de Spotify (pueden ser None si no existen las columnas)
                    'song_spotify_url': row.get('song_spotify_url'),
                    'song_spotify_id': row.get('song_spotify_id'),
                    'album_spotify_url': row.get('album_spotify_url'),
                    'album_spotify_id': row.get('album_spotify_id'),
                    'artist_spotify_url': row.get('artist_spotify_url')
                }

                # Contar enlaces disponibles
                if song.get('song_spotify_url') or song.get('song_spotify_id'):
                    songs_with_spotify_links += 1
                if song.get('album_spotify_url') or song.get('album_spotify_id'):
                    albums_with_spotify_links += 1
                if song.get('artist_spotify_url'):
                    artists_with_spotify_links += 1

                songs.append(song)

            logger.info(f"Obtenidas {len(songs)} canciones de la base de datos")
            logger.info(f"  - Canciones con enlaces directos de Spotify: {songs_with_spotify_links}")
            logger.info(f"  - Álbumes con enlaces directos de Spotify: {albums_with_spotify_links}")
            logger.info(f"  - Artistas con enlaces de Spotify: {artists_with_spotify_links}")
            logger.info(f"  - Canciones que requerirán búsqueda: {len(songs) - songs_with_spotify_links}")

            # Mostrar algunos ejemplos de enlaces encontrados para debug
            if songs_with_spotify_links > 0:
                logger.debug("Ejemplos de canciones con enlaces directos:")
                count = 0
                for song in songs:
                    if (song.get('song_spotify_url') or song.get('song_spotify_id')) and count < 3:
                        logger.debug(f"  - {song['artist']} - {song['title']}: {song.get('song_spotify_url') or song.get('song_spotify_id')}")
                        count += 1

            return songs

        except Exception as e:
            logger.error(f"Error obteniendo canciones: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []

    def normalize_text(self, text: str) -> str:
        """Normaliza texto removiendo acentos, mayúsculas y caracteres especiales"""
        if not text:
            return ""

        # Convertir a minúsculas
        text = text.lower()

        # Remover acentos y diacríticos
        text = unicodedata.normalize('NFD', text)
        text = ''.join(char for char in text if unicodedata.category(char) != 'Mn')

        # Remover caracteres especiales pero mantener espacios y letras/números
        text = re.sub(r'[^\w\s]', ' ', text)

        # Normalizar espacios múltiples a uno solo
        text = re.sub(r'\s+', ' ', text).strip()

        return text


    def extract_spotify_track_id(url_or_id: str) -> Optional[str]:
        """
        Extrae el track ID de una URL o ID de Spotify

        Args:
            url_or_id: URL de Spotify, URI de Spotify, o ID directo

        Returns:
            Track ID de Spotify (22 caracteres base62) o None si no se encuentra

        Examples:
            >>> extract_spotify_track_id("4iV5W9uYEdYUVa79Axb7Rh")
            "4iV5W9uYEdYUVa79Axb7Rh"

            >>> extract_spotify_track_id("https://open.spotify.com/track/4iV5W9uYEdYUVa79Axb7Rh")
            "4iV5W9uYEdYUVa79Axb7Rh"

            >>> extract_spotify_track_id("spotify:track:4iV5W9uYEdYUVa79Axb7Rh")
            "4iV5W9uYEdYUVa79Axb7Rh"
        """
        if not url_or_id:
            return None

        # Si ya es un ID de Spotify (formato base62, 22 caracteres)
        if re.match(r'^[0-9A-Za-z]{22}$', url_or_id):
            return url_or_id

        # Patrones para diferentes formatos de URL/URI de Spotify
        spotify_patterns = [
            r'spotify:track:([0-9A-Za-z]{22})',
            r'open\.spotify\.com/track/([0-9A-Za-z]{22})',
            r'spotify\.com/track/([0-9A-Za-z]{22})'
        ]

        for pattern in spotify_patterns:
            match = re.search(pattern, url_or_id)
            if match:
                return match.group(1)

        return None


    def extract_spotify_album_id(url_or_id: str) -> Optional[str]:
        """
        Extrae el album ID de una URL o ID de Spotify

        Args:
            url_or_id: URL de Spotify, URI de Spotify, o ID directo

        Returns:
            Album ID de Spotify (22 caracteres base62) o None si no se encuentra
        """
        if not url_or_id:
            return None

        # Si ya es un ID de Spotify (formato base62, 22 caracteres)
        if re.match(r'^[0-9A-Za-z]{22}$', url_or_id):
            return url_or_id

        # Patrones para diferentes formatos de URL/URI de álbum
        spotify_patterns = [
            r'spotify:album:([0-9A-Za-z]{22})',
            r'open\.spotify\.com/album/([0-9A-Za-z]{22})',
            r'spotify\.com/album/([0-9A-Za-z]{22})'
        ]

        for pattern in spotify_patterns:
            match = re.search(pattern, url_or_id)
            if match:
                return match.group(1)

        return None

    def extract_spotify_artist_id(url_or_id: str) -> Optional[str]:
        """
        Extrae el artist ID de una URL o ID de Spotify

        Args:
            url_or_id: URL de Spotify, URI de Spotify, o ID directo

        Returns:
            Artist ID de Spotify (22 caracteres base62) o None si no se encuentra
        """
        if not url_or_id:
            return None

        # Si ya es un ID de Spotify (formato base62, 22 caracteres)
        if re.match(r'^[0-9A-Za-z]{22}$', url_or_id):
            return url_or_id

        # Patrones para diferentes formatos de URL/URI de artista
        spotify_patterns = [
            r'spotify:artist:([0-9A-Za-z]{22})',
            r'open\.spotify\.com/artist/([0-9A-Za-z]{22})',
            r'spotify\.com/artist/([0-9A-Za-z]{22})'
        ]

        for pattern in spotify_patterns:
            match = re.search(pattern, url_or_id)
            if match:
                return match.group(1)

        return None

    def create_spotify_track_uri(track_id: str) -> str:
        """
        Crea un URI de track de Spotify a partir de un ID

        Args:
            track_id: ID del track (22 caracteres)

        Returns:
            URI de Spotify en formato "spotify:track:ID"
        """
        return f"spotify:track:{track_id}"

    def create_spotify_album_uri(album_id: str) -> str:
        """
        Crea un URI de álbum de Spotify a partir de un ID

        Args:
            album_id: ID del álbum (22 caracteres)

        Returns:
            URI de Spotify en formato "spotify:album:ID"
        """
        return f"spotify:album:{album_id}"

    def create_spotify_artist_uri(artist_id: str) -> str:
        """
        Crea un URI de artista de Spotify a partir de un ID

        Args:
            artist_id: ID del artista (22 caracteres)

        Returns:
            URI de Spotify en formato "spotify:artist:ID"
        """
        return f"spotify:artist:{artist_id}"

    def validate_spotify_id(spotify_id: str) -> bool:
        """
        Valida si un string es un ID válido de Spotify

        Args:
            spotify_id: String a validar

        Returns:
            True si es un ID válido de Spotify (22 caracteres base62)
        """
        if not spotify_id:
            return False

        return bool(re.match(r'^[0-9A-Za-z]{22}$', spotify_id))

    def detect_spotify_entity_type(url_or_uri: str) -> Optional[str]:
        """
        Detecta el tipo de entidad de Spotify (track, album, artist) de una URL o URI

        Args:
            url_or_uri: URL o URI de Spotify

        Returns:
            'track', 'album', 'artist' o None si no se puede determinar
        """
        if not url_or_uri:
            return None

        # Patrones para detectar tipo de entidad
        if re.search(r'(spotify:track:|/track/)', url_or_uri):
            return 'track'
        elif re.search(r'(spotify:album:|/album/)', url_or_uri):
            return 'album'
        elif re.search(r'(spotify:artist:|/artist/)', url_or_uri):
            return 'artist'

        return None

    # Función principal para extraer cualquier ID de Spotify
    def extract_spotify_id(url_or_id: str) -> Optional[tuple[str, str]]:
        """
        Extrae ID y tipo de una URL/URI de Spotify

        Args:
            url_or_id: URL, URI o ID de Spotify

        Returns:
            Tupla (id, type) o None si no es válido

        Example:
            >>> extract_spotify_id("https://open.spotify.com/track/4iV5W9uYEdYUVa79Axb7Rh")
            ("4iV5W9uYEdYUVa79Axb7Rh", "track")
        """
        if not url_or_id:
            return None

        entity_type = detect_spotify_entity_type(url_or_id)

        if entity_type == 'track':
            track_id = extract_spotify_track_id(url_or_id)
            return (track_id, 'track') if track_id else None
        elif entity_type == 'album':
            album_id = extract_spotify_album_id(url_or_id)
            return (album_id, 'album') if album_id else None
        elif entity_type == 'artist':
            artist_id = extract_spotify_artist_id(url_or_id)
            return (artist_id, 'artist') if artist_id else None

        return None



    def get_tracks_from_spotify_album(self, album_spotify_id: str, target_song: Dict) -> Optional[str]:
        """Busca una canción específica dentro de un álbum de Spotify"""
        try:
            album_id = self.extract_spotify_track_id(album_spotify_id)
            if not album_id:
                return None

            # Obtener todas las canciones del álbum
            tracks = self.spotify.album_tracks(album_id, limit=50)

            for track in tracks['items']:
                if self.validate_spotify_match(target_song, track):
                    logger.debug(f"✅ Canción encontrada en álbum: {track['name']}")
                    return track['uri']

            logger.debug(f"❌ Canción no encontrada en el álbum de Spotify")
            return None

        except Exception as e:
            logger.debug(f"Error buscando en álbum de Spotify: {e}")
            return None

    def get_spotify_track_uri(self, song: Dict) -> Optional[str]:
        """Obtiene el URI de Spotify de una canción, priorizando enlaces existentes"""

        # 1. PRIORIDAD MÁXIMA: Enlace directo de la canción
        if song.get('song_spotify_url') or song.get('song_spotify_id'):
            spotify_track_id = self.extract_spotify_track_id(
                song.get('song_spotify_url') or song.get('song_spotify_id')
            )
            if spotify_track_id:
                track_uri = f"spotify:track:{spotify_track_id}"
                logger.debug(f"🔗 Usando enlace directo de canción: {song['artist']} - {song['title']}")

                # Opcional: Validar que el enlace sigue siendo válido
                try:
                    track_info = self.spotify.track(spotify_track_id)
                    if self.validate_spotify_match(song, track_info):
                        return track_uri
                    else:
                        logger.warning(f"⚠️ El enlace directo no coincide con la canción: {song['artist']} - {song['title']}")
                except Exception as e:
                    logger.warning(f"⚠️ Error validando enlace directo: {e}")
                    # Continuar con otros métodos

        # 2. SEGUNDA PRIORIDAD: Buscar en el álbum si tenemos enlace del álbum
        if song.get('album_spotify_url') or song.get('album_spotify_id'):
            album_link = song.get('album_spotify_url') or song.get('album_spotify_id')
            track_uri = self.get_tracks_from_spotify_album(album_link, song)
            if track_uri:
                logger.debug(f"📀 Encontrado en álbum conocido: {song['artist']} - {song['title']}")
                return track_uri

        # 3. ÚLTIMA OPCIÓN: Búsqueda por texto en Spotify
        logger.debug(f"🔍 Buscando por texto: {song['artist']} - {song['title']}")
        return self.search_spotify_track(song)
        """Comprueba si dos textos son lo suficientemente similares"""
        norm1 = self.normalize_text(text1)
        norm2 = self.normalize_text(text2)

        # Coincidencia exacta
        if norm1 == norm2:
            return True

        # Si uno está contenido en el otro (para casos de títulos extendidos)
        if norm1 and norm2:
            shorter = min(norm1, norm2, key=len)
            longer = max(norm1, norm2, key=len)

            # Si el texto más corto está contenido en el más largo
            if len(shorter) > 3 and shorter in longer:
                return True

            # Calcular similitud simple basada en palabras comunes
            words1 = set(norm1.split())
            words2 = set(norm2.split())

            if not words1 or not words2:
                return False

            # Palabras en común
            common_words = words1 & words2
            total_words = words1 | words2

            similarity = len(common_words) / len(total_words) if total_words else 0
            return similarity >= similarity_threshold

        return False

    def validate_spotify_match(self, original_song: Dict, spotify_track: Dict) -> bool:
        """Valida si un track de Spotify coincide con nuestra canción original"""
        try:
            # Obtener datos del track de Spotify
            spotify_title = spotify_track.get('name', '')
            spotify_artists = [artist['name'] for artist in spotify_track.get('artists', [])]
            spotify_album = spotify_track.get('album', {}).get('name', '')

            # Datos de nuestra canción
            original_title = original_song.get('title', '')
            original_artist = original_song.get('artist', '')
            original_album = original_song.get('album', '')

            # Verificar título
            title_match = self.texts_match(original_title, spotify_title)
            if not title_match:
                logger.debug(f"Título no coincide: '{original_title}' vs '{spotify_title}'")
                return False

            # Verificar artista (debe coincidir con al menos uno de los artistas de Spotify)
            artist_match = False
            for spotify_artist in spotify_artists:
                if self.texts_match(original_artist, spotify_artist):
                    artist_match = True
                    break

            if not artist_match:
                logger.debug(f"Artista no coincide: '{original_artist}' vs {spotify_artists}")
                return False

            # Opcional: verificar álbum (menos estricto porque puede variar mucho)
            if original_album and original_album != 'Unknown Album' and spotify_album:
                album_match = self.texts_match(original_album, spotify_album, similarity_threshold=0.6)
                if album_match:
                    logger.debug(f"✅ Coincidencia completa encontrada (incluye álbum)")
                else:
                    logger.debug(f"⚠️  Álbum no coincide pero título y artista sí: '{original_album}' vs '{spotify_album}'")

            logger.debug(f"✅ Coincidencia válida: {original_artist} - {original_title}")
            return True

        except Exception as e:
            logger.debug(f"Error validando coincidencia: {e}")
            return False
        """Busca una canción en Spotify y retorna su URI"""
        try:
            # Construir query de búsqueda
            title = song['title'].replace('"', '').replace("'", "")
            artist = song['artist'].replace('"', '').replace("'", "")
            album = song['album'].replace('"', '').replace("'", "") if song['album'] else ""

            # Intentar diferentes estrategias de búsqueda
            search_queries = [
                f'track:"{title}" artist:"{artist}"',
                f'"{title}" "{artist}"',
                f'{title} {artist}',
            ]

            # Si tenemos álbum, añadir búsquedas con álbum
            if album and album != 'Unknown Album':
                search_queries.insert(0, f'track:"{title}" artist:"{artist}" album:"{album}"')

            for query in search_queries:
                try:
                    results = self.spotify.search(q=query, type='track', limit=1)
                    if results['tracks']['items']:
                        track = results['tracks']['items'][0]
                        logger.debug(f"Encontrado: {artist} - {title} -> {track['artists'][0]['name']} - {track['name']}")
                        return track['uri']
                except Exception as search_error:
                    logger.debug(f"Error en búsqueda '{query}': {search_error}")
                    continue

            return None

        except Exception as e:
            logger.warning(f"Error buscando '{song['artist']} - {song['title']}': {e}")
            return None

    def create_playlist(self, name: str, songs: List[Dict], batch_size: int = 1000) -> bool:
        """Crea una playlist de Spotify con las canciones proporcionadas"""
        try:
            # Obtener usuario actual
            user_id = self.spotify.current_user()['id']
            logger.info(f"Usuario de Spotify: {user_id}")

            # Buscar si la playlist ya existe
            playlist_id = None
            playlists = self.spotify.current_user_playlists(limit=50)

            while playlists:
                for playlist in playlists['items']:
                    if playlist['name'] == name and playlist['owner']['id'] == user_id:
                        playlist_id = playlist['id']
                        logger.info(f"Playlist '{name}' encontrada, será actualizada")
                        break

                if playlist_id or not playlists['next']:
                    break

                playlists = self.spotify.next(playlists)

            # Crear playlist si no existe
            if not playlist_id:
                description = f"Mi biblioteca musical completa - {len(songs)} canciones - Generada el {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                playlist = self.spotify.user_playlist_create(
                    user_id,
                    name,
                    public=False,
                    description=description
                )
                playlist_id = playlist['id']
                logger.info(f"Playlist '{name}' creada")
            else:
                # Limpiar playlist existente
                self.spotify.user_playlist_replace_tracks(user_id, playlist_id, [])
                logger.info(f"Playlist '{name}' limpiada")

            # Procesar canciones en lotes
            found_tracks = []
            not_found = []
            total_songs = len(songs)

            for i, song in enumerate(songs, 1):
                if i % 100 == 0 or i == total_songs:
                    logger.info(f"Procesando canción {i}/{total_songs}: {song['artist']} - {song['title']}")

                spotify_uri = self.search_spotify_track(song)
                if spotify_uri:
                    found_tracks.append(spotify_uri)
                else:
                    not_found.append(f"{song['artist']} - {song['title']}")

                # Rate limiting
                time.sleep(0.1)

                # Procesar en lotes para evitar memory issues
                if len(found_tracks) >= batch_size:
                    self._add_tracks_to_playlist(user_id, playlist_id, found_tracks)
                    found_tracks = []

            # Añadir últimos tracks si quedan
            if found_tracks:
                self._add_tracks_to_playlist(user_id, playlist_id, found_tracks)

            # Actualizar descripción con estadísticas
            total_found = len(songs) - len(not_found)
            new_description = f"Mi biblioteca musical - {total_found} canciones encontradas de {len(songs)} totales - Actualizada el {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            self.spotify.user_playlist_change_details(playlist_id, description=new_description)

            # Mostrar estadísticas
            logger.info(f"✅ Playlist '{name}' completada:")
            logger.info(f"  - Canciones encontradas en Spotify: {total_found}")
            logger.info(f"  - Canciones no encontradas: {len(not_found)}")
            logger.info(f"  - Porcentaje de éxito: {(total_found/len(songs)*100):.1f}%")

            # Mostrar algunas canciones no encontradas
            if not_found:
                logger.info("Primeras 10 canciones no encontradas:")
                for song in not_found[:10]:
                    logger.info(f"  - {song}")
                if len(not_found) > 10:
                    logger.info(f"  - ... y {len(not_found) - 10} más")

            return True

        except Exception as e:
            logger.error(f"Error creando playlist: {e}")
            return False

    def _add_tracks_to_playlist(self, user_id: str, playlist_id: str, track_uris: List[str]):
        """Añade tracks a la playlist en lotes de 100 (límite de Spotify)"""
        for i in range(0, len(track_uris), 100):
            batch = track_uris[i:i+100]
            try:
                self.spotify.user_playlist_add_tracks(user_id, playlist_id, batch)
                logger.debug(f"Añadidas {len(batch)} canciones a la playlist")
            except Exception as e:
                logger.error(f"Error añadiendo lote de canciones: {e}")

    def get_available_origenes(self) -> List[str]:
        """Obtiene los valores únicos de 'origen' disponibles en la BD"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT DISTINCT origen FROM songs WHERE origen IS NOT NULL ORDER BY origen")
            origenes = [row[0] for row in cursor.fetchall()]
            return origenes
        except Exception as e:
            logger.error(f"Error obteniendo orígenes: {e}")
            return []

    def close(self):
        """Cierra la conexión a la base de datos"""
        if self.conn:
            self.conn.close()

def main():
    """Función principal"""
    parser = argparse.ArgumentParser(description='Crear playlist de Spotify desde base de datos SQLite')
    parser.add_argument('--db-path', help='Ruta a la base de datos SQLite')
    parser.add_argument('--playlist-name', default='Mi Biblioteca Musical',
                       help='Nombre de la playlist (default: "Mi Biblioteca Musical")')
    parser.add_argument('--limit', type=int, help='Limitar número de canciones a procesar')
    parser.add_argument('--origen', help='Filtrar por origen específico')
    parser.add_argument('--list-origenes', action='store_true',
                       help='Mostrar valores de origen disponibles y salir')
    parser.add_argument('--clear-cache', action='store_true',
                       help='Elimina el caché de Spotify para permitir login con nuevo usuario')
    parser.add_argument('--stats', action='store_true',
                       help='Mostrar estadísticas de la base de datos y salir')
    parser.add_argument('--debug', action='store_true',
                       help='Activar logging detallado para debugging')
    parser.add_argument('--strict-matching', action='store_true',
                       help='Usar validación estricta de coincidencias (recomendado)')

    args = parser.parse_args()

    # Configurar nivel de logging
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        # Crear instancia del generador
        generator = SQLiteSpotifyPlaylist(args.db_path, clear_spotify_cache=args.clear_cache)

        # Configurar validación estricta por defecto
        generator.strict_matching = True  # Por defecto siempre estricto

        # Mostrar estadísticas si se solicita
        if args.stats:
            stats = generator.get_database_stats()
            logger.info("📊 Estadísticas de la base de datos:")
            logger.info(f"  - Artistas: {stats.get('artists', 0):,}")
            logger.info(f"  - Álbumes: {stats.get('albums', 0):,}")
            logger.info(f"  - Canciones totales: {stats.get('songs', 0):,}")
            logger.info(f"  - Canciones con info completa: {stats.get('songs_with_complete_info', 0):,}")
            generator.close()
            return

        # Listar orígenes disponibles si se solicita
        if args.list_origenes:
            origenes = generator.get_available_origenes()
            if origenes:
                logger.info("🎵 Orígenes disponibles en la base de datos:")
                for origen in origenes:
                    logger.info(f"  - {origen}")
            else:
                logger.info("No se encontraron valores de origen en la base de datos")
            generator.close()
            return

        # Obtener canciones de la base de datos
        logger.info("🎵 Obteniendo canciones de la base de datos...")
        songs = generator.get_songs_from_database(limit=args.limit, filter_origen=args.origen)

        if not songs:
            logger.error("No se encontraron canciones en la base de datos")
            generator.close()
            sys.exit(1)

        # Mostrar información sobre la validación
        logger.info("🔍 Validación de coincidencias activada - Solo se añadirán canciones que coincidan exactamente")

        # Crear playlist
        logger.info(f"🎧 Creando playlist '{args.playlist_name}'...")
        success = generator.create_playlist(args.playlist_name, songs)

        generator.close()

        if success:
            logger.info("✅ Proceso completado exitosamente")
        else:
            logger.error("❌ Error durante la creación de la playlist")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Error durante la ejecución: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
