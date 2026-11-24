#!/usr/bin/env python3
"""
Script para generar HTML con embeds de Bandcamp organizados por género
Lee correos de un servidor IMAP y extrae enlaces de Bandcamp
Versión 2: Con botones de acción y API para gestionar correos
"""

import os
import re
import email
import json
from pathlib import Path
from html import escape
from collections import defaultdict
from urllib.parse import urlparse, parse_qs
import argparse
import urllib.request
import time
from html.parser import HTMLParser
import imaplib
import getpass
from email.header import decode_header
from email.utils import parsedate_to_datetime
from datetime import datetime



class IMAPConfig:
    """Configuración para conexión IMAP"""
    def __init__(self, server, port, email_address, password, use_ssl=True):
        self.server = server
        self.port = port
        self.email = email_address
        self.password = password
        self.use_ssl = use_ssl


class IMAPSessionManager:
    """Gestor de sesión IMAP persistente"""
    _instance = None
    _config_file = '.imap_session.json'

    def __init__(self):
        self.config = None
        self.mail = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def save_config(self, config):
        """Guarda la configuración (sin contraseña) para recordar servidor/email"""
        data = {
            'server': config.server,
            'port': config.port,
            'email': config.email
        }
        with open(self._config_file, 'w') as f:
            json.dump(data, f)

    def load_config(self):
        """Carga la configuración guardada"""
        if os.path.exists(self._config_file):
            with open(self._config_file, 'r') as f:
                return json.load(f)
        return None

    def connect(self, config):
        """Conecta y guarda la sesión"""
        self.config = config
        self.mail = connect_imap(config)
        self.save_config(config)
        return self.mail

    def get_connection(self):
        """Obtiene la conexión activa"""
        return self.mail

    def disconnect(self):
        """Cierra la conexión"""
        if self.mail:
            try:
                self.mail.close()
                self.mail.logout()
            except:
                pass
            self.mail = None


def connect_imap(config):
    """
    Conecta al servidor IMAP y hace login.

    Args:
        config: IMAPConfig con los datos de conexión

    Returns:
        Objeto IMAP4_SSL o IMAP4 conectado y autenticado
    """
    try:
        print(f"🔌 Conectando a {config.server}:{config.port}...")

        if config.use_ssl:
            mail = imaplib.IMAP4_SSL(config.server, config.port)
        else:
            mail = imaplib.IMAP4(config.server, config.port)

        print(f"🔑 Autenticando como {config.email}...")
        mail.login(config.email, config.password)

        print("✓ Conexión establecida\n")
        return mail

    except imaplib.IMAP4.error as e:
        print(f"❌ Error de autenticación: {e}")
        raise
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        raise


def decode_mime_header(header):
    """
    Decodifica headers MIME a texto legible.
    """
    if header is None:
        return ""

    decoded_parts = decode_header(header)
    decoded_str = ""

    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            if encoding:
                try:
                    decoded_str += part.decode(encoding)
                except:
                    decoded_str += part.decode('utf-8', errors='ignore')
            else:
                decoded_str += part.decode('utf-8', errors='ignore')
        else:
            decoded_str += str(part)

    return decoded_str


def get_imap_folders(mail):
    """
    Lista todas las carpetas disponibles en el servidor IMAP.

    Returns:
        Lista de nombres de carpetas
    """
    status, folders = mail.list()
    folder_names = []

    if status == 'OK':
        for folder in folders:
            # Decodificar el nombre de la carpeta
            folder_str = folder.decode()
            # Extraer el nombre (está entre comillas al final)
            match = re.search(r'"([^"]+)"$', folder_str)
            if match:
                folder_names.append(match.group(1))

    return folder_names


def get_email_body(msg):
    """
    Extrae el cuerpo del correo (texto plano o HTML).

    Args:
        msg: Objeto email.message.Message

    Returns:
        String con el contenido del correo
    """
    body = ""

    if msg.is_multipart():
        # Si el mensaje es multipart, buscar en todas las partes
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))

            # Buscar texto plano o HTML
            if "attachment" not in content_disposition:
                if content_type == "text/plain" or content_type == "text/html":
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or 'utf-8'
                            body += payload.decode(charset, errors='ignore')
                    except:
                        pass
    else:
        # Mensaje simple
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or 'utf-8'
                body = payload.decode(charset, errors='ignore')
        except:
            pass

    return body


