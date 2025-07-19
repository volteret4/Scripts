#!/usr/bin/env python3
"""
Scheduled Search Manager para el Bot de Conciertos
Ejecuta búsquedas automáticas diarias y envía notificaciones
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict
import schedule
import time
import threading

# Importar los servicios existentes
from apis.ticketmaster import TicketmasterService
from apis.spotify import SpotifyService
from apis.setlistfm import SetlistfmService
from database_manager import ConcertBotDatabase

# Importar componentes de Telegram
from telegram import Bot
from telegram.error import TelegramError

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('scheduled_searches.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ScheduledSearchManager:
    """Maneja las búsquedas automáticas y notificaciones"""

    def __init__(self, config: Dict = None):
        """
        Inicializa el manager de búsquedas programadas

        Args:
            config: Diccionario de configuración
        """
        # Configuración por defecto
        self.config = config or {}

        # Configuración de rutas
        self.base_dir = Path(__file__).resolve().parent
        self.cache_dir = self.base_dir / "cache"
        self.cache_dir.mkdir(exist_ok=True)

        # Configuración de APIs
        self.telegram_bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        self.ticketmaster_api_key = os.environ.get("TICKETMASTER_API_KEY")
        self.spotify_client_id = os.environ.get("SPOTIFY_CLIENT_ID")
        self.spotify_client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
        self.spotify_redirect_uri = os.environ.get("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback")
        self.setlistfm_api_key = os.environ.get("SETLISTFM_API_KEY")

        # Inicializar base de datos
        db_path = self.config.get('db_path', 'concert_bot.db')
        self.db = ConcertBotDatabase(db_path)

        # Inicializar bot de Telegram
        if self.telegram_bot_token:
            self.telegram_bot = Bot(token=self.telegram_bot_token)
        else:
            self.telegram_bot = None
            logger.warning("Token de Telegram no configurado. Las notificaciones están deshabilitadas.")

        # Inicializar servicios de búsqueda
        self._init_search_services()

        # Control de ejecución
        self.running = False
        self.search_timeout = 30  # Timeout por servicio
        self.max_concerts_per_service = 10

    def _init_search_services(self):
        """Inicializa los servicios de búsqueda de conciertos"""
        try:
            # Ticketmaster
            self.ticketmaster_service = TicketmasterService(
                api_key=self.ticketmaster_api_key,
                cache_dir=self.cache_dir / "ticketmaster"
            ) if self.ticketmaster_api_key else None

            # Spotify
            self.spotify_service = SpotifyService(
                client_id=self.spotify_client_id,
                client_secret=self.spotify_client_secret,
                redirect_uri=self.spotify_redirect_uri,
                cache_dir=self.cache_dir / "spotify"
            ) if self.spotify_client_id and self.spotify_client_secret else None

            # Setlist.fm
            self.setlistfm_service = SetlistfmService(
                api_key=self.setlistfm_api_key,
                cache_dir=self.cache_dir / "setlistfm",
                db_path=None  # No usamos DB para búsquedas programadas
            ) if self.setlistfm_api_key else None

            logger.info("Servicios de búsqueda inicializados")

        except Exception as e:
            logger.error(f"Error inicializando servicios: {e}")

    async def search_concerts_for_artist(self, artist_name: str, country_code: str = "ES") -> List[Dict]:
        """
        Busca conciertos para un artista en todos los servicios disponibles

        Args:
            artist_name: Nombre del artista
            country_code: Código de país

        Returns:
            Lista de conciertos encontrados
        """
        all_concerts = []

        # Funciones de búsqueda segura con timeout
        async def safe_search_ticketmaster():
            if not self.ticketmaster_service:
                return []
            try:
                return await asyncio.wait_for(
                    asyncio.to_thread(
                        self.ticketmaster_service.search_concerts,
                        artist_name,
                        country_code
                    ),
                    timeout=self.search_timeout
                )
            except asyncio.TimeoutError:
                logger.warning(f"Timeout en Ticketmaster para {artist_name}")
                return []
            except Exception as e:
                logger.error(f"Error en Ticketmaster para {artist_name}: {e}")
                return []

        async def safe_search_spotify():
            if not self.spotify_service:
                return []
            try:
                concerts, message = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.spotify_service.search_artist_and_concerts,
                        artist_name
                    ),
                    timeout=self.search_timeout
                )
                return concerts
            except asyncio.TimeoutError:
                logger.warning(f"Timeout en Spotify para {artist_name}")
                return []
            except Exception as e:
                logger.error(f"Error en Spotify para {artist_name}: {e}")
                return []

        async def safe_search_setlistfm():
            if not self.setlistfm_service:
                return []
            try:
                concerts, message = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.setlistfm_service.search_concerts,
                        artist_name,
                        country_code
                    ),
                    timeout=self.search_timeout
                )
                return concerts
            except asyncio.TimeoutError:
                logger.warning(f"Timeout en Setlist.fm para {artist_name}")
                return []
            except Exception as e:
                logger.error(f"Error en Setlist.fm para {artist_name}: {e}")
                return []

        # Ejecutar búsquedas en paralelo
        try:
            tasks = [
                safe_search_ticketmaster(),
                safe_search_spotify(),
                safe_search_setlistfm()
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Procesar resultados
            service_names = ["Ticketmaster", "Spotify", "Setlist.fm"]

            for i, (service_name, result) in enumerate(zip(service_names, results)):
                if isinstance(result, Exception):
                    logger.error(f"Error en {service_name} para {artist_name}: {result}")
                    continue

                if isinstance(result, tuple):
                    concerts = result[0] if result[0] else []
                elif isinstance(result, list):
                    concerts = result
                else:
                    concerts = []

                # Añadir información de fuente a cada concierto
                for concert in concerts[:self.max_concerts_per_service]:
                    concert['source'] = service_name
                    all_concerts.append(concert)

            logger.info(f"Encontrados {len(all_concerts)} conciertos para {artist_name}")
            return all_concerts

        except Exception as e:
            logger.error(f"Error general en búsqueda para {artist_name}: {e}")
            return []

    async def process_scheduled_searches(self):
        """Procesa todas las búsquedas programadas pendientes"""
        if not self.running:
            return

        logger.info("Iniciando proceso de búsquedas programadas...")

        try:
            # Obtener búsquedas pendientes
            pending_searches = self.db.get_pending_searches()

            if not pending_searches:
                logger.info("No hay búsquedas pendientes")
                return

            logger.info(f"Procesando {len(pending_searches)} búsquedas pendientes")

            total_new_concerts = 0

            for search in pending_searches:
                if not self.running:
                    break

                search_id = search['id']
                artist_name = search['artist_name']
                country_code = search['country_code']

                logger.info(f"Buscando conciertos para {artist_name} ({country_code})")

                try:
                    # Buscar conciertos
                    concerts = await self.search_concerts_for_artist(artist_name, country_code)

                    # Guardar conciertos nuevos en la base de datos
                    new_concerts = 0
                    for concert_data in concerts:
                        concert_id = self.db.save_concert(concert_data)
                        if concert_id > 0:  # Es un concierto nuevo
                            new_concerts += 1

                    if new_concerts > 0:
                        logger.info(f"Guardados {new_concerts} conciertos nuevos para {artist_name}")
                        total_new_concerts += new_concerts

                    # Actualizar timestamp de búsqueda
                    self.db.update_search_timestamp(search_id)

                    # Pausa entre búsquedas para no sobrecargar las APIs
                    await asyncio.sleep(2)

                except Exception as e:
                    logger.error(f"Error procesando búsqueda para {artist_name}: {e}")
                    continue

            logger.info(f"Proceso completado. Total de conciertos nuevos: {total_new_concerts}")

            # Enviar notificaciones después de todas las búsquedas
            if total_new_concerts > 0:
                await self.send_pending_notifications()

        except Exception as e:
            logger.error(f"Error en proceso de búsquedas programadas: {e}")

    async def send_pending_notifications(self):
        """Envía notificaciones pendientes a todos los usuarios"""
        if not self.telegram_bot:
            logger.warning("Bot de Telegram no disponible. Omitiendo notificaciones.")
            return

        logger.info("Enviando notificaciones pendientes...")

        try:
            # Obtener todos los usuarios con notificaciones habilitadas
            with self.db._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT telegram_id FROM users
                    WHERE notifications_enabled = 1
                """)

                users = [row['telegram_id'] for row in cursor.fetchall()]

            total_notifications = 0

            for telegram_id in users:
                if not self.running:
                    break

                try:
                    # Obtener conciertos nuevos para este usuario
                    new_concerts = self.db.get_new_concerts_for_user(telegram_id)

                    if not new_concerts:
                        continue

                    # Agrupar conciertos por artista
                    concerts_by_artist = {}
                    for concert in new_concerts:
                        artist = concert['artist_name']
                        if artist not in concerts_by_artist:
                            concerts_by_artist[artist] = []
                        concerts_by_artist[artist].append(concert)

                    # Enviar notificación para cada artista
                    for artist_name, artist_concerts in concerts_by_artist.items():
                        message = self._format_notification_message(artist_name, artist_concerts)

                        try:
                            await self.telegram_bot.send_message(
                                chat_id=telegram_id,
                                text=message,
                                parse_mode='Markdown',
                                disable_web_page_preview=True
                            )

                            # Marcar conciertos como notificados
                            for concert in artist_concerts:
                                self.db.mark_concert_notified(telegram_id, concert['id'])

                            total_notifications += 1
                            logger.info(f"Notificación enviada a {telegram_id} para {artist_name}")

                            # Pausa entre mensajes para evitar rate limiting
                            await asyncio.sleep(1)

                        except TelegramError as e:
                            logger.error(f"Error enviando notificación a {telegram_id}: {e}")
                            continue

                except Exception as e:
                    logger.error(f"Error procesando notificaciones para usuario {telegram_id}: {e}")
                    continue

            logger.info(f"Notificaciones enviadas: {total_notifications}")

        except Exception as e:
            logger.error(f"Error en envío de notificaciones: {e}")

    def _format_notification_message(self, artist_name: str, concerts: List[Dict]) -> str:
        """
        Formatea el mensaje de notificación para un artista

        Args:
            artist_name: Nombre del artista
            concerts: Lista de conciertos

        Returns:
            Mensaje formateado para Telegram
        """
        # Escapar caracteres especiales de Markdown
        safe_artist_name = artist_name.replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")

        message_lines = [
            f"🎵 *¡Nuevos conciertos de {safe_artist_name}!*\n"
        ]

        # Ordenar conciertos por fecha
        try:
            sorted_concerts = sorted(concerts, key=lambda x: x.get('date', '9999-99-99'))
        except Exception:
            sorted_concerts = concerts

        for concert in sorted_concerts[:5]:  # Máximo 5 conciertos por notificación
            venue = concert.get('venue', 'Lugar desconocido')
            city = concert.get('city', '')
            date = concert.get('date', 'Fecha desconocida')
            source = concert.get('source', 'Desconocido')

            # Formatear fecha si está en formato ISO
            if date and len(date) >= 10 and '-' in date:
                try:
                    from datetime import datetime
                    date_obj = datetime.strptime(date[:10], '%Y-%m-%d')
                    date = date_obj.strftime('%d/%m/%Y')
                except ValueError:
                    pass

            # Escapar caracteres especiales de Markdown
            safe_venue = str(venue).replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")
            safe_city = str(city).replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")

            location = f"{safe_venue}, {safe_city}" if safe_city else safe_venue
            url = concert.get('url', '')

            if url and url.startswith(('http://', 'https://')):
                url = url.replace(")", "\\)")
                message_lines.append(f"• {date}: [{location}]({url}) _{source}_")
            else:
                message_lines.append(f"• {date}: {location} _{source}_")

        if len(concerts) > 5:
            remaining = len(concerts) - 5
            message_lines.append(f"\n_...y {remaining} conciertos más. Usa /b {artist_name} para ver todos._")

        return "\n".join(message_lines)

    def start_scheduler(self):
        """Inicia el programador de tareas"""
        self.running = True

        # Programar búsquedas diarias a las 9:00
        schedule.every().day.at("09:00").do(self._run_async_task, self.process_scheduled_searches)

        # Programar limpieza semanal (domingos a las 2:00)
        schedule.every().sunday.at("02:00").do(self._cleanup_old_data)

        logger.info("Programador de tareas iniciado")
        logger.info("Búsquedas programadas: Diario a las 9:00")
        logger.info("Limpieza de datos: Domingos a las 2:00")

        # Ejecutar primera búsqueda inmediatamente si hay búsquedas pendientes
        pending = self.db.get_pending_searches()
        if pending:
            logger.info(f"Ejecutando {len(pending)} búsquedas pendientes inmediatamente...")
            self._run_async_task(self.process_scheduled_searches)

        # Loop principal del programador
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Verificar cada minuto
            except KeyboardInterrupt:
                logger.info("Deteniendo programador por interrupción del usuario...")
                self.stop_scheduler()
                break
            except Exception as e:
                logger.error(f"Error en el loop del programador: {e}")
                time.sleep(60)

    def stop_scheduler(self):
        """Detiene el programador de tareas"""
        self.running = False
        schedule.clear()
        logger.info("Programador de tareas detenido")

    def _run_async_task(self, coro):
        """Ejecuta una tarea asíncrona en el hilo principal"""
        def run_in_thread():
            try:
                # Crear nuevo loop si no existe
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                if loop.is_running():
                    # Si el loop está corriendo, crear una nueva tarea
                    task = asyncio.create_task(coro())
                else:
                    # Si no está corriendo, usar run_until_complete
                    loop.run_until_complete(coro())

            except Exception as e:
                logger.error(f"Error ejecutando tarea asíncrona: {e}")

        # Ejecutar en un hilo separado para evitar bloqueos
        thread = threading.Thread(target=run_in_thread)
        thread.daemon = True
        thread.start()
        thread.join(timeout=300)  # Timeout de 5 minutos

    def _cleanup_old_data(self):
        """Limpia datos antiguos de la base de datos"""
        try:
            logger.info("Iniciando limpieza de datos antiguos...")
            self.db.cleanup_old_data(days_old=30)
            logger.info("Limpieza de datos completada")
        except Exception as e:
            logger.error(f"Error en limpieza de datos: {e}")

    def run_manual_search(self, artist_name: str, country_code: str = "ES"):
        """
        Ejecuta una búsqueda manual para un artista específico

        Args:
            artist_name: Nombre del artista
            country_code: Código de país
        """
        async def manual_search():
            logger.info(f"Ejecutando búsqueda manual para {artist_name} ({country_code})")
            concerts = await self.search_concerts_for_artist(artist_name, country_code)

            new_concerts = 0
            for concert_data in concerts:
                concert_id = self.db.save_concert(concert_data)
                if concert_id > 0:
                    new_concerts += 1

            logger.info(f"Búsqueda manual completada. Conciertos nuevos: {new_concerts}")
            return new_concerts

        self._run_async_task(manual_search)

def main():
    """Función principal para ejecutar el manager de búsquedas programadas"""
    # Configuración
    config = {
        'db_path': os.environ.get('CONCERT_BOT_DB_PATH', 'concert_bot.db'),
        'log_level': os.environ.get('LOG_LEVEL', 'INFO')
    }

    # Ajustar nivel de logging
    log_level = getattr(logging, config['log_level'].upper(), logging.INFO)
    logging.getLogger().setLevel(log_level)

    # Verificar variables de entorno críticas
    required_env_vars = ['TELEGRAM_BOT_TOKEN']
    missing_vars = [var for var in required_env_vars if not os.environ.get(var)]

    if missing_vars:
        logger.error(f"Variables de entorno faltantes: {missing_vars}")
        sys.exit(1)

    # Crear y ejecutar el manager
    try:
        manager = ScheduledSearchManager(config)
        logger.info("Iniciando Scheduled Search Manager...")

        # Ejecutar programador en el hilo principal
        manager.start_scheduler()

    except KeyboardInterrupt:
        logger.info("Deteniendo por interrupción del usuario...")
    except Exception as e:
        logger.error(f"Error crítico: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
