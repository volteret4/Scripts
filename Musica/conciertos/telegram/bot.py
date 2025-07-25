#!/usr/bin/env python3
"""
Sistema de seguimiento de artistas con bot de Telegram
Permite a los usuarios seguir artistas y gestionar sus listas personales
Incluye notificaciones automáticas de conciertos
Adaptado para python-telegram-bot 22.2
"""

import sqlite3
import logging
import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
from telegram import Update, ForceReply, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters

country_state_city = None
lastfm_service = None

# Importar funciones del archivo mb_artist_info.py existente
try:
    from apis.mb_artist_info import (
        search_artist_in_musicbrainz,
        get_artist_from_musicbrainz,
        setup_musicbrainz,
        setup_cache
    )
except ImportError:
    print("Advertencia: No se pudo importar mb_artist_info.py")
    print("Asegúrate de que el archivo esté en el mismo directorio")

# Importar servicios de búsqueda de conciertos
try:
    from apis.country_state_city import CountryCityService, ArtistTrackerDatabaseExtended
    from apis.ticketmaster import TicketmasterService
    from apis.spotify import SpotifyService
    from apis.setlistfm import SetlistfmService
except ImportError:
    print("Advertencia: No se pudieron importar los servicios de conciertos")

# Importar servicio de Last.fm
try:
    from apis.lastfm import LastFmService