def process_imap_folder(mail, folder_name, genre, mark_as_read=True, include_read=False, delete_after=False, config=None):
    """
    Procesa una carpeta IMAP buscando enlaces de Bandcamp.

    Args:
        mail: Conexión IMAP activa
        folder_name: Nombre de la carpeta a procesar
        genre: Género musical para clasificar
        mark_as_read: Si True, marca los correos como leídos después de procesarlos
        include_read: Si True, incluye correos ya leídos (por defecto solo no leídos)
        delete_after: Si True, elimina los correos después de procesarlos
        config: IMAPConfig para guardar en metadata

    Returns:
        Lista de embeds de Bandcamp encontrados
    """
    embeds = []

    print(f"\n{'='*80}")
    print(f"📂 Procesando carpeta: {folder_name}")
    print(f"🎵 Género: {genre}")
    print(f"{'='*80}\n")

    try:
        # Seleccionar la carpeta
        status, messages = mail.select(f'"{folder_name}"', readonly=False)

        if status != 'OK':
            print(f"❌ No se pudo acceder a la carpeta {folder_name}")
            return embeds

        num_messages = int(messages[0])
        print(f"📧 Correos en la carpeta: {num_messages}")

        if num_messages == 0:
            print("ℹ️  Carpeta vacía")
            return embeds

        # Buscar correos según el parámetro include_read
        if include_read:
            status, messages = mail.search(None, 'ALL')
            print(f"🔍 Buscando TODOS los correos (leídos y no leídos)...")
        else:
            status, messages = mail.search(None, 'UNSEEN')
            print(f"🔍 Buscando solo correos NO LEÍDOS...")

        if status != 'OK':
            print("❌ Error al buscar correos")
            return embeds

        email_ids = messages[0].split()
        print(f"🔍 Procesando {len(email_ids)} correos...\n")

        if len(email_ids) == 0:
            print("ℹ️  No hay correos que procesar con los criterios especificados")
            return embeds

        for i, email_id in enumerate(email_ids, 1):
            try:
                # Obtener el correo
                status, msg_data = mail.fetch(email_id, '(RFC822)')

                if status != 'OK':
                    continue

                # Parsear el correo
                email_body = msg_data[0][1]
                msg = email.message_from_bytes(email_body)

                # Obtener información del correo
                subject = decode_mime_header(msg.get('Subject', ''))
                sender = decode_mime_header(msg.get('From', ''))
                date = msg.get('Date', '')
                message_id = msg.get('Message-ID', '')

                # Parsear fecha para ordenamiento
                from email.utils import parsedate_to_datetime
                try:
                    date_obj = parsedate_to_datetime(date) if date else None
                except:
                    date_obj = None

                print(f"  [{i}/{len(email_ids)}] De: {sender[:50]}")
                print(f"       Asunto: {subject[:70]}")

                # Extraer el cuerpo del correo
                email_content = get_email_body(msg)

                if not email_content:
                    print("       ⚠️  Sin contenido")
                    continue

                # Buscar enlace de Bandcamp
                bandcamp_link = extract_bandcamp_link(email_content)

                if bandcamp_link:
                    print(f"       ✓ Enlace encontrado!")
                    print(f"       🔗 URL completa: {bandcamp_link}")

                    # Obtener el embed
                    embed_code = get_bandcamp_embed(bandcamp_link)

                    if embed_code:
                        email_id_str = email_id.decode() if isinstance(email_id, bytes) else str(email_id)

                        embeds.append({
                            'url': bandcamp_link,
                            'embed': embed_code,
                            'subject': subject,
                            'date': date,
                            'date_obj': date_obj,  # Para ordenar
                            'sender': sender,
                            'email_id': email_id_str,
                            'message_id': message_id,
                            'folder': folder_name,
                            'genre': genre
                        })
                        print(f"       ✓ Embed obtenido ({len(embeds)} total)")

                        # Marcar como leído si se encontró un enlace y la opción está activa
                        if mark_as_read:
                            mail.store(email_id, '+FLAGS', '\\Seen')
                            print(f"       📖 Marcado como leído")

                        # Eliminar si la opción está activa
                        if delete_after:
                            mail.store(email_id, '+FLAGS', '\\Deleted')
                            print(f"       🗑️  Marcado para eliminar")
                    else:
                        print(f"       ⚠️  No se pudo obtener el embed")
                else:
                    print("       • Sin enlaces de Bandcamp")

            except Exception as e:
                print(f"       ❌ Error procesando correo: {e}")
                continue

        # Expunge para eliminar permanentemente los correos marcados
        if delete_after:
            mail.expunge()
            print(f"\n🗑️  Correos eliminados permanentemente")

        print(f"\n{'='*80}")
        print(f"✓ Procesamiento completado: {len(embeds)} embeds encontrados")
        print(f"{'='*80}\n")

        # Ordenar por fecha (más reciente primero)
        embeds.sort(key=lambda x: x.get('date_obj') or datetime.min, reverse=True)

    except Exception as e:
        print(f"❌ Error al procesar carpeta {folder_name}: {e}")

    return embeds


