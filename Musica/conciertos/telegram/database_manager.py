#!/usr/bin/env python3
"""
Database Manager para el Bot de Conciertos
Maneja usuarios, artistas favoritos y notificaciones de conciertos
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import json

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class ConcertBotDatabase:
    """Maneja la base de datos del bot de conciertos"""

    def __init__(self, db_path: str = "concert_bot.db"):
        """
        Inicializa la conexión a la base de datos

        Args:
            db_path: Ruta al archivo de base de datos SQLite
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Crear las tablas si no existen
        self._init_database()

    def _init_database(self):
        """Crea las tablas necesarias en la base de datos"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Tabla de usuarios
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    country_code TEXT DEFAULT 'ES',
                    language_code TEXT DEFAULT 'es',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    notifications_enabled BOOLEAN DEFAULT 1
                )
            """)

            # Tabla de artistas favoritos de usuarios
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_artists (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    artist_name TEXT NOT NULL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    notifications_enabled BOOLEAN DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    UNIQUE(user_id, artist_name)
                )
            """)

            # Tabla de conciertos encontrados
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS concerts (
                    id INTEGER PRIMARY KEY,
                    artist_name TEXT NOT NULL,
                    concert_name TEXT NOT NULL,
                    venue TEXT,
                    city TEXT,
                    country TEXT,
                    date TEXT,
                    time TEXT,
                    url TEXT,
                    image_url TEXT,
                    source TEXT NOT NULL,
                    external_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(artist_name, venue, city, date, source)
                )
            """)

            # Tabla de notificaciones enviadas
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notifications_sent (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    concert_id INTEGER NOT NULL,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    notification_type TEXT DEFAULT 'new_concert',
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (concert_id) REFERENCES concerts (id),
                    UNIQUE(user_id, concert_id)
                )
            """)

            # Tabla de búsquedas programadas
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scheduled_searches (
                    id INTEGER PRIMARY KEY,
                    artist_name TEXT NOT NULL,
                    country_code TEXT NOT NULL,
                    last_search TIMESTAMP,
                    next_search TIMESTAMP,
                    active BOOLEAN DEFAULT 1,
                    UNIQUE(artist_name, country_code)
                )
            """)

            # Crear índices para optimizar consultas
            self._create_indexes(cursor)

            conn.commit()
            logger.info("Base de datos inicializada correctamente")

    def _create_indexes(self, cursor):
        """Crea índices para optimizar las consultas"""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)",
            "CREATE INDEX IF NOT EXISTS idx_user_artists_user_id ON user_artists(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_user_artists_artist_name ON user_artists(artist_name)",
            "CREATE INDEX IF NOT EXISTS idx_concerts_artist_name ON concerts(artist_name)",
            "CREATE INDEX IF NOT EXISTS idx_concerts_date ON concerts(date)",
            "CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications_sent(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_notifications_concert_id ON notifications_sent(concert_id)",
            "CREATE INDEX IF NOT EXISTS idx_scheduled_searches_next_search ON scheduled_searches(next_search)"
        ]

        for index in indexes:
            try:
                cursor.execute(index)
            except sqlite3.Error as e:
                logger.warning(f"Error creando índice: {e}")

    # ==================== GESTIÓN DE USUARIOS ====================

    def add_or_update_user(self, telegram_id: int, username: str = None,
                          first_name: str = None, last_name: str = None,
                          language_code: str = 'es') -> int:
        """
        Añade un nuevo usuario o actualiza uno existente

        Args:
            telegram_id: ID de Telegram del usuario
            username: Nombre de usuario de Telegram
            first_name: Nombre del usuario
            last_name: Apellido del usuario
            language_code: Código de idioma del usuario

        Returns:
            ID del usuario en la base de datos
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Verificar si el usuario ya existe
            cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,))
            result = cursor.fetchone()

            if result:
                # Actualizar usuario existente
                user_id = result[0]
                cursor.execute("""
                    UPDATE users
                    SET username = ?, first_name = ?, last_name = ?,
                        language_code = ?, last_active = CURRENT_TIMESTAMP
                    WHERE telegram_id = ?
                """, (username, first_name, last_name, language_code, telegram_id))
                logger.info(f"Usuario actualizado: {telegram_id}")
            else:
                # Crear nuevo usuario
                cursor.execute("""
                    INSERT INTO users (telegram_id, username, first_name, last_name, language_code)
                    VALUES (?, ?, ?, ?, ?)
                """, (telegram_id, username, first_name, last_name, language_code))
                user_id = cursor.lastrowid
                logger.info(f"Nuevo usuario creado: {telegram_id} (ID: {user_id})")

            conn.commit()
            return user_id

    def get_user(self, telegram_id: int) -> Optional[Dict]:
        """
        Obtiene información de un usuario

        Args:
            telegram_id: ID de Telegram del usuario

        Returns:
            Diccionario con datos del usuario o None si no existe
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            result = cursor.fetchone()

            if result:
                return dict(result)
            return None

    def update_user_country(self, telegram_id: int, country_code: str) -> bool:
        """
        Actualiza el país de un usuario

        Args:
            telegram_id: ID de Telegram del usuario
            country_code: Código de país (ES, US, etc.)

        Returns:
            True si se actualizó correctamente
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE users
                SET country_code = ?, last_active = CURRENT_TIMESTAMP
                WHERE telegram_id = ?
            """, (country_code, telegram_id))

            success = cursor.rowcount > 0
            conn.commit()

            if success:
                logger.info(f"País actualizado para usuario {telegram_id}: {country_code}")

            return success

    def toggle_user_notifications(self, telegram_id: int) -> bool:
        """
        Activa/desactiva las notificaciones para un usuario

        Args:
            telegram_id: ID de Telegram del usuario

        Returns:
            Estado actual de las notificaciones (True = activadas)
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Obtener estado actual
            cursor.execute("SELECT notifications_enabled FROM users WHERE telegram_id = ?", (telegram_id,))
            result = cursor.fetchone()

            if result:
                new_state = not bool(result[0])
                cursor.execute("""
                    UPDATE users
                    SET notifications_enabled = ?, last_active = CURRENT_TIMESTAMP
                    WHERE telegram_id = ?
                """, (new_state, telegram_id))
                conn.commit()

                logger.info(f"Notificaciones {'activadas' if new_state else 'desactivadas'} para usuario {telegram_id}")
                return new_state

            return False

    # ==================== GESTIÓN DE ARTISTAS FAVORITOS ====================

    def add_favorite_artist(self, telegram_id: int, artist_name: str) -> bool:
        """
        Añade un artista a los favoritos de un usuario

        Args:
            telegram_id: ID de Telegram del usuario
            artist_name: Nombre del artista

        Returns:
            True si se añadió correctamente, False si ya existía
        """
        user = self.get_user(telegram_id)
        if not user:
            return False

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            try:
                cursor.execute("""
                    INSERT INTO user_artists (user_id, artist_name)
                    VALUES (?, ?)
                """, (user['id'], artist_name))

                # Añadir a búsquedas programadas
                self._add_to_scheduled_searches(artist_name, user['country_code'])

                conn.commit()
                logger.info(f"Artista favorito añadido: {artist_name} para usuario {telegram_id}")
                return True

            except sqlite3.IntegrityError:
                # El artista ya está en favoritos
                logger.info(f"Artista {artist_name} ya está en favoritos de usuario {telegram_id}")
                return False

    def remove_favorite_artist(self, telegram_id: int, artist_name: str) -> bool:
        """
        Elimina un artista de los favoritos de un usuario

        Args:
            telegram_id: ID de Telegram del usuario
            artist_name: Nombre del artista

        Returns:
            True si se eliminó correctamente
        """
        user = self.get_user(telegram_id)
        if not user:
            return False

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                DELETE FROM user_artists
                WHERE user_id = ? AND artist_name = ?
            """, (user['id'], artist_name))

            success = cursor.rowcount > 0
            conn.commit()

            if success:
                logger.info(f"Artista favorito eliminado: {artist_name} para usuario {telegram_id}")
                # Verificar si algún otro usuario tiene este artista para limpieza
                self._cleanup_scheduled_searches(artist_name, user['country_code'])

            return success

    def get_user_favorite_artists(self, telegram_id: int) -> List[Dict]:
        """
        Obtiene la lista de artistas favoritos de un usuario

        Args:
            telegram_id: ID de Telegram del usuario

        Returns:
            Lista de diccionarios con información de artistas favoritos
        """
        user = self.get_user(telegram_id)
        if not user:
            return []

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT artist_name, added_at, notifications_enabled
                FROM user_artists
                WHERE user_id = ?
                ORDER BY added_at DESC
            """, (user['id'],))

            return [dict(row) for row in cursor.fetchall()]

    def toggle_artist_notifications(self, telegram_id: int, artist_name: str) -> bool:
        """
        Activa/desactiva notificaciones para un artista específico

        Args:
            telegram_id: ID de Telegram del usuario
            artist_name: Nombre del artista

        Returns:
            Estado actual de las notificaciones para ese artista
        """
        user = self.get_user(telegram_id)
        if not user:
            return False

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Obtener estado actual
            cursor.execute("""
                SELECT notifications_enabled FROM user_artists
                WHERE user_id = ? AND artist_name = ?
            """, (user['id'], artist_name))

            result = cursor.fetchone()
            if result:
                new_state = not bool(result[0])
                cursor.execute("""
                    UPDATE user_artists
                    SET notifications_enabled = ?
                    WHERE user_id = ? AND artist_name = ?
                """, (new_state, user['id'], artist_name))
                conn.commit()

                logger.info(f"Notificaciones de {artist_name} {'activadas' if new_state else 'desactivadas'} para usuario {telegram_id}")
                return new_state

            return False

    # ==================== GESTIÓN DE CONCIERTOS ====================

    def save_concert(self, concert_data: Dict) -> int:
        """
        Guarda un concierto en la base de datos

        Args:
            concert_data: Diccionario con datos del concierto

        Returns:
            ID del concierto guardado o 0 si ya existía
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            try:
                cursor.execute("""
                    INSERT INTO concerts (
                        artist_name, concert_name, venue, city, country,
                        date, time, url, image_url, source, external_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    concert_data.get('artist'),
                    concert_data.get('name'),
                    concert_data.get('venue'),
                    concert_data.get('city'),
                    concert_data.get('country'),
                    concert_data.get('date'),
                    concert_data.get('time'),
                    concert_data.get('url'),
                    concert_data.get('image'),
                    concert_data.get('source'),
                    concert_data.get('id')
                ))

                concert_id = cursor.lastrowid
                conn.commit()
                logger.info(f"Concierto guardado: {concert_data.get('name')} (ID: {concert_id})")
                return concert_id

            except sqlite3.IntegrityError:
                # El concierto ya existe
                logger.debug(f"Concierto ya existe: {concert_data.get('name')}")
                return 0

    def get_concerts_by_artist(self, artist_name: str, days_ahead: int = 365) -> List[Dict]:
        """
        Obtiene conciertos de un artista en un período determinado

        Args:
            artist_name: Nombre del artista
            days_ahead: Días hacia adelante desde hoy

        Returns:
            Lista de conciertos
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            future_date = (datetime.now() + timedelta(days=days_ahead)).strftime('%Y-%m-%d')

            cursor.execute("""
                SELECT * FROM concerts
                WHERE artist_name = ?
                AND (date >= date('now') OR date = '')
                AND (date <= ? OR date = '')
                ORDER BY date ASC
            """, (artist_name, future_date))

            return [dict(row) for row in cursor.fetchall()]

    def get_new_concerts_for_user(self, telegram_id: int) -> List[Dict]:
        """
        Obtiene conciertos nuevos (no notificados) para un usuario

        Args:
            telegram_id: ID de Telegram del usuario

        Returns:
            Lista de conciertos nuevos
        """
        user = self.get_user(telegram_id)
        if not user:
            return []

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT DISTINCT c.* FROM concerts c
                INNER JOIN user_artists ua ON c.artist_name = ua.artist_name
                LEFT JOIN notifications_sent ns ON c.id = ns.concert_id AND ns.user_id = ?
                WHERE ua.user_id = ?
                AND ua.notifications_enabled = 1
                AND ns.id IS NULL
                AND (c.date >= date('now') OR c.date = '')
                ORDER BY c.date ASC
            """, (user['id'], user['id']))

            return [dict(row) for row in cursor.fetchall()]

    def mark_concert_notified(self, telegram_id: int, concert_id: int) -> bool:
        """
        Marca un concierto como notificado para un usuario

        Args:
            telegram_id: ID de Telegram del usuario
            concert_id: ID del concierto

        Returns:
            True si se marcó correctamente
        """
        user = self.get_user(telegram_id)
        if not user:
            return False

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            try:
                cursor.execute("""
                    INSERT INTO notifications_sent (user_id, concert_id)
                    VALUES (?, ?)
                """, (user['id'], concert_id))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                # Ya estaba marcado como notificado
                return False

    # ==================== GESTIÓN DE BÚSQUEDAS PROGRAMADAS ====================

    def _add_to_scheduled_searches(self, artist_name: str, country_code: str):
        """Añade un artista a las búsquedas programadas"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            try:
                next_search = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
                if next_search <= datetime.now():
                    next_search += timedelta(days=1)

                cursor.execute("""
                    INSERT INTO scheduled_searches (artist_name, country_code, next_search)
                    VALUES (?, ?, ?)
                """, (artist_name, country_code, next_search))

                logger.info(f"Añadido a búsquedas programadas: {artist_name} ({country_code})")
            except sqlite3.IntegrityError:
                # Ya existe, no hacer nada
                pass

    def _cleanup_scheduled_searches(self, artist_name: str, country_code: str):
        """Limpia búsquedas programadas si no hay usuarios interesados"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Verificar si algún usuario tiene este artista en favoritos
            cursor.execute("""
                SELECT COUNT(*) FROM user_artists ua
                INNER JOIN users u ON ua.user_id = u.id
                WHERE ua.artist_name = ? AND u.country_code = ?
            """, (artist_name, country_code))

            count = cursor.fetchone()[0]

            if count == 0:
                cursor.execute("""
                    DELETE FROM scheduled_searches
                    WHERE artist_name = ? AND country_code = ?
                """, (artist_name, country_code))

                if cursor.rowcount > 0:
                    logger.info(f"Eliminado de búsquedas programadas: {artist_name} ({country_code})")

    def get_pending_searches(self) -> List[Dict]:
        """
        Obtiene las búsquedas que deben ejecutarse

        Returns:
            Lista de búsquedas pendientes
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM scheduled_searches
                WHERE active = 1
                AND (next_search IS NULL OR next_search <= datetime('now'))
                ORDER BY artist_name
            """)

            return [dict(row) for row in cursor.fetchall()]

    def update_search_timestamp(self, search_id: int):
        """
        Actualiza el timestamp de la próxima búsqueda

        Args:
            search_id: ID de la búsqueda programada
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Próxima búsqueda: mañana a las 9:00
            next_search = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)

            cursor.execute("""
                UPDATE scheduled_searches
                SET last_search = datetime('now'), next_search = ?
                WHERE id = ?
            """, (next_search, search_id))

            conn.commit()

    # ==================== ESTADÍSTICAS Y UTILIDADES ====================

    def get_user_stats(self, telegram_id: int) -> Dict:
        """
        Obtiene estadísticas de un usuario

        Args:
            telegram_id: ID de Telegram del usuario

        Returns:
            Diccionario con estadísticas
        """
        user = self.get_user(telegram_id)
        if not user:
            return {}

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Contar artistas favoritos
            cursor.execute("SELECT COUNT(*) FROM user_artists WHERE user_id = ?", (user['id'],))
            favorite_artists = cursor.fetchone()[0]

            # Contar notificaciones enviadas
            cursor.execute("SELECT COUNT(*) FROM notifications_sent WHERE user_id = ?", (user['id'],))
            notifications_sent = cursor.fetchone()[0]

            # Contar conciertos próximos
            cursor.execute("""
                SELECT COUNT(DISTINCT c.id) FROM concerts c
                INNER JOIN user_artists ua ON c.artist_name = ua.artist_name
                WHERE ua.user_id = ?
                AND (c.date >= date('now') OR c.date = '')
            """, (user['id'],))
            upcoming_concerts = cursor.fetchone()[0]

            return {
                'favorite_artists': favorite_artists,
                'notifications_sent': notifications_sent,
                'upcoming_concerts': upcoming_concerts,
                'notifications_enabled': bool(user['notifications_enabled']),
                'country_code': user['country_code']
            }

    def cleanup_old_data(self, days_old: int = 30):
        """
        Limpia datos antiguos de la base de datos

        Args:
            days_old: Días de antigüedad para considerar datos como antiguos
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cutoff_date = (datetime.now() - timedelta(days=days_old)).strftime('%Y-%m-%d')

            # Eliminar conciertos antiguos
            cursor.execute("DELETE FROM concerts WHERE date < ? AND date != ''", (cutoff_date,))
            concerts_deleted = cursor.rowcount

            # Eliminar notificaciones antiguas
            cursor.execute("DELETE FROM notifications_sent WHERE sent_at < datetime('now', '-{} days')".format(days_old))
            notifications_deleted = cursor.rowcount

            conn.commit()

            logger.info(f"Limpieza completada: {concerts_deleted} conciertos y {notifications_deleted} notificaciones eliminadas")

    def export_user_data(self, telegram_id: int) -> Dict:
        """
        Exporta todos los datos de un usuario (GDPR compliance)

        Args:
            telegram_id: ID de Telegram del usuario

        Returns:
            Diccionario con todos los datos del usuario
        """
        user = self.get_user(telegram_id)
        if not user:
            return {}

        data = {
            'user_info': user,
            'favorite_artists': self.get_user_favorite_artists(telegram_id),
            'stats': self.get_user_stats(telegram_id)
        }

        return data
