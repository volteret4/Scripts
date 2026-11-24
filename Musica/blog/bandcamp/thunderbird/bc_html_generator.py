#!/usr/bin/env python3
"""
Script para generar HTML con embeds de Bandcamp organizados por género
Lee correos de carpetas de Thunderbird y extrae enlaces de Bandcamp
"""

import os
import re
import mailbox
import email
from pathlib import Path
from html import escape
from collections import defaultdict
from urllib.parse import urlparse, parse_qs
import argparse
import urllib.request
import time
from html.parser import HTMLParser


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
                print(f"    🔗 URL extraída (patrón {i+1}): {link[:100]}...")
                return link

    # Debug: buscar cualquier mención de bandcamp
    bandcamp_mentions = re.findall(r'bandcamp\.com[^\s<>"\']{0,100}', email_content, re.IGNORECASE)
    if bandcamp_mentions:
        print(f"    ⚠️  Menciones de bandcamp encontradas pero no pudieron extraerse:")
        for mention in bandcamp_mentions[:3]:  # Solo mostrar las primeras 3
            print(f"       {mention[:80]}")

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
        print(f"    📄 Analizando HTML ({len(html_content)} caracteres)")

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
                    print(f"    ✓ album_id encontrado en TralbumData: {album_id}")
                    embed_url = f'https://bandcamp.com/EmbeddedPlayer/album={album_id}/size=large/bgcol=333333/linkcol=9a64ff/tracklist=false/artwork=small/transparent=true/'
                    return f'<iframe style="border: 0; width: 400px; height: 120px;" src="{embed_url}" seamless></iframe>'

                # Si es un track, buscar de manera diferente
                if item_type_match and item_type_match.group(1) == 'track':
                    if track_id_in_tralbum:
                        track_id = track_id_in_tralbum.group(1)
                        print(f"    ✓ track_id encontrado: {track_id}")
                        embed_url = f'https://bandcamp.com/EmbeddedPlayer/track={track_id}/size=large/bgcol=333333/linkcol=9a64ff/tracklist=false/artwork=small/transparent=true/'
                        return f'<iframe style="border: 0; width: 400px; height: 120px;" src="{embed_url}" seamless></iframe>'
            except Exception as e:
                print(f"    ⚠️  Error procesando TralbumData: {e}")

        # MÉTODO 2: Buscar en window.pagedata o data attributes
        pagedata_match = re.search(r'data-tralbum=["\']?(\d+)["\']?', html_content)
        if pagedata_match:
            album_id = pagedata_match.group(1)
            print(f"    ✓ album_id en data-tralbum: {album_id}")
            embed_url = f'https://bandcamp.com/EmbeddedPlayer/album={album_id}/size=large/bgcol=333333/linkcol=9a64ff/tracklist=false/artwork=small/transparent=true/'
            return f'<iframe style="border: 0; width: 400px; height: 120px;" src="{embed_url}" seamless></iframe>'

        # MÉTODO 3: Buscar directamente "album_id" o "track_id" en cualquier parte
        album_id_anywhere = re.search(r'["\']?album_id["\']?\s*:\s*(\d+)', html_content)
        if album_id_anywhere:
            album_id = album_id_anywhere.group(1)
            print(f"    ✓ album_id encontrado (búsqueda general): {album_id}")
            embed_url = f'https://bandcamp.com/EmbeddedPlayer/album={album_id}/size=large/bgcol=333333/linkcol=9a64ff/tracklist=false/artwork=small/transparent=true/'
            return f'<iframe style="border: 0; width: 400px; height: 120px;" src="{embed_url}" seamless></iframe>'

        track_id_anywhere = re.search(r'["\']?track_id["\']?\s*:\s*(\d+)', html_content)
        if track_id_anywhere:
            track_id = track_id_anywhere.group(1)
            print(f"    ✓ track_id encontrado (búsqueda general): {track_id}")
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
            print(f"    ✓ iframe embed encontrado directamente")
            return f'<iframe style="border: 0; width: 400px; height: 120px;" src="{embed_url}" seamless></iframe>'

        # MÉTODO 5: Buscar en el código JavaScript
        # A veces el ID está en formato: album/1234567890
        embed_in_js = re.search(r'album[=/](\d{8,12})', html_content)
        if embed_in_js:
            album_id = embed_in_js.group(1)
            print(f"    ✓ album_id encontrado en JavaScript: {album_id}")
            embed_url = f'https://bandcamp.com/EmbeddedPlayer/album={album_id}/size=large/bgcol=333333/linkcol=9a64ff/tracklist=false/artwork=small/transparent=true/'
            return f'<iframe style="border: 0; width: 400px; height: 120px;" src="{embed_url}" seamless></iframe>'

        track_in_js = re.search(r'track[=/](\d{8,12})', html_content)
        if track_in_js:
            track_id = track_in_js.group(1)
            print(f"    ✓ track_id encontrado en JavaScript: {track_id}")
            embed_url = f'https://bandcamp.com/EmbeddedPlayer/track={track_id}/size=large/bgcol=333333/linkcol=9a64ff/tracklist=false/artwork=small/transparent=true/'
            return f'<iframe style="border: 0; width: 400px; height: 120px;" src="{embed_url}" seamless></iframe>'

        # DEBUG: Mostrar un fragmento del HTML para ayudar a diagnosticar
        print(f"    ✗ No se encontró album_id ni track_id")

        # Buscar fragmentos que podrían ser útiles
        if 'TralbumData' in html_content:
            print(f"    ℹ️  TralbumData encontrado, pero no se pudo extraer el ID")
            snippet = re.search(r'TralbumData\s*=\s*\{.{0,300}', html_content, re.DOTALL)
            if snippet:
                print(f"    ℹ️  Fragmento: {snippet.group(0)[:200]}...")

        if 'pagedata' in html_content.lower():
            print(f"    ℹ️  'pagedata' mencionado en el HTML")

        # Buscar cualquier número grande que pueda ser un ID
        big_numbers = re.findall(r'\b\d{9,11}\b', html_content[:50000])  # Solo primeros 50KB
        if big_numbers:
            print(f"    ℹ️  Números grandes encontrados (posibles IDs): {big_numbers[:5]}")

        return None

    except Exception as e:
        print(f"    ❌ Error procesando HTML: {type(e).__name__}: {e}")
        import traceback
        print(f"    ℹ️  Traceback: {traceback.format_exc()[:200]}")
        return None