def extract_bandcamp_link(email_content):
    """
    Extrae el enlace de Bandcamp del texto del correo.
    Busca diferentes patrones comunes en correos de Bandcamp.
    """
    # Lista de patrones para buscar, en orden de prioridad
    patterns = [
        # Patrón 1: "check it out here" con enlace en href
        r'check\s+it\s+out\s+here.*?href=["\']([^"\']+bandcamp\.com[^"\']*)["\']',

        # Patrón 2: href antes de "check it out here" (común en HTML)
        r'href=["\']([^"\']+bandcamp\.com[^"\']*)["\'].*?check\s+it\s+out\s+here',

        # Patrón 3: "check it out here" seguido de URL en texto plano
        r'check\s+it\s+out\s+here[^\n]*?(https?://[^\s<]+bandcamp\.com[^\s<]*)',

        # Patrón 4: Cualquier enlace de bandcamp en el correo (fallback)
        r'href=["\']([^"\']*bandcamp\.com/(?:album|track)/[^"\']+)["\']',

        # Patrón 5: URL directa de album/track en texto
        r'(https?://[^\s<]+bandcamp\.com/(?:album|track)/[^\s<]+)',
    ]

    for i, pattern in enumerate(patterns):
        match = re.search(pattern, email_content, re.IGNORECASE | re.DOTALL)
        if match:
            link = match.group(1)

            # Limpiar el enlace
            link = link.strip().rstrip('.,;!?>')

            # Decodificar entidades HTML comunes
            link = link.replace('&amp;', '&')
            link = link.replace('&lt;', '<')
            link = link.replace('&gt;', '>')

            # Limpiar parámetros de tracking pero mantener la URL base
            # Los parámetros UTM son solo tracking, la página funciona sin ellos
            if '?' in link:
                base_url, params = link.split('?', 1)
                link = base_url

            # Eliminar cualquier cosa después de espacios o caracteres extraños
            link = link.split()[0] if ' ' in link else link

            # Si el enlace es relativo, completarlo
            if link.startswith('/'):
                # Esto no debería pasar, pero por si acaso
                continue

            # Verificar que es un enlace válido de Bandcamp con album o track
            if 'bandcamp.com' in link and ('/album/' in link or '/track/' in link):
                return link

    return None


