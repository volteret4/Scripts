#!/usr/bin/env python3

import sys
import re
import os
import requests
from urllib.parse import urlparse, urlunparse, parse_qs

def extract_bandcamp_id(url):
    """Extrae el ID de album/track de Bandcamp desde un iframe"""
    album_match = re.search(r'album=(\d+)', url)
    track_match = re.search(r'track=(\d+)', url)
    
    if album_match:
        return f"https://bandcamp.com/album/{album_match.group(1)}"
    elif track_match:
        return f"https://bandcamp.com/track/{track_match.group(1)}"
    return url

def clean_youtube_url(url):
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
    try:
        response = requests.get(url)
        content = response.text

        music_patterns = [
            r'src="(//bandcamp\.com/EmbeddedPlayer/[^"]+)"',
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
        print(f"Error al extraer URLs: {e}")
        return []

def create_playlist(music_urls, output_path):
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
        print("Uso: python script.py <url> <bash_script_path>")
        sys.exit(1)

    url = sys.argv[1]
    bash_script_path = "/home/huan/Scripts/Musica/mpv/vlc_playlist_file.sh"

    temp_dir = os.path.join(os.path.expanduser('~'), '.music_extractor')
    os.makedirs(temp_dir, exist_ok=True)
    playlist_path = os.path.join(temp_dir, 'playlist.m3u')

    music_urls = extract_music_urls(url)

    if not music_urls:
        print("No se encontraron URLs de música.")
        sys.exit(1)

    playlist_file = create_playlist(music_urls, playlist_path)

    if playlist_file:
        print(f"Playlist generada: {playlist_file}")
        print("URLs encontradas:")
        for url in music_urls:
            print(url)

        try:
            os.system(f"bash {bash_script_path} {playlist_file}")
        except Exception as e:
            print(f"Error al ejecutar script bash: {e}")

if __name__ == "__main__":
    main()
    