def fetch_bandcamp_embed(url, html_content=None, retry_count=3):
    """
    Consulta la URL de Bandcamp y extrae el código embed real.
    Si se proporciona html_content, lo usa directamente sin hacer petición.
    """
    # Si se proporciona el HTML directamente, usarlo
    if html_content:
        return fetch_bandcamp_embed_from_html(html_content)

    # Validar que la URL parece correcta
    if not url or url == 'https://bandcamp.com' or '/album/' not in url and '/track/' not in url:
        print(f"    ❌ URL inválida o incompleta: {url}")
        return None

    # Intentar obtener el HTML de la URL
    for attempt in range(retry_count):
        try:
            print(f"    🌐 Descargando página (intento {attempt + 1}/{retry_count})...")

            # User agent para evitar bloqueos
            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }

            request = urllib.request.Request(url, headers=headers)

            with urllib.request.urlopen(request, timeout=15) as response:
                status_code = response.getcode()
                print(f"    ✓ Respuesta HTTP {status_code}")

                html = response.read().decode('utf-8', errors='ignore')
                result = fetch_bandcamp_embed_from_html(html)

                if result:
                    return result
                else:
                    print(f"    ⚠️  Página descargada pero no se pudo extraer el embed")
                    return None

        except urllib.error.HTTPError as e:
            print(f"    ❌ Error HTTP {e.code}: {e.reason}")
            if e.code == 404:
                print(f"    ℹ️  La página no existe (404)")
                return None
            elif attempt < retry_count - 1:
                time.sleep(2)
        except urllib.error.URLError as e:
            print(f"    ❌ Error de conexión: {e.reason}")
            if attempt < retry_count - 1:
                time.sleep(2)
        except Exception as e:
            print(f"    ❌ Error inesperado: {type(e).__name__}: {e}")
            if attempt < retry_count - 1:
                time.sleep(2)
            else:
                print(f"    💡 Consejo: Verifica que tienes conexión a Internet")
                return None

    return None