except ImportError:
    print("Advertencia: No se pudo importar lastfm.py")
    LastFmService = None

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class ArtistTrackerDatabase:
    """Clase para manejar la base de datos de usuarios y artistas seguidos"""

    def __init__(self, db_path: str = "artist_tracker.db"):
        """
        Inicializa la base de datos

        Args:
            db_path: Ruta del archivo de base de datos
        """
        self.db_path = db_path
        self.init_database()

    def get_connection(self) -> sqlite3.Connection:
        """Obtiene una conexión a la base de datos"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_database(self):
        """Inicializa las tablas de la base de datos"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Tabla de usuarios
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    chat_id INTEGER NOT NULL UNIQUE,
                    notification_time TEXT DEFAULT '09:00',
                    notification_enabled BOOLEAN DEFAULT 1,
                    country_filter TEXT DEFAULT 'ES',
                    service_ticketmaster BOOLEAN DEFAULT 1,
                    service_spotify BOOLEAN DEFAULT 1,
                    service_setlistfm BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Verificar si las nuevas columnas existen, si no, añadirlas
            cursor.execute("PRAGMA table_info(users)")
            columns = [col[1] for col in cursor.fetchall()]

            if 'country_filter' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN country_filter TEXT DEFAULT 'ES'")
                logger.info("Columna country_filter añadida a users")

            if 'service_ticketmaster' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN service_ticketmaster BOOLEAN DEFAULT 1")
                logger.info("Columna service_ticketmaster añadida a users")

            if 'service_spotify' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN service_spotify BOOLEAN DEFAULT 1")
                logger.info("Columna service_spotify añadida a users")

            if 'service_setlistfm' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN service_setlistfm BOOLEAN DEFAULT 1")
                logger.info("Columna service_setlistfm añadida a users")

            # Tabla de artistas
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS artists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    mbid TEXT UNIQUE,
                    country TEXT,
                    formed_year INTEGER,
                    ended_year INTEGER,
                    total_works INTEGER,
                    musicbrainz_url TEXT,
                    artist_type TEXT,
                    disambiguation TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(name, mbid)
                )
            """)

            # Tabla de relación usuarios-artistas seguidos
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_followed_artists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    artist_id INTEGER NOT NULL,
                    followed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                    FOREIGN KEY (artist_id) REFERENCES artists (id) ON DELETE CASCADE,
                    UNIQUE(user_id, artist_id)
                )
            """)

            # Tabla temporal para selecciones de artistas pendientes
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pending_artist_selections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    search_results TEXT NOT NULL,
                    original_query TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Nueva tabla para conciertos encontrados
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS concerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    artist_name TEXT NOT NULL,
                    concert_name TEXT NOT NULL,
                    venue TEXT,
                    city TEXT,
                    country TEXT,
                    date TEXT,
                    time TEXT,
                    url TEXT,
                    source TEXT,
                    concert_hash TEXT UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Nueva tabla para notificaciones enviadas
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notifications_sent (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    concert_id INTEGER NOT NULL,
                    notification_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                    FOREIGN KEY (concert_id) REFERENCES concerts (id) ON DELETE CASCADE,
                    UNIQUE(user_id, concert_id)
                )
            """)

            # Nueva tabla para caché de búsquedas de usuario
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_search_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    search_type TEXT NOT NULL,
                    search_data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            """)

                        # Nueva tabla para usuarios de Last.fm
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_lastfm (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    lastfm_username TEXT NOT NULL,
                    lastfm_playcount INTEGER DEFAULT 0,
                    lastfm_registered TEXT DEFAULT '',
                    sync_limit INTEGER DEFAULT 20,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                    UNIQUE(user_id)
                )
            """)

            # Tabla para almacenar selecciones pendientes de Last.fm
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pending_lastfm_sync (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    period TEXT NOT NULL,
                    artists_data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                    UNIQUE(user_id, period)
                )
            """)

            # Índices para optimizar consultas
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_chat_id ON users(chat_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_artists_mbid ON artists(mbid)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_artists_name ON artists(name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_followed_user_id ON user_followed_artists(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_followed_artist_id ON user_followed_artists(artist_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pending_chat_id ON pending_artist_selections(chat_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_concerts_hash ON concerts(concert_hash)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_concerts_artist ON concerts(artist_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications_sent(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_concert ON notifications_sent(concert_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_search_cache_user ON user_search_cache(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_search_cache_created ON user_search_cache(created_at)")

            # Índices para Last.fm
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_lastfm_user_id ON user_lastfm(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pending_lastfm_user_id ON pending_lastfm_sync(user_id)")


            conn.commit()
            logger.info("Base de datos inicializada correctamente")

        except sqlite3.Error as e:
            logger.error(f"Error al inicializar la base de datos: {e}")
            conn.rollback()
        finally:
            conn.close()

    def add_user(self, username: str, chat_id: int) -> bool:
        """
        Añade un nuevo usuario

        Args:
            username: Nombre de usuario
            chat_id: ID del chat de Telegram

        Returns:
            True si se añadió correctamente, False en caso contrario
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT OR REPLACE INTO users (username, chat_id, last_activity)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (username, chat_id))

            conn.commit()
            logger.info(f"Usuario {username} añadido/actualizado con chat_id {chat_id}")
            return True

        except sqlite3.Error as e:
            logger.error(f"Error al añadir usuario {username}: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_user_by_chat_id(self, chat_id: int) -> Optional[Dict]:
        """
        Obtiene un usuario por su chat_id

        Args:
            chat_id: ID del chat de Telegram

        Returns:
            Diccionario con datos del usuario o None si no existe
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,))
            row = cursor.fetchone()

            if row:
                return dict(row)
            return None

        except sqlite3.Error as e:
            logger.error(f"Error al obtener usuario por chat_id {chat_id}: {e}")
            return None
        finally:
            conn.close()

    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """
        Obtiene un usuario por su nombre de usuario

        Args:
            username: Nombre de usuario

        Returns:
            Diccionario con datos del usuario o None si no existe
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
            row = cursor.fetchone()

            if row:
                return dict(row)
            return None

        except sqlite3.Error as e:
            logger.error(f"Error al obtener usuario {username}: {e}")
            return None
        finally:
            conn.close()

# lastfm

    def set_user_lastfm(self, user_id: int, lastfm_username: str, user_info: dict = None) -> bool:
        """
        Establece el usuario de Last.fm para un usuario

        Args:
            user_id: ID del usuario
            lastfm_username: Nombre de usuario de Last.fm
            user_info: Información adicional del usuario (opcional)

        Returns:
            True si se estableció correctamente
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            playcount = 0
            registered = ''

            if user_info:
                playcount = user_info.get('playcount', 0)
                registered = user_info.get('registered', '')

            cursor.execute("""
                INSERT OR REPLACE INTO user_lastfm
                (user_id, lastfm_username, lastfm_playcount, lastfm_registered, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (user_id, lastfm_username, playcount, registered))

            conn.commit()
            return cursor.rowcount > 0

        except sqlite3.Error as e:
            logger.error(f"Error estableciendo usuario Last.fm: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_user_lastfm(self, user_id: int) -> Optional[Dict]:
        """
        Obtiene el usuario de Last.fm asociado

        Args:
            user_id: ID del usuario

        Returns:
            Diccionario con datos de Last.fm o None si no existe
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT * FROM user_lastfm WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()

            if row:
                return dict(row)
            return None

        except sqlite3.Error as e:
            logger.error(f"Error obteniendo usuario Last.fm: {e}")
            return None
        finally:
            conn.close()

    def set_lastfm_sync_limit(self, user_id: int, limit: int) -> bool:
        """
        Establece el límite de sincronización para Last.fm

        Args:
            user_id: ID del usuario
            limit: Número de artistas a sincronizar

        Returns:
            True si se estableció correctamente
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE user_lastfm SET sync_limit = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (limit, user_id))

            conn.commit()
            return cursor.rowcount > 0

        except sqlite3.Error as e:
            logger.error(f"Error estableciendo límite de sincronización: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def save_pending_lastfm_sync(self, user_id: int, period: str, artists_data: List[Dict]) -> bool:
        """
        Guarda una sincronización pendiente de Last.fm

        Args:
            user_id: ID del usuario
            period: Período de Last.fm
            artists_data: Lista de artistas a sincronizar

        Returns:
            True si se guardó correctamente
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT OR REPLACE INTO pending_lastfm_sync
                (user_id, period, artists_data, created_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (user_id, period, json.dumps(artists_data)))

            conn.commit()
            return True

        except sqlite3.Error as e:
            logger.error(f"Error guardando sincronización pendiente: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_pending_lastfm_sync(self, user_id: int, period: str) -> Optional[List[Dict]]:
        """
        Obtiene una sincronización pendiente de Last.fm

        Args:
            user_id: ID del usuario
            period: Período de Last.fm

        Returns:
            Lista de artistas o None si no existe
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT artists_data FROM pending_lastfm_sync
                WHERE user_id = ? AND period = ?
            """, (user_id, period))

            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None

        except (sqlite3.Error, json.JSONDecodeError) as e:
            logger.error(f"Error obteniendo sincronización pendiente: {e}")
            return None
        finally:
            conn.close()

    def clear_pending_lastfm_sync(self, user_id: int, period: str = None):
        """
        Limpia sincronizaciones pendientes de Last.fm

        Args:
            user_id: ID del usuario
            period: Período específico (opcional, si no se especifica limpia todos)
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            if period:
                cursor.execute("DELETE FROM pending_lastfm_sync WHERE user_id = ? AND period = ?", (user_id, period))
            else:
                cursor.execute("DELETE FROM pending_lastfm_sync WHERE user_id = ?", (user_id,))

            conn.commit()

        except sqlite3.Error as e:
            logger.error(f"Error limpiando sincronización pendiente: {e}")
        finally:
            conn.close()


    def get_artist_by_mbid(self, mbid: str) -> Optional[int]:
        """
        Busca un artista por su MBID

        Args:
            mbid: MusicBrainz ID del artista

        Returns:
            ID del artista o None si no existe
        """
        if not mbid:
            return None

        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT id FROM artists WHERE mbid = ?", (mbid,))
            row = cursor.fetchone()

            if row:
                return row[0]
            return None

        except sqlite3.Error as e:
            logger.error(f"Error buscando artista por MBID {mbid}: {e}")
            return None
        finally:
            conn.close()

    def format_artists_preview(self, artists: List[Dict], limit: int = 10) -> str:
        """
        Formatea una vista previa de artistas con información de MBID

        Args:
            artists: Lista de artistas
            limit: Número máximo de artistas a mostrar

        Returns:
            String formateado con los artistas
        """
        if not artists:
            return "No se encontraron artistas"

        lines = []
        display_artists = artists[:limit]
        mbid_count = sum(1 for artist in display_artists if artist.get("mbid"))

        for i, artist in enumerate(display_artists, 1):
            playcount = artist.get("playcount", 0)
            name = artist.get("name", "Nombre desconocido")
            mbid = artist.get("mbid", "")

            # Escapar caracteres especiales para Markdown
            safe_name = name.replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")

            line = f"{i}. *{safe_name}*"

            # Añadir información de reproducción
            if playcount > 0:
                line += f" ({playcount:,} reproducciones)"

            # Indicar si tiene MBID
            if mbid:
                line += " 🎵"  # Emoji para indicar que tiene MBID

            # Añadir géneros si están disponibles
            genres = artist.get("genres", [])
            if genres:
                genre_text = ", ".join(genres[:2])  # Mostrar hasta 2 géneros
                line += f" _{genre_text}_"

            lines.append(line)

        if len(artists) > limit:
            lines.append(f"_...y {len(artists) - limit} más_")

        # Añadir estadísticas de MBID
        lines.append("")
        lines.append(f"🎵 {mbid_count}/{len(display_artists)} artistas con MBID para sincronización precisa")

        return "\n".join(lines)




# countries
    def set_country_filter(self, user_id: int, country_code: str) -> bool:
        """
        VERSIÓN LEGACY - Mantener compatibilidad
        Ahora redirige al sistema de países múltiples
        """
        if country_state_city:
            # Limpiar países existentes y añadir el nuevo
            user_countries = country_state_city.get_user_countries(user_id)
            for country in user_countries:
                country_state_city.remove_user_country(user_id, country['code'])

            # Añadir el nuevo país
            return country_state_city.add_user_country(user_id, country_code)
        else:
            # Fallback al sistema original
            conn = self.get_connection()
            cursor = conn.cursor()

            try:
                cursor.execute("""
                    UPDATE users SET country_filter = ? WHERE id = ?
                """, (country_code.upper(), user_id))

                conn.commit()
                return cursor.rowcount > 0

            except sqlite3.Error as e:
                logger.error(f"Error al establecer filtro de país: {e}")
                return False
            finally:
                conn.close()


    def _search_exact_artist(self, artist_name: str) -> List[Dict]:
        """Búsqueda exacta usando comillas"""
        try:
            # Buscar con comillas para coincidencia exacta
            exact_query = f'"{artist_name}"'
            search_results = search_artist_in_musicbrainz(exact_query)

            if not search_results:
                return []

            candidates = []
            for result in search_results[:5]:  # Limitar manualmente a 5
                candidate = self._parse_search_result(result, boost_score=20)  # Boost para exactos
                candidates.append(candidate)

            return candidates

        except Exception as e:
            logger.error(f"Error en búsqueda exacta: {e}")
            return []

    def _search_basic_artist(self, artist_name: str) -> List[Dict]:
        """Búsqueda básica como último recurso"""
        try:
            # Búsqueda básica sin modificadores especiales
            search_results = search_artist_in_musicbrainz(artist_name)

            if not search_results:
                return []

            candidates = []
            for result in search_results[:8]:  # Limitar manualmente a 8
                candidate = self._parse_search_result(result, boost_score=0)  # Sin boost
                candidates.append(candidate)

            return candidates

        except Exception as e:
            logger.error(f"Error en búsqueda básica: {e}")
            return []


    def _fallback_search(self, artist_name: str) -> List[Dict]:
        """Búsqueda de fallback usando el método original"""
        try:
            logger.info(f"Usando búsqueda de fallback para '{artist_name}'")
            search_results = search_artist_in_musicbrainz(artist_name)

            if not search_results:
                return []

            candidates = []
            for result in search_results[:10]:  # Usar el código original
                # Convertir score a entero de forma segura
                score = 0
                try:
                    score_value = result.get('ext:score', result.get('score', 0))
                    if isinstance(score_value, str):
                        score = int(float(score_value))
                    elif isinstance(score_value, (int, float)):
                        score = int(score_value)
                except (ValueError, TypeError):
                    score = 0

                candidate = {
                    'mbid': result.get('id'),
                    'name': result.get('name', artist_name),
                    'type': result.get('type', ''),
                    'country': result.get('country', ''),
                    'disambiguation': result.get('disambiguation', ''),
                    'score': score
                }

                # Obtener información de fecha si está disponible
                if 'life-span' in result:
                    life_span = result['life-span']
                    if 'begin' in life_span and life_span['begin']:
                        candidate['formed_year'] = life_span['begin'][:4]
                    if 'end' in life_span and life_span['end']:
                        candidate['ended_year'] = life_span['end'][:4]

                candidates.append(candidate)

            # Ordenar por score descendente
            candidates.sort(key=lambda x: x['score'], reverse=True)
            return candidates

        except Exception as e:
            logger.error(f"Error en búsqueda de fallback: {e}")
            return []



    def _search_artist_field(self, artist_name: str) -> List[Dict]:
        """Búsqueda específica en el campo artist"""
        try:
            # Buscar específicamente en el campo artist con comillas
            field_query = f'artist:"{artist_name}"'
            search_results = search_artist_in_musicbrainz(field_query)

            if not search_results:
                # Fallback sin comillas en el campo artist
                field_query = f'artist:{artist_name}'
                search_results = search_artist_in_musicbrainz(field_query)

            if not search_results:
                return []

            candidates = []
            for result in search_results[:5]:  # Limitar manualmente a 5
                candidate = self._parse_search_result(result, boost_score=10)  # Boost moderado
                candidates.append(candidate)

            return candidates

        except Exception as e:
            logger.error(f"Error en búsqueda por campo: {e}")
            return []


    def _search_fuzzy_artist(self, artist_name: str) -> List[Dict]:
        """Búsqueda fuzzy como último recurso"""
        try:
            # Búsqueda fuzzy solo para nombres cortos o casos especiales
            words = artist_name.split()

            # Solo hacer búsqueda fuzzy si tenemos pocas palabras
            if len(words) > 2:
                return []

            fuzzy_query = artist_name  # Búsqueda básica sin modificadores
            search_results = search_artist_in_musicbrainz(fuzzy_query, limit=8)

            if not search_results:
                return []

            candidates = []
            for result in search_results:
                candidate = self._parse_search_result(result, boost_score=0)  # Sin boost
                candidates.append(candidate)

            return candidates

        except Exception as e:
            logger.error(f"Error en búsqueda fuzzy: {e}")
            return []

    def _parse_search_result(self, result: Dict, boost_score: int = 0) -> Dict:
        """Convierte un resultado de MusicBrainz en un candidato"""
        # Convertir score a entero de forma segura
        score = 0
        try:
            score_value = result.get('ext:score', result.get('score', 0))
            if isinstance(score_value, str):
                score = int(float(score_value))
            elif isinstance(score_value, (int, float)):
                score = int(score_value)
        except (ValueError, TypeError):
            score = 0

        # Aplicar boost
        score += boost_score

        candidate = {
            'mbid': result.get('id'),
            'name': result.get('name', ''),
            'type': result.get('type', ''),
            'country': result.get('country', ''),
            'disambiguation': result.get('disambiguation', ''),
            'score': score
        }

        # Obtener información de fecha si está disponible
        if 'life-span' in result:
            life_span = result['life-span']
            if 'begin' in life_span and life_span['begin']:
                candidate['formed_year'] = life_span['begin'][:4]
            if 'end' in life_span and life_span['end']:
                candidate['ended_year'] = life_span['end'][:4]

        return candidate



    def _filter_candidates_by_relevance(self, candidates: List[Dict], original_query: str) -> List[Dict]:
        """Filtra candidatos por relevancia usando múltiples criterios"""
        if not candidates:
            return []

        filtered = []
        query_lower = original_query.lower()
        query_words = set(query_lower.split())

        for candidate in candidates:
            name_lower = candidate['name'].lower()
            name_words = set(name_lower.split())

            # Calcular score de relevancia
            relevance_score = 0

            # 1. Coincidencia exacta (máxima puntuación)
            if name_lower == query_lower:
                relevance_score += 100

            # 2. Coincidencia de todas las palabras
            elif query_words.issubset(name_words):
                relevance_score += 80

            # 3. Coincidencia parcial de palabras
            else:
                word_matches = len(query_words.intersection(name_words))
                if word_matches > 0:
                    # Dar más peso si coinciden palabras importantes
                    match_ratio = word_matches / len(query_words)
                    relevance_score += match_ratio * 60

                    # Bonus extra si la primera palabra coincide
                    if query_words and name_words:
                        first_query_word = list(query_words)[0]
                        if first_query_word in name_words:
                            relevance_score += 10
                else:
                    # Si no hay coincidencia de palabras, revisar si es substring
                    if any(word in name_lower for word in query_words):
                        relevance_score += 20
                    else:
                        # Sin coincidencia, probablemente irrelevante
                        continue

            # 4. Penalizar si tiene demasiadas palabras extra (pero no tanto)
            extra_words = len(name_words) - len(query_words)
            if extra_words > 2:
                relevance_score -= extra_words * 3  # Reducido de 5 a 3

            # 5. Bonus por tipo de artista
            artist_type = candidate.get('type', '').lower()
            if artist_type in ['person', 'group', 'band']:
                relevance_score += 5

            # 6. Penalizar resultados muy antiguos solo si es evidente que es compositor clásico
            formed_year = candidate.get('formed_year')
            if formed_year:
                try:
                    year = int(formed_year)
                    if year < 1700:  # Solo penalizar compositores muy antiguos
                        relevance_score -= 15
                    elif year < 1900 and 'composer' in candidate.get('type', '').lower():
                        relevance_score -= 10
                except (ValueError, TypeError):
                    pass

            candidate['relevance_score'] = max(0, relevance_score)

            # Umbral de relevancia más permisivo
            min_threshold = 15 if len(candidates) < 5 else 25
            if relevance_score >= min_threshold:
                filtered.append(candidate)

        # Si no hay resultados después del filtro, usar umbral más bajo
        if not filtered and candidates:
            logger.info(f"Aplicando umbral más permisivo para '{original_query}'")
            for candidate in candidates:
                if candidate.get('relevance_score', 0) >= 10:
                    filtered.append(candidate)

        # Si aún no hay resultados, tomar los mejores por score original
        if not filtered and candidates:
            logger.info(f"Usando fallback de score original para '{original_query}'")
            filtered = sorted(candidates, key=lambda x: x.get('score', 0), reverse=True)[:3]

        return filtered


    def _rank_candidates(self, candidates: List[Dict], original_query: str) -> List[Dict]:
        """Ordena candidatos por relevancia combinada"""
        if not candidates:
            return []

        def combined_score(candidate):
            # Combinar score de MusicBrainz y score de relevancia
            mb_score = candidate.get('score', 0)
            relevance_score = candidate.get('relevance_score', 0)

            # Dar más peso a la relevancia que al score de MusicBrainz
            return (relevance_score * 1.5) + (mb_score * 0.5)

        # Ordenar por score combinado descendente
        sorted_candidates = sorted(candidates, key=combined_score, reverse=True)

        return sorted_candidates






    def search_artist_in_musicbrainz_improved(query: str, limit: int = 10) -> List[Dict]:
        """
        Versión mejorada de search_artist_in_musicbrainz que acepta limit

        Args:
            query: Consulta de búsqueda
            limit: Número máximo de resultados

        Returns:
            Lista de resultados de la búsqueda
        """
        try:
            # Esta función debería estar en mb_artist_info.py
            # Por ahora, asumo que existe la función original y la extendemos
            from apis.mb_artist_info import search_artist_in_musicbrainz

            # Si la función original no acepta limit, podemos modificarla o usar limit por defecto
            search_results = search_artist_in_musicbrainz(query)

            # Aplicar limit manualmente si es necesario
            if search_results and len(search_results) > limit:
                return search_results[:limit]

            return search_results or []

        except Exception as e:
            logger.error(f"Error en búsqueda de MusicBrainz: {e}")
            return []


    def search_artist_candidates(self, artist_name: str) -> List[Dict]:
        """
        Busca candidatos de artistas en MusicBrainz con estrategias mejoradas
        Versión corregida que funciona con la API existente

        Args:
            artist_name: Nombre del artista a buscar

        Returns:
            Lista de candidatos encontrados, ordenados por relevancia
        """
        logger.info(f"Buscando candidatos para '{artist_name}' en MusicBrainz...")

        try:
            candidates = []

            # Estrategia 1: Búsqueda exacta con comillas
            exact_results = self._search_exact_artist(artist_name)
            if exact_results:
                candidates.extend(exact_results)
                logger.info(f"Búsqueda exacta: {len(exact_results)} resultados")

            # Estrategia 2: Búsqueda por campo artist específico
            if len(candidates) < 5:  # Solo si no tenemos suficientes resultados exactos
                field_results = self._search_artist_field(artist_name)
                candidates.extend(field_results)
                logger.info(f"Búsqueda por campo: {len(field_results)} resultados adicionales")

            # Estrategia 3: Búsqueda básica solo si es necesario
            if len(candidates) < 3:  # Solo si realmente necesitamos más resultados
                basic_results = self._search_basic_artist(artist_name)
                candidates.extend(basic_results)
                logger.info(f"Búsqueda básica: {len(basic_results)} resultados adicionales")

            # Eliminar duplicados basándose en MBID
            seen_mbids = set()
            unique_candidates = []
            for candidate in candidates:
                mbid = candidate.get('mbid')
                if mbid and mbid not in seen_mbids:
                    seen_mbids.add(mbid)
                    unique_candidates.append(candidate)
                elif not mbid:  # Mantener candidatos sin MBID (aunque es raro)
                    unique_candidates.append(candidate)

            # Aplicar filtros de relevancia
            filtered_candidates = self._filter_candidates_by_relevance(unique_candidates, artist_name)

            # Ordenar por score y relevancia
            final_candidates = self._rank_candidates(filtered_candidates, artist_name)

            logger.info(f"Candidatos finales para '{artist_name}': {len(final_candidates)}")
            for i, candidate in enumerate(final_candidates[:5]):
                logger.info(f"  {i+1}. {candidate['name']} - Score: {candidate['score']} - Relevancia: {candidate.get('relevance_score', 0)}")

            return final_candidates[:10]  # Limitar a 10 mejores resultados

        except Exception as e:
            logger.error(f"Error al buscar candidatos para '{artist_name}': {e}")
            # Fallback a la búsqueda original si algo falla
            return self._fallback_search(artist_name)




    def create_artist_from_candidate(self, candidate: Dict) -> Optional[int]:
        """
        Crea un artista en la base de datos a partir de un candidato seleccionado

        Args:
            candidate: Diccionario con datos del candidato

        Returns:
            ID del artista creado o None si hay error
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            mbid = candidate['mbid']

            # Verificar si ya existe
            cursor.execute("SELECT id FROM artists WHERE mbid = ?", (mbid,))
            row = cursor.fetchone()
            if row:
                return row[0]

            # Obtener datos detallados del artista
            artist_data = get_artist_from_musicbrainz(mbid) if mbid else None

            # Extraer información relevante
            name = candidate['name']
            country = candidate.get('country')
            artist_type = candidate.get('type')
            disambiguation = candidate.get('disambiguation')
            formed_year = None
            ended_year = None
            total_works = None
            musicbrainz_url = f"https://musicbrainz.org/artist/{mbid}" if mbid else None

            if artist_data:
                # Actualizar con datos más detallados
                country = artist_data.get('country') or country
                artist_type = artist_data.get('type') or artist_type
                disambiguation = artist_data.get('disambiguation') or disambiguation

                # Extraer años de formación y disolución
                if 'life-span' in artist_data:
                    life_span = artist_data['life-span']
                    if 'begin' in life_span and life_span['begin']:
                        try:
                            formed_year = int(life_span['begin'][:4])
                        except (ValueError, TypeError):
                            pass
                    if 'end' in life_span and life_span['end']:
                        try:
                            ended_year = int(life_span['end'][:4])
                        except (ValueError, TypeError):
                            pass

                # Obtener número de release groups (álbumes) en lugar de works
                if 'release-group-count' in artist_data:
                    try:
                        total_works = int(artist_data['release-group-count'])
                    except (ValueError, TypeError):
                        pass
                elif 'work-count' in artist_data:
                    # Fallback a work-count si release-group-count no está disponible
                    try:
                        total_works = int(artist_data['work-count'])
                    except (ValueError, TypeError):
                        pass

            # Insertar artista en la base de datos
            cursor.execute("""
                INSERT INTO artists (name, mbid, country, formed_year, ended_year, total_works,
                                   musicbrainz_url, artist_type, disambiguation)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, mbid, country, formed_year, ended_year, total_works,
                  musicbrainz_url, artist_type, disambiguation))

            artist_id = cursor.lastrowid
            conn.commit()

            logger.info(f"Artista '{name}' creado con datos de MusicBrainz (MBID: {mbid})")
            return artist_id

        except sqlite3.Error as e:
            logger.error(f"Error al crear artista: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()

    def save_pending_selection(self, chat_id: int, candidates: List[Dict], original_query: str) -> bool:
        """
        Guarda una selección pendiente para un usuario

        Args:
            chat_id: ID del chat
            candidates: Lista de candidatos
            original_query: Consulta original del usuario

        Returns:
            True si se guardó correctamente
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Limpiar selecciones anteriores del mismo chat
            cursor.execute("DELETE FROM pending_artist_selections WHERE chat_id = ?", (chat_id,))

            # Guardar nueva selección
            cursor.execute("""
                INSERT INTO pending_artist_selections (chat_id, search_results, original_query)
                VALUES (?, ?, ?)
            """, (chat_id, json.dumps(candidates), original_query))

            conn.commit()
            return True

        except sqlite3.Error as e:
            logger.error(f"Error al guardar selección pendiente: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_pending_selection(self, chat_id: int) -> Optional[Tuple[List[Dict], str]]:
        """
        Obtiene una selección pendiente para un usuario

        Args:
            chat_id: ID del chat

        Returns:
            Tupla con (candidatos, consulta_original) o None si no existe
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT search_results, original_query
                FROM pending_artist_selections
                WHERE chat_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (chat_id,))

            row = cursor.fetchone()
            if row:
                candidates = json.loads(row[0])
                original_query = row[1]
                return candidates, original_query

            return None

        except (sqlite3.Error, json.JSONDecodeError) as e:
            logger.error(f"Error al obtener selección pendiente: {e}")
            return None
        finally:
            conn.close()

    def clear_pending_selection(self, chat_id: int):
        """Limpia la selección pendiente de un usuario"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("DELETE FROM pending_artist_selections WHERE chat_id = ?", (chat_id,))
            conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Error al limpiar selección pendiente: {e}")
        finally:
            conn.close()

    def add_followed_artist(self, user_id: int, artist_id: int) -> bool:
        """
        Añade un artista a la lista de seguimiento de un usuario

        Args:
            user_id: ID del usuario
            artist_id: ID del artista

        Returns:
            True si se añadió correctamente, False en caso contrario
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT OR IGNORE INTO user_followed_artists (user_id, artist_id)
                VALUES (?, ?)
            """, (user_id, artist_id))

            # Verificar si se insertó algo (rowcount > 0 significa que era nuevo)
            was_new = cursor.rowcount > 0
            conn.commit()

            return was_new

        except sqlite3.Error as e:
            logger.error(f"Error al añadir artista seguido: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_user_followed_artists(self, user_id: int) -> List[Dict]:
        """
        Obtiene la lista de artistas seguidos por un usuario

        Args:
            user_id: ID del usuario

        Returns:
            Lista de diccionarios con información de los artistas
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT a.*, ufa.followed_at
                FROM artists a
                JOIN user_followed_artists ufa ON a.id = ufa.artist_id
                WHERE ufa.user_id = ?
                ORDER BY ufa.followed_at DESC
            """, (user_id,))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        except sqlite3.Error as e:
            logger.error(f"Error al obtener artistas seguidos para usuario {user_id}: {e}")
            return []
        finally:
            conn.close()

    def remove_followed_artist(self, user_id: int, artist_name: str) -> bool:
        """
        Elimina un artista de la lista de seguimiento de un usuario

        Args:
            user_id: ID del usuario
            artist_name: Nombre del artista

        Returns:
            True si se eliminó correctamente, False en caso contrario
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                DELETE FROM user_followed_artists
                WHERE user_id = ? AND artist_id = (
                    SELECT id FROM artists WHERE LOWER(name) = LOWER(?)
                )
            """, (user_id, artist_name))

            was_removed = cursor.rowcount > 0
            conn.commit()

            return was_removed

        except sqlite3.Error as e:
            logger.error(f"Error al eliminar artista seguido: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def set_notification_time(self, user_id: int, notification_time: str) -> bool:
        """
        Establece la hora de notificación para un usuario

        Args:
            user_id: ID del usuario
            notification_time: Hora en formato HH:MM

        Returns:
            True si se actualizó correctamente
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE users SET notification_time = ? WHERE id = ?
            """, (notification_time, user_id))

            conn.commit()
            return cursor.rowcount > 0

        except sqlite3.Error as e:
            logger.error(f"Error al establecer hora de notificación: {e}")
            return False
        finally:
            conn.close()

    def toggle_notifications(self, user_id: int) -> bool:
        """
        Activa/desactiva las notificaciones para un usuario

        Args:
            user_id: ID del usuario

        Returns:
            True si están activadas después del cambio
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Obtener estado actual
            cursor.execute("SELECT notification_enabled FROM users WHERE id = ?", (user_id,))
            current_state = cursor.fetchone()[0]

            # Cambiar estado
            new_state = not current_state
            cursor.execute("""
                UPDATE users SET notification_enabled = ? WHERE id = ?
            """, (new_state, user_id))

            conn.commit()
            return new_state

        except sqlite3.Error as e:
            logger.error(f"Error al cambiar estado de notificaciones: {e}")
            return False
        finally:
            conn.close()
        """
        Establece el filtro de país para un usuario

        Args:
            user_id: ID del usuario
            country_code: Código de país (ej: ES, US, FR)

        Returns:
            True si se actualizó correctamente
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE users SET country_filter = ? WHERE id = ?
            """, (country_code.upper(), user_id))

            conn.commit()
            return cursor.rowcount > 0

        except sqlite3.Error as e:
            logger.error(f"Error al establecer filtro de país: {e}")
            return False
        finally:
            conn.close()

    def set_service_status(self, user_id: int, service: str, enabled: bool) -> bool:
        """
        Activa o desactiva un servicio para un usuario

        Args:
            user_id: ID del usuario
            service: Nombre del servicio (ticketmaster, spotify, setlistfm)
            enabled: True para activar, False para desactivar

        Returns:
            True si se actualizó correctamente
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Validar nombre del servicio
            valid_services = ['ticketmaster', 'spotify', 'setlistfm']
            if service.lower() not in valid_services:
                return False

            column_name = f"service_{service.lower()}"

            cursor.execute(f"""
                UPDATE users SET {column_name} = ? WHERE id = ?
            """, (enabled, user_id))

            conn.commit()
            return cursor.rowcount > 0

        except sqlite3.Error as e:
            logger.error(f"Error al establecer estado del servicio: {e}")
            return False
        finally:
            conn.close()

    def get_user_services(self, user_id: int) -> Dict[str, any]:
        """
        VERSIÓN EXTENDIDA - Incluye países múltiples
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT service_ticketmaster, service_spotify, service_setlistfm, country_filter
                FROM users WHERE id = ?
            """, (user_id,))

            row = cursor.fetchone()
            services = {
                'ticketmaster': bool(row[0]) if row else True,
                'spotify': bool(row[1]) if row else True,
                'setlistfm': bool(row[2]) if row else True,
                'country_filter': row[3] if row else 'ES'
            }

            # Añadir información de países múltiples
            if country_state_city:
                user_countries = country_state_city.get_user_country_codes(user_id)
                services['countries'] = user_countries

                # Mantener compatibilidad con country_filter
                if user_countries:
                    services['country_filter'] = list(user_countries)[0]
                elif not services['country_filter']:
                    services['country_filter'] = 'ES'
            else:
                # Solo country_filter legacy
                services['countries'] = {services['country_filter']}

            return services

        except sqlite3.Error as e:
            logger.error(f"Error al obtener servicios del usuario: {e}")
            return {
                'ticketmaster': True,
                'spotify': True,
                'setlistfm': True,
                'country_filter': 'ES',
                'countries': {'ES'}
            }
        finally:
            conn.close()


    def save_concert(self, concert_data: Dict) -> Optional[int]:
        """
        Guarda un concierto en la base de datos

        Args:
            concert_data: Diccionario con datos del concierto

        Returns:
            ID del concierto guardado o None si ya existe
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Crear hash único para el concierto
            concert_hash = self._create_concert_hash(concert_data)

            # Verificar si ya existe
            cursor.execute("SELECT id FROM concerts WHERE concert_hash = ?", (concert_hash,))
            existing = cursor.fetchone()
            if existing:
                return existing[0]

            # Insertar nuevo concierto
            cursor.execute("""
                INSERT INTO concerts (
                    artist_name, concert_name, venue, city, country,
                    date, time, url, source, concert_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                concert_data.get('artist', ''),
                concert_data.get('name', ''),
                concert_data.get('venue', ''),
                concert_data.get('city', ''),
                concert_data.get('country', ''),
                concert_data.get('date', ''),
                concert_data.get('time', ''),
                concert_data.get('url', ''),
                concert_data.get('source', ''),
                concert_hash
            ))

            concert_id = cursor.lastrowid
            conn.commit()
            return concert_id

        except sqlite3.Error as e:
            logger.error(f"Error al guardar concierto: {e}")
            return None
        finally:
            conn.close()

    def _create_concert_hash(self, concert_data: Dict) -> str:
        """Crea un hash único para un concierto"""
        import hashlib

        # Usar datos clave para crear el hash
        key_data = f"{concert_data.get('artist', '')}-{concert_data.get('venue', '')}-{concert_data.get('date', '')}-{concert_data.get('source', '')}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def mark_concert_notified(self, user_id: int, concert_id: int) -> bool:
        """
        Marca un concierto como notificado para un usuario

        Args:
            user_id: ID del usuario
            concert_id: ID del concierto

        Returns:
            True si se marcó correctamente
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT OR IGNORE INTO notifications_sent (user_id, concert_id)
                VALUES (?, ?)
            """, (user_id, concert_id))

            conn.commit()
            return cursor.rowcount > 0

        except sqlite3.Error as e:
            logger.error(f"Error al marcar concierto como notificado: {e}")
            return False
        finally:
            conn.close()

    def get_unnotified_concerts_for_user(self, user_id: int) -> List[Dict]:
        """
        Obtiene conciertos no notificados para un usuario

        Args:
            user_id: ID del usuario

        Returns:
            Lista de conciertos no notificados
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT DISTINCT c.*
                FROM concerts c
                JOIN artists a ON LOWER(c.artist_name) = LOWER(a.name)
                JOIN user_followed_artists ufa ON a.id = ufa.artist_id
                WHERE ufa.user_id = ?
                AND NOT EXISTS (
                    SELECT 1 FROM notifications_sent ns
                    WHERE ns.user_id = ? AND ns.concert_id = c.id
                )
                ORDER BY c.date DESC
            """, (user_id, user_id))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        except sqlite3.Error as e:
            logger.error(f"Error al obtener conciertos no notificados: {e}")
            return []
        finally:
            conn.close()

    def get_all_concerts_for_user(self, user_id: int) -> List[Dict]:
        """
        Obtiene todos los conciertos para un usuario (notificados y no notificados)

        Args:
            user_id: ID del usuario

        Returns:
            Lista de todos los conciertos
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT DISTINCT c.*,
                       CASE WHEN ns.id IS NOT NULL THEN 1 ELSE 0 END as notified
                FROM concerts c
                JOIN artists a ON LOWER(c.artist_name) = LOWER(a.name)
                JOIN user_followed_artists ufa ON a.id = ufa.artist_id
                LEFT JOIN notifications_sent ns ON ns.user_id = ? AND ns.concert_id = c.id
                WHERE ufa.user_id = ?
                ORDER BY c.date DESC
            """, (user_id, user_id))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        except sqlite3.Error as e:
            logger.error(f"Error al obtener todos los conciertos: {e}")
            return []
        finally:
            conn.close()

    def get_users_for_notifications(self) -> List[Dict]:
        """
        Obtiene usuarios que tienen notificaciones habilitadas

        Returns:
            Lista de usuarios con notificaciones habilitadas
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT * FROM users
                WHERE notification_enabled = 1
            """)

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        except sqlite3.Error as e:
            logger.error(f"Error al obtener usuarios para notificaciones: {e}")
            return []
        finally:
            conn.close()

# Variables globales para los servicios
ticketmaster_service = None
spotify_service = None
setlistfm_service = None

def initialize_concert_services():
    """Inicializa los servicios de búsqueda de conciertos"""
    global ticketmaster_service, spotify_service, setlistfm_service

    # Configuración desde variables de entorno
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    CACHE_DIR = os.path.join(BASE_DIR, "cache")
    os.makedirs(CACHE_DIR, exist_ok=True)

    TICKETMASTER_API_KEY = os.environ.get("TICKETMASTER_API_KEY")
    SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
    SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")
    SPOTIFY_REDIRECT_URI = os.environ.get("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback")
    SETLISTFM_API_KEY = os.environ.get("SETLISTFM_API_KEY")

    try:
        if TICKETMASTER_API_KEY:
            ticketmaster_service = TicketmasterService(
                api_key=TICKETMASTER_API_KEY,
                cache_dir=os.path.join(CACHE_DIR, "ticketmaster")
            )
            logger.info("✅ Ticketmaster service inicializado")
        else:
            logger.warning("⚠️ TICKETMASTER_API_KEY no configurada")

        if SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET:
            spotify_service = SpotifyService(
                client_id=SPOTIFY_CLIENT_ID,
                client_secret=SPOTIFY_CLIENT_SECRET,
                redirect_uri=SPOTIFY_REDIRECT_URI,
                cache_dir=os.path.join(CACHE_DIR, "spotify")
            )
            logger.info("✅ Spotify service inicializado")
        else:
            logger.warning("⚠️ Credenciales de Spotify incompletas")

        if SETLISTFM_API_KEY:
            setlistfm_service = SetlistfmService(
                api_key=SETLISTFM_API_KEY,
                cache_dir=os.path.join(CACHE_DIR, "setlistfm"),
                db_path=None
            )
            logger.info("✅ Setlist.fm service inicializado")
        else:
            logger.warning("⚠️ SETLISTFM_API_KEY no configurada")

    except Exception as e:
        logger.error(f"Error inicializando servicios: {e}")

def initialize_country_service():
    """Inicializa el servicio de países y ciudades"""
    global country_state_city

    COUNTRY_API_KEY = os.environ.get("COUNTRY_CITY_API_KEY")

    if not COUNTRY_API_KEY:
        logger.warning("⚠️ COUNTRY_CITY_API_KEY no configurada")
        logger.warning("⚠️ Funcionalidad de países múltiples deshabilitada")
        return False

    try:
        from apis.country_state_city import CountryCityService

        country_state_city = CountryCityService(
            api_key=COUNTRY_API_KEY,
            db_path=db.db_path
        )

        logger.info("✅ Servicio de países y ciudades inicializado")
        return True

    except Exception as e:
        logger.error(f"❌ Error inicializando servicio de países: {e}")
        return False


def initialize_lastfm_service():
    """Inicializa el servicio de Last.fm"""
    global lastfm_service

    LASTFM_API_KEY = os.environ.get("LASTFM_API_KEY")

    if not LASTFM_API_KEY:
        logger.warning("⚠️ LASTFM_API_KEY no configurada")
        logger.warning("⚠️ Funcionalidad de Last.fm deshabilitada")
        return False

    if not LastFmService:
        logger.warning("⚠️ LastFmService no disponible")
        return False

    try:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        CACHE_DIR = os.path.join(BASE_DIR, "cache")

        lastfm_service = LastFmService(
            api_key=LASTFM_API_KEY,
            cache_dir=os.path.join(CACHE_DIR, "lastfm")
        )

        if lastfm_service.setup():
            logger.info("✅ Servicio de Last.fm inicializado")
            return True
        else:
            logger.error("❌ Error configurando Last.fm")
            lastfm_service = None
            return False

    except Exception as e:
        logger.error(f"❌ Error inicializando servicio de Last.fm: {e}")
        lastfm_service = None
        return False


async def addcountry_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /addcountry - añade un país a la configuración del usuario"""
    if not context.args:
        await update.message.reply_text(
            "❌ Uso incorrecto. Debes especificar el código o nombre del país.\n"
            "Ejemplo: `/addcountry ES` o `/addcountry Spain`\n"
            "Usa `/listcountries` para ver países disponibles"
        )
        return

    if not country_state_city:
        await update.message.reply_text(
            "❌ Servicio de países no disponible.\n"
            "Contacta al administrador para configurar la API key."
        )
        return

    chat_id = update.effective_chat.id

    # Verificar que el usuario esté registrado
    user = db.get_user_by_chat_id(chat_id)
    if not user:
        await update.message.reply_text(
            "❌ Primero debes registrarte con `/adduser <tu_nombre>`"
        )
        return

    query = " ".join(context.args)

    # Mensaje de estado
    status_message = await update.message.reply_text(
        f"🔍 Buscando país: '{query}'..."
    )

    try:
        # Si es un código de 2 letras, usarlo directamente
        if len(query) == 2 and query.isalpha():
            country_code = query.upper()

            # Verificar que existe
            country_info = country_state_city.get_country_info(country_code)
            if not country_info:
                # Intentar obtener países actualizados
                countries = country_state_city.get_available_countries(force_refresh=True)
                country_info = country_state_city.get_country_info(country_code)

            if country_info:
                selected_country = country_info
            else:
                await status_message.edit_text(
                    f"❌ País con código '{country_code}' no encontrado.\n"
                    f"Usa `/listcountries` para ver países disponibles."
                )
                return
        else:
            # Buscar por nombre
            matching_countries = country_state_city.search_countries(query)

            if not matching_countries:
                await status_message.edit_text(
                    f"❌ No se encontraron países que coincidan con '{query}'.\n"
                    f"Usa `/listcountries` para ver países disponibles."
                )
                return
            elif len(matching_countries) == 1:
                selected_country = matching_countries[0]
            else:
                # Múltiples coincidencias - mostrar opciones
                await show_country_selection(update, matching_countries, query, status_message)
                return

        # Añadir país
        await status_message.edit_text(
            f"⏳ Añadiendo país {selected_country['name']} ({selected_country['code']})...\n"
            f"Esto puede tardar un momento mientras obtenemos las ciudades..."
        )

        success = country_state_city.add_user_country(user['id'], selected_country['code'])

        if success:
            # Obtener estadísticas
            cities = country_state_city.get_country_cities(selected_country['code'])
            user_countries = country_state_city.get_user_countries(user['id'])

            await status_message.edit_text(
                f"✅ País añadido: {selected_country['name']} ({selected_country['code']})\n"
                f"🏙️ {len(cities)} ciudades cargadas\n"
                f"🌍 Total países configurados: {len(user_countries)}\n\n"
                f"Usa `/mycountries` para ver tu configuración actual."
            )
        else:
            await status_message.edit_text(
                f"❌ Error añadiendo el país {selected_country['name']}.\n"
                f"Es posible que ya lo tengas configurado."
            )

    except Exception as e:
        logger.error(f"Error en comando addcountry: {e}")
        await status_message.edit_text(
            "❌ Error al añadir el país. Inténtalo de nuevo más tarde."
        )


async def show_country_selection(update: Update, countries: List[Dict], original_query: str, message_to_edit):
    """Muestra una lista de países para que el usuario elija"""
    chat_id = update.effective_chat.id

    # Guardar países para posterior selección
    db.save_pending_selection(chat_id, countries, original_query)

    # Crear mensaje con opciones (limitar a 8 para no sobrecargar)
    message_lines = [f"🌍 *Encontré varios países para '{original_query}':*\n"]

    keyboard = []
    for i, country in enumerate(countries[:8]):
        option_text = f"{i+1}. *{country['name']}* ({country['code']})"
        if country.get('currency'):
            option_text += f" - {country['currency']}"

        message_lines.append(option_text)

        # Botón para esta opción
        button_text = f"{i+1}. {country['name']} ({country['code']})"
        if len(button_text) > 30:
            button_text = f"{country['name']} ({country['code']})"
            if len(button_text) > 30:
                button_text = button_text[:27] + "..."

        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"select_country_{i}")])

    # Botón de cancelar
    keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancel_country_selection")])

    message_lines.append("\n*Selecciona el país correcto:*")

    reply_markup = InlineKeyboardMarkup(keyboard)

    # Escapar caracteres especiales para Markdown
    response = "\n".join(message_lines)
    for char in ['_', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
        if char not in ['*', '_']:  # No escapar asteriscos y guiones bajos que usamos para formato
            response = response.replace(char, f'\\{char}')

    await message_to_edit.edit_text(
        response,
        parse_mode='MarkdownV2',
        reply_markup=reply_markup
    )

async def country_selection_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja la selección de países desde los botones inline"""
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat_id

    if query.data == "cancel_country_selection":
        db.clear_pending_selection(chat_id)
        await query.edit_message_text("❌ Selección de país cancelada.")
        return

    # Extraer índice del país seleccionado
    if not query.data.startswith("select_country_"):
        return

    try:
        country_index = int(query.data.split("_")[-1])
    except ValueError:
        await query.edit_message_text("❌ Error en la selección. Inténtalo de nuevo.")
        return

    # Obtener selección pendiente
    pending_data = db.get_pending_selection(chat_id)
    if not pending_data:
        await query.edit_message_text(
            "❌ No hay selección pendiente. Usa `/addcountry` para buscar un país."
        )
        return

    countries, original_query = pending_data

    if country_index >= len(countries):
        await query.edit_message_text("❌ Selección inválida. Inténtalo de nuevo.")
        return

    selected_country = countries[country_index]

    # Verificar que el usuario esté registrado
    user = db.get_user_by_chat_id(chat_id)
    if not user:
        await query.edit_message_text(
            "❌ Primero debes registrarte con `/adduser <tu_nombre>`"
        )
        return

    # Añadir país
    await query.edit_message_text(
        f"⏳ Añadiendo país {selected_country['name']} ({selected_country['code']})...\n"
        f"Esto puede tardar un momento mientras obtenemos las ciudades..."
    )

    try:
        success = country_state_city.add_user_country(user['id'], selected_country['code'])

        # Limpiar selección pendiente
        db.clear_pending_selection(chat_id)

        if success:
            # Obtener estadísticas
            cities = country_state_city.get_country_cities(selected_country['code'])
            user_countries = country_state_city.get_user_countries(user['id'])

            await query.edit_message_text(
                f"✅ País añadido: {selected_country['name']} ({selected_country['code']})\n"
                f"🏙️ {len(cities)} ciudades cargadas\n"
                f"🌍 Total países configurados: {len(user_countries)}\n\n"
                f"Usa `/mycountries` para ver tu configuración actual."
            )
        else:
            await query.edit_message_text(
                f"❌ Error añadiendo el país {selected_country['name']}.\n"
                f"Es posible que ya lo tengas configurado."
            )
    except Exception as e:
        logger.error(f"Error añadiendo país: {e}")
        await query.edit_message_text(
            "❌ Error al añadir el país. Inténtalo de nuevo más tarde."
        )



async def removecountry_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /removecountry - elimina un país de la configuración del usuario"""
    if not context.args:
        await update.message.reply_text(
            "❌ Uso incorrecto. Debes especificar el código del país.\n"
            "Ejemplo: `/removecountry ES`\n"
            "Usa `/mycountries` para ver tus países configurados"
        )
        return

    if not country_state_city:
        await update.message.reply_text(
            "❌ Servicio de países no disponible."
        )
        return

    chat_id = update.effective_chat.id
    country_code = context.args[0].upper()

    # Verificar que el usuario esté registrado
    user = db.get_user_by_chat_id(chat_id)
    if not user:
        await update.message.reply_text(
            "❌ Primero debes registrarte con `/adduser <tu_nombre>`"
        )
        return

    # Verificar que el usuario tenga más de un país (no puede quedarse sin países)
    user_countries = country_state_city.get_user_countries(user['id'])
    if len(user_countries) <= 1:
        await update.message.reply_text(
            "❌ No puedes eliminar tu último país configurado.\n"
            "Añade otro país primero con `/addcountry`"
        )
        return

    # Eliminar país
    success = country_state_city.remove_user_country(user['id'], country_code)

    if success:
        country_info = country_state_city.get_country_info(country_code)
        country_name = country_info['name'] if country_info else country_code

        remaining_countries = country_state_city.get_user_countries(user['id'])

        await update.message.reply_text(
            f"✅ País eliminado: {country_name} ({country_code})\n"
            f"🌍 Países restantes: {len(remaining_countries)}\n\n"
            f"Usa `/mycountries` para ver tu configuración actual."
        )
    else:
        await update.message.reply_text(
            f"❌ No tenías el país '{country_code}' configurado."
        )

async def mycountries_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /mycountries - muestra países configurados del usuario"""
    if not country_state_city:
        await update.message.reply_text(
            "❌ Servicio de países no disponible."
        )
        return

    chat_id = update.effective_chat.id

    # Verificar que el usuario esté registrado
    user = db.get_user_by_chat_id(chat_id)
    if not user:
        await update.message.reply_text(
            "❌ Primero debes registrarte con `/adduser <tu_nombre>`"
        )
        return

    # Obtener países del usuario
    user_countries = country_state_city.get_user_countries(user['id'])

    if not user_countries:
        await update.message.reply_text(
            "📭 No tienes países configurados.\n"
            "Usa `/addcountry <país>` para añadir países.\n"
            "Ejemplo: `/addcountry ES`"
        )
        return

    # Formatear mensaje
    message_lines = [f"🌍 *Países configurados para {user['username']}:*\n"]

    for i, country in enumerate(user_countries, 1):
        line = f"{i}. *{country['name']}* ({country['code']})"

        details = []
        if country.get('currency'):
            details.append(f"💰 {country['currency']}")
        if country.get('phone_code'):
            details.append(f"📞 +{country['phone_code']}")

        if details:
            line += f" - {' | '.join(details)}"

        message_lines.append(line)

    message_lines.append(f"\n📊 Total: {len(user_countries)} países")
    message_lines.append("\n💡 *Comandos útiles:*")
    message_lines.append("`/addcountry <país>` - Añadir país")
    message_lines.append("`/removecountry <código>` - Eliminar país")
    message_lines.append("`/listcountries` - Ver países disponibles")

    response = "\n".join(message_lines)

    try:
        await update.message.reply_text(
            response,
            parse_mode='Markdown'
        )
    except Exception as e:
        # Si hay error con Markdown, enviar sin formato
        logger.warning(f"Error con Markdown en mycountries, enviando texto plano: {e}")
        plain_response = response.replace('*', '').replace('`', '')
        await update.message.reply_text(plain_response)

async def listcountries_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /listcountries - muestra países disponibles"""
    if not country_state_city:
        await update.message.reply_text(
            "❌ Servicio de países no disponible."
        )
        return

    # Mensaje de estado
    status_message = await update.message.reply_text(
        "🔍 Obteniendo lista de países disponibles..."
    )

    try:
        # Obtener países (usar caché si está disponible)
        countries = country_state_city.get_available_countries()

        if not countries:
            await status_message.edit_text(
                "❌ No se pudieron obtener los países disponibles.\n"
                "Inténtalo de nuevo más tarde."
            )
            return

        # Agrupar países por continente/región (simplificado)
        regions = {
            'Europa': ['AD', 'AL', 'AT', 'BA', 'BE', 'BG', 'BY', 'CH', 'CY', 'CZ', 'DE', 'DK', 'EE', 'ES', 'FI', 'FR', 'GB', 'GR', 'HR', 'HU', 'IE', 'IS', 'IT', 'LI', 'LT', 'LU', 'LV', 'MC', 'MD', 'ME', 'MK', 'MT', 'NL', 'NO', 'PL', 'PT', 'RO', 'RS', 'RU', 'SE', 'SI', 'SK', 'SM', 'UA', 'VA'],
            'América del Norte': ['CA', 'MX', 'US'],
            'América del Sur': ['AR', 'BO', 'BR', 'CL', 'CO', 'EC', 'GY', 'PE', 'PY', 'SR', 'UY', 'VE'],
            'Asia': ['CN', 'IN', 'JP', 'KR', 'TH', 'VN', 'ID', 'MY', 'PH', 'SG', 'TW'],
            'Oceanía': ['AU', 'NZ', 'FJ'],
            'África': ['ZA', 'EG', 'NG', 'KE', 'MA', 'TN']
        }

        # Crear mensaje por regiones
        message_lines = ["🌍 *Países disponibles por región:*\n"]

        countries_by_code = {c.get('iso2', c.get('code', '')): c for c in countries}

        for region_name, region_codes in regions.items():
            region_countries = []
            for code in region_codes:
                if code in countries_by_code:
                    country = countries_by_code[code]
                    region_countries.append(f"{code} - {country.get('name', '')}")

            if region_countries:
                message_lines.append(f"*{region_name}:*")
                # Mostrar solo primeros 10 por región para no sobrecargar
                for country_info in region_countries[:10]:
                    message_lines.append(f"  • {country_info}")
                if len(region_countries) > 10:
                    message_lines.append(f"  _...y {len(region_countries) - 10} más_")
                message_lines.append("")

        message_lines.append(f"📊 Total países disponibles: {len(countries)}")
        message_lines.append("\n💡 *Uso:*")
        message_lines.append("`/addcountry ES` - Añadir por código")
        message_lines.append("`/addcountry Spain` - Añadir por nombre")

        response = "\n".join(message_lines)

        # Dividir en chunks si es muy largo
        if len(response) > 4000:
            chunks = split_long_message(response, max_length=4000)

            # Editar el primer chunk
            await status_message.edit_text(
                chunks[0],
                parse_mode='Markdown'
            )

            # Enviar chunks adicionales
            for chunk in chunks[1:]:
                await update.message.reply_text(
                    chunk,
                    parse_mode='Markdown'
                )
        else:
            await status_message.edit_text(
                response,
                parse_mode='Markdown'
            )

    except Exception as e:
        logger.error(f"Error en comando listcountries: {e}")
        await status_message.edit_text(
            "❌ Error al obtener la lista de países. Inténtalo de nuevo más tarde."
        )


async def refreshcountries_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /refreshcountries - actualiza la base de datos de países (solo admins)"""
    if not country_state_city:
        await update.message.reply_text(
            "❌ Servicio de países no disponible."
        )
        return

    chat_id = update.effective_chat.id

    # Verificar que el usuario esté registrado
    user = db.get_user_by_chat_id(chat_id)
    if not user:
        await update.message.reply_text(
            "❌ Primero debes registrarte con `/adduser <tu_nombre>`"
        )
        return

    # Mensaje de estado
    status_message = await update.message.reply_text(
        "🔄 Actualizando base de datos de países desde API...\n"
        "Esto puede tardar un momento..."
    )

    try:
        # Forzar actualización desde API
        countries = country_state_city.get_available_countries(force_refresh=True)

        if countries:
            await status_message.edit_text(
                f"✅ Base de datos actualizada correctamente.\n"
                f"📊 {len(countries)} países disponibles.\n\n"
                f"Usa `/listcountries` para ver la lista actualizada."
            )
        else:
            await status_message.edit_text(
                "❌ No se pudieron actualizar los países.\n"
                "Verifica la conexión y la API key."
            )

    except Exception as e:
        logger.error(f"Error en comando refreshcountries: {e}")
        await status_message.edit_text(
            "❌ Error al actualizar países. Inténtalo de nuevo más tarde."
        )

def get_user_services_extended(user_id: int) -> Dict[str, any]:
    """
    Versión extendida que incluye países múltiples

    Returns:
        Dict con servicios y países del usuario
    """
    # Obtener configuración original
    original_services = db.get_user_services(user_id)

    # Añadir información de países
    if country_state_city:
        user_countries = country_state_city.get_user_country_codes(user_id)
        original_services['countries'] = user_countries
        original_services['country_filter'] = list(user_countries)[0] if user_countries else 'ES'  # Compatibilidad
    else:
        original_services['countries'] = {original_services.get('country_filter', 'ES')}

    return original_services

async def search_concerts_for_artist(artist_name: str, user_services: Dict[str, any] = None, user_id: int = None) -> List[Dict]:
    """
    Busca conciertos para un artista usando los servicios habilitados
    VERSIÓN MODIFICADA: Ticketmaster busca globalmente y luego filtra
    """
    if user_services is None:
        user_services = {
            'ticketmaster': True,
            'spotify': True,
            'setlistfm': True,
            'country_filter': 'ES',
            'countries': {'ES'}
        }

    all_concerts = []
    user_countries = user_services.get('countries', {'ES'})

    # Buscar en Ticketmaster si está habilitado - BÚSQUEDA GLOBAL
    if user_services.get('ticketmaster', True) and ticketmaster_service:
        try:
            # Usar búsqueda global en lugar de por país
            concerts, _ = ticketmaster_service.search_concerts_global(artist_name)
            all_concerts.extend(concerts)

            logger.info(f"Ticketmaster global: {len([c for c in concerts if c.get('source') == 'Ticketmaster'])} conciertos encontrados para {artist_name}")
        except Exception as e:
            logger.error(f"Error buscando en Ticketmaster: {e}")

    # Buscar en Spotify si está habilitado (sin cambios)
    if user_services.get('spotify', True) and spotify_service:
        try:
            concerts, _ = spotify_service.search_artist_and_concerts(artist_name)
            all_concerts.extend(concerts)
            logger.info(f"Spotify: {len([c for c in all_concerts if c.get('source') == 'Spotify'])} conciertos encontrados para {artist_name}")
        except Exception as e:
            logger.error(f"Error buscando en Spotify: {e}")

    # Buscar en Setlist.fm si está habilitado - MANTENER POR PAÍS
    if user_services.get('setlistfm', True) and setlistfm_service:
        try:
            # Setlist.fm mantiene búsqueda por país ya que es más específico
            for country_code in user_countries:
                concerts, _ = setlistfm_service.search_concerts(artist_name, country_code)
                all_concerts.extend(concerts)

            logger.info(f"Setlist.fm: {len([c for c in all_concerts if c.get('source') == 'Setlist.fm'])} conciertos encontrados para {artist_name}")
        except Exception as e:
            logger.error(f"Error buscando en Setlist.fm: {e}")

    # Filtrar conciertos por países del usuario si el servicio está disponible
    if country_city_service and user_id:
        try:
            extended_db = ArtistTrackerDatabaseExtended(db.db_path, country_city_service)
            filtered_concerts = extended_db.filter_concerts_by_countries(all_concerts, user_countries)

            logger.info(f"Conciertos filtrados para {artist_name}: {len(all_concerts)} -> {len(filtered_concerts)} (países: {user_countries})")
            return filtered_concerts
        except Exception as e:
            logger.error(f"Error filtrando conciertos: {e}")
            # Si falla el filtrado, hacer filtrado básico por país
            filtered_concerts = []
            for concert in all_concerts:
                concert_country = concert.get('country', '').upper()
                if not concert_country or concert_country in user_countries:
                    filtered_concerts.append(concert)

            logger.info(f"Filtrado básico aplicado: {len(all_concerts)} -> {len(filtered_concerts)}")
            return filtered_concerts

    return all_concerts


async def search_concerts_for_artist(artist_name: str, user_services: Dict[str, any] = None, user_id: int = None) -> List[Dict]:
    """
    Busca conciertos para un artista usando los servicios habilitados
    VERSIÓN EXTENDIDA con filtrado por países múltiples

    Args:
        artist_name: Nombre del artista
        user_services: Configuración de servicios del usuario
        user_id: ID del usuario (para filtrado por países)

    Returns:
        Lista de conciertos encontrados y filtrados
    """
    if user_services is None:
        # Configuración por defecto si no se proporciona
        user_services = {
            'ticketmaster': True,
            'spotify': True,
            'setlistfm': True,
            'country_filter': 'ES',
            'countries': {'ES'}
        }

    all_concerts = []

    # Obtener países del usuario
    user_countries = user_services.get('countries', {'ES'})
    primary_country = user_services.get('country_filter', 'ES')

    # Buscar en Ticketmaster si está habilitado
    if user_services.get('ticketmaster', True) and ticketmaster_service:
        try:
            # Buscar en cada país del usuario
            for country_code in user_countries:
                concerts, _ = ticketmaster_service.search_concerts(artist_name, country_code)
                all_concerts.extend(concerts)

            logger.info(f"Ticketmaster: {len([c for c in all_concerts if c.get('source') == 'Ticketmaster'])} conciertos encontrados para {artist_name}")
        except Exception as e:
            logger.error(f"Error buscando en Ticketmaster: {e}")

    # Buscar en Spotify si está habilitado
    if user_services.get('spotify', True) and spotify_service:
        try:
            concerts, _ = spotify_service.search_artist_and_concerts(artist_name)
            all_concerts.extend(concerts)
            logger.info(f"Spotify: {len([c for c in all_concerts if c.get('source') == 'Spotify'])} conciertos encontrados para {artist_name}")
        except Exception as e:
            logger.error(f"Error buscando en Spotify: {e}")

    # Buscar en Setlist.fm si está habilitado
    if user_services.get('setlistfm', True) and setlistfm_service:
        try:
            # Buscar en cada país del usuario
            for country_code in user_countries:
                concerts, _ = setlistfm_service.search_concerts(artist_name, country_code)
                all_concerts.extend(concerts)

            logger.info(f"Setlist.fm: {len([c for c in all_concerts if c.get('source') == 'Setlist.fm'])} conciertos encontrados para {artist_name}")
        except Exception as e:
            logger.error(f"Error buscando en Setlist.fm: {e}")

    # Filtrar conciertos por países del usuario si el servicio está disponible
    if country_state_city and user_id:
        try:
            extended_db = ArtistTrackerDatabaseExtended(db.db_path, country_state_city)
            filtered_concerts = extended_db.filter_concerts_by_countries(all_concerts, user_countries)

            logger.info(f"Conciertos filtrados para {artist_name}: {len(all_concerts)} -> {len(filtered_concerts)} (países: {user_countries})")
            return filtered_concerts
        except Exception as e:
            logger.error(f"Error filtrando conciertos: {e}")
            return all_concerts

    return all_concerts


async def update_concerts_database():
    """
    Actualiza la base de datos con nuevos conciertos
    VERSIÓN MODIFICADA: Guarda todos los conciertos globalmente
    """
    logger.info("Actualizando base de datos de conciertos...")

    # Obtener todos los artistas únicos de la base de datos
    conn = db.get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT DISTINCT name FROM artists")
        artists = [row[0] for row in cursor.fetchall()]

        total_new_concerts = 0
        total_all_concerts = 0

        for artist_name in artists:
            logger.info(f"Buscando conciertos globalmente para {artist_name}")

            # Buscar con configuración global (todos los servicios activos)
            global_services = {
                'ticketmaster': True,
                'spotify': True,
                'setlistfm': True,
                'countries': {'ES', 'US', 'FR', 'DE', 'IT', 'GB'}  # Países principales para Setlist.fm
            }

            concerts = await search_concerts_for_artist(artist_name, global_services)
            total_all_concerts += len(concerts)

            # Guardar TODOS los conciertos encontrados
            for concert in concerts:
                concert_id = db.save_concert(concert)
                if concert_id:
                    total_new_concerts += 1

            # Pausa para no sobrecargar las APIs
            await asyncio.sleep(1)

        logger.info(f"Actualización completada: {total_new_concerts} nuevos conciertos de {total_all_concerts} encontrados")

    except Exception as e:
        logger.error(f"Error actualizando base de datos de conciertos: {e}")
    finally:
        conn.close()




def format_concerts_message(concerts: List[Dict], title: str = "🎵 Conciertos encontrados", show_notified: bool = False, show_expand_buttons: bool = False, user_id: int = None) -> Tuple[str, Optional[InlineKeyboardMarkup]]:
    """
    Formatea una lista de conciertos para mostrar en Telegram
    MANTIENE LA FUNCIONALIDAD ORIGINAL pero con opción de botones
    """
    if not concerts:
        return f"{title}\n\n❌ No se encontraron conciertos.", None

    message_lines = [f"{title}\n"]

    # Agrupar por artista
    concerts_by_artist = {}
    for concert in concerts:
        artist = concert.get('artist_name', 'Artista desconocido')
        if artist not in concerts_by_artist:
            concerts_by_artist[artist] = []
        concerts_by_artist[artist].append(concert)

    # Mostrar conciertos como antes (formato original)
    for artist, artist_concerts in concerts_by_artist.items():
        # Escapar caracteres especiales
        safe_artist = artist.replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")
        message_lines.append(f"*{safe_artist}*:")

        for concert in artist_concerts[:5]:  # Limitar a 5 por artista como antes
            venue = concert.get('venue', 'Lugar desconocido')
            city = concert.get('city', '')
            date = concert.get('date', 'Fecha desconocida')
            url = concert.get('url', '')
            source = concert.get('source', '')

            # Formatear fecha
            if date and len(date) >= 10 and '-' in date:
                try:
                    date_obj = datetime.strptime(date[:10], '%Y-%m-%d')
                    date = date_obj.strftime('%d/%m/%Y')
                except ValueError:
                    pass

            # Escapar caracteres especiales
            safe_venue = str(venue).replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")
            safe_city = str(city).replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")

            location = f"{safe_venue}, {safe_city}" if safe_city else safe_venue

            concert_line = f"• {date}: "

            if url and url.startswith(('http://', 'https://')):
                url = url.replace(")", "\\)")
                concert_line += f"[{location}]({url})"
            else:
                concert_line += location

            if source:
                concert_line += f" _{source}_"

            if show_notified and concert.get('notified'):
                concert_line += " ✅"

            message_lines.append(concert_line)

        if len(artist_concerts) > 5:
            remaining = len(artist_concerts) - 5
            message_lines.append(f"_...y {remaining} más_")

        message_lines.append("")

    message_lines.append(f"📊 Total: {len(concerts)} conciertos")

    # Crear botones solo si se solicita Y hay más de 5 conciertos por artista
    keyboard = None
    if show_expand_buttons and user_id:
        buttons = []

        # Botón para expandir todos los conciertos
        buttons.append([InlineKeyboardButton("📋 Ver todos los conciertos", callback_data=f"expand_all_{user_id}")])

        # Botones para artistas con más de 5 conciertos
        for artist, artist_concerts in concerts_by_artist.items():
            if len(artist_concerts) > 5:
                button_text = f"🎵 Ver todos los de {artist}"
                if len(button_text) > 35:
                    button_text = f"🎵 {artist}"
                    if len(button_text) > 35:
                        button_text = button_text[:32] + "..."

                # Usar el mismo sistema de callback que ya existe
                buttons.append([InlineKeyboardButton(button_text, callback_data=f"expand_artist_{artist}_{user_id}")])

        if len(buttons) > 1:  # Solo crear teclado si hay más que el botón "ver todos"
            keyboard = InlineKeyboardMarkup(buttons)

    return "\n".join(message_lines), keyboard





async def back_to_summary_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el botón de volver al resumen"""
    query = update.callback_query
    await query.answer()

    try:
        # Parsear el callback data: back_to_summary_USERID
        user_id = int(query.data.split("_")[-1])

        # Obtener datos del caché o regenerar
        cache_data = get_user_search_cache(user_id)
        if not cache_data:
            await query.edit_message_text(
                "❌ La búsqueda ha expirado. Usa `/search` para buscar de nuevo."
            )
            return

        search_type, concerts = cache_data

        # Determinar el título basado en el tipo de búsqueda
        if search_type == "user_concerts":
            title = "🎵 Conciertos de tus artistas seguidos"
            show_notified = True
        else:
            # Extraer nombre del artista del tipo de búsqueda
            artist_name = search_type.replace("artist_search_", "")
            title = f"🎵 Conciertos de {artist_name}"
            show_notified = False

        # Volver al formato resumido
        message, keyboard = format_concerts_message(
            concerts,
            title,
            show_notified=show_notified,
            show_expand_buttons=True,
            user_id=user_id
        )

        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            disable_web_page_preview=True,
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Error en back_to_summary_callback: {e}")
        await query.edit_message_text(
            "❌ Error al volver al resumen. Usa `/search` para buscar de nuevo."
        )

def save_user_search_cache(user_id: int, search_type: str, data: List[Dict]):
    """Guarda datos de búsqueda en caché temporal"""
    conn = db.get_connection()
    cursor = conn.cursor()

    try:
        # Limpiar caché anterior del usuario
        cursor.execute("DELETE FROM user_search_cache WHERE user_id = ?", (user_id,))

        # Guardar nuevos datos
        cursor.execute("""
            INSERT INTO user_search_cache (user_id, search_type, search_data)
            VALUES (?, ?, ?)
        """, (user_id, search_type, json.dumps(data)))

        conn.commit()
        logger.info(f"Caché guardado para usuario {user_id}: {search_type}")

    except sqlite3.Error as e:
        logger.error(f"Error guardando caché: {e}")
    finally:
        conn.close()



def get_user_search_cache(user_id: int) -> Optional[Tuple[str, List[Dict]]]:
    """Obtiene datos de búsqueda del caché"""
    conn = db.get_connection()
    cursor = conn.cursor()

    try:
        # Limpiar caché antiguo (más de 1 hora)
        cursor.execute("""
            DELETE FROM user_search_cache
            WHERE created_at < datetime('now', '-1 hour')
        """)

        # Obtener datos del usuario
        cursor.execute("""
            SELECT search_type, search_data
            FROM user_search_cache
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (user_id,))

        row = cursor.fetchone()
        if row:
            search_type = row[0]
            data = json.loads(row[1])
            return search_type, data

        return None

    except (sqlite3.Error, json.JSONDecodeError) as e:
        logger.error(f"Error obteniendo caché: {e}")
        return None
    finally:
        conn.close()



def format_artist_concerts_detailed(concerts: List[Dict], artist_name: str, show_notified: bool = False) -> str:
    """
    Formatea los conciertos de un artista específico con todos los detalles

    Args:
        concerts: Lista de conciertos del artista
        artist_name: Nombre del artista
        show_notified: Si mostrar el estado de notificación

    Returns:
        Mensaje formateado con todos los conciertos
    """
    if not concerts:
        return f"🎵 Conciertos de {artist_name}\n\n❌ No se encontraron conciertos."

    # Escapar caracteres especiales del nombre del artista
    safe_artist = artist_name.replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")

    message_lines = [f"🎵 *Todos los conciertos de {safe_artist}*\n"]

    # Ordenar conciertos por fecha (más recientes primero)
    sorted_concerts = sorted(concerts, key=lambda x: x.get('date', ''), reverse=True)

    for i, concert in enumerate(sorted_concerts, 1):
        venue = concert.get('venue', 'Lugar desconocido')
        city = concert.get('city', '')
        date = concert.get('date', 'Fecha desconocida')
        time = concert.get('time', '')
        url = concert.get('url', '')
        source = concert.get('source', '')

        # Formatear fecha
        formatted_date = date
        if date and len(date) >= 10 and '-' in date:
            try:
                date_obj = datetime.strptime(date[:10], '%Y-%m-%d')
                formatted_date = date_obj.strftime('%d/%m/%Y')
            except ValueError:
                pass

        # Escapar caracteres especiales
        safe_venue = str(venue).replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")
        safe_city = str(city).replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")

        # Construir línea del concierto
        concert_line = f"*{i}.* {formatted_date}"

        if time:
            concert_line += f" a las {time}"

        concert_line += "\n"

        # Ubicación con enlace si está disponible
        location = f"{safe_venue}"
        if safe_city:
            location += f", {safe_city}"

        if url and url.startswith(('http://', 'https://')):
            # Escapar paréntesis en URL
            escaped_url = url.replace(")", "\\)")
            concert_line += f"   📍 [{location}]({escaped_url})"
        else:
            concert_line += f"   📍 {location}"

        # Información adicional
        if source:
            concert_line += f"\n   🔗 _{source}_"

        # Estado de notificación
        if show_notified:
            if concert.get('notified'):
                concert_line += " ✅"
            else:
                concert_line += " 🔔"

        message_lines.append(concert_line)
        message_lines.append("")  # Línea en blanco entre conciertos

    # Estadísticas finales
    total_concerts = len(concerts)
    message_lines.append(f"📊 *Total: {total_concerts} conciertos de {safe_artist}*")

    if show_notified:
        notified_count = sum(1 for c in concerts if c.get('notified'))
        pending_count = total_concerts - notified_count
        message_lines.append(f"✅ Notificados: {notified_count}")
        message_lines.append(f"🔔 Pendientes: {pending_count}")

    return "\n".join(message_lines)



async def show_artist_concerts_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja la selección de mostrar conciertos de un artista desde botones inline"""
    query = update.callback_query
    await query.answer()

    try:
        # Parsear el callback data: show_artist_concerts_ARTISTNAME_USERID
        parts = query.data.split("_")
        if not query.data.startswith("show_artist_concerts_"):
            return

        user_id = int(parts[-1])  # Último elemento es el user_id
        encoded_artist = "_".join(parts[3:-1])  # Todo entre "show_artist_concerts" y user_id

        # Decodificar el nombre del artista
        artist_name = encoded_artist.replace("__", "-").replace("_", " ")

        # Obtener todos los conciertos del usuario
        all_concerts = db.get_all_concerts_for_user(user_id)

        # Filtrar conciertos del artista específico
        artist_concerts = [c for c in all_concerts if c.get('artist_name', '').lower() == artist_name.lower()]

        if not artist_concerts:
            await query.edit_message_text(
                f"❌ No se encontraron conciertos para {artist_name}"
            )
            return

        # Formatear mensaje detallado
        message = format_artist_concerts_detailed(artist_concerts, artist_name, show_notified=True)

        # Botón para volver
        keyboard = [[
            InlineKeyboardButton("🔙 Volver al resumen", callback_data=f"back_to_summary_{user_id}")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Dividir en chunks si es muy largo
        if len(message) > 4000:
            chunks = split_long_message(message)

            # Editar mensaje original con el primer chunk
            await query.edit_message_text(
                chunks[0],
                parse_mode='Markdown',
                disable_web_page_preview=True,
                reply_markup=reply_markup
            )

            # Enviar chunks adicionales
            for chunk in chunks[1:]:
                await query.message.reply_text(
                    chunk,
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
        else:
            await query.edit_message_text(
                message,
                parse_mode='Markdown',
                disable_web_page_preview=True,
                reply_markup=reply_markup
            )

    except Exception as e:
        logger.error(f"Error en show_artist_concerts_callback: {e}")
        await query.edit_message_text(
            "❌ Error al mostrar conciertos del artista. Inténtalo de nuevo."
        )



async def showartist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /showartist - muestra todos los conciertos de un artista específico"""
    if not context.args:
        await update.message.reply_text(
            "❌ Uso incorrecto. Debes especificar el nombre del artista.\n"
            "Ejemplo: `/showartist Radiohead`"
        )
        return

    artist_name = " ".join(context.args)
    chat_id = update.effective_chat.id

    # Verificar que el usuario esté registrado
    user = db.get_user_by_chat_id(chat_id)
    if not user:
        await update.message.reply_text(
            "❌ Primero debes registrarte con `/adduser <tu_nombre>`"
        )
        return

    # Obtener todos los conciertos del usuario
    all_concerts = db.get_all_concerts_for_user(user['id'])

    # Filtrar conciertos del artista específico (búsqueda case-insensitive)
    artist_concerts = [c for c in all_concerts if c.get('artist_name', '').lower() == artist_name.lower()]

    if not artist_concerts:
        await update.message.reply_text(
            f"📭 No se encontraron conciertos para '{artist_name}'.\n"
            "Verifica que esté en tu lista de artistas seguidos con `/list`"
        )
        return

    # Usar el formato original pero mostrando TODOS los conciertos del artista
    message = format_single_artist_concerts(artist_concerts, artist_name, show_notified=True)

    # Dividir en chunks si es muy largo
    if len(message) > 4000:
        chunks = split_long_message(message)

        # Enviar el primer chunk
        await update.message.reply_text(
            chunks[0],
            parse_mode='Markdown',
            disable_web_page_preview=True
        )

        # Enviar chunks adicionales
        for chunk in chunks[1:]:
            await update.message.reply_text(
                chunk,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
    else:
        await update.message.reply_text(
            message,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )

def format_single_artist_concerts(concerts: List[Dict], artist_name: str, show_notified: bool = False) -> str:
    """
    Formatea los conciertos de un solo artista usando el formato original
    """
    if not concerts:
        return f"🎵 Conciertos de {artist_name}\n\n❌ No se encontraron conciertos."

    # Escapar caracteres especiales del nombre del artista
    safe_artist = artist_name.replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")

    message_lines = [f"🎵 Conciertos de {safe_artist}\n"]
    message_lines.append(f"*{safe_artist}*:")

    # Ordenar conciertos por fecha (más recientes primero)
    sorted_concerts = sorted(concerts, key=lambda x: x.get('date', ''), reverse=True)

    for concert in sorted_concerts:  # Mostrar TODOS los conciertos
        venue = concert.get('venue', 'Lugar desconocido')
        city = concert.get('city', '')
        date = concert.get('date', 'Fecha desconocida')
        url = concert.get('url', '')
        source = concert.get('source', '')

        # Formatear fecha
        if date and len(date) >= 10 and '-' in date:
            try:
                date_obj = datetime.strptime(date[:10], '%Y-%m-%d')
                date = date_obj.strftime('%d/%m/%Y')
            except ValueError:
                pass

        # Escapar caracteres especiales
        safe_venue = str(venue).replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")
        safe_city = str(city).replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")

        location = f"{safe_venue}, {safe_city}" if safe_city else safe_venue

        concert_line = f"• {date}: "

        if url and url.startswith(('http://', 'https://')):
            url = url.replace(")", "\\)")
            concert_line += f"[{location}]({url})"
        else:
            concert_line += location

        if source:
            concert_line += f" _{source}_"

        if show_notified and concert.get('notified'):
            concert_line += " ✅"

        message_lines.append(concert_line)

    message_lines.append("")
    message_lines.append(f"📊 Total: {len(concerts)} conciertos de {safe_artist}")

    if show_notified:
        notified_count = sum(1 for c in concerts if c.get('notified'))
        pending_count = len(concerts) - notified_count
        message_lines.append(f"✅ Notificados: {notified_count} | 🔔 Pendientes: {pending_count}")

    return "\n".join(message_lines)




# Funciones de comando
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start MODIFICADO con nuevos comandos de países"""
    help_text = (
        "¡Bienvenido al Bot de Seguimiento de Artistas! 🎵\n\n"
        "📝 *Comandos básicos:*\n"
        "/adduser <usuario> - Registrarte en el sistema\n"
        "/addartist <artista> - Seguir un artista\n"
        "/list [usuario] - Ver artistas seguidos\n"
        "/remove <artista> - Dejar de seguir un artista\n\n"
        "🔍 *Comandos de búsqueda:*\n"
        "/search - Ver conciertos de tus artistas\n"
        "/searchartist <artista> - Buscar conciertos específicos\n"
        "/showartist <artista> - Ver todos los conciertos de un artista\n\n"
        "/lastfm - Sincronizar artistas desde Last.fm\n\n"
    )

    if country_state_city:
        help_text += (
            "🌍 *Gestión de países:*\n"
            "/addcountry <país> - Añadir país a tu configuración\n"
            "/removecountry <código> - Eliminar país\n"
            "/mycountries - Ver tus países configurados\n"
            "/listcountries - Ver países disponibles\n\n"
        )
    else:
        help_text += (
            "🌍 *Configuración de país:*\n"
            "/country <código> - Establecer filtro de país (ej: ES, US, FR)\n\n"
        )

    help_text += (
        "⚙️ *Configuración:*\n"
        "/notify [HH:MM] - Configurar notificaciones diarias\n"
        "/serviceon <servicio> - Activar servicio (ticketmaster/spotify/setlistfm)\n"
        "/serviceoff <servicio> - Desactivar servicio\n"
        "/config - Ver tu configuración actual\n"
        "/help - Mostrar este mensaje de ayuda"
    )

    await update.message.reply_text(help_text, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help"""
    await start(update, context)

async def adduser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /adduser"""
    if not context.args:
        await update.message.reply_text(
            "❌ Uso incorrecto. Debes especificar un nombre de usuario.\n"
            "Ejemplo: `/adduser tu_nombre`"
        )
        return

    username = context.args[0]
    chat_id = update.effective_chat.id

    # Validar nombre de usuario
    if len(username) < 2 or len(username) > 50:
        await update.message.reply_text(
            "❌ El nombre de usuario debe tener entre 2 y 50 caracteres."
        )
        return

    if db.add_user(username, chat_id):
        await update.message.reply_text(
            f"✅ Usuario '{username}' registrado correctamente.\n"
            f"Ya puedes usar `/addartist` para seguir artistas."
        )
    else:
        await update.message.reply_text(
            "❌ Error al registrar el usuario. Inténtalo de nuevo."
        )

async def addartist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /addartist mejorado con selección múltiple"""
    if not context.args:
        await update.message.reply_text(
            "❌ Uso incorrecto. Debes especificar el nombre del artista.\n"
            "Ejemplo: `/addartist Radiohead`"
        )
        return

    artist_name = " ".join(context.args)
    chat_id = update.effective_chat.id

    # Verificar que el usuario esté registrado
    user = db.get_user_by_chat_id(chat_id)
    if not user:
        await update.message.reply_text(
            "❌ Primero debes registrarte con `/adduser <tu_nombre>`"
        )
        return

    # Mensaje de estado
    status_message = await update.message.reply_text(
        f"🔍 Buscando artistas que coincidan con '{artist_name}'..."
    )

    # Buscar candidatos
    candidates = db.search_artist_candidates(artist_name)

    if not candidates:
        await status_message.edit_text(
            f"❌ No se encontraron artistas que coincidan con '{artist_name}'.\n"
            f"Verifica la ortografía e inténtalo de nuevo."
        )
        return

    logger.info(f"Encontrados {len(candidates)} candidatos para '{artist_name}'")
    for i, candidate in enumerate(candidates):
        logger.info(f"  {i+1}. {candidate['name']} - Score: {candidate['score']}")

    # Si solo hay un candidato con score alto, añadirlo directamente
    if len(candidates) == 1:
        # Solo un candidato, añadirlo directamente
        artist_id = db.create_artist_from_candidate(candidates[0])

        if not artist_id:
            await status_message.edit_text(
                f"❌ Error al añadir el artista '{artist_name}'. Inténtalo de nuevo."
            )
            return

        was_new = db.add_followed_artist(user['id'], artist_id)

        if was_new:
            await status_message.edit_text(
                f"✅ ¡Ahora sigues a '{candidates[0]['name']}'! 🎵\n"
                f"Usa `/list` para ver todos tus artistas seguidos."
            )
        else:
            await status_message.edit_text(
                f"ℹ️ Ya seguías a '{candidates[0]['name']}'."
            )
        return

    # Múltiples candidatos: verificar si hay un candidato claramente mejor
    best_candidate = candidates[0]
    second_best = candidates[1] if len(candidates) > 1 else None

    # Si el mejor candidato tiene score muy alto y hay una diferencia significativa
    if (best_candidate['score'] >= 95 and
        (second_best is None or best_candidate['score'] - second_best['score'] >= 20)):

        artist_id = db.create_artist_from_candidate(best_candidate)

        if not artist_id:
            await status_message.edit_text(
                f"❌ Error al añadir el artista '{artist_name}'. Inténtalo de nuevo."
            )
            return

        was_new = db.add_followed_artist(user['id'], artist_id)

        if was_new:
            await status_message.edit_text(
                f"✅ ¡Ahora sigues a '{best_candidate['name']}'! 🎵\n"
                f"(Seleccionado automáticamente por alta coincidencia: {best_candidate['score']}%)\n"
                f"Usa `/list` para ver todos tus artistas seguidos."
            )
        else:
            await status_message.edit_text(
                f"ℹ️ Ya seguías a '{best_candidate['name']}'."
            )
        return

    # Múltiples candidatos: mostrar opciones
    await show_artist_candidates(update, candidates, artist_name, status_message)

async def show_artist_candidates(update: Update, candidates: List[Dict], original_query: str, message_to_edit):
    """Muestra una lista de candidatos para que el usuario elija"""
    chat_id = update.effective_chat.id

    # Guardar candidatos para posterior selección
    db.save_pending_selection(chat_id, candidates, original_query)

    # Crear mensaje con opciones
    message_lines = [f"🎵 *Encontré varios artistas para '{original_query}':*\n"]

    keyboard = []
    for i, candidate in enumerate(candidates[:8]):  # Limitar a 8 opciones
        # Formatear información del candidato
        info_parts = []
        if candidate.get('type'):
            info_parts.append(candidate['type'].title())
        if candidate.get('country'):
            info_parts.append(f"🌍 {candidate['country']}")
        if candidate.get('formed_year'):
            info_parts.append(f"📅 {candidate['formed_year']}")
        if candidate.get('disambiguation'):
            info_parts.append(f"({candidate['disambiguation']})")

        info_text = " • ".join(info_parts) if info_parts else ""

        option_text = f"{i+1}. *{candidate['name']}*"
        if info_text:
            option_text += f"\n   _{info_text}_"

        message_lines.append(option_text)

        # Botón para esta opción
        button_text = f"{i+1}. {candidate['name']}"
        if len(button_text) > 30:
            button_text = button_text[:27] + "..."

        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"select_artist_{i}")])

    # Botón de cancelar
    keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancel_artist_selection")])

    message_lines.append("\n*Selecciona el artista correcto:*")

    reply_markup = InlineKeyboardMarkup(keyboard)

    # Escapar caracteres especiales para Markdown
    response = "\n".join(message_lines)
    for char in ['_', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
        if char not in ['*', '_']:  # No escapar asteriscos y guiones bajos que usamos para formato
            response = response.replace(char, f'\\{char}')

    await message_to_edit.edit_text(
        response,
        parse_mode='MarkdownV2',
        reply_markup=reply_markup
    )

async def artist_selection_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja la selección de artistas desde los botones inline"""
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat_id

    if query.data == "cancel_artist_selection":
        db.clear_pending_selection(chat_id)
        await query.edit_message_text("❌ Selección de artista cancelada.")
        return

    # Extraer índice del artista seleccionado
    if not query.data.startswith("select_artist_"):
        return

    try:
        artist_index = int(query.data.split("_")[-1])
    except ValueError:
        await query.edit_message_text("❌ Error en la selección. Inténtalo de nuevo.")
        return

    # Obtener selección pendiente
    pending_data = db.get_pending_selection(chat_id)
    if not pending_data:
        await query.edit_message_text(
            "❌ No hay selección pendiente. Usa `/addartist` para buscar un artista."
        )
        return

    candidates, original_query = pending_data

    if artist_index >= len(candidates):
        await query.edit_message_text("❌ Selección inválida. Inténtalo de nuevo.")
        return

    selected_candidate = candidates[artist_index]

    # Verificar que el usuario esté registrado
    user = db.get_user_by_chat_id(chat_id)
    if not user:
        await query.edit_message_text(
            "❌ Primero debes registrarte con `/adduser <tu_nombre>`"
        )
        return

    # Crear el artista y añadirlo a seguimiento
    await query.edit_message_text(f"⏳ Añadiendo '{selected_candidate['name']}'...")

    artist_id = db.create_artist_from_candidate(selected_candidate)

    if not artist_id:
        await query.edit_message_text(
            f"❌ Error al añadir el artista '{selected_candidate['name']}'. Inténtalo de nuevo."
        )
        return

    was_new = db.add_followed_artist(user['id'], artist_id)

    # Limpiar selección pendiente
    db.clear_pending_selection(chat_id)

    if was_new:
        await query.edit_message_text(
            f"✅ ¡Ahora sigues a '{selected_candidate['name']}'! 🎵\n"
            f"Usa `/list` para ver todos tus artistas seguidos."
        )
    else:
        await query.edit_message_text(
            f"ℹ️ Ya seguías a '{selected_candidate['name']}'."
        )

def escape_markdown_v2(text):
    """Escapa caracteres especiales para MarkdownV2"""
    # Caracteres que necesitan escape en MarkdownV2
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']

    if not text:
        return ""

    for char in escape_chars:
        text = text.replace(char, f'\\{char}')

    return text

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /list mejorado con enlaces de MusicBrainz"""
    chat_id = update.effective_chat.id

    # Determinar qué usuario consultar
    if context.args:
        # Consultar otro usuario
        target_username = context.args[0]
        target_user = db.get_user_by_username(target_username)

        if not target_user:
            await update.message.reply_text(
                f"❌ Usuario '{target_username}' no encontrado."
            )
            return

        user_id = target_user['id']
        display_name = target_username
    else:
        # Consultar usuario actual
        current_user = db.get_user_by_chat_id(chat_id)
        if not current_user:
            await update.message.reply_text(
                "❌ Primero debes registrarte con `/adduser <tu_nombre>`"
            )
            return

        user_id = current_user['id']
        display_name = "tú"

    # Obtener artistas seguidos
    followed_artists = db.get_user_followed_artists(user_id)

    if not followed_artists:
        pronoun = "no tienes" if display_name == "tú" else "no tiene"
        await update.message.reply_text(
            f"📭 {display_name.capitalize()} {pronoun} artistas seguidos aún.\n"
            f"Usa `/addartist <nombre>` para empezar a seguir artistas."
        )
        return

    # Formatear la lista usando Markdown normal en lugar de MarkdownV2
    message_lines = [f"🎵 *Artistas seguidos por {display_name}:*\n"]

    for i, artist in enumerate(followed_artists, 1):
        # Nombre del artista
        artist_name = artist['name']

        # Crear línea con enlace si está disponible
        if artist['musicbrainz_url']:
            line = f"{i}. [{artist_name}]({artist['musicbrainz_url']})"
        else:
            line = f"{i}. *{artist_name}*"

        # Añadir información adicional si está disponible
        details = []
        if artist['country']:
            details.append(f"🌍 {artist['country']}")
        if artist['formed_year']:
            details.append(f"📅 {artist['formed_year']}")
        if artist['total_works'] and artist['total_works'] > 0:
            details.append(f"📝 {artist['total_works']} obras")
        if artist['artist_type']:
            details.append(f"🎭 {artist['artist_type'].title()}")

        if details:
            line += f" ({', '.join(details)})"

        message_lines.append(line)

    message_lines.append(f"\n📊 Total: {len(followed_artists)} artistas")

    # Unir mensaje
    response = "\n".join(message_lines)

    try:
        await update.message.reply_text(
            response,
            parse_mode='Markdown',  # Usar Markdown normal en lugar de MarkdownV2
            disable_web_page_preview=True
        )
    except Exception as e:
        # Si hay error con Markdown, enviar sin formato
        logger.warning(f"Error con Markdown, enviando texto plano: {e}")
        # Crear versión sin formato
        plain_lines = []
        for i, artist in enumerate(followed_artists, 1):
            line = f"{i}. {artist['name']}"

            details = []
            if artist['country']:
                details.append(f"🌍 {artist['country']}")
            if artist['formed_year']:
                details.append(f"📅 {artist['formed_year']}")
            if artist['total_works'] and artist['total_works'] > 0:
                details.append(f"📝 {artist['total_works']} obras")
            if artist['artist_type']:
                details.append(f"🎭 {artist['artist_type'].title()}")

            if details:
                line += f" ({', '.join(details)})"

            if artist['musicbrainz_url']:
                line += f"\n   🔗 {artist['musicbrainz_url']}"

            plain_lines.append(line)

        plain_response = f"🎵 Artistas seguidos por {display_name}:\n\n" + "\n\n".join(plain_lines) + f"\n\n📊 Total: {len(followed_artists)} artistas"
        await update.message.reply_text(plain_response)

async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /remove"""
    if not context.args:
        await update.message.reply_text(
            "❌ Uso incorrecto. Debes especificar el nombre del artista.\n"
            "Ejemplo: `/remove Radiohead`"
        )
        return

    artist_name = " ".join(context.args)
    chat_id = update.effective_chat.id

    # Verificar que el usuario esté registrado
    user = db.get_user_by_chat_id(chat_id)
    if not user:
        await update.message.reply_text(
            "❌ Primero debes registrarte con `/adduser <tu_nombre>`"
        )
        return

    # Eliminar de la lista de seguimiento
    was_removed = db.remove_followed_artist(user['id'], artist_name)

    if was_removed:
        await update.message.reply_text(
            f"✅ Has dejado de seguir a '{artist_name}'."
        )
    else:
        await update.message.reply_text(
            f"❌ No seguías a '{artist_name}' o no se encontró el artista."
        )

async def notify_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /notify para configurar notificaciones"""
    chat_id = update.effective_chat.id

    # Verificar que el usuario esté registrado
    user = db.get_user_by_chat_id(chat_id)
    if not user:
        await update.message.reply_text(
            "❌ Primero debes registrarte con `/adduser <tu_nombre>`"
        )
        return

    if not context.args:
        # Mostrar configuración actual
        status = "activadas" if user['notification_enabled'] else "desactivadas"
        await update.message.reply_text(
            f"🔔 *Configuración de notificaciones:*\n\n"
            f"Estado: {status}\n"
            f"Hora: {user['notification_time']}\n\n"
            f"*Uso:*\n"
            f"`/notify HH:MM` - Establecer hora (ej: /notify 09:00)\n"
            f"`/notify toggle` - Activar/desactivar\n"
            f"`/notify status` - Ver configuración actual\n\n"
            f"*Nota:* Las notificaciones se envían mediante un script separado.\n"
            f"Asegúrate de ejecutar `python notification_scheduler.py` en segundo plano.",
            parse_mode='Markdown'
        )
        return

    command = context.args[0].lower()

    if command == "toggle":
        # Cambiar estado de notificaciones
        new_state = db.toggle_notifications(user['id'])
        status = "activadas" if new_state else "desactivadas"
        await update.message.reply_text(
            f"🔔 Notificaciones {status}."
        )
    elif command == "status":
        # Mostrar estado actual
        status = "activadas" if user['notification_enabled'] else "desactivadas"
        await update.message.reply_text(
            f"🔔 Notificaciones: {status}\n"
            f"⏰ Hora: {user['notification_time']}"
        )
    else:
        # Intentar establecer hora
        time_str = context.args[0]

        # Validar formato de hora
        try:
            datetime.strptime(time_str, '%H:%M')
        except ValueError:
            await update.message.reply_text(
                "❌ Formato de hora inválido. Usa HH:MM (ej: 09:00)"
            )
            return

        # Establecer nueva hora
        if db.set_notification_time(user['id'], time_str):
            await update.message.reply_text(
                f"✅ Hora de notificación establecida a las {time_str}\n"
                f"🔔 Las notificaciones están {'activadas' if user['notification_enabled'] else 'desactivadas'}"
            )
        else:
            await update.message.reply_text(
                "❌ Error al establecer la hora de notificación."
            )



def format_single_artist_concerts_complete(concerts: List[Dict], artist_name: str, show_notified: bool = False) -> str:
    """
    Formatea todos los conciertos de un artista específico

    Args:
        concerts: Lista de conciertos del artista
        artist_name: Nombre del artista
        show_notified: Si mostrar el estado de notificación

    Returns:
        Mensaje formateado con todos los conciertos del artista
    """
    if not concerts:
        return f"🎵 *{artist_name}*\n\n❌ No se encontraron conciertos."

    # Escapar caracteres especiales del nombre del artista
    safe_artist = artist_name.replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")

    message_lines = [f"🎵 *{safe_artist}*\n"]

    # Ordenar conciertos por fecha (más recientes primero)
    sorted_concerts = sorted(concerts, key=lambda x: x.get('date', ''), reverse=True)

    for i, concert in enumerate(sorted_concerts, 1):
        venue = concert.get('venue', 'Lugar desconocido')
        city = concert.get('city', '')
        date = concert.get('date', 'Fecha desconocida')
        time = concert.get('time', '')
        url = concert.get('url', '')
        source = concert.get('source', '')

        # Formatear fecha
        formatted_date = date
        if date and len(date) >= 10 and '-' in date:
            try:
                date_obj = datetime.strptime(date[:10], '%Y-%m-%d')
                formatted_date = date_obj.strftime('%d/%m/%Y')
            except ValueError:
                pass

        # Escapar caracteres especiales
        safe_venue = str(venue).replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")
        safe_city = str(city).replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")

        # Construir línea del concierto
        concert_line = f"*{i}.* {formatted_date}"

        if time:
            concert_line += f" a las {time}"

        # Ubicación con enlace si está disponible
        location = f"{safe_venue}"
        if safe_city:
            location += f", {safe_city}"

        if url and url.startswith(('http://', 'https://')):
            # Escapar paréntesis en URL
            escaped_url = url.replace(")", "\\)")
            concert_line += f"\n📍 [{location}]({escaped_url})"
        else:
            concert_line += f"\n📍 {location}"

        # Información adicional
        if source:
            concert_line += f"\n🔗 _{source}_"

        # Estado de notificación
        if show_notified:
            if concert.get('notified'):
                concert_line += " ✅"
            else:
                concert_line += " 🔔"

        message_lines.append(concert_line)
        message_lines.append("")  # Línea en blanco entre conciertos

    # Estadísticas finales
    total_concerts = len(concerts)
    message_lines.append(f"📊 *Total: {total_concerts} conciertos*")

    if show_notified:
        notified_count = sum(1 for c in concerts if c.get('notified'))
        pending_count = total_concerts - notified_count
        if notified_count > 0:
            message_lines.append(f"✅ Notificados: {notified_count}")
        if pending_count > 0:
            message_lines.append(f"🔔 Pendientes: {pending_count}")

    return "\n".join(message_lines)


async def serviceon_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /serviceon para activar un servicio"""
    if not context.args:
        await update.message.reply_text(
            "❌ Uso incorrecto. Debes especificar el servicio.\n"
            "Ejemplo: `/serviceon ticketmaster`\n"
            "Servicios disponibles: ticketmaster, spotify, setlistfm"
        )
        return

    service = context.args[0].lower()
    chat_id = update.effective_chat.id

    # Verificar que el usuario esté registrado
    user = db.get_user_by_chat_id(chat_id)
    if not user:
        await update.message.reply_text(
            "❌ Primero debes registrarte con `/adduser <tu_nombre>`"
        )
        return

    # Validar servicio
    valid_services = ['ticketmaster', 'spotify', 'setlistfm']
    if service not in valid_services:
        await update.message.reply_text(
            f"❌ Servicio '{service}' no válido.\n"
            f"Servicios disponibles: {', '.join(valid_services)}"
        )
        return

    # Activar servicio
    if db.set_service_status(user['id'], service, True):
        await update.message.reply_text(
            f"✅ Servicio '{service}' activado correctamente.\n"
            f"Usa `/config` para ver tu configuración actual."
        )
    else:
        await update.message.reply_text(
            f"❌ Error al activar el servicio '{service}'."
        )

async def serviceoff_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /serviceoff para desactivar un servicio"""
    if not context.args:
        await update.message.reply_text(
            "❌ Uso incorrecto. Debes especificar el servicio.\n"
            "Ejemplo: `/serviceoff spotify`\n"
            "Servicios disponibles: ticketmaster, spotify, setlistfm"
        )
        return

    service = context.args[0].lower()
    chat_id = update.effective_chat.id

    # Verificar que el usuario esté registrado
    user = db.get_user_by_chat_id(chat_id)
    if not user:
        await update.message.reply_text(
            "❌ Primero debes registrarte con `/adduser <tu_nombre>`"
        )
        return

    # Validar servicio
    valid_services = ['ticketmaster', 'spotify', 'setlistfm']
    if service not in valid_services:
        await update.message.reply_text(
            f"❌ Servicio '{service}' no válido.\n"
            f"Servicios disponibles: {', '.join(valid_services)}"
        )
        return

    # Verificar que no sea el último servicio activo
    user_services = db.get_user_services(user['id'])
    active_services = [s for s, active in user_services.items() if active and s != 'country_filter']

    if len(active_services) == 1 and user_services.get(service, False):
        await update.message.reply_text(
            f"❌ No puedes desactivar '{service}' porque es el único servicio activo.\n"
            f"Activa otro servicio primero con `/serviceon <servicio>`."
        )
        return

    # Desactivar servicio
    if db.set_service_status(user['id'], service, False):
        await update.message.reply_text(
            f"✅ Servicio '{service}' desactivado correctamente.\n"
            f"Usa `/config` para ver tu configuración actual."
        )
    else:
        await update.message.reply_text(
            f"❌ Error al desactivar el servicio '{service}'."
        )

async def country_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /country - VERSIÓN LEGACY con redirección al nuevo sistema"""
    if not context.args:
        message = (
            "❌ Uso incorrecto. Debes especificar el código de país.\n"
            "Ejemplo: `/country ES`\n\n"
        )

        if country_state_city:
            message += (
                "💡 *Nuevo sistema disponible:*\n"
                "Ahora puedes tener múltiples países configurados:\n"
                "`/addcountry <país>` - Añadir país\n"
                "`/mycountries` - Ver países configurados\n"
                "`/listcountries` - Ver países disponibles"
            )
        else:
            message += "Códigos comunes: ES, US, FR, DE, IT, UK"

        await update.message.reply_text(message, parse_mode='Markdown')
        return

    country_code = context.args[0].upper()
    chat_id = update.effective_chat.id

    # Verificar que el usuario esté registrado
    user = db.get_user_by_chat_id(chat_id)
    if not user:
        await update.message.reply_text(
            "❌ Primero debes registrarte con `/adduser <tu_nombre>`"
        )
        return

    # Validar formato del código de país
    if len(country_code) < 2 or len(country_code) > 3 or not country_code.isalpha():
        await update.message.reply_text(
            "❌ Código de país inválido. Debe tener 2-3 letras.\n"
            "Ejemplos: ES, US, FR, DE, IT, UK"
        )
        return

    if country_state_city:
        # Usar nuevo sistema
        await update.message.reply_text(
            f"🔄 Configurando país usando el nuevo sistema...\n"
            f"Esto reemplazará tu configuración actual de países."
        )

        # Limpiar países existentes
        user_countries = country_state_city.get_user_countries(user['id'])
        for country in user_countries:
            country_state_city.remove_user_country(user['id'], country['code'])

        # Añadir nuevo país
        success = country_state_city.add_user_country(user['id'], country_code)

        if success:
            country_info = country_state_city.get_country_info(country_code)
            country_name = country_info['name'] if country_info else country_code

            await update.message.reply_text(
                f"✅ País configurado: {country_name} ({country_code})\n\n"
                f"💡 Ahora puedes añadir más países con `/addcountry`\n"
                f"Usa `/mycountries` para ver tu configuración."
            )
        else:
            await update.message.reply_text(
                f"❌ Error configurando el país {country_code}.\n"
                f"Verifica que el código sea válido."
            )
    else:
        # Usar sistema legacy
        if db.set_country_filter(user['id'], country_code):
            await update.message.reply_text(
                f"✅ Filtro de país establecido a '{country_code}'.\n"
                f"Usa `/config` para ver tu configuración actual."
            )
        else:
            await update.message.reply_text(
                f"❌ Error al establecer el filtro de país."
            )


async def searchartist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /searchartist - VERSIÓN EXTENDIDA con países múltiples"""
    if not context.args:
        await update.message.reply_text(
            "❌ Uso incorrecto. Debes especificar el nombre del artista.\n"
            "Ejemplo: `/searchartist Metallica`"
        )
        return

    artist_name = " ".join(context.args)
    chat_id = update.effective_chat.id

    # Verificar que el usuario esté registrado para usar su configuración
    user = db.get_user_by_chat_id(chat_id)
    user_services = None

    if user:
        user_services = db.get_user_services(user['id'])

        # Verificar que tenga al menos un servicio activo
        active_services = [s for s, active in user_services.items() if active and s not in ['country_filter', 'countries']]
        if not active_services:
            await update.message.reply_text(
                "❌ No tienes ningún servicio de búsqueda activo.\n"
                "Usa `/serviceon <servicio>` para activar al menos uno.\n"
                "Servicios disponibles: ticketmaster, spotify, setlistfm"
            )
            return

        # Verificar que tenga países configurados
        user_countries = user_services.get('countries', set())
        if not user_countries:
            await update.message.reply_text(
                "❌ No tienes países configurados.\n"
                "Usa `/addcountry <país>` para añadir países.\n"
                "Ejemplo: `/addcountry ES`"
            )
            return

        services_text = ", ".join(active_services)
        countries_text = ", ".join(sorted(user_countries))
        status_message = await update.message.reply_text(
            f"🔍 Buscando conciertos para '{artist_name}'...\n"
            f"🔧 Servicios activos: {services_text}\n"
            f"🌍 Países: {countries_text}"
        )
    else:
        # Usuario no registrado - usar configuración por defecto
        status_message = await update.message.reply_text(
            f"🔍 Buscando conciertos para '{artist_name}'...\n"
            f"(Usando configuración por defecto. Regístrate con `/adduser` para personalizar)"
        )

    try:
        # Buscar conciertos para el artista
        concerts = await search_concerts_for_artist(
            artist_name,
            user_services,
            user_id=user['id'] if user else None
        )

        if not concerts:
            country_info = f" en tus países configurados" if user else ""
            await status_message.edit_text(
                f"📭 No se encontraron conciertos para '{artist_name}'{country_info}.\n"
                "Verifica la ortografía e inténtalo de nuevo."
            )
            return

        # Guardar conciertos en la base de datos
        for concert in concerts:
            db.save_concert(concert)

        # Formatear mensaje usando el nuevo formato
        message = format_single_artist_concerts_complete(
            concerts,
            artist_name,
            show_notified=False
        )

        # Dividir en chunks si es muy largo
        if len(message) > 4000:
            chunks = split_long_message(message, max_length=4000)

            # Editar mensaje original con el primer chunk
            await status_message.edit_text(
                chunks[0],
                parse_mode='Markdown',
                disable_web_page_preview=True
            )

            # Enviar chunks adicionales
            for chunk in chunks[1:]:
                await update.message.reply_text(
                    chunk,
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
        else:
            await status_message.edit_text(
                message,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )

    except Exception as e:
        logger.error(f"Error en comando searchartist: {e}")
        await status_message.edit_text(
            f"❌ Error al buscar conciertos para '{artist_name}'. Inténtalo de nuevo más tarde."
        )


async def expand_concerts_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja la expansión de conciertos desde los botones inline - VERSIÓN CORREGIDA"""
    query = update.callback_query
    await query.answer()

    try:
        # Parsear el callback data
        parts = query.data.split("_")

        if query.data.startswith("expand_all_"):
            # Expandir todos los conciertos
            user_id = int(parts[2])

            # Obtener datos del caché
            cache_data = get_user_search_cache(user_id)
            if not cache_data:
                await query.edit_message_text(
                    "❌ La búsqueda ha expirado. Usa `/search` para buscar de nuevo."
                )
                return

            search_type, concerts = cache_data

            # Mostrar todos los conciertos sin límite usando el formato original
            message = format_expanded_concerts_message_original(concerts, "🎵 Todos los conciertos encontrados")

            # Dividir en chunks si es muy largo
            if len(message) > 4000:
                chunks = split_long_message(message)

                # Editar el mensaje original con el primer chunk
                await query.edit_message_text(
                    chunks[0],
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )

                # Enviar chunks adicionales
                for chunk in chunks[1:]:
                    await query.message.reply_text(
                        chunk,
                        parse_mode='Markdown',
                        disable_web_page_preview=True
                    )
            else:
                await query.edit_message_text(
                    message,
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )

        elif query.data.startswith("expand_artist_"):
            # Expandir conciertos de un artista específico
            user_id = int(parts[-1])  # Último elemento es el user_id
            artist_name = "_".join(parts[2:-1])  # Todo entre "expand_artist" y user_id

            # Obtener datos del caché
            cache_data = get_user_search_cache(user_id)
            if not cache_data:
                await query.edit_message_text(
                    "❌ La búsqueda ha expirado. Usa `/search` para buscar de nuevo."
                )
                return

            search_type, all_concerts = cache_data

            # Filtrar conciertos del artista específico
            artist_concerts = [c for c in all_concerts if c.get('artist_name', '') == artist_name]

            if not artist_concerts:
                await query.edit_message_text(
                    f"❌ No se encontraron conciertos para {artist_name}"
                )
                return

            # Mostrar todos los conciertos del artista usando formato original
            message = format_single_artist_concerts(artist_concerts, artist_name, show_notified=True)

            # Botón para volver
            keyboard = [[
                InlineKeyboardButton("🔙 Volver a la búsqueda", callback_data=f"back_to_search_{user_id}")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                message,
                parse_mode='Markdown',
                disable_web_page_preview=True,
                reply_markup=reply_markup
            )

        elif query.data.startswith("back_to_search_"):
            # Volver a la búsqueda original
            user_id = int(parts[3])

            # Obtener datos del caché
            cache_data = get_user_search_cache(user_id)
            if not cache_data:
                await query.edit_message_text(
                    "❌ La búsqueda ha expirado. Usa `/search` para buscar de nuevo."
                )
                return

            search_type, concerts = cache_data

            # Determinar el título basado en el tipo de búsqueda
            if search_type == "user_concerts":
                title = "🎵 Conciertos de tus artistas seguidos"
                show_notified = True
            else:
                # Extraer nombre del artista del tipo de búsqueda
                artist_name = search_type.replace("artist_search_", "")
                title = f"🎵 Conciertos de {artist_name}"
                show_notified = False

            # Volver al formato resumido ORIGINAL
            message, keyboard = format_concerts_message(
                concerts,
                title,
                show_notified=show_notified,
                show_expand_buttons=True,
                user_id=user_id
            )

            await query.edit_message_text(
                message,
                parse_mode='Markdown',
                disable_web_page_preview=True,
                reply_markup=keyboard
            )

    except Exception as e:
        logger.error(f"Error en expand_concerts_callback: {e}")
        await query.edit_message_text(
            "❌ Error al expandir conciertos. Inténtalo de nuevo."
        )

def format_expanded_concerts_message_original(concerts: List[Dict], title: str) -> str:
    """Formatea todos los conciertos usando el formato ORIGINAL pero sin límite"""
    if not concerts:
        return f"{title}\n\n❌ No se encontraron conciertos."

    message_lines = [f"{title}\n"]

    # Agrupar por artista
    concerts_by_artist = {}
    for concert in concerts:
        artist = concert.get('artist_name', 'Artista desconocido')
        if artist not in concerts_by_artist:
            concerts_by_artist[artist] = []
        concerts_by_artist[artist].append(concert)

    for artist, artist_concerts in concerts_by_artist.items():
        # Escapar caracteres especiales
        safe_artist = artist.replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")
        message_lines.append(f"*{safe_artist}*:")

        # Mostrar TODOS los conciertos (sin límite de 5)
        for concert in artist_concerts:
            venue = concert.get('venue', 'Lugar desconocido')
            city = concert.get('city', '')
            date = concert.get('date', 'Fecha desconocida')
            url = concert.get('url', '')
            source = concert.get('source', '')

            # Formatear fecha
            if date and len(date) >= 10 and '-' in date:
                try:
                    date_obj = datetime.strptime(date[:10], '%Y-%m-%d')
                    date = date_obj.strftime('%d/%m/%Y')
                except ValueError:
                    pass

            # Escapar caracteres especiales
            safe_venue = str(venue).replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")
            safe_city = str(city).replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")

            location = f"{safe_venue}, {safe_city}" if safe_city else safe_venue

            concert_line = f"• {date}: "

            if url and url.startswith(('http://', 'https://')):
                url = url.replace(")", "\\)")
                concert_line += f"[{location}]({url})"
            else:
                concert_line += location

            if source:
                concert_line += f" _{source}_"

            message_lines.append(concert_line)

        message_lines.append("")

    message_lines.append(f"📊 Total: {len(concerts)} conciertos")

    return "\n".join(message_lines)





def format_expanded_concerts_message(concerts: List[Dict], title: str) -> str:
    """Formatea todos los conciertos sin límite"""
    if not concerts:
        return f"{title}\n\n❌ No se encontraron conciertos."

    message_lines = [f"{title}\n"]

    # Agrupar por artista
    concerts_by_artist = {}
    for concert in concerts:
        artist = concert.get('artist_name', 'Artista desconocido')
        if artist not in concerts_by_artist:
            concerts_by_artist[artist] = []
        concerts_by_artist[artist].append(concert)

    for artist, artist_concerts in concerts_by_artist.items():
        # Escapar caracteres especiales
        safe_artist = artist.replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")
        message_lines.append(f"*{safe_artist}* ({len(artist_concerts)} conciertos):")

        # Mostrar TODOS los conciertos
        for concert in artist_concerts:
            venue = concert.get('venue', 'Lugar desconocido')
            city = concert.get('city', '')
            date = concert.get('date', 'Fecha desconocida')
            url = concert.get('url', '')
            source = concert.get('source', '')

            # Formatear fecha
            if date and len(date) >= 10 and '-' in date:
                try:
                    date_obj = datetime.strptime(date[:10], '%Y-%m-%d')
                    date = date_obj.strftime('%d/%m/%Y')
                except ValueError:
                    pass

            # Escapar caracteres especiales
            safe_venue = str(venue).replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")
            safe_city = str(city).replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")

            location = f"{safe_venue}, {safe_city}" if safe_city else safe_venue

            concert_line = f"• {date}: "

            if url and url.startswith(('http://', 'https://')):
                url = url.replace(")", "\\)")
                concert_line += f"[{location}]({url})"
            else:
                concert_line += location

            if source:
                concert_line += f" _{source}_"

            message_lines.append(concert_line)

        message_lines.append("")

    message_lines.append(f"📊 Total: {len(concerts)} conciertos")

    return "\n".join(message_lines)

def split_long_message(message: str, max_length: int = 4000) -> List[str]:
    """Divide un mensaje largo en chunks más pequeños"""
    if len(message) <= max_length:
        return [message]

    chunks = []
    lines = message.split('\n')
    current_chunk = []
    current_length = 0

    for line in lines:
        line_length = len(line) + 1  # +1 para el salto de línea

        if current_length + line_length > max_length and current_chunk:
            # Guardar chunk actual y empezar uno nuevo
            chunks.append('\n'.join(current_chunk))
            current_chunk = [line]
            current_length = line_length
        else:
            current_chunk.append(line)
            current_length += line_length

    # Añadir el último chunk
    if current_chunk:
        chunks.append('\n'.join(current_chunk))

async def config_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /config - VERSIÓN INTERACTIVA con botones"""
    chat_id = update.effective_chat.id

    # Verificar que el usuario esté registrado
    user = db.get_user_by_chat_id(chat_id)
    if not user:
        await update.message.reply_text(
            "❌ Primero debes registrarte con `/adduser <tu_nombre>`"
        )
        return

    # Mostrar configuración con botones
    await show_config_menu(update, user)



async def show_config_menu(update: Update, user: Dict, edit_message: bool = False):
    """Muestra el menú principal de configuración"""
    # Obtener configuración de servicios
    user_services = db.get_user_services(user['id'])

    # Formatear mensaje de configuración
    config_lines = [f"⚙️ *Configuración de {user['username']}*\n"]

    # Notificaciones
    notification_status = "✅ Activadas" if user['notification_enabled'] else "❌ Desactivadas"
    config_lines.append(f"🔔 *Notificaciones:* {notification_status}")
    config_lines.append(f"⏰ *Hora:* {user['notification_time']}")
    config_lines.append("")

    # Países configurados
    if country_state_city:
        user_countries = country_state_city.get_user_countries(user['id'])
        if user_countries:
            config_lines.append("🌍 *Países configurados:*")
            countries_text = ", ".join([f"{c['name']} ({c['code']})" for c in user_countries[:3]])
            if len(user_countries) > 3:
                countries_text += f" y {len(user_countries) - 3} más"
            config_lines.append(f"   {countries_text}")
        else:
            config_lines.append("🌍 *Países:* Ninguno configurado")
    else:
        # Fallback al sistema legacy
        country_filter = user_services.get('country_filter', 'ES')
        config_lines.append(f"🌍 *País:* {country_filter}")

    config_lines.append("")

    # Estado de servicios
    config_lines.append("🔧 *Servicios de búsqueda:*")
    active_services = []
    inactive_services = []

    for service in ['ticketmaster', 'spotify', 'setlistfm']:
        if user_services.get(service, True):
            active_services.append(service.capitalize())
        else:
            inactive_services.append(service.capitalize())

    if active_services:
        config_lines.append(f"   ✅ {', '.join(active_services)}")
    if inactive_services:
        config_lines.append(f"   ❌ {', '.join(inactive_services)}")

    # Artistas seguidos
    followed_artists = db.get_user_followed_artists(user['id'])
    config_lines.append("")
    config_lines.append(f"🎵 *Artistas seguidos:* {len(followed_artists)}")

    # Crear botones del menú principal
    keyboard = [
        [
            InlineKeyboardButton("🔔 Notificaciones", callback_data=f"config_notifications_{user['id']}"),
            InlineKeyboardButton("🌍 Países", callback_data=f"config_countries_{user['id']}")
        ],
        [
            InlineKeyboardButton("🔧 Servicios", callback_data=f"config_services_{user['id']}"),
            InlineKeyboardButton("🎵 Artistas", callback_data=f"config_artists_{user['id']}")
        ],
        [
            InlineKeyboardButton("🔄 Actualizar", callback_data=f"config_refresh_{user['id']}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    response = "\n".join(config_lines)

    try:
        if edit_message and hasattr(update, 'callback_query'):
            await update.callback_query.edit_message_text(
                response,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                response,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
    except Exception as e:
        # Si hay error con Markdown, enviar sin formato
        logger.warning(f"Error con Markdown en config, enviando texto plano: {e}")
        plain_response = response.replace('*', '').replace('`', '')
        if edit_message and hasattr(update, 'callback_query'):
            await update.callback_query.edit_message_text(
                plain_response,
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                plain_response,
                reply_markup=reply_markup
            )


async def config_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja todos los callbacks del sistema de configuración"""
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    logger.info(f"Config callback recibido: {callback_data}")

    # Parsear callback data
    parts = callback_data.split("_")
    if len(parts) < 3:
        await query.edit_message_text("❌ Error en el callback.")
        return

    prefix = parts[0]  # 'config', 'notif', 'country', 'service', etc.
    action = parts[1]

    # Obtener user_id del final
    try:
        user_id = int(parts[-1])
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Error de usuario.")
        return

    # Verificar que el usuario existe
    user = db.get_user_by_chat_id(query.message.chat_id)
    if not user or user['id'] != user_id:
        await query.edit_message_text("❌ Error de autenticación.")
        return

    try:
        # Manejar según el prefijo
        if prefix == "config":
            if action == "notifications":
                await show_notifications_menu(query, user)
            elif action == "countries":
                await show_countries_menu(query, user)
            elif action == "services":
                await show_services_menu(query, user)
            elif action == "artists":
                await show_artists_menu(query, user)
            elif action == "refresh" or action == "back":
                # Actualizar la configuración
                updated_user = db.get_user_by_chat_id(query.message.chat_id)
                fake_update = type('obj', (object,), {'callback_query': query})()
                await show_config_menu(fake_update, updated_user, edit_message=True)

        elif prefix == "notif":
            await handle_notification_callback(query, action, user_id, context)

        elif prefix == "country":
            await handle_country_callback(query, action, user_id, parts, context)

        elif prefix == "service":
            await handle_service_callback(query, action, user_id, parts)

        else:
            await query.edit_message_text("❌ Acción no reconocida.")

    except Exception as e:
        logger.error(f"Error en config_callback_handler: {e}")
        await query.edit_message_text("❌ Error procesando la solicitud.")

async def handle_notification_callback(query, action: str, user_id: int, context):
    """Maneja callbacks específicos de notificaciones"""
    if action == "on":
        # Activar notificaciones
        conn = db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE users SET notification_enabled = 1 WHERE id = ?", (user_id,))
            conn.commit()
            success = cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error activando notificaciones: {e}")
            success = False
        finally:
            conn.close()

        message = "✅ Notificaciones activadas correctamente." if success else "❌ Error al activar notificaciones."
        keyboard = [[InlineKeyboardButton("🔙 Volver al menú", callback_data=f"config_back_{user_id}")]]

    elif action == "off":
        # Desactivar notificaciones
        conn = db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE users SET notification_enabled = 0 WHERE id = ?", (user_id,))
            conn.commit()
            success = cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error desactivando notificaciones: {e}")
            success = False
        finally:
            conn.close()

        message = "❌ Notificaciones desactivadas." if success else "❌ Error al desactivar notificaciones."
        keyboard = [[InlineKeyboardButton("🔙 Volver al menú", callback_data=f"config_back_{user_id}")]]

    elif action == "time":
        # Solicitar nueva hora
        message = (
            "⏰ *Cambiar hora de notificación*\n\n"
            "Envía la nueva hora en formato HH:MM\n"
            "Ejemplo: 09:00, 14:30, 20:15\n\n"
            "Responde a este mensaje con la hora deseada."
        )
        keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data=f"config_back_{user_id}")]]

        # Guardar estado para esperar respuesta
        context.user_data['waiting_for_time'] = user_id

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)

async def handle_country_callback(query, action: str, user_id: int, parts: list, context):
    """Maneja callbacks específicos de países"""
    if action == "add":
        message = (
            "➕ *Añadir país*\n\n"
            "Envía el código o nombre del país que quieres añadir.\n"
            "Ejemplos: ES, Spain, FR, France\n\n"
            "Responde a este mensaje con el país deseado."
        )
        context.user_data['waiting_for_country_add'] = user_id
        keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data=f"config_countries_{user_id}")]]

    elif action == "remove":
        if country_state_city:
            user_countries = country_state_city.get_user_countries(user_id)
            if not user_countries:
                message = "❌ No tienes países configurados para eliminar."
                keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data=f"config_countries_{user_id}")]]
            elif len(user_countries) == 1:
                message = "❌ No puedes eliminar tu último país configurado."
                keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data=f"config_countries_{user_id}")]]
            else:
                message = "➖ *Eliminar país*\n\nSelecciona el país a eliminar:"
                keyboard = []
                for country in user_countries:
                    keyboard.append([InlineKeyboardButton(
                        f"❌ {country['name']} ({country['code']})",
                        callback_data=f"country_delete_{country['code']}_{user_id}"
                    )])
                keyboard.append([InlineKeyboardButton("🔙 Cancelar", callback_data=f"config_countries_{user_id}")])
        else:
            message = "❌ Sistema de países múltiples no disponible."
            keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data=f"config_countries_{user_id}")]]

    elif action == "list":
        message = (
            "📋 *Países disponibles*\n\n"
            "Usa `/listcountries` para ver la lista completa de países disponibles."
        )
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data=f"config_countries_{user_id}")]]

    elif action == "delete":
        # Manejar eliminación de país específico
        if len(parts) >= 4:
            country_code = parts[2]
            if country_state_city:
                success = country_state_city.remove_user_country(user_id, country_code)
                if success:
                    country_info = country_state_city.get_country_info(country_code)
                    country_name = country_info['name'] if country_info else country_code
                    message = f"✅ País {country_name} ({country_code}) eliminado correctamente."
                else:
                    message = f"❌ Error al eliminar el país {country_code}."
            else:
                message = "❌ Sistema de países múltiples no disponible."
        else:
            message = "❌ Error en la eliminación del país."

        keyboard = [[InlineKeyboardButton("🔙 Volver al menú", callback_data=f"config_countries_{user_id}")]]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)

async def handle_service_callback(query, action: str, user_id: int, parts: list):
    """Maneja callbacks específicos de servicios"""
    user_services = db.get_user_services(user_id)
    services = ['ticketmaster', 'spotify', 'setlistfm']

    if action == "activate":
        # Mostrar servicios inactivos para activar
        inactive_services = [s for s in services if not user_services.get(s, True)]

        if not inactive_services:
            message = "✅ Todos los servicios ya están activos."
            keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data=f"config_services_{user_id}")]]
        else:
            message = "✅ *Activar servicio*\n\nSelecciona el servicio a activar:"
            keyboard = []
            for i, service in enumerate(inactive_services, 1):
                keyboard.append([InlineKeyboardButton(
                    f"{i}. {service.capitalize()}",
                    callback_data=f"service_enable_{service}_{user_id}"
                )])
            keyboard.append([InlineKeyboardButton("🔙 Cancelar", callback_data=f"config_services_{user_id}")])

    elif action == "deactivate":
        # Mostrar servicios activos para desactivar
        active_services = [s for s in services if user_services.get(s, True)]

        if len(active_services) <= 1:
            message = "❌ Debes mantener al menos un servicio activo."
            keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data=f"config_services_{user_id}")]]
        else:
            message = "❌ *Desactivar servicio*\n\nSelecciona el servicio a desactivar:"
            keyboard = []
            for i, service in enumerate(active_services, 1):
                keyboard.append([InlineKeyboardButton(
                    f"{i}. {service.capitalize()}",
                    callback_data=f"service_disable_{service}_{user_id}"
                )])
            keyboard.append([InlineKeyboardButton("🔙 Cancelar", callback_data=f"config_services_{user_id}")])

    elif action == "enable" or action == "disable":
        # Procesar activar/desactivar servicio específico
        if len(parts) >= 4:
            service = parts[2]
            success = db.set_service_status(user_id, service, action == "enable")
            action_text = "activado" if action == "enable" else "desactivado"

            if success:
                message = f"✅ Servicio {service.capitalize()} {action_text} correctamente."
            else:
                message = f"❌ Error al modificar el servicio {service.capitalize()}."
        else:
            message = "❌ Error en la operación del servicio."

        keyboard = [[InlineKeyboardButton("🔙 Volver al menú", callback_data=f"config_services_{user_id}")]]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)




# Función principal del comando config (ya corregida)
async def config_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /config - VERSIÓN INTERACTIVA con botones"""
    chat_id = update.effective_chat.id

    # Verificar que el usuario esté registrado
    user = db.get_user_by_chat_id(chat_id)
    if not user:
        await update.message.reply_text(
            "❌ Primero debes registrarte con `/adduser <tu_nombre>`"
        )
        return

    # Mostrar configuración con botones
    await show_config_menu(update, user)

async def show_config_menu(update: Update, user: Dict, edit_message: bool = False):
    """Muestra el menú principal de configuración"""
    # Obtener configuración de servicios
    user_services = db.get_user_services(user['id'])

    # Formatear mensaje de configuración
    config_lines = [f"⚙️ *Configuración de {user['username']}*\n"]

    # Notificaciones
    notification_status = "✅ Activadas" if user['notification_enabled'] else "❌ Desactivadas"
    config_lines.append(f"🔔 *Notificaciones:* {notification_status}")
    config_lines.append(f"⏰ *Hora:* {user['notification_time']}")
    config_lines.append("")

    # Países configurados
    if country_state_city:
        user_countries = country_state_city.get_user_countries(user['id'])
        if user_countries:
            config_lines.append("🌍 *Países configurados:*")
            countries_text = ", ".join([f"{c['name']} ({c['code']})" for c in user_countries[:3]])
            if len(user_countries) > 3:
                countries_text += f" y {len(user_countries) - 3} más"
            config_lines.append(f"   {countries_text}")
        else:
            config_lines.append("🌍 *Países:* Ninguno configurado")
    else:
        # Fallback al sistema legacy
        country_filter = user_services.get('country_filter', 'ES')
        config_lines.append(f"🌍 *País:* {country_filter}")

    config_lines.append("")

    # Estado de servicios
    config_lines.append("🔧 *Servicios de búsqueda:*")
    active_services = []
    inactive_services = []

    for service in ['ticketmaster', 'spotify', 'setlistfm']:
        if user_services.get(service, True):
            active_services.append(service.capitalize())
        else:
            inactive_services.append(service.capitalize())

    if active_services:
        config_lines.append(f"   ✅ {', '.join(active_services)}")
    if inactive_services:
        config_lines.append(f"   ❌ {', '.join(inactive_services)}")

    # Artistas seguidos
    followed_artists = db.get_user_followed_artists(user['id'])
    config_lines.append("")
    config_lines.append(f"🎵 *Artistas seguidos:* {len(followed_artists)}")

    # Crear botones del menú principal
    keyboard = [
        [
            InlineKeyboardButton("🔔 Notificaciones", callback_data=f"config_notifications_{user['id']}"),
            InlineKeyboardButton("🌍 Países", callback_data=f"config_countries_{user['id']}")
        ],
        [
            InlineKeyboardButton("🔧 Servicios", callback_data=f"config_services_{user['id']}"),
            InlineKeyboardButton("🎵 Artistas", callback_data=f"config_artists_{user['id']}")
        ],
        [
            InlineKeyboardButton("🔄 Actualizar", callback_data=f"config_refresh_{user['id']}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    response = "\n".join(config_lines)

    try:
        if edit_message and hasattr(update, 'callback_query'):
            await update.callback_query.edit_message_text(
                response,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                response,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
    except Exception as e:
        # Si hay error con Markdown, enviar sin formato
        logger.warning(f"Error con Markdown en config, enviando texto plano: {e}")
        plain_response = response.replace('*', '').replace('`', '')
        if edit_message and hasattr(update, 'callback_query'):
            await update.callback_query.edit_message_text(
                plain_response,
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                plain_response,
                reply_markup=reply_markup
            )

# HANDLER PRINCIPAL - Este maneja TODOS los callbacks de configuración
async def config_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja todos los callbacks del sistema de configuración"""
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    logger.info(f"Config callback recibido: {callback_data}")

    # Parsear callback data
    parts = callback_data.split("_")
    if len(parts) < 3:
        await query.edit_message_text("❌ Error en el callback.")
        return

    prefix = parts[0]  # 'config', 'notif', 'country', 'service', etc.
    action = parts[1]

    # Obtener user_id del final
    try:
        user_id = int(parts[-1])
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Error de usuario.")
        return

    # Verificar que el usuario existe
    user = db.get_user_by_chat_id(query.message.chat_id)
    if not user or user['id'] != user_id:
        await query.edit_message_text("❌ Error de autenticación.")
        return

    try:
        # Manejar según el prefijo
        if prefix == "config":
            if action == "notifications":
                await show_notifications_menu(query, user)
            elif action == "countries":
                await show_countries_menu(query, user)
            elif action == "services":
                await show_services_menu(query, user)
            elif action == "artists":
                await show_artists_menu(query, user)
            elif action == "refresh" or action == "back":
                # Actualizar la configuración
                updated_user = db.get_user_by_chat_id(query.message.chat_id)
                fake_update = type('obj', (object,), {'callback_query': query})()
                await show_config_menu(fake_update, updated_user, edit_message=True)

        elif prefix == "notif":
            await handle_notification_callback(query, action, user_id, context)

        elif prefix == "country":
            await handle_country_callback(query, action, user_id, parts, context)

        elif prefix == "service":
            await handle_service_callback(query, action, user_id, parts)

        else:
            await query.edit_message_text("❌ Acción no reconocida.")

    except Exception as e:
        logger.error(f"Error en config_callback_handler: {e}")
        await query.edit_message_text("❌ Error procesando la solicitud.")

async def handle_notification_callback(query, action: str, user_id: int, context):
    """Maneja callbacks específicos de notificaciones"""
    if action == "on":
        # Activar notificaciones
        conn = db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE users SET notification_enabled = 1 WHERE id = ?", (user_id,))
            conn.commit()
            success = cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error activando notificaciones: {e}")
            success = False
        finally:
            conn.close()

        message = "✅ Notificaciones activadas correctamente." if success else "❌ Error al activar notificaciones."
        keyboard = [[InlineKeyboardButton("🔙 Volver al menú", callback_data=f"config_back_{user_id}")]]

    elif action == "off":
        # Desactivar notificaciones
        conn = db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE users SET notification_enabled = 0 WHERE id = ?", (user_id,))
            conn.commit()
            success = cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error desactivando notificaciones: {e}")
            success = False
        finally:
            conn.close()

        message = "❌ Notificaciones desactivadas." if success else "❌ Error al desactivar notificaciones."
        keyboard = [[InlineKeyboardButton("🔙 Volver al menú", callback_data=f"config_back_{user_id}")]]

    elif action == "time":
        # Solicitar nueva hora
        message = (
            "⏰ *Cambiar hora de notificación*\n\n"
            "Envía la nueva hora en formato HH:MM\n"
            "Ejemplo: 09:00, 14:30, 20:15\n\n"
            "Responde a este mensaje con la hora deseada."
        )
        keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data=f"config_back_{user_id}")]]

        # Guardar estado para esperar respuesta
        context.user_data['waiting_for_time'] = user_id

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)

async def handle_country_callback(query, action: str, user_id: int, parts: list, context):
    """Maneja callbacks específicos de países"""
    if action == "add":
        message = (
            "➕ *Añadir país*\n\n"
            "Envía el código o nombre del país que quieres añadir.\n"
            "Ejemplos: ES, Spain, FR, France\n\n"
            "Responde a este mensaje con el país deseado."
        )
        context.user_data['waiting_for_country_add'] = user_id
        keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data=f"config_countries_{user_id}")]]

    elif action == "remove":
        if country_state_city:
            user_countries = country_state_city.get_user_countries(user_id)
            if not user_countries:
                message = "❌ No tienes países configurados para eliminar."
                keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data=f"config_countries_{user_id}")]]
            elif len(user_countries) == 1:
                message = "❌ No puedes eliminar tu último país configurado."
                keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data=f"config_countries_{user_id}")]]
            else:
                message = "➖ *Eliminar país*\n\nSelecciona el país a eliminar:"
                keyboard = []
                for country in user_countries:
                    keyboard.append([InlineKeyboardButton(
                        f"❌ {country['name']} ({country['code']})",
                        callback_data=f"country_delete_{country['code']}_{user_id}"
                    )])
                keyboard.append([InlineKeyboardButton("🔙 Cancelar", callback_data=f"config_countries_{user_id}")])
        else:
            message = "❌ Sistema de países múltiples no disponible."
            keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data=f"config_countries_{user_id}")]]

    elif action == "list":
        message = (
            "📋 *Países disponibles*\n\n"
            "Usa `/listcountries` para ver la lista completa de países disponibles."
        )
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data=f"config_countries_{user_id}")]]

    elif action == "delete":
        # Manejar eliminación de país específico
        if len(parts) >= 4:
            country_code = parts[2]
            if country_state_city:
                success = country_state_city.remove_user_country(user_id, country_code)
                if success:
                    country_info = country_state_city.get_country_info(country_code)
                    country_name = country_info['name'] if country_info else country_code
                    message = f"✅ País {country_name} ({country_code}) eliminado correctamente."
                else:
                    message = f"❌ Error al eliminar el país {country_code}."
            else:
                message = "❌ Sistema de países múltiples no disponible."
        else:
            message = "❌ Error en la eliminación del país."

        keyboard = [[InlineKeyboardButton("🔙 Volver al menú", callback_data=f"config_countries_{user_id}")]]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)

async def handle_service_callback(query, action: str, user_id: int, parts: list):
    """Maneja callbacks específicos de servicios"""
    user_services = db.get_user_services(user_id)
    services = ['ticketmaster', 'spotify', 'setlistfm']

    if action == "activate":
        # Mostrar servicios inactivos para activar
        inactive_services = [s for s in services if not user_services.get(s, True)]

        if not inactive_services:
            message = "✅ Todos los servicios ya están activos."
            keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data=f"config_services_{user_id}")]]
        else:
            message = "✅ *Activar servicio*\n\nSelecciona el servicio a activar:"
            keyboard = []
            for i, service in enumerate(inactive_services, 1):
                keyboard.append([InlineKeyboardButton(
                    f"{i}. {service.capitalize()}",
                    callback_data=f"service_enable_{service}_{user_id}"
                )])
            keyboard.append([InlineKeyboardButton("🔙 Cancelar", callback_data=f"config_services_{user_id}")])

    elif action == "deactivate":
        # Mostrar servicios activos para desactivar
        active_services = [s for s in services if user_services.get(s, True)]

        if len(active_services) <= 1:
            message = "❌ Debes mantener al menos un servicio activo."
            keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data=f"config_services_{user_id}")]]
        else:
            message = "❌ *Desactivar servicio*\n\nSelecciona el servicio a desactivar:"
            keyboard = []
            for i, service in enumerate(active_services, 1):
                keyboard.append([InlineKeyboardButton(
                    f"{i}. {service.capitalize()}",
                    callback_data=f"service_disable_{service}_{user_id}"
                )])
            keyboard.append([InlineKeyboardButton("🔙 Cancelar", callback_data=f"config_services_{user_id}")])

    elif action == "enable" or action == "disable":
        # Procesar activar/desactivar servicio específico
        if len(parts) >= 4:
            service = parts[2]
            success = db.set_service_status(user_id, service, action == "enable")
            action_text = "activado" if action == "enable" else "desactivado"

            if success:
                message = f"✅ Servicio {service.capitalize()} {action_text} correctamente."
            else:
                message = f"❌ Error al modificar el servicio {service.capitalize()}."
        else:
            message = "❌ Error en la operación del servicio."

        keyboard = [[InlineKeyboardButton("🔙 Volver al menú", callback_data=f"config_services_{user_id}")]]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)

async def show_notifications_menu(query, user: Dict):
    """Muestra el submenú de notificaciones"""
    status = "✅ Activadas" if user['notification_enabled'] else "❌ Desactivadas"

    message = (
        f"🔔 *Gestión de Notificaciones*\n\n"
        f"Estado actual: {status}\n"
        f"Hora actual: {user['notification_time']}\n\n"
        f"Selecciona una opción:"
    )

    keyboard = [
        [
            InlineKeyboardButton("✅ Activar", callback_data=f"notif_on_{user['id']}"),
            InlineKeyboardButton("❌ Desactivar", callback_data=f"notif_off_{user['id']}")
        ],
        [
            InlineKeyboardButton("⏰ Cambiar hora", callback_data=f"notif_time_{user['id']}")
        ],
        [
            InlineKeyboardButton("🔙 Volver", callback_data=f"config_back_{user['id']}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def show_countries_menu(query, user: Dict):
    """Muestra el submenú de países"""
    if country_state_city:
        user_countries = country_state_city.get_user_countries(user['id'])
        if user_countries:
            countries_text = "\n".join([f"• {c['name']} ({c['code']})" for c in user_countries])
        else:
            countries_text = "Ningún país configurado"
    else:
        user_services = db.get_user_services(user['id'])
        countries_text = f"• {user_services.get('country_filter', 'ES')} (sistema legacy)"

    message = (
        f"🌍 *Gestión de Países*\n\n"
        f"Países actuales:\n{countries_text}\n\n"
        f"Selecciona una opción:"
    )

    keyboard = [
        [
            InlineKeyboardButton("➕ Añadir país", callback_data=f"country_add_{user['id']}"),
            InlineKeyboardButton("➖ Eliminar país", callback_data=f"country_remove_{user['id']}")
        ],
        [
            InlineKeyboardButton("📋 Ver disponibles", callback_data=f"country_list_{user['id']}")
        ],
        [
            InlineKeyboardButton("🔙 Volver", callback_data=f"config_back_{user['id']}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def show_services_menu(query, user: Dict):
    """Muestra el submenú de servicios"""
    user_services = db.get_user_services(user['id'])

    services_status = []
    for service in ['ticketmaster', 'spotify', 'setlistfm']:
        status = "✅" if user_services.get(service, True) else "❌"
        services_status.append(f"{status} {service.capitalize()}")

    message = (
        f"🔧 *Gestión de Servicios*\n\n"
        f"Estado actual:\n" + "\n".join(services_status) + "\n\n"
        f"Selecciona una opción:"
    )

    keyboard = [
        [
            InlineKeyboardButton("✅ Activar servicio", callback_data=f"service_activate_{user['id']}"),
            InlineKeyboardButton("❌ Desactivar servicio", callback_data=f"service_deactivate_{user['id']}")
        ],
        [
            InlineKeyboardButton("🔙 Volver", callback_data=f"config_back_{user['id']}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_artists_menu(query, user: Dict):
    """Muestra el submenú de artistas (equivalente a /list)"""
    followed_artists = db.get_user_followed_artists(user['id'])

    if not followed_artists:
        message = (
            f"🎵 *Artistas seguidos*\n\n"
            f"No tienes artistas seguidos aún.\n"
            f"Usa el botón de abajo para añadir artistas."
        )
    else:
        message_lines = [f"🎵 *Artistas seguidos* ({len(followed_artists)})\n"]

        # Mostrar solo los primeros 10 para no sobrecargar
        for i, artist in enumerate(followed_artists[:10], 1):
            line = f"{i}. *{artist['name']}*"

            details = []
            if artist['country']:
                details.append(f"🌍 {artist['country']}")
            if artist['formed_year']:
                details.append(f"📅 {artist['formed_year']}")

            if details:
                line += f" ({', '.join(details)})"

            message_lines.append(line)

        if len(followed_artists) > 10:
            message_lines.append(f"_...y {len(followed_artists) - 10} más_")

        message_lines.append(f"\nUsa `/list` para ver la lista completa con enlaces.")
        message = "\n".join(message_lines)

    keyboard = [
        [
            InlineKeyboardButton("➕ Añadir artista", callback_data=f"artist_add_{user['id']}"),
            InlineKeyboardButton("🔍 Buscar conciertos", callback_data=f"artist_search_{user['id']}")
        ],
        [
            InlineKeyboardButton("🔙 Volver", callback_data=f"config_back_{user['id']}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def notification_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los callbacks específicos de notificaciones"""
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    action = parts[1]
    user_id = int(parts[2])

    user = db.get_user_by_chat_id(query.message.chat_id)
    if not user or user['id'] != user_id:
        await query.edit_message_text("❌ Error de autenticación.")
        return

    if action == "on":
        # Activar notificaciones
        # Actualizar directamente en la base de datos
        conn = db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE users SET notification_enabled = 1 WHERE id = ?", (user_id,))
            conn.commit()
            success = cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error activando notificaciones: {e}")
            success = False
        finally:
            conn.close()

        message = "✅ Notificaciones activadas correctamente." if success else "❌ Error al activar notificaciones."
        keyboard = [[InlineKeyboardButton("🔙 Volver al menú", callback_data=f"config_back_{user_id}")]]

    elif action == "off":
        # Desactivar notificaciones
        conn = db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE users SET notification_enabled = 0 WHERE id = ?", (user_id,))
            conn.commit()
            success = cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error desactivando notificaciones: {e}")
            success = False
        finally:
            conn.close()

        message = "❌ Notificaciones desactivadas." if success else "❌ Error al desactivar notificaciones."
        keyboard = [[InlineKeyboardButton("🔙 Volver al menú", callback_data=f"config_back_{user_id}")]]

    elif action == "time":
        # Solicitar nueva hora
        message = (
            "⏰ *Cambiar hora de notificación*\n\n"
            "Envía la nueva hora en formato HH:MM\n"
            "Ejemplo: 09:00, 14:30, 20:15\n\n"
            "Responde a este mensaje con la hora deseada."
        )
        keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data=f"config_back_{user_id}")]]

        # Guardar estado para esperar respuesta
        context.user_data['waiting_for_time'] = user_id

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)

async def country_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los callbacks específicos de países"""
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    action = parts[1]
    user_id = int(parts[2])

    user = db.get_user_by_chat_id(query.message.chat_id)
    if not user or user['id'] != user_id:
        await query.edit_message_text("❌ Error de autenticación.")
        return

    if action == "add":
        message = (
            "➕ *Añadir país*\n\n"
            "Envía el código o nombre del país que quieres añadir.\n"
            "Ejemplos: ES, Spain, FR, France\n\n"
            "Responde a este mensaje con el país deseado."
        )
        context.user_data['waiting_for_country_add'] = user_id

    elif action == "remove":
        if country_state_city:
            user_countries = country_state_city.get_user_countries(user_id)
            if not user_countries:
                message = "❌ No tienes países configurados para eliminar."
                keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data=f"config_countries_{user_id}")]]
            elif len(user_countries) == 1:
                message = "❌ No puedes eliminar tu último país configurado."
                keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data=f"config_countries_{user_id}")]]
            else:
                message = "➖ *Eliminar país*\n\nSelecciona el país a eliminar:"
                keyboard = []
                for country in user_countries:
                    keyboard.append([InlineKeyboardButton(
                        f"❌ {country['name']} ({country['code']})",
                        callback_data=f"country_delete_{country['code']}_{user_id}"
                    )])
                keyboard.append([InlineKeyboardButton("🔙 Cancelar", callback_data=f"config_countries_{user_id}")])
        else:
            message = "❌ Sistema de países múltiples no disponible."
            keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data=f"config_countries_{user_id}")]]

    elif action == "list":
        message = (
            "📋 *Países disponibles*\n\n"
            "Obteniendo lista de países disponibles...\n"
            "Esto puede tardar un momento."
        )
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data=f"config_countries_{user_id}")]]
        # Aquí podrías implementar una lista paginada de países

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)

async def service_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los callbacks específicos de servicios"""
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    action = parts[1]
    user_id = int(parts[2])

    user = db.get_user_by_chat_id(query.message.chat_id)
    if not user or user['id'] != user_id:
        await query.edit_message_text("❌ Error de autenticación.")
        return

    user_services = db.get_user_services(user_id)
    services = ['ticketmaster', 'spotify', 'setlistfm']

    if action == "activate":
        # Mostrar servicios inactivos para activar
        inactive_services = [s for s in services if not user_services.get(s, True)]

        if not inactive_services:
            message = "✅ Todos los servicios ya están activos."
            keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data=f"config_services_{user_id}")]]
        else:
            message = "✅ *Activar servicio*\n\nSelecciona el servicio a activar:"
            keyboard = []
            for i, service in enumerate(inactive_services, 1):
                keyboard.append([InlineKeyboardButton(
                    f"{i}. {service.capitalize()}",
                    callback_data=f"service_enable_{service}_{user_id}"
                )])
            keyboard.append([InlineKeyboardButton("🔙 Cancelar", callback_data=f"config_services_{user_id}")])

    elif action == "deactivate":
        # Mostrar servicios activos para desactivar
        active_services = [s for s in services if user_services.get(s, True)]

        if len(active_services) <= 1:
            message = "❌ Debes mantener al menos un servicio activo."
            keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data=f"config_services_{user_id}")]]
        else:
            message = "❌ *Desactivar servicio*\n\nSelecciona el servicio a desactivar:"
            keyboard = []
            for i, service in enumerate(active_services, 1):
                keyboard.append([InlineKeyboardButton(
                    f"{i}. {service.capitalize()}",
                    callback_data=f"service_disable_{service}_{user_id}"
                )])
            keyboard.append([InlineKeyboardButton("🔙 Cancelar", callback_data=f"config_services_{user_id}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)

async def service_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja las acciones específicas de activar/desactivar servicios"""
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    action = parts[1]  # enable o disable
    service = parts[2]
    user_id = int(parts[3])

    success = False
    if action == "enable":
        success = db.set_service_status(user_id, service, True)
        action_text = "activado"
    elif action == "disable":
        success = db.set_service_status(user_id, service, False)
        action_text = "desactivado"

    if success:
        message = f"✅ Servicio {service.capitalize()} {action_text} correctamente."
    else:
        message = f"❌ Error al modificar el servicio {service.capitalize()}."

    keyboard = [[InlineKeyboardButton("🔙 Volver al menú", callback_data=f"config_services_{user_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, reply_markup=reply_markup)

async def config_back_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el botón de volver al menú principal de configuración"""
    query = update.callback_query
    await query.answer()

    user_id = int(query.data.split("_")[-1])
    user = db.get_user_by_chat_id(query.message.chat_id)

    if not user or user['id'] != user_id:
        await query.edit_message_text("❌ Error de autenticación.")
        return

    # Actualizar usuario y mostrar menú principal
    updated_user = db.get_user_by_chat_id(query.message.chat_id)
    fake_update = type('obj', (object,), {'callback_query': query})()
    await show_config_menu(fake_update, updated_user, edit_message=True)


# Función auxiliar para manejar mensajes de texto cuando se espera input
async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja la entrada de texto cuando se espera configuración"""
    logger.info(f"DEBUG: handle_text_input llamado con user_data: {context.user_data}")

    # PRIORIDAD 1: Cambio de hora de notificación
    if 'waiting_for_time' in context.user_data:
        # Procesar nueva hora de notificación
        user_id = context.user_data['waiting_for_time']
        time_str = update.message.text.strip()

        try:
            # Validar formato de hora
            datetime.strptime(time_str, '%H:%M')

            if db.set_notification_time(user_id, time_str):
                await update.message.reply_text(
                    f"✅ Hora de notificación cambiada a {time_str}",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Volver a configuración", callback_data=f"config_back_{user_id}")
                    ]])
                )
            else:
                await update.message.reply_text("❌ Error al cambiar la hora.")
        except ValueError:
            await update.message.reply_text("❌ Formato inválido. Usa HH:MM (ejemplo: 09:00)")

        del context.user_data['waiting_for_time']
        return

    # PRIORIDAD 2: Añadir país
    elif 'waiting_for_country_add' in context.user_data:
        # Procesar añadir país
        user_id = context.user_data['waiting_for_country_add']
        country_input = update.message.text.strip()

        if country_state_city:
            # Usar el sistema existente de añadir países
            if len(country_input) == 2 and country_input.isalpha():
                country_code = country_input.upper()
                success = country_state_city.add_user_country(user_id, country_code)
            else:
                # Buscar por nombre
                matching_countries = country_state_city.search_countries(country_input)
                if len(matching_countries) == 1:
                    success = country_state_city.add_user_country(user_id, matching_countries[0]['code'])
                else:
                    await update.message.reply_text("❌ País no encontrado o ambiguo. Usa el código de 2 letras.")
                    del context.user_data['waiting_for_country_add']
                    return

            if success:
                await update.message.reply_text(
                    f"✅ País añadido correctamente",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Volver a configuración", callback_data=f"config_back_{user_id}")
                    ]])
                )
            else:
                await update.message.reply_text("❌ Error al añadir el país o ya lo tienes configurado.")
        else:
            await update.message.reply_text("❌ Sistema de países múltiples no disponible.")

        del context.user_data['waiting_for_country_add']
        return

    # PRIORIDAD 3: Usuario de Last.fm (nuevo)
    elif 'waiting_for_lastfm_user' in context.user_data:
        # Procesar nuevo usuario de Last.fm
        user_id = context.user_data['waiting_for_lastfm_user']
        lastfm_username = update.message.text.strip()

        logger.info(f"DEBUG: Procesando usuario Last.fm: {lastfm_username}")

        if not lastfm_username:
            await update.message.reply_text("❌ Nombre de usuario no válido.")
            del context.user_data['waiting_for_lastfm_user']
            return

        # Verificar que el servicio esté disponible
        if not lastfm_service:
            await update.message.reply_text("❌ Servicio de Last.fm no disponible.")
            del context.user_data['waiting_for_lastfm_user']
            return

        # Verificar que el usuario existe en Last.fm
        status_message = await update.message.reply_text(f"🔍 Verificando usuario '{lastfm_username}'...")

        try:
            if not lastfm_service.check_user_exists(lastfm_username):
                await status_message.edit_text(
                    f"❌ El usuario '{lastfm_username}' no existe en Last.fm.\n"
                    f"Verifica el nombre e inténtalo de nuevo."
                )
                del context.user_data['waiting_for_lastfm_user']
                return

            # Obtener información del usuario
            user_info = lastfm_service.get_user_info(lastfm_username)

            # Guardar en base de datos
            if db.set_user_lastfm(user_id, lastfm_username, user_info):
                message = f"✅ Usuario de Last.fm configurado: {lastfm_username}"
                if user_info and user_info.get('playcount', 0) > 0:
                    message += f"\n📊 Reproducciones: {user_info['playcount']:,}"

                await status_message.edit_text(
                    message,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🎵 Abrir Last.fm", callback_data=f"lastfm_menu_{user_id}")
                    ]])
                )
            else:
                await status_message.edit_text("❌ Error al configurar el usuario de Last.fm.")

        except Exception as e:
            logger.error(f"Error configurando usuario Last.fm: {e}")
            await status_message.edit_text("❌ Error verificando el usuario. Inténtalo de nuevo.")

        del context.user_data['waiting_for_lastfm_user']
        return

    # PRIORIDAD 4: Cambio de usuario de Last.fm
    elif 'waiting_for_lastfm_change_user' in context.user_data:
        # Procesar cambio de usuario de Last.fm
        user_id = context.user_data['waiting_for_lastfm_change_user']
        lastfm_username = update.message.text.strip()

        if not lastfm_username:
            await update.message.reply_text("❌ Nombre de usuario no válido.")
            del context.user_data['waiting_for_lastfm_change_user']
            return

        if not lastfm_service:
            await update.message.reply_text("❌ Servicio de Last.fm no disponible.")
            del context.user_data['waiting_for_lastfm_change_user']
            return

        # Verificar usuario
        status_message = await update.message.reply_text(f"🔍 Verificando usuario '{lastfm_username}'...")

        try:
            if not lastfm_service.check_user_exists(lastfm_username):
                await status_message.edit_text(
                    f"❌ El usuario '{lastfm_username}' no existe en Last.fm.\n"
                    f"Verifica el nombre e inténtalo de nuevo."
                )
                del context.user_data['waiting_for_lastfm_change_user']
                return

            # Obtener información y actualizar
            user_info = lastfm_service.get_user_info(lastfm_username)

            if db.set_user_lastfm(user_id, lastfm_username, user_info):
                message = f"✅ Usuario de Last.fm actualizado: {lastfm_username}"
                if user_info and user_info.get('playcount', 0) > 0:
                    message += f"\n📊 Reproducciones: {user_info['playcount']:,}"

                await status_message.edit_text(
                    message,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Volver a Last.fm", callback_data=f"lastfm_menu_{user_id}")
                    ]])
                )
            else:
                await status_message.edit_text("❌ Error al actualizar el usuario de Last.fm.")

        except Exception as e:
            logger.error(f"Error actualizando usuario Last.fm: {e}")
            await status_message.edit_text("❌ Error verificando el usuario. Inténtalo de nuevo.")

        del context.user_data['waiting_for_lastfm_change_user']
        return

    # PRIORIDAD 5: Límite de Last.fm
    elif 'waiting_for_lastfm_limit' in context.user_data:
        # Procesar nuevo límite de Last.fm
        user_id = context.user_data['waiting_for_lastfm_limit']
        limit_text = update.message.text.strip()

        try:
            limit = int(limit_text)

            if limit < 5 or limit > 200:
                await update.message.reply_text("❌ El límite debe estar entre 5 y 200 artistas.")
                del context.user_data['waiting_for_lastfm_limit']
                return

            if db.set_lastfm_sync_limit(user_id, limit):
                await update.message.reply_text(
                    f"✅ Límite de sincronización establecido a {limit} artistas.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Volver a Last.fm", callback_data=f"lastfm_menu_{user_id}")
                    ]])
                )
            else:
                await update.message.reply_text("❌ Error al establecer el límite.")

        except ValueError:
            await update.message.reply_text("❌ Debes enviar un número válido.")

        del context.user_data['waiting_for_lastfm_limit']
        return

    # PRIORIDAD 6: Añadir artista
    elif 'waiting_for_artist_add' in context.user_data:
        # Procesar añadir artista
        user_id = context.user_data['waiting_for_artist_add']
        artist_name = update.message.text.strip()

        if not artist_name:
            await update.message.reply_text("❌ Nombre de artista no válido.")
            del context.user_data['waiting_for_artist_add']
            return

        # Simular el comando addartist
        fake_context = type('obj', (object,), {
            'args': artist_name.split(),
            'user_data': context.user_data
        })()

        fake_update = type('obj', (object,), {
            'effective_chat': type('obj', (object,), {'id': update.effective_chat.id})(),
            'message': update.message
        })()

        # Llamar al comando addartist existente
        await addartist_command(fake_update, fake_context)

        del context.user_data['waiting_for_artist_add']
        return

    # Si no hay nada esperado, no hacer nada
    else:
        logger.info(f"DEBUG: No hay handlers esperando input, user_data: {context.user_data}")
        return



async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja la entrada de texto cuando se espera configuración"""
    print(f"DEBUG: handle_text_input llamado con user_data: {context.user_data}")  # DEBUG temporal

    if 'waiting_for_lastfm_user' in context.user_data:
        # Procesar nuevo usuario de Last.fm
        user_id = context.user_data['waiting_for_lastfm_user']
        lastfm_username = update.message.text.strip()

        print(f"DEBUG: Procesando usuario Last.fm: {lastfm_username}")  # DEBUG temporal

        if not lastfm_username:
            await update.message.reply_text("❌ Nombre de usuario no válido.")
            del context.user_data['waiting_for_lastfm_user']
            return

        # Verificar que el servicio esté disponible
        if not lastfm_service:
            await update.message.reply_text("❌ Servicio de Last.fm no disponible.")
            del context.user_data['waiting_for_lastfm_user']
            return

        # Verificar que el usuario existe en Last.fm
        status_message = await update.message.reply_text(f"🔍 Verificando usuario '{lastfm_username}'...")

        try:
            if not lastfm_service.check_user_exists(lastfm_username):
                await status_message.edit_text(
                    f"❌ El usuario '{lastfm_username}' no existe en Last.fm.\n"
                    f"Verifica el nombre e inténtalo de nuevo."
                )
                del context.user_data['waiting_for_lastfm_user']
                return

            # Obtener información del usuario
            user_info = lastfm_service.get_user_info(lastfm_username)

            # Guardar en base de datos
            if db.set_user_lastfm(user_id, lastfm_username, user_info):
                message = f"✅ Usuario de Last.fm configurado: {lastfm_username}"
                if user_info and user_info.get('playcount', 0) > 0:
                    message += f"\n📊 Reproducciones: {user_info['playcount']:,}"

                await status_message.edit_text(
                    message,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🎵 Abrir Last.fm", callback_data=f"lastfm_menu_{user_id}")
                    ]])
                )
            else:
                await status_message.edit_text("❌ Error al configurar el usuario de Last.fm.")

        except Exception as e:
            logger.error(f"Error configurando usuario Last.fm: {e}")
            await status_message.edit_text("❌ Error verificando el usuario. Inténtalo de nuevo.")

        del context.user_data['waiting_for_lastfm_user']
        return

    elif 'waiting_for_lastfm_limit' in context.user_data:
        # Procesar nuevo límite de Last.fm
        user_id = context.user_data['waiting_for_lastfm_limit']
        limit_text = update.message.text.strip()

        try:
            limit = int(limit_text)

            if limit < 5 or limit > 200:
                await update.message.reply_text("❌ El límite debe estar entre 5 y 200 artistas.")
                del context.user_data['waiting_for_lastfm_limit']
                return

            if db.set_lastfm_sync_limit(user_id, limit):
                await update.message.reply_text(
                    f"✅ Límite de sincronización establecido a {limit} artistas.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Volver a Last.fm", callback_data=f"lastfm_menu_{user_id}")
                    ]])
                )
            else:
                await update.message.reply_text("❌ Error al establecer el límite.")

        except ValueError:
            await update.message.reply_text("❌ Debes enviar un número válido.")

        del context.user_data['waiting_for_lastfm_limit']
        return

    elif 'waiting_for_lastfm_change_user' in context.user_data:
        # Procesar cambio de usuario de Last.fm
        user_id = context.user_data['waiting_for_lastfm_change_user']
        lastfm_username = update.message.text.strip()

        if not lastfm_username:
            await update.message.reply_text("❌ Nombre de usuario no válido.")
            del context.user_data['waiting_for_lastfm_change_user']
            return

        if not lastfm_service:
            await update.message.reply_text("❌ Servicio de Last.fm no disponible.")
            del context.user_data['waiting_for_lastfm_change_user']
            return

        # Verificar usuario
        status_message = await update.message.reply_text(f"🔍 Verificando usuario '{lastfm_username}'...")

        try:
            if not lastfm_service.check_user_exists(lastfm_username):
                await status_message.edit_text(
                    f"❌ El usuario '{lastfm_username}' no existe en Last.fm.\n"
                    f"Verifica el nombre e inténtalo de nuevo."
                )
                del context.user_data['waiting_for_lastfm_change_user']
                return

            # Obtener información y actualizar
            user_info = lastfm_service.get_user_info(lastfm_username)

            if db.set_user_lastfm(user_id, lastfm_username, user_info):
                message = f"✅ Usuario de Last.fm actualizado: {lastfm_username}"
                if user_info and user_info.get('playcount', 0) > 0:
                    message += f"\n📊 Reproducciones: {user_info['playcount']:,}"

                await status_message.edit_text(
                    message,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Volver a Last.fm", callback_data=f"lastfm_menu_{user_id}")
                    ]])
                )
            else:
                await status_message.edit_text("❌ Error al actualizar el usuario de Last.fm.")

        except Exception as e:
            logger.error(f"Error actualizando usuario Last.fm: {e}")
            await status_message.edit_text("❌ Error verificando el usuario. Inténtalo de nuevo.")

        del context.user_data['waiting_for_lastfm_change_user']
        return

    # Resto de handlers de texto existentes (notificaciones, países, etc.)
    elif 'waiting_for_time' in context.user_data:
        # ... código existente para notificaciones ...
        pass

    elif 'waiting_for_country_add' in context.user_data:
        # ... código existente para países ...
        pass

    # Si no hay nada esperado, no hacer nada
    else:
        print(f"DEBUG: No hay handlers esperando input, user_data: {context.user_data}")  # DEBUG temporal




