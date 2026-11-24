#!/usr/bin/env python3
"""
Sincronizador de Playlists M3U a Airsonic - VERSIÓN MEJORADA CON BÚSQUEDA JERÁRQUICA
Versión mejorada con búsqueda más precisa: album_artist -> album -> title

MEJORAS:
- Búsqueda jerárquica estricta (album_artist -> album -> title)
- Modos de matching configurables (strict, balanced, fuzzy)
- Estadísticas detalladas de matches
- Mejor reporting de falsos positivos
- Modo interactivo mejorado con debugging
"""

import os
import re
import requests
import hashlib
import json
import argparse
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Set, Tuple
from urllib.parse import urlencode
from dataclasses import dataclass
from enum import Enum
import logging
import sys
from dotenv import load_dotenv

# Importar mutagen para leer metadata (REQUERIDO)
try:
    from mutagen import File as MutagenFile
    from mutagen.id3 import ID3NoHeaderError
    MUTAGEN_AVAILABLE = True
except ImportError:
    print("❌ ERROR: mutagen es REQUERIDO para esta versión del script.", file=sys.stderr)
    print("   Instala con: pip install mutagen", file=sys.stderr)
    sys.exit(1)

# Configuración de rutas
script_dir = Path(__file__).parent.absolute()

# Cargar variables de entorno
env_file = script_dir / ".env"
if env_file.exists():
    load_dotenv(env_file)
else:
    print(f"Error: No se encontró .env en {env_file}", file=sys.stderr)
    sys.exit(1)

