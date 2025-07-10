#!/usr/bin/env python3
"""
Sincronizador de Playlists M3U a Airsonic (Compatible con Cron)
Sincroniza playlists locales .m3u con Airsonic usando sincronización incremental.
Solo añade canciones nuevas y elimina las que ya no existen.
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
            print(f"🔍 Estado del cache: {cache_status}")

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
                        self.logger.error("Prueba expirada")
                    elif error_code == 70:
                        self.logger.error("Los datos solicitados no se encontraron")

                    return None

            return data

        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"Error de conexión a Airsonic: {e}")
            self.logger.error(f"Verifica que Airsonic esté ejecutándose en {self.airsonic_url}")
            return None
        except requests.exceptions.Timeout as e:
            self.logger.error(f"Timeout en petición a Airsonic: {e}")
            return None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error en petición HTTP: {e}")
            return None
        except json.JSONDecodeError as e:
            self.logger.error(f"Error decodificando JSON: {e}")
            self.logger.error("La respuesta del servidor no es JSON válido")
            return None
        except Exception as e:
            self.logger.error(f"Error inesperado en petición: {e}")
            return None

    def _load_song_cache(self):
        """Carga el cache de canciones desde archivo si existe"""
        if not self.song_cache_file.exists():
            self._song_cache = {}
            return

        try:
            with open(self.song_cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            # Validar estructura del cache
            if isinstance(cache_data, dict) and 'songs' in cache_data:
                self._song_cache = cache_data['songs']
                # Solo usar logger si ya existe
                if hasattr(self, 'logger'):
                    self.logger.info(f"Cache de canciones cargado: {len(self._song_cache)} entradas")
            else:
                # Cache corrupto
                self._song_cache = {}
                if hasattr(self, 'logger'):
                    self.logger.warning("Cache corrupto, será reconstruido")

        except Exception as e:
            self._song_cache = {}
            if hasattr(self, 'logger'):
                self.logger.warning(f"Error cargando cache de canciones: {e}")


    def _save_song_cache(self):
        """Guarda el cache de canciones en archivo con verificación"""
        try:
            # Crear directorio si no existe
            self.song_cache_file.parent.mkdir(parents=True, exist_ok=True)

            cache_data = {
                'songs': self._song_cache,
                'created': datetime.now().isoformat(),
                'version': '1.0',
                'total_entries': len(self._song_cache)
            }

            # Escribir a archivo temporal primero
            temp_file = self.song_cache_file.with_suffix('.tmp')

            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)

            # Verificar que se escribió correctamente
            with open(temp_file, 'r', encoding='utf-8') as f:
                verification = json.load(f)

            if verification.get('total_entries') == len(self._song_cache):
                # Mover archivo temporal al definitivo
                temp_file.replace(self.song_cache_file)

                if hasattr(self, 'interactive') and self.interactive:
                    print(f"💾 Cache guardado: {len(self._song_cache)} entradas en {self.song_cache_file}")
                self.logger.info(f"Cache guardado: {len(self._song_cache)} entradas")
            else:
                raise ValueError("Verificación de cache falló")

        except Exception as e:
            if hasattr(self, 'interactive') and self.interactive:
                print(f"❌ Error guardando cache: {e}")
            self.logger.error(f"Error guardando cache de canciones: {e}")

            # Limpiar archivo temporal si existe
            if 'temp_file' in locals() and temp_file.exists():
                temp_file.unlink()

    def verify_cache_integrity(self) -> bool:
        """Verifica que el cache esté íntegro y sea usable"""
        try:
            if not self._song_cache:
                return False

            # Verificar que tenga entradas válidas
            sample_size = min(10, len(self._song_cache))
            sample_keys = list(self._song_cache.keys())[:sample_size]

            for key in sample_keys:
                entries = self._song_cache[key]
                if not isinstance(entries, list) or not entries:
                    return False

                # Verificar que las entradas tengan campos requeridos
                for entry in entries[:3]:  # Solo verificar las primeras 3
                    if not isinstance(entry, dict):
                        return False
                    if 'id' not in entry or 'title' not in entry:
                        return False

            return True

        except Exception:
            return False

    def _is_cache_stale(self) -> bool:
        """Verifica si el cache es muy viejo (más de 24 horas)"""
        if not self.song_cache_file.exists():
            return True

        try:
            # Verificar tiempo de modificación del archivo
            file_time = os.path.getmtime(self.song_cache_file)
            current_time = time.time()
            age_hours = (current_time - file_time) / 3600

            # Log para debug
            self.logger.debug(f"Cache age: {age_hours:.1f} hours")

            return age_hours > 24  # Cache viejo si tiene más de 24 horas
        except Exception as e:
            # Asegurar que logger existe antes de usarlo
            if hasattr(self, 'logger'):
                self.logger.warning(f"Error verificando edad del cache: {e}")
            return True


    def _build_song_cache(self):
        """Construye un cache de todas las canciones en Airsonic para búsquedas rápidas"""
        self.logger.info("Construyendo cache de canciones de Airsonic...")

        try:
            # Limpiar cache existente
            self._song_cache = {}

            # Obtener todos los artistas
            response = self._make_request('getArtists')
            if not response or 'artists' not in response:
                self.logger.warning("No se pudieron obtener artistas de Airsonic")
                return

            song_count = 0

            # Para cada artista, obtener álbumes y canciones
            for index in response['artists'].get('index', []):
                for artist in index.get('artist', []):
                    artist_id = artist['id']

                    # Obtener álbumes del artista
                    albums_response = self._make_request('getArtist', {'id': artist_id})
                    if not albums_response or 'artist' not in albums_response:
                        continue

                    artist_data = albums_response['artist']

                    # Procesar álbumes
                    for album in artist_data.get('album', []):
                        album_id = album['id']

                        # Obtener canciones del álbum
                        songs_response = self._make_request('getAlbum', {'id': album_id})
                        if not songs_response or 'album' not in songs_response:
                            continue

                        album_data = songs_response['album']

                        # Indexar canciones
                        for song in album_data.get('song', []):
                            song_info = {
                                'id': song['id'],
                                'title': song.get('title', ''),
                                'artist': song.get('artist', ''),
                                'album': song.get('album', ''),
                                'track': song.get('track', 0),
                                'year': song.get('year', 0),
                                'genre': song.get('genre', ''),
                                'path': song.get('path', ''),
                                'suffix': song.get('suffix', ''),
                                'duration': song.get('duration', 0)
                            }

                            # Crear claves de búsqueda normalizadas
                            normalized_title = self._normalize_string(song_info['title'])
                            normalized_artist = self._normalize_string(song_info['artist'])
                            normalized_album = self._normalize_string(song_info['album'])

                            # Múltiples estrategias de indexado
                            search_keys = [
                                f"{normalized_artist}|{normalized_title}",
                                f"{normalized_artist}|{normalized_title}|{normalized_album}",
                                f"{normalized_title}|{normalized_artist}",
                                normalized_title if len(normalized_title) > 3 else None,
                            ]

                            for key in search_keys:
                                if key:
                                    if key not in self._song_cache:
                                        self._song_cache[key] = []
                                    self._song_cache[key].append(song_info)

                            song_count += 1

                    time.sleep(0.1)  # Pequeña pausa para no sobrecargar el servidor

            self.logger.info(f"Cache construido: {song_count} canciones indexadas con {len(self._song_cache)} claves de búsqueda")

            # Guardar cache en archivo
            self._save_song_cache()

        except Exception as e:
            self.logger.error(f"Error construyendo cache: {e}")

    def _normalize_string(self, text: str) -> str:
        """Normaliza strings para búsquedas más flexibles"""
        if not text:
            return ""

        # Convertir a minúsculas
        text = text.lower()

        # Remover acentos básicos
        accents = {
            'á': 'a', 'à': 'a', 'ä': 'a', 'â': 'a', 'ā': 'a', 'ã': 'a',
            'é': 'e', 'è': 'e', 'ë': 'e', 'ê': 'e', 'ē': 'e',
            'í': 'i', 'ì': 'i', 'ï': 'i', 'î': 'i', 'ī': 'i',
            'ó': 'o', 'ò': 'o', 'ö': 'o', 'ô': 'o', 'ō': 'o', 'õ': 'o',
            'ú': 'u', 'ù': 'u', 'ü': 'u', 'û': 'u', 'ū': 'u',
            'ñ': 'n', 'ç': 'c'
        }

        for accented, plain in accents.items():
            text = text.replace(accented, plain)

        # Remover caracteres especiales y espacios extra
        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()

        return text

    def _load_sync_state(self) -> Dict:
        """Carga el estado de sincronización anterior"""
        if self.sync_state_file.exists():
            try:
                with open(self.sync_state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Error cargando estado de sincronización: {e}")

        return {"playlists": {}, "last_sync": None}

    def _save_sync_state(self):
        """Guarda el estado de sincronización"""
        try:
            self.sync_state["last_sync"] = datetime.now().isoformat()
            with open(self.sync_state_file, 'w', encoding='utf-8') as f:
                json.dump(self.sync_state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Error guardando estado de sincronización: {e}")

    def _get_m3u_hash(self, m3u_path: str) -> str:
        """Genera hash del contenido del archivo M3U"""
        try:
            with open(m3u_path, 'rb') as f:
                content = f.read()
            return hashlib.md5(content).hexdigest()
        except Exception as e:
            self.logger.error(f"Error generando hash para {m3u_path}: {e}")
            return ""

    def parse_m3u_file(self, m3u_path: str) -> List[Dict[str, str]]:
        """Parsea un archivo M3U y extrae información de las canciones."""
        tracks = []

        try:
            with open(m3u_path, 'r', encoding='utf-8') as file:
                for line in file:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        track_info = self._parse_track_filename(line)
                        if track_info:
                            tracks.append(track_info)

        except Exception as e:
            self.logger.error(f"Error leyendo archivo M3U {m3u_path}: {e}")

        return tracks

    def _parse_track_filename(self, filename: str) -> Optional[Dict[str, str]]:
        """Parsea el nombre de archivo para extraer información de la canción."""
        pattern = r'([^/]+)/([^-]+)\s*-\s*([^[]+)\s*\[([^-]+)\s*-\s*([^\]]+)\]\.(\w+)'
        match = re.match(pattern, filename)

        if match:
            genre, artist, title, year, album, extension = match.groups()
            return {
                'genre': genre.strip(),
                'artist': artist.strip(),
                'title': title.strip(),
                'year': year.strip(),
                'album': album.strip(),
                'filename': filename,
                'file_path': filename
            }
        else:
            self.logger.warning(f"No se pudo parsear: {filename}")
            return None

    def find_track_in_db(self, track_info: Dict[str, str]) -> Optional[Dict[str, any]]:
        """Busca una canción en la base de datos local."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = """
            SELECT s.*, a.name as artist_name, al.name as album_name
            FROM songs s
            LEFT JOIN artists a ON s.artist = a.name
            LEFT JOIN albums al ON s.album = al.name
            WHERE LOWER(s.artist) LIKE LOWER(?)
            AND LOWER(s.title) LIKE LOWER(?)
            ORDER BY
                CASE
                    WHEN LOWER(s.artist) = LOWER(?) AND LOWER(s.title) = LOWER(?) THEN 1
                    ELSE 2
                END
            LIMIT 1
            """

            artist = track_info['artist'].strip()
            title = track_info['title'].strip()

            cursor.execute(query, (f"%{artist}%", f"%{title}%", artist, title))
            result = cursor.fetchone()

            if result:
                return dict(result)

            # Búsqueda FTS alternativa
            try:
                fts_query = """
                SELECT s.*, a.name as artist_name, al.name as album_name
                FROM song_fts
                JOIN songs s ON song_fts.id = s.id
                LEFT JOIN artists a ON s.artist = a.name
                LEFT JOIN albums al ON s.album = al.name
                WHERE song_fts MATCH ?
                LIMIT 1
                """
                search_term = f'"{artist}" "{title}"'
                cursor.execute(fts_query, (search_term,))
                result = cursor.fetchone()

                if result:
                    return dict(result)
            except:
                pass

            return None

        except Exception as e:
            self.logger.error(f"Error buscando en DB: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def search_track_in_airsonic(self, track_info: Dict[str, str], db_track: Optional[Dict] = None) -> Optional[str]:
        """
        Busca una canción en Airsonic usando el cache construido.

        Returns:
            ID de la canción en Airsonic o None si no se encuentra
        """
        try:
            # Usar información de la DB local si está disponible
            if db_track:
                search_artist = db_track.get('artist', track_info['artist'])
                search_title = db_track.get('title', track_info['title'])
                search_album = db_track.get('album', track_info['album'])
            else:
                search_artist = track_info['artist']
                search_title = track_info['title']
                search_album = track_info['album']

            # Normalizar strings de búsqueda
            norm_artist = self._normalize_string(search_artist)
            norm_title = self._normalize_string(search_title)
            norm_album = self._normalize_string(search_album)

            # Estrategias de búsqueda en orden de preferencia
            search_strategies = [
                f"{norm_artist}|{norm_title}|{norm_album}",  # Coincidencia exacta
                f"{norm_artist}|{norm_title}",               # Artista + título
                f"{norm_title}|{norm_artist}",               # Título + artista (orden inverso)
                norm_title if len(norm_title) > 3 else None  # Solo título (si es lo suficientemente largo)
            ]

            for strategy in search_strategies:
                if not strategy:
                    continue

                if strategy in self._song_cache:
                    candidates = self._song_cache[strategy]

                    # Si hay múltiples candidatos, elegir el mejor
                    if len(candidates) == 1:
                        match = candidates[0]
                        self.logger.debug(f"Encontrado en Airsonic: {search_artist} - {search_title}")
                        return match['id']
                    elif len(candidates) > 1:
                        # Usar scoring para elegir la mejor coincidencia
                        best_match = self._score_matches(candidates, norm_artist, norm_title, norm_album)
                        if best_match:
                            self.logger.debug(f"Encontrado en Airsonic (múltiples): {search_artist} - {search_title}")
                            return best_match['id']

            # Fallback: búsqueda por API si el cache no tiene resultados
            api_result = self._search_by_api(search_title, search_artist)
            if api_result:
                self.logger.debug(f"Encontrado en Airsonic (API): {search_artist} - {search_title}")
                return api_result

            self.logger.debug(f"No encontrado en Airsonic: {search_artist} - {search_title}")
            return None

        except Exception as e:
            self.logger.error(f"Error buscando en Airsonic: {e}")
            return None

    def _score_matches(self, candidates: List[Dict], norm_artist: str, norm_title: str, norm_album: str) -> Optional[Dict]:
        """Puntúa múltiples candidatos y retorna el mejor"""
        best_score = 0
        best_match = None

        for candidate in candidates:
            score = 0

            cand_artist = self._normalize_string(candidate['artist'])
            cand_title = self._normalize_string(candidate['title'])
            cand_album = self._normalize_string(candidate['album'])

            # Puntuación por coincidencia exacta
            if cand_artist == norm_artist:
                score += 10
            elif norm_artist in cand_artist or cand_artist in norm_artist:
                score += 5

            if cand_title == norm_title:
                score += 10
            elif norm_title in cand_title or cand_title in norm_title:
                score += 5

            if cand_album == norm_album:
                score += 3
            elif norm_album in cand_album or cand_album in norm_album:
                score += 1

            if score > best_score:
                best_score = score
                best_match = candidate

        # Solo retornar si hay una coincidencia razonable
        return best_match if best_score >= 10 else None

    def _search_by_api(self, title: str, artist: str) -> Optional[str]:
        """Búsqueda fallback usando la API de Airsonic"""
        try:
            # Búsqueda combinada
            query = f"{title} {artist}".strip()
            if not query:
                return None

            response = self._make_request('search3', {
                'query': query,
                'songCount': 10,
                'songOffset': 0
            })

            if response and 'searchResult3' in response:
                songs = response['searchResult3'].get('song', [])

                if songs:
                    # Buscar la mejor coincidencia
                    norm_title = self._normalize_string(title)
                    norm_artist = self._normalize_string(artist)

                    for song in songs:
                        song_title = self._normalize_string(song.get('title', ''))
                        song_artist = self._normalize_string(song.get('artist', ''))

                        if (norm_title in song_title or song_title in norm_title) and \
                           (norm_artist in song_artist or song_artist in norm_artist):
                            return song['id']

            return None

        except Exception as e:
            self.logger.error(f"Error en búsqueda por API: {e}")
            return None

    def get_airsonic_playlist(self, playlist_name: str) -> Optional[Dict]:
        """Obtiene información de una playlist existente en Airsonic"""
        try:
            response = self._make_request('getPlaylists')
            if not response or 'playlists' not in response:
                return None

            for playlist in response['playlists'].get('playlist', []):
                if playlist['name'] == playlist_name:
                    # Obtener detalles completos de la playlist
                    detail_response = self._make_request('getPlaylist', {'id': playlist['id']})
                    if detail_response and 'playlist' in detail_response:
                        return detail_response['playlist']

            return None

        except Exception as e:
            self.logger.error(f"Error obteniendo playlist {playlist_name}: {e}")
            return None

    def create_airsonic_playlist(self, playlist_name: str, song_ids: List[str]) -> Optional[str]:
        """Crea una nueva playlist en Airsonic (compatible con API 1.15.0)"""
        try:
            if not song_ids:
                self.logger.warning("No se pueden crear playlists vacías")
                return None

            # Crear playlist vacía primero
            response = self._make_request('createPlaylist', {'name': playlist_name})
            if not response:
                self.logger.error(f"Error creando playlist {playlist_name}")
                return None

            # En API 1.15.0, la respuesta puede no incluir el ID directamente
            playlist_id = None
            if 'playlist' in response:
                playlist_id = response['playlist'].get('id')

            # Si no obtuvimos el ID, buscar la playlist recién creada
            if not playlist_id:
                time.sleep(1)  # Pequeña pausa para que se propague la creación
                response = self._make_request('getPlaylists')
                if response and 'playlists' in response:
                    for playlist in response['playlists'].get('playlist', []):
                        if playlist['name'] == playlist_name:
                            playlist_id = playlist['id']
                            break

            if not playlist_id:
                self.logger.error(f"No se pudo obtener ID de playlist creada: {playlist_name}")
                return None

            # Añadir canciones de una en una (más compatible con versiones antiguas)
            success_count = 0
            for song_id in song_ids:
                try:
                    add_response = self._make_request('updatePlaylist', {
                        'playlistId': playlist_id,
                        'songIdToAdd': song_id
                    })
                    if add_response:
                        success_count += 1
                    else:
                        self.logger.warning(f"Error añadiendo canción {song_id} a playlist {playlist_name}")

                    # Pausa pequeña para evitar sobrecargar la API
                    time.sleep(0.1)

                except Exception as e:
                    self.logger.warning(f"Error añadiendo canción {song_id}: {e}")
                    continue

            if success_count > 0:
                self.logger.info(f"Playlist '{playlist_name}' creada con {success_count}/{len(song_ids)} canciones")
                return playlist_id
            else:
                self.logger.error(f"No se pudieron añadir canciones a playlist {playlist_name}")
                return None

        except Exception as e:
            self.logger.error(f"Error creando playlist: {e}")
            return None

    def update_airsonic_playlist(self, playlist_id: str, new_song_ids: Set[str], current_song_ids: Set[str]) -> bool:
        """Actualiza una playlist existente en Airsonic de forma incremental (compatible con API 1.15.0)"""
        try:
            # Calcular diferencias
            songs_to_add = new_song_ids - current_song_ids
            songs_to_remove = current_song_ids - new_song_ids

            changes_made = False

            # Eliminar canciones que ya no están (de atrás hacia adelante para mantener índices)
            if songs_to_remove:
                # Obtener playlist actual para los índices
                current_playlist = self._make_request('getPlaylist', {'id': playlist_id})
                if current_playlist and 'playlist' in current_playlist:
                    entries = current_playlist['playlist'].get('entry', [])

                    # Crear lista de índices a eliminar (de mayor a menor)
                    indices_to_remove = []
                    for i, entry in enumerate(entries):
                        if entry['id'] in songs_to_remove:
                            indices_to_remove.append(i)

                    # Eliminar de atrás hacia adelante
                    for index in sorted(indices_to_remove, reverse=True):
                        try:
                            remove_response = self._make_request('updatePlaylist', {
                                'playlistId': playlist_id,
                                'songIndexToRemove': index
                            })
                            if remove_response:
                                changes_made = True
                            time.sleep(0.1)
                        except Exception as e:
                            self.logger.warning(f"Error eliminando canción en índice {index}: {e}")

                self.logger.info(f"Eliminadas {len(indices_to_remove)} canciones")

            # Añadir canciones nuevas de una en una
            if songs_to_add:
                success_count = 0
                for song_id in songs_to_add:
                    try:
                        add_response = self._make_request('updatePlaylist', {
                            'playlistId': playlist_id,
                            'songIdToAdd': song_id
                        })
                        if add_response:
                            success_count += 1
                            changes_made = True
                        time.sleep(0.1)
                    except Exception as e:
                        self.logger.warning(f"Error añadiendo canción {song_id}: {e}")

                self.logger.info(f"Añadidas {success_count}/{len(songs_to_add)} canciones nuevas")

            if not changes_made:
                self.logger.info("No hay cambios que sincronizar")

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

        # Buscar canciones en Airsonic
        airsonic_song_ids = set()
        not_found = []

        for i, track_info in enumerate(tracks, 1):
            if self.interactive:
                self.logger.info(f"Procesando {i}/{len(tracks)}: {track_info['artist']} - {track_info['title']}")

            # Buscar en base de datos local
            db_track = self.find_track_in_db(track_info)

            # Buscar en Airsonic
            song_id = self.search_track_in_airsonic(track_info, db_track)

            if song_id:
                airsonic_song_ids.add(song_id)
            else:
                not_found.append(f"{track_info['artist']} - {track_info['title']}")

            time.sleep(0.05)  # Rate limiting más suave

        # Sincronizar con Airsonic
        if airsonic_song_ids or force_full_sync:
            # Verificar si la playlist ya existe
            existing_playlist = self.get_airsonic_playlist(playlist_name)

            if existing_playlist:
                # Actualización incremental
                current_song_ids = set(entry['id'] for entry in existing_playlist.get('entry', []))

                if self.update_airsonic_playlist(existing_playlist['id'], airsonic_song_ids, current_song_ids):
                    success = True
                    playlist_id = existing_playlist['id']
                else:
                    success = False
                    playlist_id = None
            else:
                # Crear nueva playlist
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

                if not_found and self.interactive:
                    self.logger.warning(f"❌ Canciones no encontradas ({len(not_found)}):")
                    for track in not_found[:5]:
                        self.logger.warning(f"  - {track}")
                    if len(not_found) > 5:
                        self.logger.warning(f"  ... y {len(not_found) - 5} más")

                return True
            else:
                self.logger.error("Error en la sincronización")
                return False
        else:
            self.logger.warning("No se encontraron canciones válidas para sincronizar")
            return False

def main():
    """Función principal"""
    parser = argparse.ArgumentParser(description='Sincronizador de Playlists M3U a Airsonic')
    parser.add_argument('--cron', action='store_true', help='Modo no interactivo para cron')
    parser.add_argument('--force', action='store_true', help='Forzar sincronización completa')
    parser.add_argument('--playlist', type=str, help='Sincronizar solo una playlist específica')
    parser.add_argument('--db-path', type=str, help='Ruta a la base de datos SQLite')
    parser.add_argument('--m3u-folder', type=str, help='Carpeta con archivos M3U')
    parser.add_argument('--rebuild-cache', action='store_true', help='Reconstruir cache de canciones')
    parser.add_argument('--data-dir', type=str, help='Directorio para archivos de estado y cache')

    args = parser.parse_args()

    # Configuración de rutas desde argumentos o variables de entorno
    DB_PATH = Path(args.db_path) if args.db_path else Path(DEFAULT_DB_PATH)
    M3U_FOLDER = Path(args.m3u_folder) if args.m3u_folder else Path(DEFAULT_M3U_FOLDER)
    DATA_DIR = Path(args.data_dir) if args.data_dir else Path(DEFAULT_DATA_DIR)

    if not args.cron:
        print("🎵 SINCRONIZADOR DE PLAYLISTS M3U -> AIRSONIC")
        print("=" * 55)

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

            if syncer.sync_m3u_to_airsonic(str(m3u_file), force_full_sync=args.force):
                successful += 1

        syncer.logger.info(f"Sincronización completada: {successful}/{len(files_to_sync)} playlists")

        if not args.cron:
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
