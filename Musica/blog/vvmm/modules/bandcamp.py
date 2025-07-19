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
            response = requests.head(url, headers=headers, allow_redirects=True, timeout=10)
            if response.status_code == 200:
                return url
        except:
            continue

    return None

def get_search_url(artist, album):
    """Construye la URL de búsqueda correctamente codificada"""
    # CORREGIR: Codificar correctamente los espacios
    search_terms = f"{artist} {album}"
    encoded_terms = quote(search_terms)  # Esto convierte espacios a %20
    return f"https://bandcamp.com/search?q={encoded_terms}&item_type=a"

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

        # CORREGIR: Buscar en resultados con selectores más específicos
        search_results = soup.find_all(['li', 'div'], class_=['searchresult', 'result-item', 'searchresult-album'])

        for result in search_results:
            # Buscar enlaces de álbumes
            album_links = result.find_all('a', href=True)
            for link in album_links:
                href = link.get('href')
                if not href:
                    continue

                # Verificar que es un enlace de álbum de Bandcamp
                if '/album/' in href and 'bandcamp.com' in href:
                    # Obtener el texto completo del enlace y elementos cercanos
                    full_text = ' '.join(link.stripped_strings)

                    # También buscar texto en elementos padre
                    parent_text = ''
                    if link.parent:
                        parent_text = ' '.join(link.parent.stripped_strings)

                    combined_text = f"{full_text} {parent_text}"

                    if is_valid_match(combined_text, artist_name, album_name):
                        album_url = href
                        if not album_url.startswith('http'):
                            album_url = f"https:{album_url}"
                        return album_url

        # NUEVO: Si no se encuentra con búsqueda de álbumes, intentar búsqueda general
        general_search_url = f"https://bandcamp.com/search?q={quote(f'{artist_name} {album_name}')}"
        response = requests.get(general_search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Buscar cualquier enlace que contenga /album/
        all_links = soup.find_all('a', href=True)
        for link in all_links:
            href = link.get('href')
            if '/album/' in href and 'bandcamp.com' in href:
                link_text = link.get_text(strip=True)
                if artist_name.lower() in link_text.lower() or album_name.lower() in link_text.lower():
                    if not href.startswith('http'):
                        href = f"https:{href}"
                    return href

        # Si no se encuentra nada específico, NO devolver URL de búsqueda
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
