#!/usr/bin/env python3
"""
Main Launcher para el Bot de Conciertos
Ejecuta tanto el bot de Telegram como las búsquedas programadas
"""

import os
import sys
import time
import signal
import logging
import asyncio
import threading
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Añadir el directorio actual al path para imports
sys.path.append(str(Path(__file__).parent))

# Importar nuestros módulos
from database_manager import ConcertBotDatabase
from scheduled_search_manager import ScheduledSearchManager

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, os.environ.get('LOG_LEVEL', 'INFO').upper()),
    handlers=[
        logging.FileHandler('concert_bot_main.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ConcertBotLauncher:
    """Lanzador principal que maneja bot y búsquedas programadas"""

    def __init__(self):
        """Inicializa el lanzador"""
        self.bot_process = None
        self.scheduler_manager = None
        self.running = False

        # Verificar configuración
        self._check_environment()

        # Configurar handlers de señales
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _check_environment(self):
        """Verifica que las variables de entorno estén configuradas"""
        required_vars = ['TELEGRAM_BOT_TOKEN']
        missing_vars = [var for var in required_vars if not os.environ.get(var)]

        if missing_vars:
            logger.error(f"Variables de entorno faltantes: {missing_vars}")
            logger.error("Por favor, configura las variables en el archivo .env")
            sys.exit(1)

        # Verificar APIs opcionales
        optional_apis = {
            'TICKETMASTER_API_KEY': 'Ticketmaster',
            'SPOTIFY_CLIENT_ID': 'Spotify',
            'SETLISTFM_API_KEY': 'Setlist.fm'
        }

        missing_apis = []
        for var, service in optional_apis.items():
            if not os.environ.get(var):
                missing_apis.append(service)

        if missing_apis:
            logger.warning(f"APIs no configuradas (funcionalidad limitada): {', '.join(missing_apis)}")
        else:
            logger.info("✅ Todas las APIs están configuradas")

    def _signal_handler(self, signum, frame):
        """Maneja señales de terminación"""
        logger.info(f"Señal {signum} recibida. Iniciando parada graceful...")
        self.stop()

    def start_telegram_bot(self):
        """Inicia el bot de Telegram en un hilo separado"""
        def run_bot():
            try:
                logger.info("🤖 Iniciando bot de Telegram...")

                # Importar y ejecutar el bot principal
                from enhanced_telegram_bot import main as run_telegram_bot
                run_telegram_bot()

            except Exception as e:
                logger.error(f"Error en bot de Telegram: {e}")
                self.running = False

        self.bot_thread = threading.Thread(target=run_bot, name="TelegramBot")
        self.bot_thread.daemon = True
        self.bot_thread.start()
        logger.info("✅ Hilo del bot de Telegram iniciado")

    def start_scheduled_searches(self):
        """Inicia el manager de búsquedas programadas"""
        try:
            logger.info("⏰ Iniciando búsquedas programadas...")

            config = {
                'db_path': os.environ.get('CONCERT_BOT_DB_PATH', 'concert_bot.db'),
                'log_level': os.environ.get('LOG_LEVEL', 'INFO')
            }

            self.scheduler_manager = ScheduledSearchManager(config)

            # Ejecutar en hilo separado
            def run_scheduler():
                try:
                    self.scheduler_manager.start_scheduler()
                except Exception as e:
                    logger.error(f"Error en búsquedas programadas: {e}")
                    self.running = False

            self.scheduler_thread = threading.Thread(target=run_scheduler, name="ScheduledSearches")
            self.scheduler_thread.daemon = True
            self.scheduler_thread.start()
            logger.info("✅ Hilo de búsquedas programadas iniciado")

        except Exception as e:
            logger.error(f"Error iniciando búsquedas programadas: {e}")

    def initialize_database(self):
        """Inicializa la base de datos si es necesario"""
        try:
            logger.info("📊 Inicializando base de datos...")
            db_path = os.environ.get('CONCERT_BOT_DB_PATH', 'concert_bot.db')
            db = ConcertBotDatabase(db_path)
            logger.info("✅ Base de datos inicializada")
            return True
        except Exception as e:
            logger.error(f"Error inicializando base de datos: {e}")
            return False

    def start(self):
        """Inicia todos los componentes del bot"""
        try:
            logger.info("🚀 Iniciando Concert Bot Launcher...")

            # Verificar e inicializar base de datos
            if not self.initialize_database():
                logger.error("❌ No se pudo inicializar la base de datos")
                return False

            self.running = True

            # Iniciar componentes
            self.start_telegram_bot()
            time.sleep(2)  # Dar tiempo al bot para iniciar

            self.start_scheduled_searches()
            time.sleep(2)  # Dar tiempo al scheduler para iniciar

            logger.info("✅ Todos los componentes iniciados correctamente")
            logger.info("🎵 Concert Bot está funcionando!")
            logger.info("📱 Bot de Telegram: Activo")
            logger.info("⏰ Búsquedas programadas: Activas (diario a las 9:00)")
            logger.info("💾 Base de datos: Inicializada")
            logger.info("\nPresiona Ctrl+C para detener el bot...")

            # Loop principal
            while self.running:
                try:
                    # Verificar que los hilos sigan activos
                    if not self.bot_thread.is_alive():
                        logger.error("❌ Hilo del bot de Telegram se detuvo inesperadamente")
                        self.running = False
                        break

                    if not self.scheduler_thread.is_alive():
                        logger.error("❌ Hilo de búsquedas programadas se detuvo inesperadamente")
                        self.running = False
                        break

                    time.sleep(10)  # Verificar cada 10 segundos

                except KeyboardInterrupt:
                    logger.info("🛑 Interrupción del usuario detectada")
                    break
                except Exception as e:
                    logger.error(f"Error en loop principal: {e}")
                    time.sleep(5)

            return True

        except Exception as e:
            logger.error(f"Error crítico iniciando el launcher: {e}")
            return False
        finally:
            self.stop()

    def stop(self):
        """Detiene todos los componentes gracefully"""
        if not self.running:
            return

        logger.info("🛑 Deteniendo Concert Bot...")
        self.running = False

        try:
            # Detener búsquedas programadas
            if self.scheduler_manager:
                logger.info("⏰ Deteniendo búsquedas programadas...")
                self.scheduler_manager.stop_scheduler()

            # Esperar a que los hilos terminen
            if hasattr(self, 'scheduler_thread') and self.scheduler_thread.is_alive():
                logger.info("⏳ Esperando a que termine el hilo de búsquedas...")
                self.scheduler_thread.join(timeout=10)

            if hasattr(self, 'bot_thread') and self.bot_thread.is_alive():
                logger.info("⏳ Esperando a que termine el hilo del bot...")
                self.bot_thread.join(timeout=10)

            logger.info("✅ Concert Bot detenido correctamente")

        except Exception as e:
            logger.error(f"Error deteniendo componentes: {e}")

def show_banner():
    """Muestra el banner de inicio"""
    banner = """
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║               🎵 CONCERT BOT LAUNCHER 🎵                     ║
    ║                                                              ║
    ║  Bot de Telegram para búsqueda y notificación de conciertos ║
    ║                                                              ║
    ║  Características:                                            ║
    ║  • 🔍 Búsqueda en Ticketmaster, Spotify y Setlist.fm       ║
    ║  • ⭐ Artistas favoritos personalizados                     ║
    ║  • 🌍 Configuración de país                                 ║
    ║  • 🔔 Notificaciones automáticas diarias                   ║
    ║  • 💾 Persistencia de datos                                 ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)

def show_status():
    """Muestra el estado de la configuración"""
    print("\n📋 ESTADO DE CONFIGURACIÓN:")
    print("=" * 50)

    # Verificar variables críticas
    telegram_token = "✅ Configurado" if os.environ.get('TELEGRAM_BOT_TOKEN') else "❌ Faltante"
    print(f"Telegram Bot Token: {telegram_token}")

    # Verificar APIs
    apis = {
        'Ticketmaster': os.environ.get('TICKETMASTER_API_KEY'),
        'Spotify': os.environ.get('SPOTIFY_CLIENT_ID') and os.environ.get('SPOTIFY_CLIENT_SECRET'),
        'Setlist.fm': os.environ.get('SETLISTFM_API_KEY')
    }

    print("\nAPIs de servicios:")
    for service, configured in apis.items():
        status = "✅ Configurado" if configured else "⚠️  No configurado"
        print(f"  {service}: {status}")

    # Información de base de datos
    db_path = os.environ.get('CONCERT_BOT_DB_PATH', 'concert_bot.db')
    db_exists = Path(db_path).exists()
    db_status = "✅ Existe" if db_exists else "🆕 Se creará"
    print(f"\nBase de datos ({db_path}): {db_status}")

    print("=" * 50)

def main():
    """Función principal"""
    try:
        show_banner()
        show_status()

        print("\n🚀 Iniciando Concert Bot...")
        time.sleep(2)

        # Crear y ejecutar el launcher
        launcher = ConcertBotLauncher()
        success = launcher.start()

        if not success:
            logger.error("❌ Error iniciando el bot")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("🛑 Interrupción del usuario")
    except Exception as e:
        logger.error(f"❌ Error crítico: {e}")
        sys.exit(1)

# Funciones de utilidad para scripts separados
def run_bot_only():
    """Ejecuta solo el bot de Telegram"""
    try:
        from enhanced_telegram_bot import main as run_telegram_bot
        logger.info("🤖 Ejecutando solo el bot de Telegram...")
        run_telegram_bot()
    except Exception as e:
        logger.error(f"Error ejecutando bot: {e}")

def run_scheduler_only():
    """Ejecuta solo las búsquedas programadas"""
    try:
        from scheduled_search_manager import main as run_scheduler
        logger.info("⏰ Ejecutando solo las búsquedas programadas...")
        run_scheduler()
    except Exception as e:
        logger.error(f"Error ejecutando scheduler: {e}")

def initialize_db_only():
    """Solo inicializa la base de datos"""
    try:
        logger.info("📊 Inicializando solo la base de datos...")
        db_path = os.environ.get('CONCERT_BOT_DB_PATH', 'concert_bot.db')
        db = ConcertBotDatabase(db_path)
        logger.info("✅ Base de datos inicializada correctamente")

        # Mostrar estadísticas
        print(f"\n📊 Base de datos creada en: {db_path}")
        print("🎯 Tablas creadas:")
        print("  • users - Información de usuarios")
        print("  • user_artists - Artistas favoritos")
        print("  • concerts - Conciertos encontrados")
        print("  • notifications_sent - Historial de notificaciones")
        print("  • scheduled_searches - Búsquedas programadas")

    except Exception as e:
        logger.error(f"Error inicializando base de datos: {e}")

if __name__ == "__main__":
    # Verificar argumentos de línea de comandos
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == "bot":
            run_bot_only()
        elif command == "scheduler":
            run_scheduler_only()
        elif command == "init-db":
            initialize_db_only()
        elif command == "help":
            print("""
Uso: python main.py [comando]

Comandos disponibles:
  (sin argumentos)  - Ejecuta todo el sistema (bot + scheduler)
  bot              - Ejecuta solo el bot de Telegram
  scheduler        - Ejecuta solo las búsquedas programadas
  init-db          - Solo inicializa la base de datos
  help             - Muestra esta ayuda

Ejemplos:
  python main.py              # Sistema completo
  python main.py bot          # Solo bot
  python main.py scheduler    # Solo búsquedas automáticas
  python main.py init-db      # Solo crear base de datos
            """)
        else:
            print(f"Comando desconocido: {command}")
            print("Usa 'python main.py help' para ver comandos disponibles")
    else:
        # Ejecutar sistema completo por defecto
        main()
