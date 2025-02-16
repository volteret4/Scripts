#!/usr/bin/env python
#
# Script Name: blogs_pte.py
# Description: Crear playlists por blog y por mes de los feeds de freshrss.
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# TODO: 
# Notes:
#   Dependencies:  - python3, 
#

import requests
import logging
import os
import re
from typing import List, Dict, Set
from pathlib import Path
from dotenv import load_dotenv
from urllib.parse import quote, urlparse, parse_qs
from datetime import datetime
from collections import defaultdict

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def extract_bandcamp_id(url: str) -> str:
    """Extrae el ID de album/track de Bandcamp desde un iframe"""
    album_match = re.search(r'album=(\d+)', url)
    track_match = re.search(r'track=(\d+)', url)
    
    if album_match:
        return f"https://bandcamp.com/album/{album_match.group(1)}"
    elif track_match:
        return f"https://bandcamp.com/track/{track_match.group(1)}"
    return url

def clean_youtube_url(url: str) -> str:
    parsed_url = urlparse(url)
    if 'youtube.com/embed/' in url:
        video_id = parsed_url.path.split('/')[-1]
        return f'https://youtube.com/watch?v={video_id}'
    if 'youtu.be' in url:
        video_id = parsed_url.path.lstrip('/')
        return f'https://youtube.com/watch?v={video_id}'
    if 'youtube.com/watch' in url:
        parsed_query = parse_qs(parsed_url.query)
        video_id = parsed_query.get('v', [''])[0]
        return f'https://youtube.com/watch?v={video_id}'
    return url

def extract_music_urls(url: str) -> List[str]:
    try:
        response = requests.get(url)
        content = response.text

        music_patterns = [
            r'https://[a-z0-9\-.]+\.bandcamp\.com/(album|track)/[a-z0-9\-_]+' 
            r'(https?://(www\.)?(soundcloud\.com/[^\s"\']+))',
            r'(https?://(www\.)?(youtube\.com/embed/[^\s"\']+))',
            r'(https?://(www\.)?(youtube\.com/watch\?[^\s"\']+))',
            r'(https?://(www\.)?(youtu\.be/[^\s"\']+))'
        ]

        music_urls = set()
        for pattern in music_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                url = match[0] if isinstance(match, tuple) else match
                if 'bandcamp.com' in url:
                    if url.startswith('//'):
                        url = 'https:' + url
                    url = extract_bandcamp_id(url)
                else:
                    url = clean_youtube_url(url)
                music_urls.add(url)

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
                    logger.debug(f"Token obtenido correctamente")
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Error en login: {str(e)}")
            return False
            
    def get_headers(self) -> Dict[str, str]:
        if not self.auth_token:
            raise ValueError("No se ha realizado el login")
            
        return {
            'Authorization': f'GoogleLogin auth={self.auth_token}',
            'User-Agent': 'FreshRSS-Script/1.0'
        }

    def get_feed_subscriptions(self) -> List[Dict]:
        endpoint = f"{self.api_endpoint}/reader/api/0/subscription/list"
        params = {'output': 'json'}
        
        response = requests.get(endpoint, headers=self.get_headers(), params=params)
        response.raise_for_status()
        
        return response.json().get('subscriptions', [])

    def get_blog_feeds(self) -> List[Dict]:
        subscriptions = self.get_feed_subscriptions()
        blog_feeds = []
        
        for feed in subscriptions:
            for category in feed.get('categories', []):
                if category['label'] == 'Blogs':
                    blog_feeds.append(feed)
                    break
                    
        return blog_feeds

    def get_unread_posts(self, feed_id: str) -> List[Dict[str, str]]:
        endpoint = f"{self.api_endpoint}/reader/api/0/stream/contents/{quote(feed_id)}"
        params = {
            'output': 'json',
            'n': 1000,
            'xt': 'user/-/state/com.google/read'
        }
        
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
        
    def process_posts(self, posts: List[Dict[str, str]]):
        """Procesa los posts y crea playlists organizadas por feed y mes"""
        # Organizar posts por feed y luego por mes
        posts_by_feed_and_month = defaultdict(lambda: defaultdict(list))
        
        for post in posts:
            feed_title = post['feed_title']
            month_key = post['month_key']
            posts_by_feed_and_month[feed_title][month_key].append(post)
        
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
                    self.create_m3u_playlist(
                        list(all_music_urls),
                        feed_dir,
                        month_key
                    )

def main():
    # Cargar variables de entorno
    load_dotenv()
    
    # Configuración
    FRESHRSS_URL = "https://freshrss.pollete.duckdns.org"
    USERNAME = "pollo"
    AUTH_TOKEN = os.getenv('AUTH_TOKEN')
    OUTPUT_DIR = "/home/huan/Música/blogs_playlists"
    
    if not AUTH_TOKEN:
        logger.error("No se encontró AUTH_TOKEN en el archivo .env")
        return
    
    reader = FreshRSSReader(FRESHRSS_URL, USERNAME, AUTH_TOKEN)
    playlist_manager = PlaylistManager(OUTPUT_DIR)
    
    try:
        # Login inicial
        if not reader.login():
            logger.error("Error en la autenticación")
            return
            
        # Obtener feeds de la categoría Blogs
        blog_feeds = reader.get_blog_feeds()
        logger.info(f"Encontrados {len(blog_feeds)} feeds en la categoría Blogs")
        
        # Obtener posts no leídos de cada feed
        all_posts = []
        for feed in blog_feeds:
            logger.info(f"Procesando feed: {feed['title']}")
            try:
                posts = reader.get_unread_posts(feed['id'])
                all_posts.extend(posts)
                logger.info(f"  Obtenidos {len(posts)} posts nuevos")
            except Exception as e:
                logger.error(f"Error procesando feed {feed['title']}: {str(e)}")
                continue
        
        # Procesar posts y crear playlists
        playlist_manager.process_posts(all_posts)
        logger.info(f"Proceso completado. Posts totales procesados: {len(all_posts)}")
        
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()