async def country_delete_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja la eliminación de países específicos"""
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    country_code = parts[2]
    user_id = int(parts[3])

    if country_state_city:
        success = country_state_city.remove_user_country(user_id, country_code)
        if success:
            country_info = country_state_city.get_country_info(country_code)
            country_name = country_info['name'] if country_info else country_code
            message = f"✅ País {country_name} ({country_code}) eliminado correctamente."
        else:
            message = f"❌ Error al eliminar el país {country_code}."
    else:
        message = "❌ Sistema de países múltiples no disponible."

    keyboard = [[InlineKeyboardButton("🔙 Volver al menú", callback_data=f"config_countries_{user_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, reply_markup=reply_markup)

async def artist_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja las acciones relacionadas con artistas desde el menú de configuración"""
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    action = parts[1]
    user_id = int(parts[2])

    if action == "add":
        message = (
            "➕ *Añadir artista*\n\n"
            "Envía el nombre del artista que quieres seguir.\n"
            "Ejemplo: Radiohead, Metallica, Taylor Swift\n\n"
            "Responde a este mensaje con el nombre del artista."
        )
        context.user_data['waiting_for_artist_add'] = user_id

    elif action == "search":
        message = (
            "🔍 *Buscar conciertos*\n\n"
            "Buscando conciertos de todos tus artistas seguidos...\n"
            "Esto puede tardar un momento."
        )
        # Ejecutar búsqueda de conciertos (equivalente a /search)
        # Crear un update falso para reutilizar la función existente
        fake_update = type('obj', (object,), {
            'effective_chat': type('obj', (object,), {'id': query.message.chat_id})(),
            'message': type('obj', (object,), {
                'reply_text': lambda text, **kwargs: query.message.reply_text(text, **kwargs)
            })()
        })()

        # Llamar al comando search existente
        await search_command(fake_update, context)
        return

    keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data=f"config_artists_{user_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)