def fetch_bandcamp_embed_from_html(html_content):
    """
    Extrae el código embed del contenido HTML de una página de Bandcamp.
    Usa múltiples métodos para encontrar los IDs necesarios.
    """
    try:
        print(f"       📄 Analizando HTML ({len(html_content)} caracteres)")

        # MÉTODO 1: Buscar en el bloque TralbumData (más común)
        tralbum_data_match = re.search(
            r'var\s+TralbumData\s*=\s*(\{.+?\});',
            html_content,
            re.DOTALL
        )

        if tralbum_data_match:
            try:
                tralbum_json_str = tralbum_data_match.group(1)

                # Buscar album_id
                album_id_match = re.search(r'"?album_id"?\s*:\s*(\d+)', tralbum_json_str)
                if album_id_match:
                    album_id = album_id_match.group(1)
                    print(f"       ✓ album_id encontrado en TralbumData: {album_id}")
                    embed_url = f'https://bandcamp.com/EmbeddedPlayer/album={album_id}/size=large/bgcol=333333/linkcol=9a64ff/tracklist=false/artwork=small/transparent=true/'
                    return f'<iframe style="border: 0; width: 400px; height: 120px;" src="{embed_url}" seamless></iframe>'

                # Buscar track_id si es un track
                item_type_match = re.search(r'"?item_type"?\s*:\s*"?(track|album)"?', tralbum_json_str)
                if item_type_match and item_type_match.group(1) == 'track':
                    track_id_match = re.search(r'"?id"?\s*:\s*(\d+)', tralbum_json_str)
                    if track_id_match:
                        track_id = track_id_match.group(1)
                        print(f"       ✓ track_id encontrado en TralbumData: {track_id}")
                        embed_url = f'https://bandcamp.com/EmbeddedPlayer/track={track_id}/size=large/bgcol=333333/linkcol=9a64ff/tracklist=false/artwork=small/transparent=true/'
                        return f'<iframe style="border: 0; width: 400px; height: 120px;" src="{embed_url}" seamless></iframe>'
            except Exception as e:
                print(f"       ⚠️  Error en TralbumData: {e}")

        # MÉTODO 2: Buscar en EmbedData
        embed_data_match = re.search(
            r'var\s+EmbedData\s*=\s*(\{.+?\});',
            html_content,
            re.DOTALL
        )

        if embed_data_match:
            try:
                embed_json_str = embed_data_match.group(1)

                album_id_match = re.search(r'"?album_id"?\s*:\s*(\d+)', embed_json_str)
                if album_id_match:
                    album_id = album_id_match.group(1)
                    print(f"       ✓ album_id encontrado en EmbedData: {album_id}")
                    embed_url = f'https://bandcamp.com/EmbeddedPlayer/album={album_id}/size=large/bgcol=333333/linkcol=9a64ff/tracklist=false/artwork=small/transparent=true/'
                    return f'<iframe style="border: 0; width: 400px; height: 120px;" src="{embed_url}" seamless></iframe>'

                track_id_match = re.search(r'"?track_id"?\s*:\s*(\d+)', embed_json_str)
                if track_id_match:
                    track_id = track_id_match.group(1)
                    print(f"       ✓ track_id encontrado en EmbedData: {track_id}")
                    embed_url = f'https://bandcamp.com/EmbeddedPlayer/track={track_id}/size=large/bgcol=333333/linkcol=9a64ff/tracklist=false/artwork=small/transparent=true/'
                    return f'<iframe style="border: 0; width: 400px; height: 120px;" src="{embed_url}" seamless></iframe>'
            except Exception as e:
                print(f"       ⚠️  Error en EmbedData: {e}")

        # MÉTODO 3: Buscar directamente en el HTML
        # Buscar album_id en cualquier parte
        album_id_patterns = [
            r'data-band-id="(\d+)".*?data-item-id="(\d+)".*?data-item-type="album"',
            r'"?album_id"?\s*:\s*(\d+)',
            r'album[=/](\d{8,12})',
        ]

        for pattern in album_id_patterns:
            match = re.search(pattern, html_content, re.DOTALL)
            if match:
                album_id = match.group(2) if len(match.groups()) > 1 else match.group(1)
                print(f"       ✓ album_id encontrado (búsqueda general): {album_id}")
                embed_url = f'https://bandcamp.com/EmbeddedPlayer/album={album_id}/size=large/bgcol=333333/linkcol=9a64ff/tracklist=false/artwork=small/transparent=true/'
                return f'<iframe style="border: 0; width: 400px; height: 120px;" src="{embed_url}" seamless></iframe>'

        # Buscar track_id
        track_id_patterns = [
            r'data-band-id="(\d+)".*?data-item-id="(\d+)".*?data-item-type="track"',
            r'"?track_id"?\s*:\s*(\d+)',
            r'track[=/](\d{8,12})',
        ]

        for pattern in track_id_patterns:
            match = re.search(pattern, html_content, re.DOTALL)
            if match:
                track_id = match.group(2) if len(match.groups()) > 1 else match.group(1)
                print(f"       ✓ track_id encontrado (búsqueda general): {track_id}")
                embed_url = f'https://bandcamp.com/EmbeddedPlayer/track={track_id}/size=large/bgcol=333333/linkcol=9a64ff/tracklist=false/artwork=small/transparent=true/'
                return f'<iframe style="border: 0; width: 400px; height: 120px;" src="{embed_url}" seamless></iframe>'

        # MÉTODO 4: Buscar el iframe embed directo
        iframe_match = re.search(
            r'<iframe[^>]*src=["\']([^"\']*EmbeddedPlayer[^"\']*)["\']',
            html_content,
            re.IGNORECASE
        )
        if iframe_match:
            embed_url = iframe_match.group(1)
            if embed_url.startswith('//'):
                embed_url = 'https:' + embed_url
            print(f"       ✓ iframe embed encontrado directamente")
            return f'<iframe style="border: 0; width: 400px; height: 120px;" src="{embed_url}" seamless></iframe>'

        print(f"       ❌ No se encontró embed en ningún método")

        # Debug extra: buscar si hay contenido relevante
        if 'album' in html_content.lower() or 'track' in html_content.lower():
            print(f"       ℹ️  La página contiene referencias a album/track")

        # Verificar si es una página válida de Bandcamp
        if 'bandcamp' not in html_content.lower():
            print(f"       ⚠️  La página no parece ser de Bandcamp")

        # Buscar mensajes de error comunes
        if 'not found' in html_content.lower() or '404' in html_content:
            print(f"       ⚠️  La página muestra error 404 - el álbum no existe")

        if 'private' in html_content.lower() or 'unavailable' in html_content.lower():
            print(f"       ⚠️  El álbum podría ser privado o no disponible")

        return None

    except Exception as e:
        print(f"       ❌ Error extrayendo embed: {e}")
        return None


