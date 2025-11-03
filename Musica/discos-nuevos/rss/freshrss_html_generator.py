#!/usr/bin/env python3
"""
Script para generar HTML con embeds de Bandcamp, YouTube y SoundCloud
desde feeds de FreshRSS.

Lee artículos de feeds RSS mediante la API de FreshRSS y extrae enlaces
de los tres servicios, generando un HTML por cada feed seleccionado.

CORRECCIONES APLICADAS:
1. YouTube: Cambiado a youtube-nocookie.com y agregado parámetros necesarios
2. Bandcamp: Corregido el formato de embed URL y dimensiones del iframe
"""

import os
import re
import json
import argparse
import getpass
import requests
import urllib.request
import urllib.error
import time
from pathlib import Path
from html import escape
from collections import defaultdict
from urllib.parse import urlparse, parse_qs
from datetime import datetime


class FreshRSSConfig:
    """Configuración para conexión a FreshRSS"""
    def __init__(self, server_url, username, password):
        self.server_url = server_url.rstrip('/')
        self.username = username
        self.password = password
        self.api_url = f"{self.server_url}/api/greader.php"
        self.token = None


class FreshRSSClient:
    """Cliente para interactuar con la API de FreshRSS (Google Reader API)"""

    def __init__(self, config):
        self.config = config
        self.session = requests.Session()

    def authenticate(self):
        """Autentica con FreshRSS y obtiene el token"""
        print(f"🔌 Conectando a {self.config.server_url}...")

        # Paso 1: Obtener el token de autenticación
        auth_url = f"{self.config.api_url}/accounts/ClientLogin"
        auth_data = {
            'Email': self.config.username,
            'Passwd': self.config.password
        }

        try:
            response = self.session.post(auth_url, data=auth_data)
            response.raise_for_status()

            # Extraer el token de la respuesta
            for line in response.text.split('\n'):
                if line.startswith('Auth='):
                    self.config.token = line.split('=', 1)[1]
                    break

            if not self.config.token:
                raise Exception("No se pudo obtener el token de autenticación")

            print("✓ Autenticación exitosa\n")
            return True

        except requests.exceptions.RequestException as e:
            print(f"❌ Error de autenticación: {e}")
            return False

    def get_feeds(self):
        """Obtiene la lista de feeds disponibles"""
        url = f"{self.config.api_url}/reader/api/0/subscription/list"
        headers = {'Authorization': f'GoogleLogin auth={self.config.token}'}
        params = {'output': 'json'}

        try:
            response = self.session.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            feeds = []
            for subscription in data.get('subscriptions', []):
                feed = {
                    'id': subscription.get('id', ''),
                    'title': subscription.get('title', ''),
                    'categories': [cat.get('label', '') for cat in subscription.get('categories', [])]
                }
                feeds.append(feed)

            return feeds

        except Exception as e:
            print(f"❌ Error obteniendo feeds: {e}")
            return []

    def get_categories(self):
        """Obtiene la lista de categorías disponibles"""
        url = f"{self.config.api_url}/reader/api/0/tag/list"
        headers = {'Authorization': f'GoogleLogin auth={self.config.token}'}
        params = {'output': 'json'}

        try:
            response = self.session.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            categories = []
            for tag in data.get('tags', []):
                if tag.get('id', '').startswith('user/-/label/'):
                    label = tag.get('id', '').split('user/-/label/')[-1]
                    categories.append(label)

            return categories

        except Exception as e:
            print(f"❌ Error obteniendo categorías: {e}")
            return []

    def get_articles(self, feed_id=None, category=None, count=100, unread_only=False):
        """
        Obtiene artículos de un feed o categoría específica.

        Args:
            feed_id: ID del feed (formato: feed/123)
            category: Nombre de la categoría
            count: Número máximo de artículos a obtener
            unread_only: Si True, solo obtiene artículos no leídos
        """
        url = f"{self.config.api_url}/reader/api/0/stream/contents"
        headers = {'Authorization': f'GoogleLogin auth={self.config.token}'}

        params = {'n': count, 'output': 'json'}

        if feed_id:
            params['s'] = feed_id
        elif category:
            params['s'] = f'user/-/label/{category}'
        else:
            params['s'] = 'user/-/state/com.google/reading-list'

        if unread_only:
            params['xt'] = 'user/-/state/com.google/read'

        try:
            response = self.session.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            articles = []
            for item in data.get('items', []):
                article = {
                    'id': item.get('id', ''),
                    'title': item.get('title', ''),
                    'link': item.get('alternate', [{}])[0].get('href', '') if item.get('alternate') else '',
                    'content': item.get('summary', {}).get('content', ''),
                    'published': item.get('published', 0),
                    'author': item.get('author', ''),
                    'feed_title': item.get('origin', {}).get('title', ''),
                    'feed_id': item.get('origin', {}).get('streamId', '')
                }
                articles.append(article)

            return articles

        except Exception as e:
            print(f"❌ Error obteniendo artículos: {e}")
            return []