# Configurar rutas desde variables de entorno
CACHE_DIR = Path(os.getenv('CACHE_DIR', script_dir / ".content/cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_M3U_FOLDER = os.getenv('M3U_FOLDER', str(script_dir))
DEFAULT_DATA_DIR = os.getenv('DATA_DIR', str(CACHE_DIR))


class MatchMode(Enum):
    """Modos de matching disponibles"""
    STRICT = "strict"      # Requiere coincidencia exacta en album_artist, album y title
    BALANCED = "balanced"  # Balance entre precisión y recall (default)
    FUZZY = "fuzzy"        # Más permisivo, acepta similitudes mayores


@dataclass
class MatchConfig:
    """Configuración de umbrales de matching"""
    mode: MatchMode
    artist_threshold: float
    album_threshold: float
    title_threshold: float
    require_album: bool  # Si es True, solo acepta matches con álbum coincidente

    @classmethod
    def from_mode(cls, mode: MatchMode) -> 'MatchConfig':
        """Crea configuración según el modo"""
        configs = {
            MatchMode.STRICT: cls(
                mode=MatchMode.STRICT,
                artist_threshold=0.95,  # Casi exacto
                album_threshold=0.90,   # Casi exacto
                title_threshold=0.95,   # Casi exacto
                require_album=True      # DEBE tener álbum
            ),
            MatchMode.BALANCED: cls(
                mode=MatchMode.BALANCED,
                artist_threshold=0.85,  # Bastante preciso
                album_threshold=0.80,   # Bastante preciso
                title_threshold=0.90,   # Muy preciso en título
                require_album=False     # No requiere álbum pero lo prefiere
            ),
            MatchMode.FUZZY: cls(
                mode=MatchMode.FUZZY,
                artist_threshold=0.70,  # Más permisivo
                album_threshold=0.65,   # Más permisivo
                title_threshold=0.80,   # Aún exigente en título
                require_album=False
            )
        }
        return configs[mode]


@dataclass
class MatchResult:
    """Resultado de un intento de matching"""
    success: bool
    song_id: Optional[str]
    confidence: float
    matched_artist: str
    matched_album: str
    matched_title: str
    match_path: str  # Describe cómo se hizo el match
    reason: str      # Por qué se aceptó/rechazó


class AirsonicMetadataSyncImproved:
    def __init__(self, interactive: bool = True, data_dir: str = None,
                 match_mode: MatchMode = MatchMode.BALANCED,
                 verbose: bool = False):
        """
        Inicializa el sincronizador mejorado.

        Args:
            interactive: Si False, no solicita input del usuario (para cron)
            data_dir: Directorio para archivos de estado y cache
            match_mode: Modo de matching a usar
            verbose: Mostrar información detallada de debugging
        """
        self.interactive = interactive
        self.verbose = verbose
        self.match_config = MatchConfig.from_mode(match_mode)

        # Configurar directorio de datos
        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            self.data_dir = Path(DEFAULT_DATA_DIR)

        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Archivos de estado
        self.sync_state_file = self.data_dir / "airsonic_metadata_sync_state.json"
        self.song_cache_file = self.data_dir / "airsonic_metadata_song_cache.json"
        self.stats_file = self.data_dir / "matching_stats.json"

        # Configurar logging
        log_level = logging.DEBUG if verbose else (logging.INFO if interactive else logging.WARNING)
        log_handlers = [logging.FileHandler(self.data_dir / 'airsonic_metadata_sync.log')]
        if interactive:
            log_handlers.append(logging.StreamHandler())

        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=log_handlers,
            force=True
        )
        self.logger = logging.getLogger(__name__)

        # Estadísticas de matching
        self.match_stats = {
            'total_attempts': 0,
            'exact_matches': 0,
            'fuzzy_matches': 0,
            'cache_hits': 0,
            'api_searches': 0,
            'not_found': 0,
            'album_required_rejected': 0,
            'artist_mismatch': 0,
            'album_mismatch': 0,
            'title_mismatch': 0
        }

        # Configuración de Airsonic
        self.airsonic_url = os.getenv('AIRSONIC_URL', 'http://localhost:4040')
        self.airsonic_user = os.getenv('AIRSONIC_USER')
        self.airsonic_password = os.getenv('AIRSONIC_PASSWORD')
        self.airsonic_api_version = os.getenv('AIRSONIC_API_VERSION', '1.16.1')

        if not self.airsonic_user or not self.airsonic_password:
            self.logger.error("Error: AIRSONIC_USER y AIRSONIC_PASSWORD deben estar configurados en .env")
            sys.exit(1)

        # Configurar autenticación
        self.auth_params = {
            'u': self.airsonic_user,
            'p': self.airsonic_password,
            'v': self.airsonic_api_version,
            'c': 'MetadataPlaylistSyncerImproved',
            'f': 'json'
        }

        # Verificar conexión
        if not self._test_connection():
            self.logger.error("No se pudo conectar a Airsonic")
            sys.exit(1)

        # Cargar estado
        self.sync_state = self._load_sync_state()

        # Cache de canciones
        self._song_cache = {}
        self._album_artist_index = {}  # Índice por album_artist
        self._load_song_cache()

        # Configuración de cache
        cache_needs_rebuild = False
        cache_status = ""

        if not self._song_cache:
            cache_needs_rebuild = True
            cache_status = "Cache vacío"
        elif self._is_cache_stale(max_age_hours=12):
            cache_needs_rebuild = True
            cache_status = "Cache obsoleto (>12h)"
        else:
            cache_status = f"Cache válido con {len(self._song_cache)} entradas"

        if interactive:
            print(f"🔍 Modo de matching: {match_mode.value.upper()}")
            print(f"   - Artist threshold: {self.match_config.artist_threshold:.0%}")
            print(f"   - Album threshold: {self.match_config.album_threshold:.0%}")
            print(f"   - Title threshold: {self.match_config.title_threshold:.0%}")
            print(f"   - Require album: {'Sí' if self.match_config.require_album else 'No'}")
            print(f"📁 Directorio de datos: {self.data_dir}")
            print(f"💾 Archivo de cache: {self.song_cache_file}")
            print(f"📊 Estado del cache: {cache_status}")

        self.logger.info(f"Inicializado - Modo: {match_mode.value} - {cache_status}")

        # Reconstruir cache si es necesario
        if cache_needs_rebuild:
            if interactive:
                print("🔨 Reconstruyendo cache de canciones...")
            self.logger.info("Reconstruyendo cache de canciones")
            self._build_song_cache()
        else:
            if interactive:
                print("✅ Usando cache existente")

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
                    self.logger.error(f"Error de Airsonic: {error.get('message', 'Unknown')}")
                    return None

            return None

        except Exception as e:
            self.logger.error(f"Error en petición: {e}")
            return None

    def _load_sync_state(self) -> Dict:
        """Carga el estado de sincronización desde archivo"""
        if self.sync_state_file.exists():
            try:
                with open(self.sync_state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Error cargando estado: {e}")

        return {"playlists": {}, "last_update": datetime.now().isoformat()}

    def _save_sync_state(self):
        """Guarda el estado de sincronización"""
        try:
            self.sync_state["last_update"] = datetime.now().isoformat()
            with open(self.sync_state_file, 'w') as f:
                json.dump(self.sync_state, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error guardando estado: {e}")

    def _save_match_stats(self):
        """Guarda estadísticas de matching"""
        try:
            stats_data = {
                'timestamp': datetime.now().isoformat(),
                'match_mode': self.match_config.mode.value,
                'stats': self.match_stats
            }
            with open(self.stats_file, 'w') as f:
                json.dump(stats_data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error guardando estadísticas: {e}")

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
                    self._album_artist_index = cache_data.get('album_artist_index', {})
                    self._cache_timestamp = cache_data.get('timestamp', 0)
                    self.logger.info(f"Cache cargado: {len(self._song_cache)} entradas")
            except Exception as e:
                self.logger.warning(f"Error cargando cache: {e}")
                self._song_cache = {}
                self._album_artist_index = {}
                self._cache_timestamp = 0
        else:
            self._cache_timestamp = 0

    def _save_song_cache(self):
        """Guarda el cache de canciones"""
        try:
            cache_data = {
                'timestamp': time.time(),
                'songs': self._song_cache,
                'album_artist_index': self._album_artist_index
            }
            with open(self.song_cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error guardando cache: {e}")

    def _is_cache_stale(self, max_age_hours: int = 12) -> bool:
        """Verifica si el cache está obsoleto"""
        if not hasattr(self, '_cache_timestamp'):
            return True
        age_hours = (time.time() - self._cache_timestamp) / 3600
        return age_hours > max_age_hours

    def _build_song_cache(self):
        """Construye cache de todas las canciones en Airsonic con índice por album_artist"""
        self.logger.info("Construyendo cache de canciones con índice jerárquico...")

        try:
            response = self._make_request('search3', {'query': '*', 'songCount': 10000})

            if response and 'searchResult3' in response:
                songs = response['searchResult3'].get('song', [])

                for song in songs:
                    song_id = song.get('id')
                    if isinstance(song_id, list):
                        song_id = song_id[0] if song_id else None
                    if not song_id:
                        continue
                    song_id = str(song_id)

                    # Extraer metadata
                    artist = song.get('artist', '')
                    title = song.get('title', '')
                    album = song.get('album', '')
                    album_artist = song.get('albumArtist', artist)  # Usar artist si no hay albumArtist

                    if not artist or not title:
                        continue

                    # Normalizar valores
                    artist_norm = self._normalize_text(artist)
                    title_norm = self._normalize_text(title)
                    album_norm = self._normalize_text(album)
                    album_artist_norm = self._normalize_text(album_artist)

                    # Crear entrada en cache
                    song_entry = {
                        'id': song_id,
                        'artist': artist,
                        'artist_norm': artist_norm,
                        'title': title,
                        'title_norm': title_norm,
                        'album': album,
                        'album_norm': album_norm,
                        'album_artist': album_artist,
                        'album_artist_norm': album_artist_norm,
                        'path': song.get('path', '')
                    }

                    # Crear claves de búsqueda
                    # 1. Clave principal: album_artist|album|title
                    if album_artist_norm and album_norm and title_norm:
                        main_key = f"{album_artist_norm}|{album_norm}|{title_norm}"
                        self._song_cache[main_key] = song_entry

                    # 2. Clave alternativa: artist|album|title (si artist != album_artist)
                    if artist_norm != album_artist_norm and artist_norm and album_norm and title_norm:
                        alt_key = f"{artist_norm}|{album_norm}|{title_norm}"
                        self._song_cache[alt_key] = song_entry

                    # 3. Clave sin álbum: album_artist|title
                    if album_artist_norm and title_norm:
                        no_album_key = f"{album_artist_norm}|{title_norm}"
                        self._song_cache[no_album_key] = song_entry

                    # 4. Índice por album_artist para búsqueda jerárquica
                    if album_artist_norm:
                        if album_artist_norm not in self._album_artist_index:
                            self._album_artist_index[album_artist_norm] = []
                        self._album_artist_index[album_artist_norm].append(song_entry)

                self._save_song_cache()
                self.logger.info(f"Cache construido: {len(songs)} canciones, {len(self._song_cache)} claves, "
                               f"{len(self._album_artist_index)} album_artists")
            else:
                self.logger.warning("No se pudieron obtener canciones de Airsonic")

        except Exception as e:
            self.logger.error(f"Error construyendo cache: {e}")

    def _normalize_text(self, text: str) -> str:
        """Normaliza texto para búsqueda"""
        if not text:
            return ""
        # Convertir a minúsculas y normalizar espacios
        normalized = ' '.join(text.lower().strip().split())
        # Remover caracteres especiales comunes
        normalized = re.sub(r'[^\w\s]', '', normalized)
        return normalized

    def extract_metadata_from_file(self, file_path: str) -> Optional[Dict[str, str]]:
        """Extrae metadata completa del archivo de audio"""
        if not os.path.exists(file_path):
            self.logger.debug(f"Archivo no encontrado: {file_path}")
            return None

        try:
            audio = MutagenFile(file_path, easy=True)
            if audio is None:
                self.logger.debug(f"No se pudo leer archivo de audio: {file_path}")
                return None

            metadata = {}

            # Extraer album_artist (PRIORIDAD MÁXIMA)
            for tag in ['albumartist', 'album artist', 'album_artist']:
                if tag in audio and audio[tag]:
                    album_artist = audio[tag]
                    metadata['album_artist'] = album_artist[0] if isinstance(album_artist, list) else str(album_artist)
                    break

            # Extraer artista (si no hay album_artist, se usará como fallback)
            for tag in ['artist', 'performer']:
                if tag in audio and audio[tag]:
                    artist = audio[tag]
                    metadata['artist'] = artist[0] if isinstance(artist, list) else str(artist)
                    break

            # Si no hay album_artist pero hay artist, usar artist como album_artist
            if not metadata.get('album_artist') and metadata.get('artist'):
                metadata['album_artist'] = metadata['artist']

            # Extraer título
            if 'title' in audio and audio['title']:
                title = audio['title']
                metadata['title'] = title[0] if isinstance(title, list) else str(title)

            # Extraer álbum
            if 'album' in audio and audio['album']:
                album = audio['album']
                metadata['album'] = album[0] if isinstance(album, list) else str(album)

            # Extraer año
            if 'date' in audio and audio['date']:
                date = audio['date']
                metadata['date'] = date[0] if isinstance(date, list) else str(date)

            # Extraer número de pista
            if 'tracknumber' in audio and audio['tracknumber']:
                track = audio['tracknumber']
                metadata['tracknumber'] = track[0] if isinstance(track, list) else str(track)

            # Si no tenemos información mínima, intentar extraer del nombre de archivo
            if not metadata.get('album_artist') or not metadata.get('title'):
                filename_info = self._extract_info_from_filename(file_path)
                if not metadata.get('album_artist') and filename_info.get('artist'):
                    metadata['album_artist'] = filename_info['artist']
                    metadata['artist'] = filename_info['artist']
                if not metadata.get('title') and filename_info.get('title'):
                    metadata['title'] = filename_info['title']

            if metadata.get('album_artist') or metadata.get('title'):
                self.logger.debug(f"Metadata extraída: {metadata.get('album_artist', 'N/A')} - "
                                f"{metadata.get('title', 'N/A')} [{metadata.get('album', 'N/A')}]")
                return metadata
            else:
                self.logger.debug(f"No se encontró metadata útil en: {file_path}")
                return None

        except ID3NoHeaderError:
            self.logger.debug(f"Archivo sin tags ID3: {file_path}")
        except Exception as e:
            self.logger.debug(f"Error leyendo metadata de {file_path}: {e}")

        return None

    def _extract_info_from_filename(self, file_path: str) -> Dict[str, str]:
        """Extrae información del nombre del archivo como fallback"""
        filename = os.path.basename(file_path)
        name_without_ext = os.path.splitext(filename)[0]

        patterns = [
            r'^(.+?)\s*-\s*(.+?)$',
            r'^(.+?)_-_(.+?)$',
            r'^\[.+?\]\s*(.+?)\s*-\s*(.+?)$',
            r'^\(.+?\)\s*(.+?)\s*-\s*(.+?)$',
            r'^\d+\.\s*(.+?)\s*-\s*(.+?)$',
        ]

        for pattern in patterns:
            match = re.search(pattern, name_without_ext)
            if match:
                return {
                    'artist': match.group(1).strip(),
                    'title': match.group(2).strip()
                }

        if ' - ' in name_without_ext:
            parts = name_without_ext.split(' - ', 1)
            artist = re.sub(r'^\[.+?\]|\(.+?\)|\d+\.\s*', '', parts[0]).strip()
            return {
                'artist': artist,
                'title': parts[1].strip()
            }

        return {'artist': '', 'title': name_without_ext}

    def parse_m3u_file(self, m3u_path: str) -> List[Dict[str, str]]:
        """Parsea archivo M3U y extrae metadata REAL de cada archivo listado"""
        tracks = []

        with open(m3u_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        current_extinf_info = {}
        processed_files = set()

        for line_num, line in enumerate(lines, 1):
            line = line.strip()

            # Procesar líneas EXTINF
            if line.startswith('#EXTINF:'):
                match = re.search(r'#EXTINF:.*?,\s*(.+?)\s*-\s*(.+)', line)
                if match:
                    current_extinf_info = {
                        'extinf_artist': match.group(1).strip(),
                        'extinf_title': match.group(2).strip()
                    }

            # Procesar rutas de archivo
            elif line and not line.startswith('#'):
                file_path = line.strip()

                if file_path in processed_files:
                    continue
                processed_files.add(file_path)

                if not os.path.exists(file_path):
                    self.logger.warning(f"Archivo no encontrado (línea {line_num}): {file_path}")
                    continue

                # Extraer metadata REAL del archivo
                metadata = self.extract_metadata_from_file(file_path)

                if metadata:
                    track_info = {
                        'album_artist': metadata.get('album_artist', ''),
                        'artist': metadata.get('artist', ''),
                        'title': metadata.get('title', ''),
                        'album': metadata.get('album', ''),
                        'path': file_path,
                        'source': 'metadata'
                    }

                    if metadata.get('date'):
                        track_info['date'] = metadata['date']
                    if metadata.get('tracknumber'):
                        track_info['tracknumber'] = metadata['tracknumber']

                    if current_extinf_info:
                        track_info['extinf_artist'] = current_extinf_info.get('extinf_artist', '')
                        track_info['extinf_title'] = current_extinf_info.get('extinf_title', '')

                    tracks.append(track_info)
                    self.logger.debug(f"Track añadido: {track_info['album_artist']} - "
                                    f"{track_info['title']} [{track_info['album']}]")

                else:
                    # Fallback a EXTINF
                    if current_extinf_info:
                        track_info = {
                            'album_artist': current_extinf_info.get('extinf_artist', ''),
                            'artist': current_extinf_info.get('extinf_artist', ''),
                            'title': current_extinf_info.get('extinf_title', ''),
                            'album': '',
                            'path': file_path,
                            'source': 'extinf'
                        }
                        tracks.append(track_info)
                        self.logger.debug(f"Track añadido (EXTINF): {track_info['album_artist']} - {track_info['title']}")
                    else:
                        self.logger.warning(f"No se pudo extraer información de: {file_path}")

                current_extinf_info = {}

        return tracks

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """
        Calcula similitud entre dos textos (0.0 a 1.0)
        Usa varios métodos para mejor precisión
        """
        if not text1 or not text2:
            return 0.0

        text1_norm = self._normalize_text(text1)
        text2_norm = self._normalize_text(text2)

        # Coincidencia exacta
        if text1_norm == text2_norm:
            return 1.0

        # Similitud por palabras comunes (Jaccard)
        words1 = set(text1_norm.split())
        words2 = set(text2_norm.split())

        if not words1 or not words2:
            return 0.0

        common = words1.intersection(words2)
        total = words1.union(words2)

        jaccard = len(common) / len(total) if total else 0.0

        # Similitud por substring (si uno contiene al otro)
        contains_similarity = 0.0
        if text1_norm in text2_norm or text2_norm in text1_norm:
            contains_similarity = 0.3

        # Combinar métricas
        return min(1.0, jaccard + contains_similarity)

    def search_track_hierarchical(self, track_info: Dict[str, str]) -> MatchResult:
        """
        Búsqueda JERÁRQUICA mejorada:
        1. Buscar por album_artist
        2. Filtrar por álbum
        3. Seleccionar por título

        Este es el método PRINCIPAL mejorado.
        """
        self.match_stats['total_attempts'] += 1

        album_artist = track_info.get('album_artist', '').strip()
        artist = track_info.get('artist', album_artist).strip()
        title = track_info.get('title', '').strip()
        album = track_info.get('album', '').strip()

        if not album_artist or not title:
            self.match_stats['not_found'] += 1
            return MatchResult(
                success=False,
                song_id=None,
                confidence=0.0,
                matched_artist='',
                matched_album='',
                matched_title='',
                match_path='missing_data',
                reason=f"Faltan datos básicos: album_artist='{album_artist}', title='{title}'"
            )

        # PASO 1: Búsqueda exacta en cache
        cache_keys = []
        if album:
            cache_keys.append(f"{self._normalize_text(album_artist)}|{self._normalize_text(album)}|{self._normalize_text(title)}")
        cache_keys.append(f"{self._normalize_text(album_artist)}|{self._normalize_text(title)}")

        for cache_key in cache_keys:
            if cache_key in self._song_cache:
                cached_song = self._song_cache[cache_key]
                song_id = cached_song['id'] if isinstance(cached_song, dict) else str(cached_song)

                self.match_stats['cache_hits'] += 1
                self.match_stats['exact_matches'] += 1

                if self.verbose:
                    self.logger.debug(f"✅ CACHE HIT (exacto): {album_artist} - {title} [{album}]")

                return MatchResult(
                    success=True,
                    song_id=song_id,
                    confidence=1.0,
                    matched_artist=cached_song.get('artist', ''),
                    matched_album=cached_song.get('album', ''),
                    matched_title=cached_song.get('title', ''),
                    match_path='cache_exact',
                    reason='Coincidencia exacta en cache'
                )

        # PASO 2: Búsqueda jerárquica en índice de album_artist
        album_artist_norm = self._normalize_text(album_artist)

        if album_artist_norm in self._album_artist_index:
            candidates = self._album_artist_index[album_artist_norm]

            if self.verbose:
                self.logger.debug(f"🔍 Encontrados {len(candidates)} candidatos para album_artist '{album_artist}'")

            # Filtrar por álbum si está disponible
            if album:
                album_norm = self._normalize_text(album)
                album_candidates = []

                for candidate in candidates:
                    candidate_album_norm = candidate.get('album_norm', '')
                    if not candidate_album_norm:
                        continue

                    album_similarity = self._calculate_text_similarity(album, candidate['album'])

                    if album_similarity >= self.match_config.album_threshold:
                        album_candidates.append((candidate, album_similarity))

                if album_candidates:
                    candidates_to_check = [c[0] for c in album_candidates]
                    if self.verbose:
                        self.logger.debug(f"📀 Filtrados a {len(candidates_to_check)} candidatos por álbum")
                else:
                    # Si require_album está activado y no hay coincidencias de álbum, rechazar
                    if self.match_config.require_album:
                        self.match_stats['album_required_rejected'] += 1
                        self.match_stats['album_mismatch'] += 1
                        return MatchResult(
                            success=False,
                            song_id=None,
                            confidence=0.0,
                            matched_artist='',
                            matched_album='',
                            matched_title='',
                            match_path='album_required_failed',
                            reason=f"No se encontró álbum '{album}' (requerido en modo {self.match_config.mode.value})"
                        )
                    else:
                        # En modo no-estricto, continuar con todos los candidatos
                        candidates_to_check = candidates
                        if self.verbose:
                            self.logger.debug(f"⚠️  Álbum no encontrado, continuando con {len(candidates)} candidatos")
            else:
                candidates_to_check = candidates

            # Buscar por título en los candidatos filtrados
            best_match = None
            best_similarity = 0.0

            for candidate in candidates_to_check:
                title_similarity = self._calculate_text_similarity(title, candidate['title'])

                if title_similarity >= self.match_config.title_threshold:
                    if title_similarity > best_similarity:
                        best_similarity = title_similarity
                        best_match = candidate

            if best_match:
                is_exact = best_similarity >= 0.95
                if is_exact:
                    self.match_stats['exact_matches'] += 1
                else:
                    self.match_stats['fuzzy_matches'] += 1

                if self.verbose:
                    self.logger.debug(f"✅ MATCH JERÁRQUICO: {best_match['artist']} - {best_match['title']} "
                                    f"[{best_match['album']}] (similitud: {best_similarity:.2%})")

                return MatchResult(
                    success=True,
                    song_id=best_match['id'],
                    confidence=best_similarity,
                    matched_artist=best_match['artist'],
                    matched_album=best_match['album'],
                    matched_title=best_match['title'],
                    match_path='hierarchical_search',
                    reason=f"Match jerárquico con {best_similarity:.0%} similitud en título"
                )
            else:
                self.match_stats['title_mismatch'] += 1
                if self.verbose:
                    self.logger.debug(f"❌ No se encontró título '{title}' entre los candidatos")

        # PASO 3: Búsqueda en API como último recurso (solo en modo fuzzy)
        if self.match_config.mode == MatchMode.FUZZY:
            self.match_stats['api_searches'] += 1

            if self.verbose:
                self.logger.debug(f"🌐 Búsqueda en API (modo fuzzy): {album_artist} - {title}")

            try:
                query = f'"{album_artist}" "{title}"'
                if album:
                    query = f'"{album_artist}" "{title}" "{album}"'

                response = self._make_request('search3', {'query': query, 'songCount': 10})

                if response and 'searchResult3' in response:
                    songs = response['searchResult3'].get('song', [])

                    for song in songs:
                        song_artist = song.get('artist', '')
                        song_album_artist = song.get('albumArtist', song_artist)
                        song_title = song.get('title', '')
                        song_album = song.get('album', '')
                        song_id = song.get('id')

                        if isinstance(song_id, list):
                            song_id = song_id[0] if song_id else None
                        if not song_id:
                            continue
                        song_id = str(song_id)

                        # Verificar similitudes
                        artist_sim = self._calculate_text_similarity(album_artist, song_album_artist)
                        title_sim = self._calculate_text_similarity(title, song_title)

                        if artist_sim >= self.match_config.artist_threshold and title_sim >= self.match_config.title_threshold:
                            # Verificar álbum si está disponible
                            if album and song_album:
                                album_sim = self._calculate_text_similarity(album, song_album)
                                if album_sim < self.match_config.album_threshold:
                                    continue

                            confidence = (artist_sim + title_sim) / 2
                            self.match_stats['fuzzy_matches'] += 1

                            if self.verbose:
                                self.logger.debug(f"✅ API MATCH: {song_artist} - {song_title} [{song_album}] "
                                                f"(confianza: {confidence:.2%})")

                            return MatchResult(
                                success=True,
                                song_id=song_id,
                                confidence=confidence,
                                matched_artist=song_artist,
                                matched_album=song_album,
                                matched_title=song_title,
                                match_path='api_search',
                                reason=f"Match en API con {confidence:.0%} confianza"
                            )

            except Exception as e:
                self.logger.debug(f"Error en búsqueda API: {e}")

        # No se encontró
        self.match_stats['not_found'] += 1
        return MatchResult(
            success=False,
            song_id=None,
            confidence=0.0,
            matched_artist='',
            matched_album='',
            matched_title='',
            match_path='not_found',
            reason=f"No se encontró match con criterios del modo {self.match_config.mode.value}"
        )

    def get_airsonic_playlist(self, name: str) -> Optional[Dict]:
        """Obtiene una playlist de Airsonic por nombre"""
        try:
            response = self._make_request('getPlaylists')
            if response and 'playlists' in response:
                playlists = response['playlists'].get('playlist', [])
                for playlist in playlists:
                    if playlist.get('name') == name:
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
                return None

            params = {'name': name, 'songId': song_ids}
            response = self._make_request('createPlaylist', params)

            if response and 'playlist' in response:
                playlist_id = response['playlist']['id']
                self.logger.info(f"Playlist '{name}' creada con {len(song_ids)} canciones")
                return playlist_id

            return None
        except Exception as e:
            self.logger.error(f"Error creando playlist: {e}")
            return None

    def update_airsonic_playlist(self, playlist_id: str, new_song_ids: Set[str], current_song_ids: Set[str]) -> bool:
        """Actualiza una playlist existente"""
        try:
            to_add = new_song_ids - current_song_ids
            to_remove = current_song_ids - new_song_ids

            self.logger.info(f"Cambios: +{len(to_add)} canciones, -{len(to_remove)} canciones")

            if to_add:
                params = {
                    'playlistId': playlist_id,
                    'songIdToAdd': list(to_add)
                }
                response = self._make_request('updatePlaylist', params)
                if not response:
                    self.logger.error("Error añadiendo canciones")
                    return False

            if to_remove:
                for song_id in to_remove:
                    index = self._get_song_index_in_playlist(playlist_id, song_id)
                    if index is not None:
                        params = {
                            'playlistId': playlist_id,
                            'songIndexToRemove': index
                        }
                        self._make_request('updatePlaylist', params)

            return True
        except Exception as e:
            self.logger.error(f"Error actualizando playlist: {e}")
            return False

    def _get_song_index_in_playlist(self, playlist_id: str, song_id: str) -> Optional[int]:
        """Obtiene el índice de una canción en una playlist"""
        try:
            response = self._make_request('getPlaylist', {'id': playlist_id})
            if response and 'playlist' in response:
                entries = response['playlist'].get('entry', [])
                for i, entry in enumerate(entries):
                    if entry.get('id') == song_id:
                        return i
            return None
        except Exception as e:
            return None

    def sync_m3u_to_airsonic(self, m3u_path: str, playlist_name: Optional[str] = None,
                            force_full_sync: bool = False, dry_run: bool = False) -> bool:
        """
        Sincroniza un archivo M3U con Airsonic usando búsqueda jerárquica mejorada.
        """
        if not os.path.exists(m3u_path):
            self.logger.error(f"Archivo M3U no encontrado: {m3u_path}")
            return False

        if not playlist_name:
            playlist_name = Path(m3u_path).stem

        # Verificar cambios
        current_hash = self._get_m3u_hash(m3u_path)
        playlist_state = self.sync_state["playlists"].get(playlist_name, {})
        last_hash = playlist_state.get("hash", "")

        if not force_full_sync and current_hash == last_hash:
            self.logger.info(f"No hay cambios en {playlist_name}, omitiendo sincronización")
            return True

        self.logger.info(f"🎵 Iniciando sincronización de {playlist_name}")
        if self.interactive:
            print(f"\n{'='*60}")
            print(f"🎵 SINCRONIZANDO: {playlist_name}")
            print(f"{'='*60}")

        # Parsear M3U
        tracks = self.parse_m3u_file(m3u_path)
        self.logger.info(f"📁 Procesados {len(tracks)} archivos del M3U")

        if not tracks:
            self.logger.warning(f"No se encontraron tracks válidos en {m3u_path}")
            return False

        # Buscar canciones usando búsqueda jerárquica
        airsonic_song_ids = set()
        match_details = []

        # Resetear estadísticas para este sync
        sync_stats = {
            'exact': 0,
            'fuzzy': 0,
            'not_found': 0,
            'by_metadata': 0,
            'by_extinf': 0
        }

        for i, track_info in enumerate(tracks, 1):
            if self.interactive:
                album_info = f" [{track_info['album']}]" if track_info.get('album') else ""
                print(f"\r[{i}/{len(tracks)}] Procesando: {track_info['album_artist']} - {track_info['title']}{album_info}...", end='')

            # BÚSQUEDA JERÁRQUICA MEJORADA
            match_result = self.search_track_hierarchical(track_info)

            if match_result.success:
                airsonic_song_ids.add(match_result.song_id)

                if match_result.confidence >= 0.95:
                    sync_stats['exact'] += 1
                else:
                    sync_stats['fuzzy'] += 1

                if track_info.get('source') == 'metadata':
                    sync_stats['by_metadata'] += 1
                else:
                    sync_stats['by_extinf'] += 1

                match_details.append({
                    'track': track_info,
                    'result': match_result,
                    'matched': True
                })

                if self.verbose:
                    self.logger.debug(f"✅ [{match_result.match_path}] {track_info['album_artist']} - "
                                    f"{track_info['title']} -> {match_result.matched_artist} - "
                                    f"{match_result.matched_title} (conf: {match_result.confidence:.0%})")
            else:
                sync_stats['not_found'] += 1
                match_details.append({
                    'track': track_info,
                    'result': match_result,
                    'matched': False
                })

                if self.verbose:
                    self.logger.warning(f"❌ No encontrado: {track_info['album_artist']} - "
                                      f"{track_info['title']} [{track_info.get('album', 'N/A')}] - "
                                      f"Razón: {match_result.reason}")

            time.sleep(0.02)  # Rate limiting suave

        if self.interactive:
            print()  # Nueva línea después del progreso

        # Mostrar estadísticas
        success_rate = len(airsonic_song_ids) / len(tracks) * 100 if tracks else 0

        print(f"\n{'='*60}")
        print(f"📊 ESTADÍSTICAS DE MATCHING - Modo: {self.match_config.mode.value.upper()}")
        print(f"{'='*60}")
        print(f"Total de tracks:           {len(tracks)}")
        print(f"✅ Encontrados:            {len(airsonic_song_ids)} ({success_rate:.1f}%)")
        print(f"   - Matches exactos:      {sync_stats['exact']}")
        print(f"   - Matches fuzzy:        {sync_stats['fuzzy']}")
        print(f"   - Por metadata:         {sync_stats['by_metadata']}")
        print(f"   - Por EXTINF:           {sync_stats['by_extinf']}")
        print(f"❌ No encontrados:         {sync_stats['not_found']}")
        print(f"{'='*60}")

        # Mostrar detalles de no encontrados
        if sync_stats['not_found'] > 0 and self.interactive:
            print(f"\n⚠️  CANCIONES NO ENCONTRADAS:")
            not_found_tracks = [d for d in match_details if not d['matched']]
            for i, detail in enumerate(not_found_tracks[:10], 1):
                track = detail['track']
                result = detail['result']
                album_info = f" [{track.get('album', 'N/A')}]" if track.get('album') else ""
                print(f"  {i}. {track['album_artist']} - {track['title']}{album_info}")
                print(f"     Razón: {result.reason}")

            if len(not_found_tracks) > 10:
                print(f"  ... y {len(not_found_tracks) - 10} más")

        # Guardar estadísticas
        self._save_match_stats()

        # Sincronizar con Airsonic (si no es dry-run)
        if dry_run:
            print(f"\n🔍 DRY-RUN: No se realizaron cambios en Airsonic")
            return True

        if airsonic_song_ids:
            try:
                existing_playlist = self.get_airsonic_playlist(playlist_name)

                if existing_playlist:
                    current_song_ids = set(entry['id'] for entry in existing_playlist.get('entry', []))
                    success = self.update_airsonic_playlist(existing_playlist['id'], airsonic_song_ids, current_song_ids)
                    playlist_id = existing_playlist['id']
                else:
                    playlist_id = self.create_airsonic_playlist(playlist_name, list(airsonic_song_ids))
                    success = playlist_id is not None

                if success:
                    self.sync_state["playlists"][playlist_name] = {
                        "hash": current_hash,
                        "airsonic_id": playlist_id,
                        "last_sync": datetime.now().isoformat(),
                        "tracks_found": len(airsonic_song_ids),
                        "tracks_total": len(tracks),
                        "match_mode": self.match_config.mode.value,
                        "success_rate": success_rate
                    }
                    self._save_sync_state()

                    print(f"\n✅ Sincronización completada exitosamente")
                    return True
                else:
                    self.logger.error("Error en la sincronización")
                    return False

            except Exception as e:
                self.logger.error(f"Error en sincronización: {e}")
                return False
        else:
            self.logger.warning("No se encontraron canciones válidas para sincronizar")
            return False


def main():
    """Función principal"""
    parser = argparse.ArgumentParser(
        description='Sincronizador M3U a Airsonic - VERSIÓN MEJORADA CON BÚSQUEDA JERÁRQUICA',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
MODOS DE MATCHING:
  strict    - Requiere coincidencia casi exacta en album_artist, album y title
              Umbrales: artist=95%, album=90%, title=95%, require_album=True

  balanced  - Balance entre precisión y recall (DEFAULT)
              Umbrales: artist=85%, album=80%, title=90%, require_album=False

  fuzzy     - Más permisivo, acepta similitudes mayores
              Umbrales: artist=70%, album=65%, title=80%, require_album=False

EJEMPLOS:
  # Modo interactivo con configuración balanceada (default)
  python script.py

  # Modo estricto para máxima precisión
  python script.py --match-mode strict

  # Modo fuzzy para encontrar más matches
  python script.py --match-mode fuzzy

  # Sincronizar playlist específica en modo verbose
  python script.py --playlist "Mi Playlist" --verbose

  # Dry-run para ver qué haría sin hacer cambios
  python script.py --dry-run --verbose

  # Modo cron (automático, sin interacción)
  python script.py --cron --match-mode balanced
        """
    )

    parser.add_argument('--cron', action='store_true',
                       help='Modo no interactivo (para cron)')
    parser.add_argument('--force', action='store_true',
                       help='Forzar sincronización completa')
    parser.add_argument('--playlist', type=str,
                       help='Sincronizar playlist específica')
    parser.add_argument('--m3u-folder', type=str,
                       help='Carpeta con archivos M3U')
    parser.add_argument('--rebuild-cache', action='store_true',
                       help='Reconstruir cache de canciones')
    parser.add_argument('--data-dir', type=str,
                       help='Directorio para archivos de estado')
    parser.add_argument('--dry-run', action='store_true',
                       help='Solo mostrar qué se haría sin hacer cambios')
    parser.add_argument('--match-mode', type=str,
                       choices=['strict', 'balanced', 'fuzzy'],
                       default='balanced',
                       help='Modo de matching (default: balanced)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Mostrar información detallada de debugging')

    args = parser.parse_args()

    # Convertir string a enum
    match_mode = MatchMode(args.match_mode)

    M3U_FOLDER = Path(args.m3u_folder) if args.m3u_folder else Path(DEFAULT_M3U_FOLDER)
    DATA_DIR = Path(args.data_dir) if args.data_dir else Path(DEFAULT_DATA_DIR)

    if not args.cron:
        print("🎵 SINCRONIZADOR M3U -> AIRSONIC (VERSIÓN MEJORADA)")
        print("=" * 60)
        print("✨ CARACTERÍSTICAS:")
        print("  - Búsqueda jerárquica: album_artist → album → title")
        print("  - Tres modos de matching configurables")
        print("  - Estadísticas detalladas de matches")
        print("  - Mejor manejo de falsos positivos")
        print()

    try:
        syncer = AirsonicMetadataSyncImproved(
            interactive=not args.cron,
            data_dir=str(DATA_DIR),
            match_mode=match_mode,
            verbose=args.verbose
        )

        if args.rebuild_cache:
            syncer._song_cache = {}
            syncer._album_artist_index = {}
            syncer._build_song_cache()
            if not args.playlist:
                return

        # Buscar archivos M3U
        if args.playlist:
            m3u_path = M3U_FOLDER / f"{args.playlist}.m3u"
            if not m3u_path.exists():
                print(f"❌ Archivo no encontrado: {m3u_path}")
                sys.exit(1)
            files_to_sync = [m3u_path]
        else:
            files_to_sync = list(M3U_FOLDER.glob("*.m3u"))
            if not files_to_sync:
                print(f"❌ No se encontraron archivos .m3u en {M3U_FOLDER}")
                sys.exit(1)

        if not args.cron:
            print(f"📁 Encontrados {len(files_to_sync)} archivos M3U:")
            for f in files_to_sync:
                print(f"  - {f.name}")

        # Sincronizar archivos
        successful = 0
        for m3u_file in files_to_sync:
            if syncer.sync_m3u_to_airsonic(str(m3u_file),
                                          force_full_sync=args.force,
                                          dry_run=args.dry_run):
                successful += 1

        # Mostrar estadísticas globales
        if not args.cron:
            print(f"\n{'='*60}")
            print(f"📊 ESTADÍSTICAS GLOBALES")
            print(f"{'='*60}")
            print(f"Total intentos de match:    {syncer.match_stats['total_attempts']}")
            print(f"Matches exactos:            {syncer.match_stats['exact_matches']}")
            print(f"Matches fuzzy:              {syncer.match_stats['fuzzy_matches']}")
            print(f"Cache hits:                 {syncer.match_stats['cache_hits']}")
            print(f"Búsquedas API:              {syncer.match_stats['api_searches']}")
            print(f"No encontrados:             {syncer.match_stats['not_found']}")
            if syncer.match_stats['album_required_rejected'] > 0:
                print(f"Rechazados (álbum req.):    {syncer.match_stats['album_required_rejected']}")
            print(f"{'='*60}")

            action = "analizadas" if args.dry_run else "sincronizadas"
            print(f"\n✅ {successful}/{len(files_to_sync)} playlists {action}")

    except KeyboardInterrupt:
        print("\n\n⚠️  Proceso interrumpido por usuario")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
