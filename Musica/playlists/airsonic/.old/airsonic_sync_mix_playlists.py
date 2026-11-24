#!/usr/bin/env python3
"""
Sincronizador de Playlists M3U a Airsonic (Compatible con Cron) - VERSIÓN CORREGIDA
Sincroniza playlists locales .m3u con Airsonic usando sincronización incremental.
Solo añade canciones nuevas y elimina las que ya no existen.

CORRECCIÓN: Evita agregar canciones incorrectas con búsquedas más estrictas.
"""

import os
import re
import sqlite3
import requests
import hashlib
import json
import argparse
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Set
from urllib.parse import urlencode
import logging
import sys
from dotenv import load_dotenv

# Intentar importar mutagen para leer metadata
try:
    from mutagen import File as MutagenFile
    from mutagen.easyid3 import EasyID3
    from mutagen.mp3 import MP3
    from mutagen.flac import FLAC
    from mutagen.mp4 import MP4
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False
    print("⚠️  Advertencia: mutagen no está instalado. No se podrá leer metadata de archivos.", file=sys.stderr)
    print("   Instala con: pip install mutagen", file=sys.stderr)

# Configuración de rutas
script_dir = Path(__file__).parent.absolute()

# Cargar variables de entorno desde la carpeta del script
env_file = script_dir / ".env"
if env_file.exists():
    load_dotenv(env_file)
else:
    print(f"Error: No se encontró .env en {env_file}", file=sys.stderr)
    sys.exit(1)