def convert_to_embed(bandcamp_url):
    """
    Convierte una URL de Bandcamp en un iframe embed.
    Ahora consulta la página real para obtener el embed correcto.
    """
    print(f"    🔍 URL: {bandcamp_url[:80]}{'...' if len(bandcamp_url) > 80 else ''}")

    # Intentar obtener el embed real de la página
    embed = fetch_bandcamp_embed(bandcamp_url)

    if embed:
        print(f"    ✅ Embed generado exitosamente")
        return embed

    print(f"    ❌ No se pudo generar el embed")
    return None


def process_mbox_folder(folder_path, genre_name):
    """
    Procesa una carpeta mbox de Thunderbird y extrae los embeds de Bandcamp.
    Elimina duplicados basándose en el album_id del embed.
    """
    embeds = []
    seen_album_ids = set()  # Para evitar duplicados por album_id
    seen_urls = set()  # Backup para URLs sin album_id

    if not os.path.exists(folder_path):
        print(f"Advertencia: La carpeta {folder_path} no existe")
        return embeds

    try:
        # Intentar abrir como mbox
        mbox = mailbox.mbox(folder_path)

        for message_key, message in mbox.items():
            # Obtener el contenido del mensaje
            if message.is_multipart():
                content = ''
                for part in message.walk():
                    if part.get_content_type() == 'text/plain':
                        content += part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    elif part.get_content_type() == 'text/html':
                        content += part.get_payload(decode=True).decode('utf-8', errors='ignore')
            else:
                content = message.get_payload(decode=True).decode('utf-8', errors='ignore')

            # Extraer enlace de Bandcamp
            link = extract_bandcamp_link(content)
            if link:
                # Limpiar la URL de parámetros para comparación básica
                clean_url = link.split('?')[0].strip()

                # Normalizar la URL (quitar trailing slash, convertir a minúsculas)
                normalized_url = clean_url.lower().rstrip('/')

                # Intentar obtener el título del álbum del asunto
                subject = message.get('Subject', '')
                message_id = message.get('Message-ID', '')

                print(f"\n  📧 {subject[:70]}")
                print(f"  " + "─" * 80)

                # Crear embed consultando la página real
                embed = convert_to_embed(link)

                if embed:
                    # Extraer album_id o track_id del embed para detección de duplicados
                    album_id_match = re.search(r'/album=(\d+)/', embed)
                    track_id_match = re.search(r'/track=(\d+)/', embed)

                    # Determinar el identificador único
                    unique_id = None
                    if album_id_match:
                        unique_id = ('album', album_id_match.group(1))
                    elif track_id_match:
                        unique_id = ('track', track_id_match.group(1))

                    # Verificar duplicado por ID
                    if unique_id and unique_id in seen_album_ids:
                        print(f"    ⏭️  DUPLICADO (mismo ID: {unique_id[0]}={unique_id[1]})")
                        print(f"  " + "─" * 80)
                        continue

                    # Verificar duplicado por URL normalizada (backup)
                    if normalized_url in seen_urls:
                        print(f"    ⏭️  DUPLICADO (misma URL)")
                        print(f"  " + "─" * 80)
                        continue

                    # Añadir a la lista con información para identificar el correo
                    embeds.append({
                        'embed': embed,
                        'url': link,
                        'subject': subject,
                        'genre': genre_name,
                        'message_id': message_id,
                        'mbox_path': folder_path,
                        'mbox_key': message_key
                    })

                    # Marcar como procesado
                    if unique_id:
                        seen_album_ids.add(unique_id)
                    seen_urls.add(normalized_url)

                    print(f"    ✅ Añadido (total: {len(embeds)})")
                    print(f"  " + "─" * 80)

                # Pequeña pausa para no saturar el servidor de Bandcamp
                time.sleep(1)

    except Exception as e:
        print(f"Error procesando {folder_path}: {e}")

    print(f"\n  📊 Resumen: {len(embeds)} discos únicos de {len(seen_urls)} correos procesados")

    return embeds


