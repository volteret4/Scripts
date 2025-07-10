#!/usr/bin/env python

import requests
from bs4 import BeautifulSoup
import sys
import re
from urllib.parse import quote
from time import sleep

def clean_text(text):
    """Limpia el texto de caracteres especiales y espacios extra"""
    return re.sub(r'[^\w\s-]', '', text.lower()).strip()

def try_direct_url(artist_name, album_name):
    """Intenta acceder directamente a la URL del álbum usando el formato común de Bandcamp"""
    # Limpia y formatea los nombres para la URL
    artist_url = clean_text(artist_name).replace(' ', '')
    album_url = clean_text(album_name).replace(' ', '')
    
    potential_urls = [
        f"https://{artist_url}.bandcamp.com/album/{album_url}",
        f"https://{artist_url}.bandcamp.com/album/{album_name.lower().replace(' ', '-')}",
        f"https://{artist_name.lower().replace(' ', '')}.bandcamp.com/album/{album_name.lower().replace(' ', '-')}",
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    for url in potential_urls:
        try:
            response = requests.head(url, headers=headers, allow_redirects=True)
            if response.status_code == 200:
                return url
        except:
            continue
    
    return None

def get_search_url(artist, album):
    """Construye la URL de búsqueda correctamente codificada"""
    search_terms = f"{artist} {album}"
    return f"https://bandcamp.com/search?q={quote(search_terms)}&item_type=a"

def is_valid_match(link_text, artist_name, album_name):
    """Verifica si el enlace es una coincidencia válida"""
    link_text = clean_text(link_text)
    artist_name = clean_text(artist_name)
    album_name = clean_text(album_name)
    
    # Verifica si tanto el artista como el álbum están en el texto del enlace
    has_artist = artist_name in link_text
    has_album = album_name in link_text
    
    return has_artist and has_album

def get_album_info(artist_name, album_name):
    # Primero intenta la URL directa
    direct_url = try_direct_url(artist_name, album_name)
    if direct_url:
        return direct_url
        
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Intenta la búsqueda general
        search_url = get_search_url(artist_name, album_name)
        response = requests.get(search_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Busca en resultados de búsqueda
        search_results = soup.find_all(['li', 'div'], class_=['searchresult', 'result-item'])
        
        for result in search_results:
            # Busca enlaces tanto en .heading como directamente en el resultado
            links = result.find_all('a')
            for link in links:
                if not link.get('href'):
                    continue
                    
                # Obtiene el texto completo del enlace y elementos cercanos
                full_text = ' '.join(link.stripped_strings)
                
                if is_valid_match(full_text, artist_name, album_name):
                    album_url = link.get('href')
                    if album_url:
                        if not album_url.startswith('http'):
                            album_url = f"https:{album_url}"
                        return album_url
        
        # Si no se encuentra nada, intenta una búsqueda más específica
        artist_search = f"https://bandcamp.com/search?q={quote(artist_name)}"
        response = requests.get(artist_search, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Busca enlaces que contengan el nombre del artista
        all_links = soup.find_all('a')
        for link in all_links:
            href = link.get('href', '')
            if artist_name.lower().replace(' ', '') in href and 'bandcamp.com' in href:
                # Si encuentra la página del artista, busca el álbum allí
                artist_page = requests.get(href, headers=headers, timeout=10)
                artist_soup = BeautifulSoup(artist_page.text, 'html.parser')
                album_links = artist_soup.find_all('a')
                
                for album_link in album_links:
                    if album_name.lower() in album_link.text.lower():
                        album_url = album_link.get('href')
                        if album_url:
                            if not album_url.startswith('http'):
                                album_url = f"https:{album_url}"
                            return album_url
        
        return None
        
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        return None

def main():
    if len(sys.argv) != 3:
        print("Uso: python bandcamp.py 'nombre del artista' 'nombre del album'")
        sys.exit(1)

    artist_name = sys.argv[1]
    album_name = sys.argv[2]

    album_link = get_album_info(artist_name, album_name)
    
    if album_link:
        print(album_link)
    else:
        print("error")

if __name__ == "__main__":
    main()