def get_bandcamp_embed(url, retry_count=3):
    """
    Obtiene el código embed de Bandcamp para una URL dada.
    Intenta varias veces en caso de error.
    """
    for attempt in range(retry_count):
        try:
            if attempt > 0:
                print(f"       🔄 Reintento {attempt + 1}/{retry_count}...")
                time.sleep(2)

            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
            )

            with urllib.request.urlopen(req, timeout=15) as response:
                html = response.read().decode('utf-8', errors='ignore')
                print(f"       ✓ Página descargada (código {response.status})")

            embed = fetch_bandcamp_embed_from_html(html)

            if embed:
                return embed
            else:
                print(f"       ⚠️  No se encontró embed en intento {attempt + 1}")

        except urllib.error.HTTPError as e:
            print(f"       ❌ Error HTTP {e.code}: {e.reason}")
            if e.code == 404:
                print(f"       ℹ️  La página no existe (404)")
                return None
            elif e.code >= 500:
                print(f"       ℹ️  Error del servidor, reintentando...")
        except urllib.error.URLError as e:
            print(f"       ❌ Error de conexión: {e.reason}")
        except Exception as e:
            print(f"       ❌ Error inesperado: {type(e).__name__}: {e}")

    print(f"       ❌ Falló después de {retry_count} intentos")
    return None


