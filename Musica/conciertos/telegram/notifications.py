#!/usr/bin/env python3
"""
Script separado para el sistema de notificaciones del bot de artistas
Se ejecuta de forma independiente y envía notificaciones a las horas programadas
"""

import os
import sys
import asyncio
import sqlite3
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict
import requests
import json

# Añadir el directorio principal al path para importar los módulos
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Importar servicios de búsqueda de conciertos
try:
    from apis.ticketmaster import TicketmasterService
    from apis.spotify import SpotifyService
    from apis.setlistfm import SetlistfmService
except ImportError as e:
    print(f"Error importando servicios: {e}")
    sys.exit(1)

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('notifications.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class NotificationService:
    """Servicio para manejar notificaciones"""

    def __init__(self, db_path: str, telegram_token: str):
        self.db_path = db_path
        self.telegram_token = telegram_token
        self.telegram_api_url = f"https://api.telegram.org/bot{telegram_token}"

        # Inicializar servicios de búsqueda de conciertos
        self.init_concert_services()

    def init_concert_services(self):
        """Inicializa los servicios de búsqueda de conciertos"""
        BASE_DIR = Path(__file__).resolve().parent
        CACHE_DIR = BASE_DIR / "cache"
        CACHE_DIR.mkdir(exist_ok=True)

        # Variables de entorno
        TICKETMASTER_API_KEY = os.environ.get("TICKETMASTER_API_KEY")
        SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
        SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")
        SPOTIFY_REDIRECT_URI = os.environ.get("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback")
        SETLISTFM_API_KEY = os.environ.get("SETLISTFM_API_KEY")

        self.services = {}

        try:
            if TICKETMASTER_API_KEY:
                self.services['ticketmaster'] = TicketmasterService(
                    api_key=TICKETMASTER_API_KEY,
                    cache_dir=CACHE_DIR / "ticketmaster"
                )
                logger.info("✅ Ticketmaster service inicializado")

            if SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET:
                self.services['spotify'] = SpotifyService(
                    client_id=SPOTIFY_CLIENT_ID,
                    client_secret=SPOTIFY_CLIENT_SECRET,
                    redirect_uri=SPOTIFY_REDIRECT_URI,
                    cache_dir=CACHE_DIR / "spotify"
                )
                logger.info("✅ Spotify service inicializado")

            if SETLISTFM_API_KEY:
                self.services['setlistfm'] = SetlistfmService(
                    api_key=SETLISTFM_API_KEY,
                    cache_dir=CACHE_DIR / "setlistfm",
                    db_path=None
                )
                logger.info("✅ Setlist.fm service inicializado")

        except Exception as e:
            logger.error(f"Error inicializando servicios: {e}")

    def get_db_connection(self):
        """Obtiene conexión a la base de datos"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    async def search_concerts_for_artist(self, artist_name: str, user_services: Dict[str, bool]) -> List[Dict]:
        """Busca conciertos para un artista usando los servicios habilitados por el usuario"""
        all_concerts = []
        country_code = user_services.get('country_filter', 'ES')

        # Buscar en Ticketmaster si está habilitado
        if user_services.get('ticketmaster', True) and 'ticketmaster' in self.services:
            try:
                concerts, _ = self.services['ticketmaster'].search_concerts(artist_name, country_code)
                all_concerts.extend(concerts)
                logger.info(f"Ticketmaster: {len(concerts)} conciertos encontrados para {artist_name}")
            except Exception as e:
                logger.error(f"Error buscando en Ticketmaster: {e}")

        # Buscar en Spotify si está habilitado
        if user_services.get('spotify', True) and 'spotify' in self.services:
            try:
                concerts, _ = self.services['spotify'].search_artist_and_concerts(artist_name)
                all_concerts.extend(concerts)
                logger.info(f"Spotify: {len(concerts)} conciertos encontrados para {artist_name}")
            except Exception as e:
                logger.error(f"Error buscando en Spotify: {e}")

        # Buscar en Setlist.fm si está habilitado
        if user_services.get('setlistfm', True) and 'setlistfm' in self.services:
            try:
                concerts, _ = self.services['setlistfm'].search_concerts(artist_name, country_code)
                all_concerts.extend(concerts)
                logger.info(f"Setlist.fm: {len(concerts)} conciertos encontrados para {artist_name}")
            except Exception as e:
                logger.error(f"Error buscando en Setlist.fm: {e}")

        return all_concerts

    def create_concert_hash(self, concert_data: Dict) -> str:
        """Crea un hash único para un concierto"""
        import hashlib
        key_data = f"{concert_data.get('artist', '')}-{concert_data.get('venue', '')}-{concert_data.get('date', '')}-{concert_data.get('source', '')}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def save_concert(self, concert_data: Dict) -> int:
        """Guarda un concierto en la base de datos"""
        conn = self.get_db_connection()
        cursor = conn.cursor()

        try:
            # Crear hash único para el concierto
            concert_hash = self.create_concert_hash(concert_data)

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

    def get_user_services(self, user_id: int) -> Dict[str, bool]:
        """Obtiene la configuración de servicios para un usuario"""
        conn = self.get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT service_ticketmaster, service_spotify, service_setlistfm, country_filter
                FROM users WHERE id = ?
            """, (user_id,))

            row = cursor.fetchone()
            if row:
                return {
                    'ticketmaster': bool(row[0]),
                    'spotify': bool(row[1]),
                    'setlistfm': bool(row[2]),
                    'country_filter': row[3] or 'ES'
                }

            # Valores por defecto si no se encuentra el usuario
            return {
                'ticketmaster': True,
                'spotify': True,
                'setlistfm': True,
                'country_filter': 'ES'
            }

        except sqlite3.Error as e:
            logger.error(f"Error obteniendo configuración de servicios: {e}")
            return {
                'ticketmaster': True,
                'spotify': True,
                'setlistfm': True,
                'country_filter': 'ES'
            }
        finally:
            conn.close()

    def get_user_followed_artists(self, user_id: int) -> List[Dict]:
        """Obtiene artistas seguidos por un usuario"""
        conn = self.get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT a.name
                FROM artists a
                JOIN user_followed_artists ufa ON a.id = ufa.artist_id
                WHERE ufa.user_id = ?
            """, (user_id,))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        except sqlite3.Error as e:
            logger.error(f"Error obteniendo artistas seguidos: {e}")
            return []
        finally:
            conn.close()

    def get_users_for_time(self, notification_time: str) -> List[Dict]:
        """Obtiene usuarios que deben recibir notificación a una hora específica"""
        conn = self.get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT * FROM users
                WHERE notification_enabled = 1
                AND notification_time = ?
            """, (notification_time,))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        except sqlite3.Error as e:
            logger.error(f"Error obteniendo usuarios para hora {notification_time}: {e}")
            return []
        finally:
            conn.close()
        """Obtiene la configuración de servicios para un usuario"""
        conn = self.get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT service_ticketmaster, service_spotify, service_setlistfm, country_filter
                FROM users WHERE id = ?
            """, (user_id,))

            row = cursor.fetchone()
            if row:
                return {
                    'ticketmaster': bool(row[0]),
                    'spotify': bool(row[1]),
                    'setlistfm': bool(row[2]),
                    'country_filter': row[3] or 'ES'
                }

            # Valores por defecto si no se encuentra el usuario
            return {
                'ticketmaster': True,
                'spotify': True,
                'setlistfm': True,
                'country_filter': 'ES'
            }

        except sqlite3.Error as e:
            logger.error(f"Error obteniendo configuración de servicios: {e}")
            return {
                'ticketmaster': True,
                'spotify': True,
                'setlistfm': True,
                'country_filter': 'ES'
            }
        finally:
            conn.close()
        """Obtiene usuarios que deben recibir notificación a una hora específica"""
        conn = self.get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT * FROM users
                WHERE notification_enabled = 1
                AND notification_time = ?
            """, (notification_time,))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        except sqlite3.Error as e:
            logger.error(f"Error obteniendo usuarios para hora {notification_time}: {e}")
            return []
        finally:
            conn.close()

    def get_user_followed_artists(self, user_id: int) -> List[Dict]:
        """Obtiene artistas seguidos por un usuario"""
        conn = self.get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT a.name
                FROM artists a
                JOIN user_followed_artists ufa ON a.id = ufa.artist_id
                WHERE ufa.user_id = ?
            """, (user_id,))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        except sqlite3.Error as e:
            logger.error(f"Error obteniendo artistas seguidos: {e}")
            return []
        finally:
            conn.close()

    def get_unnotified_concerts_for_user(self, user_id: int) -> List[Dict]:
        """Obtiene conciertos no notificados para un usuario"""
        conn = self.get_db_connection()
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
                ORDER BY c.date ASC
            """, (user_id, user_id))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        except sqlite3.Error as e:
            logger.error(f"Error obteniendo conciertos no notificados: {e}")
            return []
        finally:
            conn.close()

    def mark_concert_notified(self, user_id: int, concert_id: int) -> bool:
        """Marca un concierto como notificado para un usuario"""
        conn = self.get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT OR IGNORE INTO notifications_sent (user_id, concert_id)
                VALUES (?, ?)
            """, (user_id, concert_id))

            conn.commit()
            return cursor.rowcount > 0

        except sqlite3.Error as e:
            logger.error(f"Error marcando concierto como notificado: {e}")
            return False
        finally:
            conn.close()

    def format_concerts_message(self, concerts: List[Dict], title: str = "🔔 Nuevos conciertos encontrados") -> str:
        """Formatea una lista de conciertos para mostrar en Telegram (versión para notificaciones)"""
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
            message_lines.append(f"*{artist}*:")

            for concert in artist_concerts[:3]:  # Limitar a 3 por artista en notificaciones
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

                location = f"{venue}, {city}" if city else venue

                concert_line = f"• {date}: "

                if url and url.startswith(('http://', 'https://')):
                    concert_line += f"[{location}]({url})"
                else:
                    concert_line += location

                if source:
                    concert_line += f" _{source}_"

                message_lines.append(concert_line)

            if len(artist_concerts) > 3:
                remaining = len(artist_concerts) - 3
                message_lines.append(f"_...y {remaining} más_")

            message_lines.append("")

        message_lines.append(f"📊 Total: {len(concerts)} conciertos")
        message_lines.append(f"\n💡 Usa `/search` en el bot para ver todos los detalles")

        return "\n".join(message_lines)

    async def send_telegram_message(self, chat_id: int, message: str) -> bool:
        """Envía un mensaje de Telegram"""
        try:
            data = {
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': True
            }

            response = requests.post(
                f"{self.telegram_api_url}/sendMessage",
                data=data,
                timeout=30
            )

            if response.status_code == 200:
                return True
            else:
                logger.error(f"Error enviando mensaje Telegram: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error enviando mensaje Telegram: {e}")
            return False

    async def process_notifications_for_time(self, notification_time: str):
        """Procesa notificaciones para una hora específica"""
        logger.info(f"Procesando notificaciones para las {notification_time}")

        # Obtener usuarios para esta hora
        users = self.get_users_for_time(notification_time)

        if not users:
            logger.info(f"No hay usuarios configurados para las {notification_time}")
            return

        logger.info(f"Encontrados {len(users)} usuarios para notificación a las {notification_time}")

        for user in users:
            try:
                logger.info(f"Procesando notificaciones para {user['username']}")

                # Obtener artistas seguidos
                followed_artists = self.get_user_followed_artists(user['id'])

                if not followed_artists:
                    logger.info(f"Usuario {user['username']} no sigue ningún artista")
                    continue

                # Obtener configuración de servicios del usuario
                user_services = self.get_user_services(user['id'])

                # Verificar que tenga al menos un servicio activo
                active_services = [s for s, active in user_services.items() if active and s != 'country_filter']
                if not active_services:
                    logger.warning(f"Usuario {user['username']} no tiene servicios activos")
                    continue

                logger.info(f"Servicios activos para {user['username']}: {active_services}, País: {user_services['country_filter']}")

                # Buscar y guardar nuevos conciertos
                total_new_concerts = 0
                for artist in followed_artists:
                    artist_name = artist['name']
                    logger.info(f"Buscando conciertos para {artist_name} con configuración del usuario")

                    concerts = await self.search_concerts_for_artist(artist_name, user_services)

                    for concert in concerts:
                        concert_id = self.save_concert(concert)
                        if concert_id:
                            total_new_concerts += 1

                    # Pausa para no sobrecargar las APIs
                    await asyncio.sleep(1)

                logger.info(f"Encontrados {total_new_concerts} nuevos conciertos para {user['username']}")

                # Obtener conciertos no notificados
                unnotified_concerts = self.get_unnotified_concerts_for_user(user['id'])

                if unnotified_concerts:
                    # Limitar a 15 conciertos por notificación
                    concerts_to_notify = unnotified_concerts[:15]

                    # Formatear mensaje
                    message = self.format_concerts_message(concerts_to_notify)

                    # Enviar notificación
                    if await self.send_telegram_message(user['chat_id'], message):
                        # Marcar conciertos como notificados
                        for concert in concerts_to_notify:
                            self.mark_concert_notified(user['id'], concert['id'])

                        logger.info(f"Notificación enviada a {user['username']}: {len(concerts_to_notify)} conciertos")
                    else:
                        logger.error(f"Falló el envío de notificación a {user['username']}")
                else:
                    logger.info(f"No hay nuevos conciertos para {user['username']}")

            except Exception as e:
                logger.error(f"Error procesando notificaciones para {user['username']}: {e}")

        logger.info(f"Notificaciones completadas para las {notification_time}")

def main():
    """Función principal del script de notificaciones"""
    # Configuración desde variables de entorno
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_CONCIERTOS')
    DB_PATH = os.getenv('DB_PATH', 'artist_tracker.db')

    if not TELEGRAM_TOKEN:
        logger.error("❌ No se ha configurado TELEGRAM_BOT_CONCIERTOS en las variables de entorno")
        sys.exit(1)

    if not os.path.exists(DB_PATH):
        logger.error(f"❌ No se encuentra la base de datos en {DB_PATH}")
        sys.exit(1)

    # Crear servicio de notificaciones
    notification_service = NotificationService(DB_PATH, TELEGRAM_TOKEN)

    logger.info("🔔 Script de notificaciones iniciado")
    logger.info("⏰ Verificando notificaciones cada minuto...")

    try:
        while True:
            current_time = datetime.now().strftime('%H:%M')

            # Ejecutar notificaciones para la hora actual
            asyncio.run(notification_service.process_notifications_for_time(current_time))

            # Esperar hasta el siguiente minuto
            time.sleep(60)

    except KeyboardInterrupt:
        logger.info("🛑 Script de notificaciones detenido por el usuario")
    except Exception as e:
        logger.error(f"❌ Error crítico en el script de notificaciones: {e}")

if __name__ == "__main__":
    main()
