#!/usr/bin/env python
#
# Script Name: blogs_playlist_generator.py
# Description: Genera playlists a partir de blogs en FreshRSS, extrayendo URLs de YouTube, Bandcamp, etc.
# Author: volteret4 (adaptado)
#
# Notes:
#   Dependencies:  - python3, PyQt6
#                  - mpv
#                  - yt-dlp
#                  - servidor freshrss y categoria blog creada en el.
#

import logging
import os
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import re
import requests
from typing import List, Dict
from urllib.parse import quote
import subprocess
import sys
import argparse
import traceback

# Configuración de logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def clean_youtube_url(url):
    """Limpia y normaliza URLs de YouTube"""
    # Eliminar parámetros innecesarios
    if 'youtube.com/watch' in url:
        video_id = re.search(r'v=([^&]+)', url)
        if video_id:
            return f'https://youtube.com/watch?v={video_id.group(1)}'
    elif 'youtu.be/' in url:
        video_id = url.split('/')[-1].split('?')[0]
        return f'https://youtube.com/watch?v={video_id}'
    elif 'youtube.com/embed/' in url:
        video_id = url.split('/')[-1].split('?')[0]
        return f'https://youtube.com/watch?v={video_id}'
    return url

def extract_bandcamp_id(url):
    """Extrae y normaliza URLs de Bandcamp"""
    # Asegurarse de que la URL es completa
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url.lstrip('/')
    return url

def extract_music_urls(url):
    """
    Extrae las URLs de música (Bandcamp, SoundCloud, YouTube) del contenido HTML de la URL dada.
    """
    try:
        response = requests.get(url)
        content = response.text
        music_patterns = [
            r'(https?://[a-zA-Z0-9-]+\.bandcamp\.com\S*)',
            r'(https?://(?:www\.)?soundcloud\.com/[^\s"\'<>]+)',
            r'(https?://(?:www\.)?youtube\.com/embed/[^\s"\'<>]+)',
            r'(https?://(?:www\.)?youtube\.com/watch\?[^\s"\'<>]+)',
            r'(https?://(?:www\.)?youtu\.be/[^\s"\'<>]+)'
        ]
        music_urls = set()
        
        for pattern in music_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                extracted_url = match
                if 'bandcamp.com' in extracted_url:
                    if extracted_url.startswith('//'):
                        extracted_url = 'https:' + extracted_url
                    extracted_url = extract_bandcamp_id(extracted_url)
                else:
                    extracted_url = clean_youtube_url(extracted_url)
                music_urls.add(extracted_url)
                
        return list(music_urls)
    except Exception as e:
        logger.error(f"Error al extraer URLs: {e}")
        return []

class FreshRSSReader:
    def __init__(self, base_url: str, username: str, api_password: str):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.api_password = api_password
        self.api_endpoint = f"{self.base_url}/api/greader.php"
        self.auth_token = None
        
    def login(self) -> bool:
        """Inicia sesión en la API de FreshRSS"""
        endpoint = f"{self.api_endpoint}/accounts/ClientLogin"
        params = {
            'Email': self.username,
            'Passwd': self.api_password
        }
        
        try:
            response = requests.get(endpoint, params=params)
            response.raise_for_status()
            
            for line in response.text.splitlines():
                if line.startswith('Auth='):
                    self.auth_token = line.replace('Auth=', '').strip()
                    logger.info(f"Token obtenido correctamente")
                    return True
            
            logger.error("No se encontró el token de autenticación")
            return False
        except Exception as e:
            logger.error(f"Error en login: {str(e)}")
            return False
            
    def get_headers(self) -> Dict[str, str]:
        """Obtiene los headers para las peticiones a la API"""
        if not self.auth_token:
            raise ValueError("No se ha realizado el login")
            
        return {
            'Authorization': f'GoogleLogin auth={self.auth_token}',
            'User-Agent': 'FreshRSS-Script/1.0'
        }

    def get_feed_subscriptions(self) -> List[Dict]:
        """Obtiene los feeds subscritos"""
        endpoint = f"{self.api_endpoint}/reader/api/0/subscription/list"
        params = {'output': 'json'}
        
        try:
            response = requests.get(endpoint, headers=self.get_headers(), params=params)
            response.raise_for_status()
            return response.json().get('subscriptions', [])
        except Exception as e:
            logger.error(f"Error obteniendo subscripciones: {str(e)}")
            return []

    def get_blog_feeds(self) -> List[Dict]:
        """Obtiene los feeds de la categoría 'Blogs'"""
        subscriptions = self.get_feed_subscriptions()
        blog_feeds = []
        
        for feed in subscriptions:
            for category in feed.get('categories', []):
                if category['label'] == 'Blogs':
                    blog_feeds.append(feed)
                    break
                    
        return blog_feeds

    def get_unread_posts(self, feed_id: str) -> List[Dict[str, str]]:
        """Obtiene los posts no leídos de un feed"""
        endpoint = f"{self.api_endpoint}/reader/api/0/stream/contents/{quote(feed_id)}"
        params = {
            'output': 'json',
            'n': 1000,
            'xt': 'user/-/state/com.google/read'
        }
        
        try:
            response = requests.get(endpoint, headers=self.get_headers(), params=params)
            response.raise_for_status()
            data = response.json()
            
            posts = []
            for item in data.get('items', []):
                url = None
                if 'canonical' in item and item['canonical']:
                    url = item['canonical'][0]['href']
                elif 'alternate' in item and item['alternate']:
                    url = item['alternate'][0]['href']
                
                if url:
                    published_date = datetime.fromtimestamp(item.get('published', 0))
                    posts.append({
                        'url': url,
                        'date': published_date,
                        'title': item.get('title', 'Sin título'),
                        'month_key': published_date.strftime('%Y-%m'),
                        'feed_title': item.get('origin', {}).get('title', 'Unknown Feed')
                    })
                    
            return posts
        except Exception as e:
            logger.error(f"Error obteniendo posts de {feed_id}: {str(e)}")
            return []