def generate_genre_html_with_api(genre, embeds, output_dir, config, items_per_page=10):
    """
    Genera un archivo HTML para un género específico con botones de acción.
    Incluye API para marcar como leído y eliminar correos.
    Los embeds se ordenan por fecha del correo (más reciente primero).
    """
    # Ordenar embeds por fecha (más reciente primero)
    # Los que no tienen date_obj van al final
    embeds_sorted = sorted(
        embeds,
        key=lambda x: x.get('date_obj') or datetime.min,
        reverse=True  # Más reciente primero
    )

    # Sanitizar el nombre del archivo
    safe_genre = re.sub(r'[^\w\s-]', '', genre).strip().replace(' ', '_')
    filename = f"{safe_genre}.html"

    total_items = len(embeds_sorted)
    total_pages = (total_items + items_per_page - 1) // items_per_page

    # Guardar metadata de conexión para el API
    metadata = {
        'server': config.server,
        'port': config.port,
        'email': config.email
    }

    metadata_json = json.dumps(metadata)

    # Generar los embeds HTML con botones
    embeds_html = ""
    for i, embed_data in enumerate(embeds_sorted):
        page_num = (i // items_per_page) + 1
        page_class = f"page-{page_num}" if total_pages > 1 else ""

        # Crear identificador único para este embed
        embed_id = f"embed_{i}"
        email_id = embed_data.get('email_id', '')
        folder = embed_data.get('folder', '')

        embeds_html += f"""
        <div class="embed-item {page_class}" data-page="{page_num}" id="{embed_id}">
            {embed_data['embed']}
            <div class="embed-info">
                <strong>{escape(embed_data.get('subject', 'Sin título'))}</strong><br>
                <small>📅 {escape(embed_data.get('date', 'Fecha desconocida'))}</small>
            </div>
            <div class="embed-actions">
                <button class="action-btn mark-read-btn" onclick="markAsRead('{embed_id}', '{email_id}', '{folder}')">
                    📖 Marcar como leído
                </button>
                <button class="action-btn delete-btn" onclick="deleteEmail('{embed_id}', '{email_id}', '{folder}')">
                    🗑️ Eliminar
                </button>
            </div>
        </div>
        """

    # Generar controles de paginación
    pagination_html = ""
    if total_pages > 1:
        pagination_html = '<div class="pagination">'
        for page in range(1, total_pages + 1):
            active = "active" if page == 1 else ""
            pagination_html += f'<button class="page-btn {active}" data-page="{page}">Página {page}</button>'
        pagination_html += '</div>'

    # HTML completo con API y estilos
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎵 {escape(genre)} - Bandcamp Collection</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        header {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
        }}

        h1 {{
            color: #333;
            font-size: 2.5em;
            margin-bottom: 10px;
        }}

        .subtitle {{
            color: #666;
            font-size: 1.1em;
        }}

        .back-link {{
            display: inline-block;
            margin-top: 15px;
            color: #667eea;
            text-decoration: none;
            font-weight: 500;
            transition: color 0.3s;
        }}

        .back-link:hover {{
            color: #764ba2;
        }}

        .embeds-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
            gap: 25px;
            margin-bottom: 30px;
        }}

        .embed-item {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 5px 20px rgba(0, 0, 0, 0.1);
            transition: transform 0.3s, box-shadow 0.3s, opacity 0.3s;
        }}

        .embed-item:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.15);
        }}

        .embed-item.hidden {{
            display: none;
        }}

        .embed-item.removed {{
            opacity: 0.3;
            pointer-events: none;
        }}

        .embed-info {{
            margin-top: 15px;
            color: #555;
            font-size: 0.9em;
        }}

        .embed-actions {{
            margin-top: 15px;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}

        .action-btn {{
            flex: 1;
            min-width: 150px;
            padding: 10px 15px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 500;
            font-size: 0.9em;
            transition: all 0.3s;
        }}

        .mark-read-btn {{
            background: #4CAF50;
            color: white;
        }}

        .mark-read-btn:hover {{
            background: #45a049;
            transform: translateY(-2px);
        }}

        .mark-read-btn:disabled {{
            background: #ccc;
            cursor: not-allowed;
            transform: none;
        }}

        .delete-btn {{
            background: #f44336;
            color: white;
        }}

        .delete-btn:hover {{
            background: #da190b;
            transform: translateY(-2px);
        }}

        .delete-btn:disabled {{
            background: #ccc;
            cursor: not-allowed;
            transform: none;
        }}

        .pagination {{
            display: flex;
            justify-content: center;
            gap: 10px;
            flex-wrap: wrap;
            margin-top: 30px;
        }}

        .page-btn {{
            background: rgba(255, 255, 255, 0.95);
            border: 2px solid #667eea;
            color: #667eea;
            padding: 10px 20px;
            border-radius: 25px;
            cursor: pointer;
            font-weight: 500;
            transition: all 0.3s;
        }}

        .page-btn:hover {{
            background: #667eea;
            color: white;
        }}

        .page-btn.active {{
            background: #667eea;
            color: white;
        }}

        .notification {{
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 25px;
            border-radius: 10px;
            background: white;
            box-shadow: 0 5px 20px rgba(0, 0, 0, 0.2);
            z-index: 1000;
            display: none;
            animation: slideIn 0.3s ease;
        }}

        .notification.show {{
            display: block;
        }}

        .notification.success {{
            border-left: 4px solid #4CAF50;
        }}

        .notification.error {{
            border-left: 4px solid #f44336;
        }}

        @keyframes slideIn {{
            from {{
                transform: translateX(400px);
                opacity: 0;
            }}
            to {{
                transform: translateX(0);
                opacity: 1;
            }}
        }}

        @media (max-width: 768px) {{
            .embeds-grid {{
                grid-template-columns: 1fr;
            }}

            h1 {{
                font-size: 2em;
            }}

            .action-btn {{
                min-width: 100%;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎵 {escape(genre)}</h1>
            <p class="subtitle">📀 {total_items} disco{"s" if total_items != 1 else ""}</p>
            <a href="index.html" class="back-link">← Volver al índice</a>
        </header>

        <div class="embeds-grid">
            {embeds_html}
        </div>

        {pagination_html}
    </div>

    <div id="notification" class="notification"></div>

    <script>
        // Configuración de conexión IMAP
        const imapConfig = {metadata_json};

        // Paginación
        const pageButtons = document.querySelectorAll('.page-btn');
        const embedItems = document.querySelectorAll('.embed-item');

        pageButtons.forEach(button => {{
            button.addEventListener('click', () => {{
                const page = button.dataset.page;

                pageButtons.forEach(btn => btn.classList.remove('active'));
                button.classList.add('active');

                embedItems.forEach(item => {{
                    if (item.dataset.page === page) {{
                        item.classList.remove('hidden');
                    }} else {{
                        item.classList.add('hidden');
                    }}
                }});

                window.scrollTo({{ top: 0, behavior: 'smooth' }});
            }});
        }});

        // Mostrar solo la primera página al cargar
        if (pageButtons.length > 0) {{
            embedItems.forEach(item => {{
                if (item.dataset.page !== '1') {{
                    item.classList.add('hidden');
                }}
            }});
        }}

        // Funciones de notificación
        function showNotification(message, type = 'success') {{
            const notification = document.getElementById('notification');
            notification.textContent = message;
            notification.className = `notification show ${{type}}`;

            setTimeout(() => {{
                notification.classList.remove('show');
            }}, 3000);
        }}

        // Función para marcar como leído
        async function markAsRead(embedId, emailId, folder) {{
            const embedElement = document.getElementById(embedId);
            const button = embedElement.querySelector('.mark-read-btn');

            button.disabled = true;
            button.textContent = '⏳ Procesando...';

            try {{
                // Aquí llamarías a tu API backend
                // Por ahora simulamos la operación
                const response = await fetch('/api/mark-read', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                    }},
                    body: JSON.stringify({{
                        server: imapConfig.server,
                        port: imapConfig.port,
                        email: imapConfig.email,
                        emailId: emailId,
                        folder: folder
                    }})
                }});

                if (response.ok) {{
                    button.textContent = '✓ Leído';
                    button.style.background = '#95d5b2';
                    showNotification('Correo marcado como leído', 'success');
                }} else {{
                    throw new Error('Error al marcar como leído');
                }}
            }} catch (error) {{
                console.error('Error:', error);
                button.disabled = false;
                button.textContent = '📖 Marcar como leído';
                showNotification('Error: ' + error.message + ' (API no disponible)', 'error');
            }}
        }}

        // Función para eliminar
        async function deleteEmail(embedId, emailId, folder) {{
            if (!confirm('¿Estás seguro de que quieres eliminar este correo? Esta acción no se puede deshacer.')) {{
                return;
            }}

            const embedElement = document.getElementById(embedId);
            const button = embedElement.querySelector('.delete-btn');

            button.disabled = true;
            button.textContent = '⏳ Eliminando...';

            try {{
                // Aquí llamarías a tu API backend
                const response = await fetch('/api/delete-email', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                    }},
                    body: JSON.stringify({{
                        server: imapConfig.server,
                        port: imapConfig.port,
                        email: imapConfig.email,
                        emailId: emailId,
                        folder: folder
                    }})
                }});

                if (response.ok) {{
                    embedElement.classList.add('removed');
                    button.textContent = '✓ Eliminado';
                    showNotification('Correo eliminado', 'success');

                    setTimeout(() => {{
                        embedElement.style.display = 'none';
                    }}, 1000);
                }} else {{
                    throw new Error('Error al eliminar');
                }}
            }} catch (error) {{
                console.error('Error:', error);
                button.disabled = false;
                button.textContent = '🗑️ Eliminar';
                showNotification('Error: ' + error.message + ' (API no disponible)', 'error');
            }}
        }}

        // Aviso sobre el API
        console.log('%c⚠️ NOTA: Los botones de acción requieren un servidor API backend', 'color: orange; font-size: 14px; font-weight: bold');
        console.log('Para implementar la funcionalidad completa, necesitas crear un servidor que maneje las peticiones /api/mark-read y /api/delete-email');
    </script>