async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /search - VERSIÓN EXTENDIDA con países múltiples"""
    chat_id = update.effective_chat.id

    # Verificar que el usuario esté registrado
    user = db.get_user_by_chat_id(chat_id)
    if not user:
        await update.message.reply_text(
            "❌ Primero debes registrarte con `/adduser <tu_nombre>`"
        )
        return

    # Obtener configuración de servicios del usuario (versión extendida)
    user_services = db.get_user_services(user['id'])

    # Verificar que tenga al menos un servicio activo
    active_services = [s for s, active in user_services.items() if active and s not in ['country_filter', 'countries']]
    if not active_services:
        await update.message.reply_text(
            "❌ No tienes ningún servicio de búsqueda activo.\n"
            "Usa `/serviceon <servicio>` para activar al menos uno.\n"
            "Servicios disponibles: ticketmaster, spotify, setlistfm"
        )
        return

    # Verificar que tenga países configurados
    user_countries = user_services.get('countries', set())
    if not user_countries:
        await update.message.reply_text(
            "❌ No tienes países configurados.\n"
            "Usa `/addcountry <país>` para añadir países.\n"
            "Ejemplo: `/addcountry ES`"
        )
        return

    # Mensaje de estado
    services_text = ", ".join(active_services)
    countries_text = ", ".join(sorted(user_countries))
    status_message = await update.message.reply_text(
        f"🔍 Buscando conciertos de tus artistas seguidos...\n"
        f"🔧 Servicios activos: {services_text}\n"
        f"🌍 Países: {countries_text}"
    )

    try:
        # Actualizar base de datos con nuevos conciertos
        followed_artists = db.get_user_followed_artists(user['id'])

        if not followed_artists:
            await status_message.edit_text(
                "📭 No tienes artistas seguidos aún.\n"
                "Usa `/addartist` para seguir artistas."
            )
            return

        total_new_concerts = 0
        for artist in followed_artists:
            concerts = await search_concerts_for_artist(
                artist['name'],
                user_services,
                user_id=user['id']  # Pasar user_id para filtrado
            )
            for concert in concerts:
                concert_id = db.save_concert(concert)
                if concert_id:
                    total_new_concerts += 1
            await asyncio.sleep(0.5)  # Pausa corta

        # Obtener todos los conciertos para el usuario
        all_concerts = db.get_all_concerts_for_user(user['id'])

        # Filtrar adicional por países si es necesario
        if country_state_city:
            extended_db = ArtistTrackerDatabaseExtended(db.db_path, country_state_city)
            all_concerts = extended_db.filter_concerts_by_countries(all_concerts, user_countries)

        # Agrupar conciertos por artista
        concerts_by_artist = {}
        for concert in all_concerts:
            artist_name = concert.get('artist_name', 'Artista desconocido')
            if artist_name not in concerts_by_artist:
                concerts_by_artist[artist_name] = []
            concerts_by_artist[artist_name].append(concert)

        # Actualizar mensaje de estado
        await status_message.edit_text(
            f"✅ Búsqueda completada!\n"
            f"📊 {len(concerts_by_artist)} artistas con conciertos\n"
            f"🎵 {len(all_concerts)} conciertos en total\n"
            f"🆕 {total_new_concerts} nuevos conciertos\n\n"
            f"Enviando resultados por artista..."
        )

        # Enviar un mensaje por cada artista con conciertos
        artists_with_concerts = 0
        for artist_name, artist_concerts in concerts_by_artist.items():
            if artist_concerts:  # Solo enviar si tiene conciertos
                # Formatear mensaje del artista
                message = format_single_artist_concerts_complete(
                    artist_concerts,
                    artist_name,
                    show_notified=True
                )

                # Dividir en chunks si es muy largo
                if len(message) > 4000:
                    chunks = split_long_message(message, max_length=4000)
                    for i, chunk in enumerate(chunks):
                        await update.message.reply_text(
                            chunk,
                            parse_mode='Markdown',
                            disable_web_page_preview=True
                        )
                else:
                    await update.message.reply_text(
                        message,
                        parse_mode='Markdown',
                        disable_web_page_preview=True
                    )

                artists_with_concerts += 1
                await asyncio.sleep(0.3)  # Pausa breve entre mensajes

        # Mensaje final de resumen
        if artists_with_concerts == 0:
            await update.message.reply_text(
                f"📭 No se encontraron conciertos en tus países configurados ({countries_text}).\n"
                f"Prueba añadir más países con `/addcountry`"
            )
        else:
            summary_message = (
                f"🎉 *Búsqueda completada*\n\n"
                f"📊 Artistas con conciertos: {artists_with_concerts}\n"
                f"🎵 Total de conciertos: {len(all_concerts)}\n"
                f"🆕 Nuevos conciertos encontrados: {total_new_concerts}\n"
                f"🌍 Países consultados: {countries_text}\n\n"
                f"💡 Usa `/showartist <nombre>` para ver todos los conciertos de un artista específico"
            )
            await update.message.reply_text(
                summary_message,
                parse_mode='Markdown'
            )

    except Exception as e:
        logger.error(f"Error en comando search: {e}")
        await status_message.edit_text(
            "❌ Error al buscar conciertos. Inténtalo de nuevo más tarde."
        )


async def send_notifications():
    """Envía notificaciones diarias a los usuarios"""
    logger.info("ADVERTENCIA: Esta función está deshabilitada.")
    logger.info("Use el script notification_scheduler.py para las notificaciones.")

def schedule_notifications():
    """Programa las notificaciones para cada usuario según su hora configurada"""
    logger.info("ADVERTENCIA: Sistema de notificaciones interno deshabilitado.")
    logger.info("Use el script notification_scheduler.py para las notificaciones.")

async def send_user_notification(user_id: int):
    """Envía notificación a un usuario específico"""
    logger.info("ADVERTENCIA: Esta función está deshabilitada.")
    logger.info("Use el script notification_scheduler.py para las notificaciones.")

def run_scheduler():
    """Ejecuta el programador de tareas en un hilo separado"""
    logger.info("ADVERTENCIA: Programador interno deshabilitado.")
    logger.info("Use el script notification_scheduler.py para las notificaciones.")

def validate_services():
    """Valida que los servicios están configurados correctamente"""
    issues = []

    try:
        from apis.mb_artist_info import search_artist_in_musicbrainz
        logger.info("✅ MusicBrainz configurado correctamente")
    except ImportError:
        issues.append("⚠️ MusicBrainz (mb_artist_info.py) no disponible")

    if not ticketmaster_service:
        issues.append("⚠️ Ticketmaster service no inicializado")

    if not spotify_service:
        issues.append("⚠️ Spotify service no inicializado")

    if not setlistfm_service:
        issues.append("⚠️ Setlist.fm service no inicializado")

    if not lastfm_service:
        issues.append("⚠️ Last.fm service no inicializado")

    if issues:
        logger.warning("Problemas de configuración detectados:")
        for issue in issues:
            logger.warning(issue)
    else:
        logger.info("✅ Todos los servicios están configurados")

    return len(issues) == 0

# Variable global para la aplicación
application = None

async def lastfm_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /lastfm - gestión de sincronización con Last.fm"""
    if not lastfm_service:
        await update.message.reply_text(
            "❌ Servicio de Last.fm no disponible.\n"
            "Contacta al administrador para configurar la API key."
        )
        return

    chat_id = update.effective_chat.id

    # Verificar que el usuario esté registrado
    user = db.get_user_by_chat_id(chat_id)
    if not user:
        await update.message.reply_text(
            "❌ Primero debes registrarte con `/adduser <tu_nombre>`"
        )
        return

    # Verificar si ya tiene usuario de Last.fm configurado
    lastfm_user = db.get_user_lastfm(user['id'])

    if not lastfm_user:
        # No tiene usuario configurado, pedirlo
        # CORREGIDO: Marcar que estamos esperando el usuario de Last.fm
        context.user_data['waiting_for_lastfm_user'] = user['id']
        await show_lastfm_setup(update, user, context)
    else:
        # Ya tiene usuario, mostrar menú principal
        await show_lastfm_menu(update, user, lastfm_user)


