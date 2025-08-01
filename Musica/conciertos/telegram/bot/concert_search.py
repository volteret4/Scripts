#!/usr/bin/env python3
"""
Módulo de búsqueda y gestión de conciertos
Contiene todas las funciones relacionadas con la búsqueda y formateo de conciertos
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)

async def search_concerts_for_artist(artist_name: str, user_services: Dict[str, any] = None,
                                   user_id: int = None, services: Dict = None, database = None) -> List[Dict]:
    """
    Busca conciertos para un artista usando los servicios habilitados
    VERSIÓN CORREGIDA: Guarda todos los conciertos y retorna todos los encontrados (sin filtrar por países)
    El filtrado por países se hace después en el comando que llama a esta función

    Args:
        artist_name: Nombre del artista
        user_services: Configuración de servicios del usuario
        user_id: ID del usuario
        services: Diccionario con referencias a los servicios
        database: Instancia de la base de datos
    """
    if user_services is None:
        user_services = {
            'ticketmaster': True,
            'spotify': True,
            'setlistfm': True,
            'country_filter': 'ES',
            'countries': {'ES'}
        }

    if services is None:
        from user_services import get_services
        services = get_services()

    all_concerts = []
    user_countries = user_services.get('countries', {'ES'})

    # Buscar en Ticketmaster si está habilitado - BÚSQUEDA GLOBAL Y GUARDADO
    if user_services.get('ticketmaster', True) and services.get('ticketmaster_service'):
        try:
            # Usar búsqueda global para obtener TODOS los conciertos
            concerts, status = services['ticketmaster_service'].search_concerts_global(artist_name)

            # GUARDAR TODOS los conciertos encontrados (sin filtrar)
            saved_count = 0
            for concert in concerts:
                if database:
                    # Asegurar que el concierto tenga el artist_name correcto
                    concert['artist_name'] = artist_name
                    concert_id = database.save_concert(concert)
                    if concert_id:
                        saved_count += 1
                        logger.debug(f"Guardado concierto: {concert.get('name', '')} en {concert.get('city', '')}, {concert.get('country', '')}")

            all_concerts.extend(concerts)
            logger.info(f"Ticketmaster global: {len(concerts)} conciertos encontrados, {saved_count} guardados para {artist_name}")

        except Exception as e:
            logger.error(f"Error buscando en Ticketmaster: {e}")

    # Buscar en Spotify si está habilitado
    if user_services.get('spotify', True) and services.get('spotify_service'):
        try:
            concerts, status = services['spotify_service'].search_artist_and_concerts(artist_name)

            saved_count = 0
            for concert in concerts:
                if database:
                    concert['artist_name'] = artist_name
                    concert_id = database.save_concert(concert)
                    if concert_id:
                        saved_count += 1

            all_concerts.extend(concerts)
            spotify_concerts = [c for c in concerts if c.get('source') == 'Spotify']
            logger.info(f"Spotify: {len(spotify_concerts)} conciertos encontrados, {saved_count} guardados para {artist_name}")

        except Exception as e:
            logger.error(f"Error buscando en Spotify: {e}")

    # Buscar en Setlist.fm si está habilitado - BÚSQUEDA POR PAÍS
    if user_services.get('setlistfm', True) and services.get('setlistfm_service'):
        try:
            setlist_concerts = []
            saved_count = 0

            # Setlist.fm mantiene búsqueda por país ya que es más específico
            for country_code in user_countries:
                concerts, status = services['setlistfm_service'].search_concerts(artist_name, country_code)

                for concert in concerts:
                    if database:
                        concert['artist_name'] = artist_name
                        concert_id = database.save_concert(concert)
                        if concert_id:
                            saved_count += 1

                setlist_concerts.extend(concerts)

            all_concerts.extend(setlist_concerts)
            logger.info(f"Setlist.fm: {len(setlist_concerts)} conciertos encontrados, {saved_count} guardados para {artist_name}")

        except Exception as e:
            logger.error(f"Error buscando en Setlist.fm: {e}")

    # RETORNAR TODOS los conciertos encontrados SIN FILTRAR
    # El filtrado por países se hará después en el comando
    logger.info(f"Total para {artist_name}: {len(all_concerts)} conciertos encontrados y guardados")
    return all_concerts



async def update_concerts_database(database, services: Dict = None):
    """
    Actualiza la base de datos con nuevos conciertos
    VERSIÓN MEJORADA: Guarda todos los conciertos globalmente con pausas

    Args:
        database: Instancia de la base de datos
        services: Diccionario con referencias a los servicios
    """
    if services is None:
        from user_services import get_services
        services = get_services()

    logger.info("Actualizando base de datos de conciertos...")

    # Obtener todos los artistas únicos de la base de datos
    conn = database.get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT DISTINCT name FROM artists")
        artists = [row[0] for row in cursor.fetchall()]

        total_new_concerts = 0
        total_all_concerts = 0
        processed_artists = 0

        logger.info(f"Iniciando actualización para {len(artists)} artistas")

        for artist_name in artists:
            processed_artists += 1

            if processed_artists % 10 == 0:
                logger.info(f"Progreso: {processed_artists}/{len(artists)} artistas procesados")

            logger.debug(f"Buscando conciertos globalmente para {artist_name}")

            # Buscar con configuración global (todos los servicios activos)
            global_services = {
                'ticketmaster': True,
                'spotify': True,
                'setlistfm': True,
                'countries': {'ES', 'US', 'FR', 'DE', 'IT', 'GB', 'CA', 'AU', 'JP', 'BR'}  # Países principales
            }

            concerts = await search_concerts_for_artist(artist_name, global_services, services=services, database=database)
            total_all_concerts += len(concerts)

            # Los conciertos ya se guardan dentro de search_concerts_for_artist
            # Solo necesitamos contar los nuevos
            for concert in concerts:
                # Verificar si es nuevo (esto es aproximado ya que save_concert devuelve ID o None)
                concert_id = database.save_concert(concert)
                if concert_id:
                    total_new_concerts += 1

            # Pausa de 1 segundo para no sobrecargar las APIs
            await asyncio.sleep(1.0)

        logger.info(f"Actualización completada: {total_new_concerts} nuevos conciertos de {total_all_concerts} encontrados")
        logger.info(f"Total artistas procesados: {processed_artists}")

    except Exception as e:
        logger.error(f"Error actualizando base de datos de conciertos: {e}")
    finally:
        conn.close()

def format_concerts_message(concerts: List[Dict], title: str = "🎵 Conciertos encontrados",
                          show_notified: bool = False, show_expand_buttons: bool = False,
                          user_id: int = None) -> Tuple[str, Optional[InlineKeyboardMarkup]]:
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

def format_single_artist_concerts_complete(concerts: List[Dict], artist_name: str, show_notified: bool = False) -> str:
    """
    Formatea todos los conciertos de un artista específico
    VERSIÓN MEJORADA: Filtra y muestra solo conciertos futuros (SIN filtrar por notificaciones)

    Args:
        concerts: Lista de conciertos del artista
        artist_name: Nombre del artista
        show_notified: Si mostrar información de notificación (no filtra, solo muestra)

    Returns:
        Mensaje formateado con todos los conciertos futuros del artista
    """
    if not concerts:
        return f"🎵 *{artist_name}*\n\n❌ No se encontraron conciertos."

    # Filtrar solo conciertos futuros (NO filtrar por notificaciones)
    today = datetime.now().date()
    future_concerts = []

    for concert in concerts:
        concert_date = concert.get('date', '')
        if concert_date and len(concert_date) >= 10:
            try:
                concert_date_obj = datetime.strptime(concert_date[:10], '%Y-%m-%d').date()
                if concert_date_obj >= today:
                    future_concerts.append(concert)
            except ValueError:
                # Si no se puede parsear la fecha, incluir el concierto por seguridad
                future_concerts.append(concert)
        else:
            # Si no hay fecha, incluir por seguridad
            future_concerts.append(concert)

    if not future_concerts:
        return f"🎵 *{artist_name}*\n\n📅 No hay conciertos futuros programados."

    # Escapar caracteres especiales del nombre del artista
    safe_artist = artist_name.replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")

    message_lines = [f"🎵 *{safe_artist} - Próximos conciertos*\n"]

    # Ordenar conciertos por fecha (más próximos primero)
    sorted_concerts = sorted(future_concerts, key=lambda x: x.get('date', '9999-12-31'))

    for i, concert in enumerate(sorted_concerts, 1):
        venue = concert.get('venue', 'Lugar desconocido')
        city = concert.get('city', '')
        country = concert.get('country', '')
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

                # Calcular días hasta el concierto
                days_until = (date_obj.date() - today).days
                if days_until == 0:
                    formatted_date += " (¡HOY!)"
                elif days_until == 1:
                    formatted_date += " (mañana)"
                elif days_until <= 7:
                    formatted_date += f" (en {days_until} días)"
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
        location_parts = []
        if safe_venue:
            location_parts.append(safe_venue)
        if safe_city:
            location_parts.append(safe_city)
        if country:
            location_parts.append(f"({country})")

        location = ", ".join(location_parts) if location_parts else "Ubicación desconocida"

        if url and url.startswith(('http://', 'https://')):
            # Escapar paréntesis en URL
            escaped_url = url.replace(")", "\\)")
            concert_line += f"   📍 [{location}]({escaped_url})"
        else:
            concert_line += f"   📍 {location}"

        # Información adicional
        if source:
            concert_line += f"\n   🔗 _{source}_"

        # OPCIONAL: Mostrar información de notificación (solo informativo, no filtra)
        if show_notified:
            if concert.get('notified'):
                concert_line += " ✅"  # Ya notificado
            # No mostrar nada si no está notificado (evitar spam visual)

        message_lines.append(concert_line)
        message_lines.append("")  # Línea en blanco entre conciertos

    # Estadísticas finales
    total_concerts = len(future_concerts)
    message_lines.append(f"📊 *Total: {total_concerts} conciertos futuros*")

    # OPCIONAL: Mostrar estadísticas de notificación solo si se solicita y hay datos
    if show_notified:
        notified_count = sum(1 for c in future_concerts if c.get('notified'))
        if notified_count > 0:
            message_lines.append(f"✅ Previamente notificados: {notified_count}")

    return "\n".join(message_lines)

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

def format_artist_concerts_detailed(concerts: List[Dict], artist_name: str, show_notified: bool = False) -> str:
    """Formatea conciertos de un artista de manera detallada - FUNCIÓN FALTANTE"""
    if not concerts:
        return f"📭 No hay conciertos para {artist_name}"

    # Filtrar solo conciertos futuros
    today = datetime.now().date()
    future_concerts = []

    for concert in concerts:
        concert_date = concert.get('date', '')
        if concert_date and len(concert_date) >= 10:
            try:
                concert_date_obj = datetime.strptime(concert_date[:10], '%Y-%m-%d').date()
                if concert_date_obj >= today:
                    future_concerts.append(concert)
            except ValueError:
                future_concerts.append(concert)
        else:
            future_concerts.append(concert)

    if not future_concerts:
        return f"📭 No hay conciertos futuros para {artist_name}"

    # Ordenar por fecha
    future_concerts.sort(key=lambda x: x.get('date', ''))

    message_lines = [f"🎵 *Conciertos de {artist_name}*\n"]

    for i, concert in enumerate(future_concerts, 1):
        venue = concert.get('venue', 'Venue TBA')
        city = concert.get('city', '')
        country = concert.get('country', '')
        date = concert.get('date', '')
        url = concert.get('url', '')
        source = concert.get('source', '')

        # Formatear fecha
        if date and len(date) >= 10:
            try:
                date_obj = datetime.strptime(date[:10], '%Y-%m-%d')
                formatted_date = date_obj.strftime('%d/%m/%Y')
            except ValueError:
                formatted_date = date
        else:
            formatted_date = 'Fecha TBA'

        # Crear línea del concierto
        line = f"{i}. *{venue}*"

        # Añadir ubicación
        location_parts = []
        if city:
            location_parts.append(city)
        if country:
            location_parts.append(country)

        if location_parts:
            line += f" - {', '.join(location_parts)}"

        line += f" ({formatted_date})"

        # Añadir enlace si está disponible
        if url:
            line += f" [🎫]({url})"

        # Mostrar fuente
        if source:
            line += f" _{source}_"

        # Mostrar si ya se notificó
        if show_notified and concert.get('notified'):
            line += " ✅"

        message_lines.append(line)

    message_lines.append(f"\n📊 Total: {len(future_concerts)} conciertos futuros")

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

    return chunks
