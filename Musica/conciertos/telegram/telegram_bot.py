#!/usr/bin/env python3
import os
import logging
import asyncio
from pathlib import Path
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler


# Importar los servicios de búsqueda de conciertos
from apis.ticketmaster import TicketmasterService
from apis.spotify import SpotifyService
from apis.setlistfm import SetlistfmService

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Rutas y configuración
BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / "cache"
CACHE_DIR.mkdir(exist_ok=True)

# Configuración del bot (lee desde variables de entorno)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TICKETMASTER_API_KEY = os.environ.get("TICKETMASTER_API_KEY")
SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.environ.get("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback")
SETLISTFM_API_KEY = os.environ.get("SETLISTFM_API_KEY")

# Inicializar servicios
ticketmaster_service = TicketmasterService(
    api_key=TICKETMASTER_API_KEY,
    cache_dir=CACHE_DIR / "ticketmaster"
)

spotify_service = SpotifyService(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET,
    redirect_uri=SPOTIFY_REDIRECT_URI,
    cache_dir=CACHE_DIR / "spotify"
)

setlistfm_service = SetlistfmService(
    api_key=SETLISTFM_API_KEY,
    cache_dir=CACHE_DIR / "setlistfm",
    db_path=None  # No usamos DB para el bot
)

# Limitar resultados por servicio para evitar mensajes muy largos
MAX_CONCERTS_PER_SERVICE = 5
SEARCH_TIMEOUT = 30  # Timeout en segundos para cada servicio

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start que da la bienvenida al usuario"""
    help_text = (
        "¡Bienvenido al Bot de Búsqueda de Conciertos!\n\n"
        "Comandos disponibles:\n"
        "/b artista - Buscar conciertos para un artista\n"
        "/help - Mostrar este mensaje de ayuda\n\n"
        "Ejemplo: `/b Metallica`"
    )
    await update.message.reply_text(help_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help con instrucciones"""
    await start(update, context)

