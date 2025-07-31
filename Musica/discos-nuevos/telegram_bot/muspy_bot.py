#!/usr/bin/env python3
"""
Bot de Telegram multiusuario para buscar lanzamientos musicales usando Muspy y MusicBrainz
"""
import os
import logging
import requests
import json
import sqlite3
import hashlib
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
    filters,
    ConversationHandler
)

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Estados para ConversationHandler
LOGIN_EMAIL, LOGIN_PASSWORD, LOGIN_USERID = range(3)

class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Inicializa la base de datos con las tablas necesarias"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Agregar columnas para credenciales de Muspy en users
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN muspy_email TEXT")
            cursor.execute("ALTER TABLE users ADD COLUMN muspy_password TEXT")
            cursor.execute("ALTER TABLE users ADD COLUMN muspy_userid TEXT")
        except sqlite3.OperationalError:
            pass  # Las columnas ya existen

        # Agregar columna muspy en user_followed_artists
        try:
            cursor.execute("ALTER TABLE user_followed_artists ADD COLUMN muspy BOOLEAN DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # La columna ya existe

        conn.commit()
        conn.close()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def get_or_create_user(self, username: str, chat_id: int) -> int:
        """Obtiene o crea un usuario y retorna su ID"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Buscar usuario existente
        cursor.execute("SELECT id FROM users WHERE chat_id = ?", (chat_id,))
        result = cursor.fetchone()

        if result:
            user_id = result[0]
            # Actualizar última actividad
            cursor.execute("UPDATE users SET last_activity = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))
        else:
            # Crear nuevo usuario
            cursor.execute("""
                INSERT INTO users (username, chat_id, notification_time, notification_enabled,
                                 country_filter, service_ticketmaster, service_spotify, service_setlistfm)
                VALUES (?, ?, '09:00', 1, 'ES', 1, 1, 1)
            """, (username, chat_id))
            user_id = cursor.lastrowid

        conn.commit()
        conn.close()
        return user_id

    def save_muspy_credentials(self, user_id: int, email: str, password: str, userid: str):
        """Guarda las credenciales de Muspy para un usuario"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE users
            SET muspy_email = ?, muspy_password = ?, muspy_userid = ?
            WHERE id = ?
        """, (email, password, userid, user_id))

        conn.commit()
        conn.close()

    def get_muspy_credentials(self, user_id: int) -> Optional[Tuple[str, str, str]]:
        """Obtiene las credenciales de Muspy de un usuario"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT muspy_email, muspy_password, muspy_userid FROM users WHERE id = ?", (user_id,))
        result = cursor.fetchone()

        conn.close()

        if result and all(result):
            return result
        return None

    def get_or_create_artist(self, name: str, mbid: str = None, **kwargs) -> int:
        """Obtiene o crea un artista y retorna su ID"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Buscar artista existente por mbid o nombre
        if mbid:
            cursor.execute("SELECT id FROM artists WHERE mbid = ?", (mbid,))
        else:
            cursor.execute("SELECT id FROM artists WHERE name = ?", (name,))

        result = cursor.fetchone()

        if result:
            artist_id = result[0]
        else:
            # Crear nuevo artista
            cursor.execute("""
                INSERT INTO artists (name, mbid, country, formed_year, ended_year,
                                   total_works, musicbrainz_url, artist_type, disambiguation)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                name,
                mbid,
                kwargs.get('country'),
                kwargs.get('formed_year'),
                kwargs.get('ended_year'),
                kwargs.get('total_works'),
                kwargs.get('musicbrainz_url'),
                kwargs.get('artist_type'),
                kwargs.get('disambiguation')
            ))
            artist_id = cursor.lastrowid

        conn.commit()
        conn.close()
        return artist_id

    def add_user_followed_artist(self, user_id: int, artist_id: int, muspy: bool = False):
        """Añade un artista seguido por el usuario"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Verificar si ya existe la relación
        cursor.execute("SELECT id FROM user_followed_artists WHERE user_id = ? AND artist_id = ?",
                      (user_id, artist_id))

        if cursor.fetchone():
            # Actualizar el estado de muspy si es necesario
            if muspy:
                cursor.execute("UPDATE user_followed_artists SET muspy = 1 WHERE user_id = ? AND artist_id = ?",
                              (user_id, artist_id))
        else:
            # Crear nueva relación
            cursor.execute("""
                INSERT INTO user_followed_artists (user_id, artist_id, muspy)
                VALUES (?, ?, ?)
            """, (user_id, artist_id, muspy))

        conn.commit()
        conn.close()

    def get_user_followed_artists(self, user_id: int, muspy_only: bool = False) -> List[Dict]:
        """Obtiene los artistas seguidos por un usuario"""
        conn = self.get_connection()
        cursor = conn.cursor()

        query = """
            SELECT a.id, a.name, a.mbid, a.country, a.disambiguation, ufa.muspy
            FROM artists a
            JOIN user_followed_artists ufa ON a.id = ufa.artist_id
            WHERE ufa.user_id = ?
        """

        if muspy_only:
            query += " AND ufa.muspy = 1"

        query += " ORDER BY a.name"

        cursor.execute(query, (user_id,))
        results = cursor.fetchall()

        conn.close()

        artists = []
        for row in results:
            artists.append({
                'id': row[0],
                'name': row[1],
                'mbid': row[2],
                'country': row[3],
                'disambiguation': row[4],
                'muspy': bool(row[5])
            })

        return artists

    def update_muspy_status_for_artists(self, user_id: int, artist_ids: List[int], muspy_status: bool):
        """Actualiza el estado de muspy para una lista de artistas"""
        conn = self.get_connection()
        cursor = conn.cursor()

        for artist_id in artist_ids:
            cursor.execute("""
                UPDATE user_followed_artists
                SET muspy = ?
                WHERE user_id = ? AND artist_id = ?
            """, (muspy_status, user_id, artist_id))

        conn.commit()
        conn.close()

class MuspyTelegramBot:
    def __init__(self, telegram_token: str, db_path: str):
        """
        Inicializa el bot de Telegram

        Args:
            telegram_token: Token del bot de Telegram
            db_path: Ruta a la base de datos SQLite
        """
        self.telegram_token = telegram_token
        self.db = DatabaseManager(db_path)
        self.muspy_base_url = "https://muspy.com/api/1"

        # Almacenamiento temporal de búsquedas por usuario
        self.user_searches: Dict[int, List[Dict]] = {}
        self.user_artists: Dict[int, List[Dict]] = {}

        # Headers para MusicBrainz
        self.mb_headers = {
            "User-Agent": "MuspyTelegramBot/1.0 (telegram-bot)"
        }

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /start"""
        user_id = self.db.get_or_create_user(
            update.effective_user.username or "Unknown",
            update.effective_chat.id
        )

        welcome_text = """
🎵 *Bot de Lanzamientos Musicales*

¡Hola! Este bot te ayuda a encontrar próximos lanzamientos de tus artistas favoritos.

*Comandos disponibles:*
• `/muspy` - Panel de configuración de Muspy
• `/buscar [artista]` - Busca lanzamientos de un artista
• `/help` - Muestra esta ayuda

*Ejemplo:*
`/buscar Radiohead`

Para usar todas las funcionalidades, configura tu cuenta de Muspy con `/muspy`.
        """
        await update.message.reply_text(welcome_text, parse_mode='Markdown')

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /help"""
        help_text = """