def generate_genre_html(genre, embeds, output_dir, items_per_page=10):
    """
    Genera un archivo HTML para un género específico con paginación.
    """
    import math

    total_pages = math.ceil(len(embeds) / items_per_page)

    # CSS y JavaScript comunes
    common_head = """
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #1a1a1a;
            color: #e0e0e0;
            padding: 20px;
            line-height: 1.6;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
        }

        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid #4c1da3;
        }

        .back-link {
            color: #9a64ff;
            text-decoration: none;
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 10px 20px;
            background: #2a2a2a;
            border-radius: 8px;
            transition: background 0.3s;
        }

        .back-link:hover {
            background: #333;
        }

        h1 {
            color: #4c1da3;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
        }

        .genre-info {
            background: #2a2a2a;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .stats {
            display: flex;
            gap: 30px;
        }

        .stat {
            text-align: center;
        }

        .stat-number {
            font-size: 2em;
            color: #9a64ff;
            font-weight: bold;
        }

        .stat-label {
            color: #888;
            font-size: 0.9em;
        }

        .embed-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }

        .embed-item {
            background: #2a2a2a;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            transition: transform 0.2s, box-shadow 0.2s;
            position: relative;
        }

        .embed-item:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.3);
        }

        .embed-item.listened {
            opacity: 0.5;
            background: #1a1a1a;
        }

        .embed-item iframe {
            width: 100%;
            border-radius: 4px;
        }

        .embed-title {
            margin-top: 10px;
            font-size: 0.9em;
            color: #b0b0b0;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }

        .listened-btn {
            margin-top: 10px;
            width: 100%;
            padding: 8px 15px;
            background: #4c1da3;
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.9em;
            transition: all 0.3s;
        }

        .listened-btn:hover {
            background: #6b2fb5;
        }

        .listened-btn.marked {
            background: #2a7a2a;
        }

        .listened-btn.marked:hover {
            background: #3a9a3a;
        }

        .pagination {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 10px;
            margin: 40px 0;
            flex-wrap: wrap;
        }

        .page-btn {
            padding: 10px 15px;
            background: #2a2a2a;
            color: #e0e0e0;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.3s;
            font-size: 1em;
        }

        .page-btn:hover:not(:disabled) {
            background: #4c1da3;
            transform: translateY(-2px);
        }

        .page-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        .page-btn.active {
            background: #4c1da3;
            font-weight: bold;
        }

        .page-info {
            padding: 10px 20px;
            background: #2a2a2a;
            border-radius: 6px;
            color: #9a64ff;
        }

        .page-content {
            display: none;
        }

        .page-content.active {
            display: block;
        }

        @media (max-width: 768px) {
            .embed-grid {
                grid-template-columns: 1fr;
            }

            h1 {
                font-size: 1.8em;
            }

            .header {
                flex-direction: column;
                gap: 20px;
            }

            .stats {
                flex-direction: column;
                gap: 15px;
            }
        }
    </style>
"""

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{escape(genre)} - Bandcamp Collection</title>
    {common_head}
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎵 {escape(genre)}</h1>
            <a href="index.html" class="back-link">
                <span>←</span>
                <span>Volver al índice</span>
            </a>
        </div>

        <div class="genre-info">
            <div class="stats">
                <div class="stat">
                    <div class="stat-number">{len(embeds)}</div>
                    <div class="stat-label">Discos</div>
                </div>
                <div class="stat">
                    <div class="stat-number">{total_pages}</div>
                    <div class="stat-label">Páginas</div>
                </div>
            </div>
        </div>
"""

    # Crear páginas
    for page_num in range(total_pages):
        start_idx = page_num * items_per_page
        end_idx = min(start_idx + items_per_page, len(embeds))
        page_embeds = embeds[start_idx:end_idx]

        active_class = "active" if page_num == 0 else ""

        html += f"""
        <div class="page-content {active_class}" id="page-{page_num + 1}">
            <div class="embed-grid">
"""

        for item in page_embeds:
            # Crear un ID único para este embed basado en message_id
            embed_id = escape(item.get('message_id', ''))
            mbox_path = escape(item.get('mbox_path', ''))

            html += f"""
                <div class="embed-item" id="embed-{hash(embed_id)}" data-message-id="{embed_id}" data-mbox-path="{mbox_path}">
                    {item['embed']}
                    <div class="embed-title">{escape(item['subject'][:150])}</div>
                    <button class="listened-btn" onclick="markAsListened('{embed_id}', '{mbox_path}', this)">
                        ✓ Escuchado
                    </button>
                </div>
"""

        html += """
            </div>
        </div>
"""

    # Controles de paginación
    html += """
        <div class="pagination">
            <button class="page-btn" id="prev-btn" onclick="changePage(-1)">← Anterior</button>
            <div class="page-info">
                Página <span id="current-page">1</span> de <span id="total-pages">""" + str(total_pages) + """</span>
            </div>
