#!/usr/bin/env python3
"""
Handlers específicos para funcionalidades de Muspy
"""

import logging
import asyncio
from datetime import datetime, date
from typing import Dict, List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

logger = logging.getLogger(__name__)

# Estados para ConversationHandler
MUSPY_EMAIL, MUSPY_PASSWORD, MUSPY_USERID = range(3)

class MuspyHandlers:
    """Clase que contiene todos los handlers de Muspy"""

    def __init__(self, database, muspy_service):
        self.db = database
        self.muspy_service = muspy_service

        # Almacenamiento temporal por usuario
        self.user_artists_cache = {}

    async def muspy_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando /muspy - Panel principal de configuración"""
        user_id = self._get_or_create_user_id(update)
        if not user_id:
            await update.message.reply_text(
                "❌ Primero debes registrarte con `/adduser <tu_nombre>`",
                parse_mode='Markdown'
            )
            return

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
            [InlineKeyboardButton("🔄 Nuevos lanzamientos", callback_data=f"muspy_releases_{user_id}")],
            [InlineKeyboardButton("👥 Artistas Muspy", callback_data=f"muspy_artists_{user_id}")],
            [InlineKeyboardButton("🔑 Login Muspy", callback_data=f"muspy_login_{user_id}")],
        ]

        if credentials:
            keyboard.extend([
                [InlineKeyboardButton("➕ Añadir a Muspy", callback_data=f"muspy_add_artists_{user_id}")],
                [InlineKeyboardButton("⬇️ Seguir artistas de Muspy", callback_data=f"muspy_import_artists_{user_id}")],
                [InlineKeyboardButton("🗑️ Desconectar cuenta", callback_data=f"muspy_disconnect_{user_id}")]
            ])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    async def muspy_callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Maneja los callbacks del panel de Muspy"""
        query = update.callback_query
        await query.answer()

        callback_data = query.data
        parts = callback_data.split("_")

        if len(parts) < 3:
            await query.edit_message_text("❌ Error en el callback.")
            return

        action = parts[1]
        user_id = int(parts[-1])

        # Verificar usuario
        if not self._verify_user(update, user_id):
            await query.edit_message_text("❌ Error de autenticación.")
            return

        try
