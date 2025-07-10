#!/usr/bin/env python3
"""
Bot de Telegram para buscar lanzamientos musicales usando Muspy y MusicBrainz
"""
import os
import logging
import requests
import json
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class MuspyTelegramBot:
    def __init__(self, telegram_token: str, muspy_username: str, muspy_api_key: str, muspy_password: str):
        """
        Inicializa el bot de Telegram

        Args:
            telegram_token: Token del bot de Telegram
            muspy_username: Usuario de Muspy
            muspy_api_key: API key de Muspy (también es el user ID)
            muspy_password: Contraseña de Muspy
        """
        self.telegram_token = telegram_token
        self.muspy_username = muspy_username
        self.muspy_api_key = muspy_api_key
        self.muspy_password = muspy_password
        self.muspy_base_url = "https://muspy.com/api/1"

        # Almacenamiento temporal de búsquedas y artistas por usuario
        self.user_searches: Dict[int, List[Dict]] = {}
        self.user_artists: Dict[int, List[Dict]] = {}

        # Headers para MusicBrainz
        self.mb_headers = {
            "User-Agent": "MuspyTelegramBot/1.0 (telegram-bot)"
        }

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /start"""
        welcome_text = """
🎵 *Bot de Lanzamientos Musicales*

¡Hola! Este bot te ayuda a encontrar próximos lanzamientos de tus artistas favoritos.

*Comandos disponibles:*
• `/buscar [artista]` - Busca lanzamientos de un artista
• `/artistas` - Lista tus artistas seguidos en Muspy
• `/mostrar` - Muestra próximos lanzamientos de todos tus artistas
• `/help` - Muestra esta ayuda

*Ejemplo:*
`/buscar Radiohead`

