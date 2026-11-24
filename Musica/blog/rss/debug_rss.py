#!/usr/bin/env python3
"""
Script de debug para FreshRSS - Ver qué contenido tienen los artículos
"""

import sys
import re
import json
import getpass
import requests

# Copiar las clases del script principal
class FreshRSSConfig:
    def __init__(self, server_url, username, password):
        self.server_url = server_url.rstrip('/')
        self.username = username
        self.password = password
        self.api_url = f"{self.server_url}/api/greader.php"
        self.token = None


class FreshRSSClient:
    def __init__(self, config):
        self.config = config
        self.session = requests.Session()

    def authenticate(self):
        print(f"🔌 Conectando a {self.config.server_url}...")
        auth_url = f"{self.config.api_url}/accounts/ClientLogin"
        auth_data = {
            'Email': self.config.username,
            'Passwd': self.config.password
        }

        try:
            response = self.session.post(auth_url, data=auth_data)
            response.raise_for_status()

            for line in response.text.split('\n'):
                if line.startswith('Auth='):
                    self.config.token = line.split('=', 1)[1]
                    break

            if not self.config.token:
                raise Exception("No se pudo obtener el token")

            print("✓ Autenticación exitosa\n")
            return True

        except requests.exceptions.RequestException as e:
            print(f"✗ Error: {e}")
            return False

    def get_articles(self, feed_id=None, count=5):
        url = f"{self.config.api_url}/reader/api/0/stream/contents"
        headers = {'Authorization': f'GoogleLogin auth={self.config.token}'}
        params = {'n': count, 'output': 'json'}

        if feed_id:
            params['s'] = feed_id
        else:
            params['s'] = 'user/-/state/com.google/reading-list'

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
            print(f"✗ Error: {e}")
            return []


def extract_urls(text):
    """Busca URLs de Bandcamp, YouTube y SoundCloud"""
    results = {
        'bandcamp': [],
        'youtube': [],
        'soundcloud': []
    }

    # Bandcamp
    bc_patterns = [
        r'https?://[a-zA-Z0-9-]+\.bandcamp\.com/(?:album|track)/[a-zA-Z0-9-]+',
    ]
    for pattern in bc_patterns:
        results['bandcamp'].extend(re.findall(pattern, text))

    # YouTube
    yt_patterns = [
        r'https?://(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
        r'https?://(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        r'https?://youtu\.be/([a-zA-Z0-9_-]{11})',
    ]
    for pattern in yt_patterns:
        results['youtube'].extend(re.findall(pattern, text))

    # SoundCloud
    sc_patterns = [
        r'https?://soundcloud\.com/[a-zA-Z0-9-_]+/[a-zA-Z0-9-_]+',
    ]
    for pattern in sc_patterns:
        results['soundcloud'].extend(re.findall(pattern, text))

    return results


def main():
    print("\n" + "="*80)
    print("🔍 DEBUG FRESHRSS - Ver contenido de artículos")
    print("="*80 + "\n")

    server = input("URL del servidor (ej: https://rss.pollete.duckdns.org): ").strip()
    username = input("Usuario: ").strip()
    password = getpass.getpass("Contraseña: ")
    feed_id = input("Feed ID (ej: feed/123) o Enter para todos: ").strip() or None

    config = FreshRSSConfig(server, username, password)
    client = FreshRSSClient(config)

    if not client.authenticate():
        print("\n✗ No se pudo autenticar")
        return

    print(f"\n{'='*80}")
    print(f"📥 Obteniendo primeros 5 artículos...")
    print(f"{'='*80}\n")

    articles = client.get_articles(feed_id=feed_id, count=5)

    if not articles:
        print("✗ No se obtuvieron artículos")
        return

    print(f"✓ Obtenidos {len(articles)} artículos\n")

    for i, article in enumerate(articles, 1):
        print(f"\n{'='*80}")
        print(f"📄 ARTÍCULO {i}/{len(articles)}")
        print(f"{'='*80}")
        print(f"Título: {article['title']}")
        print(f"Feed: {article['feed_title']}")
        print(f"Link: {article['link']}")
        print(f"Autor: {article['author']}")
        print(f"\n--- CONTENIDO (primeros 500 chars) ---")
        print(article['content'][:500])
        print("...")

        # Buscar URLs
        search_text = article['content'] + ' ' + article['link']
        urls = extract_urls(search_text)

        print(f"\n--- URLS ENCONTRADAS ---")
        total = sum(len(v) for v in urls.values())
        if total == 0:
            print("⚠️  No se encontraron URLs de Bandcamp, YouTube o SoundCloud")
        else:
            if urls['bandcamp']:
                print(f"🎵 Bandcamp: {len(urls['bandcamp'])}")
                for url in urls['bandcamp']:
                    print(f"   • {url}")
            if urls['youtube']:
                print(f"📺 YouTube: {len(urls['youtube'])}")
                for vid_id in urls['youtube']:
                    print(f"   • https://youtube.com/watch?v={vid_id}")
            if urls['soundcloud']:
                print(f"🔊 SoundCloud: {len(urls['soundcloud'])}")
                for url in urls['soundcloud']:
                    print(f"   • {url}")

    print(f"\n{'='*80}")
    print("✅ DEBUG COMPLETADO")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    main()