# Configurar rutas desde variables de entorno
CACHE_DIR = Path(os.getenv('CACHE_DIR', script_dir / ".content/cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Rutas configurables
DEFAULT_DB_PATH = os.getenv('DB_PATH', str(script_dir / "music.db"))
DEFAULT_M3U_FOLDER = os.getenv('M3U_FOLDER', str(script_dir))
DEFAULT_DATA_DIR = os.getenv('DATA_DIR', str(CACHE_DIR))

class AirsonicSyncer:
    def __init__(self, db_path: str, interactive: bool = True, data_dir: str = None):
        """
        Inicializa el sincronizador de playlists para Airsonic.

        Args:
            db_path: Ruta a la base de datos SQLite
            interactive: Si False, no solicita input del usuario (para cron)
            data_dir: Directorio para archivos de estado y cache
        """
        self.db_path = db_path
        self.interactive = interactive

        # Configurar directorio de datos PRIMERO
        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            self.data_dir = Path(DEFAULT_DATA_DIR)

        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Archivos de estado en el directorio configurado
        self.sync_state_file = self.data_dir / "airsonic_sync_state.json"
        self.song_cache_file = self.data_dir / "airsonic_song_cache.json"

        # IMPORTANTE: Configurar logging ANTES de usarlo
        log_level = logging.INFO if interactive else logging.WARNING
        log_handlers = [logging.FileHandler(self.data_dir / 'airsonic_sync.log')]
        if interactive:
            log_handlers.append(logging.StreamHandler())

        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=log_handlers,
            force=True
        )
        # CREAR EL LOGGER ANTES DE USARLO
        self.logger = logging.getLogger(__name__)

        # Configuración de Airsonic desde variables de entorno
        self.airsonic_url = os.getenv('AIRSONIC_URL', 'http://localhost:4040')
        self.airsonic_user = os.getenv('AIRSONIC_USER')
        self.airsonic_password = os.getenv('AIRSONIC_PASSWORD')
        self.airsonic_api_version = os.getenv('AIRSONIC_API_VERSION', '1.16.1')

        if not self.airsonic_user or not self.airsonic_password:
            self.logger.error("Error: AIRSONIC_USER y AIRSONIC_PASSWORD deben estar configurados en .env")
            self.logger.error("Ejemplo en .env:")
            self.logger.error("AIRSONIC_URL=http://localhost:4040")
            self.logger.error("AIRSONIC_USER=admin")
            self.logger.error("AIRSONIC_PASSWORD=tu_password")
            sys.exit(1)

        # Configurar autenticación
        self.auth_params = {
            'u': self.airsonic_user,
            'p': self.airsonic_password,
            'v': self.airsonic_api_version,
            'c': 'PlaylistSyncer',
            'f': 'json'
        }

        # Verificar conexión
        if not self._test_connection():
            self.logger.error("No se pudo conectar a Airsonic")
            sys.exit(1)

        # Cargar estado de sincronización
        self.sync_state = self._load_sync_state()

        # Cache para búsquedas
        self._song_cache = {}
        self._load_song_cache()

        # MEJORAR LÓGICA DE CACHE: Solo reconstruir si realmente es necesario
        cache_needs_rebuild = False
        cache_status = ""

        if not self._song_cache:
            cache_needs_rebuild = True
            cache_status = "Cache vacío"
        elif self._is_cache_stale():
            cache_needs_rebuild = True
            cache_status = "Cache obsoleto (>24h)"
        else:
            cache_status = f"Cache válido con {len(self._song_cache)} entradas"

        if interactive:
            print(f"📁 Directorio de datos: {self.data_dir}")
            print(f"💾 Archivo de cache: {self.song_cache_file}")
            print(f"📊 Estado del cache: {cache_status}")

        self.logger.info(f"Inicializado - {cache_status}")

        # Solo reconstruir cache si es necesario
        if cache_needs_rebuild:
            if interactive:
                print("🔨 Reconstruyendo cache de canciones...")
            self.logger.info("Reconstruyendo cache de canciones")
            self._build_song_cache()
        else:
            if interactive:
                print("✅ Usando cache existente")
            self.logger.info("Usando cache existente")

    def _test_connection(self) -> bool:
        """Verifica la conexión con Airsonic"""
        try:
            response = self._make_request('ping')
            if response and response.get('status') == 'ok':
                self.logger.info(f"Conectado a Airsonic: {self.airsonic_url}")
                return True
            else:
                self.logger.error(f"Error en respuesta de Airsonic: {response}")
                return False
        except Exception as e:
            self.logger.error(f"Error conectando a Airsonic: {e}")
            return False

    def _make_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Realiza una petición a la API de Airsonic con mejor manejo de errores"""
        try:
            url = f"{self.airsonic_url}/rest/{endpoint}"
            request_params = self.auth_params.copy()
            if params:
                request_params.update(params)

            self.logger.debug(f"Petición a {endpoint} con parámetros: {list(request_params.keys())}")

            response = requests.get(url, params=request_params, timeout=30)
            response.raise_for_status()

            data = response.json()

            if 'subsonic-response' in data:
                subsonic_response = data['subsonic-response']
                if subsonic_response.get('status') == 'ok':
                    return subsonic_response
                else:
                    error = subsonic_response.get('error', {})
                    error_code = error.get('code', 0)
                    error_message = error.get('message', 'Error desconocido')
                    self.logger.error(f"Error de Airsonic [{error_code}]: {error_message}")

                    # Errores específicos de API
                    if error_code == 10:
                        self.logger.error("Credenciales incorrectas - verifica AIRSONIC_USER y AIRSONIC_PASSWORD")
                    elif error_code == 20:
                        self.logger.error("Versión de API incompatible - verifica AIRSONIC_API_VERSION")
                    elif error_code == 30:
                        self.logger.error("Versión de API no soportada por el servidor")
                    elif error_code == 40:
                        self.logger.error("Parámetro requerido faltante")
                    elif error_code == 50:
                        self.logger.error("Cliente no autorizado")
                    elif error_code == 60:
                        self.logger.error("Prueba de servidor requerida")
                    elif error_code == 70:
                        self.logger.error("Recurso no encontrado")

                    return None

            return None

        except requests.exceptions.ConnectionError:
            self.logger.error(f"Error de conexión con {self.airsonic_url}")
            return None
        except requests.exceptions.Timeout:
            self.logger.error("Timeout en la conexión con Airsonic")
            return None
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"Error HTTP: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error en petición: {e}")
            return None

    def _load_sync_state(self) -> Dict:
        """Carga el estado de sincronización desde archivo"""
        if self.sync_state_file.exists():
            try:
                with open(self.sync_state_file, 'r') as f:
                    state = json.load(f)
                    self.logger.info(f"Estado de sincronización cargado: {len(state.get('playlists', {}))} playlists")
                    return state
            except Exception as e:
                self.logger.warning(f"Error cargando estado: {e}")

        return {
            "playlists": {},
            "last_update": datetime.now().isoformat()
        }

    def _save_sync_state(self):
        """Guarda el estado de sincronización"""
        try:
            self.sync_state["last_update"] = datetime.now().isoformat()
            with open(self.sync_state_file, 'w') as f:
                json.dump(self.sync_state, f, indent=2)
            self.logger.debug("Estado guardado correctamente")
        except Exception as e:
            self.logger.error(f"Error guardando estado: {e}")

    def _get_m3u_hash(self, m3u_path: str) -> str:
        """Calcula hash SHA256 del archivo M3U"""
        with open(m3u_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()

    def _load_song_cache(self):
        """Carga el cache de canciones desde archivo"""
        if self.song_cache_file.exists():
            try:
                with open(self.song_cache_file, 'r') as f:
                    cache_data = json.load(f)
                    self._song_cache = cache_data.get('songs', {})
                    self._cache_timestamp = cache_data.get('timestamp', 0)
                    self.logger.info(f"Cache cargado: {len(self._song_cache)} entradas")
            except Exception as e:
                self.logger.warning(f"Error cargando cache: {e}")
                self._song_cache = {}
                self._cache_timestamp = 0
        else:
            self._cache_timestamp = 0

    def _save_song_cache(self):
        """Guarda el cache de canciones"""
        try:
            cache_data = {
                'timestamp': time.time(),
                'songs': self._song_cache
            }
            with open(self.song_cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            self.logger.debug("Cache guardado correctamente")
        except Exception as e:
            self.logger.error(f"Error guardando cache: {e}")

    def _is_cache_stale(self, max_age_hours: int = 24) -> bool:
        """Verifica si el cache está obsoleto"""
        if not hasattr(self, '_cache_timestamp'):
            return True
        age_hours = (time.time() - self._cache_timestamp) / 3600
        return age_hours > max_age_hours

    def _build_song_cache(self):
        """Construye cache de todas las canciones en Airsonic"""
        self.logger.info("Construyendo cache de canciones...")

        try:
            # Obtener todas las canciones de Airsonic
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

                    # Normalizar para búsqueda - SOLO CREAR CLAVES EXACTAS
                    artist = self._normalize_text(song.get('artist', ''))
                    title = self._normalize_text(song.get('title', ''))
                    album = self._normalize_text(song.get('album', ''))

                    # CORRECCIÓN: Solo crear claves exactas para evitar falsos positivos
                    if artist and title:
                        exact_key = f"{artist}|{title}"
                        self._song_cache[exact_key] = {
                            'id': song_id,
                            'artist': song.get('artist', ''),
                            'title': song.get('title', ''),
                            'album': song.get('album', ''),
                            'path': song.get('path', '')
                        }

                        # Si hay álbum, crear otra clave con álbum
                        if album:
                            exact_key_with_album = f"{artist}|{title}|{album}"
                            self._song_cache[exact_key_with_album] = {
                                'id': song_id,
                                'artist': song.get('artist', ''),
                                'title': song.get('title', ''),
                                'album': song.get('album', ''),
                                'path': song.get('path', '')
                            }

                self._save_song_cache()
                self.logger.info(f"Cache construido: {len(songs)} canciones, {len(self._song_cache)} claves exactas")
            else:
                self.logger.warning("No se pudieron obtener canciones de Airsonic")

        except Exception as e:
            self.logger.error(f"Error construyendo cache: {e}")

    def _normalize_text(self, text: str) -> str:
        """Normaliza texto para búsqueda (lowercase, sin espacios extra)"""
        if not text:
            return ""
        return ' '.join(text.lower().strip().split())

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """
        Calcula similitud entre dos strings usando Jaro-Winkler simplificado.
        Retorna valor entre 0.0 y 1.0 (1.0 = idéntico)
        """
        str1_norm = self._normalize_text(str1)
        str2_norm = self._normalize_text(str2)

        if str1_norm == str2_norm:
            return 1.0

        if not str1_norm or not str2_norm:
            return 0.0

        # Similitud básica usando palabras en común
        words1 = set(str1_norm.split())
        words2 = set(str2_norm.split())

        if not words1 or not words2:
            return 0.0

        common = words1.intersection(words2)
        total = words1.union(words2)

        return len(common) / len(total) if total else 0.0

    def parse_m3u_file(self, m3u_path: str) -> List[Dict[str, str]]:
        """
        Parsea archivo M3U y extrae información de las canciones.
        MEJORA: Extrae metadata del archivo cuando el regex no funciona.
        """
        tracks = []

        with open(m3u_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        current_info = {}
        for line in lines:
            line = line.strip()

            # Líneas de info EXTINF
            if line.startswith('#EXTINF:'):
                match = re.search(r'#EXTINF:.*?,\s*(.+?)\s*-\s*(.+)', line)
                if match:
                    current_info = {
                        'artist': match.group(1).strip(),
                        'title': match.group(2).strip()
                    }

            # Líneas de archivo
            elif line and not line.startswith('#'):
                file_path = line

                # Si no tenemos info del EXTINF, intentar extraer del nombre de archivo
                if not current_info:
                    current_info = self._extract_info_from_filename(file_path)

                # Si aún no tenemos info completa, intentar extraer metadata del archivo
                if not current_info.get('artist') or not current_info.get('title'):
                    metadata_info = self._extract_metadata_from_file(file_path)
                    if metadata_info:
                        # Usar metadata solo si no tenemos la info
                        if not current_info.get('artist'):
                            current_info['artist'] = metadata_info.get('artist', '')
                        if not current_info.get('title'):
                            current_info['title'] = metadata_info.get('title', '')
                        if metadata_info.get('album'):
                            current_info['album'] = metadata_info['album']

                # Agregar path del archivo
                current_info['path'] = file_path

                # Solo agregar si tenemos al menos artista o título
                if current_info.get('artist') or current_info.get('title'):
                    tracks.append(current_info.copy())

                # Reset para siguiente canción
                current_info = {}

        return tracks

    def _extract_info_from_filename(self, file_path: str) -> Dict[str, str]:
        """Extrae información del nombre del archivo usando regex"""
        filename = os.path.basename(file_path)
        name_without_ext = os.path.splitext(filename)[0]

        # Patrones comunes de nombres de archivo
        patterns = [
            # Artista - Título
            r'^(.+?)\s*-\s*(.+?)$',
            # Artista_-_Título
            r'^(.+?)_-_(.+?)$',
            # [Sello] Artista - Título
            r'^\[.+?\]\s*(.+?)\s*-\s*(.+?)$',
            # (Sello) Artista - Título
            r'^\(.+?\)\s*(.+?)\s*-\s*(.+?)$',
            # Número. Artista - Título
            r'^\d+\.\s*(.+?)\s*-\s*(.+?)$',
        ]

        for pattern in patterns:
            match = re.search(pattern, name_without_ext)
            if match:
                return {
                    'artist': match.group(1).strip(),
                    'title': match.group(2).strip()
                }

        # Si no hay match, intentar dividir por guión
        if ' - ' in name_without_ext:
            parts = name_without_ext.split(' - ', 1)
            # Limpiar posibles prefijos de sello/número
            artist = re.sub(r'^\[.+?\]|\(.+?\)|\d+\.\s*', '', parts[0]).strip()
            return {
                'artist': artist,
                'title': parts[1].strip()
            }

        return {'artist': '', 'title': name_without_ext}

    def _extract_metadata_from_file(self, file_path: str) -> Optional[Dict[str, str]]:
        """
        NUEVA FUNCIÓN: Extrae metadata (ID3 tags, etc.) del archivo de audio.

        Args:
            file_path: Ruta al archivo de audio

        Returns:
            Diccionario con artist, title, album o None si no se puede leer
        """
        if not MUTAGEN_AVAILABLE:
            return None

        # Verificar si el archivo existe
        if not os.path.exists(file_path):
            self.logger.debug(f"Archivo no encontrado para metadata: {file_path}")
            return None

        try:
            audio = MutagenFile(file_path, easy=True)

            if audio is None:
                return None

            metadata = {}

            # Intentar extraer artista
            if 'artist' in audio:
                artists = audio['artist']
                metadata['artist'] = artists[0] if isinstance(artists, list) else str(artists)
            elif 'albumartist' in audio:
                artists = audio['albumartist']
                metadata['artist'] = artists[0] if isinstance(artists, list) else str(artists)

            # Intentar extraer título
            if 'title' in audio:
                titles = audio['title']
                metadata['title'] = titles[0] if isinstance(titles, list) else str(titles)

            # Intentar extraer álbum
            if 'album' in audio:
                albums = audio['album']
                metadata['album'] = albums[0] if isinstance(albums, list) else str(albums)

            if metadata.get('artist') or metadata.get('title'):
                self.logger.debug(f"Metadata extraída: {metadata.get('artist', 'N/A')} - {metadata.get('title', 'N/A')}")
                return metadata

        except Exception as e:
            self.logger.debug(f"No se pudo leer metadata de {file_path}: {e}")

        return None

    def find_track_in_db(self, track_info: Dict[str, str]) -> Optional[Dict]:
        """Busca una canción en la base de datos local"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            artist = track_info.get('artist', '')
            title = track_info.get('title', '')

            # Búsqueda exacta
            cursor.execute("""
                SELECT artist, title, album, path
                FROM tracks
                WHERE LOWER(artist) = LOWER(?) AND LOWER(title) = LOWER(?)
            """, (artist, title))

            result = cursor.fetchone()
            conn.close()

            if result:
                return {
                    'artist': result[0],
                    'title': result[1],
                    'album': result[2],
                    'path': result[3]
                }

        except Exception as e:
            self.logger.debug(f"Error buscando en DB: {e}")

        return None

    def search_track_in_airsonic(self, track_info: Dict[str, str], db_track: Optional[Dict] = None) -> Optional[str]:
        """
        FUNCIÓN CORREGIDA: Busca una canción en Airsonic con criterios más estrictos.
        Evita falsos positivos que añaden canciones incorrectas.
        """
        artist = track_info.get('artist', '').strip()
        title = track_info.get('title', '').strip()
        album = track_info.get('album', '').strip()

        if not artist and not title:
            self.logger.debug("❌ Sin artista ni título para buscar")
            return None

        # 1. BÚSQUEDA EXACTA EN CACHE
        cache_keys = []

        if artist and title:
            # Crear claves exactas normalizadas
            artist_norm = self._normalize_text(artist)
            title_norm = self._normalize_text(title)
            album_norm = self._normalize_text(album) if album else ""

            cache_keys.append(f"{artist_norm}|{title_norm}")
            if album_norm:
                cache_keys.append(f"{artist_norm}|{title_norm}|{album_norm}")

        for key in cache_keys:
            if key in self._song_cache:
                cached_song = self._song_cache[key]
                song_id = cached_song['id'] if isinstance(cached_song, dict) else cached_song

                if isinstance(song_id, list):
                    song_id = song_id[0] if song_id else None

                if song_id:
                    self.logger.debug(f"✓ Cache hit exacto: {artist} - {title}")
                    return str(song_id)

        # 2. BÚSQUEDA EN API CON CRITERIOS ESTRICTOS
        if not artist or not title:
            self.logger.debug("❌ Búsqueda en API requiere artista Y título")
            return None

        try:
            # Usar query específica con artista y título
            query = f'"{artist}" "{title}"'
            response = self._make_request('search3', {
                'query': query,
                'songCount': 5  # Reducir resultados para evitar falsos positivos
            })

            if response and 'searchResult3' in response:
                songs = response['searchResult3'].get('song', [])

                best_match = None
                best_score = 0.0
                MIN_SIMILARITY = 0.85  # Umbral mínimo de similitud

                for song in songs:
                    song_artist = song.get('artist', '')
                    song_title = song.get('title', '')
                    song_album = song.get('album', '')
                    song_id = song.get('id')

                    # CORRECCIÓN: Validar ID correctamente
                    if isinstance(song_id, list):
                        song_id = song_id[0] if song_id else None
                    if not song_id:
                        continue
                    song_id = str(song_id)

                    # Calcular similitud con criterios estrictos
                    artist_similarity = self._calculate_similarity(artist, song_artist)
                    title_similarity = self._calculate_similarity(title, song_title)

                    # Ambos deben tener alta similitud
                    if artist_similarity >= MIN_SIMILARITY and title_similarity >= MIN_SIMILARITY:
                        # Calcular puntuación total
                        score = (artist_similarity + title_similarity) / 2

                        # Bonus si coincide el álbum
                        if album and song_album:
                            album_similarity = self._calculate_similarity(album, song_album)
                            if album_similarity >= MIN_SIMILARITY:
                                score += 0.1  # Bonus por álbum correcto

                        if score > best_score:
                            best_match = song_id
                            best_score = score

                        self.logger.debug(f"🔍 Candidato: {song_artist} - {song_title} (Score: {score:.3f})")

                if best_match and best_score >= MIN_SIMILARITY:
                    self.logger.debug(f"✓ Mejor coincidencia: {artist} - {title} (Score: {best_score:.3f})")
                    return best_match
                else:
                    self.logger.debug(f"❌ No hay coincidencia suficiente (mejor score: {best_score:.3f})")

        except Exception as e:
            self.logger.debug(f"Error en búsqueda de Airsonic: {e}")

        self.logger.debug(f"❌ No encontrado: {artist} - {title}")
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
        """Crea una nueva playlist en Airsonic"""
        try:
            if not song_ids:
                self.logger.warning("No hay canciones para crear la playlist")
                return None

            # Crear playlist
            params = {
                'name': name,
                'songId': song_ids
            }

            response = self._make_request('createPlaylist', params)

            if response and 'playlist' in response:
                playlist_id = response['playlist']['id']
                self.logger.info(f"Playlist '{name}' creada con {len(song_ids)} canciones")
                return playlist_id
            else:
                self.logger.error(f"Error creando playlist: {response}")
                return None

        except Exception as e:
            self.logger.error(f"Error creando playlist: {e}")
            return None

    def update_airsonic_playlist(self, playlist_id: str, new_song_ids: Set[str], current_song_ids: Set[str]) -> bool:
        """
        Actualiza una playlist existente con sincronización incremental.
        Solo añade canciones nuevas y elimina las que ya no existen.
        """
        try:
            to_add = new_song_ids - current_song_ids
            to_remove = current_song_ids - new_song_ids

            self.logger.info(f"Cambios: +{len(to_add)} canciones, -{len(to_remove)} canciones")

            # Añadir nuevas canciones
            if to_add:
                params = {
                    'playlistId': playlist_id,
                    'songIdToAdd': list(to_add)
                }
                response = self._make_request('updatePlaylist', params)
                if not response:
                    self.logger.error("Error añadiendo canciones")
                    return False
                self.logger.info(f"✅ {len(to_add)} canciones añadidas")

            # Eliminar canciones obsoletas
            if to_remove:
                for song_id in to_remove:
                    # Obtener índice de la canción en la playlist
                    index = self._get_song_index_in_playlist(playlist_id, song_id)
                    if index is not None:
                        params = {
                            'playlistId': playlist_id,
                            'songIndexToRemove': index
                        }
                        self._make_request('updatePlaylist', params)

                self.logger.info(f"✅ {len(to_remove)} canciones eliminadas")

            return True

        except Exception as e:
            self.logger.error(f"Error actualizando playlist: {e}")
            return False

    def _get_song_index_in_playlist(self, playlist_id: str, song_id: str) -> Optional[int]:
        """Obtiene el índice de una canción en una playlist (necesario para eliminar en API 1.15.0)"""
        try:
            response = self._make_request('getPlaylist', {'id': playlist_id})
            if response and 'playlist' in response:
                entries = response['playlist'].get('entry', [])
                for i, entry in enumerate(entries):
                    if entry.get('id') == song_id:
                        return i
            return None
        except Exception as e:
            self.logger.warning(f"Error obteniendo índice de canción {song_id}: {e}")
            return None

    def sync_m3u_to_airsonic(self, m3u_path: str, playlist_name: Optional[str] = None, force_full_sync: bool = False) -> bool:
        """
        Sincroniza un archivo M3U con Airsonic usando sincronización incremental.
        CORRECCIÓN: Solo añade canciones que realmente están en el archivo M3U.
        """
        if not os.path.exists(m3u_path):
            self.logger.error(f"Archivo M3U no encontrado: {m3u_path}")
            return False

        if not playlist_name:
            playlist_name = Path(m3u_path).stem

        # Verificar si el archivo ha cambiado
        current_hash = self._get_m3u_hash(m3u_path)
        playlist_state = self.sync_state["playlists"].get(playlist_name, {})
        last_hash = playlist_state.get("hash", "")

        if not force_full_sync and current_hash == last_hash:
            self.logger.info(f"No hay cambios en {playlist_name}, omitiendo sincronización")
            return True

        self.logger.info(f"Iniciando sincronización de {playlist_name}")

        # Parsear M3U
        tracks = self.parse_m3u_file(m3u_path)
        self.logger.info(f"Encontradas {len(tracks)} canciones en el archivo M3U")

        if not tracks:
            self.logger.warning(f"No se encontraron canciones válidas en {m3u_path}")
            return False

        # Buscar canciones en Airsonic con logging detallado
        airsonic_song_ids = set()
        not_found = []
        found_with_metadata = 0

        for i, track_info in enumerate(tracks, 1):
            if self.interactive:
                album_info = f" ({track_info['album']})" if track_info.get('album') else ""
                self.logger.info(f"Procesando {i}/{len(tracks)}: {track_info.get('artist', 'N/A')} - {track_info.get('title', 'N/A')}{album_info}")

            # CORRECCIÓN: Validar que tenemos información mínima
            if not track_info.get('artist') and not track_info.get('title'):
                self.logger.warning(f"Saltando canción {i} sin artista ni título")
                continue

            # Buscar en base de datos local
            db_track = self.find_track_in_db(track_info)

            # Buscar en Airsonic con criterios estrictos
            song_id = self.search_track_in_airsonic(track_info, db_track)

            if song_id:
                airsonic_song_ids.add(song_id)
                if track_info.get('album'):
                    found_with_metadata += 1
                self.logger.debug(f"✅ Canción encontrada: {song_id}")
            else:
                album_info = f" ({track_info['album']})" if track_info.get('album') else ""
                not_found_track = f"{track_info.get('artist', 'N/A')} - {track_info.get('title', 'N/A')}{album_info}"
                not_found.append(not_found_track)
                self.logger.debug(f"❌ Canción no encontrada: {not_found_track}")

            time.sleep(0.05)  # Rate limiting más suave

        # VALIDACIÓN: Verificar que tenemos canciones para sincronizar
        if not airsonic_song_ids:
            self.logger.warning(f"No se encontraron canciones válidas de {len(tracks)} en el archivo M3U")

            if not_found and self.interactive:
                self.logger.warning(f"Canciones no encontradas ({len(not_found)}):")
                for track in not_found[:10]:  # Mostrar hasta 10
                    self.logger.warning(f"  - {track}")
                if len(not_found) > 10:
                    self.logger.warning(f"  ... y {len(not_found) - 10} más")

            return False

        # Sincronizar con Airsonic
        try:
            # Verificar si la playlist ya existe
            existing_playlist = self.get_airsonic_playlist(playlist_name)

            if existing_playlist:
                # Actualización incremental
                current_song_ids = set(entry['id'] for entry in existing_playlist.get('entry', []))

                self.logger.info(f"📋 Playlist existente: {len(current_song_ids)} canciones")
                self.logger.info(f"📝 Archivo M3U: {len(airsonic_song_ids)} canciones encontradas")

                if self.update_airsonic_playlist(existing_playlist['id'], airsonic_song_ids, current_song_ids):
                    success = True
                    playlist_id = existing_playlist['id']
                else:
                    success = False
                    playlist_id = None
            else:
                # Crear nueva playlist
                self.logger.info(f"📋 Creando nueva playlist con {len(airsonic_song_ids)} canciones")
                playlist_id = self.create_airsonic_playlist(playlist_name, list(airsonic_song_ids))
                success = playlist_id is not None

            if success:
                # Actualizar estado
                self.sync_state["playlists"][playlist_name] = {
                    "hash": current_hash,
                    "airsonic_id": playlist_id,
                    "last_sync": datetime.now().isoformat(),
                    "tracks_found": len(airsonic_song_ids),
                    "tracks_total": len(tracks)
                }
                self._save_sync_state()

                success_rate = len(airsonic_song_ids) / len(tracks) * 100 if tracks else 0
                self.logger.info(f"✅ Sincronización completada: {len(airsonic_song_ids)}/{len(tracks)} canciones ({success_rate:.1f}%)")

                if found_with_metadata > 0:
                    self.logger.info(f"📊 {found_with_metadata} canciones encontradas usando metadata del archivo")

                if not_found and self.interactive:
                    self.logger.warning(f"⚠ Canciones no encontradas ({len(not_found)}):")
                    for track in not_found[:5]:
                        self.logger.warning(f"  - {track}")
                    if len(not_found) > 5:
                        self.logger.warning(f"  ... y {len(not_found) - 5} más")

                return True
            else:
                self.logger.error("Error en la sincronización")
                return False

        except Exception as e:
            self.logger.error(f"Error en sincronización: {e}")
            return False

def main():
    """Función principal"""
    parser = argparse.ArgumentParser(description='Sincronizador de Playlists M3U a Airsonic (VERSIÓN CORREGIDA)')
    parser.add_argument('--cron', action='store_true', help='Modo no interactivo para cron')
    parser.add_argument('--force', action='store_true', help='Forzar sincronización completa')
    parser.add_argument('--playlist', type=str, help='Sincronizar solo una playlist específica')
    parser.add_argument('--db-path', type=str, help='Ruta a la base de datos SQLite')
    parser.add_argument('--m3u-folder', type=str, help='Carpeta con archivos M3U')
    parser.add_argument('--rebuild-cache', action='store_true', help='Reconstruir cache de canciones')
    parser.add_argument('--data-dir', type=str, help='Directorio para archivos de estado y cache')
    parser.add_argument('--dry-run', action='store_true', help='Solo mostrar qué se haría sin hacer cambios')

    args = parser.parse_args()

    # Configuración de rutas desde argumentos o variables de entorno
    DB_PATH = Path(args.db_path) if args.db_path else Path(DEFAULT_DB_PATH)
    M3U_FOLDER = Path(args.m3u_folder) if args.m3u_folder else Path(DEFAULT_M3U_FOLDER)
    DATA_DIR = Path(args.data_dir) if args.data_dir else Path(DEFAULT_DATA_DIR)

    if not args.cron:
        print("🎵 SINCRONIZADOR DE PLAYLISTS M3U -> AIRSONIC (VERSIÓN CORREGIDA)")
        print("=" * 70)
        print("🔧 CORRECCIONES APLICADAS:")
        print("  - Búsquedas más estrictas para evitar falsos positivos")
        print("  - Umbral de similitud mínimo del 85%")
        print("  - Validación mejorada de canciones")
        print("  - Solo añade canciones que realmente están en el M3U")
        print()
        if MUTAGEN_AVAILABLE:
            print("✅ Soporte de metadata activado (mutagen disponible)")
        else:
            print("⚠️  Soporte de metadata desactivado (instala mutagen)")
        print()

    # Verificar base de datos
    if not DB_PATH.exists():
        print(f"❌ Error: Base de datos no encontrada: {DB_PATH}")
        sys.exit(1)

    try:
        # Inicializar sincronizador
        syncer = AirsonicSyncer(str(DB_PATH), interactive=not args.cron, data_dir=str(DATA_DIR))

        # Reconstruir cache si se solicita
        if args.rebuild_cache:
            syncer.logger.info("Reconstruyendo cache de canciones...")
            syncer._song_cache = {}
            syncer._build_song_cache()
            syncer.logger.info("Cache reconstruido")
            if not args.playlist:
                return

        # Buscar archivos M3U
        if args.playlist:
            # Sincronizar playlist específica
            m3u_path = M3U_FOLDER / f"{args.playlist}.m3u"
            if not m3u_path.exists():
                syncer.logger.error(f"Archivo no encontrado: {m3u_path}")
                sys.exit(1)
            files_to_sync = [m3u_path]
        else:
            # Buscar todos los archivos M3U
            files_to_sync = list(M3U_FOLDER.glob("*.m3u"))

            if not files_to_sync:
                syncer.logger.error(f"No se encontraron archivos .m3u en {M3U_FOLDER}")
                sys.exit(1)

        if not args.cron:
            print(f"📁 Encontrados {len(files_to_sync)} archivos M3U:")
            for f in files_to_sync:
                print(f"  - {f.name}")

        # Sincronizar archivos
        successful = 0
        for m3u_file in files_to_sync:
            if not args.cron:
                print(f"\n🎵 Sincronizando {m3u_file.name}...")

            if args.dry_run:
                # Solo mostrar qué se haría
                tracks = syncer.parse_m3u_file(str(m3u_file))
                print(f"🔍 DRY-RUN: Se procesarían {len(tracks)} canciones")
                for i, track in enumerate(tracks[:5], 1):  # Mostrar primeras 5
                    print(f"  {i}. {track.get('artist', 'N/A')} - {track.get('title', 'N/A')}")
                if len(tracks) > 5:
                    print(f"  ... y {len(tracks) - 5} más")
                successful += 1
            else:
                if syncer.sync_m3u_to_airsonic(str(m3u_file), force_full_sync=args.force):
                    successful += 1

        syncer.logger.info(f"Sincronización completada: {successful}/{len(files_to_sync)} playlists")

        if not args.cron:
            if args.dry_run:
                print(f"\n🔍 DRY-RUN completado: {successful}/{len(files_to_sync)} playlists analizadas")
            else:
                print(f"\n✅ Sincronización completada: {successful}/{len(files_to_sync)} playlists")

    except KeyboardInterrupt:
        if not args.cron:
            print("\n\nProceso interrumpido por el usuario")
        sys.exit(0)
    except Exception as e:
        logging.error(f"Error general: {e}")
        if not args.cron:
            print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