class PlaylistManager:
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def create_m3u_playlist(self, urls: List[str], feed_dir: Path, filename: str):
        """Crea un archivo .m3u con las URLs proporcionadas"""
        # Asegurarse de que existe el directorio del feed
        feed_dir.mkdir(parents=True, exist_ok=True)
        
        playlist_path = feed_dir / f"{filename}.m3u"
        
        with open(playlist_path, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            for url in urls:
                f.write(f"{url}\n")
                
        logger.info(f"Playlist creada: {playlist_path}")
        
        # Extract titles asynchronously
        self.extract_titles_for_playlist(playlist_path)
        return playlist_path
    
    def extract_titles_for_playlist(self, playlist_path: Path):
        """Extrae los títulos de los vídeos/canciones usando yt-dlp"""
        logger.info(f"Extrayendo títulos para: {playlist_path}")
        
        try:
            # Leer URLs del playlist
            with open(playlist_path, 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]

            titles = []
            for url in urls:
                logger.info(f"Extrayendo título de: {url}")
                try:
                    # Usar yt-dlp para obtener el título
                    result = subprocess.run(
                        ['yt-dlp', '--get-title', url],
                        capture_output=True,
                        text=True,
                        check=True,
                        timeout=30  # Añadir timeout para evitar cuelgues
                    )
                    title = result.stdout.strip()
                    if title:
                        titles.append(title)
                        logger.info(f"Título encontrado: {title}")
                except Exception as e:
                    logger.error(f"Error extrayendo título de {url}: {str(e)}")
                    continue

            # Escribir títulos en un archivo .txt
            txt_path = playlist_path.with_suffix('.txt')
            with open(txt_path, 'w', encoding='utf-8') as f:
                for title in titles:
                    f.write(f"{title}\n")

            logger.info(f"Archivo de títulos creado: {txt_path}")
            
        except Exception as e:
            logger.error(f"Error durante la extracción de títulos: {str(e)}")
    
    def process_posts(self, posts: List[Dict[str, str]]):
        """Procesa los posts y crea playlists organizadas por feed y mes"""
        # Organizar posts por feed y luego por mes
        posts_by_feed_and_month = defaultdict(lambda: defaultdict(list))
        
        for post in posts:
            feed_title = post['feed_title']
            month_key = post['month_key']
            posts_by_feed_and_month[feed_title][month_key].append(post)
        
        created_playlists = []
        
        # Procesar cada feed
        for feed_title, months in posts_by_feed_and_month.items():
            # Crear un nombre seguro para el directorio del feed
            safe_feed_name = re.sub(r'[^\w\-_]', '_', feed_title)
            feed_dir = self.output_dir / safe_feed_name
            
            # Procesar cada mes del feed
            for month_key, month_posts in months.items():
                all_music_urls = set()
                for post in month_posts:
                    music_urls = extract_music_urls(post['url'])
                    all_music_urls.update(music_urls)
                
                if all_music_urls:
                    playlist_path = self.create_m3u_playlist(
                        list(all_music_urls),
                        feed_dir,
                        month_key
                    )
                    created_playlists.append(str(playlist_path))
        
        return created_playlists

def main():
    # Parsear argumentos de línea de comandos
    parser = argparse.ArgumentParser(description='Genera playlists de música desde feeds de blogs en FreshRSS')
    parser.add_argument('--url', required=True, help='URL de FreshRSS')
    parser.add_argument('--username', required=True, help='Nombre de usuario de FreshRSS')
    parser.add_argument('--auth_token', required=True, help='Token de API de FreshRSS')
    parser.add_argument('--output_dir', required=True, help='Directorio para guardar las playlists')
    
    args = parser.parse_args()
    
    try:
        # Iniciar proceso
        print(f"Generando playlists desde {args.url}")
        print(f"Guardando en: {args.output_dir}")
        
        # Inicializar objetos
        reader = FreshRSSReader(args.url, args.username, args.auth_token)
        playlist_manager = PlaylistManager(args.output_dir)
        
        # Login
        if not reader.login():
            print("Error en la autenticación")
            return 1
            
        # Obtener feeds
        print("Obteniendo feeds de blogs...")
        blog_feeds = reader.get_blog_feeds()
        print(f"Encontrados {len(blog_feeds)} feeds en la categoría Blogs")
        
        # Procesar posts
        all_posts = []
        for feed in blog_feeds:
            print(f"Procesando feed: {feed['title']}")
            try:
                posts = reader.get_unread_posts(feed['id'])
                all_posts.extend(posts)
                print(f"  Obtenidos {len(posts)} posts nuevos")
            except Exception as e:
                print(f"Error procesando feed {feed['title']}: {str(e)}")
                continue
                
        # Crear playlists
        print("Creando playlists...")
        created_playlists = playlist_manager.process_posts(all_posts)
        
        # Mostrar resultados
        print(f"Proceso completado. Posts totales procesados: {len(all_posts)}")
        print(f"Playlists creadas: {len(created_playlists)}")
        for playlist in created_playlists:
            print(f"  - {playlist}")
            
        return 0
        
    except Exception as e:
        print(f"Error inesperado: {str(e)}")
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())