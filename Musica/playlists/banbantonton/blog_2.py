#!/usr/bin/env python
#
# Script Name: blog_2.py
# Description: Extraer música de una URL (YouTube, Bandcamp, SoundCloud)
# Author: volteret4 - modificado por ChatGPT
# Repository: https://github.com/volteret4/
# License:
# Dependencies: python3, requests
#
# Fuentes:
# - Documentación de Python (sys, os, datetime, re): https://docs.python.org/3/
# - Requests: https://docs.python-requests.org/en/latest/
#

import sys
import re
import os
import requests
from urllib.parse import urlparse, parse_qs
import datetime

def extract_bandcamp_id(url):
    """Extrae el ID de álbum/track de Bandcamp desde un iframe."""
    album_match = re.search(r'album=(\d+)', url)
    track_match = re.search(r'track=(\d+)', url)
    
    if album_match:
        return f"https://bandcamp.com/album/{album_match.group(1)}"
    elif track_match:
        return f"https://bandcamp.com/track/{track_match.group(1)}"
    return url

def clean_youtube_url(url):
    """Normaliza la URL de YouTube para obtener el formato watch?v=."""
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

def extract_music_urls(url):
    """
    Extrae las URLs de música (Bandcamp, SoundCloud, YouTube) del contenido HTML de la URL dada.
    """
    try:
        response = requests.get(url)
        content = response.text

        music_patterns = [
            r'src="(//bandcamp\.com/EmbeddedPlayer/[^"]+)"',
            r'(https?://(?:www\.)?soundcloud\.com/[^\s"\'<>]+)',
            r'(https?://(?:www\.)?youtube\.com/embed/[^\s"\'<>]+)',
            r'(https?://(?:www\.)?youtube\.com/watch\?[^\s"\'<>]+)',
            r'(https?://(?:www\.)?youtu\.be/[^\s"\'<>]+)'
        ]

        music_urls = set()
        for pattern in music_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                extracted_url = match[0] if isinstance(match, tuple) else match
                if 'bandcamp.com' in extracted_url:
                    if extracted_url.startswith('//'):
                        extracted_url = 'https:' + extracted_url
                    extracted_url = extract_bandcamp_id(extracted_url)
                else:
                    extracted_url = clean_youtube_url(extracted_url)
                music_urls.add(extracted_url)

        return list(music_urls)

    except Exception as e:
        print(f"Error al extraer URLs: {e}")
        return []

def create_playlist(music_urls, output_path):
    """
    Crea un archivo de playlist en formato M3U con las URLs proporcionadas.
    """
    try:
        with open(output_path, 'w') as f:
            f.write("#EXTM3U\n")
            for url in music_urls:
                f.write(f"{url}\n")
        return output_path
    except Exception as e:
        print(f"Error al crear playlist: {e}")
        return None

def main():
    if len(sys.argv) < 2:
        print("Uso: python blog_2.py <URL>")
        sys.exit(1)

    url = sys.argv[1]
    bash_script_path = "/home/huan/Scripts/Musica/mpv/vlc_playlist_file.sh"

    temp_dir = os.path.join(os.path.expanduser('~'), '.music_extractor')
    os.makedirs(temp_dir, exist_ok=True)

    # Nombre de la playlist basado en el mes y año actual
    current_month = datetime.datetime.now().strftime("%m-%Y")
    playlist_path = os.path.join(temp_dir, f'{current_month}.m3u')

    print(f"Procesando URL: {url}")
    music_urls = extract_music_urls(url)
    if not music_urls:
        print(f"No se encontraron URLs de música en {url}.")
        sys.exit(1)

    # Crear la playlist con las canciones extraídas
    playlist_file = create_playlist(music_urls, playlist_path)
    if playlist_file:
        print(f"Playlist generada: {playlist_file}")
        print("Todas las URLs encontradas:")
        for music_url in music_urls:
            print(music_url)
        try:
            os.system(f"bash {bash_script_path} {playlist_file}")
        except Exception as e:
            print(f"Error al ejecutar script bash: {e}")

if __name__ == "__main__":
    main()