"""

    for page_num in range(1, total_pages + 1):
        active_class = "active" if page_num == 1 else ""
        html += f"""
            <button class="page-btn page-number {active_class}" onclick="goToPage({page_num})">{page_num}</button>
"""

    html += """
            <button class="page-btn" id="next-btn" onclick="changePage(1)">Siguiente →</button>
        </div>
    </div>

    <script>
        let currentPage = 1;
        const totalPages = """ + str(total_pages) + """;

        // Cargar estado de escuchados desde localStorage
        function loadListenedState() {
            const listened = JSON.parse(localStorage.getItem('listened_albums') || '[]');
            listened.forEach(messageId => {
                const embedItem = document.querySelector(`[data-message-id="${messageId}"]`);
                if (embedItem) {
                    embedItem.classList.add('listened');
                    const btn = embedItem.querySelector('.listened-btn');
                    if (btn) {
                        btn.classList.add('marked');
                        btn.textContent = '✓ Marcado';
                    }
                }
            });
        }

        // Marcar álbum como escuchado
        function markAsListened(messageId, mboxPath, button) {
            const embedItem = button.closest('.embed-item');
            const listened = JSON.parse(localStorage.getItem('listened_albums') || '[]');

            if (listened.includes(messageId)) {
                // Ya está marcado, desmarcarlo
                const index = listened.indexOf(messageId);
                listened.splice(index, 1);
                embedItem.classList.remove('listened');
                button.classList.remove('marked');
                button.textContent = '✓ Escuchado';
            } else {
                // Marcarlo como escuchado
                listened.push(messageId);
                embedItem.classList.add('listened');
                button.classList.add('marked');
                button.textContent = '✓ Marcado';

                // Enviar petición al servidor para marcar como leído en Thunderbird
                markEmailAsRead(messageId, mboxPath);
            }

            localStorage.setItem('listened_albums', JSON.stringify(listened));
        }

        // Intentar marcar el correo como leído en Thunderbird
        function markEmailAsRead(messageId, mboxPath) {
            // Enviar petición al servidor local si está corriendo
            fetch('http://localhost:8765/mark_read', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message_id: messageId,
                    mbox_path: mboxPath
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    console.log('✓ Correo marcado como leído en Thunderbird');
                } else {
                    console.log('⚠ No se pudo marcar en Thunderbird (servidor no disponible)');
                }
            })
            .catch(error => {
                console.log('ℹ️ Marcado solo localmente (inicia el servidor para sincronizar con Thunderbird)');
            });
        }

        function updatePagination() {
            // Actualizar visibilidad de páginas
            document.querySelectorAll('.page-content').forEach((page, index) => {
                page.classList.toggle('active', index === currentPage - 1);
            });

            // Actualizar botones de página
            document.querySelectorAll('.page-number').forEach((btn, index) => {
                btn.classList.toggle('active', index === currentPage - 1);
            });

            // Actualizar info de página
            document.getElementById('current-page').textContent = currentPage;

            // Actualizar botones prev/next
            document.getElementById('prev-btn').disabled = currentPage === 1;
            document.getElementById('next-btn').disabled = currentPage === totalPages;

            // Scroll al inicio
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }

        function changePage(delta) {
            const newPage = currentPage + delta;
            if (newPage >= 1 && newPage <= totalPages) {
                currentPage = newPage;
                updatePagination();
            }
        }

        function goToPage(page) {
            if (page >= 1 && page <= totalPages) {
                currentPage = page;
                updatePagination();
            }
        }

        // Atajos de teclado
        document.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowLeft') {
                changePage(-1);
            } else if (e.key === 'ArrowRight') {
                changePage(1);
            }
        });

        // Inicializar
        updatePagination();
        loadListenedState();
    </script>