</body>
</html>
"""

    filepath = os.path.join(output_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"      ✓ {filename} generado con botones de acción")
    return filename


def interactive_setup():
    """
    Modo interactivo para configurar la conexión IMAP.
    """
    print("\n" + "="*80)
    print("🔧 CONFIGURACIÓN IMAP")
    print("="*80 + "\n")

    # Intentar cargar configuración previa
    session = IMAPSessionManager.get_instance()
    saved_config = session.load_config()

    if saved_config:
        print("📋 Configuración guardada encontrada:")
        print(f"   Servidor: {saved_config['server']}")
        print(f"   Email: {saved_config['email']}")
        use_saved = input("\n¿Usar esta configuración? (s/n): ").strip().lower()

        if use_saved == 's':
            server = saved_config['server']
            port = saved_config['port']
            email_address = saved_config['email']
        else:
            server = input("Servidor IMAP (ej: imap.gmail.com): ").strip()
            port = input("Puerto (default: 993): ").strip() or "993"
            email_address = input("Email: ").strip()
    else:
        print("Proveedores comunes:")
        print("  Gmail:         imap.gmail.com:993")
        print("  Outlook/Live:  imap-mail.outlook.com:993")
        print("  Yahoo:         imap.mail.yahoo.com:993")
        print("  iCloud:        imap.mail.me.com:993")
        print()

        server = input("Servidor IMAP (ej: imap.gmail.com): ").strip()
        port = input("Puerto (default: 993): ").strip() or "993"
        email_address = input("Email: ").strip()

    password = getpass.getpass("Contraseña: ")

    return IMAPConfig(server, int(port), email_address, password)


def main():
    parser = argparse.ArgumentParser(
        description='Genera HTML con embeds de Bandcamp desde correos IMAP - Versión 2'
    )

    # Opciones de conexión
    parser.add_argument('--interactive', action='store_true',
                       help='Modo interactivo para configurar la conexión')
    parser.add_argument('--server', help='Servidor IMAP (ej: imap.gmail.com)')
    parser.add_argument('--port', type=int, default=993, help='Puerto IMAP (default: 993)')
    parser.add_argument('--email', help='Dirección de email')
    parser.add_argument('--password', help='Contraseña (no recomendado, usa --interactive)')

    # Opciones de operación
    parser.add_argument('--list-folders', action='store_true',
                       help='Listar todas las carpetas disponibles y salir')
    parser.add_argument('--folders', nargs='+',
                       help='Carpetas en formato "ruta:género" (ej: "INBOX/Rock:Rock")')
    parser.add_argument('--no-mark-read', action='store_true',
                       help='NO marcar los correos como leídos después de procesarlos')
    parser.add_argument('--include-read', action='store_true',
                       help='Incluir correos ya leídos (por defecto solo procesa no leídos)')
    parser.add_argument('--delete', action='store_true',
                       help='Eliminar correos después de procesarlos (¡CUIDADO!)')

    # Opciones de salida
    parser.add_argument('--output-dir', default='bandcamp_html',
                       help='Directorio de salida para los archivos HTML (default: bandcamp_html)')
    parser.add_argument('--items-per-page', type=int, default=10,
                       help='Número de discos por página en cada género (default: 10)')

    args = parser.parse_args()

    # Configurar conexión IMAP
    if args.interactive:
        config = interactive_setup()
    elif args.server and args.email:
        password = args.password
        if not password:
            password = getpass.getpass(f"Contraseña para {args.email}: ")
        config = IMAPConfig(args.server, args.port, args.email, password)
    else:
        print("❌ Debes usar --interactive o proporcionar --server y --email")
        print("Usa --help para ver ejemplos de uso")
        return

    # Conectar al servidor IMAP usando el gestor de sesión
    try:
        session = IMAPSessionManager.get_instance()
        mail = session.connect(config)
    except Exception as e:
        print(f"\n❌ No se pudo conectar al servidor IMAP")
        print(f"Error: {e}")
        return

    try:
        # Listar carpetas si se solicita
        if args.list_folders:
            print("\n" + "="*80)
            print("📁 CARPETAS DISPONIBLES")
            print("="*80 + "\n")
            folders = get_imap_folders(mail)
            for i, folder in enumerate(folders, 1):
                print(f"  {i}. {folder}")
            print(f"\n📊 Total: {len(folders)} carpetas")
            print("\nUsa estas carpetas con --folders \"carpeta:género\"")
            return

        # Procesar carpetas
        if not args.folders:
            print("\n❌ Debes especificar carpetas con --folders o usar --list-folders")
            print("Ejemplo: --folders \"INBOX:Rock\" \"Sent:Electronic\"")
            return

        embeds_by_genre = defaultdict(list)
        mark_as_read = not args.no_mark_read
        include_read = args.include_read
        delete_after = args.delete

        if delete_after:
            confirm = input("\n⚠️  ¡ATENCIÓN! Vas a ELIMINAR correos. ¿Estás seguro? (escribe 'SI' para confirmar): ")
            if confirm != 'SI':
                print("Operación cancelada")
                return

        print(f"\n{'='*80}")
        print(f"📧 PROCESANDO CORREOS")
        print(f"{'='*80}")
        print(f"Servidor: {config.server}")
        print(f"Email: {config.email}")
        print(f"Marcar como leídos: {'Sí' if mark_as_read else 'No'}")
        print(f"Incluir ya leídos: {'Sí' if include_read else 'No'}")
        print(f"Eliminar correos: {'Sí' if delete_after else 'No'}")
        print(f"{'='*80}\n")

        for folder_spec in args.folders:
            if ':' in folder_spec:
                folder_name, genre = folder_spec.rsplit(':', 1)
            else:
                folder_name = folder_spec
                genre = folder_name.split('/')[-1]

            embeds = process_imap_folder(
                mail, folder_name, genre,
                mark_as_read=mark_as_read,
                include_read=include_read,
                delete_after=delete_after,
                config=config
            )
            embeds_by_genre[genre].extend(embeds)

        # Crear directorio de salida
        os.makedirs(args.output_dir, exist_ok=True)

        # Generar HTMLs por género
        total_embeds = sum(len(embeds) for embeds in embeds_by_genre.values())
        print(f"\n{'='*80}")
        print(f"📊 RESUMEN")
        print(f"{'='*80}")
        print(f"Total de embeds encontrados: {total_embeds}")
        print(f"Géneros: {len(embeds_by_genre)}")

        if total_embeds > 0:
            print(f"\n📝 Generando archivos HTML...")

            for genre, embeds in sorted(embeds_by_genre.items()):
                if not embeds:
                    continue

                print(f"\n  Generando {genre}... ({len(embeds)} discos)")
                filename = generate_genre_html_with_api(
                    genre, embeds, args.output_dir, config, args.items_per_page
                )
                print(f"  Total: {len(embeds)} discos en {genre}")

            print(f"\n{'='*80}")
            print(f"✅ Archivos HTML generados en: {args.output_dir}")
            print(f"{'='*80}\n")
            print(f"📌 IMPORTANTE:")
            print(f"   • Los archivos HTML incluyen botones de acción")
            print(f"   • Para que funcionen, necesitas implementar un servidor API")
            print(f"   • Ver documentación para configurar el backend")
            print(f"\n🌐 Los archivos HTML están listos para visualizar")
            print(f"📝 Ejecuta el generador de índice para crear index.html")
        else:
            print("\n⚠ No se encontraron embeds de Bandcamp en los correos")

    finally:
        # Mantener la sesión abierta (no cerrar automáticamente)
        print("\n✓ Sesión IMAP mantenida abierta para futuras operaciones")


if __name__ == '__main__':
    main()
