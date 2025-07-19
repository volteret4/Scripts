#!/usr/bin/env python3
"""
VVMM Post Creator - Python Version
Creador automático de posts para blog VVMM

Author: volteret4
Repository: https://github.com/volteret4/
License: MIT
"""

import os
import sys
import subprocess
import argparse
import logging
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import json
import shutil
import signal
import tempfile

# Third-party imports
try:
    import requests
    from dotenv import load_dotenv
    from bs4 import BeautifulSoup
except ImportError as e:
    print(f"Error: Falta instalar dependencias básicas: {e}")
    print("Ejecuta: pip install requests python-dotenv beautifulsoup4")
    sys.exit(1)

# Optional imports
try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials
    SPOTIFY_AVAILABLE = True
except ImportError:
    SPOTIFY_AVAILABLE = False


class VVMMPostCreator:
    """Clase principal para crear posts del blog VVMM"""

    def _validate_scripts(self):
        """Validar y corregir permisos de scripts"""
        scripts_to_check = [
            'limpia_var.sh',
            'lastfm.sh',
            'portada_mb.sh'
        ]

        for script_name in scripts_to_check:
            script_path = self.modules_dir / script_name
            if script_path.exists():
                try:
                    # Asegurar que el script es ejecutable
                    os.chmod(script_path, 0o755)
                    self.logger.debug(f"Permisos corregidos para {script_name}")
                except Exception as e:
                    self.logger.warning(f"No se pudieron corregir permisos de {script_name}: {e}")

    def __init__(self, project_root: str = None):
        """Inicializar el creador de posts"""
        # Configurar rutas
        self.script_dir = Path(__file__).parent.absolute()
        self.project_root = Path(project_root) if project_root else self.script_dir
        self.modules_dir = self.project_root / "modules"
        self.content_dir = self.project_root / ".content"
        self.logs_dir = self.content_dir / "logs"
        self.cache_dir = self.content_dir / "cache"

        # Crear directorios necesarios
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Configurar logging
        self._setup_logging()

        # Validar scripts
        self._validate_scripts()

        # Cargar configuración
        self._load_environment()

        # Variables de estado
        self.current_metadata = {}
        self.database_data = {}
        self.post_file = None
        self.links = {}
        self.success = True

    def _setup_logging(self):
        """Configurar sistema de logging"""
        log_file = self.logs_dir / f"vvmm_{datetime.now().strftime('%Y%m%d')}.log"

        # Configurar formatters
        file_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        console_formatter = logging.Formatter(
            '%(levelname)s: %(message)s'
        )

        # Configurar logger principal
        self.logger = logging.getLogger('vvmm')
        self.logger.setLevel(logging.DEBUG)

        # Handler para archivo
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(file_formatter)

        # Handler para consola
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(console_formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def _load_environment(self):
        """Cargar variables de entorno"""
        env_file = self.project_root / ".env"
        if not env_file.exists():
            self.logger.error(f"No se encontró .env en {env_file}")
            sys.exit(1)

        load_dotenv(env_file)

        # Variables requeridas
        required_vars = [
            'SPOTIFY_CLIENT', 'SPOTIFY_SECRET', 'DISCOGS_TOKEN'
        ]

        for var in required_vars:
            if not os.getenv(var):
                self.logger.warning(f"Variable {var} no configurada")

        # Configuración
        self.config = {
            'blog_dir': Path(os.getenv('BLOG_DIR', '/mnt/NFS/blogs/vvmm')),
            'database_path': Path(os.getenv('DATABASE_PATH', self.project_root / 'music_database.db')),
            'python_venv_path': os.getenv('PYTHON_VENV_PATH'),
            'enable_spotify': os.getenv('ENABLE_SPOTIFY_INTEGRATION', 'true').lower() == 'true',
            'enable_preview': os.getenv('ENABLE_PREVIEW', 'true').lower() == 'true',
            'enable_git_push': os.getenv('ENABLE_GIT_PUSH', 'true').lower() == 'true',
            'debug_mode': os.getenv('DEBUG_MODE', 'false').lower() == 'true'
        }

    def get_current_song_metadata(self) -> bool:
        """Obtener metadata de la canción en reproducción usando playerctl"""
        self.logger.info("Obteniendo metadata de la canción en reproducción...")

        try:
            # Obtener reproductores disponibles
            result = subprocess.run(['playerctl', '-l'],
                                  capture_output=True, text=True, check=True)
            players = result.stdout.strip().split('\n')

            if not players or players == ['']:
                self.logger.error("No hay reproductores disponibles")
                self._notify("Error", "No hay reproductores de música activos")
                return False

        except subprocess.CalledProcessError:
            self.logger.error("playerctl no está disponible")
            self._notify("Error", "playerctl no está instalado")
            return False

        # Buscar reproductor activo
        active_player = None
        for player in players:
            try:
                status = subprocess.run(['playerctl', '-p', player, 'status'],
                                      capture_output=True, text=True, check=True)
                if status.stdout.strip() == 'Playing':
                    active_player = player
                    break
            except subprocess.CalledProcessError:
                continue

        if not active_player:
            active_player = players[0]  # Usar el primero disponible

        self.logger.info(f"Reproductor detectado: {active_player}")

        # Obtener metadata
        try:
            def get_metadata(field):
                try:
                    result = subprocess.run(['playerctl', '-p', active_player, 'metadata', field],
                                          capture_output=True, text=True, check=True)
                    return result.stdout.strip().replace('"', '').replace(':', '')
                except subprocess.CalledProcessError:
                    return ""

            artist_raw = get_metadata('artist')
            album_raw = get_metadata('album')
            title_raw = get_metadata('title')

            if not artist_raw or not title_raw:
                self.logger.error("No se pudo obtener metadata suficiente")
                self._notify("Error", "No se pudo obtener información de la canción")
                return False

            # Si no hay álbum, usar título
            if not album_raw:
                album_raw = title_raw
                self.logger.warning("No se encontró álbum, usando título")

            # NUEVA ESTRATEGIA: Usar metadata RAW para búsqueda en BD, limpia solo para URLs
            self.current_metadata = {
                'artist_raw': artist_raw,
                'album_raw': album_raw,
                'title_raw': title_raw,
                # Para BD: usar datos casi sin procesar (solo reemplazar & por and)
                'artist': artist_raw.replace('&', 'and').strip(),
                'album': album_raw.replace('&', 'and').strip(),
                # Para URLs: procesamiento más agresivo
                'artist_processed': self._process_for_url(artist_raw),
                'album_processed': self._process_for_url(album_raw)
            }

            self.logger.info(f"Metadata obtenida: '{self.current_metadata['artist']}' - '{self.current_metadata['album']}'")
            self.logger.debug(f"RAW: '{artist_raw}' - '{album_raw}'")
            self.logger.debug(f"Para URLs: '{self.current_metadata['artist_processed']}' - '{self.current_metadata['album_processed']}'")
            return True

        except Exception as e:
            self.logger.error(f"Error obteniendo metadata: {e}")
            return False

    def _clean_variable(self, text: str) -> str:
        """Limpiar variables de texto (versión menos agresiva)"""
        import re

        # Solo reemplazar & por and, mantener guiones y caracteres especiales
        cleaned = text.replace('&', 'and')

        # Limpiar solo caracteres realmente problemáticos, mantener guiones
        # Mantener: letras, números, espacios, guiones, puntos, apostrofes
        cleaned = re.sub(r'[^\w\s\-\.\']', '', cleaned)

        # Limpiar espacios múltiples pero mantener espacios simples
        cleaned = ' '.join(cleaned.split())

        return cleaned.strip()

    def _process_for_url(self, text: str) -> str:
        """Procesar texto para URL (reemplazar acentos, espacios, etc.)"""
        import unicodedata
        import re

        # Normalizar y quitar acentos
        nfkd = unicodedata.normalize('NFKD', text)
        without_accents = ''.join([c for c in nfkd if not unicodedata.combining(c)])

        # Reemplazos específicos problemáticos
        processed = (without_accents
                    .replace('&', 'and')
                    .replace("'", '-')
                    .replace('`', '-')
                    .replace('.', '-')  # NUEVO: Reemplazar puntos por guiones
                    .replace(',', '-')  # NUEVO: Reemplazar comas por guiones
                    .replace(':', '-')  # NUEVO: Reemplazar dos puntos por guiones
                    .replace(';', '-')  # NUEVO: Reemplazar punto y coma por guiones
                    .replace('(', '-')  # NUEVO: Reemplazar paréntesis por guiones
                    .replace(')', '-')
                    .replace('[', '-')  # NUEVO: Reemplazar corchetes por guiones
                    .replace(']', '-')
                    .replace('{', '-')  # NUEVO: Reemplazar llaves por guiones
                    .replace('}', '-')
                    .replace('!', '-')  # NUEVO: Reemplazar exclamaciones por guiones
                    .replace('?', '-')  # NUEVO: Reemplazar interrogaciones por guiones
                    .replace('#', '-')  # NUEVO: Reemplazar hashtags por guiones
                    .replace('@', '-')  # NUEVO: Reemplazar arrobas por guiones
                    .replace('%', '-')  # NUEVO: Reemplazar porcentajes por guiones
                    .replace('$', '-')  # NUEVO: Reemplazar dólares por guiones
                    .replace('+', '-')  # NUEVO: Reemplazar más por guiones
                    .replace('=', '-')  # NUEVO: Reemplazar igual por guiones
                    .replace('/', '-')  # NUEVO: Reemplazar barras por guiones
                    .replace('\\', '-') # NUEVO: Reemplazar barras invertidas por guiones
                    .replace('|', '-')  # NUEVO: Reemplazar pipes por guiones
                    .replace('<', '-')  # NUEVO: Reemplazar menor que por guiones
                    .replace('>', '-')  # NUEVO: Reemplazar mayor que por guiones
                    .replace('"', '-')  # NUEVO: Reemplazar comillas dobles por guiones
                    .replace('*', '-')  # NUEVO: Reemplazar asteriscos por guiones
                    .replace('~', '-')  # NUEVO: Reemplazar tildes por guiones
                    .replace('^', '-')  # NUEVO: Reemplazar circunflejo por guiones
                    )

        # Limpiar caracteres especiales restantes (solo mantener letras, números y guiones)
        processed = re.sub(r'[^\w\s-]', '-', processed)

        # Reemplazar espacios por guiones
        processed = re.sub(r'\s+', '-', processed)

        # Limpiar múltiples guiones consecutivos
        processed = re.sub(r'-+', '-', processed)

        # Quitar guiones al inicio y final
        processed = processed.strip('-')

        # Convertir a minúsculas para consistencia
        processed = processed.lower()

        return processed

    def _normalize_for_db_search(self, text: str) -> str:
        """Normalizar texto para búsqueda en base de datos"""
        import unicodedata
        import re

        if not text:
            return ""

        # 1. Normalizar Unicode y quitar acentos
        nfkd = unicodedata.normalize('NFKD', text)
        without_accents = ''.join([c for c in nfkd if not unicodedata.combining(c)])

        # 2. Reemplazos específicos para caracteres problemáticos
        normalized = (without_accents
                     .replace('…', '')      # NUEVO: Quitar puntos suspensivos Unicode
                     .replace('...', '')    # NUEVO: Quitar tres puntos
                     .replace('..', '')     # NUEVO: Quitar dos puntos
                     .replace('&', 'and')
                     .replace("'", "")      # Quitar apostrofes
                     .replace('`', "")      # Quitar acentos graves
                     .replace('.', '')      # Quitar puntos
                     .replace(',', '')      # Quitar comas
                     .replace(':', '')      # Quitar dos puntos
                     .replace(';', '')      # Quitar punto y coma
                     .replace('!', '')      # Quitar exclamaciones
                     .replace('?', '')      # Quitar interrogaciones
                     .replace('(', '')      # Quitar paréntesis
                     .replace(')', '')
                     .replace('[', '')      # Quitar corchetes
                     .replace(']', '')
                     .replace('{', '')      # Quitar llaves
                     .replace('}', '')
                     .replace('-', ' ')     # Convertir guiones a espacios
                     .replace('_', ' ')     # Convertir guiones bajos a espacios
                     .replace('–', ' ')     # NUEVO: Guión largo
                     .replace('—', ' ')     # NUEVO: Guión aún más largo
                     .replace('"', '')      # NUEVO: Comillas dobles
                     .replace('"', '')      # NUEVO: Comillas Unicode izquierda
                     .replace('"', '')      # NUEVO: Comillas Unicode derecha
                     .replace(''', '')      # NUEVO: Comillas simples Unicode
                     .replace(''', '')      # NUEVO: Comillas simples Unicode
                     )

        # 3. Limpiar caracteres especiales restantes
        normalized = re.sub(r'[^\w\s]', '', normalized)

        # 4. Normalizar espacios
        normalized = ' '.join(normalized.split())

        # 5. Convertir a minúsculas
        return normalized.lower().strip()


    def check_database_first(self) -> bool:
        """Verificar si existe información en la base de datos con búsqueda mejorada"""
        self.logger.info("Verificando si existe información en la base de datos...")

        if not self.config['database_path'].exists():
            self.logger.warning(f"Base de datos no encontrada en {self.config['database_path']}")
            return False

        try:
            conn = sqlite3.connect(self.config['database_path'])
            cursor = conn.cursor()

            artist = self.current_metadata['artist']
            album = self.current_metadata['album']

            self.logger.debug(f"Buscando en BD: '{artist}' - '{album}'")

            # ESTRATEGIAS DE BÚSQUEDA MEJORADAS
            search_strategies = [
                # 1. Búsqueda exacta (como antes)
                {
                    'name': 'exacta',
                    'artist_search': artist,
                    'album_search': album,
                    'query': """
                        SELECT a.name, al.name FROM albums al
                        JOIN artists a ON al.artist_id = a.id
                        WHERE TRIM(a.name) = TRIM(?) AND TRIM(al.name) = TRIM(?)
                        LIMIT 1;
                    """
                },

                # 2. Búsqueda con datos RAW
                {
                    'name': 'raw',
                    'artist_search': self.current_metadata['artist_raw'],
                    'album_search': self.current_metadata['album_raw'],
                    'query': """
                        SELECT a.name, al.name FROM albums al
                        JOIN artists a ON al.artist_id = a.id
                        WHERE TRIM(a.name) = TRIM(?) AND TRIM(al.name) = TRIM(?)
                        LIMIT 1;
                    """
                },

                # 3. Búsqueda caso insensitivo
                {
                    'name': 'case insensitive',
                    'artist_search': artist.lower(),
                    'album_search': album.lower(),
                    'query': """
                        SELECT a.name, al.name FROM albums al
                        JOIN artists a ON al.artist_id = a.id
                        WHERE LOWER(TRIM(a.name)) = LOWER(TRIM(?)) AND LOWER(TRIM(al.name)) = LOWER(TRIM(?))
                        LIMIT 1;
                    """
                },

                # 4. NUEVA: Búsqueda normalizada (sin acentos, puntos, etc.)
                {
                    'name': 'normalizada',
                    'artist_search': self._normalize_for_db_search(artist),
                    'album_search': self._normalize_for_db_search(album),
                    'query': """
                        SELECT a.name, al.name FROM albums al
                        JOIN artists a ON al.artist_id = a.id
                        WHERE LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(TRIM(a.name), '.', ''), '!', ''), '?', ''), '(', ''), ')', ''), '-', ' '), '…', ''), '...', ''), '"', ''))
                              = LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(TRIM(?), '.', ''), '!', ''), '?', ''), '(', ''), ')', ''), '-', ' '), '…', ''), '...', ''), '"', ''))
                        AND LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(TRIM(al.name), '.', ''), '!', ''), '?', ''), '(', ''), ')', ''), '-', ' '), '…', ''), '...', ''), '"', ''))
                            = LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(TRIM(?), '.', ''), '!', ''), '?', ''), '(', ''), ')', ''), '-', ' '), '…', ''), '...', ''), '"', ''))
                        LIMIT 1;
                    """
                },

                # 5. NUEVA: Búsqueda con LIKE (más flexible)
                {
                    'name': 'fuzzy',
                    'artist_search': f"%{self._normalize_for_db_search(artist)}%",
                    'album_search': f"%{self._normalize_for_db_search(album)}%",
                    'query': """
                        SELECT a.name, al.name FROM albums al
                        JOIN artists a ON al.artist_id = a.id
                        WHERE LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(a.name, '.', ''), '!', ''), '?', ''), '(', ''), ')', ''), '-', ' '), '…', ''), '...', ''), '"', ''))
                              LIKE LOWER(?)
                        AND LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(al.name, '.', ''), '!', ''), '?', ''), '(', ''), ')', ''), '-', ' '), '…', ''), '...', ''), '"', ''))
                            LIKE LOWER(?)
                        LIMIT 1;
                    """
                },

                # 6. NUEVA: Búsqueda solo por artista (si el álbum es muy problemático)
                {
                    'name': 'solo artista',
                    'artist_search': self._normalize_for_db_search(artist),
                    'album_search': '',
                    'query': """
                        SELECT a.name, al.name FROM albums al
                        JOIN artists a ON al.artist_id = a.id
                        WHERE LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(a.name, '.', ''), '!', ''), '?', ''), '(', ''), ')', ''), '-', ' '), '…', ''), '...', ''), '"', ''))
                              LIKE LOWER(?)
                        ORDER BY
                            CASE WHEN LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(al.name, '.', ''), '!', ''), '?', ''), '(', ''), ')', ''), '-', ' '), '…', ''), '...', ''), '"', ''))
                                      LIKE LOWER(?) THEN 1 ELSE 2 END
                        LIMIT 1;
                    """
                }
            ]

            test_result = None
            successful_strategy = None

            for strategy in search_strategies:
                strategy_name = strategy['name']
                artist_search = strategy['artist_search']
                album_search = strategy['album_search']
                query = strategy['query']

                self.logger.debug(f"Probando estrategia '{strategy_name}':")
                self.logger.debug(f"  Artista: '{artist_search}'")
                self.logger.debug(f"  Álbum: '{album_search}'")

                try:
                    if strategy_name == 'solo artista':
                        # Para búsqueda solo por artista, usar el álbum normalizado también
                        album_search_normalized = self._normalize_for_db_search(album)
                        cursor.execute(query, (f"%{artist_search}%", f"%{album_search_normalized}%"))
                    else:
                        cursor.execute(query, (artist_search, album_search))

                    test_result = cursor.fetchone()

                    if test_result:
                        successful_strategy = strategy_name
                        self.logger.info(f"✅ Encontrado con estrategia '{strategy_name}': '{test_result[0]}' - '{test_result[1]}'")
                        break
                    else:
                        self.logger.debug(f"❌ No encontrado con estrategia '{strategy_name}'")

                except sqlite3.Error as e:
                    self.logger.debug(f"Error en estrategia '{strategy_name}': {e}")
                    continue

            if not test_result:
                # Debug final: mostrar qué hay en la BD que se parezca
                self.logger.debug("🔍 Buscando artistas similares en la BD:")

                # Buscar artistas que contengan parte del nombre
                artist_words = self._normalize_for_db_search(artist).split()
                if artist_words:
                    search_word = artist_words[0]  # Usar la primera palabra
                    cursor.execute("""
                        SELECT DISTINCT a.name
                        FROM artists a
                        WHERE LOWER(a.name) LIKE LOWER(?)
                        ORDER BY a.name
                        LIMIT 5
                    """, (f"%{search_word}%",))

                    similar_artists = cursor.fetchall()
                    for (db_artist,) in similar_artists:
                        self.logger.debug(f"  Similar: '{db_artist}'")

                conn.close()
                return False

            # Si encontramos algo, hacer consulta completa usando los nombres reales de la BD
            found_artist, found_album = test_result
            self.logger.info(f"Haciendo consulta completa para: '{found_artist}' - '{found_album}'")
            self.logger.info(f"Estrategia exitosa: {successful_strategy}")

            # Consulta expandida con todos los enlaces usando nombres de la BD
            full_query = """
            SELECT
                -- Datos básicos
                a.name, al.name,

                -- Enlaces del álbum
                COALESCE(al.discogs_url, ''),
                COALESCE(al.musicbrainz_url, ''),
                COALESCE(al.spotify_url, ''),
                COALESCE(al.spotify_id, ''),
                COALESCE(al.bandcamp_url, ''),
                COALESCE(al.lastfm_url, ''),
                COALESCE(al.youtube_url, ''),
                COALESCE(al.wikipedia_url, ''),
                COALESCE(al.rateyourmusic_url, ''),

                -- Enlaces del artista
                COALESCE(a.spotify_url, ''),
                COALESCE(a.youtube_url, ''),
                COALESCE(a.musicbrainz_url, ''),
                COALESCE(a.discogs_url, ''),
                COALESCE(a.rateyourmusic_url, ''),
                COALESCE(a.wikipedia_url, ''),
                COALESCE(a.lastfm_url, ''),
                COALESCE(a.bandcamp_url, ''),
                COALESCE(a.website, ''),

                -- Información básica del álbum
                COALESCE(al.label, ''),
                COALESCE(al.year, ''),
                COALESCE(al.album_art_path, ''),
                COALESCE(al.genre, ''),
                al.total_tracks,
                al.id,
                a.id

            FROM albums al
            JOIN artists a ON al.artist_id = a.id
            WHERE a.name = ? AND al.name = ?
            LIMIT 1;
            """

            cursor.execute(full_query, (found_artist, found_album))
            result = cursor.fetchone()

            if result:
                self.logger.info(f"¡Información completa encontrada en base de datos! Artista BD: '{result[0]}', Album BD: '{result[1]}'")
                self._parse_database_result(result)
                conn.close()
                return True
            else:
                self.logger.warning("Error extraño: encontrado en búsqueda simple pero no en consulta completa")
                conn.close()
                return False

        except sqlite3.Error as e:
            self.logger.error(f"Error consultando base de datos: {e}")
            return False


    def _parse_database_result(self, result: tuple):
        """Parsear resultado de la base de datos"""
        fields = [
            'db_artist', 'db_album',
            'album_discogs_url', 'album_musicbrainz_url', 'album_spotify_url',
            'album_spotify_id', 'album_bandcamp_url', 'album_lastfm_url',
            'album_youtube_url', 'album_wikipedia_url', 'album_rateyourmusic_url',
            'artist_spotify_url', 'artist_youtube_url', 'artist_musicbrainz_url',
            'artist_discogs_url', 'artist_rateyourmusic_url', 'artist_wikipedia_url',
            'artist_lastfm_url', 'artist_bandcamp_url', 'artist_website',
            'record_label', 'release_year', 'cover_path', 'genre',
            'total_tracks', 'album_id', 'artist_id'
        ]

        self.database_data = dict(zip(fields, result))
        self.logger.debug(f"Datos de BD parseados: {self.database_data['db_artist']} - {self.database_data['db_album']}")

    def get_user_tags(self) -> bool:
        """Solicitar tags al usuario usando yad"""
        self.logger.info("Solicitando tags al usuario...")

        try:
            artist = self.current_metadata['artist']
            album = self.current_metadata['album']

            cmd = [
                'yad', '--entry',
                '--title=Comentario',
                '--text=' + f"{artist} {album}\nTAGS [x z y]:",
                '--entry-text='
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            tags_input = result.stdout.strip()

            if not tags_input:
                self._notify("Cancelando post", "Sin TAGS proporcionados")
                self.logger.warning("Post cancelado: Sin tags proporcionados")
                return False

            # Procesar tags especiales (como 'r' para editar artista/álbum)
            if tags_input == 'r':
                if not self._edit_artist_album():
                    return False
                return self.get_user_tags()  # Recursivo después de editar

            # Convertir tags a lista
            self.current_metadata['tags'] = tags_input.split()
            self.logger.info(f"Tags obtenidos: {self.current_metadata['tags']}")
            return True

        except subprocess.CalledProcessError:
            self.logger.error("Error solicitando tags al usuario")
            return False

    def _edit_artist_album(self) -> bool:
        """Permitir edición de artista y álbum"""
        try:
            # Editar artista
            cmd = ['yad', '--entry', '--text=Artista',
                   '--entry-text=' + self.current_metadata['artist']]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            new_artist = result.stdout.strip()

            if not new_artist:
                return False

            # Editar álbum
            cmd = ['yad', '--entry', '--text=Álbum',
                   '--entry-text=' + self.current_metadata['album']]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            new_album = result.stdout.strip()

            if not new_album:
                return False

            # Actualizar metadata
            self.current_metadata.update({
                'artist': new_artist,
                'album': new_album,
                'artist_processed': self._process_for_url(new_artist),
                'album_processed': self._process_for_url(new_album)
            })

            return True

        except subprocess.CalledProcessError:
            return False

    def create_hugo_post(self) -> bool:
        """Crear post de Hugo con slug mejorado"""
        self.logger.info("Creando post de Hugo...")

        try:
            os.chdir(self.config['blog_dir'])

            # Generar nombres de archivos con procesamiento mejorado
            artist_clean = self._process_for_url(self.current_metadata['artist'])
            album_clean = self._process_for_url(self.current_metadata['album'])

            # Crear slug con guión bajo para separar artista de álbum
            post_slug = f"{artist_clean}_-{album_clean}"

            # Verificar longitud y truncar si es necesario (Hugo tiene límites)
            if len(post_slug) > 100:
                # Truncar manteniendo proporción artista/álbum
                artist_max = min(len(artist_clean), 50)
                album_max = min(len(album_clean), 45)

                artist_truncated = artist_clean[:artist_max].rstrip('-')
                album_truncated = album_clean[:album_max].rstrip('-')

                post_slug = f"{artist_truncated}_-{album_truncated}"
                self.logger.warning(f"Slug truncado por longitud: {post_slug}")

            self.post_file = self.config['blog_dir'] / f"content/posts/{post_slug}/index.md"

            # Debug: mostrar el slug generado
            self.logger.info(f"Slug generado: {post_slug}")
            self.logger.debug(f"De: '{self.current_metadata['artist']}' - '{self.current_metadata['album']}'")

            # Verificar si el post ya existe
            if self.post_file.exists():
                self.logger.warning(f"El post ya existe: {self.post_file}")
                self._notify("Post existente", f"El post para {self.current_metadata['artist']} - {self.current_metadata['album']} ya existe")
                return False

            # Crear el post con Hugo
            cmd = ['hugo', 'new', '--kind', 'post-bundle', f'posts/{post_slug}']

            # Debug: mostrar comando exacto
            self.logger.debug(f"Comando Hugo: {' '.join(cmd)}")

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            # Log de salida de Hugo para debug
            if result.stdout:
                self.logger.debug(f"Hugo stdout: {result.stdout}")
            if result.stderr:
                self.logger.debug(f"Hugo stderr: {result.stderr}")

            self.logger.info(f"Post creado exitosamente: {self.post_file}")
            return True

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error al crear post con Hugo: {e}")
            if e.stdout:
                self.logger.error(f"Hugo stdout: {e.stdout}")
            if e.stderr:
                self.logger.error(f"Hugo stderr: {e.stderr}")
            return False
        except Exception as e:
            self.logger.error(f"Error inesperado creando post: {e}")
            return False


    def _test_normalization(self):
        """Función de prueba para verificar normalización"""
        test_cases = [
            "Ólafur Arnalds",
            "...And They Have Escaped The Weight Of Darkness",
            "…and They Have Escaped the Weight of Darkness",  # NUEVO: Como está en BD
            "Fontaines D.C.",
            "Sigur Rós",
            "Godspeed You! Black Emperor",
            "Mr. Bungle",
            "Thee Oh Sees"
        ]

        print("=== PRUEBAS DE NORMALIZACIÓN PARA BD ===")
        for text in test_cases:
            normalized = self._normalize_for_db_search(text)
            print(f"'{text}' -> '{normalized}'")

        # Prueba específica del caso problemático
        print("\n=== PRUEBA DEL CASO ESPECÍFICO ===")
        playerctl_album = "...And They Have Escaped The Weight Of Darkness"
        bd_album = "…and They Have Escaped the Weight of Darkness"

        playerctl_norm = self._normalize_for_db_search(playerctl_album)
        bd_norm = self._normalize_for_db_search(bd_album)

        print(f"Playerctl: '{playerctl_album}' -> '{playerctl_norm}'")
        print(f"BD:        '{bd_album}' -> '{bd_norm}'")
        print(f"¿Coinciden? {playerctl_norm == bd_norm}")
        print("="*50)


    def _test_slug_generation(self):
        """Función de prueba para verificar generación de slugs"""
        test_cases = [
            "Fontaines D.C.",
            "Ólafur Àrnalds",
            "Sigur Rós",
            "Björk",
            "A.C.T.",
            "Mr. Bungle",
            "!!!",
            "65daysofstatic",
            "Godspeed You! Black Emperor",
            "Mono & Nikitaman",
            "Sunn O)))",
            "Thee Oh Sees",
            "...And You Will Know Us by the Trail of Dead"
        ]

        print("=== PRUEBAS DE GENERACIÓN DE SLUGS ===")
        for artist in test_cases:
            slug = self._process_for_url(artist)
            print(f"'{artist}' -> '{slug}'")
        print("="*50)


    def generate_links_from_database(self):
        """Generar enlaces desde la base de datos"""
        self.logger.info("Generando enlaces desde base de datos...")

        self.links = {}

        # Función auxiliar para generar enlace
        def make_link(service, url, comment="not_in_db"):
            if url and url != "NULL" and url != "":
                return f'[![{service}](../links/svg/{service}.png ({service}))]({url})'
            else:
                return f'<!-- [![{service}](../links/svg/{service}.png ({service}))]({comment}) -->'

        # Enlaces principales (priorizar álbum, luego artista)
        services = ['bandcamp', 'discogs', 'spotify', 'youtube', 'lastfm',
                   'musicbrainz', 'wikipedia', 'rateyourmusic']

        for service in services:
            album_url = self.database_data.get(f'album_{service}_url', '')
            artist_url = self.database_data.get(f'artist_{service}_url', '')

            # Priorizar URL del álbum
            url = album_url if album_url and album_url != "NULL" else artist_url
            self.links[f'link_{service}'] = make_link(service, url)

        self.logger.info("Enlaces generados desde base de datos")

    def search_missing_services(self):
        """Buscar en servicios musicales para enlaces faltantes"""
        self.logger.info("Buscando enlaces en servicios musicales...")

        # Activar entorno Python si existe
        self._activate_python_env()

        artist = self.current_metadata['artist']
        album = self.current_metadata['album']

        # Diccionario de scripts de búsqueda (sin Spotify que lo manejamos directo)
        search_scripts = {
            'bandcamp': 'bandcamp.py',
            'lastfm': 'lastfm.sh',
            'musicbrainz': 'musicbrainz.py',
            'youtube': 'youtube.py',
            'wikipedia': 'wikipedia.py'
        }

        # Buscar solo los que faltan
        for service, script in search_scripts.items():
            if f'link_{service}' not in self.links or '<!--' in self.links[f'link_{service}']:
                url = self._run_search_script(script, artist, album)
                if url and url != "error":
                    self.links[f'url_{service}'] = url
                    service_link = f'[![{service}](../links/svg/{service}.png ({service}))]({url})'
                    self.links[f'link_{service}'] = service_link

        # Spotify - usar búsqueda directa con spotipy
        if 'link_spotify' not in self.links or '<!--' in self.links.get('link_spotify', ''):
            spotify_url = self._search_spotify_album(artist, album)
            if spotify_url:
                self.links['url_spotify'] = spotify_url
                self.links['link_spotify'] = f'[![spotify](../links/svg/spotify.png (spotify))]({spotify_url})'

        # Discogs requiere procesamiento especial
        self._search_discogs(artist, album)

    def _search_spotify_album(self, artist: str, album: str) -> str:
        """Buscar álbum en Spotify usando API directa"""
        if not SPOTIFY_AVAILABLE:
            self.logger.warning("spotipy no disponible para búsqueda de álbum")
            return ""

        try:
            # Configurar OAuth solo para búsqueda (scope mínimo)
            client_id = os.getenv('SPOTIFY_CLIENT')
            client_secret = os.getenv('SPOTIFY_SECRET')

            if not client_id or not client_secret:
                self.logger.warning("Credenciales de Spotify no configuradas")
                return ""

            # Para búsquedas no necesitamos autorización del usuario, usar Client Credentials
            client_credentials_manager = SpotifyClientCredentials(
                client_id=client_id,
                client_secret=client_secret
            )

            sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

            # Buscar álbum
            query = f"artist:{artist} album:{album}"
            results = sp.search(q=query, type='album', limit=1)

            if results['albums']['items']:
                album_url = results['albums']['items'][0]['external_urls']['spotify']
                self.logger.info(f"Álbum encontrado en Spotify: {album_url}")
                return album_url
            else:
                self.logger.debug(f"No se encontró álbum en Spotify: {artist} - {album}")
                return ""

        except Exception as e:
            self.logger.warning(f"Error buscando álbum en Spotify: {e}")
            return ""

    def _run_search_script(self, script: str, artist: str, album: str) -> str:
        """Ejecutar script de búsqueda"""
        try:
            script_path = self.modules_dir / script

            # Scripts especiales que manejamos directamente en Python
            if script == 'lastfm.sh':
                return self._search_lastfm(artist, album)

            if script.endswith('.py'):
                cmd = ['python3', str(script_path), artist, album]
            else:
                # Para scripts bash, asegurar que son ejecutables
                if not os.access(script_path, os.X_OK):
                    os.chmod(script_path, 0o755)
                cmd = ['bash', str(script_path), artist, album]

            result = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=30, check=True)
            return result.stdout.strip()

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            self.logger.warning(f"Error en script {script}: {e}")
            return ""

    def _search_lastfm(self, artist: str, album: str) -> str:
        """Búsqueda en Last.fm implementada directamente en Python"""
        try:
            api_key = os.getenv('LASTFM_API_KEY')
            if not api_key:
                self.logger.warning("LASTFM_API_KEY no configurada")
                return ""

            url = "http://ws.audioscrobbler.com/2.0/"
            params = {
                'method': 'album.getinfo',
                'album': album,
                'artist': artist,
                'api_key': api_key,
                'format': 'json'
            }

            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'album' in data and 'url' in data['album']:
                    return data['album']['url']

            return ""

        except Exception as e:
            self.logger.warning(f"Error buscando en Last.fm: {e}")
            return ""

    def _search_discogs(self, artist: str, album: str):
        """Búsqueda específica en Discogs"""
        try:
            # Limpiar archivo de releases
            releases_file = self.config['blog_dir'] / 'releases.txt'
            releases_file.touch()

            result = subprocess.run(['python3', str(self.modules_dir / 'discogs.py'),
                                   artist, album], capture_output=True, text=True, check=True)
            master_id = result.stdout.strip()

            if master_id == 'bash_script':
                # Obtener release ID
                release_result = subprocess.run(['python3', str(self.modules_dir / 'release_id.py'),
                                               album], capture_output=True, text=True, check=True)
                release_id = release_result.stdout.strip()
                if release_id:
                    self.current_metadata['release_id'] = release_id
            else:
                if 'Error' in master_id:
                    master_id = master_id.replace('Error', '').strip()
                if master_id:
                    url = f"https://www.discogs.com/master/{master_id}"
                    self.links['url_discogs'] = url
                    self.links['link_discogs'] = f'[![discogs](../links/svg/discogs.png (discogs))]({url})'
                    self.current_metadata['master_id'] = master_id

        except subprocess.CalledProcessError as e:
            self.logger.warning(f"Error buscando en Discogs: {e}")

    def add_content_to_post(self):
        """Añadir contenido al post"""
        self.logger.info("Añadiendo contenido al post...")

        if not self.post_file or not self.post_file.exists():
            self.logger.error("Archivo de post no existe")
            return False

        try:
            # Añadir portada
            content = [
                f"![cover](image.jpeg ({self.current_metadata['artist']} - {self.current_metadata['album']}))",
                " "
            ]

            # Añadir enlaces principales
            main_services = ['spotify', 'bandcamp', 'youtube', 'lastfm',
                           'discogs', 'musicbrainz', 'wikipedia', 'rateyourmusic']

            for service in main_services:
                link = self.links.get(f'link_{service}', '')
                if link and not link.startswith('<!--'):
                    content.append(link)

            content.append("")

            # Añadir información de la base de datos si existe
            if self.database_data:
                self._add_database_info_to_content(content)

                # NUEVA FUNCIONALIDAD: Añadir tabla de información de producción
                self._add_production_table_to_content(content)

                # NUEVA FUNCIONALIDAD: Añadir tracklist con enlaces
                self._add_tracklist_with_links_to_content(content)

                # NUEVA FUNCIONALIDAD: Añadir tabla de instrumentos/equipboard
                self._add_equipment_table_to_content(content)

                # NUEVA FUNCIONALIDAD: Añadir información adicional (estudios, equipo, etc.)
                self._add_extended_info_to_content(content)

                # NUEVA FUNCIONALIDAD: Añadir tablas de reviews, menciones y puntuaciones
                self._add_reviews_and_mentions_tables(content)

            # Escribir contenido al archivo
            with open(self.post_file, 'a', encoding='utf-8') as f:
                f.write('\n'.join(content))

            return True

        except Exception as e:
            self.logger.error(f"Error añadiendo contenido: {e}")
            return False


    def _add_production_table_to_content(self, content: List[str]):
        """Añadir tabla de información de producción al contenido"""
        self.logger.info("Obteniendo información de producción desde base de datos...")

        try:
            conn = sqlite3.connect(self.config['database_path'])
            cursor = conn.cursor()

            # Obtener información de producción desde albums y discogs_discography
            production_query = """
            SELECT
                COALESCE(al.producers, '') as producers,
                COALESCE(al.engineers, '') as engineers,
                COALESCE(al.mastering_engineers, '') as mastering,
                COALESCE(al.label, '') as label,
                COALESCE(al.year, '') as year,
                COALESCE(al.genre, '') as genre,
                COALESCE(al.credits, '') as credits,
                al.total_tracks
            FROM albums al
            WHERE al.id = ?
            """

            cursor.execute(production_query, (self.database_data['album_id'],))
            production_result = cursor.fetchone()

            # Obtener información adicional de discogs_discography si existe
            discogs_extra_query = """
            SELECT
                COALESCE(dd.extraartists, '') as extraartists,
                COALESCE(dd.format, '') as format,
                COALESCE(dd.status, '') as status,
                COALESCE(dd.notes, '') as dd_notes
            FROM discogs_discography dd
            WHERE dd.artist_id = ? AND dd.album_name LIKE ?
            LIMIT 1
            """

            cursor.execute(discogs_extra_query, (
                self.database_data['artist_id'],
                f"%{self.database_data['db_album']}%"
            ))
            discogs_result = cursor.fetchone()

            # Obtener información adicional de mb_release_group si existe
            mb_extra_query = """
            SELECT
                COALESCE(producer, '') as mb_producer,
                COALESCE(productor, '') as mb_productor,
                COALESCE(colaborador, '') as mb_colaborador
            FROM mb_release_group
            WHERE artist_id = ? AND title LIKE ?
            LIMIT 1
            """

            cursor.execute(mb_extra_query, (
                self.database_data['artist_id'],
                f"%{self.database_data['db_album']}%"
            ))
            mb_result = cursor.fetchone()

            conn.close()

            if not production_result:
                return

            # Crear tabla de información
            content.extend(["", "## Información de Producción", ""])

            # Tabla principal con información básica
            table_rows = []

            producers, engineers, mastering, label, year, genre, credits, total_tracks = production_result

            if label:
                table_rows.append(f"| **Sello** | {label} |")
            if year:
                table_rows.append(f"| **Año** | {year} |")
            if genre:
                table_rows.append(f"| **Género** | {genre} |")
            if total_tracks and total_tracks > 0:
                table_rows.append(f"| **Total de pistas** | {total_tracks} |")

            # Combinar productores de diferentes fuentes
            all_producers = []
            if producers:
                all_producers.append(producers)

            # Añadir productores de MusicBrainz si existen
            if mb_result:
                mb_producer, mb_productor, mb_colaborador = mb_result
                if mb_producer:
                    all_producers.append(mb_producer)
                if mb_productor:
                    all_producers.append(mb_productor)

            if all_producers:
                producers_text = ", ".join(set(all_producers))  # Eliminar duplicados
                table_rows.append(f"| **Productores** | {producers_text} |")

            if engineers:
                table_rows.append(f"| **Ingeniería** | {engineers} |")
            if mastering:
                table_rows.append(f"| **Masterización** | {mastering} |")

            # Añadir información de Discogs si existe
            if discogs_result:
                extraartists, format_info, status, dd_notes = discogs_result

                if format_info:
                    table_rows.append(f"| **Formato** | {format_info} |")
                if status:
                    table_rows.append(f"| **Estado** | {status} |")
                if extraartists:
                    # Procesar JSON de extraartists si es necesario
                    extraartists_rows = self._process_credits_json_to_rows(extraartists)
                    table_rows.extend(extraartists_rows)
                if dd_notes:
                    table_rows.append(f"| **Notas (Discogs)** | {dd_notes} |")

            # Añadir colaboradores de MusicBrainz
            if mb_result and mb_colaborador:
                table_rows.append(f"| **Colaborador** | {mb_colaborador} |")

            # Procesar créditos adicionales (JSON) - CADA ROL EN UNA FILA SEPARADA
            if credits:
                credits_rows = self._process_credits_json_to_rows(credits)
                table_rows.extend(credits_rows)

            if table_rows:
                content.extend([
                    "| Campo | Información |",
                    "|-------|-------------|"
                ])
                content.extend(table_rows)
                content.append("")

        except sqlite3.Error as e:
            self.logger.warning(f"Error obteniendo información de producción: {e}")
        except Exception as e:
            self.logger.warning(f"Error creando tabla de producción: {e}")

    def _process_credits_json_to_rows(self, field_value: str) -> List[str]:
        """Procesar campo JSON de créditos y convertir a filas separadas de tabla"""
        rows = []

        if not field_value or field_value.strip() == '':
            return rows

        try:
            # Intentar parsear como JSON
            data = json.loads(field_value)

            if isinstance(data, dict):
                # Es un diccionario - crear una fila por cada rol
                for role, people in data.items():
                    if isinstance(people, list):
                        people_str = ", ".join(people)
                    else:
                        people_str = str(people)

                    # Limpiar y formatear el rol
                    clean_role = role.replace('_', ' ').replace('[', '').replace(']', '').title()

                    # Crear fila de tabla
                    rows.append(f"| **{clean_role}** | {people_str} |")

            elif isinstance(data, list):
                # Es una lista - crear una sola fila
                people_str = ", ".join(str(item) for item in data)
                rows.append(f"| **Artistas Adicionales** | {people_str} |")

            else:
                # Es otro tipo de dato JSON
                rows.append(f"| **Información Adicional** | {str(data)} |")

        except json.JSONDecodeError:
            # No es JSON válido, crear una fila con el texto plano
            rows.append(f"| **Información Adicional** | {field_value} |")

        return rows


    def _process_json_field(self, field_value: str, field_name: str) -> str:
        """Procesar campo que puede contener JSON y formatear para markdown"""
        if not field_value or field_value.strip() == '':
            return ""

        try:
            # Intentar parsear como JSON
            data = json.loads(field_value)

            if isinstance(data, dict):
                # Es un diccionario - formatear como lista de roles y personas
                formatted_parts = []
                for role, people in data.items():
                    if isinstance(people, list):
                        people_str = ", ".join(people)
                    else:
                        people_str = str(people)

                    # Limpiar y formatear el rol
                    clean_role = role.replace('_', ' ').replace('[', '').replace(']', '').title()
                    formatted_parts.append(f"**{clean_role}**: {people_str}")

                return " • ".join(formatted_parts)

            elif isinstance(data, list):
                # Es una lista - unir con comas
                return ", ".join(str(item) for item in data)

            else:
                # Es otro tipo de dato JSON
                return str(data)

        except json.JSONDecodeError:
            # No es JSON válido, devolver como texto plano
            return field_value


    def _add_reviews_and_mentions_tables(self, content: List[str]):
        """Añadir tablas de reviews, menciones y puntuaciones"""
        self.logger.info("Obteniendo reviews, menciones y puntuaciones desde base de datos...")

        try:
            conn = sqlite3.connect(self.config['database_path'])
            cursor = conn.cursor()

            # 1. Tabla de Menciones
            menciones_query = """
            SELECT
                m.artist_name,
                f.feed_name,
                f.post_title,
                f.post_url,
                f.post_date
            FROM menciones m
            JOIN feeds f ON m.feed_id = f.id
            WHERE m.artist_id = ?
            ORDER BY f.post_date DESC
            LIMIT 10
            """

            cursor.execute(menciones_query, (self.database_data['artist_id'],))
            menciones_result = cursor.fetchall()

            # 2. Tabla de Feeds relacionados con el álbum
            feeds_query = """
            SELECT
                f.feed_name,
                f.post_title,
                f.post_url,
                f.post_date,
                f.origen
            FROM feeds f
            WHERE (f.entity_type = 'album' AND f.entity_id = ?)
               OR (f.entity_type = 'artist' AND f.entity_id = ? AND
                   (LOWER(f.post_title) LIKE LOWER(?) OR LOWER(f.content) LIKE LOWER(?)))
            ORDER BY f.post_date DESC
            LIMIT 10
            """

            album_search_term = f"%{self.database_data['db_album']}%"
            cursor.execute(feeds_query, (
                self.database_data['album_id'],
                self.database_data['artist_id'],
                album_search_term,
                album_search_term
            ))
            feeds_result = cursor.fetchall()

            # 3. Puntuaciones Album of the Year
            aoty_query = """
            SELECT
                aoty.user_score,
                aoty.critic_score,
                aoty.num_user_ratings,
                aoty.num_critic_ratings,
                aoty.aoty_url,
                aoty.last_updated
            FROM album_aoty aoty
            WHERE aoty.album_id = ?
            """

            cursor.execute(aoty_query, (self.database_data['album_id'],))
            aoty_result = cursor.fetchone()

            # 4. Puntuaciones Metacritic
            metacritic_query = """
            SELECT
                mc.metascore,
                mc.num_critics,
                mc.positive_reviews,
                mc.mixed_reviews,
                mc.negative_reviews,
                mc.metacritic_url,
                mc.last_updated
            FROM album_metacritic mc
            WHERE mc.album_id = ?
            """

            cursor.execute(metacritic_query, (self.database_data['album_id'],))
            metacritic_result = cursor.fetchone()

            conn.close()

            # DEBUG: Log para verificar que se ejecutan las consultas
            self.logger.debug(f"Menciones encontradas: {len(menciones_result) if menciones_result else 0}")
            self.logger.debug(f"Feeds encontrados: {len(feeds_result) if feeds_result else 0}")
            self.logger.debug(f"AOTY result: {aoty_result is not None}")
            self.logger.debug(f"Metacritic result: {metacritic_result is not None}")

            # Renderizar tablas si hay datos
            tables_added = False

            # Tabla de Menciones
            if menciones_result:
                if not tables_added:
                    content.extend(["", "## Reviews y Menciones", ""])
                    tables_added = True

                content.extend(["", "### 📰 Menciones en Medios", ""])
                content.extend([
                    "| Medio | Título | Fecha |",
                    "|-------|--------|-------|"
                ])

                for artist_name, feed_name, post_title, post_url, post_date in menciones_result:
                    # Formatear fecha
                    formatted_date = self._format_date(post_date)

                    # Crear enlace si hay URL
                    if post_url:
                        title_link = f"[{post_title}]({post_url})"
                    else:
                        title_link = post_title

                    content.append(f"| **{feed_name}** | {title_link} | {formatted_date} |")

                content.append("")
                self.logger.info(f"Tabla de menciones añadida: {len(menciones_result)} menciones")

            # Tabla de Feeds/Reviews
            if feeds_result:
                if not tables_added:
                    content.extend(["", "## Reviews y Menciones", ""])
                    tables_added = True

                content.extend(["", "### 📝 Reviews y Artículos", ""])
                content.extend([
                    "| Fuente | Título | Fecha | Origen |",
                    "|--------|--------|-------|--------|"
                ])

                for feed_name, post_title, post_url, post_date, origen in feeds_result:
                    # Formatear fecha
                    formatted_date = self._format_date(post_date)

                    # Crear enlace si hay URL
                    if post_url:
                        title_link = f"[{post_title}]({post_url})"
                    else:
                        title_link = post_title

                    origen_display = origen if origen else "-"

                    content.append(f"| **{feed_name}** | {title_link} | {formatted_date} | {origen_display} |")

                content.append("")
                self.logger.info(f"Tabla de feeds añadida: {len(feeds_result)} artículos")

            # Tabla de Puntuaciones
            if aoty_result or metacritic_result:
                if not tables_added:
                    content.extend(["", "## Reviews y Menciones", ""])
                    tables_added = True

                content.extend(["", "### ⭐ Puntuaciones y Críticas", ""])
                content.extend([
                    "| Plataforma | Puntuación Críticos | Puntuación Usuarios | Enlaces |",
                    "|------------|-------------------|-------------------|---------|"
                ])

                # Album of the Year
                if aoty_result:
                    user_score, critic_score, num_user_ratings, num_critic_ratings, aoty_url, last_updated = aoty_result

                    critic_text = f"{critic_score}/100" if critic_score else "-"
                    if num_critic_ratings:
                        critic_text += f" ({num_critic_ratings} reviews)"

                    user_text = f"{user_score}/100" if user_score else "-"
                    if num_user_ratings:
                        user_text += f" ({num_user_ratings} ratings)"

                    aoty_link = f"[🔗 AOTY]({aoty_url})" if aoty_url else "-"

                    content.append(f"| **Album of the Year** | {critic_text} | {user_text} | {aoty_link} |")
                    self.logger.info("Puntuaciones AOTY añadidas")

                # Metacritic
                if metacritic_result:
                    metascore, num_critics, positive_reviews, mixed_reviews, negative_reviews, metacritic_url, last_updated = metacritic_result

                    critic_text = f"{metascore}/100" if metascore else "-"
                    if num_critics:
                        critic_text += f" ({num_critics} reviews)"
                        if positive_reviews or mixed_reviews or negative_reviews:
                            breakdown = f" • ✅{positive_reviews or 0} ⚠️{mixed_reviews or 0} ❌{negative_reviews or 0}"
                            critic_text += breakdown

                    metacritic_link = f"[🔗 Metacritic]({metacritic_url})" if metacritic_url else "-"

                    content.append(f"| **Metacritic** | {critic_text} | - | {metacritic_link} |")
                    self.logger.info("Puntuaciones Metacritic añadidas")

                content.append("")

            if not tables_added:
                self.logger.info("No se encontraron reviews, menciones o puntuaciones para añadir")
            else:
                self.logger.info("Tablas de reviews y menciones añadidas exitosamente")

        except sqlite3.Error as e:
            self.logger.warning(f"Error obteniendo reviews y menciones: {e}")
        except Exception as e:
            self.logger.warning(f"Error creando tablas de reviews: {e}")



    def _format_date(self, date_value) -> str:
        """Formatear fecha para mostrar en tablas"""
        if not date_value:
            return "-"

        try:
            # Intentar parsear diferentes formatos de fecha
            if isinstance(date_value, str):
                # Formato ISO (YYYY-MM-DD HH:MM:SS)
                if 'T' in date_value or ' ' in date_value:
                    if 'T' in date_value:
                        date_part = date_value.split('T')[0]
                    else:
                        date_part = date_value.split(' ')[0]

                    # Convertir YYYY-MM-DD a DD/MM/YYYY
                    if '-' in date_part and len(date_part) == 10:
                        year, month, day = date_part.split('-')
                        return f"{day}/{month}/{year}"

                # Si ya está en formato DD/MM/YYYY o similar
                return date_value

            return str(date_value)

        except Exception:
            return str(date_value) if date_value else "-"


    def _add_tracklist_with_links_to_content(self, content: List[str]):
        """Añadir tracklist con enlaces al contenido"""
        self.logger.info("Obteniendo tracklist con enlaces desde base de datos...")

        try:
            conn = sqlite3.connect(self.config['database_path'])
            cursor = conn.cursor()

            # Obtener tracklist con enlaces (usando las columnas reales)
            tracklist_query = """
            SELECT
                s.track_number,
                s.title,
                s.duration,
                COALESCE(sl.spotify_url, '') as spotify_url,
                COALESCE(sl.youtube_url, '') as youtube_url,
                COALESCE(sl.bandcamp_url, '') as bandcamp_url,
                s.has_lyrics,
                COALESCE(l.lyrics, '') as lyrics_text
            FROM songs s
            LEFT JOIN song_links sl ON s.id = sl.song_id
            LEFT JOIN lyrics l ON s.id = l.track_id
            WHERE s.artist = ? AND s.album = ?
            ORDER BY s.track_number
            """

            cursor.execute(tracklist_query, (self.database_data['db_artist'], self.database_data['db_album']))
            tracks_result = cursor.fetchall()

            conn.close()

            if not tracks_result:
                self.logger.debug("No se encontró tracklist en la base de datos")
                return

            content.extend(["", "## Tracklist", ""])

            for track_num, title, duration, spotify_url, youtube_url, bandcamp_url, has_lyrics, lyrics_text in tracks_result:
                # Formatear línea principal de la canción
                track_line = f"**{track_num}.** {title}"

                # Añadir duración si está disponible
                if duration:
                    formatted_duration = self._format_duration(duration)
                    if formatted_duration:
                        track_line += f" *[{formatted_duration}]*"

                # Añadir mini-enlaces
                links = []
                if spotify_url:
                    links.append(f"[🎵 Spotify]({spotify_url})")
                if youtube_url:
                    links.append(f"[📺 YouTube]({youtube_url})")
                if bandcamp_url:
                    links.append(f"[🏷️ Bandcamp]({bandcamp_url})")

                # Añadir icono de letras
                if lyrics_text:
                    links.append("📔 Letras")
                elif has_lyrics:
                    links.append("📔 Letras")

                if links:
                    track_line += " | " + " • ".join(links)

                content.append(track_line)
                content.append("")  # Línea vacía entre canciones

            self.logger.info(f"Tracklist añadido: {len(tracks_result)} canciones")

        except sqlite3.Error as e:
            self.logger.warning(f"Error obteniendo tracklist: {e}")
        except Exception as e:
            self.logger.warning(f"Error creando tracklist: {e}")

    def _add_equipment_table_to_content(self, content: List[str]):
        """Añadir tabla de instrumentos y equipos utilizados"""
        self.logger.info("Obteniendo información de equipos desde base de datos...")

        try:
            conn = sqlite3.connect(self.config['database_path'])
            cursor = conn.cursor()

            # Obtener equipos desde las tablas equipboard reales
            equipment_query = """
            SELECT
                ei.equipment_type,
                ei.brand,
                ei.model,
                ei.equipment_url,
                ed.min_price,
                ed.average_price,
                ed.max_price,
                ed.review_score,
                ed.total_reviews,
                ed.year_made,
                ed.detailed_description
            FROM equipboard_instruments ei
            LEFT JOIN equipboard_details ed ON ei.equipment_id = ed.equipment_id
            WHERE ei.artist_id = ?
            ORDER BY
                CASE ei.equipment_type
                    WHEN 'Guitar' THEN 1
                    WHEN 'Bass' THEN 2
                    WHEN 'Drums' THEN 3
                    WHEN 'Keyboard' THEN 4
                    WHEN 'Synthesizer' THEN 5
                    WHEN 'Amplifier' THEN 6
                    WHEN 'Effects' THEN 7
                    ELSE 8
                END,
                ei.brand, ei.model
            """

            cursor.execute(equipment_query, (self.database_data['artist_id'],))
            equipment_result = cursor.fetchall()

            conn.close()

            if not equipment_result:
                self.logger.debug("No se encontró información de equipos")
                return

            content.extend(["", "## Instrumentos y Equipos", ""])
            content.extend([
                "| Tipo | Marca | Modelo | Año | Precio | Puntuación | Enlaces |",
                "|------|-------|--------|-----|--------|------------|---------|"
            ])

            for (eq_type, brand, model, equipment_url, min_price, avg_price,
                 max_price, review_score, total_reviews, year_made, description) in equipment_result:

                # Construir fila de la tabla
                row_brand = brand or "-"
                row_model = model or "-"
                row_year = str(year_made) if year_made else "-"

                # Construir columna de precio
                price_text = "-"
                if avg_price:
                    price_text = f"${avg_price:,.0f}"
                elif min_price and max_price:
                    price_text = f"${min_price:,.0f}-${max_price:,.0f}"
                elif min_price:
                    price_text = f"${min_price:,.0f}+"

                # Construir columna de puntuación
                score_text = "-"
                if review_score and total_reviews:
                    score_text = f"{review_score:.1f}/5 ({total_reviews} reviews)"
                elif review_score:
                    score_text = f"{review_score:.1f}/5"

                # Construir columna de enlaces
                links_text = "-"
                if equipment_url:
                    links_text = f"[🎛️ Equipboard]({equipment_url})"

                # Formatear fila completa
                table_row = f"| **{eq_type}** | {row_brand} | {row_model} | {row_year} | {price_text} | {score_text} | {links_text} |"
                content.append(table_row)

            content.append("")
            self.logger.info(f"Tabla de equipos añadida: {len(equipment_result)} elementos")

        except sqlite3.Error as e:
            self.logger.warning(f"Error obteniendo información de equipos: {e}")
        except Exception as e:
            self.logger.warning(f"Error creando tabla de equipos: {e}")

    def _format_duration(self, duration) -> str:
        """Formatear duración a formato mm:ss"""
        try:
            if isinstance(duration, str):
                # Si ya está en formato mm:ss
                if ':' in duration:
                    return duration
                # Si es un número como string
                duration = float(duration)

            if isinstance(duration, (int, float)) and duration > 0:
                minutes = int(duration // 60)
                seconds = int(duration % 60)
                return f"{minutes}:{seconds:02d}"

            return ""
        except (ValueError, TypeError):
            return ""

    def _add_extended_info_to_content(self, content: List[str]):
        """Añadir información extendida como estudios de grabación, equipos, etc."""
        self.logger.info("Obteniendo información extendida desde base de datos...")

        try:
            conn = sqlite3.connect(self.config['database_path'])
            cursor = conn.cursor()

            # Obtener información de Discogs adicional si existe
            discogs_query = """
            SELECT DISTINCT
                COALESCE(grabado_en, '') as recorded_at,
                COALESCE(fecha_de_grabación, '') as recording_date,
                COALESCE(caracterizado_por, '') as characterized_by,
                COALESCE(notes, '') as notes,
                COALESCE(extraartists, '') as extraartists
            FROM discogs_discography
            WHERE artist_id = ? AND album_name LIKE ?
            LIMIT 1
            """

            cursor.execute(discogs_query, (
                self.database_data['artist_id'],
                f"%{self.database_data['db_album']}%"
            ))
            discogs_info = cursor.fetchone()

            # Obtener información de MusicBrainz si existe
            mb_query = """
            SELECT DISTINCT
                COALESCE(caracterizado_por, '') as characterized_by,
                COALESCE(grabado_en, '') as recorded_at,
                COALESCE(fecha_de_grabación, '') as recording_date,
                COALESCE(producer, '') as producer,
                COALESCE(productor, '') as productor,
                COALESCE(colaborador, '') as colaborador
            FROM mb_release_group
            WHERE artist_id = ? AND title LIKE ?
            LIMIT 1
            """

            cursor.execute(mb_query, (
                self.database_data['artist_id'],
                f"%{self.database_data['db_album']}%"
            ))
            mb_info = cursor.fetchone()

            conn.close()

            # Procesar información extendida
            if discogs_info or mb_info:
                content.extend(["", "## Información Adicional", ""])

                # Combinar información de Discogs y MusicBrainz
                info_table = []

                if discogs_info:
                    recorded_at, recording_date, characterized_by, notes, extraartists = discogs_info

                    if recorded_at:
                        info_table.append(f"| **Grabado en** | {recorded_at} |")
                    if recording_date:
                        info_table.append(f"| **Fecha de grabación** | {recording_date} |")
                    if characterized_by:
                        info_table.append(f"| **Caracterizado por** | {characterized_by} |")
                    if extraartists:
                        info_table.append(f"| **Artistas adicionales** | {extraartists} |")
                    if notes:
                        info_table.append(f"| **Notas** | {notes} |")

                if mb_info:
                    (mb_characterized_by, mb_recorded_at, mb_recording_date,
                     mb_producer, mb_productor, mb_colaborador) = mb_info

                    # Solo añadir si no está ya desde Discogs
                    if mb_producer and not any('Productor' in row for row in info_table):
                        info_table.append(f"| **Productor (MB)** | {mb_producer} |")
                    if mb_colaborador and not any('Colaborador' in row for row in info_table):
                        info_table.append(f"| **Colaborador (MB)** | {mb_colaborador} |")

                if info_table:
                    content.extend([
                        "| Campo | Información |",
                        "|-------|-------------|"
                    ])
                    content.extend(info_table)
                    content.append("")

        except sqlite3.Error as e:
            self.logger.debug(f"Error obteniendo información extendida: {e}")
        except Exception as e:
            self.logger.debug(f"Error procesando información extendida: {e}")

    def show_content_summary(self):
        """Mostrar resumen del contenido añadido"""
        if not self.database_data:
            return

        self.logger.info("📋 Resumen del contenido añadido:")

        # Contar secciones añadidas
        sections_added = []

        if self.database_data.get('genre') or self.database_data.get('release_year'):
            sections_added.append("Información básica")

        # Verificar si hay info de producción
        try:
            conn = sqlite3.connect(self.config['database_path'])
            cursor = conn.cursor()

            # Contar tracklist
            cursor.execute("SELECT COUNT(*) FROM songs WHERE artist = ? AND album = ?",
                         (self.database_data['db_artist'], self.database_data['db_album']))
            track_count = cursor.fetchone()[0]

            if track_count > 0:
                sections_added.append(f"Tracklist ({track_count} canciones)")

            # Contar colaboradores desde discogs_discography
            cursor.execute("""
                SELECT COUNT(*) FROM discogs_discography dd
                WHERE dd.artist_id = ? AND dd.album_name LIKE ?
                AND (dd.extraartists IS NOT NULL OR dd.colaborador IS NOT NULL)
            """, (self.database_data['artist_id'], f"%{self.database_data['db_album']}%"))
            collab_count = cursor.fetchone()[0]

            if collab_count > 0:
                sections_added.append(f"Colaboradores ({collab_count} registros)")

            # Contar equipos
            cursor.execute("""
                SELECT COUNT(*) FROM equipboard_instruments
                WHERE artist_id = ?
            """, (self.database_data['artist_id'],))
            equipment_count = cursor.fetchone()[0]

            if equipment_count > 0:
                sections_added.append(f"Equipos e instrumentos ({equipment_count} elementos)")

            # Contar canciones con letras
            cursor.execute("""
                SELECT COUNT(*) FROM songs s
                LEFT JOIN lyrics l ON s.id = l.track_id
                WHERE s.artist = ? AND s.album = ?
                AND (s.has_lyrics = 1 OR l.lyrics IS NOT NULL)
            """, (self.database_data['db_artist'], self.database_data['db_album']))
            lyrics_count = cursor.fetchone()[0]

            if lyrics_count > 0:
                sections_added.append(f"Canciones con letras ({lyrics_count})")

            conn.close()

        except sqlite3.Error:
            pass

        for section in sections_added:
            self.logger.info(f"  ✅ {section}")

        if not sections_added:
            self.logger.info("  ℹ️  Solo información básica añadida")

    def _add_database_info_to_content(self, content: List[str]):
        """Añadir información de la base de datos al contenido"""

        # Información básica
        if self.database_data.get('genre'):
            content.extend(["", f"**Género:** {self.database_data['genre']}", ""])

        if self.database_data.get('record_label'):
            content.extend([f"**Sello:** {self.database_data['record_label']}", ""])

        if self.database_data.get('release_year'):
            content.extend([f"**Año:** {self.database_data['release_year']}", ""])

        if self.database_data.get('total_tracks'):
            content.extend([f"**Total de pistas:** {self.database_data['total_tracks']}", ""])

    def download_cover_art(self) -> bool:
        """Descargar carátula del álbum"""
        self.logger.info("Descargando carátula...")

        try:
            post_folder = self.post_file.parent
            os.chdir(post_folder)

            # Si hay carátula en BD, usarla
            if self.database_data.get('cover_path'):
                cover_path = Path(self.database_data['cover_path'])
                if cover_path.exists():
                    shutil.copy2(cover_path, post_folder / 'image.jpeg')
                    self.logger.info(f"Carátula copiada desde BD: {cover_path}")
                    return True

            # Activar entorno Python
            self._activate_python_env()

            # Intentar Spotify primero
            result = subprocess.run([
                'python3', str(self.modules_dir / 'caratula-spotify.py'),
                self.current_metadata['artist'], self.current_metadata['album']
            ], capture_output=True, text=True, timeout=60)

            if 'Error' in result.stdout:
                self.logger.warning("Error con Spotify, intentando fuente alternativa...")
                # Usar script alternativo
                subprocess.run([
                    'python3', str(self.modules_dir / 'caratula-alternativa.py'),
                    self.current_metadata['artist'], self.current_metadata['album'],
                    str(post_folder)
                ], timeout=60)
            else:
                # Copiar desde resultado de Spotify
                spotify_cover = result.stdout.strip()
                if spotify_cover and Path(spotify_cover).exists():
                    shutil.copy2(spotify_cover, post_folder / 'image.jpeg')

            # Verificar que se descargó
            if (post_folder / 'image.jpeg').exists():
                self.logger.info("Carátula descargada exitosamente")
                return True
            else:
                self.logger.warning("No se pudo descargar la carátula")
                return False

        except subprocess.TimeoutExpired:
            self.logger.warning("Timeout descargando carátula")
            return False
        except Exception as e:
            self.logger.error(f"Error descargando carátula: {e}")
            return False

    def add_tags_to_post(self) -> bool:
        """Añadir tags al post"""
        self.logger.info("Añadiendo tags al post...")

        try:
            if not self.current_metadata.get('tags'):
                return True

            # Leer archivo actual
            with open(self.post_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Reemplazar placeholders de tags
            tag_patterns = ["#- tagA", "#- tagB", "#- tagC", "#- tagD", "#tagE"]

            for i, tag in enumerate(self.current_metadata['tags']):
                if i < len(tag_patterns):
                    content = content.replace(tag_patterns[i], f"- {tag}")

            # Escribir archivo actualizado
            with open(self.post_file, 'w', encoding='utf-8') as f:
                f.write(content)

            return True

        except Exception as e:
            self.logger.error(f"Error añadiendo tags: {e}")
            return False

    def format_post_content(self) -> bool:
        """Formatear contenido del post"""
        self.logger.info("Formateando contenido del post...")

        try:
            with open(self.post_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Cambiar draft a false
            content = content.replace('draft: true', 'draft: false')

            with open(self.post_file, 'w', encoding='utf-8') as f:
                f.write(content)

            return True

        except Exception as e:
            self.logger.error(f"Error formateando contenido: {e}")
            return False

    def build_and_publish(self) -> bool:
        """Construir y publicar sitio"""
        self.logger.info("Construyendo y publicando sitio...")

        try:
            os.chdir(self.config['blog_dir'])

            # Construir sitio
            subprocess.run(['hugo'], check=True)
            self.logger.info("Sitio construido con Hugo")

            # Subir a GitHub si está habilitado
            if self.config['enable_git_push']:
                self.logger.info("Subiendo cambios a GitHub...")

                # Configurar SSH agent
                ssh_key = os.getenv('SSH_KEY_GITHUB')
                if ssh_key:
                    subprocess.run(['ssh-agent', '-s'], check=True)
                    subprocess.run(['ssh-add', ssh_key], check=True)

                # Git operations
                subprocess.run(['git', 'add', '.'], check=True)
                commit_msg = f"{self.current_metadata['artist']} {self.current_metadata['album']}"
                subprocess.run(['git', 'commit', '-m', commit_msg], check=True)
                subprocess.run(['git', 'push'], check=True)

                self.logger.info("Cambios subidos a GitHub")
            else:
                self.logger.info("Publicación en GitHub deshabilitada")

            return True

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error en construcción/publicación: {e}")
            return False

    def add_to_spotify_playlist(self) -> bool:
        """Añadir canción a playlist de Spotify (opcional)"""
        if not self.config['enable_spotify']:
            self.logger.info("Integración con Spotify deshabilitada")
            return True

        self.logger.info("Intentando añadir a playlist de Spotify...")

        try:
            # Usar implementación directa en lugar de scripts externos
            return self._spotify_integration_direct()

        except Exception as e:
            self.logger.warning(f"Error inesperado en Spotify: {e}")
            return True

    def _spotify_integration_direct(self) -> bool:
        """Integración directa con Spotify API usando spotipy"""
        if not SPOTIFY_AVAILABLE:
            self.logger.warning("spotipy no está instalado. Ejecuta: pip install spotipy")
            self.logger.info("Saltando integración con Spotify...")
            return True

        try:
            # Configurar OAuth
            client_id = os.getenv('SPOTIFY_CLIENT')
            client_secret = os.getenv('SPOTIFY_SECRET')
            redirect_uri = os.getenv('SPOTIFY_REDIRECT', 'http://127.0.0.1:8090')

            if not client_id or not client_secret:
                self.logger.warning("Credenciales de Spotify no configuradas")
                return True

            scope = "playlist-read-private playlist-modify-public playlist-modify-private"
            cache_path = self.cache_dir / "spotify_token.txt"

            sp_oauth = SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                scope=scope,
                cache_path=str(cache_path),
                open_browser=False
            )

            # Obtener token (con manejo interactivo)
            token_info = self._get_spotify_token(sp_oauth)
            if not token_info:
                self.logger.info("No se pudo obtener token de Spotify, saltando integración")
                return True

            # Crear cliente de Spotify
            sp = spotipy.Spotify(auth=token_info['access_token'])

            # Buscar canción
            artist = self.current_metadata['artist']
            title = self.current_metadata.get('title_raw', self.current_metadata['album'])

            track_info = self._search_spotify_track(sp, artist, title)
            if not track_info:
                return True

            track_id, track_url = track_info

            # Obtener/crear playlist
            playlist_id = self._get_spotify_playlist(sp)
            if not playlist_id:
                return True

            # Verificar duplicados
            if self._check_spotify_duplicate(sp, playlist_id, track_id):
                self.logger.info("La canción ya está en la playlist")
                self._notify("VVMM + Spotify", "Canción ya estaba en la playlist")
                return True

            # Añadir a playlist
            sp.playlist_add_items(playlist_id, [track_id])

            self.logger.info("✅ Canción añadida a playlist de Spotify exitosamente")
            self._show_spotify_success_notification(playlist_id, track_url)
            return True

        except Exception as e:
            self.logger.warning(f"Error en integración directa con Spotify: {e}")
            return True

    def _get_spotify_token(self, sp_oauth) -> dict:
        """Obtener token de Spotify con manejo interactivo"""
        # Intentar obtener token desde caché
        token_info = sp_oauth.get_cached_token()
        if token_info:
            self.logger.info("Token de Spotify obtenido desde caché")
            return token_info

        # Si no hay token, solicitar autorización
        self.logger.info("Token de Spotify no encontrado, solicitando autorización...")

        try:
            auth_url = sp_oauth.get_authorize_url()

            # Guardar URL en archivo temporal para fácil acceso
            temp_file = self.cache_dir / "spotify_auth_url.txt"
            with open(temp_file, 'w') as f:
                f.write(auth_url)

            # Mensaje simplificado sin caracteres especiales
            message = f"Autorizacion requerida para Spotify\n\n1. Abre esta URL en tu navegador:\n{auth_url}\n\n2. Autoriza la aplicacion\n3. Copia el codigo de la URL de respuesta\n\nURL guardada en: {temp_file}"

            result = subprocess.run([
                'yad', '--text-info',
                '--title=Autorizacion Spotify',
                '--width=700', '--height=400',
                '--text=' + message,
                '--button=URL copiada, continuar:0',
                '--button=Abrir URL:3',
                '--button=Cancelar:1'
            ], capture_output=True, text=True, timeout=120)

            if result.returncode == 3:  # Abrir URL
                self._open_url(auth_url)
                # Mostrar diálogo otra vez después de abrir
                result = subprocess.run([
                    'yad', '--info',
                    '--title=Autorizacion Spotify',
                    '--text=URL abierta en navegador.\nDespues de autorizar, continua aqui.',
                    '--button=Continuar:0',
                    '--button=Cancelar:1',
                    '--timeout=60'
                ], capture_output=True, text=True, timeout=65)

            if result.returncode != 0:
                self.logger.info("Usuario canceló autorización de Spotify")
                return None

            # Solicitar código con diálogo simple
            code_result = subprocess.run([
                'yad', '--entry',
                '--title=Codigo de Spotify',
                '--text=Pega aqui el codigo de autorizacion de Spotify:',
                '--width=500',
                '--timeout=120'
            ], capture_output=True, text=True, timeout=150)

            if code_result.returncode != 0:
                self.logger.info("Usuario canceló ingreso de código")
                return None

            code = code_result.stdout.strip()
            if not code:
                self.logger.warning("No se proporcionó código de autorización")
                return None

            # Intercambiar código por token
            token_info = sp_oauth.get_access_token(code, as_dict=True, check_cache=False)

            self.logger.info("✅ Token de Spotify obtenido exitosamente")
            return token_info

        except subprocess.TimeoutExpired:
            self.logger.info("Timeout en autorización de Spotify")
            return None
        except Exception as e:
            self.logger.warning(f"Error obteniendo token de Spotify: {e}")
            return None

    def _search_spotify_track(self, sp, artist: str, title: str) -> Optional[Tuple[str, str]]:
        """Buscar canción en Spotify"""
        try:
            query = f"artist:{artist} track:{title}"
            results = sp.search(q=query, type='track', limit=1)

            if results['tracks']['items']:
                track = results['tracks']['items'][0]
                track_id = track['id']
                track_url = track['external_urls']['spotify']
                track_name = track['name']
                artist_name = track['artists'][0]['name']

                self.logger.info(f"Canción encontrada en Spotify: '{track_name}' - '{artist_name}'")

                # Confirmar que es la canción correcta
                confirmation = subprocess.run([
                    'yad', '--question',
                    '--title=Confirmar canción',
                    '--text=' + f"¿Es esta la canción correcta?\n\n🎵 {track_name}\n👤 {artist_name}\n🔗 {track_url}",
                    '--button=✅ Sí:0',
                    '--button=🔍 Buscar otra:1',
                    '--button=❌ Cancelar:2',
                    '--timeout=30'
                ], capture_output=True, timeout=35)

                if confirmation.returncode == 0:  # Sí
                    return track_id, track_url
                elif confirmation.returncode == 1:  # Buscar otra
                    return self._manual_spotify_search(sp, artist, title)
                else:  # Cancelar o timeout
                    return None
            else:
                self.logger.info("No se encontró la canción automáticamente")
                return self._manual_spotify_search(sp, artist, title)

        except Exception as e:
            self.logger.warning(f"Error buscando en Spotify: {e}")
            return None

    def _manual_spotify_search(self, sp, default_artist: str, default_title: str) -> Optional[Tuple[str, str]]:
        """Búsqueda manual de canción en Spotify"""
        try:
            # Solicitar términos de búsqueda manual
            manual_result = subprocess.run([
                'yad', '--entry',
                '--entry-text=' + f"{default_artist} - {default_title}",
                '--text=No se encontró automáticamente.\nPrueba con otros términos de búsqueda:',
                '--title=Búsqueda manual en Spotify',
                '--button=🔍 Buscar:0',
                '--button=❌ Cancelar:1',
                '--timeout=60'
            ], capture_output=True, text=True, timeout=65)

            if manual_result.returncode != 0:
                return None

            manual_search = manual_result.stdout.strip()
            if not manual_search:
                return None

            # Buscar con términos manuales
            if ' - ' in manual_search:
                manual_artist, manual_title = manual_search.split(' - ', 1)
                query = f"artist:{manual_artist.strip()} track:{manual_title.strip()}"
            else:
                query = manual_search

            results = sp.search(q=query, type='track', limit=5)

            if not results['tracks']['items']:
                self.logger.warning("No se encontraron resultados con búsqueda manual")
                return None

            # Mostrar múltiples opciones si hay varias
            if len(results['tracks']['items']) > 1:
                options = []
                for i, track in enumerate(results['tracks']['items'][:5]):
                    artist_name = track['artists'][0]['name']
                    track_name = track['name']
                    album_name = track['album']['name']
                    options.append(f"{i+1}. {track_name} - {artist_name} ({album_name})")

                menu_text = "Selecciona la canción correcta:\n\n" + "\n".join(options)

                choice_result = subprocess.run([
                    'yad', '--entry',
                    '--title=Múltiples resultados',
                    '--text=' + menu_text + "\n\nIngresa el número:",
                    '--timeout=30'
                ], capture_output=True, text=True, timeout=35)

                if choice_result.returncode != 0:
                    return None

                try:
                    choice_index = int(choice_result.stdout.strip()) - 1
                    if 0 <= choice_index < len(results['tracks']['items']):
                        track = results['tracks']['items'][choice_index]
                        return track['id'], track['external_urls']['spotify']
                except ValueError:
                    pass

            # Si solo hay una opción o falló la selección, usar la primera
            track = results['tracks']['items'][0]
            return track['id'], track['external_urls']['spotify']

        except Exception as e:
            self.logger.warning(f"Error en búsqueda manual: {e}")
            return None

    def _get_spotify_playlist(self, sp) -> Optional[str]:
        """Obtener ID de playlist de Spotify"""
        try:
            # Obtener todas las playlists del usuario
            playlists = []
            offset = 0
            while True:
                results = sp.current_user_playlists(offset=offset, limit=50)
                playlists.extend(results['items'])
                if len(results['items']) < 50:
                    break
                offset += 50

            if not playlists:
                self.logger.warning("No se encontraron playlists")
                return None

            # Crear lista de opciones para el menú
            playlist_options = []
            for i, pl in enumerate(playlists[:15]):  # Limitar a 15 para que quepa en pantalla
                name = pl['name']
                track_count = pl['tracks']['total']
                # Truncar nombres largos
                if len(name) > 30:
                    name = name[:27] + "..."
                playlist_options.append(f"{i+1}. {name} ({track_count} tracks)")

            playlist_options.append(f"{len(playlist_options)+1}. 🎵 CREAR NUEVA PLAYLIST")

            # Mostrar menú usando yad
            menu_text = "Selecciona una playlist:\n\n" + "\n".join(playlist_options)

            result = subprocess.run([
                'yad', '--entry',
                '--title=Seleccionar Playlist de Spotify',
                '--text=' + menu_text + "\n\nIngresa el número:",
                '--width=500',
                '--timeout=60'
            ], capture_output=True, text=True, timeout=65)

            if result.returncode != 0:
                self.logger.info("Usuario canceló selección de playlist")
                return None

            selection = result.stdout.strip()

            try:
                index = int(selection) - 1
                if 0 <= index < len(playlists):
                    selected_playlist = playlists[index]
                    self.logger.info(f"Playlist seleccionada: {selected_playlist['name']}")
                    return selected_playlist['id']
                elif index == len(playlists):  # Nueva playlist
                    return self._create_spotify_playlist(sp)
                else:
                    self.logger.warning(f"Selección inválida: {selection}")
                    return None
            except ValueError:
                self.logger.warning(f"Entrada no numérica: {selection}")
                return None

        except Exception as e:
            self.logger.warning(f"Error obteniendo playlist: {e}")
            return None

    def _create_spotify_playlist(self, sp) -> Optional[str]:
        """Crear nueva playlist de Spotify"""
        try:
            result = subprocess.run([
                'yad', '--entry',
                '--title=Nueva Playlist',
                '--text=Nombre de la nueva playlist:',
                '--timeout=30'
            ], capture_output=True, text=True, timeout=35)

            if result.returncode != 0:
                return None

            playlist_name = result.stdout.strip()
            if not playlist_name:
                return None

            user = sp.current_user()
            new_playlist = sp.user_playlist_create(
                user=user['id'],
                name=playlist_name,
                public=True
            )

            self.logger.info(f"Nueva playlist creada: {playlist_name}")
            return new_playlist['id']

        except Exception as e:
            self.logger.warning(f"Error creando playlist: {e}")
            return None

    def _check_spotify_duplicate(self, sp, playlist_id: str, track_id: str) -> bool:
        """Verificar si la canción ya está en la playlist"""
        try:
            tracks = sp.playlist_tracks(playlist_id)
            for item in tracks['items']:
                if item['track'] and item['track']['id'] == track_id:
                    return True
            return False
        except Exception as e:
            self.logger.warning(f"Error verificando duplicados: {e}")
            return False

    def _show_spotify_success_notification(self, playlist_id: str, song_url: str):
        """Mostrar notificación de éxito de Spotify"""
        try:
            cover_file = self.post_file.parent / 'image.jpeg' if self.post_file else None
            playlist_url = f"https://open.spotify.com/playlist/{playlist_id}"

            artist = self.current_metadata['artist']
            title = self.current_metadata.get('title_raw', 'cancion')

            # Limpiar caracteres problemáticos del texto
            clean_artist = artist.replace('&', 'and').replace('"', "'")
            clean_title = title.replace('&', 'and').replace('"', "'")

            # Crear archivo temporal con la URL para que sea fácil de copiar
            temp_file = self.cache_dir / "spotify_playlist_url.txt"
            with open(temp_file, 'w') as f:
                f.write(playlist_url)

            if cover_file and cover_file.exists():
                # Texto simple sin caracteres especiales
                dialog_text = f"Cancion anadida a Spotify\n\n{clean_artist} - {clean_title}\n\nURL: {playlist_url}\n\nURL guardada en: {temp_file}"

                result = subprocess.run([
                    'yad', '--picture',
                    '--size=fit',
                    '--width=500', '--height=400',
                    '--filename=' + str(cover_file),
                    '--timeout=10',
                    '--text=' + dialog_text,
                    '--title=VVMM - Spotify',
                    '--button=Abrir playlist:2',
                    '--button=OK:0'
                ], timeout=15, capture_output=True)

                if result.returncode == 2:
                    self._open_url(playlist_url)
            else:
                # Diálogo de texto simple
                dialog_text = f"Cancion anadida a Spotify\n\n{clean_artist} - {clean_title}\n\nURL de playlist:\n{playlist_url}\n\nURL guardada en:\n{temp_file}"

                result = subprocess.run([
                    'yad', '--info',
                    '--width=600', '--height=300',
                    '--timeout=15',
                    '--text=' + dialog_text,
                    '--title=VVMM - Spotify Success',
                    '--button=Abrir playlist:2',
                    '--button=Copiar URL:3',
                    '--button=OK:0'
                ], timeout=20, capture_output=True)

                if result.returncode == 2:
                    self._open_url(playlist_url)
                elif result.returncode == 3:
                    self._copy_to_clipboard(playlist_url)

            # También mostrar en consola para debug
            self.logger.info(f"Playlist URL: {playlist_url}")
            print(f"\n🎵 Spotify Playlist URL: {playlist_url}\n")

        except subprocess.TimeoutExpired:
            # Si timeout, mostrar al menos en consola
            print(f"\n🎵 Canción añadida a Spotify: {playlist_url}\n")
            self._notify("VVMM + Spotify", f"Cancion anadida - URL en logs")
        except Exception as e:
            self.logger.debug(f"Error en notificación Spotify: {e}")
            print(f"\n🎵 Spotify URL: {playlist_url}\n")
            self._notify("VVMM + Spotify", f"Cancion anadida a playlist")

    def _copy_to_clipboard(self, text: str):
        """Copiar texto al portapapeles"""
        try:
            # Intentar diferentes métodos para copiar al portapapeles
            if shutil.which('xclip'):
                subprocess.run(['xclip', '-selection', 'clipboard'],
                             input=text.encode(), check=True)
                self.logger.info("URL copiada al portapapeles con xclip")
            elif shutil.which('xsel'):
                subprocess.run(['xsel', '--clipboard', '--input'],
                             input=text.encode(), check=True)
                self.logger.info("URL copiada al portapapeles con xsel")
            else:
                self.logger.warning("No se encontró xclip ni xsel para copiar al portapapeles")
                self._notify("URL no copiada", "Instala xclip o xsel para copiar automáticamente")
        except Exception as e:
            self.logger.warning(f"Error copiando al portapapeles: {e}")

    def _open_url(self, url: str):
        """Abrir URL en el navegador"""
        try:
            # Intentar diferentes navegadores
            browsers = ['xdg-open', 'chromium', 'firefox', 'google-chrome']

            for browser in browsers:
                if shutil.which(browser):  # Verificar si el comando existe
                    subprocess.Popen([browser, url],
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
                    self.logger.info(f"Abriendo {url} con {browser}")
                    return

            # Si no encuentra navegador, al menos mostrar la URL
            self.logger.warning(f"No se encontró navegador. URL: {url}")
            self._notify("URL de playlist", url)

        except Exception as e:
            self.logger.warning(f"Error abriendo URL: {e}")
            self._notify("URL de playlist", url)

    def preview_site(self) -> bool:
        """Mostrar preview del sitio"""
        if not self.config['enable_preview']:
            self.logger.info("Preview del sitio deshabilitado")
            return True

        self.logger.info("Iniciando servidor de preview...")

        try:
            os.chdir(self.config['blog_dir'])

            # Iniciar servidor Hugo
            hugo_process = subprocess.Popen([
                'hugo', 'server', '--bind', '0.0.0.0',
                '--baseURL', 'http://localhost'
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Esperar un poco para que el servidor arranque
            import time
            time.sleep(3)

            # Abrir navegador
            post_slug = f"{self.current_metadata['artist_processed']}-_-{self.current_metadata['album_processed']}"
            url = f"http://localhost:1313/posts/{post_slug}"

            browser_process = subprocess.Popen([
                'qutebrowser', '--target', 'auto', url
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Esperar un tiempo y luego cerrar
            time.sleep(20)

            # Terminar procesos
            hugo_process.terminate()
            browser_process.terminate()

            self.logger.info("Preview completado")
            return True

        except Exception as e:
            self.logger.warning(f"Error en preview: {e}")
            return True  # No es crítico

    def _activate_python_env(self):
        """Activar entorno virtual de Python si existe"""
        venv_path = self.config.get('python_venv_path')
        if venv_path and Path(venv_path).exists():
            activate_script = Path(venv_path) / 'bin' / 'activate'
            if activate_script.exists():
                # En subprocess, necesitamos usar el python del venv directamente
                python_path = Path(venv_path) / 'bin' / 'python3'
                if python_path.exists():
                    # Actualizar PATH para usar el python del venv
                    venv_bin = str(Path(venv_path) / 'bin')
                    current_path = os.environ.get('PATH', '')
                    os.environ['PATH'] = f"{venv_bin}:{current_path}"
                    self.logger.debug(f"Entorno virtual activado: {venv_path}")

    def _notify(self, title: str, message: str, timeout: int = 5000):
        """Enviar notificación del sistema"""
        try:
            subprocess.run([
                'notify-send', '-t', str(timeout), title, message
            ], check=False)
        except Exception:
            pass  # Notificaciones no son críticas

    def cleanup(self):
        """Limpiar recursos y archivos temporales"""
        self.logger.info("Ejecutando limpieza...")

        try:
            # Limpiar archivos temporales
            temp_files = [
                self.cache_dir / 'tracklist_parts*',
                self.modules_dir / 'discogs_info_extra.txt'
            ]

            for pattern in temp_files:
                for file in self.cache_dir.glob('tracklist_parts*'):
                    file.unlink()

                if (self.modules_dir / 'discogs_info_extra.txt').exists():
                    (self.modules_dir / 'discogs_info_extra.txt').unlink()

            self.logger.info("Limpieza completada")

        except Exception as e:
            self.logger.warning(f"Error en limpieza: {e}")

    def run(self, args) -> int:
        """Ejecutar el flujo principal"""
        try:
            self.logger.info("=== Iniciando VVMM Post Creator (Python) ===")
            self.logger.info(f"Timestamp: {datetime.now()}")

            # 1. Obtener metadata de la canción actual
            if not self.get_current_song_metadata():
                self.logger.error("Error fatal: No se pudo obtener metadata")
                return 1

            # 2. Verificar base de datos primero
            use_database = self.check_database_first()

            if use_database:
                self.logger.info("✅ Usando información de base de datos")
                self.generate_links_from_database()
            else:
                self.logger.info("ℹ️ Usando flujo tradicional con búsquedas")
                self.search_missing_services()

            # 3. Solicitar tags al usuario
            if not self.get_user_tags():
                self.logger.error("Error fatal: No se pudieron obtener tags")
                return 1

            # 4. Crear post de Hugo
            if not self.create_hugo_post():
                self.logger.error("Error fatal: No se pudo crear post")
                return 1

            # 5. Añadir contenido al post
            if not self.add_content_to_post():
                self.logger.error("Error fatal: No se pudo añadir contenido")
                return 1

            # 5.1 Mostrar resumen del contenido añadido
            self.show_content_summary()

            # 6. Descargar carátula (no crítico)
            if not self.download_cover_art():
                self.logger.warning("Error descargando carátula, continuando...")
                self.success = False

            # 7. Añadir tags
            if not self.add_tags_to_post():
                self.logger.error("Error fatal: No se pudieron añadir tags")
                return 1

            # 8. Formatear contenido
            if not self.format_post_content():
                self.logger.error("Error fatal: No se pudo formatear contenido")
                return 1

            # 9. Añadir a playlist de Spotify (opcional)
            if not self.add_to_spotify_playlist():
                self.logger.warning("Integración con Spotify falló")
                self.success = False

            # 10. Preview del sitio (opcional)
            if not self.preview_site():
                self.logger.warning("Error en preview del sitio")
                self.success = False

            # 11. Construir y publicar
            if not self.build_and_publish():
                self.logger.error("Error en construcción/publicación")
                self.success = False

            # 12. Mostrar resumen final
            self._show_final_summary()

            return 0 if self.success else 1

        except KeyboardInterrupt:
            self.logger.info("Proceso interrumpido por el usuario")
            return 130
        except Exception as e:
            self.logger.error(f"Error inesperado: {e}")
            return 1
        finally:
            self.cleanup()

    def _show_final_summary(self):
        """Mostrar resumen final"""
        self.logger.info("=== RESUMEN FINAL ===")

        if self.success:
            self.logger.info("✅ Post creado EXITOSAMENTE")
            self._notify("🎉 VVMM Post Creator",
                        f"✅ Post creado exitosamente\n🎵 {self.current_metadata['artist']} - {self.current_metadata['album']}")
        else:
            self.logger.warning("⚠️ Post creado con ADVERTENCIAS")
            self._notify("⚠️ VVMM Post Creator",
                        f"Post creado con advertencias\n🎵 {self.current_metadata['artist']} - {self.current_metadata['album']}")

        # Información del post
        self.logger.info("📊 Información del post:")
        self.logger.info(f"  Artista: {self.current_metadata['artist']}")
        self.logger.info(f"  Álbum: {self.current_metadata['album']}")
        self.logger.info(f"  Tags: {self.current_metadata.get('tags', [])}")
        if self.post_file:
            self.logger.info(f"  Archivo: {self.post_file}")

        self.logger.info("🎵 ¡Gracias por usar VVMM Post Creator!")


def signal_handler(signum, frame):
    """Manejador de señales para limpieza"""
    print("\nProceso interrumpido. Limpiando...")
    sys.exit(130)


def main():
    """Función principal"""
    # Configurar manejadores de señales
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Configurar argumentos de línea de comandos
    parser = argparse.ArgumentParser(
        description="VVMM Post Creator - Creador automático de posts para blog musical",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
    python vvmm_post_creator.py                 # Ejecución normal
    python vvmm_post_creator.py --debug         # Con debug activado
    python vvmm_post_creator.py --no-preview    # Sin preview del sitio
    python vvmm_post_creator.py --validate-only # Solo validar entorno
        """
    )

    parser.add_argument('-d', '--debug', action='store_true',
                       help='Activar modo debug')
    parser.add_argument('--no-preview', action='store_true',
                       help='Deshabilitar preview del sitio')
    parser.add_argument('--no-git', action='store_true',
                       help='Deshabilitar push a GitHub')
    parser.add_argument('--no-spotify', action='store_true',
                       help='Deshabilitar integración con Spotify')
    parser.add_argument('--validate-only', action='store_true',
                       help='Solo validar entorno y salir')
    parser.add_argument('--project-root', type=str,
                       help='Ruta del directorio raíz del proyecto')

    args = parser.parse_args()

    # Configurar variables de entorno basadas en argumentos
    if args.debug:
        os.environ['DEBUG_MODE'] = 'true'
    if args.no_preview:
        os.environ['ENABLE_PREVIEW'] = 'false'
    if args.no_git:
        os.environ['ENABLE_GIT_PUSH'] = 'false'
    if args.no_spotify:
        os.environ['ENABLE_SPOTIFY_INTEGRATION'] = 'false'

    try:
        # Crear instancia del creador de posts
        creator = VVMMPostCreator(args.project_root)

        # Solo validar si se solicita
        if args.validate_only:
            creator.logger.info("Validación completada exitosamente")
            return 0

        # Ejecutar flujo principal
        return creator.run(args)

    except Exception as e:
        print(f"Error fatal: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