async def show_lastfm_setup(update: Update, user: Dict, context: ContextTypes.DEFAULT_TYPE = None):
    """Muestra el setup inicial de Last.fm"""
    message = (
        "🎵 *Configuración de Last.fm*\n\n"
        "Para sincronizar tus artistas más escuchados desde Last.fm, "
        "necesito tu nombre de usuario.\n\n"
        "Envía tu nombre de usuario de Last.fm:"
    )

    keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data=f"lastfm_cancel_{user['id']}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        message,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def show_lastfm_menu(update: Update, user: Dict, lastfm_user: Dict):
    """Muestra el menú principal de Last.fm"""
    username = lastfm_user['lastfm_username']
    playcount = lastfm_user.get('lastfm_playcount', 0)
    sync_limit = lastfm_user.get('sync_limit', 20)

    message = (
        f"🎵 *Last.fm - {username}*\n\n"
        f"📊 Reproducciones: {playcount:,}\n"
        f"🔢 Límite de sincronización: {sync_limit} artistas\n\n"
        f"Selecciona el período para sincronizar:"
    )

    keyboard = [
        [
            InlineKeyboardButton("🌟 De siempre", callback_data=f"lastfm_period_overall_{user['id']}"),
            InlineKeyboardButton("📅 Último año", callback_data=f"lastfm_period_12month_{user['id']}")
        ],
        [
            InlineKeyboardButton("📊 Último mes", callback_data=f"lastfm_period_1month_{user['id']}"),
            InlineKeyboardButton("⚡ Última semana", callback_data=f"lastfm_period_7day_{user['id']}")
        ],
        [
            InlineKeyboardButton("🔢 Cambiar cantidad", callback_data=f"lastfm_limit_{user['id']}"),
            InlineKeyboardButton("👤 Cambiar usuario", callback_data=f"lastfm_changeuser_{user['id']}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        message,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def lastfm_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja todos los callbacks de Last.fm"""
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    logger.info(f"Last.fm callback recibido: {callback_data}")

    # Parsear callback data
    parts = callback_data.split("_")
    if len(parts) < 3 or parts[0] != "lastfm":
        return

    action = parts[1]

    # Obtener user_id del final
    try:
        user_id = int(parts[-1])
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Error de usuario.")
        return

    # Verificar que el usuario existe
    user = db.get_user_by_chat_id(query.message.chat_id)
    if not user or user['id'] != user_id:
        await query.edit_message_text("❌ Error de autenticación.")
        return

    try:
        if action == "cancel":
            await query.edit_message_text("❌ Configuración de Last.fm cancelada.")

        elif action == "period":
            period = parts[2]
            await handle_lastfm_period_selection(query, user, period)

        elif action == "page":
            # NUEVO: Manejar paginación
            period = parts[2]
            page = int(parts[3])

            # Obtener artistas pendientes
            artists = db.get_pending_lastfm_sync(user['id'], period)
            if not artists:
                await query.edit_message_text("❌ No hay datos de artistas disponibles.")
                return

            await show_lastfm_artists_page(query, user, period, artists, page)

        elif callback_data == "current_lastfm_page":
            # No hacer nada si presiona el botón de página actual
            return

        elif action == "sync":
            period = parts[2]
            await handle_lastfm_do_sync(query, user, period)

        elif action == "limit":
            await handle_lastfm_change_limit(query, user, context)

        elif action == "changeuser":
            await handle_lastfm_change_user(query, user, context)

        else:
            await query.edit_message_text("❌ Acción no reconocida.")

    except Exception as e:
        logger.error(f"Error en lastfm_callback_handler: {e}")
        await query.edit_message_text("❌ Error procesando la solicitud.")

async def handle_lastfm_period_selection(query, user: Dict, period: str):
    """Maneja la selección de período de Last.fm"""
    if not lastfm_service:
        await query.edit_message_text("❌ Servicio de Last.fm no disponible.")
        return

    # Obtener usuario de Last.fm
    lastfm_user = db.get_user_lastfm(user['id'])
    if not lastfm_user:
        await query.edit_message_text("❌ No tienes usuario de Last.fm configurado.")
        return

    username = lastfm_user['lastfm_username']
    sync_limit = lastfm_user.get('sync_limit', 20)

    # Mensaje de estado
    period_name = lastfm_service.get_period_display_name(period)
    await query.edit_message_text(
        f"🔍 Obteniendo top artistas de {username} ({period_name})...\n"
        f"Esto puede tardar un momento."
    )

    try:
        # Obtener artistas de Last.fm
        artists, status_message = lastfm_service.get_top_artists(username, period, sync_limit)

        if not artists:
            await query.edit_message_text(
                f"📭 No se encontraron artistas para el período {period_name}.\n"
                f"Estado: {status_message}"
            )
            return

        # Guardar selección pendiente
        db.save_pending_lastfm_sync(user['id'], period, artists)

        # CAMBIO: Mostrar primera página en lugar de preview
        await show_lastfm_artists_page(query, user, period, artists, page=0)

    except Exception as e:
        logger.error(f"Error obteniendo artistas de Last.fm: {e}")
        await query.edit_message_text(
            f"❌ Error obteniendo artistas de {username}.\n"
            f"Inténtalo de nuevo más tarde."
        )

async def show_lastfm_artists_page(query, user: Dict, period: str, artists: List[Dict], page: int = 0):
    """
    Muestra una página de artistas de Last.fm con paginación

    Args:
        query: Query del callback
        user: Usuario de la base de datos
        period: Período de Last.fm
        artists: Lista completa de artistas
        page: Número de página (empezando desde 0)
    """
    artists_per_page = 15  # Mostrar 15 artistas por página
    total_pages = (len(artists) + artists_per_page - 1) // artists_per_page

    if page >= total_pages:
        page = total_pages - 1
    elif page < 0:
        page = 0

    start_idx = page * artists_per_page
    end_idx = min(start_idx + artists_per_page, len(artists))
    page_artists = artists[start_idx:end_idx]

    # Obtener nombre del período
    period_name = lastfm_service.get_period_display_name(period) if lastfm_service else period
    username = db.get_user_lastfm(user['id'])['lastfm_username']

    # Construir texto
    message_lines = [
        f"🎵 *Top artistas de {username}*",
        f"📊 Período: {period_name}",
        f"🔢 Total encontrados: {len(artists)} artistas",
        f"📄 Página {page + 1} de {total_pages}\n"
    ]

    # Contar artistas con MBID en esta página
    mbid_count = sum(1 for artist in page_artists if artist.get("mbid"))

    for i, artist in enumerate(page_artists, start_idx + 1):
        playcount = artist.get("playcount", 0)
        name = artist.get("name", "Nombre desconocido")
        mbid = artist.get("mbid", "")

        # Escapar caracteres especiales para Markdown
        safe_name = name.replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")

        line = f"{i}. *{safe_name}*"

        # Añadir información de reproducción
        if playcount > 0:
            line += f" ({playcount:,} reproducciones)"

        # Indicar si tiene MBID
        if mbid:
            line += " 🎵"  # Emoji para indicar que tiene MBID

        # Añadir géneros si están disponibles
        genres = artist.get("genres", [])
        if genres:
            genre_text = ", ".join(genres[:2])  # Mostrar hasta 2 géneros
            line += f" _{genre_text}_"

        message_lines.append(line)

    message_lines.append("")
    message_lines.append(f"🎵 {mbid_count}/{len(page_artists)} artistas con MBID para sincronización precisa")

    # Crear botones de navegación
    keyboard = []
    nav_buttons = []

    # Botón anterior
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton("⬅️ Anterior", callback_data=f"lastfm_page_{period}_{page-1}_{user['id']}")
        )

    # Botón de página actual
    nav_buttons.append(
        InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data="current_lastfm_page")
    )

    # Botón siguiente
    if page < total_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton("Siguiente ➡️", callback_data=f"lastfm_page_{period}_{page+1}_{user['id']}")
        )

    if nav_buttons:
        keyboard.append(nav_buttons)

    # Botón para confirmar sincronización
    keyboard.append([
        InlineKeyboardButton("✅ Sincronizar todos", callback_data=f"lastfm_sync_{period}_{user['id']}")
    ])

    # Botón para cancelar
    keyboard.append([
        InlineKeyboardButton("❌ Cancelar", callback_data=f"lastfm_cancel_{user['id']}")
    ])

    message = "\n".join(message_lines)
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )




