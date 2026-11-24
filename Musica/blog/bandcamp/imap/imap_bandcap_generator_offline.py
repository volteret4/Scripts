#!/usr/bin/env python3
"""
Script para generar HTML con embeds de Bandcamp organizados por género
Lee correos de un servidor IMAP y extrae enlaces de Bandcamp
"""

import os
import re
import email
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


class IMAPConfig:
    """Configuración para conexión IMAP"""
    def __init__(self, server, port, email_address, password, use_ssl=True):
        self.server = server
        self.port = port
        self.email = email_address
        self.password = password
        self.use_ssl = use_ssl


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


def process_imap_folder(mail, folder_name, genre, mark_as_read=True):
    """
    Procesa una carpeta IMAP buscando enlaces de Bandcamp.

    Args:
        mail: Conexión IMAP activa
        folder_name: Nombre de la carpeta a procesar
        genre: Género musical para clasificar
        mark_as_read: Si True, marca los correos como leídos después de procesarlos

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

        # Buscar todos los correos (o solo los no leídos si prefieres)
        # Para buscar solo no leídos: status, messages = mail.search(None, 'UNSEEN')
        status, messages = mail.search(None, 'ALL')

        if status != 'OK':
            print("❌ Error al buscar correos")
            return embeds

        email_ids = messages[0].split()
        print(f"🔍 Procesando {len(email_ids)} correos...\n")

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

                    # Obtener el embed
                    embed_code = get_bandcamp_embed(bandcamp_link)

                    if embed_code:
                        embeds.append({
                            'url': bandcamp_link,
                            'embed': embed_code,
                            'subject': subject,
                            'date': date,
                            'sender': sender
                        })
                        print(f"       ✓ Embed obtenido ({len(embeds)} total)")
                    else:
                        print(f"       ⚠️  No se pudo obtener el embed")

                    # Marcar como leído si se encontró un enlace y la opción está activa
                    if mark_as_read:
                        mail.store(email_id, '+FLAGS', '\\Seen')
                        print(f"       📖 Marcado como leído")
                else:
                    print("       • Sin enlaces de Bandcamp")

            except Exception as e:
                print(f"       ❌ Error procesando correo: {e}")
                continue

        print(f"\n{'='*80}")
        print(f"✓ Procesamiento completado: {len(embeds)} embeds encontrados")
        print(f"{'='*80}\n")

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

            # Si el enlace es relativo, completarlo
            if link.startswith('/'):
                # Esto no debería pasar, pero por si acaso
                continue

            # Verificar que es un enlace válido de Bandcamp con album o track
            if 'bandcamp.com' in link and ('/album/' in link or '/track/' in link):
                print(f"       🔗 URL extraída (patrón {i+1}): {link[:100]}...")
                return link

    # Debug: buscar cualquier mención de bandcamp
    bandcamp_mentions = re.findall(r'bandcamp\.com[^\s<>"\']{0,100}', email_content, re.IGNORECASE)
    if bandcamp_mentions:
        print(f"       ⚠️  Menciones de bandcamp encontradas pero no pudieron extraerse:")
        for mention in bandcamp_mentions[:3]:  # Solo mostrar las primeras 3
            print(f"          {mention[:80]}")

    return None


class BandcampEmbedParser(HTMLParser):
    """Parser para extraer el código embed de una página de Bandcamp."""

    def __init__(self):
        super().__init__()
        self.embed_code = None
        self.in_embed_section = False

    def handle_starttag(self, tag, attrs):
        if tag == 'iframe':
            attrs_dict = dict(attrs)
            src = attrs_dict.get('src', '')
            # Buscar iframes de Bandcamp embed
            if 'bandcamp.com/EmbeddedPlayer' in src or 'bandcamp.com/EmbeddedPlayer' in src:
                # Reconstruir el iframe
                style = attrs_dict.get('style', 'border: 0; width: 400px; height: 120px;')
                seamless = 'seamless' if 'seamless' in [a[0] for a in attrs] else ''

                self.embed_code = f'<iframe style="{style}" src="{src}" {seamless}></iframe>'


def fetch_bandcamp_embed_from_html(html_content):
    """
    Extrae el código embed del contenido HTML de una página de Bandcamp.
    Busca en múltiples ubicaciones con patrones flexibles.
    """
    try:
        print(f"       📄 Analizando HTML ({len(html_content)} caracteres)")

        # MÉTODO 1: Buscar en el bloque TralbumData (más común)
        # Este es el lugar principal donde Bandcamp guarda la info
        tralbum_data_match = re.search(
            r'var\s+TralbumData\s*=\s*(\{[^;]+\});',
            html_content,
            re.DOTALL
        )

        if tralbum_data_match:
            try:
                import json
                # Intentar parsear el JSON
                tralbum_json_str = tralbum_data_match.group(1)
                # Limpiar el JSON (a veces tiene comentarios o trailing commas)
                tralbum_json_str = re.sub(r',\s*}', '}', tralbum_json_str)
                tralbum_json_str = re.sub(r',\s*]', ']', tralbum_json_str)

                # Buscar los IDs dentro del texto JSON sin parsearlo completamente
                album_id_in_tralbum = re.search(r'"?album_id"?\s*:\s*(\d+)', tralbum_json_str)
                track_id_in_tralbum = re.search(r'"?id"?\s*:\s*(\d+)', tralbum_json_str)
                item_type_match = re.search(r'"?item_type"?\s*:\s*"?(track|album)"?', tralbum_json_str)

                if album_id_in_tralbum:
                    album_id = album_id_in_tralbum.group(1)
                    print(f"       ✓ album_id encontrado en TralbumData: {album_id}")
                    embed_url = f'https://bandcamp.com/EmbeddedPlayer/album={album_id}/size=large/bgcol=333333/linkcol=9a64ff/tracklist=false/artwork=small/transparent=true/'
                    return f'<iframe style="border: 0; width: 400px; height: 120px;" src="{embed_url}" seamless></iframe>'

                # Si es un track, buscar de manera diferente
                if item_type_match and item_type_match.group(1) == 'track':
                    if track_id_in_tralbum:
                        track_id = track_id_in_tralbum.group(1)
                        print(f"       ✓ track_id encontrado: {track_id}")
                        embed_url = f'https://bandcamp.com/EmbeddedPlayer/track={track_id}/size=large/bgcol=333333/linkcol=9a64ff/tracklist=false/artwork=small/transparent=true/'
                        return f'<iframe style="border: 0; width: 400px; height: 120px;" src="{embed_url}" seamless></iframe>'
            except Exception as e:
                print(f"       ⚠️  Error procesando TralbumData: {e}")

        # MÉTODO 2: Buscar en window.pagedata o data attributes
        pagedata_match = re.search(r'data-tralbum=["\']?(\d+)["\']?', html_content)
        if pagedata_match:
            album_id = pagedata_match.group(1)
            print(f"       ✓ album_id en data-tralbum: {album_id}")
            embed_url = f'https://bandcamp.com/EmbeddedPlayer/album={album_id}/size=large/bgcol=333333/linkcol=9a64ff/tracklist=false/artwork=small/transparent=true/'
            return f'<iframe style="border: 0; width: 400px; height: 120px;" src="{embed_url}" seamless></iframe>'

        # MÉTODO 3: Buscar directamente "album_id" o "track_id" en cualquier parte
        album_id_anywhere = re.search(r'["\']?album_id["\']?\s*:\s*(\d+)', html_content)
        if album_id_anywhere:
            album_id = album_id_anywhere.group(1)
            print(f"       ✓ album_id encontrado (búsqueda general): {album_id}")
            embed_url = f'https://bandcamp.com/EmbeddedPlayer/album={album_id}/size=large/bgcol=333333/linkcol=9a64ff/tracklist=false/artwork=small/transparent=true/'
            return f'<iframe style="border: 0; width: 400px; height: 120px;" src="{embed_url}" seamless></iframe>'

        track_id_anywhere = re.search(r'["\']?track_id["\']?\s*:\s*(\d+)', html_content)
        if track_id_anywhere:
            track_id = track_id_anywhere.group(1)
            print(f"       ✓ track_id encontrado (búsqueda general): {track_id}")
            embed_url = f'https://bandcamp.com/EmbeddedPlayer/track={track_id}/size=large/bgcol=333333/linkcol=9a64ff/tracklist=false/artwork=small/transparent=true/'
            return f'<iframe style="border: 0; width: 400px; height: 120px;" src="{embed_url}" seamless></iframe>'

        # MÉTODO 4: Buscar el iframe embed directo (si ya está en la página)
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

        # MÉTODO 5: Buscar en el código JavaScript
        # A veces el ID está en formato: album/1234567890
        embed_in_js = re.search(r'album[=/](\d{8,12})', html_content)
        if embed_in_js:
            album_id = embed_in_js.group(1)
            print(f"       ✓ album_id encontrado en JavaScript: {album_id}")
            embed_url = f'https://bandcamp.com/EmbeddedPlayer/album={album_id}/size=large/bgcol=333333/linkcol=9a64ff/tracklist=false/artwork=small/transparent=true/'
            return f'<iframe style="border: 0; width: 400px; height: 120px;" src="{embed_url}" seamless></iframe>'

        track_in_js = re.search(r'track[=/](\d{8,12})', html_content)
        if track_in_js:
            track_id = track_in_js.group(1)
            print(f"       ✓ track_id encontrado en JavaScript: {track_id}")
            embed_url = f'https://bandcamp.com/EmbeddedPlayer/track={track_id}/size=large/bgcol=333333/linkcol=9a64ff/tracklist=false/artwork=small/transparent=true/'
            return f'<iframe style="border: 0; width: 400px; height: 120px;" src="{embed_url}" seamless></iframe>'

        print(f"       ❌ No se pudo encontrar el embed en el HTML")
        return None

    except Exception as e:
        print(f"       ❌ Error extrayendo embed del HTML: {e}")
        return None


def get_bandcamp_embed(url, retry_count=3):
    """
    Obtiene el código embed de Bandcamp para una URL dada.
    Intenta varias veces en caso de error.
    """
    for attempt in range(retry_count):
        try:
            # Pequeño delay para no saturar el servidor
            if attempt > 0:
                time.sleep(2)
                print(f"       🔄 Reintento {attempt + 1}/{retry_count}...")

            # Descargar la página
            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8', errors='ignore')

            # Extraer el embed del HTML
            embed = fetch_bandcamp_embed_from_html(html)

            if embed:
                return embed

        except urllib.error.HTTPError as e:
            print(f"       ⚠️  Error HTTP {e.code}: {e.reason}")
            if e.code == 404:
                # No reintentar si la página no existe
                return None
        except urllib.error.URLError as e:
            print(f"       ⚠️  Error de conexión: {e.reason}")
        except Exception as e:
            print(f"       ⚠️  Error inesperado: {e}")

    return None


def generate_genre_html(genre, embeds, output_dir, items_per_page=10):
    """
    Genera un archivo HTML para un género específico con sus embeds.
    Incluye paginación si hay muchos discos.
    """
    # Sanitizar el nombre del archivo
    safe_genre = re.sub(r'[^\w\s-]', '', genre).strip().replace(' ', '_')
    filename = f"{safe_genre}.html"

    total_items = len(embeds)
    total_pages = (total_items + items_per_page - 1) // items_per_page

    # Generar los embeds HTML
    embeds_html = ""
    for i, embed_data in enumerate(embeds):
        page_num = (i // items_per_page) + 1
        page_class = f"page-{page_num}" if total_pages > 1 else ""

        embeds_html += f"""
        <div class="embed-item {page_class}" data-page="{page_num}">
            {embed_data['embed']}
            <div class="embed-info">
                <strong>{escape(embed_data.get('subject', 'Sin título'))}</strong><br>
                <small>📅 {escape(embed_data.get('date', 'Fecha desconocida'))}</small>
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

    # HTML completo con estilos mejorados
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
            transition: transform 0.3s, box-shadow 0.3s;
        }}

        .embed-item:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.15);
        }}

        .embed-item.hidden {{
            display: none;
        }}

        .embed-info {{
            margin-top: 15px;
            color: #555;
            font-size: 0.9em;
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

        @media (max-width: 768px) {{
            .embeds-grid {{
                grid-template-columns: 1fr;
            }}

            h1 {{
                font-size: 2em;
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

    <script>
        // Paginación
        const pageButtons = document.querySelectorAll('.page-btn');
        const embedItems = document.querySelectorAll('.embed-item');

        pageButtons.forEach(button => {{
            button.addEventListener('click', () => {{
                const page = button.dataset.page;

                // Actualizar botones activos
                pageButtons.forEach(btn => btn.classList.remove('active'));
                button.classList.add('active');

                // Mostrar/ocultar items
                embedItems.forEach(item => {{
                    if (item.dataset.page === page) {{
                        item.classList.remove('hidden');
                    }} else {{
                        item.classList.add('hidden');
                    }}
                }});

                // Scroll suave al inicio
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
    </script>
</body>
</html>
"""

    filepath = os.path.join(output_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)

    return filename


def generate_index_html(genres_data, output_dir):
    """
    Genera el archivo index.html con enlaces a todos los géneros.
    genres_data: dict con formato {genre_name: {'filename': '...', 'count': N}}
    """
    # Generar cards de géneros
    cards_html = ""
    for genre, data in sorted(genres_data.items()):
        filename = data['filename']
        count = data['count']

        cards_html += f"""
        <div class="genre-card" data-genre="{escape(genre.lower())}">
            <h2>🎵 {escape(genre)}</h2>
            <p class="genre-count">📀 {count} disco{"s" if count != 1 else ""}</p>
            <a href="{filename}" class="genre-link">Ver colección →</a>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎵 Mi Colección de Bandcamp</title>
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
            max-width: 1400px;
            margin: 0 auto;
        }}

        header {{
            text-align: center;
            color: white;
            padding: 50px 20px;
            margin-bottom: 40px;
        }}

        h1 {{
            font-size: 3.5em;
            margin-bottom: 15px;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.2);
        }}

        .subtitle {{
            font-size: 1.3em;
            opacity: 0.9;
        }}

        .search-container {{
            max-width: 600px;
            margin: 0 auto 40px;
        }}

        .search-box {{
            width: 100%;
            padding: 15px 25px;
            font-size: 1.1em;
            border: none;
            border-radius: 50px;
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            box-shadow: 0 5px 20px rgba(0, 0, 0, 0.1);
            outline: none;
            transition: box-shadow 0.3s;
        }}

        .search-box:focus {{
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.15);
        }}

        .genres-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 25px;
            margin-bottom: 40px;
        }}

        .genre-card {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
            transition: transform 0.3s, box-shadow 0.3s;
            text-decoration: none;
            color: inherit;
        }}

        .genre-card:hover {{
            transform: translateY(-10px);
            box-shadow: 0 15px 40px rgba(0, 0, 0, 0.15);
        }}

        .genre-card.hidden {{
            display: none;
        }}

        .genre-card h2 {{
            color: #333;
            font-size: 1.8em;
            margin-bottom: 10px;
        }}

        .genre-count {{
            color: #666;
            font-size: 1.1em;
            margin-bottom: 20px;
        }}

        .genre-link {{
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px 30px;
            border-radius: 25px;
            text-decoration: none;
            font-weight: 500;
            transition: transform 0.3s;
        }}

        .genre-link:hover {{
            transform: scale(1.05);
        }}

        .no-results {{
            text-align: center;
            color: white;
            font-size: 1.3em;
            padding: 40px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            display: none;
        }}

        .no-results.visible {{
            display: block;
        }}

        footer {{
            text-align: center;
            color: rgba(255, 255, 255, 0.8);
            padding: 30px;
            margin-top: 40px;
        }}

        @media (max-width: 768px) {{
            h1 {{
                font-size: 2.5em;
            }}

            .genres-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎵 Mi Colección de Bandcamp</h1>
            <p class="subtitle">Explora tu música por género</p>
        </header>

        <div class="search-container">
            <input type="text" class="search-box" placeholder="🔍 Buscar género..." id="searchInput">
        </div>

        <div class="genres-grid" id="genresGrid">
            {cards_html}
        </div>

        <div class="no-results" id="noResults">
            No se encontraron géneros que coincidan con tu búsqueda
        </div>

        <footer>
            <p>Generado con ❤️ para los amantes de Bandcamp</p>
            <p style="margin-top: 10px; font-size: 0.9em;">
                Total de géneros: {len(genres_data)} |
                Total de discos: {sum(d['count'] for d in genres_data.values())}
            </p>
        </footer>
    </div>

    <script>
        const searchInput = document.getElementById('searchInput');
        const genreCards = document.querySelectorAll('.genre-card');
        const noResults = document.getElementById('noResults');

        // Búsqueda en tiempo real
        searchInput.addEventListener('input', (e) => {{
            const searchTerm = e.target.value.toLowerCase().trim();
            let visibleCount = 0;

            genreCards.forEach(card => {{
                const genreName = card.dataset.genre;
                const matches = genreName.includes(searchTerm);

                card.classList.toggle('hidden', !matches);
                if (matches) visibleCount++;
            }});

            noResults.classList.toggle('visible', visibleCount === 0 && searchTerm !== '');
        }});

        // Limpiar búsqueda con ESC
        searchInput.addEventListener('keydown', (e) => {{
            if (e.key === 'Escape') {{
                searchInput.value = '';
                searchInput.dispatchEvent(new Event('input'));
            }}
        }});
    </script>
</body>
</html>
"""

    filepath = os.path.join(output_dir, 'index.html')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"\n✓ Index generado: {filepath}")


def generate_all_html_files(embeds_by_genre, output_dir, items_per_page=10):
    """
    Genera todos los archivos HTML: uno por género y actualiza el index principal.
    Si ya existe un index, lo actualiza con los nuevos géneros.
    """
    # Crear directorio de salida si no existe
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n{'='*80}")
    print(f"📝 Generando archivos HTML...")
    print(f"{'='*80}\n")

    # Detectar HTMLs existentes en el directorio
    existing_genres = {}
    index_path = os.path.join(output_dir, 'index.html')

    print(f"  🔍 Buscando archivos HTML existentes en {output_dir}...")

    for file in os.listdir(output_dir):
        if file.endswith('.html') and file != 'index.html':
            filepath = os.path.join(output_dir, file)
            # Intentar extraer información del HTML
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Buscar el título del género en el HTML
                    title_match = re.search(r'<h1>🎵 ([^<]+)</h1>', content)
                    # Contar discos buscando embed-item
                    count = len(re.findall(r'class="embed-item"', content))

                    if title_match and count > 0:
                        genre_name = title_match.group(1).strip()
                        existing_genres[genre_name] = {
                            'filename': file,
                            'count': count
                        }
                        print(f"    ✓ Encontrado: {file} ({genre_name}, {count} discos)")
            except Exception as e:
                print(f"    ⚠ No se pudo leer {file}: {e}")

    if existing_genres:
        print(f"\n  📊 {len(existing_genres)} géneros existentes detectados")
    else:
        print(f"\n  ℹ️  No se encontraron géneros previos")

    # Generar nuevos HTML por género
    print(f"\n  🆕 Generando nuevos géneros...")
    new_genres = {}

    for genre, embeds in sorted(embeds_by_genre.items()):
        if not embeds:
            continue

        print(f"    Generando {genre}... ({len(embeds)} discos)")
        filename = generate_genre_html(genre, embeds, output_dir, items_per_page)

        new_genres[genre] = {
            'count': len(embeds),
            'filename': filename
        }

        print(f"      ✓ {filename}")

        # Actualizar o añadir en existing_genres
        existing_genres[genre] = new_genres[genre]

    # Generar/actualizar index con TODOS los géneros (existentes + nuevos)
    print(f"\n  📑 {'Actualizando' if len(existing_genres) > len(new_genres) else 'Generando'} index principal...")
    generate_index_html(existing_genres, output_dir)

    print(f"\n{'='*80}")
    print(f"✅ Archivos HTML en: {output_dir}")
    print(f"{'='*80}\n")
    print(f"📂 Contenido del índice:")
    print(f"   • index.html (página principal)")

    # Mostrar todos los géneros en el índice
    for genre, data in sorted(existing_genres.items()):
        status = "🆕" if genre in new_genres else "📌"
        print(f"   {status} {data['filename']} ({data['count']} discos) - {genre}")

    print(f"\n🌐 Abre {os.path.join(output_dir, 'index.html')} en tu navegador")

    return existing_genres


def interactive_setup():
    """
    Modo interactivo para configurar la conexión IMAP.
    """
    print("\n" + "="*80)
    print("🔧 CONFIGURACIÓN IMAP")
    print("="*80 + "\n")

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
        description='Genera HTML con embeds de Bandcamp desde correos IMAP',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:

1. Modo interactivo (recomendado para primera vez):
   python3 bc_html_generator_imap.py --interactive

2. Listar carpetas disponibles:
   python3 bc_html_generator_imap.py --list-folders \\
     --server imap.gmail.com --email tu@email.com

3. Procesar carpetas específicas:
   python3 bc_html_generator_imap.py \\
     --server imap.gmail.com --email tu@email.com \\
     --folders "INBOX/Rock:Rock" "INBOX/Electronic:Electronic"

4. No marcar como leídos (solo leer):
   python3 bc_html_generator_imap.py --interactive --no-mark-read

Notas:
  - Para Gmail, necesitas usar una "Contraseña de aplicación"
    https://support.google.com/accounts/answer/185833
  - Las carpetas se especifican como "ruta:género"
  - Por defecto los correos procesados se marcan como leídos
        """
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

    # Conectar al servidor IMAP
    try:
        mail = connect_imap(config)
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

        print(f"\n{'='*80}")
        print(f"📧 PROCESANDO CORREOS")
        print(f"{'='*80}")
        print(f"Servidor: {config.server}")
        print(f"Email: {config.email}")
        print(f"Marcar como leídos: {'Sí' if mark_as_read else 'No'}")
        print(f"{'='*80}\n")

        for folder_spec in args.folders:
            if ':' in folder_spec:
                folder_name, genre = folder_spec.rsplit(':', 1)
            else:
                folder_name = folder_spec
                genre = folder_name.split('/')[-1]  # Usar la última parte como género

            embeds = process_imap_folder(mail, folder_name, genre, mark_as_read)
            embeds_by_genre[genre].extend(embeds)

        # Generar HTMLs
        total_embeds = sum(len(embeds) for embeds in embeds_by_genre.values())
        print(f"\n{'='*80}")
        print(f"📊 RESUMEN DE LA COLECCIÓN")
        print(f"{'='*80}")
        print(f"Total de embeds encontrados: {total_embeds}")
        print(f"Géneros: {len(embeds_by_genre)}")
        for genre, embeds in sorted(embeds_by_genre.items()):
            print(f"  • {genre}: {len(embeds)} discos")

        if total_embeds > 0:
            generate_all_html_files(embeds_by_genre, args.output_dir, args.items_per_page)
        else:
            print("\n⚠ No se encontraron embeds de Bandcamp en los correos")

    finally:
        # Cerrar conexión
        try:
            mail.close()
            mail.logout()
            print("\n✓ Conexión cerrada")
        except:
            pass


if __name__ == '__main__':
    main()