🔍 *Cómo usar el bot:*

1. **Configura Muspy:** Usa `/muspy` para acceder al panel de configuración
2. **Busca artistas:** Usa `/buscar [nombre del artista]` para buscar lanzamientos
3. **Gestiona tus artistas:** Desde el panel de Muspy puedes ver y sincronizar tus artistas

*Panel de Muspy (`/muspy`):*
• *Nuevos lanzamientos* - Ver próximos lanzamientos de tus artistas
• *Artistas Muspy* - Gestionar tu lista de artistas seguidos
• *Login Muspy* - Configurar tu cuenta de Muspy
• *Añadir a Muspy* - Sincronizar artistas locales con Muspy
• *Seguir artistas de Muspy* - Importar artistas desde Muspy

*Ejemplos:*
• `/buscar The Beatles`
• `/muspy` - Panel principal

💡 *Tip:* Una vez configurado Muspy, tendrás acceso a todas las funcionalidades avanzadas.
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def muspy_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /muspy - Panel principal de configuración"""
        user_id = self.db.get_or_create_user(
            update.effective_user.username or "Unknown",
            update.effective_chat.id
        )

        # Verificar si tiene credenciales configuradas
        credentials = self.db.get_muspy_credentials(user_id)

        text = "🎵 *Panel de Muspy*\n\n"

        if credentials:
            text += "✅ *Cuenta configurada*\n"
            text += f"📧 Email: `{credentials[0]}`\n"
            text += f"🆔 User ID: `{credentials[2]}`\n\n"
        else:
            text += "❌ *Cuenta no configurada*\n"
            text += "Configura tu cuenta de Muspy para acceder a todas las funcionalidades.\n\n"

        text += "*Selecciona una opción:*"

        keyboard = [
            [InlineKeyboardButton("🔄 Nuevos lanzamientos", callback_data="muspy_releases")],
            [InlineKeyboardButton("👥 Artistas Muspy", callback_data="muspy_artists")],
            [InlineKeyboardButton("🔑 Login Muspy", callback_data="muspy_login")],
        ]

        if credentials:
            keyboard.extend([
                [InlineKeyboardButton("➕ Añadir a Muspy", callback_data="muspy_add_artists")],
                [InlineKeyboardButton("⬇️ Seguir artistas de Muspy", callback_data="muspy_import_artists")]
            ])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    async def muspy_callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Maneja los callbacks del panel de Muspy"""
        query = update.callback_query
        await query.answer()

        user_id = self.db.get_or_create_user(
            update.effective_user.username or "Unknown",
            update.effective_chat.id
        )

        if query.data == "muspy_releases":
            await self.show_muspy_releases(query, user_id)
        elif query.data == "muspy_artists":
            await self.show_muspy_artists(query, user_id)
        elif query.data == "muspy_login":
            await self.start_muspy_login(query, context)
        elif query.data == "muspy_add_artists":
            await self.add_artists_to_muspy(query, user_id)
        elif query.data == "muspy_import_artists":
            await self.import_artists_from_muspy(query, user_id)

    async def show_muspy_releases(self, query, user_id: int) -> None:
        """Muestra los nuevos lanzamientos usando la API de Muspy"""
        credentials = self.db.get_muspy_credentials(user_id)

        if not credentials:
            await query.edit_message_text(
                "❌ No tienes configurada tu cuenta de Muspy.\n"
                "Usa el botón 'Login Muspy' para configurarla.",
                parse_mode='Markdown'
            )
            return

        await query.edit_message_text("🔍 Obteniendo nuevos lanzamientos...")

        try:
            releases = await self.get_all_user_releases_from_muspy(credentials)

            if not releases:
                await query.edit_message_text(
                    "📭 No se encontraron próximos lanzamientos en tu cuenta de Muspy.",
                    parse_mode='Markdown'
                )
                return

            # Filtrar solo lanzamientos futuros
            today = date.today().strftime("%Y-%m-%d")
            future_releases = [r for r in releases if r.get('date', '0000-00-00') >= today]

            if not future_releases:
                await query.edit_message_text(
                    f"📭 No hay próximos lanzamientos anunciados.\n"
                    f"📊 Total de lanzamientos en la base de datos: {len(releases)}",
                    parse_mode='Markdown'
                )
                return

            await self.format_and_send_all_releases(query.message, future_releases)

        except Exception as e:
            logger.error(f"Error obteniendo releases: {e}")
            await query.edit_message_text(
                "❌ Error al obtener los lanzamientos. Verifica tu configuración de Muspy."
            )

    async def show_muspy_artists(self, query, user_id: int) -> None:
        """Muestra los artistas seguidos desde la base de datos"""
        await query.edit_message_text("🔍 Cargando tu lista de artistas...")

        try:
            artists = self.db.get_user_followed_artists(user_id)

            if not artists:
                await query.edit_message_text(
                    "📭 No tienes artistas seguidos.\n"
                    "Importa artistas desde Muspy o añade nuevos con /buscar.",
                    parse_mode='Markdown'
                )
                return

            # Almacenar artistas para este usuario
            self.user_artists[user_id] = artists

            # Mostrar primera página
            await self.show_artists_page(query.message, user_id, page=0)

        except Exception as e:
            logger.error(f"Error obteniendo artistas: {e}")
            await query.edit_message_text(
                "❌ Error al obtener la lista de artistas."
            )

    async def start_muspy_login(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Inicia el proceso de login de Muspy"""
        query = update.callback_query
        await query.answer()

        await query.edit_message_text(
            "🔑 *Configuración de Muspy*\n\n"
            "Para conectar tu cuenta de Muspy necesito:\n"
            "1. Tu email de Muspy\n"
            "2. Tu contraseña\n"
            "3. Tu User ID de Muspy\n\n"
            "📧 *Paso 1:* Envía tu email de Muspy:",
            parse_mode='Markdown'
        )

        # Guardar el chat_id para el ConversationHandler
        context.user_data['muspy_login_chat_id'] = query.message.chat_id
        return LOGIN_EMAIL

    async def login_email_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Maneja el email en el proceso de login"""
        email = update.message.text.strip()

        # Validación básica de email
        if '@' not in email or '.' not in email:
            await update.message.reply_text(
                "❌ Email inválido. Por favor, envía un email válido:"
            )
            return LOGIN_EMAIL

        context.user_data['muspy_email'] = email

        await update.message.reply_text(
            f"✅ Email guardado: `{email}`\n\n"
            f"🔒 *Paso 2:* Envía tu contraseña de Muspy:",
            parse_mode='Markdown'
        )

        return LOGIN_PASSWORD

    async def login_password_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Maneja la contraseña en el proceso de login"""
        password = update.message.text.strip()

        if len(password) < 1:
            await update.message.reply_text(
                "❌ Contraseña muy corta. Por favor, envía tu contraseña:"
            )
            return LOGIN_PASSWORD

        context.user_data['muspy_password'] = password

        # Borrar el mensaje con la contraseña por seguridad
        try:
            await update.message.delete()
        except:
            pass

        await update.message.reply_text(
            "✅ Contraseña guardada.\n\n"
            "🆔 *Paso 3:* Envía tu User ID de Muspy:\n"
            "(Puedes encontrarlo en tu perfil de Muspy)",
            parse_mode='Markdown'
        )

        return LOGIN_USERID

    async def login_userid_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Maneja el User ID y completa el login"""
        userid = update.message.text.strip()

        if not userid:
            await update.message.reply_text(
                "❌ User ID inválido. Por favor, envía tu User ID de Muspy:"
            )
            return LOGIN_USERID

        # Obtener datos guardados
        email = context.user_data.get('muspy_email')
        password = context.user_data.get('muspy_password')

        # Verificar credenciales con la API de Muspy
        await update.message.reply_text("🔍 Verificando credenciales...")

        try:
            # Probar conexión con Muspy
            url = f"{self.muspy_base_url}/artists/{userid}"
            auth = (email, password)

            response = requests.get(url, auth=auth, timeout=10)

            if response.status_code == 401:
                await update.message.reply_text(
                    "❌ Credenciales incorrectas. Inténtalo de nuevo con `/muspy`."
                )
                return ConversationHandler.END
            elif response.status_code != 200:
                await update.message.reply_text(
                    f"❌ Error al conectar con Muspy (código {response.status_code}). "
                    f"Verifica tu User ID e inténtalo más tarde."
                )
                return ConversationHandler.END

            # Guardar credenciales en la base de datos
            user_id = self.db.get_or_create_user(
                update.effective_user.username or "Unknown",
                update.effective_chat.id
            )

            self.db.save_muspy_credentials(user_id, email, password, userid)

            await update.message.reply_text(
                "✅ *¡Configuración completada!*\n\n"
                f"📧 Email: `{email}`\n"
                f"🆔 User ID: `{userid}`\n\n"
                "Ya puedes usar todas las funcionalidades de Muspy.\n"
                "Usa `/muspy` para acceder al panel principal.",
                parse_mode='Markdown'
            )

            # Limpiar datos temporales
            context.user_data.clear()

        except Exception as e:
            logger.error(f"Error verificando credenciales: {e}")
            await update.message.reply_text(
                "❌ Error al verificar las credenciales. Inténtalo más tarde."
            )

        return ConversationHandler.END

    async def cancel_login(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancela el proceso de login"""
        await update.message.reply_text(
            "❌ Configuración de Muspy cancelada.\n"
            "Usa `/muspy` cuando quieras configurar tu cuenta."
        )
        context.user_data.clear()
        return ConversationHandler.END

    async def get_all_user_releases_from_muspy(self, credentials: Tuple[str, str, str]) -> List[Dict]:
        """Obtiene todos los lanzamientos del usuario desde Muspy"""
        email, password, userid = credentials

        try:
            url = f"{self.muspy_base_url}/releases/{userid}"
            auth = (email, password)

            response = requests.get(url, auth=auth, timeout=30)

            if response.status_code != 200:
                logger.error(f"Error al consultar lanzamientos: {response.status_code}")
                return []

            releases = response.json()
            releases.sort(key=lambda x: x.get('date', '9999-99-99'))

            return releases

        except Exception as e:
            logger.error(f"Error obteniendo releases desde Muspy: {e}")
            return []

    async def import_artists_from_muspy(self, query, user_id: int) -> None:
        """Importa artistas desde Muspy y los guarda en la base de datos"""
        credentials = self.db.get_muspy_credentials(user_id)

        if not credentials:
            await query.edit_message_text(
                "❌ No tienes configurada tu cuenta de Muspy."
            )
            return

        await query.edit_message_text("🔍 Obteniendo artistas desde Muspy...")

        try:
            email, password, userid = credentials

            # Obtener artistas desde Muspy con timeout más largo
            url = f"{self.muspy_base_url}/artists/{userid}"
            auth = (email, password)

            response = requests.get(url, auth=auth, timeout=30)

            if response.status_code != 200:
                await query.edit_message_text(
                    f"❌ Error al obtener artistas desde Muspy (código {response.status_code})"
                )
                return

            muspy_artists = response.json()

            if not muspy_artists:
                await query.edit_message_text(
                    "📭 No tienes artistas seguidos en Muspy."
                )
                return

            # Inicializar contadores
            imported_count = 0
            errors = []
            total_artists = len(muspy_artists)

            await query.edit_message_text(
                f"🔄 *Importando desde Muspy...*\n\n"
                f"📊 Total de artistas: {total_artists}\n"
                f"⏱️ Tiempo estimado: {total_artists // 60 + 1} min\n"
                f"🎵 Iniciando importación...",
                parse_mode='Markdown'
            )

            # Procesar en lotes más pequeños para evitar timeouts
            batch_size = 20
            last_update_time = datetime.now()

            for i, artist_data in enumerate(muspy_artists, 1):
                try:
                    # Procesar artista individual con timeout corto
                    artist_id = await self.process_single_artist_import(
                        artist_data, user_id, timeout_seconds=5
                    )

                    if artist_id:
                        imported_count += 1
                    else:
                        errors.append(f"❌ {artist_data.get('name', 'Artista desconocido')} - Error al procesar")

                except Exception as e:
                    logger.error(f"Error procesando artista {artist_data}: {e}")
                    artist_name = artist_data.get('name', 'Artista desconocido')
                    errors.append(f"❌ {artist_name} - Timeout o error de BD")
                    continue

                # Actualizar progreso cada 10 artistas o cada 30 segundos
                current_time = datetime.now()
                time_since_update = (current_time - last_update_time).seconds

                if (i % 10 == 0 or i == total_artists or time_since_update >= 30):
                    try:
                        progress_text = f"🔄 *Importando desde Muspy...*\n\n"
                        progress_text += f"📊 Progreso: {i}/{total_artists} artistas\n"
                        progress_text += f"✅ Importados: {imported_count}\n"
                        progress_text += f"❌ Errores: {len(errors)}\n"
                        progress_text += f"⏱️ Restante: ~{(total_artists - i) // 60 + 1} min\n\n"
                        progress_text += f"🎵 Procesando: *{artist_data.get('name', 'Artista sin nombre')[:50]}*"

                        await query.edit_message_text(progress_text, parse_mode='Markdown')
                        last_update_time = current_time

                    except Exception as update_error:
                        logger.error(f"Error actualizando progreso: {update_error}")
                        # Continuar aunque falle la actualización
                        pass

                # Pausa pequeña para evitar sobrecarga
                if i % batch_size == 0:
                    await asyncio.sleep(0.5)

            # Construir mensaje de resultado final
            result_text = f"✅ *Importación completada*\n\n"
            result_text += f"📊 Artistas importados: {imported_count}\n"
            result_text += f"📊 Total en Muspy: {total_artists}\n"
            result_text += f"📊 Tasa de éxito: {(imported_count/total_artists*100):.1f}%\n\n"

            if errors:
                result_text += f"*Errores encontrados ({len(errors)}):*\n"
                # Mostrar solo los primeros 5 errores para evitar mensajes muy largos
                for error in errors[:5]:
                    result_text += f"{error}\n"

                if len(errors) > 5:
                    result_text += f"... y {len(errors) - 5} errores más.\n"

                result_text += "\n"

            result_text += f"Usa '/muspy' → 'Artistas Muspy' para ver tu lista completa."

            await query.edit_message_text(result_text, parse_mode='Markdown')

        except requests.Timeout:
            await query.edit_message_text(
                "⏱️ *Timeout al obtener artistas*\n\n"
                "❌ Muspy tiene demasiados artistas para procesar de una vez.\n"
                "💡 Intenta de nuevo más tarde o contacta al desarrollador para implementar importación por lotes.",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error importando artistas: {e}")
            await query.edit_message_text(
                f"❌ Error al importar artistas desde Muspy.\n"
                f"🔍 Detalles: {str(e)[:100]}...",
                parse_mode='Markdown'
            )

    async def process_single_artist_import(self, artist_data: Dict, user_id: int, timeout_seconds: int = 5) -> Optional[int]:
        """
        Procesa la importación de un solo artista con timeout controlado

        Returns:
            ID del artista si se procesa correctamente, None si hay error
        """
        try:
            # Usar asyncio.wait_for para controlar timeout
            return await asyncio.wait_for(
                self._import_artist_to_db(artist_data, user_id),
                timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            logger.warning(f"Timeout procesando artista: {artist_data.get('name', 'Unknown')}")
            return None
        except Exception as e:
            logger.error(f"Error en process_single_artist_import: {e}")
            return None

    async def _import_artist_to_db(self, artist_data: Dict, user_id: int) -> int:
        """
        Función interna para importar un artista a la base de datos
        """
        # Ejecutar en thread para no bloquear el loop de asyncio
        loop = asyncio.get_event_loop()

        def sync_import():
            # Crear o obtener artista en la base de datos
            artist_id = self.db.get_or_create_artist(
                name=artist_data.get('name', 'Sin nombre'),
                mbid=artist_data.get('mbid'),
                disambiguation=artist_data.get('disambiguation', ''),
            )

            # Añadir a la lista de seguidos del usuario con marca de Muspy
            self.db.add_user_followed_artist(user_id, artist_id, muspy=True)

            return artist_id

        return await loop.run_in_executor(None, sync_import)

    async def add_artists_to_muspy(self, query, user_id: int) -> None:
        """Añade artistas locales a Muspy usando la API correcta"""
        credentials = self.db.get_muspy_credentials(user_id)

        if not credentials:
            await query.edit_message_text(
                "❌ No tienes configurada tu cuenta de Muspy."
            )
            return

        await query.edit_message_text("🔍 Sincronizando artistas con Muspy...")

        try:
            # Obtener artistas locales que no están en Muspy
            local_artists = self.db.get_user_followed_artists(user_id, muspy_only=False)
            non_muspy_artists = [a for a in local_artists if not a['muspy']]

            if not non_muspy_artists:
                await query.edit_message_text(
                    "✅ Todos tus artistas ya están sincronizados con Muspy."
                )
                return

            email, password, userid = credentials
            added_count = 0
            errors = []
            total_artists = len(non_muspy_artists)
            last_update_time = datetime.now()

            await query.edit_message_text(
                f"🔄 *Sincronizando con Muspy...*\n\n"
                f"📊 Total de artistas: {total_artists}\n"
                f"⏱️ Tiempo estimado: {total_artists // 30 + 1} min\n"
                f"🎵 Iniciando sincronización...",
                parse_mode='Markdown'
            )

            for i, artist in enumerate(non_muspy_artists, 1):
                # Actualizar progreso cada 10 artistas o cada 30 segundos
                current_time = datetime.now()
                time_since_update = (current_time - last_update_time).seconds

                if (i % 10 == 0 or i == total_artists or time_since_update >= 30):
                    try:
                        progress_text = f"🔄 *Sincronizando con Muspy...*\n\n"
                        progress_text += f"📊 Progreso: {i}/{total_artists} artistas\n"
                        progress_text += f"✅ Añadidos: {added_count}\n"
                        progress_text += f"❌ Errores: {len(errors)}\n"
                        progress_text += f"⏱️ Restante: ~{(total_artists - i) // 30 + 1} min\n\n"
                        progress_text += f"🎵 Procesando: *{artist['name'][:50]}*"

                        await query.edit_message_text(progress_text, parse_mode='Markdown')
                        last_update_time = current_time

                    except Exception as update_error:
                        logger.error(f"Error actualizando progreso: {update_error}")
                        # Continuar aunque falle la actualización
                        pass

                if not artist['mbid']:
                    errors.append(f"❌ {artist['name']} - Sin MBID")
                    continue  # Solo podemos añadir artistas con MBID

                try:
                    # Añadir artista a Muspy con timeout controlado
                    success = await self.add_single_artist_to_muspy(
                        artist, email, password, userid, timeout_seconds=8
                    )

                    if success:
                        # Marcar como sincronizado en la base de datos
                        self.db.update_muspy_status_for_artists(user_id, [artist['id']], True)
                        added_count += 1
                    else:
                        errors.append(f"❌ {artist['name']} - Timeout o error API")

                except Exception as e:
                    logger.error(f"Error añadiendo artista {artist['name']} a Muspy: {e}")
                    errors.append(f"❌ {artist['name']} - Error de conexión")
                    continue

                # Pausa pequeña para no sobrecargar la API de Muspy
                if i % 10 == 0:
                    await asyncio.sleep(1)

            # Construir mensaje de resultado final
            result_text = f"✅ *Sincronización completada*\n\n"
            result_text += f"📊 Artistas añadidos a Muspy: {added_count}\n"
            result_text += f"📊 Artistas procesados: {total_artists}\n"
            result_text += f"📊 Tasa de éxito: {(added_count/total_artists*100):.1f}%\n\n"

            if errors:
                result_text += f"*Errores encontrados ({len(errors)}):*\n"
                # Mostrar solo los primeros 5 errores para evitar mensajes muy largos
                for error in errors[:5]:
                    result_text += f"{error}\n"

                if len(errors) > 5:
                    result_text += f"... y {len(errors) - 5} errores más.\n"

                result_text += "\n"

            result_text += "💡 *Nota:* Solo se pueden añadir artistas con MBID válido."

            await query.edit_message_text(result_text, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error añadiendo artistas a Muspy: {e}")
            await query.edit_message_text(
                f"❌ Error al sincronizar artistas con Muspy.\n"
                f"🔍 Detalles: {str(e)[:100]}...",
                parse_mode='Markdown'
            )

    async def add_single_artist_to_muspy(self, artist: Dict, email: str, password: str, userid: str, timeout_seconds: int = 8) -> bool:
        """
        Añade un solo artista a Muspy con timeout controlado

        Returns:
            True si se añade correctamente, False si hay error
        """
        try:
            # Usar asyncio.wait_for para controlar timeout
            return await asyncio.wait_for(
                self._add_artist_to_muspy_api(artist, email, password, userid),
                timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            logger.warning(f"Timeout añadiendo artista a Muspy: {artist['name']}")
            return False
        except Exception as e:
            logger.error(f"Error en add_single_artist_to_muspy: {e}")
            return False

    async def _add_artist_to_muspy_api(self, artist: Dict, email: str, password: str, userid: str) -> bool:
        """
        Función interna para añadir un artista a Muspy via API
        """
        # Ejecutar en thread para no bloquear el loop de asyncio
        loop = asyncio.get_event_loop()

        def sync_add():
            url = f"{self.muspy_base_url}/artists/{userid}"
            auth = (email, password)
            data = {'mbid': artist['mbid']}

            response = requests.put(url, auth=auth, data=data, timeout=8)

            if response.status_code in [200, 201]:
                return True
            elif response.status_code == 400:
                # El artista ya está seguido, considerar como éxito
                return True
            else:
                logger.warning(f"Error API Muspy {response.status_code} para {artist['name']}")
                return False

        return await loop.run_in_executor(None, sync_add)

    # Mantener métodos existentes para búsqueda y navegación
    async def buscar_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /buscar [artista]"""
        user_id = self.db.get_or_create_user(
            update.effective_user.username or "Unknown",
            update.effective_chat.id
        )

        if not context.args:
            await update.message.reply_text(
                "❌ Por favor proporciona el nombre de un artista.\n"
                "Ejemplo: `/buscar Radiohead`",
                parse_mode='Markdown'
            )
            return

        artist_name = " ".join(context.args)

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
                await self.get_releases_for_artist(update, artist, searching_msg, user_id)
            else:
                # Múltiples artistas, mostrar opciones
                self.user_searches[user_id] = artists
                await self.show_artist_selection(update, artists, searching_msg)

        except Exception as e:
            logger.error(f"Error en búsqueda: {e}")
            await searching_msg.edit_text(
                "❌ Error al buscar el artista. Inténtalo de nuevo más tarde."
            )

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

        user_id = self.db.get_or_create_user(
            update.effective_user.username or "Unknown",
            update.effective_chat.id
        )

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
            await self.get_releases_for_artist(update, artist, query.message, user_id)

            # Limpiar búsqueda temporal
            del self.user_searches[user_id]

        except (IndexError, ValueError) as e:
            logger.error(f"Error en selección de artista: {e}")
            await query.edit_message_text("❌ Error en la selección. Inténtalo de nuevo.")

    async def get_releases_for_artist(self, update: Update, artist: Dict, message, user_id: int) -> None:
        """Obtiene y muestra los lanzamientos de un artista desde Muspy"""
        credentials = self.db.get_muspy_credentials(user_id)

        if not credentials:
            await message.edit_text(
                f"🎵 *{artist['name']}*\n\n"
                f"❌ Para ver lanzamientos necesitas configurar tu cuenta de Muspy.\n"
                f"Usa `/muspy` para configurarla.",
                parse_mode='Markdown'
            )
            return

        try:
            mbid = artist["id"]
            artist_name = artist["name"]
            email, password, userid = credentials

            # Consultar API de Muspy
            url = f"{self.muspy_base_url}/releases"
            params = {"mbid": mbid}
            auth = (email, password)

            response = requests.get(url, auth=auth, params=params, timeout=15)

            if response.status_code == 401:
                await message.edit_text("❌ Error de autenticación con Muspy. Verifica las credenciales.")
                return
            elif response.status_code != 200:
                await message.edit_text(f"❌ Error al consultar Muspy (código {response.status_code})")
                return

            releases = response.json()

            # Guardar/actualizar artista en la base de datos
            artist_id = self.db.get_or_create_artist(
                name=artist_name,
                mbid=mbid,
                country=artist.get('country'),
                disambiguation=artist.get('disambiguation'),
                artist_type=artist.get('type'),
                musicbrainz_url=f"https://musicbrainz.org/artist/{mbid}"
            )

            # Añadir a la lista de seguidos del usuario
            self.db.add_user_followed_artist(user_id, artist_id)

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

    async def show_artists_page(self, message, user_id: int, page: int = 0) -> None:
        """
        Muestra una página de artistas seguidos

        Args:
            message: Mensaje a editar
            user_id: ID del usuario
            page: Número de página (empezando desde 0)
        """
        if user_id not in self.user_artists:
            await message.edit_text("❌ Lista de artistas no encontrada. Usa /muspy de nuevo.")
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
        text = f"🎵 *Artistas seguidos*\n"
        text += f"📊 Total: {len(artists)} artistas\n"
        text += f"📄 Página {page + 1} de {total_pages}\n\n"

        for i, artist in enumerate(page_artists, start_idx + 1):
            name = artist.get('name', 'Sin nombre')
            disambiguation = artist.get('disambiguation', '')
            muspy_status = "🔗" if artist.get('muspy') else "📱"

            # Formato: número. nombre (disambiguation si existe) + estado
            artist_line = f"{i}. *{name}*"
            if disambiguation:
                artist_line += f" _{disambiguation}_"
            artist_line += f" {muspy_status}"

            text += artist_line + "\n"

        text += f"\n🔗 = En Muspy | 📱 = Solo local"

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

    async def artists_navigation_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Maneja la navegación entre páginas de artistas"""
        query = update.callback_query
        await query.answer()

        user_id = self.db.get_or_create_user(
            update.effective_user.username or "Unknown",
            update.effective_chat.id
        )

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
            await self.get_releases_for_followed_artist(query, artist, user_id)

            # Limpiar datos temporales
            if user_id in self.user_artists:
                del self.user_artists[user_id]

        except (IndexError, ValueError) as e:
            logger.error(f"Error en selección de artista seguido: {e}")
            await query.edit_message_text("❌ Error en la selección.")

    async def get_releases_for_followed_artist(self, query, artist: Dict, user_id: int) -> None:
        """Obtiene lanzamientos para un artista de la lista de seguidos"""
        credentials = self.db.get_muspy_credentials(user_id)

        if not credentials:
            await query.edit_message_text(
                f"❌ No tienes configurada tu cuenta de Muspy para ver lanzamientos."
            )
            return

        try:
            mbid = artist["mbid"]
            artist_name = artist["name"]
            email, password, userid = credentials

            # Consultar API de Muspy
            url = f"{self.muspy_base_url}/releases"
            params = {"mbid": mbid}
            auth = (email, password)

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

    async def format_and_send_all_releases(self, message, releases: List[Dict]) -> None:
        """Formatea y envía todos los lanzamientos encontrados"""

        # Debug: imprimir estructura de un release para entender el formato
        if releases:
            logger.info(f"Estructura del primer release: {json.dumps(releases[0], indent=2)}")

        # Agrupar por artista para estadísticas
        artists_with_releases = set()

        for release in releases:
            artist_name = self.extract_artist_name(release)
            if artist_name != 'Artista desconocido':
                artists_with_releases.add(artist_name)

        header = f"🎵 *Próximos lanzamientos*\n"
        header += f"📊 {len(releases)} lanzamientos de {len(artists_with_releases)} artistas\n\n"

        current_text = header
        messages_to_send = []

        for i, release in enumerate(releases, 1):
            # Extraer información del release
            artist_name = self.extract_artist_name(release)
            title = self.extract_title(release)
            date_str = release.get('date', 'Fecha desconocida')
            release_type = self.extract_release_type(release)

            # Formatear fecha
            try:
                if date_str != 'Fecha desconocida' and date_str:
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

    def extract_artist_name(self, release: Dict) -> str:
        """Extrae el nombre del artista desde diferentes posibles campos"""

        # Opción 1: artist_credit (común en MusicBrainz)
        if 'artist_credit' in release and isinstance(release['artist_credit'], list) and len(release['artist_credit']) > 0:
            artist = release['artist_credit'][0]
            if isinstance(artist, dict):
                return artist.get('name', artist.get('artist', {}).get('name', 'Artista desconocido'))
            elif isinstance(artist, str):
                return artist

        # Opción 2: artist_name directo
        if 'artist_name' in release and release['artist_name']:
            return release['artist_name']

        # Opción 3: artist como objeto
        if 'artist' in release:
            artist = release['artist']
            if isinstance(artist, dict):
                return artist.get('name', 'Artista desconocido')
            elif isinstance(artist, str):
                return artist

        # Opción 4: artists como lista
        if 'artists' in release and isinstance(release['artists'], list) and len(release['artists']) > 0:
            first_artist = release['artists'][0]
            if isinstance(first_artist, dict):
                return first_artist.get('name', 'Artista desconocido')
            elif isinstance(first_artist, str):
                return first_artist

        # Opción 5: campos alternativos comunes
        for field in ['performer', 'creator', 'artist_display_name']:
            if field in release and release[field]:
                return release[field]

        return 'Artista desconocido'

    def extract_title(self, release: Dict) -> str:
        """Extrae el título del lanzamiento desde diferentes posibles campos"""

        # Campos comunes para el título
        for field in ['title', 'name', 'album', 'release_name']:
            if field in release and release[field]:
                return release[field]

        return 'Sin título'

    def extract_release_type(self, release: Dict) -> str:
        """Extrae el tipo de lanzamiento"""

        # Campos comunes para el tipo
        for field in ['type', 'release_type', 'primary_type']:
            if field in release and release[field]:
                return release[field].title()

        # Si hay información de grupo de release
        if 'release_group' in release:
            rg = release['release_group']
            if isinstance(rg, dict):
                for field in ['type', 'primary_type']:
                    if field in rg and rg[field]:
                        return rg[field].title()

        return 'Release'

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

        # ConversationHandler para el login de Muspy
        login_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(
                self.start_muspy_login,
                pattern="^muspy_login$"
            )],
            states={
                LOGIN_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.login_email_handler)],
                LOGIN_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.login_password_handler)],
                LOGIN_USERID: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.login_userid_handler)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel_login)],
            per_chat=True,
            per_user=True
        )

        # Añadir handlers
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("muspy", self.muspy_command))
        application.add_handler(CommandHandler("buscar", self.buscar_command))

        # Handler para el panel de Muspy
        application.add_handler(CallbackQueryHandler(
            self.muspy_callback_handler,
            pattern="^muspy_(releases|artists|add_artists|import_artists)$"
        ))

        # ConversationHandler para login
        application.add_handler(login_conv_handler)

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
    telegram_token = os.getenv('TELEGRAM_BOT_RYMERS')
    db_path = os.getenv('DATABASE_PATH', 'artist_tracker.db')

    # Verificar que el token esté disponible
    if not telegram_token:
        print("❌ Error: Falta el token de Telegram.")
        print("Asegúrate de configurar la variable de entorno:")
        print("- TELEGRAM_BOT_RYMERS")
        return

    # Crear y ejecutar bot
    bot = MuspyTelegramBot(telegram_token, db_path)

    try:
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot detenido por el usuario.")
    except Exception as e:
        logger.error(f"Error fatal: {e}")

if __name__ == '__main__':
    main()