El bot buscará el artista en MusicBrainz y luego consultará los próximos lanzamientos en Muspy.
        """
        await update.message.reply_text(welcome_text, parse_mode='Markdown')

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /help"""
        help_text = """
🔍 *Cómo usar el bot:*

1. Usa `/buscar [nombre del artista]` para buscar lanzamientos
2. Usa `/artistas` para ver tu lista de artistas seguidos
3. Usa `/mostrar` para ver próximos lanzamientos de todos tus artistas
4. Si hay múltiples artistas con el mismo nombre, selecciona el correcto
5. El bot mostrará los próximos lanzamientos encontrados

*Ejemplos:*
• `/buscar The Beatles`
• `/buscar Daft Punk`
• `/buscar Iron Maiden`
• `/artistas` - Ver tu lista de seguidos
• `/mostrar` - Ver todos los próximos lanzamientos

💡 *Tip:* Puedes ser más específico si hay artistas con nombres similares.
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def buscar_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /buscar [artista]"""
        if not context.args:
            await update.message.reply_text(
                "❌ Por favor proporciona el nombre de un artista.\n"
                "Ejemplo: `/buscar Radiohead`",
                parse_mode='Markdown'
            )
            return

        artist_name = " ".join(context.args)
        user_id = update.effective_user.id

        # Mensaje de "buscando..."
        searching_msg = await update.message.reply_text(
            f"🔍 Buscando información de *{artist_name}*...",
            parse_mode='Markdown'
        )

        try:
            # Buscar artista en MusicBrainz
            artists = await self.search_musicbrainz_artist(artist_name)

            if not artists:
                await searching_msg.edit_text(
                    f"❌ No se encontró ningún artista con el nombre *{artist_name}*",
                    parse_mode='Markdown'
                )
                return

            if len(artists) == 1:
                # Solo un artista encontrado, buscar directamente
                artist = artists[0]
                await searching_msg.edit_text(
                    f"✅ Artista encontrado: *{artist['name']}*\n"
                    f"🔍 Buscando lanzamientos...",
                    parse_mode='Markdown'
                )
                await self.get_releases_for_artist(update, artist, searching_msg)
            else:
                # Múltiples artistas, mostrar opciones
                self.user_searches[user_id] = artists
                await self.show_artist_selection(update, artists, searching_msg)

        except Exception as e:
            logger.error(f"Error en búsqueda: {e}")
            await searching_msg.edit_text(
                "❌ Error al buscar el artista. Inténtalo de nuevo más tarde."
            )

    async def artistas_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /artistas - Lista los artistas seguidos en Muspy"""
        user_id = update.effective_user.id

        # Mensaje de "cargando..."
        loading_msg = await update.message.reply_text(
            "🔍 Cargando tu lista de artistas seguidos...",
            parse_mode='Markdown'
        )

        try:
            # Obtener lista de artistas seguidos
            artists = await self.get_followed_artists()

            if not artists:
                await loading_msg.edit_text(
                    "📭 No se encontraron artistas seguidos en tu cuenta de Muspy.",
                    parse_mode='Markdown'
                )
                return

            # Almacenar artistas para este usuario
            self.user_artists[user_id] = artists

            # Mostrar primera página
            await self.show_artists_page(loading_msg, user_id, page=0)

        except Exception as e:
            logger.error(f"Error obteniendo artistas: {e}")
            await loading_msg.edit_text(
                "❌ Error al obtener la lista de artistas. Verifica tu conexión con Muspy."
            )

    async def get_followed_artists(self) -> List[Dict]:
        """
        Obtiene la lista de artistas seguidos desde Muspy

        Returns:
            Lista de artistas con mbid, name, sort_name, disambiguation
        """
        try:
            url = f"{self.muspy_base_url}/artists/{self.muspy_api_key}"
            auth = (self.muspy_username, self.muspy_password)

            response = requests.get(url, auth=auth, timeout=15)

            if response.status_code == 401:
                logger.error("Error de autenticación con Muspy")
                return []
            elif response.status_code != 200:
                logger.error(f"Error al consultar Muspy: {response.status_code}")
                return []

            artists = response.json()

            # Ordenar por nombre para mejor navegación
            artists.sort(key=lambda x: x.get('sort_name', x.get('name', '')).lower())

            return artists

        except requests.RequestException as e:
            logger.error(f"Error de conexión con Muspy: {e}")
            return []
        except Exception as e:
            logger.error(f"Error obteniendo artistas: {e}")
            return []

    async def show_artists_page(self, message, user_id: int, page: int = 0) -> None:
        """
        Muestra una página de artistas seguidos

        Args:
            message: Mensaje a editar
            user_id: ID del usuario
            page: Número de página (empezando desde 0)
        """
        if user_id not in self.user_artists:
            await message.edit_text("❌ Lista de artistas no encontrada. Usa /artistas de nuevo.")
            return

        artists = self.user_artists[user_id]
        artists_per_page = 20
        total_pages = (len(artists) + artists_per_page - 1) // artists_per_page

        if page >= total_pages:
            page = total_pages - 1
        elif page < 0:
            page = 0

        start_idx = page * artists_per_page
        end_idx = min(start_idx + artists_per_page, len(artists))
        page_artists = artists[start_idx:end_idx]

        # Construir texto
        text = f"🎵 *Artistas seguidos en Muspy*\n"
        text += f"📊 Total: {len(artists)} artistas\n"
        text += f"📄 Página {page + 1} de {total_pages}\n\n"

        for i, artist in enumerate(page_artists, start_idx + 1):
            name = artist.get('name', 'Sin nombre')
            disambiguation = artist.get('disambiguation', '')

            # Formato: número. nombre (disambiguation si existe)
            artist_line = f"{i}. *{name}*"
            if disambiguation:
                artist_line += f" _{disambiguation}_"

            text += artist_line + "\n"

        # Crear botones de navegación
        keyboard = []
        nav_buttons = []

        # Botón anterior
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton("⬅️ Anterior", callback_data=f"artists_page_{page-1}")
            )

        # Botón de página actual
        nav_buttons.append(
            InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data="current_page")
        )

        # Botón siguiente
        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton("Siguiente ➡️", callback_data=f"artists_page_{page+1}")
            )

        if nav_buttons:
            keyboard.append(nav_buttons)

        # Botón para seleccionar artista
        keyboard.append([
            InlineKeyboardButton("🎯 Ver lanzamientos", callback_data="select_from_followed")
        ])

        # Botón para cerrar
        keyboard.append([
            InlineKeyboardButton("❌ Cerrar", callback_data="close_artists")
        ])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await message.edit_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    async def show_artist_selection_from_followed(self, query, user_id: int) -> None:
        """Muestra la lista de artistas seguidos para seleccionar uno"""
        if user_id not in self.user_artists:
            await query.edit_message_text("❌ Lista de artistas no encontrada.")
            return

        artists = self.user_artists[user_id]

        # Mostrar solo los primeros 30 artistas para evitar problemas con botones
        display_artists = artists[:30]

        text = f"🎯 *Selecciona un artista para ver sus lanzamientos:*\n\n"
        text += f"📊 Mostrando {len(display_artists)} de {len(artists)} artistas\n\n"

        keyboard = []
        for i, artist in enumerate(display_artists):
            name = artist.get('name', 'Sin nombre')
            disambiguation = artist.get('disambiguation', '')

            button_text = name[:30] + ('...' if len(name) > 30 else '')
            if disambiguation:
                button_text += f" ({disambiguation[:10]}{'...' if len(disambiguation) > 10 else ''})"

            keyboard.append([
                InlineKeyboardButton(button_text, callback_data=f"select_followed_{i}")
            ])

        # Botón para volver
        keyboard.append([
            InlineKeyboardButton("⬅️ Volver a la lista", callback_data="artists_page_0")
        ])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    async def search_musicbrainz_artist(self, artist_name: str) -> List[Dict]:
        """
        Busca un artista en MusicBrainz

        Returns:
            Lista de artistas encontrados con id, name, disambiguation, etc.
        """
        try:
            url = "https://musicbrainz.org/ws/2/artist/"
            params = {
                "query": f"artist:{artist_name}",
                "fmt": "json",
                "limit": 10
            }

            response = requests.get(url, params=params, headers=self.mb_headers, timeout=10)
            response.raise_for_status()

            data = response.json()
            artists = []

            for artist in data.get("artists", []):
                artist_info = {
                    "id": artist.get("id"),
                    "name": artist.get("name"),
                    "disambiguation": artist.get("disambiguation", ""),
                    "country": artist.get("country", ""),
                    "type": artist.get("type", ""),
                    "score": artist.get("score", 0)
                }

                # Añadir información adicional si está disponible
                if "life-span" in artist:
                    life_span = artist["life-span"]
                    if "begin" in life_span:
                        artist_info["begin"] = life_span["begin"]
                    if "end" in life_span:
                        artist_info["end"] = life_span["end"]

                artists.append(artist_info)

            # Ordenar por score (relevancia)
            artists.sort(key=lambda x: x["score"], reverse=True)

            return artists

        except Exception as e:
            logger.error(f"Error buscando en MusicBrainz: {e}")
            return []

    async def show_artist_selection(self, update: Update, artists: List[Dict], message) -> None:
        """Muestra una lista de artistas para seleccionar"""
        text = f"🎯 Encontrados *{len(artists)}* artistas:\n\n"

        keyboard = []
        for i, artist in enumerate(artists, 1):
            # Información del artista
            artist_info = f"*{artist['name']}*"

            if artist.get('disambiguation'):
                artist_info += f" _{artist['disambiguation']}_"

            details = []
            if artist.get('country'):
                details.append(f"🌍 {artist['country']}")

            if artist.get('begin'):
                if artist.get('end'):
                    details.append(f"📅 {artist['begin']}-{artist['end']}")
                else:
                    details.append(f"📅 desde {artist['begin']}")

            if details:
                artist_info += f" ({', '.join(details)})"

            text += f"{i}. {artist_info}\n"

            # Botón para seleccionar
            keyboard.append([
                InlineKeyboardButton(
                    f"{i}. {artist['name'][:30]}{'...' if len(artist['name']) > 30 else ''}",
                    callback_data=f"select_artist_{i-1}"
                )
            ])

        text += "\n💡 Selecciona el artista correcto:"

        reply_markup = InlineKeyboardMarkup(keyboard)
        await message.edit_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    async def artist_selection_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Maneja la selección de un artista"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id

        if user_id not in self.user_searches:
            await query.edit_message_text("❌ Búsqueda expirada. Usa /buscar de nuevo.")
            return

        try:
            # Extraer el índice del artista seleccionado
            artist_index = int(query.data.split("_")[-1])
            artist = self.user_searches[user_id][artist_index]

            await query.edit_message_text(
                f"✅ Seleccionaste: *{artist['name']}*\n"
                f"🔍 Buscando lanzamientos...",
                parse_mode='Markdown'
            )

            # Buscar lanzamientos
            await self.get_releases_for_artist(update, artist, query.message)

            # Limpiar búsqueda temporal
            del self.user_searches[user_id]

        except (IndexError, ValueError) as e:
            logger.error(f"Error en selección de artista: {e}")
            await query.edit_message_text("❌ Error en la selección. Inténtalo de nuevo.")

    async def artists_navigation_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Maneja la navegación entre páginas de artistas"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id

        if query.data == "current_page":
            # No hacer nada si presiona el botón de página actual
            return
        elif query.data == "close_artists":
            # Cerrar lista de artistas
            if user_id in self.user_artists:
                del self.user_artists[user_id]
            await query.edit_message_text("✅ Lista de artistas cerrada.")
            return
        elif query.data == "select_from_followed":
            # Cambiar a modo de selección
            await self.show_artist_selection_from_followed(query, user_id)
            return
        elif query.data.startswith("artists_page_"):
            # Navegación de páginas
            try:
                page = int(query.data.split("_")[-1])
                await self.show_artists_page(query.message, user_id, page)
            except ValueError:
                await query.edit_message_text("❌ Error en la navegación.")
        elif query.data.startswith("select_followed_"):
            # Selección de artista desde la lista de seguidos
            await self.handle_followed_artist_selection(query, user_id)

    async def handle_followed_artist_selection(self, query, user_id: int) -> None:
        """Maneja la selección de un artista desde la lista de seguidos"""
        if user_id not in self.user_artists:
            await query.edit_message_text("❌ Lista de artistas no encontrada.")
            return

        try:
            # Extraer índice del artista
            artist_index = int(query.data.split("_")[-1])
            artist = self.user_artists[user_id][artist_index]

            await query.edit_message_text(
                f"✅ Seleccionaste: *{artist['name']}*\n"
                f"🔍 Buscando lanzamientos...",
                parse_mode='Markdown'
            )

            # Buscar lanzamientos para este artista
            await self.get_releases_for_followed_artist(query, artist)

            # Limpiar datos temporales
            if user_id in self.user_artists:
                del self.user_artists[user_id]

        except (IndexError, ValueError) as e:
            logger.error(f"Error en selección de artista seguido: {e}")
            await query.edit_message_text("❌ Error en la selección.")

    async def get_releases_for_artist(self, update: Update, artist: Dict, message) -> None:
        """Obtiene y muestra los lanzamientos de un artista desde Muspy"""
        try:
            mbid = artist["id"]
            artist_name = artist["name"]

            # Consultar API de Muspy
            url = f"{self.muspy_base_url}/releases"
            params = {"mbid": mbid}
            auth = (self.muspy_username, self.muspy_password)

            response = requests.get(url, auth=auth, params=params, timeout=15)

            if response.status_code == 401:
                await message.edit_text("❌ Error de autenticación con Muspy. Verifica las credenciales.")
                return
            elif response.status_code != 200:
                await message.edit_text(f"❌ Error al consultar Muspy (código {response.status_code})")
                return

            releases = response.json()

            if not releases:
                await message.edit_text(
                    f"🎵 *{artist_name}*\n\n"
                    f"📭 No se encontraron lanzamientos registrados en Muspy.",
                    parse_mode='Markdown'
                )
                return

            # Filtrar solo lanzamientos futuros
            today = date.today().strftime("%Y-%m-%d")
            future_releases = [r for r in releases if r.get('date', '0000-00-00') >= today]

            if not future_releases:
                await message.edit_text(
                    f"🎵 *{artist_name}*\n\n"
                    f"📭 No hay próximos lanzamientos anunciados.\n"
                    f"📊 Total de lanzamientos en la base de datos: {len(releases)}",
                    parse_mode='Markdown'
                )
                return

            # Formatear y enviar resultados
            await self.format_and_send_releases(message, artist_name, future_releases)

        except requests.RequestException as e:
            logger.error(f"Error consultando Muspy: {e}")
            await message.edit_text("❌ Error de conexión con Muspy. Inténtalo más tarde.")
        except Exception as e:
            logger.error(f"Error obteniendo lanzamientos: {e}")
            await message.edit_text("❌ Error inesperado. Inténtalo más tarde.")

    async def get_releases_for_followed_artist(self, query, artist: Dict) -> None:
        """Obtiene lanzamientos para un artista de la lista de seguidos"""
        try:
            mbid = artist["mbid"]
            artist_name = artist["name"]

            # Consultar API de Muspy
            url = f"{self.muspy_base_url}/releases"
            params = {"mbid": mbid}
            auth = (self.muspy_username, self.muspy_password)

            response = requests.get(url, auth=auth, params=params, timeout=15)

            if response.status_code != 200:
                await query.edit_message_text(
                    f"❌ Error al consultar lanzamientos para {artist_name}"
                )
                return

            releases = response.json()

            if not releases:
                await query.edit_message_text(
                    f"🎵 *{artist_name}*\n\n"
                    f"📭 No se encontraron lanzamientos registrados.",
                    parse_mode='Markdown'
                )
                return

            # Filtrar lanzamientos futuros
            today = date.today().strftime("%Y-%m-%d")
            future_releases = [r for r in releases if r.get('date', '0000-00-00') >= today]

            if not future_releases:
                await query.edit_message_text(
                    f"🎵 *{artist_name}*\n\n"
                    f"📭 No hay próximos lanzamientos anunciados.\n"
                    f"📊 Total de lanzamientos en la base de datos: {len(releases)}",
                    parse_mode='Markdown'
                )
                return

            # Formatear y enviar resultados
            await self.format_and_send_releases(query.message, artist_name, future_releases)

        except Exception as e:
            logger.error(f"Error obteniendo lanzamientos para artista seguido: {e}")
            await query.edit_message_text(
                f"❌ Error al obtener lanzamientos para {artist.get('name', 'artista')}"
            )

    async def mostrar_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /mostrar - Muestra próximos lanzamientos de todos los artistas seguidos"""

        # Mensaje de "cargando..."
        loading_msg = await update.message.reply_text(
            "🔍 Buscando próximos lanzamientos de todos tus artistas seguidos...\n"
            "⏳ Esto puede tomar unos momentos...",
            parse_mode='Markdown'
        )

        try:
            # Obtener lista de artistas seguidos
            artists = await self.get_followed_artists()

            if not artists:
                await loading_msg.edit_text(
                    "📭 No se encontraron artistas seguidos en tu cuenta de Muspy.",
                    parse_mode='Markdown'
                )
                return

            await loading_msg.edit_text(
                f"🔍 Consultando lanzamientos para {len(artists)} artistas...\n"
                f"⏳ Por favor espera...",
                parse_mode='Markdown'
            )

            # Obtener todos los lanzamientos
            all_releases = await self.get_all_upcoming_releases(artists, loading_msg)

            if not all_releases:
                await loading_msg.edit_text(
                    f"📭 No se encontraron próximos lanzamientos para ninguno de tus {len(artists)} artistas seguidos.",
                    parse_mode='Markdown'
                )
                return

            # Formatear y enviar resultados
            await self.format_and_send_all_releases(loading_msg, all_releases)

        except Exception as e:
            logger.error(f"Error en comando mostrar: {e}")
            await loading_msg.edit_text(
                "❌ Error al obtener los lanzamientos. Inténtalo más tarde."
            )

    async def get_all_upcoming_releases(self, artists: List[Dict], status_msg) -> List[Dict]:
        """
        Obtiene todos los próximos lanzamientos para una lista de artistas

        Returns:
            Lista de releases con información del artista incluida
        """
        all_releases = []
        today = date.today().strftime("%Y-%m-%d")
        processed = 0

        for artist in artists:
            try:
                mbid = artist["mbid"]
                artist_name = artist["name"]

                # Actualizar estado cada 10 artistas
                processed += 1
                if processed % 10 == 0:
                    await status_msg.edit_text(
                        f"🔍 Procesando artistas... ({processed}/{len(artists)})\n"
                        f"⏳ Consultando: *{artist_name}*",
                        parse_mode='Markdown'
                    )

                # Consultar API de Muspy
                url = f"{self.muspy_base_url}/releases"
                params = {"mbid": mbid}
                auth = (self.muspy_username, self.muspy_password)

                response = requests.get(url, auth=auth, params=params, timeout=10)

                if response.status_code == 200:
                    releases = response.json()

                    # Filtrar solo lanzamientos futuros y agregar info del artista
                    future_releases = []
                    for release in releases:
                        if release.get('date', '0000-00-00') >= today:
                            release['artist_name'] = artist_name
                            release['artist_mbid'] = mbid
                            future_releases.append(release)

                    all_releases.extend(future_releases)

                # Pequeña pausa para no sobrecargar la API
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Error obteniendo releases para {artist.get('name', 'artista')}: {e}")
                continue

        # Ordenar por fecha
        all_releases.sort(key=lambda x: x.get('date', '9999-99-99'))

        return all_releases

    async def format_and_send_all_releases(self, message, releases: List[Dict]) -> None:
        """Formatea y envía todos los lanzamientos encontrados"""

        # Agrupar por artista para estadísticas
        artists_with_releases = set(r['artist_name'] for r in releases)

        header = f"🎵 *Próximos lanzamientos*\n"
        header += f"📊 {len(releases)} lanzamientos de {len(artists_with_releases)} artistas\n\n"

        current_text = header
        messages_to_send = []

        for i, release in enumerate(releases, 1):
            artist_name = release.get('artist_name', 'Artista desconocido')
            title = release.get('title', 'Sin título')
            date_str = release.get('date', 'Fecha desconocida')
            release_type = release.get('type', 'Release').title()

            # Formatear fecha
            try:
                if date_str != 'Fecha desconocida':
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    formatted_date = date_obj.strftime("%d/%m/%Y")
                else:
                    formatted_date = date_str
            except:
                formatted_date = date_str

            release_text = f"{i}. *{artist_name}* - *{title}*\n"
            release_text += f"   📅 {formatted_date} • 💿 {release_type}\n"

            # Añadir información adicional si está disponible
            if release.get('format'):
                release_text += f"   🎧 {release['format']}\n"

            if release.get('country'):
                release_text += f"   🌍 {release['country']}\n"

            release_text += "\n"

            # Verificar si el mensaje se vuelve muy largo
            if len(current_text + release_text) > 4000:
                messages_to_send.append(current_text.strip())
                current_text = release_text
            else:
                current_text += release_text

        # Añadir el último mensaje
        if current_text.strip():
            messages_to_send.append(current_text.strip())

        # Enviar mensajes
        if messages_to_send:
            # Editar el primer mensaje
            await message.edit_text(messages_to_send[0], parse_mode='Markdown')

            # Enviar mensajes adicionales si es necesario
            for msg in messages_to_send[1:]:
                await message.reply_text(msg, parse_mode='Markdown')
        else:
            await message.edit_text(
                "📭 No se encontraron próximos lanzamientos.",
                parse_mode='Markdown'
            )

    async def format_and_send_releases(self, message, artist_name: str, releases: List[Dict]) -> None:
        """Formatea y envía la lista de lanzamientos"""
        text = f"🎵 *{artist_name}*\n"
        text += f"🗓 *Próximos lanzamientos ({len(releases)}):*\n\n"

        # Ordenar por fecha
        releases.sort(key=lambda x: x.get('date', '9999-99-99'))

        for i, release in enumerate(releases, 1):
            title = release.get('title', 'Sin título')
            date_str = release.get('date', 'Fecha desconocida')
            release_type = release.get('type', 'Release').title()

            # Formatear fecha
            try:
                if date_str != 'Fecha desconocida':
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    formatted_date = date_obj.strftime("%d/%m/%Y")
                else:
                    formatted_date = date_str
            except:
                formatted_date = date_str

            text += f"{i}. *{title}*\n"
            text += f"   📅 {formatted_date} • 💿 {release_type}\n"

            # Añadir información adicional si está disponible
            if release.get('format'):
                text += f"   🎧 Formato: {release['format']}\n"

            if release.get('country'):
                text += f"   🌍 País: {release['country']}\n"

            text += "\n"

        # Verificar si el mensaje es muy largo
        if len(text) > 4000:
            # Dividir en múltiples mensajes
            messages = self.split_long_message(text)

            await message.edit_text(messages[0], parse_mode='Markdown')

            for msg in messages[1:]:
                await message.reply_text(msg, parse_mode='Markdown')
        else:
            await message.edit_text(text, parse_mode='Markdown')

    def split_long_message(self, text: str, max_length: int = 4000) -> List[str]:
        """Divide un mensaje largo en múltiples mensajes"""
        messages = []
        current_message = ""

        lines = text.split('\n')

        for line in lines:
            if len(current_message + line + '\n') > max_length:
                if current_message:
                    messages.append(current_message.strip())
                    current_message = line + '\n'
                else:
                    # Línea individual muy larga, cortarla
                    messages.append(line[:max_length])
                    current_message = line[max_length:] + '\n' if len(line) > max_length else ""
            else:
                current_message += line + '\n'

        if current_message.strip():
            messages.append(current_message.strip())

        return messages

    async def handle_unknown_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Maneja comandos desconocidos"""
        await update.message.reply_text(
            "❓ Comando no reconocido.\n"
            "Usa /help para ver los comandos disponibles."
        )

    def run(self):
        """Inicia el bot"""
        # Crear aplicación
        application = Application.builder().token(self.telegram_token).build()

        # Añadir handlers
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("buscar", self.buscar_command))
        application.add_handler(CommandHandler("artistas", self.artistas_command))
        application.add_handler(CommandHandler("mostrar", self.mostrar_command))

        # Handler para selección de artista
        application.add_handler(CallbackQueryHandler(
            self.artist_selection_callback,
            pattern="^select_artist_"
        ))

        # Handler para navegación de artistas seguidos
        application.add_handler(CallbackQueryHandler(
            self.artists_navigation_callback,
            pattern="^(artists_page_|select_from_followed|close_artists|current_page|select_followed_)"
        ))

        # Handler para mensajes desconocidos
        application.add_handler(MessageHandler(
            filters.COMMAND,
            self.handle_unknown_command
        ))

        logger.info("Bot iniciado. Presiona Ctrl+C para detener.")

        # Ejecutar bot
        application.run_polling(allowed_updates=Update.ALL_TYPES)

def main():
    """Función principal"""
    # Obtener credenciales de variables de entorno
    telegram_token = os.getenv('TELEGRAM_BOT_CONCIERTOS')
    muspy_username = os.getenv('MUSPY_USERNAME')
    muspy_api_key = os.getenv('MUSPY_API_KEY')
    muspy_pw = os.getenv('MUSPY_PW')

    # Verificar que todas las credenciales estén disponibles
    if not all([telegram_token, muspy_username, muspy_api_key]):
        print("❌ Error: Faltan credenciales requeridas.")
        print("Asegúrate de configurar las siguientes variables de entorno:")
        print("- TELEGRAM_BOT_CONCIERTOS")
        print("- MUSPY_USERNAME")
        print("- MUSPY_API_KEY")
        print("- MUSPY_PW")
        return

    # Crear y ejecutar bot
    bot = MuspyTelegramBot(telegram_token, muspy_username, muspy_api_key, muspy_pw)

    try:
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot detenido por el usuario.")
    except Exception as e:
        logger.error(f"Error fatal: {e}")

if __name__ == '__main__':
    main()