async def search_concerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Busca conciertos para un artista en todos los servicios disponibles"""
    if not context.args:
        await update.message.reply_text("Por favor, proporciona el nombre de un artista. Ejemplo: `/b Metallica`")
        return

    artist_name = " ".join(context.args)

    # Escapar caracteres especiales de Markdown
    safe_artist_name = artist_name.replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")

    # Mensaje inicial mientras se realiza la búsqueda
    processing_message = await update.message.reply_text(
        f"🔍 Buscando conciertos para *{safe_artist_name}*...",
        parse_mode="Markdown"
    )

    # Realizar búsqueda en los 3 servicios (paralelizamos para mayor rapidez)
    try:
        results = await search_all_services(artist_name)

        # Formatear y enviar resultados
        response = format_concert_results(artist_name, results)

        # Botones para ver más resultados por servicio
        keyboard = []
        for service_name, (concerts, _) in results.items():
            if len(concerts) > MAX_CONCERTS_PER_SERVICE:
                keyboard.append([
                    InlineKeyboardButton(f"Ver todos en {service_name} ({len(concerts)})",
                                         callback_data=f"more_{service_name}_{artist_name}")
                ])

        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

        # Actualizar el mensaje con los resultados
        await processing_message.edit_text(
            response,
            parse_mode="Markdown",
            disable_web_page_preview=True,
            reply_markup=reply_markup
        )

    except Exception as e:
        logger.error(f"Error searching concerts: {e}")
        await processing_message.edit_text(
            f"❌ Error al buscar conciertos para *{safe_artist_name}*: {str(e)}",
            parse_mode="Markdown"
        )

async def search_all_services(artist_name, country_code="ES"):
    """Busca conciertos en todos los servicios de forma asíncrona con timeouts"""

    async def safe_search_ticketmaster():
        """Búsqueda segura en Ticketmaster con timeout"""
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(ticketmaster_service.search_concerts, artist_name, country_code),
                timeout=SEARCH_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.warning(f"Timeout en Ticketmaster para {artist_name}")
            return [], f"Timeout en Ticketmaster (>{SEARCH_TIMEOUT}s)"
        except Exception as e:
            logger.error(f"Error en Ticketmaster para {artist_name}: {e}")
            return [], f"Error en Ticketmaster: {str(e)}"

    async def safe_search_spotify():
        """Búsqueda segura en Spotify con timeout"""
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(spotify_service.search_artist_and_concerts, artist_name),
                timeout=SEARCH_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.warning(f"Timeout en Spotify para {artist_name}")
            return [], f"Timeout en Spotify (>{SEARCH_TIMEOUT}s)"
        except Exception as e:
            logger.error(f"Error en Spotify para {artist_name}: {e}")
            return [], f"Error en Spotify: {str(e)}"

    async def safe_search_setlistfm():
        """Búsqueda segura en Setlist.fm con timeout"""
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(setlistfm_service.search_concerts, artist_name, country_code),
                timeout=SEARCH_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.warning(f"Timeout en Setlist.fm para {artist_name}")
            return [], f"Timeout en Setlist.fm (>{SEARCH_TIMEOUT}s)"
        except Exception as e:
            logger.error(f"Error en Setlist.fm para {artist_name}: {e}")
            return [], f"Error en Setlist.fm: {str(e)}"

    # Ejecutar todas las búsquedas en paralelo con manejo de errores individual
    tasks = [
        safe_search_ticketmaster(),
        safe_search_spotify(),
        safe_search_setlistfm()
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Procesar resultados
    processed_results = {}
    service_names = ["Ticketmaster", "Spotify", "Setlist.fm"]

    for i, (service_name, result) in enumerate(zip(service_names, results)):
        if isinstance(result, Exception):
            processed_results[service_name] = ([], f"Error en {service_name}: {str(result)}")
        elif isinstance(result, tuple) and len(result) == 2:
            processed_results[service_name] = result
        else:
            processed_results[service_name] = ([], f"Formato de respuesta desconocido en {service_name}")

    return processed_results

def format_concert_results(artist_name, results):
    """Formatea los resultados de los conciertos para mostrarlos en Telegram"""
    # Escapar caracteres especiales de Markdown en el nombre del artista
    safe_artist_name = artist_name.replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")

    response = [f"🎵 *Conciertos para {safe_artist_name}*\n"]
    total_concerts = 0

    for service_name, (concerts, message) in results.items():
        if concerts:
            # Ordenar conciertos por fecha
            try:
                sorted_concerts = sorted(concerts, key=lambda x: x.get('date', '9999-99-99'))
            except Exception:
                sorted_concerts = concerts

            # Limitar cantidad de conciertos mostrados
            display_concerts = sorted_concerts[:MAX_CONCERTS_PER_SERVICE]
            response.append(f"*{service_name}* ({len(concerts)} encontrados):")

            for concert in display_concerts:
                venue = concert.get('venue', 'Lugar desconocido')
                city = concert.get('city', '')
                date = concert.get('date', 'Fecha desconocida')

                # Formatear fecha si está en formato ISO
                if date and len(date) >= 10 and '-' in date:
                    try:
                        date_obj = datetime.strptime(date[:10], '%Y-%m-%d')
                        date = date_obj.strftime('%d/%m/%Y')
                    except ValueError:
                        pass

                # Escapar caracteres especiales de Markdown
                safe_venue = str(venue).replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")
                safe_city = str(city).replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")
                location = f"{safe_venue}, {safe_city}" if safe_city else safe_venue

                url = concert.get('url', '')

                if url and url.startswith(('http://', 'https://')):
                    # Asegurarse de que la URL es válida para Markdown
                    url = url.replace(")", "\\)")
                    response.append(f"• {date}: [{location}]({url})")
                else:
                    response.append(f"• {date}: {location}")

            # Indicar si hay más conciertos
            if len(sorted_concerts) > MAX_CONCERTS_PER_SERVICE:
                remaining = len(sorted_concerts) - MAX_CONCERTS_PER_SERVICE
                response.append(f"_...y {remaining} más (usa los botones para ver todos)_\n")
            else:
                response.append("")

            total_concerts += len(concerts)
        else:
            # Solo agregamos el servicio si hay un mensaje específico de error o timeout
            if any(keyword in message for keyword in ["Error", "Timeout", "No se encontraron"]):
                # Escapar caracteres especiales en el mensaje de error
                safe_message = message.replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")
                response.append(f"*{service_name}*: _{safe_message}_\n")

    if total_concerts == 0:
        response.append(f"❌ No se encontraron conciertos para *{safe_artist_name}*.")
        response.append("\n💡 *Sugerencias:*")
        response.append("• Verifica la ortografía del nombre del artista")
        response.append("• Prueba con nombres alternativos o abreviaciones")
        response.append("• Algunos artistas pueden no tener conciertos programados")

    return "\n".join(response)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestiona las pulsaciones de botones para ver más conciertos"""
    query = update.callback_query
    await query.answer()

    # Extraer datos del callback
    # El formato es "more_SERVICE_ARTISTNAME"
    parts = query.data.split("_", 2)
    if len(parts) < 3 or parts[0] != "more":
        return

    service_name = parts[1]
    artist_name = parts[2]

    # Escapar caracteres especiales de Markdown
    safe_artist_name = artist_name.replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")

    try:
        # Buscar de nuevo en el servicio específico con timeout
        if service_name == "Ticketmaster":
            concerts, message = await asyncio.wait_for(
                asyncio.to_thread(ticketmaster_service.search_concerts, artist_name),
                timeout=SEARCH_TIMEOUT
            )
        elif service_name == "Spotify":
            concerts, message = await asyncio.wait_for(
                asyncio.to_thread(spotify_service.search_artist_and_concerts, artist_name),
                timeout=SEARCH_TIMEOUT
            )
        elif service_name == "Setlist.fm":
            concerts, message = await asyncio.wait_for(
                asyncio.to_thread(setlistfm_service.search_concerts, artist_name),
                timeout=SEARCH_TIMEOUT
            )
        else:
            await query.edit_message_text(
                f"Servicio desconocido: {service_name}",
                parse_mode="Markdown"
            )
            return

        if not concerts:
            safe_message = message.replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")
            await query.edit_message_text(
                f"No se encontraron conciertos para *{safe_artist_name}* en {service_name}.\n\n{safe_message}",
                parse_mode="Markdown"
            )
            return

        # Ordenar conciertos por fecha
        try:
            sorted_concerts = sorted(concerts, key=lambda x: x.get('date', '9999-99-99'))
        except Exception:
            sorted_concerts = concerts

        # Formatear todos los conciertos
        response = [f"🎵 *Todos los conciertos de {safe_artist_name} en {service_name}*\n"]

        for concert in sorted_concerts:
            venue = concert.get('venue', 'Lugar desconocido')
            city = concert.get('city', '')
            date = concert.get('date', 'Fecha desconocida')

            # Formatear fecha si está en formato ISO
            if date and len(date) >= 10 and '-' in date:
                try:
                    date_obj = datetime.strptime(date[:10], '%Y-%m-%d')
                    date = date_obj.strftime('%d/%m/%Y')
                except ValueError:
                    pass

            # Escapar caracteres especiales de Markdown
            safe_venue = str(venue).replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")
            safe_city = str(city).replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")
            location = f"{safe_venue}, {safe_city}" if safe_city else safe_venue

            url = concert.get('url', '')

            if url and url.startswith(('http://', 'https://')):
                url = url.replace(")", "\\)")
                response.append(f"• {date}: [{location}]({url})")
            else:
                response.append(f"• {date}: {location}")

        # Botón para volver a la búsqueda completa
        keyboard = [[
            InlineKeyboardButton("🔍 Volver a la búsqueda completa",
                              callback_data=f"search_{artist_name}")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Enviamos un nuevo mensaje si el resultado es muy largo
        if len("\n".join(response)) > 4000:
            chunks = []
            current_chunk = [response[0]]
            current_length = len(response[0])

            for line in response[1:]:
                if current_length + len(line) + 1 > 3900:  # +1 por el salto de línea
                    chunks.append("\n".join(current_chunk))
                    current_chunk = [f"🎵 *Conciertos de {safe_artist_name} en {service_name} (continuación)*\n"]
                    current_length = len(current_chunk[0])

                current_chunk.append(line)
                current_length += len(line) + 1

            if current_chunk:
                chunks.append("\n".join(current_chunk))

            # Enviamos el primer chunk como edición del mensaje original
            await query.edit_message_text(
                chunks[0],
                parse_mode="Markdown",
                disable_web_page_preview=True,
                reply_markup=reply_markup if len(chunks) == 1 else None
            )

            # Enviamos el resto como mensajes nuevos
            for i, chunk in enumerate(chunks[1:], 1):
                if i == len(chunks) - 1:  # Si es el último chunk
                    await query.message.reply_text(
                        chunk,
                        parse_mode="Markdown",
                        disable_web_page_preview=True,
                        reply_markup=reply_markup
                    )
                else:
                    await query.message.reply_text(
                        chunk,
                        parse_mode="Markdown",
                        disable_web_page_preview=True
                    )
        else:
            # Si el mensaje no es muy largo, lo enviamos en una sola parte
            await query.edit_message_text(
                "\n".join(response),
                parse_mode="Markdown",
                disable_web_page_preview=True,
                reply_markup=reply_markup
            )

    except asyncio.TimeoutError:
        await query.edit_message_text(
            f"⏰ Timeout al buscar más conciertos de *{safe_artist_name}* en {service_name}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error showing more concerts: {e}")
        await query.edit_message_text(
            f"❌ Error al mostrar más conciertos de *{safe_artist_name}* en {service_name}: {str(e)}",
            parse_mode="Markdown"
        )

async def search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestiona el callback para volver a la búsqueda completa"""
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_", 1)
    if len(parts) < 2 or parts[0] != "search":
        return

    artist_name = parts[1]

    # Escapar caracteres especiales de Markdown
    safe_artist_name = artist_name.replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")

    # Mensaje mientras se realiza la búsqueda
    await query.edit_message_text(
        f"🔍 Buscando conciertos para *{safe_artist_name}*...",
        parse_mode="Markdown"
    )

    try:
        results = await search_all_services(artist_name)
        response = format_concert_results(artist_name, results)

        # Botones para ver más resultados
        keyboard = []
        for service_name, (concerts, _) in results.items():
            if len(concerts) > MAX_CONCERTS_PER_SERVICE:
                keyboard.append([
                    InlineKeyboardButton(f"Ver todos en {service_name} ({len(concerts)})",
                                        callback_data=f"more_{service_name}_{artist_name}")
                ])

        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

        await query.edit_message_text(
            response,
            parse_mode="Markdown",
            disable_web_page_preview=True,
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error in search callback: {e}")
        await query.edit_message_text(
            f"❌ Error al buscar conciertos para *{safe_artist_name}*: {str(e)}",
            parse_mode="Markdown"
        )

def validate_services():
    """Valida que los servicios están configurados correctamente"""
    issues = []

    if not TICKETMASTER_API_KEY:
        issues.append("⚠️ TICKETMASTER_API_KEY no configurada")

    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        issues.append("⚠️ Credenciales de Spotify incompletas")

    if not SETLISTFM_API_KEY:
        issues.append("⚠️ SETLISTFM_API_KEY no configurada")

    if issues:
        logger.warning("Problemas de configuración detectados:")
        for issue in issues:
            logger.warning(issue)
    else:
        logger.info("✅ Todos los servicios están configurados")

    return len(issues) == 0

def main():
    """Función principal para ejecutar el bot"""
    # Verificar que tenemos el token de Telegram
    if not TELEGRAM_BOT_TOKEN:
        logger.error("❌ No se ha configurado TELEGRAM_BOT_TOKEN en las variables de entorno")
        return

    # Validar configuración de servicios
    validate_services()

    # Crear la aplicación y agregar handlers
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("b", search_concerts))
    application.add_handler(CallbackQueryHandler(button_callback, pattern="^more_"))
    application.add_handler(CallbackQueryHandler(search_callback, pattern="^search_"))

    # Iniciar el bot
    logger.info("🤖 Bot iniciado. Presiona Ctrl+C para detenerlo.")
    try:
        application.run_polling()
    except KeyboardInterrupt:
        logger.info("🛑 Bot detenido por el usuario")
    except Exception as e:
        logger.error(f"❌ Error crítico en el bot: {e}")

if __name__ == "__main__":
    main()