def fetch_bandcamp_embed_from_html(html_content):
    """
    Extrae el código embed del contenido HTML de una página de Bandcamp.
    Usa múltiples métodos para encontrar los IDs necesarios.
    COPIADO EXACTAMENTE DE bc_imap_generator.py que funciona correctamente.
    """
    try:
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
        return None

    except Exception as e:
        print(f"       ❌ Error extrayendo embed: {e}")
        return None


def get_bandcamp_embed(url, retry_count=3):
    """
    Obtiene el código embed de Bandcamp para una URL dada.
    Intenta varias veces en caso de error.
    COPIADO EXACTAMENTE DE bc_imap_generator.py que funciona correctamente.
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


def extract_bandcamp_url(text):
    """Extrae URLs de Bandcamp del texto"""
    patterns = [
        r'https?://[a-zA-Z0-9-]+\.bandcamp\.com/(?:album|track)/[a-zA-Z0-9-]+',
        r'https?://bandcamp\.com/[a-zA-Z0-9-]+',
    ]

    urls = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        urls.extend(matches)

    return list(set(urls))


def extract_youtube_url(text):
    """Extrae URLs de YouTube del texto"""
    patterns = [
        r'https?://(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
        r'https?://(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        r'https?://youtu\.be/([a-zA-Z0-9_-]{11})',
    ]

    video_ids = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        video_ids.extend(matches)

    # Usar youtube.com normal (youtube-nocookie causa error 153 en algunos videos)
    urls = [f"https://www.youtube.com/embed/{vid}" for vid in set(video_ids)]
    return urls


def extract_soundcloud_url(text):
    """Extrae URLs de SoundCloud del texto"""
    patterns = [
        r'https?://soundcloud\.com/[a-zA-Z0-9-_]+/[a-zA-Z0-9-_]+',
        r'https?://(?:w|m)\.soundcloud\.com/[a-zA-Z0-9-_]+/[a-zA-Z0-9-_]+',
    ]

    urls = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        urls.extend(matches)

    return list(set(urls))


def process_feed(client, feed_id, feed_name, unread_only=False, max_articles=100):
    """
    Procesa un feed individual y extrae los embeds de Bandcamp, YouTube y SoundCloud.
    """
    print(f"\n{'='*80}")
    print(f"📡 Procesando feed: {feed_name}")
    print(f"{'='*80}\n")

    articles = client.get_articles(feed_id=feed_id, count=max_articles, unread_only=unread_only)

    embeds = {
        'bandcamp': [],
        'youtube': [],
        'soundcloud': []
    }

    print(f"Artículos obtenidos: {len(articles)}")

    for i, article in enumerate(articles, 1):
        content = article['content'] + ' ' + article['link']

        # Extraer URLs de Bandcamp
        bc_urls = extract_bandcamp_url(content)
        for url in bc_urls:
            print(f"  [{i}/{len(articles)}] 🎵 Bandcamp encontrado: {url}")
            embed_code = get_bandcamp_embed(url)

            if embed_code:
                embeds['bandcamp'].append({
                    'url': url,
                    'embed': embed_code,  # Guardamos el código HTML completo del iframe
                    'title': article['title'],
                    'article_link': article['link'],
                    'author': article['author'],
                    'feed': article['feed_title'],
                    'date': datetime.fromtimestamp(article['published']).strftime('%Y-%m-%d %H:%M')
                })
                print(f"       ✓ Embed obtenido")
            else:
                print(f"       ⚠ No se pudo obtener embed")

        # Extraer URLs de YouTube
        yt_urls = extract_youtube_url(content)
        for url in yt_urls:
            print(f"  [{i}/{len(articles)}] 📺 YouTube encontrado: {url}")
            embeds['youtube'].append({
                'url': url,
                'title': article['title'],
                'article_link': article['link'],
                'author': article['author'],
                'feed': article['feed_title'],
                'date': datetime.fromtimestamp(article['published']).strftime('%Y-%m-%d %H:%M')
            })

        # Extraer URLs de SoundCloud
        sc_urls = extract_soundcloud_url(content)
        for url in sc_urls:
            print(f"  [{i}/{len(articles)}] 🔊 SoundCloud encontrado: {url}")
            embeds['soundcloud'].append({
                'url': url,
                'title': article['title'],
                'article_link': article['link'],
                'author': article['author'],
                'feed': article['feed_title'],
                'date': datetime.fromtimestamp(article['published']).strftime('%Y-%m-%d %H:%M')
            })

    total = len(embeds['bandcamp']) + len(embeds['youtube']) + len(embeds['soundcloud'])
    print(f"\n📊 Total encontrados: {total} embeds")
    print(f"   Bandcamp: {len(embeds['bandcamp'])}")
    print(f"   YouTube: {len(embeds['youtube'])}")
    print(f"   SoundCloud: {len(embeds['soundcloud'])}\n")

    return embeds


def process_category(client, category, unread_only=False, max_articles=100):
    """
    Procesa una categoría completa y extrae los embeds.
    """
    print(f"\n{'='*80}")
    print(f"📁 Procesando categoría: {category}")
    print(f"{'='*80}\n")

    articles = client.get_articles(category=category, count=max_articles, unread_only=unread_only)

    embeds = {
        'bandcamp': [],
        'youtube': [],
        'soundcloud': []
    }

    print(f"Artículos obtenidos: {len(articles)}")

    for i, article in enumerate(articles, 1):
        content = article['content'] + ' ' + article['link']

        # Extraer URLs de Bandcamp
        bc_urls = extract_bandcamp_url(content)
        for url in bc_urls:
            print(f"  [{i}/{len(articles)}] 🎵 Bandcamp encontrado: {url}")
            embed_code = get_bandcamp_embed(url)

            if embed_code:
                embeds['bandcamp'].append({
                    'url': url,
                    'embed': embed_code,  # Guardamos el código HTML completo del iframe
                    'title': article['title'],
                    'article_link': article['link'],
                    'author': article['author'],
                    'feed': article['feed_title'],
                    'date': datetime.fromtimestamp(article['published']).strftime('%Y-%m-%d %H:%M')
                })
                print(f"       ✓ Embed obtenido")
            else:
                print(f"       ⚠ No se pudo obtener embed")

        # Extraer URLs de YouTube
        yt_urls = extract_youtube_url(content)
        for url in yt_urls:
            print(f"  [{i}/{len(articles)}] 📺 YouTube encontrado: {url}")
            embeds['youtube'].append({
                'url': url,
                'title': article['title'],
                'article_link': article['link'],
                'author': article['author'],
                'feed': article['feed_title'],
                'date': datetime.fromtimestamp(article['published']).strftime('%Y-%m-%d %H:%M')
            })

        # Extraer URLs de SoundCloud
        sc_urls = extract_soundcloud_url(content)
        for url in sc_urls:
            print(f"  [{i}/{len(articles)}] 🔊 SoundCloud encontrado: {url}")
            embeds['soundcloud'].append({
                'url': url,
                'title': article['title'],
                'article_link': article['link'],
                'author': article['author'],
                'feed': article['feed_title'],
                'date': datetime.fromtimestamp(article['published']).strftime('%Y-%m-%d %H:%M')
            })

    total = len(embeds['bandcamp']) + len(embeds['youtube']) + len(embeds['soundcloud'])
    print(f"\n📊 Total encontrados: {total} embeds")
    print(f"   Bandcamp: {len(embeds['bandcamp'])}")
    print(f"   YouTube: {len(embeds['youtube'])}")
    print(f"   SoundCloud: {len(embeds['soundcloud'])}\n")

    return embeds


def generate_feed_html(feed_name, embeds, output_dir, items_per_page=8, max_pages_buttons=15):
    """
    Genera un archivo HTML con paginación para un feed específico.
    CORRECCIONES: YouTube usa youtube-nocookie.com y Bandcamp usa dimensiones correctas
    """
    # Combinar todos los embeds en una sola lista
    all_embeds = []

    for bc in embeds['bandcamp']:
        all_embeds.append({
            'type': 'bandcamp',
            'url': bc['url'],
            'embed_html': bc.get('embed'),  # Código HTML completo del iframe
            'title': bc['title'],
            'article_link': bc['article_link'],
            'author': bc['author'],
            'feed': bc['feed'],
            'date': bc['date']
        })

    for yt in embeds['youtube']:
        all_embeds.append({
            'type': 'youtube',
            'url': yt['url'],
            'title': yt['title'],
            'article_link': yt['article_link'],
            'author': yt['author'],
            'feed': yt['feed'],
            'date': yt['date']
        })

    for sc in embeds['soundcloud']:
        all_embeds.append({
            'type': 'soundcloud',
            'url': sc['url'],
            'title': sc['title'],
            'article_link': sc['article_link'],
            'author': sc['author'],
            'feed': sc['feed'],
            'date': sc['date']
        })

    # Ordenar por fecha (más recientes primero)
    all_embeds.sort(key=lambda x: x['date'], reverse=True)

    # Paginar
    total_items = len(all_embeds)
    total_pages = (total_items + items_per_page - 1) // items_per_page

    pages_data = {}
    for i in range(total_pages):
        start_idx = i * items_per_page
        end_idx = start_idx + items_per_page
        pages_data[str(i + 1)] = all_embeds[start_idx:end_idx]

    # Convertir a JSON para incrustar
    pages_data_json = json.dumps(pages_data, ensure_ascii=False, indent=2)

    # Generar nombre de archivo
    safe_name = re.sub(r'[^\w\s-]', '', feed_name).strip().replace(' ', '_')
    main_filename = f"{safe_name}.html"

    # Generar HTML
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{escape(feed_name)} - Embeds</title>
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
            margin-bottom: 40px;
        }}

        h1 {{
            color: white;
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }}

        .stats {{
            color: rgba(255,255,255,0.9);
            font-size: 1.1em;
        }}

        .embeds-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 30px;
            margin-bottom: 40px;
        }}

        @media (max-width: 768px) {{
            .embeds-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        .embed-item {{
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: transform 0.3s, box-shadow 0.3s;
        }}

        .embed-item:hover {{
            transform: translateY(-5px);
            box-shadow: 0 8px 12px rgba(0,0,0,0.15);
        }}

        .embed-info {{
            margin-bottom: 15px;
        }}

        .embed-type {{
            display: inline-block;
            font-size: 1.2em;
            margin-bottom: 8px;
        }}

        .embed-info h3 {{
            font-size: 1.1em;
            color: #2d3748;
            margin-bottom: 10px;
            line-height: 1.4;
        }}

        .embed-info .meta {{
            font-size: 0.9em;
            color: #718096;
            margin-bottom: 8px;
        }}

        .embed-info a {{
            color: #667eea;
            text-decoration: none;
            font-size: 0.9em;
        }}

        .embed-info a:hover {{
            text-decoration: underline;
        }}

        .embed-container {{
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 200px;
        }}

        .embed-container iframe {{
            max-width: 100%;
        }}

        .pagination {{
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 10px;
            margin: 40px 0;
            flex-wrap: wrap;
        }}

        .page-btn {{
            padding: 10px 20px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1em;
            transition: background 0.3s;
        }}

        .page-btn:hover:not(:disabled) {{
            background: #5568d3;
        }}

        .page-btn:disabled {{
            background: #cbd5e0;
            cursor: not-allowed;
        }}

        .page-btn.active {{
            background: #764ba2;
            font-weight: bold;
        }}

        .page-info {{
            padding: 10px 20px;
            background: #f7fafc;
            border-radius: 8px;
            font-weight: 600;
        }}

        .loading {{
            text-align: center;
            padding: 40px;
            font-size: 1.2em;
            color: #718096;
        }}

        .loading::after {{
            content: '...';
            animation: dots 1.5s steps(4, end) infinite;
        }}

        @keyframes dots {{
            0%, 20% {{ content: '.'; }}
            40% {{ content: '..'; }}
            60%, 100% {{ content: '...'; }}
        }}

        footer {{
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 2px solid rgba(255,255,255,0.2);
            color: rgba(255,255,255,0.8);
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{escape(feed_name)}</h1>
            <div class="stats">
                Total: {total_items} embeds | Páginas: {total_pages}
            </div>
        </header>

        <div id="pagination-top" class="pagination"></div>
        <div id="content"></div>
        <div id="pagination-bottom" class="pagination"></div>

        <footer>
            <p>Generado desde FreshRSS</p>
        </footer>
    </div>

    <script>
        // Datos incrustados directamente en el HTML
        const allPagesData = {pages_data_json};
        const totalPages = {total_pages};
        const maxPagesButtons = {max_pages_buttons};
        let currentPage = 1;

        // FUNCIONES CORREGIDAS PARA GENERAR EMBEDS
        function generateBandcampEmbed(item) {{
            // CORRECCIÓN CRÍTICA: Usar directamente el HTML del embed que viene del servidor
            // en lugar de intentar generarlo en el cliente
            if (item.embed_html) {{
                return item.embed_html;
            }}
            return `<p>URL de Bandcamp: <a href="${{item.url}}" target="_blank">${{item.url}}</a></p>`;
        }}

        function generateYoutubeEmbed(url) {{
            // La URL ya viene correcta desde Python: https://www.youtube-nocookie.com/embed/VIDEO_ID
            // Solo agregamos los parámetros necesarios
            const embedUrl = url.includes('?') ? url : `${{url}}`;
            return `<iframe width="560" height="315" src="${{embedUrl}}" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe>`;
        }}

        function generateSoundcloudEmbed(url) {{
            const encodedUrl = encodeURIComponent(url);
            const embedUrl = `https://w.soundcloud.com/player/?url=${{encodedUrl}}&color=%23ff5500&auto_play=false&hide_related=false&show_comments=true&show_user=true&show_reposts=false&show_teaser=true`;
            return `<iframe width="100%" height="166" scrolling="no" frameborder="no" allow="autoplay" src="${{embedUrl}}"></iframe>`;
        }}

        function escapeHtml(text) {{
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }}

        function generateEmbedHTML(item) {{
            const typeIcons = {{
                'bandcamp': '🎵',
                'youtube': '📺',
                'soundcloud': '🔊'
            }};

            const typeNames = {{
                'bandcamp': 'Bandcamp',
                'youtube': 'YouTube',
                'soundcloud': 'SoundCloud'
            }};

            let embedCode = '';
            if (item.type === 'bandcamp') {{
                embedCode = generateBandcampEmbed(item);
            }} else if (item.type === 'youtube') {{
                embedCode = generateYoutubeEmbed(item.url);
            }} else if (item.type === 'soundcloud') {{
                embedCode = generateSoundcloudEmbed(item.url);
            }}

            return `
                <div class="embed-item">
                    <div class="embed-info">
                        <div class="embed-type">${{typeIcons[item.type]}} ${{typeNames[item.type]}}</div>
                        <h3>${{escapeHtml(item.title)}}</h3>
                        <p class="meta">
                            📅 ${{item.date}}
                            ${{item.author ? ` | 👤 ${{escapeHtml(item.author)}}` : ''}}
                            ${{item.feed ? ` | 📡 ${{escapeHtml(item.feed)}}` : ''}}
                        </p>
                        <p><a href="${{escapeHtml(item.article_link)}}" target="_blank">Ver artículo original →</a></p>
                    </div>
                    <div class="embed-container">
                        ${{embedCode}}
                    </div>
                </div>
            `;
        }}

        function loadPage(pageNum) {{
            if (pageNum < 1 || pageNum > totalPages) return;

            const content = document.getElementById('content');
            const pageData = allPagesData[String(pageNum)];

            if (!pageData) {{
                content.innerHTML = '<div class="loading">Página no encontrada</div>';
                return;
            }}

            let html = '<div class="embeds-grid">';
            for (const item of pageData) {{
                html += generateEmbedHTML(item);
            }}
            html += '</div>';

            content.innerHTML = html;
            currentPage = pageNum;
            renderPagination();

            // Scroll al principio
            window.scrollTo({{ top: 0, behavior: 'smooth' }});
        }}

        function renderPagination() {{
            const paginationHTML = createPaginationButtons();
            document.getElementById('pagination-top').innerHTML = paginationHTML;
            document.getElementById('pagination-bottom').innerHTML = paginationHTML;
        }}

        function createPaginationButtons() {{
            let html = '';

            // Botón anterior
            if (currentPage > 1) {{
                html += `<button class="page-btn" onclick="changePage(${{currentPage - 1}})">← Anterior</button>`;
            }} else {{
                html += `<button class="page-btn" disabled>← Anterior</button>`;
            }}

            // Calcular rango de páginas a mostrar
            let startPage = Math.max(1, currentPage - Math.floor(maxPagesButtons / 2));
            let endPage = Math.min(totalPages, startPage + maxPagesButtons - 1);

            // Ajustar si estamos cerca del final
            if (endPage - startPage < maxPagesButtons - 1) {{
                startPage = Math.max(1, endPage - maxPagesButtons + 1);
            }}

            // Primera página si no está en el rango
            if (startPage > 1) {{
                html += `<button class="page-btn" onclick="changePage(1)">1</button>`;
                if (startPage > 2) {{
                    html += `<span class="page-info">...</span>`;
                }}
            }}

            // Páginas numeradas
            for (let i = startPage; i <= endPage; i++) {{
                if (i === currentPage) {{
                    html += `<button class="page-btn active">${{i}}</button>`;
                }} else {{
                    html += `<button class="page-btn" onclick="changePage(${{i}})">${{i}}</button>`;
                }}
            }}

            // Última página si no está en el rango
            if (endPage < totalPages) {{
                if (endPage < totalPages - 1) {{
                    html += `<span class="page-info">...</span>`;
                }}
                html += `<button class="page-btn" onclick="changePage(${{totalPages}})">${{totalPages}}</button>`;
            }}

            // Botón siguiente
            if (currentPage < totalPages) {{
                html += `<button class="page-btn" onclick="changePage(${{currentPage + 1}})")>Siguiente →</button>`;
            }} else {{
                html += `<button class="page-btn" disabled>Siguiente →</button>`;
            }}

            return html;
        }}

        function changePage(pageNum) {{
            if (pageNum >= 1 && pageNum <= totalPages) {{
                loadPage(pageNum);
            }}
        }}

        // Cargar primera página al inicio
        console.log('Datos cargados:', Object.keys(allPagesData).length, 'páginas');
        loadPage(1);

        // Soporte para teclas de navegación
        document.addEventListener('keydown', (e) => {{
            if (e.key === 'ArrowLeft') {{
                changePage(currentPage - 1);
            }} else if (e.key === 'ArrowRight') {{
                changePage(currentPage + 1);
            }}
        }});
    </script>
</body>
</html>
"""

    filepath = os.path.join(output_dir, main_filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"      ✓ {main_filename} generado ({total_pages} páginas)")
    return main_filename