</body>
</html>
"""

    # Guardar archivo
    filename = f"{genre.lower().replace(' ', '_').replace('/', '_')}.html"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)

    return filename


def generate_index_html(genres_data, output_dir):
    """
    Genera el archivo index.html principal con enlaces a todos los géneros.
    genres_data: dict con {género: {'count': n, 'filename': 'file.html'}}
    """
    html = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bandcamp Collection</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #1a1a1a;
            color: #e0e0e0;
            padding: 20px;
            line-height: 1.6;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            width: 100%;
        }

        header {
            text-align: center;
            margin-bottom: 50px;
            padding: 40px 20px;
            background: linear-gradient(135deg, #2a2a2a 0%, #1a1a1a 100%);
            border-radius: 12px;
        }

        h1 {
            font-size: 3.5em;
            color: #4c1da3;
            margin-bottom: 10px;
            text-shadow: 3px 3px 6px rgba(0,0,0,0.5);
        }

        .subtitle {
            font-size: 1.2em;
            color: #888;
        }

        .stats-bar {
            display: flex;
            justify-content: center;
            gap: 40px;
            margin: 30px 0;
            padding: 20px;
            background: #2a2a2a;
            border-radius: 8px;
        }

        .stat {
            text-align: center;
        }

        .stat-number {
            font-size: 2.5em;
            color: #9a64ff;
            font-weight: bold;
        }

        .stat-label {
            color: #888;
            font-size: 1em;
            margin-top: 5px;
        }

        .search-box {
            max-width: 600px;
            margin: 0 auto 40px;
            position: relative;
        }

        .search-input {
            width: 100%;
            padding: 15px 50px 15px 20px;
            font-size: 1.1em;
            background: #2a2a2a;
            border: 2px solid #333;
            border-radius: 10px;
            color: #e0e0e0;
            transition: border-color 0.3s;
        }

        .search-input:focus {
            outline: none;
            border-color: #4c1da3;
        }

        .search-icon {
            position: absolute;
            right: 20px;
            top: 50%;
            transform: translateY(-50%);
            color: #888;
            font-size: 1.2em;
        }

        .genres-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 25px;
            margin-bottom: 40px;
        }

        .genre-card {
            background: linear-gradient(135deg, #2a2a2a 0%, #222 100%);
            padding: 30px;
            border-radius: 12px;
            text-decoration: none;
            color: inherit;
            transition: all 0.3s;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            border: 2px solid transparent;
            cursor: pointer;
        }

        .genre-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 16px rgba(76, 29, 163, 0.4);
            border-color: #4c1da3;
        }

        .genre-card.hidden {
            display: none;
        }

        .genre-icon {
            font-size: 3em;
            margin-bottom: 15px;
            text-align: center;
        }

        .genre-name {
            font-size: 1.5em;
            font-weight: bold;
            color: #e0e0e0;
            margin-bottom: 10px;
            text-align: center;
        }

        .genre-count {
            text-align: center;
            color: #9a64ff;
            font-size: 1.1em;
            font-weight: bold;
        }

        .genre-count::after {
            content: ' discos';
            font-weight: normal;
            color: #888;
        }

        .no-results {
            text-align: center;
            padding: 60px 20px;
            color: #888;
            font-size: 1.2em;
            display: none;
        }

        .no-results.visible {
            display: block;
        }

        footer {
            text-align: center;
            margin-top: auto;
            padding: 30px 20px;
            color: #666;
            border-top: 1px solid #333;
        }

        @media (max-width: 768px) {
            h1 {
                font-size: 2em;
            }

            .genres-grid {
                grid-template-columns: 1fr;
            }

            .stats-bar {
                flex-direction: column;
                gap: 20px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎵 Mi Colección de Bandcamp</h1>
            <p class="subtitle">Explora tu música por género</p>
        </header>

        <div class="stats-bar">
            <div class="stat">
                <div class="stat-number" id="total-genres">""" + str(len(genres_data)) + """</div>
                <div class="stat-label">Géneros</div>
            </div>
            <div class="stat">
                <div class="stat-number" id="total-albums">""" + str(sum(data['count'] for data in genres_data.values())) + """</div>
                <div class="stat-label">Discos</div>
            </div>
        </div>

        <div class="search-box">
            <input type="text"
                   class="search-input"
                   id="search-input"
                   placeholder="Buscar género..."
                   autocomplete="off">
            <span class="search-icon">🔍</span>
        </div>

        <div class="genres-grid" id="genres-grid">
"""

    # Iconos por género (puedes personalizarlos)
    genre_icons = {
        'rock': '🎸',
        'metal': '🤘',
        'synth pop': '🎹',
        'electronica': '🎹',
        'ambient': '🌙',
        'jazz': '🎺',
        'classical': '🎻',
        'hip-hop': '🎤',
        'hip hop': '🎤',
        'folk': '🪕',
        'musthave': '🎧',
        'experimental': '🔬',
        'deep': '🌊',
        'disco': '💃',
        'techno': '🔊',
        'house': '🏠',
        'punk': '⚡',
        'blues': '🎸',
        'soul': '✨',
        'soul funk': '🕺',
        'reggae': '🌴',
        'world': '🌍',
    }

    # Ordenar géneros alfabéticamente
    for genre in sorted(genres_data.keys()):
        data = genres_data[genre]
        icon = genre_icons.get(genre.lower(), '🎵')

        html += f"""
            <a href="{data['filename']}" class="genre-card" data-genre="{escape(genre.lower())}">
                <div class="genre-icon">{icon}</div>
                <div class="genre-name">{escape(genre)}</div>
                <div class="genre-count">{data['count']}</div>
            </a>
"""

    html += """
        </div>

        <div class="no-results" id="no-results">
            No se encontraron géneros que coincidan con tu búsqueda 😕
        </div>

        <footer>
            Generado con ❤️ desde tus correos de Bandcamp
        </footer>
    </div>

    <script>
        const searchInput = document.getElementById('search-input');
        const genreCards = document.querySelectorAll('.genre-card');
        const noResults = document.getElementById('no-results');
        const genresGrid = document.getElementById('genres-grid');

        searchInput.addEventListener('input', (e) => {
            const searchTerm = e.target.value.toLowerCase().trim();
            let visibleCount = 0;

            genreCards.forEach(card => {
                const genreName = card.dataset.genre;
                const matches = genreName.includes(searchTerm);

                card.classList.toggle('hidden', !matches);
                if (matches) visibleCount++;
            });

            noResults.classList.toggle('visible', visibleCount === 0 && searchTerm !== '');
        });

        // Limpiar búsqueda con ESC
        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                searchInput.value = '';
                searchInput.dispatchEvent(new Event('input'));
            }
        });
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


def main():
    parser = argparse.ArgumentParser(
        description='Genera HTML con embeds de Bandcamp organizados por género'
    )
    parser.add_argument(
        '--mail-dir',
        default=os.path.expanduser('~/.thunderbird'),
        help='Directorio base de Thunderbird (default: ~/.thunderbird)'
    )
    parser.add_argument(
        '--output-dir',
        default='bandcamp_html',
        help='Directorio de salida para los archivos HTML (default: bandcamp_html)'
    )
    parser.add_argument(
        '--items-per-page',
        type=int,
        default=10,
        help='Número de discos por página en cada género (default: 10)'
    )
    parser.add_argument(
        '--folders',
        nargs='+',
        help='Lista de carpetas en formato "ruta:género" (ej: /path/to/mbox:Rock)'
    )

    args = parser.parse_args()

    embeds_by_genre = defaultdict(list)

    if args.folders:
        # Usar las carpetas especificadas
        print("Procesando carpetas especificadas...\n")
        for folder_spec in args.folders:
            if ':' in folder_spec:
                folder_path, genre = folder_spec.rsplit(':', 1)
            else:
                folder_path = folder_spec
                genre = os.path.basename(folder_path)

            print(f"Procesando {genre}...")
            embeds = process_mbox_folder(folder_path, genre)
            embeds_by_genre[genre].extend(embeds)
    else:
        print("Por favor, especifica las carpetas con --folders")
        print("\nEjemplo:")
        print("  python3 bandcamp_html_generator.py --folders \\")
        print("    '/path/to/rock.mbox:Rock' \\")
        print("    '/path/to/electronic.mbox:Electronic' \\")
        print("    '/path/to/jazz.mbox:Jazz' \\")
        print("    --output-dir mi_coleccion \\")
        print("    --items-per-page 15")
        return

    # Generar HTMLs
    total_embeds = sum(len(embeds) for embeds in embeds_by_genre.values())
    print(f"\n{'='*80}")
    print(f"📊 Resumen de la colección:")
    print(f"{'='*80}")
    print(f"Total de embeds encontrados: {total_embeds}")
    print(f"Géneros: {len(embeds_by_genre)}")
    for genre, embeds in sorted(embeds_by_genre.items()):
        print(f"  • {genre}: {len(embeds)} discos")

    if total_embeds > 0:
        generate_all_html_files(embeds_by_genre, args.output_dir, args.items_per_page)
    else:
        print("\n⚠ No se encontraron embeds de Bandcamp en los correos")


if __name__ == '__main__':
    main()
