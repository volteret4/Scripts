#!/usr/bin/env python3
"""
Enhanced Telegram Bot para Búsqueda de Conciertos
Versión mejorada con favoritos, configuración de país y notificaciones automáticas
"""

import os
import logging
import asyncio
from pathlib import Path
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ContextTypes, CallbackQueryHandler,
    ConversationHandler, MessageHandler, filters
)

# Importar los servicios de búsqueda de conciertos
from apis.ticketmaster import TicketmasterService
from apis.spotify import SpotifyService
from apis.setlistfm import SetlistfmService

# Importar el manager de base de datos
from database_manager import ConcertBotDatabase

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Estados para el ConversationHandler
WAITING_COUNTRY, WAITING_ARTIST_NAME, CONFIRMING_REMOVE = range(3)

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

# Base de datos
DB_PATH = os.environ.get('CONCERT_BOT_DB_PATH', 'concert_bot.db')
db = ConcertBotDatabase(DB_PATH)

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

# Configuración
MAX_CONCERTS_PER_SERVICE = 5
SEARCH_TIMEOUT = 30

# Códigos de país disponibles
COUNTRY_CODES = {
    'España': 'ES',
    'Francia': 'FR',
    'Italia': 'IT',
    'Alemania': 'DE',
    'Reino Unido': 'GB',
    'Portugal': 'PT',
    'Estados Unidos': 'US',
    'México': 'MX',
    'Argentina': 'AR',
    'Colombia': 'CO',
    'Chile': 'CL',
    'Brasil': 'BR'
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start que da la bienvenida al usuario y lo registra"""
    user = update.effective_user

    # Registrar o actualizar usuario en la base de datos
    user_id = db.add_or_update_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        language_code=user.language_code or 'es'
    )

    # Obtener estadísticas del usuario
    stats = db.get_user_stats(user.id)

    help_text = (
        f"¡Bienvenido al Bot de Búsqueda de Conciertos, {user.first_name}! 🎵\n\n"
        "*Comandos disponibles:*\n"
        "/b artista - Buscar conciertos para un artista\n"
        "/fav artista - Añadir artista a favoritos\n"
        "/favoritos - Ver tus artistas favoritos\n"
        "/pais - Configurar tu país\n"
        "/notificaciones - Activar/desactivar notificaciones\n"
        "/stats - Ver tus estadísticas\n"
        "/help - Mostrar esta ayuda\n\n"
        f"*Tu configuración actual:*\n"
        f"País: {stats.get('country_code', 'ES')}\n"
        f"Notificaciones: {'✅ Activadas' if stats.get('notifications_enabled') else '❌ Desactivadas'}\n"
        f"Artistas favoritos: {stats.get('favorite_artists', 0)}\n\n"
        "*Ejemplo:* `/b Metallica`"
    )

    await update.message.reply_text(help_text, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help con instrucciones detalladas"""
    await start(update, context)

async def search_concerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Busca conciertos para un artista en todos los servicios disponibles"""
    if not context.args:
        await update.message.reply_text(
            "Por favor, proporciona el nombre de un artista.\n"
            "*Ejemplo:* `/b Metallica`",
            parse_mode="Markdown"
        )
        return

    artist_name = " ".join(context.args)
    user = update.effective_user

    # Obtener país del usuario
    user_data = db.get_user(user.id)
    country_code = user_data['country_code'] if user_data else 'ES'

    # Escapar caracteres especiales de Markdown
    safe_artist_name = artist_name.replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")

    # Mensaje inicial mientras se realiza la búsqueda
    processing_message = await update.message.reply_text(
        f"🔍 Buscando conciertos para *{safe_artist_name}* en {country_code}...",
        parse_mode="Markdown"
    )

    # Realizar búsqueda en los 3 servicios
    try:
        results = await search_all_services(artist_name, country_code)

        # Formatear y enviar resultados
        response = format_concert_results(artist_name, results)

        # Botones para acciones adicionales
        keyboard = []

        # Botón para añadir a favoritos
        user_favorites = db.get_user_favorite_artists(user.id)
        favorite_names = [fav['artist_name'] for fav in user_favorites]

        if artist_name not in favorite_names:
            keyboard.append([
                InlineKeyboardButton(f"⭐ Añadir {artist_name} a favoritos",
                                   callback_data=f"add_fav_{artist_name}")
            ])

        # Botones para ver más resultados por servicio
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

async def add_favorite_artist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Añade un artista a favoritos"""
    if not context.args:
        await update.message.reply_text(
            "Por favor, proporciona el nombre de un artista.\n"
            "*Ejemplo:* `/fav Metallica`",
            parse_mode="Markdown"
        )
        return

    artist_name = " ".join(context.args)
    user = update.effective_user

    # Añadir a favoritos
    success = db.add_favorite_artist(user.id, artist_name)

    if success:
        await update.message.reply_text(
            f"⭐ *{artist_name}* añadido a tus favoritos!\n\n"
            "Ahora recibirás notificaciones automáticas cuando haya nuevos conciertos.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"*{artist_name}* ya está en tus favoritos.",
            parse_mode="Markdown"
        )

async def show_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra los artistas favoritos del usuario"""
    user = update.effective_user
    favorites = db.get_user_favorite_artists(user.id)

    if not favorites:
        await update.message.reply_text(
            "No tienes artistas favoritos aún.\n\n"
            "Usa `/fav nombre_artista` para añadir uno.",
            parse_mode="Markdown"
        )
        return

    # Crear botones para cada artista favorito
    keyboard = []
    for fav in favorites:
        artist_name = fav['artist_name']
        notifications_status = "🔔" if fav['notifications_enabled'] else "🔕"

        keyboard.append([
            InlineKeyboardButton(
                f"{notifications_status} {artist_name}",
                callback_data=f"fav_menu_{artist_name}"
            )
        ])

    # Botones adicionales
    keyboard.append([
        InlineKeyboardButton("➕ Añadir artista", callback_data="add_favorite"),
        InlineKeyboardButton("🗑️ Gestionar favoritos", callback_data="manage_favorites")
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    message_text = (
        f"⭐ *Tus artistas favoritos ({len(favorites)}):*\n\n"
        "🔔 = Notificaciones activadas\n"
        "🔕 = Notificaciones desactivadas\n\n"
        "_Selecciona un artista para ver opciones:_"
    )

    await update.message.reply_text(
        message_text,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def set_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia el proceso para configurar el país del usuario"""
    # Crear botones con países disponibles
    keyboard = []
    row = []

    for country_name, country_code in COUNTRY_CODES.items():
        row.append(InlineKeyboardButton(f"{country_name} ({country_code})",
                                      callback_data=f"country_{country_code}"))
        if len(row) == 2:  # 2 países por fila
            keyboard.append(row)
            row = []

    if row:  # Añadir la última fila si tiene elementos
        keyboard.append(row)

    reply_markup = InlineKeyboardMarkup(keyboard)

    user = update.effective_user
    user_data = db.get_user(user.id)
    current_country = user_data['country_code'] if user_data else 'ES'

    await update.message.reply_text(
        f"🌍 *Configurar país*\n\n"
        f"País actual: *{current_country}*\n\n"
        "Selecciona tu país para personalizar las búsquedas de conciertos:",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def toggle_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Activa/desactiva las notificaciones para el usuario"""
    user = update.effective_user
    new_state = db.toggle_user_notifications(user.id)

    status_text = "✅ *Notificaciones activadas*" if new_state else "❌ *Notificaciones desactivadas*"
    description = (
        "Recibirás alertas automáticas cuando haya nuevos conciertos de tus artistas favoritos."
        if new_state else
        "No recibirás notificaciones automáticas."
    )

    await update.message.reply_text(
        f"{status_text}\n\n{description}",
        parse_mode="Markdown"
    )

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra estadísticas del usuario"""
    user = update.effective_user
    stats = db.get_user_stats(user.id)

    if not stats:
        await update.message.reply_text("No se pudieron obtener tus estadísticas.")
        return

    stats_text = (
        f"📊 *Estadísticas de {user.first_name}*\n\n"
        f"⭐ Artistas favoritos: {stats['favorite_artists']}\n"
        f"🎵 Conciertos próximos: {stats['upcoming_concerts']}\n"
        f"📬 Notificaciones enviadas: {stats['notifications_sent']}\n"
        f"🌍 País: {stats['country_code']}\n"
        f"🔔 Notificaciones: {'✅ Activadas' if stats['notifications_enabled'] else '❌ Desactivadas'}"
    )

    # Botones de acción rápida
    keyboard = [
        [
            InlineKeyboardButton("⭐ Ver favoritos", callback_data="show_favorites"),
            InlineKeyboardButton("🌍 Cambiar país", callback_data="change_country")
        ],
        [
            InlineKeyboardButton("🔔 Notificaciones", callback_data="toggle_notifications")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        stats_text,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestiona las pulsaciones de botones inline"""
    query = update.callback_query
    await query.answer()

    data = query.data
    user = update.effective_user

    # Callback para añadir artista a favoritos
    if data.startswith("add_fav_"):
        artist_name = data[8:]  # Remover "add_fav_"
        success = db.add_favorite_artist(user.id, artist_name)

        if success:
            await query.edit_message_text(
                f"⭐ *{artist_name}* añadido a favoritos!\n\n"
                "Ahora recibirás notificaciones automáticas.",
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text(
                f"*{artist_name}* ya está en tus favoritos.",
                parse_mode="Markdown"
            )
        return

    # Callback para configurar país
    if data.startswith("country_"):
        country_code = data[8:]  # Remover "country_"
        success = db.update_user_country(user.id, country_code)

        if success:
            await query.edit_message_text(
                f"🌍 País actualizado a *{country_code}*\n\n"
                "Las búsquedas de conciertos usarán este país por defecto.",
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text(
                "❌ Error al actualizar el país. Inténtalo de nuevo.",
                parse_mode="Markdown"
            )
        return

    # Callback para menú de artista favorito
    if data.startswith("fav_menu_"):
        artist_name = data[9:]  # Remover "fav_menu_"

        # Obtener estado actual de notificaciones para este artista
        favorites = db.get_user_favorite_artists(user.id)
        artist_fav = next((fav for fav in favorites if fav['artist_name'] == artist_name), None)

        if not artist_fav:
            await query.edit_message_text("❌ Artista no encontrado en favoritos.")
            return

        notifications_enabled = artist_fav['notifications_enabled']
        notification_text = "🔔 Desactivar notificaciones" if notifications_enabled else "🔕 Activar notificaciones"

        keyboard = [
            [
                InlineKeyboardButton("🔍 Buscar conciertos", callback_data=f"search_{artist_name}"),
                InlineKeyboardButton(notification_text, callback_data=f"toggle_artist_notif_{artist_name}")
            ],
            [
                InlineKeyboardButton("🗑️ Eliminar de favoritos", callback_data=f"remove_fav_{artist_name}"),
                InlineKeyboardButton("🔙 Volver", callback_data="show_favorites")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"⭐ *{artist_name}*\n\n"
            f"Notificaciones: {'✅ Activadas' if notifications_enabled else '❌ Desactivadas'}\n\n"
            "¿Qué quieres hacer?",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        return

    # Callback para alternar notificaciones de artista
    if data.startswith("toggle_artist_notif_"):
        artist_name = data[20:]  # Remover "toggle_artist_notif_"
        new_state = db.toggle_artist_notifications(user.id, artist_name)

        status = "activadas" if new_state else "desactivadas"
        await query.edit_message_text(
            f"🔔 Notificaciones {status} para *{artist_name}*",
            parse_mode="Markdown"
        )
        return

    # Callback para eliminar artista de favoritos
    if data.startswith("remove_fav_"):
        artist_name = data[11:]  # Remover "remove_fav_"

        keyboard = [
            [
                InlineKeyboardButton("✅ Sí, eliminar", callback_data=f"confirm_remove_{artist_name}"),
                InlineKeyboardButton("❌ Cancelar", callback_data=f"fav_menu_{artist_name}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"🗑️ ¿Estás seguro de que quieres eliminar *{artist_name}* de tus favoritos?\n\n"
            "Ya no recibirás notificaciones de este artista.",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        return

    # Callback para confirmar eliminación
    if data.startswith("confirm_remove_"):
        artist_name = data[15:]  # Remover "confirm_remove_"
        success = db.remove_favorite_artist(user.id, artist_name)

        if success:
            await query.edit_message_text(
                f"🗑️ *{artist_name}* eliminado de tus favoritos.",
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text(
                "❌ Error al eliminar el artista. Inténtalo de nuevo.",
                parse_mode="Markdown"
            )
        return

    # Callbacks para acciones desde stats
    if data == "show_favorites":
        await show_favorites_inline(query)
        return

    if data == "change_country":
        await set_country_inline(query)
        return

    if data == "toggle_notifications":
        new_state = db.toggle_user_notifications(user.id)
        status_text = "✅ activadas" if new_state else "❌ desactivadas"

        await query.edit_message_text(
            f"🔔 Notificaciones {status_text}",
            parse_mode="Markdown"
        )
        return

    # Callback para buscar conciertos desde favoritos
    if data.startswith("search_"):
        artist_name = data[7:]  # Remover "search_"

        # Obtener país del usuario
        user_data = db.get_user(user.id)
        country_code = user_data['country_code'] if user_data else 'ES'

        # Mensaje de búsqueda
        await query.edit_message_text(
            f"🔍 Buscando conciertos para *{artist_name}* en {country_code}...",
            parse_mode="Markdown"
        )

        # Realizar búsqueda
        try:
            results = await search_all_services(artist_name, country_code)
            response = format_concert_results(artist_name, results)

            # Botón para volver a favoritos
            keyboard = [[
                InlineKeyboardButton("🔙 Volver a favoritos", callback_data="show_favorites")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                response,
                parse_mode="Markdown",
                disable_web_page_preview=True,
                reply_markup=reply_markup
            )
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error al buscar conciertos para *{artist_name}*: {str(e)}",
                parse_mode="Markdown"
            )
        return

    # Callbacks originales para "ver más"
    if data.startswith("more_"):
        await handle_more_concerts(update, context)
        return

async def show_favorites_inline(query):
    """Muestra favoritos en callback inline"""
    user = query.from_user
    favorites = db.get_user_favorite_artists(user.id)

    if not favorites:
        await query.edit_message_text(
            "No tienes artistas favoritos aún.\n\n"
            "Usa `/fav nombre_artista` para añadir uno.",
            parse_mode="Markdown"
        )
        return

    # Crear botones para cada artista favorito
    keyboard = []
    for fav in favorites:
        artist_name = fav['artist_name']
        notifications_status = "🔔" if fav['notifications_enabled'] else "🔕"

        keyboard.append([
            InlineKeyboardButton(
                f"{notifications_status} {artist_name}",
                callback_data=f"fav_menu_{artist_name}"
            )
        ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    message_text = (
        f"⭐ *Tus artistas favoritos ({len(favorites)}):*\n\n"
        "🔔 = Notificaciones activadas\n"
        "🔕 = Notificaciones desactivadas\n\n"
        "_Selecciona un artista para ver opciones:_"
    )

    await query.edit_message_text(
        message_text,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def set_country_inline(query):
    """Configurar país desde callback inline"""
    # Crear botones con países disponibles
    keyboard = []
    row = []

    for country_name, country_code in COUNTRY_CODES.items():
        row.append(InlineKeyboardButton(f"{country_name} ({country_code})",
                                      callback_data=f"country_{country_code}"))
        if len(row) == 2:  # 2 países por fila
            keyboard.append(row)
            row = []

    if row:  # Añadir la última fila si tiene elementos
        keyboard.append(row)

    reply_markup = InlineKeyboardMarkup(keyboard)

    user = query.from_user
    user_data = db.get_user(user.id)
    current_country = user_data['country_code'] if user_data else 'ES'

    await query.edit_message_text(
        f"🌍 *Configurar país*\n\n"
        f"País actual: *{current_country}*\n\n"
        "Selecciona tu país:",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def handle_more_concerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestiona los callbacks para ver más conciertos (función original adaptada)"""
    query = update.callback_query
    await query.answer()

    # Extraer datos del callback
    parts = query.data.split("_", 2)
    if len(parts) < 3 or parts[0] != "more":
        return

    service_name = parts[1]
    artist_name = parts[2]

    # Obtener país del usuario
    user = query.from_user
    user_data = db.get_user(user.id)
    country_code = user_data['country_code'] if user_data else 'ES'

    # Escapar caracteres especiales de Markdown
    safe_artist_name = artist_name.replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")

    try:
        # Buscar de nuevo en el servicio específico con timeout
        if service_name == "Ticketmaster":
            concerts, message = await asyncio.wait_for(
                asyncio.to_thread(ticketmaster_service.search_concerts, artist_name, country_code),
                timeout=SEARCH_TIMEOUT
            )
        elif service_name == "Spotify":
            concerts, message = await asyncio.wait_for(
                asyncio.to_thread(spotify_service.search_artist_and_concerts, artist_name),
                timeout=SEARCH_TIMEOUT
            )
        elif service_name == "Setlist.fm":
            concerts, message = await asyncio.wait_for(
                asyncio.to_thread(setlistfm_service.search_concerts, artist_name, country_code),
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

        # Formatear todos los conciertos (implementación original adaptada)
        response = format_all_concerts_for_service(artist_name, service_name, concerts)

        # Botón para volver
        keyboard = [[
            InlineKeyboardButton("🔍 Volver a la búsqueda completa",
                              callback_data=f"search_{artist_name}")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            response,
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

def format_all_concerts_for_service(artist_name: str, service_name: str, concerts: list) -> str:
    """Formatea todos los conciertos de un servicio específico"""
    safe_artist_name = artist_name.replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")

    # Ordenar conciertos por fecha
    try:
        sorted_concerts = sorted(concerts, key=lambda x: x.get('date', '9999-99-99'))
    except Exception:
        sorted_concerts = concerts

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

    return "\n".join(response)

# Funciones originales adaptadas
async def search_all_services(artist_name, country_code="ES"):
    """Busca conciertos en todos los servicios (función original adaptada)"""

    async def safe_search_ticketmaster():
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

    # Ejecutar todas las búsquedas en paralelo
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
    """Formatea los resultados de los conciertos (función original)"""
    safe_artist_name = artist_name.replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")

    response = [f"🎵 *Conciertos para {safe_artist_name}*\n"]
    total_concerts = 0

    for service_name, (concerts, message) in results.items():
        if concerts:
            try:
                sorted_concerts = sorted(concerts, key=lambda x: x.get('date', '9999-99-99'))
            except Exception:
                sorted_concerts = concerts

            display_concerts = sorted_concerts[:MAX_CONCERTS_PER_SERVICE]
            response.append(f"*{service_name}* ({len(concerts)} encontrados):")

            for concert in display_concerts:
                venue = concert.get('venue', 'Lugar desconocido')
                city = concert.get('city', '')
                date = concert.get('date', 'Fecha desconocida')

                if date and len(date) >= 10 and '-' in date:
                    try:
                        date_obj = datetime.strptime(date[:10], '%Y-%m-%d')
                        date = date_obj.strftime('%d/%m/%Y')
                    except ValueError:
                        pass

                safe_venue = str(venue).replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")
                safe_city = str(city).replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")
                location = f"{safe_venue}, {safe_city}" if safe_city else safe_venue

                url = concert.get('url', '')

                if url and url.startswith(('http://', 'https://')):
                    url = url.replace(")", "\\)")
                    response.append(f"• {date}: [{location}]({url})")
                else:
                    response.append(f"• {date}: {location}")

            if len(sorted_concerts) > MAX_CONCERTS_PER_SERVICE:
                remaining = len(sorted_concerts) - MAX_CONCERTS_PER_SERVICE
                response.append(f"_...y {remaining} más (usa los botones para ver todos)_\n")
            else:
                response.append("")

            total_concerts += len(concerts)
        else:
            if any(keyword in message for keyword in ["Error", "Timeout", "No se encontraron"]):
                safe_message = message.replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")
                response.append(f"*{service_name}*: _{safe_message}_\n")

    if total_concerts == 0:
        response.append(f"❌ No se encontraron conciertos para *{safe_artist_name}*.")
        response.append("\n💡 *Sugerencias:*")
        response.append("• Verifica la ortografía del nombre del artista")
        response.append("• Prueba con nombres alternativos o abreviaciones")
        response.append("• Algunos artistas pueden no tener conciertos programados")

    return "\n".join(response)

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

    # Comandos básicos
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("b", search_concerts))

    # Comandos de favoritos
    application.add_handler(CommandHandler("fav", add_favorite_artist))
    application.add_handler(CommandHandler("favoritos", show_favorites))

    # Comandos de configuración
    application.add_handler(CommandHandler("pais", set_country))
    application.add_handler(CommandHandler("notificaciones", toggle_notifications))
    application.add_handler(CommandHandler("stats", show_stats))

    # Callback handlers
    application.add_handler(CallbackQueryHandler(button_callback))

    # Iniciar el bot
    logger.info("🤖 Bot mejorado iniciado. Presiona Ctrl+C para detenerlo.")
    try:
        application.run_polling()
    except KeyboardInterrupt:
        logger.info("🛑 Bot detenido por el usuario")
    except Exception as e:
        logger.error(f"❌ Error crítico en el bot: {e}")

if __name__ == "__main__":
    main()