def interactive_setup():
    """Modo interactivo para configurar la conexión a FreshRSS"""
    print("\n" + "="*80)
    print("🔧 CONFIGURACIÓN FRESHRSS")
    print("="*80 + "\n")

    print("Introduce la URL de tu servidor FreshRSS")
    print("Ejemplo: https://rss.example.com o http://localhost:8080")
    server_url = input("URL del servidor: ").strip()

    username = input("Usuario: ").strip()
    password = getpass.getpass("Contraseña: ")

    return FreshRSSConfig(server_url, username, password)


def main():
    parser = argparse.ArgumentParser(
        description='Genera HTML con embeds de Bandcamp, YouTube y SoundCloud desde FreshRSS (VERSIÓN CORREGIDA)'
    )

    # Opciones de conexión
    parser.add_argument('--interactive', action='store_true',
                       help='Modo interactivo para configurar la conexión')
    parser.add_argument('--server', help='URL del servidor FreshRSS (ej: https://rss.example.com)')
    parser.add_argument('--username', help='Usuario de FreshRSS')
    parser.add_argument('--password', help='Contraseña (no recomendado, usa --interactive)')

    # Opciones de operación
    parser.add_argument('--list-feeds', action='store_true',
                       help='Listar todos los feeds disponibles y salir')
    parser.add_argument('--list-categories', action='store_true',
                       help='Listar todas las categorías disponibles y salir')
    parser.add_argument('--feeds', nargs='+',
                       help='IDs de feeds a procesar (ej: feed/123 feed/456)')
    parser.add_argument('--categories', nargs='+',
                       help='Nombres de categorías a procesar')
    parser.add_argument('--unread-only', action='store_true',
                       help='Solo procesar artículos no leídos')
    parser.add_argument('--max-articles', type=int, default=100,
                       help='Número máximo de artículos a obtener por feed/categoría (default: 100)')

    # Opciones de salida
    parser.add_argument('--output-dir', default='freshrss_embeds',
                       help='Directorio de salida para los archivos HTML (default: freshrss_embeds)')
    parser.add_argument('--items-per-page', type=int, default=8,
                       help='Número de embeds por página (default: 8)')
    parser.add_argument('--max-pages-buttons', type=int, default=15,
                       help='Número máximo de botones de páginas a mostrar (default: 15)')

    args = parser.parse_args()

    # Configurar conexión a FreshRSS
    if args.interactive:
        config = interactive_setup()
    elif args.server and args.username:
        password = args.password
        if not password:
            password = getpass.getpass(f"Contraseña para {args.username}: ")
        config = FreshRSSConfig(args.server, args.username, password)
    else:
        print("❌ Debes usar --interactive o proporcionar --server y --username")
        print("Usa --help para ver ejemplos de uso")
        return

    # Crear cliente y autenticar
    client = FreshRSSClient(config)
    if not client.authenticate():
        print("\n❌ No se pudo autenticar con FreshRSS")
        return

    try:
        # Listar feeds si se solicita
        if args.list_feeds:
            print("\n" + "="*80)
            print("📡 FEEDS DISPONIBLES")
            print("="*80 + "\n")
            feeds = client.get_feeds()

            for i, feed in enumerate(feeds, 1):
                categories = ', '.join(feed['categories']) if feed['categories'] else 'Sin categoría'
                print(f"  {i}. {feed['title']}")
                print(f"     ID: {feed['id']}")
                print(f"     Categorías: {categories}\n")

            print(f"📊 Total: {len(feeds)} feeds")
            print("\nUsa estos IDs con --feeds")
            return

        # Listar categorías si se solicita
        if args.list_categories:
            print("\n" + "="*80)
            print("📁 CATEGORÍAS DISPONIBLES")
            print("="*80 + "\n")
            categories = client.get_categories()

            for i, category in enumerate(categories, 1):
                print(f"  {i}. {category}")

            print(f"\n📊 Total: {len(categories)} categorías")
            print("\nUsa estos nombres con --categories")
            return

        # Verificar que se especificaron feeds o categorías
        if not args.feeds and not args.categories:
            print("\n❌ Debes especificar feeds con --feeds o categorías con --categories")
            print("   O usa --list-feeds / --list-categories para ver las opciones disponibles")
            return

        # Crear directorio de salida
        os.makedirs(args.output_dir, exist_ok=True)

        print(f"\n{'='*80}")
        print(f"📡 PROCESANDO FEEDS/CATEGORÍAS")
        print(f"{'='*80}")
        print(f"Servidor: {config.server_url}")
        print(f"Usuario: {config.username}")
        print(f"Solo no leídos: {'Sí' if args.unread_only else 'No'}")
        print(f"Máx. artículos: {args.max_articles}")
        print(f"{'='*80}\n")

        all_results = []

        # Procesar feeds individuales
        if args.feeds:
            # Obtener nombres de los feeds
            feeds_list = client.get_feeds()
            feeds_dict = {feed['id']: feed['title'] for feed in feeds_list}

            for feed_id in args.feeds:
                feed_name = feeds_dict.get(feed_id, feed_id)
                embeds = process_feed(
                    client, feed_id, feed_name,
                    unread_only=args.unread_only,
                    max_articles=args.max_articles
                )

                total = len(embeds['bandcamp']) + len(embeds['youtube']) + len(embeds['soundcloud'])
                if total > 0:
                    all_results.append((feed_name, embeds))

        # Procesar categorías
        if args.categories:
            for category in args.categories:
                embeds = process_category(
                    client, category,
                    unread_only=args.unread_only,
                    max_articles=args.max_articles
                )

                total = len(embeds['bandcamp']) + len(embeds['youtube']) + len(embeds['soundcloud'])
                if total > 0:
                    all_results.append((category, embeds))

        # Generar archivos HTML
        if all_results:
            print(f"\n{'='*80}")
            print(f"📝 GENERANDO ARCHIVOS HTML")
            print(f"{'='*80}\n")

            for name, embeds in all_results:
                print(f"  Generando {name}...")
                filename = generate_feed_html(name, embeds, args.output_dir, args.items_per_page, args.max_pages_buttons)
                total = len(embeds['bandcamp']) + len(embeds['youtube']) + len(embeds['soundcloud'])
                print(f"  Total: {total} embeds\n")

            print(f"{'='*80}")
            print(f"✅ Archivos HTML generados en: {args.output_dir}")
            print(f"{'='*80}\n")
            print("🔧 CORRECCIONES APLICADAS:")
            print("   ✓ YouTube ahora usa youtube-nocookie.com")
            print("   ✓ Bandcamp usa dimensiones correctas (350x470)")
            print("   ✓ Parámetros de embed corregidos")
        else:
            print("\n⚠ No se encontraron enlaces en los feeds/categorías especificados")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