async def handle_lastfm_do_sync(query, user: Dict, period: str):
    """Realiza la sincronización de artistas de Last.fm usando MBID cuando esté disponible"""
    # Obtener artistas pendientes
    artists = db.get_pending_lastfm_sync(user['id'], period)
    if not artists:
        await query.edit_message_text("❌ No hay sincronización pendiente.")
        return

    period_name = lastfm_service.get_period_display_name(period) if lastfm_service else period

    # Mensaje de estado
    await query.edit_message_text(
        f"⏳ Sincronizando {len(artists)} artistas de Last.fm...\n"
        f"Esto puede tardar un momento."
    )

    try:
        added_count = 0
        skipped_count = 0
        error_count = 0
        mbid_used_count = 0
        mbid_available_count = 0

        total_artists = len(artists)
        processed = 0

        for artist_data in artists:
            artist_name = artist_data.get('name', '')
            artist_mbid = artist_data.get('mbid', '')

            processed += 1

            # Actualizar mensaje de progreso cada 5 artistas
            if processed % 5 == 0 or processed == total_artists:
                progress_msg = (
                    f"⏳ Sincronizando {total_artists} artistas de Last.fm...\n"
                    f"Progreso: {processed}/{total_artists}\n"
                    f"✅ Añadidos: {added_count} | ⏭️ Ya seguidos: {skipped_count} | ❌ Errores: {error_count}"
                )
                try:
                    await query.edit_message_text(progress_msg)
                except:
                    pass  # Ignorar errores de edición (rate limit)

            if not artist_name:
                error_count += 1
                continue

            try:
                artist_id = None

                # Estrategia 1: Si tenemos MBID, intentar usarlo directamente
                if artist_mbid:
                    mbid_available_count += 1
                    artist_id = db.get_artist_by_mbid(artist_mbid)

                    if artist_id:
                        print(f"✅ Artista encontrado por MBID: {artist_name} ({artist_mbid})")
                        mbid_used_count += 1
                    else:
                        # Crear artista usando MBID directamente
                        candidate = {
                            'mbid': artist_mbid,
                            'name': artist_name,
                            'type': '',
                            'country': '',
                            'disambiguation': '',
                            'score': 100  # Score alto porque viene de Last.fm
                        }

                        # Añadir información extra de Last.fm si está disponible
                        if 'genres' in artist_data:
                            candidate['genres'] = artist_data['genres']
                        if 'listeners' in artist_data:
                            candidate['listeners'] = artist_data['listeners']

                        artist_id = db.create_artist_from_candidate(candidate)
                        if artist_id:
                            print(f"✅ Artista creado con MBID: {artist_name} ({artist_mbid})")
                            mbid_used_count += 1

                # Estrategia 2: Si no hay MBID o falló, usar búsqueda tradicional
                if not artist_id:
                    candidates = db.search_artist_candidates(artist_name)

                    if not candidates:
                        skipped_count += 1
                        print(f"⚠️ No se encontraron candidatos para: {artist_name}")
                        continue

                    # Usar el mejor candidato
                    best_candidate = candidates[0]
                    artist_id = db.create_artist_from_candidate(best_candidate)

                    if artist_id:
                        print(f"✅ Artista creado por búsqueda: {artist_name}")

                if not artist_id:
                    error_count += 1
                    print(f"❌ Error creando artista: {artist_name}")
                    continue

                # Añadir a seguimiento
                was_new = db.add_followed_artist(user['id'], artist_id)

                if was_new:
                    added_count += 1
                else:
                    skipped_count += 1  # Ya lo seguía

                # Pausa breve para no sobrecargar
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Error procesando artista {artist_name}: {e}")
                error_count += 1
                continue

        # Limpiar sincronización pendiente
        db.clear_pending_lastfm_sync(user['id'], period)

        # Mensaje de resultado detallado
        message = (
            f"✅ *Sincronización de Last.fm completada*\n\n"
            f"📊 Período: {period_name}\n"
            f"➕ Artistas añadidos: {added_count}\n"
            f"⏭️ Ya seguidos: {skipped_count}\n"
        )

        if error_count > 0:
            message += f"❌ Errores: {error_count}\n"

        message += f"\n🎯 *Estadísticas de MBID:*\n"
        message += f"📋 Artistas con MBID: {mbid_available_count}/{total_artists}\n"
        message += f"🎵 Sincronizados via MBID: {mbid_used_count}\n"

        # Calcular porcentaje de éxito
        success_rate = ((added_count + skipped_count) / total_artists) * 100 if total_artists > 0 else 0
        message += f"📈 Tasa de éxito: {success_rate:.1f}%\n"

        message += f"\nUsa `/list` para ver todos tus artistas seguidos."

        keyboard = [[InlineKeyboardButton("🔙 Volver a Last.fm", callback_data=f"lastfm_menu_{user['id']}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

    except Exception as e:
        logger.error(f"Error en sincronización de Last.fm: {e}")
        await query.edit_message_text("❌ Error durante la sincronización. Inténtalo de nuevo.")


async def handle_lastfm_change_limit(query, user: Dict, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el cambio de límite de sincronización"""
    message = (
        "🔢 *Cambiar cantidad de artistas*\n\n"
        "Envía el número de artistas que quieres sincronizar por período.\n"
        "Rango permitido: 5-200 artistas\n\n"
        "Ejemplo: 50"
    )

    keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data=f"lastfm_cancel_{user['id']}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # CORREGIDO: Marcar que estamos esperando el límite
    context.user_data['waiting_for_lastfm_limit'] = user['id']

    await query.edit_message_text(
        message,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def handle_lastfm_change_user(query, user: Dict, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el cambio de usuario de Last.fm"""
    message = (
        "👤 *Cambiar usuario de Last.fm*\n\n"
        "Envía tu nuevo nombre de usuario de Last.fm:"
    )

    keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data=f"lastfm_cancel_{user['id']}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Marcar que estamos esperando el nuevo usuario
    context.user_data['waiting_for_lastfm_change_user'] = user['id']

    await query.edit_message_text(
        message,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def lastfm_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Vuelve al menú principal de Last.fm"""
    query = update.callback_query
    await query.answer()

    user_id = int(query.data.split("_")[-1])
    user = db.get_user_by_chat_id(query.message.chat_id)

    if not user or user['id'] != user_id:
        await query.edit_message_text("❌ Error de autenticación.")
        return

    lastfm_user = db.get_user_lastfm(user['id'])
    if not lastfm_user:
        await query.edit_message_text("❌ No tienes usuario de Last.fm configurado.")
        return

    # Mostrar menú principal
    fake_update = type('obj', (object,), {'message': query.message})()
    await show_lastfm_menu(fake_update, user, lastfm_user)



def main():
    """Función principal MODIFICADA para incluir sistema de países"""
    global db, application, country_state_city

    # Configuración
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_CONCIERTOS')
    DB_PATH = os.getenv('DB_PATH', 'artist_tracker.db')
    CACHE_DIR = os.getenv('CACHE_DIR', './cache')

    if not TELEGRAM_TOKEN:
        logger.error("❌ No se ha configurado TELEGRAM_BOT_CONCIERTOS en las variables de entorno")
        return

    # Inicializar base de datos
    db = ArtistTrackerDatabase(DB_PATH)

    # Inicializar servicios de conciertos
    initialize_concert_services()

    # Inicializar servicio de países
    initialize_country_service()

    # Inicializar servicio de Lastfm
    initialize_lastfm_service()

    # Configurar MusicBrainz si está disponible
    user_agent = {
        "app": "ArtistTrackerBot",
        "version": "1.0",
        "contact": "dev@example.com"
    }

    try:
        setup_musicbrainz(user_agent=user_agent, cache_directory=CACHE_DIR)
        logger.info("MusicBrainz configurado correctamente")
    except Exception as e:
        logger.warning(f"MusicBrainz no disponible: {e}")

    # Validar servicios
    validate_services()

    # Crear la aplicación y agregar handlers
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Handlers de comandos básicos
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("adduser", adduser_command))
    application.add_handler(CommandHandler("addartist", addartist_command))
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(CommandHandler("remove", remove_command))
    application.add_handler(CommandHandler("notify", notify_command))

    # Handlers de búsqueda
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(CommandHandler("searchartist", searchartist_command))
    application.add_handler(CommandHandler("showartist", showartist_command))

    # Handlers de servicios
    application.add_handler(CommandHandler("serviceon", serviceon_command))
    application.add_handler(CommandHandler("serviceoff", serviceoff_command))

    # Handlers de países
    application.add_handler(CommandHandler("country", country_command))
    application.add_handler(CommandHandler("addcountry", addcountry_command))
    application.add_handler(CommandHandler("removecountry", removecountry_command))
    application.add_handler(CommandHandler("mycountries", mycountries_command))
    application.add_handler(CommandHandler("listcountries", listcountries_command))
    application.add_handler(CommandHandler("refreshcountries", refreshcountries_command))

    # Handler de configuración
    application.add_handler(CommandHandler("config", config_command))

    # Handler de Last.fm
    application.add_handler(CommandHandler("lastfm", lastfm_command))

    # IMPORTANTE: Los handlers de callback deben ir en orden específico para evitar conflictos

    # Handlers específicos de Last.fm (DEBEN IR ANTES que los genéricos)
    application.add_handler(CallbackQueryHandler(lastfm_callback_handler, pattern="^lastfm_"))
    application.add_handler(CallbackQueryHandler(lastfm_menu_callback, pattern="^lastfm_menu_"))

    # Handlers específicos de otros sistemas
    application.add_handler(CallbackQueryHandler(artist_selection_callback, pattern="^(select_artist_|cancel_artist_selection)"))
    application.add_handler(CallbackQueryHandler(country_selection_callback, pattern="^(select_country_|cancel_country_selection)"))
    application.add_handler(CallbackQueryHandler(expand_concerts_callback, pattern="^(expand_all_|back_to_search_)"))
    application.add_handler(CallbackQueryHandler(show_artist_concerts_callback, pattern="^show_artist_concerts_"))
    application.add_handler(CallbackQueryHandler(back_to_summary_callback, pattern="^back_to_summary_"))

    # Handler genérico de configuración (DEBE IR AL FINAL de los callbacks)
    application.add_handler(CallbackQueryHandler(config_callback_handler, pattern="^(config_|notif_|country_|service_|artist_)"))

    # Handler de texto (DEBE SER EL ÚLTIMO)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))

    # Iniciar el bot
    logger.info("🤖 Bot de seguimiento de artistas iniciado con sistema de países múltiples.")
    if country_state_city:
        logger.info("✅ Sistema de países múltiples activado")
    else:
        logger.info("⚠️ Sistema de países múltiples no disponible (falta API key)")

    logger.info("🔔 Para notificaciones, ejecuta: python notification_scheduler.py")
    logger.info("Presiona Ctrl+C para detenerlo.")


    try:
        application.run_polling()
    except KeyboardInterrupt:
        logger.info("🛑 Bot detenido por el usuario")
    except Exception as e:
        logger.error(f"❌ Error crítico en el bot: {e}")

if __name__ == "__main__":
    main()
