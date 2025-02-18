#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script para recopilar información sobre un artista y su álbum utilizando APIs y scraping.
Se obtienen datos desde:
- Wikipedia (usando el módulo python 'wikipedia')
- Last.fm (API)
- Spotify (usando Spotipy)
- AllMusic (scraping - placeholder)
- WhoSampled (scraping - placeholder)
- Gear: Equipboard o Gearspace (scraping)
- Entrevistas: YouTube y otras revistas (scraping/API)
- Reviews: Resident Advisor, Pitchfork, Rolling Stone y RateYourMusic (scraping)

Fuentes y documentación:
- Wikipedia Python module: https://pypi.org/project/wikipedia/
- Last.fm API: https://www.last.fm/api
- Spotipy: https://spotipy.readthedocs.io/
- Equipboard: https://equipboard.com/ 
- Gearspace: https://gearspace.com/
- YouTube Data API: https://developers.google.com/youtube/v3
- Resident Advisor: https://www.residentadvisor.net/
- Pitchfork: https://pitchfork.com/
- Rolling Stone: https://www.rollingstone.com/
- RateYourMusic: https://rateyourmusic.com/
"""

import requests
import wikipedia
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from bs4 import BeautifulSoup
import datetime
import urllib
import os
from dotenv import load_dotenv

load_dotenv()
# ========================
# Configuración de API keys y credenciales
# ========================


LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# Inicializar Spotipy con Client Credentials
sp_credentials = SpotifyClientCredentials(client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_CLIENT_SECRET)
sp = spotipy.Spotify(client_credentials_manager=sp_credentials)

# ========================
# Funciones para cada fuente
# ========================

def get_wikipedia_data(artist, album, lang="en"):
    """
    Obtiene información completa de Wikipedia para el álbum y, si existe, para el artista usando el enlace en la infobox.
    Se utiliza el módulo python 'wikipedia'.
    """
    data = {}

    wikipedia.set_lang(lang)

    # Primero, se busca la página del álbum (intentando búsqueda exacta combinada)
    album_query = f"{artist} {album}"
    try:
        album_page = wikipedia.page(album_query)
    except Exception as e:
        # Si falla, se busca solo por el nombre del álbum
        try:
            album_page = wikipedia.page(album)
        except Exception as ex:
            data['album'] = {"error": f"No se encontró la página del álbum: {str(ex)}"}
            album_page = None

    if album_page:
        # Extraer contenido completo del álbum
        data['album'] = {
            "title": album_page.title,
            "content": album_page.content,
            "url": album_page.url
        }
        # Intentar obtener el enlace al artista desde la infobox del álbum
        try:
            album_html = album_page.html()
            soup = BeautifulSoup(album_html, 'html.parser')
            infobox = soup.find("table", {"class": "infobox"})
            artist_url = None
            if infobox:
                # Buscar una fila cuyo encabezado contenga "Artist" (o "By")
                artist_th = infobox.find("th", string=lambda text: text and ("Artist" in text or "By" in text))
                if artist_th:
                    artist_td = artist_th.find_next("td")
                    if artist_td:
                        a_tag = artist_td.find("a", href=True)
                        if a_tag:
                            href = a_tag['href']
                            # Si es relativa, la completamos
                            if href.startswith("/wiki/"):
                                artist_url = "https://en.wikipedia.org" + href
            if artist_url:
                # Obtener la página del artista usando la URL (se extrae el título de la URL)
                # Nota: el módulo wikipedia no permite obtener la página directamente desde URL,
                # por lo que se extrae el título y se realiza una búsqueda.
                artist_title = urllib.parse.unquote(artist_url.split("/wiki/")[-1])
                try:
                    artist_page = wikipedia.page(artist_title)
                    data['artist'] = {
                        "title": artist_page.title,
                        "content": artist_page.content,
                        "url": artist_page.url
                    }
                except Exception as e:
                    data['artist'] = {"error": f"No se pudo obtener la página del artista usando el enlace: {str(e)}"}
            else:
                # Si no se encuentra el enlace, se busca por el nombre del artista
                try:
                    artist_page = wikipedia.page(artist)
                    data['artist'] = {
                        "title": artist_page.title,
                        "content": artist_page.content,
                        "url": artist_page.url
                    }
                except Exception as e:
                    data['artist'] = {"error": f"No se encontró la página del artista: {str(e)}"}
        except Exception as e:
            data['artist'] = {"error": f"Error al procesar el HTML del álbum para extraer el artista: {str(e)}"}

    return data

def get_lastfm_data(artist, album):
    """
    Obtiene información de Last.fm para el artista y el álbum.
    Fuente: https://www.last.fm/api
    """
    data = {}
    base_url = "http://ws.audioscrobbler.com/2.0/"
    # Datos del artista
    params_artist = {
        "method": "artist.getInfo",
        "artist": artist,
        "api_key": LASTFM_API_KEY,
        "format": "json"
    }
    try:
        r_artist = requests.get(base_url, params=params_artist)
        if r_artist.status_code == 200:
            data['artist'] = r_artist.json().get("artist", {})
        else:
            data['artist'] = {"error": "Error al obtener datos de Last.fm para el artista."}
    except Exception as e:
        data['artist'] = {"error": f"Excepción en Last.fm (artista): {str(e)}"}

    # Datos del álbum
    params_album = {
        "method": "album.getInfo",
        "artist": artist,
        "album": album,
        "api_key": LASTFM_API_KEY,
        "format": "json"
    }
    try:
        r_album = requests.get(base_url, params=params_album)
        if r_album.status_code == 200:
            data['album'] = r_album.json().get("album", {})
        else:
            data['album'] = {"error": "Error al obtener datos de Last.fm para el álbum."}
    except Exception as e:
        data['album'] = {"error": f"Excepción en Last.fm (álbum): {str(e)}"}

    return data

def get_spotify_data(artist, album):
    """
    Obtiene información de Spotify utilizando Spotipy.
    Fuente: https://spotipy.readthedocs.io/ y https://developer.spotify.com/documentation/web-api/
    """
    data = {}
    try:
        result_artist = sp.search(q=f"artist:{artist}", type="artist", limit=1)
        if result_artist.get("artists", {}).get("items"):
            artist_info = result_artist["artists"]["items"][0]
            data['artist'] = artist_info
        else:
            data['artist'] = {"error": "No se encontró el artista en Spotify."}
    except Exception as e:
        data['artist'] = {"error": f"Excepción al consultar Spotify (artista): {str(e)}"}

    try:
        result_album = sp.search(q=f"album:{album} artist:{artist}", type="album", limit=1)
        if result_album.get("albums", {}).get("items"):
            album_info = result_album["albums"]["items"][0]
            data['album'] = album_info
        else:
            data['album'] = {"error": "No se encontró el álbum en Spotify."}
    except Exception as e:
        data['album'] = {"error": f"Excepción al consultar Spotify (álbum): {str(e)}"}

    return data

def get_allmusic_data(artist, album):
    """
    Obtiene información de AllMusic mediante scraping.
    Fuente: https://www.allmusic.com/
    Nota: Respetar los términos de uso.
    """
    data = {}
    search_url = f"https://www.allmusic.com/search/artists/{artist}"
    try:
        r = requests.get(search_url)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            bio_section = soup.find("div", class_="artist-bio")
            if bio_section:
                data['artist_bio'] = bio_section.get_text(strip=True)
            else:
                data['artist_bio'] = "Biografía no encontrada en AllMusic."
        else:
            data['artist_bio'] = "Error al acceder a AllMusic."
    except Exception as e:
        data['artist_bio'] = f"Excepción al acceder a AllMusic: {str(e)}"
    return data
def get_whosampled_data(album):
    """
    Obtiene información de WhoSampled para un álbum.
    Se construye la URL de búsqueda a partir del nombre del álbum.
    Se utiliza lxml para aplicar los siguientes _xpaths_ en cada track (ejemplo para el primer track):
      - Título de la canción: /html/body/div/main/div[3]/div/div[1]/section[1]/section[1]/header/h3/a/span
      - Tipo de conexión: /html/body/div/main/div[3]/div/div[1]/section[1]/section[1]/div/div/span
      - Detalle de conexión (sample, remix, etc.): de cada <li>, se extrae el primer <a>
    Se itera sobre cada track encontrado en la página.
    """
    data = {}
    # Construir la URL de búsqueda; se URL-encode el nombre del álbum
    query = urllib.parse.quote(album)
    search_url = f"https://www.whosampled.com/search/?q={query}"

    try:
        r = requests.get(search_url)
        if r.status_code == 200:
            tree = html.fromstring(r.text)
            # Obtener todos los track items (usamos el contenedor de tracks; en este ejemplo asumimos que son secciones con clase "trackItem")
            track_elements = tree.xpath('//section[contains(@class, "trackItem")]')
            tracks = []
            for track in track_elements:
                # Extraer título de la canción
                title = track.xpath('.//h3[contains(@class, "trackName")]/a/span/text()')
                title = title[0].strip() if title else "N/A"
                # Extraer tipo de conexión (sampled, remixed, etc.)
                connection_type = track.xpath('.//div[contains(@class, "track-connection")]/span[contains(@class, "sampleAction")]/text()')
                connection_type = connection_type[0].strip() if connection_type else "N/A"
                # Extraer detalles de cada conexión: se iteran los <li> dentro de la sección correspondiente
                connection_items = []
                li_items = track.xpath('.//div[contains(@class, "track-connection")]//ul/li')
                for li in li_items:
                    sample_title = li.xpath('.//a[1]/text()')
                    sample_title = sample_title[0].strip() if sample_title else "N/A"
                    # Puedes extraer más datos (por ejemplo, el artista del sample) si es necesario
                    connection_items.append(sample_title)
                tracks.append({
                    "track_title": title,
                    "connection_type": connection_type,
                    "connections": connection_items
                })
            data['tracks'] = tracks
        else:
            data['error'] = f"Error al acceder a WhoSampled: {r.status_code}"
    except Exception as e:
        data['error'] = f"Excepción al acceder a WhoSampled: {str(e)}"
    return data

def get_gear_info(artist, album):
    """
    Obtiene información sobre el gear/instrumentos usados por el artista.
    Se intenta obtener datos desde Equipboard y Gearspace.
    
    Fuentes:
    - Equipboard: https://equipboard.com/
    - Gearspace: https://gearspace.com/
    
    NOTA: Esta función utiliza scraping; es necesario ajustar los selectores
    según la estructura actual de las páginas y respetar sus términos de uso.
    """
    data = {}
    gear_info = {}

    # Ejemplo de scraping en Equipboard (placeholder)
    try:
        url_equipboard = f"https://equipboard.com/search?q={artist}"
        r_eq = requests.get(url_equipboard)
        if r_eq.status_code == 200:
            soup_eq = BeautifulSoup(r_eq.text, 'html.parser')
            # Ajusta los selectores según la estructura real
            items = soup_eq.find_all("div", class_="equip-item")
            gear_items = [item.get_text(strip=True) for item in items]
            gear_info["Equipboard"] = gear_items if gear_items else "No se encontraron datos en Equipboard."
        else:
            gear_info["Equipboard"] = f"Error al acceder a Equipboard: {r_eq.status_code}"
    except Exception as e:
        gear_info["Equipboard"] = f"Excepción al acceder a Equipboard: {str(e)}"

    # Ejemplo de scraping en Gearspace (placeholder)
    try:
        url_gearspace = f"https://gearspace.com/search/?q={artist}"
        r_gs = requests.get(url_gearspace)
        if r_gs.status_code == 200:
            soup_gs = BeautifulSoup(r_gs.text, 'html.parser')
            # Ajusta los selectores según la estructura real
            items = soup_gs.find_all("div", class_="gear-item")
            gear_items = [item.get_text(strip=True) for item in items]
            gear_info["Gearspace"] = gear_items if gear_items else "No se encontraron datos en Gearspace."
        else:
            gear_info["Gearspace"] = f"Error al acceder a Gearspace: {r_gs.status_code}"
    except Exception as e:
        gear_info["Gearspace"] = f"Excepción al acceder a Gearspace: {str(e)}"
        
    data['gear'] = gear_info
    return data

def get_interviews(artist, album):
    """
    Busca entrevistas (video, audio o texto) sobre el artista y el álbum.
    Se utiliza la YouTube Data API para buscar videos de entrevistas.
    Además, se deja un placeholder para entrevistas en revistas.
    
    Fuente YouTube Data API: https://developers.google.com/youtube/v3
    """
    data = {}
    interviews = {}
    # Búsqueda en YouTube
    search_url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": f"{artist} {album} interview",
        "type": "video",
        "maxResults": 5,
        "key": YOUTUBE_API_KEY
    }
    try:
        r = requests.get(search_url, params=params)
        if r.status_code == 200:
            items = r.json().get("items", [])
            youtube_interviews = []
            for item in items:
                video_id = item["id"]["videoId"]
                title = item["snippet"]["title"]
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                youtube_interviews.append({"title": title, "url": video_url})
            interviews["YouTube"] = youtube_interviews if youtube_interviews else "No se encontraron entrevistas en YouTube."
        else:
            interviews["YouTube"] = f"Error en búsqueda de YouTube: {r.status_code}"
    except Exception as e:
        interviews["YouTube"] = f"Excepción en búsqueda de YouTube: {str(e)}"

    # Placeholder para entrevistas en revistas (scraping o APIs específicas)
    interviews["Revistas"] = "Búsqueda de entrevistas en revistas no implementada aún."

    data["interviews"] = interviews
    return data

def get_reviews(artist, album):
    """
    Obtiene reseñas del álbum o artista desde diferentes sitios:
    - Resident Advisor
    - Pitchfork
    - Rolling Stone
    - RateYourMusic
    
    NOTA: Se utiliza scraping; es necesario ajustar los selectores y respetar los términos de uso.
    """
    data = {}
    reviews = {}

    # Resident Advisor (placeholder)
    try:
        ra_url = f"https://www.residentadvisor.net/search?search={artist}+{album}"
        r_ra = requests.get(ra_url)
        if r_ra.status_code == 200:
            soup_ra = BeautifulSoup(r_ra.text, 'html.parser')
            # Ajusta los selectores para extraer la reseña
            reviews["ResidentAdvisor"] = "Información extraída de Resident Advisor (placeholder)"
        else:
            reviews["ResidentAdvisor"] = f"Error al acceder a Resident Advisor: {r_ra.status_code}"
    except Exception as e:
        reviews["ResidentAdvisor"] = f"Excepción: {str(e)}"

    # Pitchfork (placeholder)
    try:
        pitchfork_url = f"https://pitchfork.com/search/?query={artist}+{album}"
        r_pf = requests.get(pitchfork_url)
        if r_pf.status_code == 200:
            soup_pf = BeautifulSoup(r_pf.text, 'html.parser')
            reviews["Pitchfork"] = "Información extraída de Pitchfork (placeholder)"
        else:
            reviews["Pitchfork"] = f"Error al acceder a Pitchfork: {r_pf.status_code}"
    except Exception as e:
        reviews["Pitchfork"] = f"Excepción: {str(e)}"

    # Rolling Stone (placeholder)
    try:
        rolling_url = f"https://www.rollingstone.com/search/?query={artist}+{album}"
        r_rs = requests.get(rolling_url)
        if r_rs.status_code == 200:
            soup_rs = BeautifulSoup(r_rs.text, 'html.parser')
            reviews["RollingStone"] = "Información extraída de Rolling Stone (placeholder)"
        else:
            reviews["RollingStone"] = f"Error al acceder a Rolling Stone: {r_rs.status_code}"
    except Exception as e:
        reviews["RollingStone"] = f"Excepción: {str(e)}"

    # RateYourMusic (placeholder)
    try:
        rym_url = f"https://rateyourmusic.com/search?searchtype=review&searchterm={artist}+{album}"
        r_rym = requests.get(rym_url)
        if r_rym.status_code == 200:
            soup_rym = BeautifulSoup(r_rym.text, 'html.parser')
            reviews["RateYourMusic"] = "Información extraída de RateYourMusic (placeholder)"
        else:
            reviews["RateYourMusic"] = f"Error al acceder a RateYourMusic: {r_rym.status_code}"
    except Exception as e:
        reviews["RateYourMusic"] = f"Excepción: {str(e)}"

    data["reviews"] = reviews
    return data

# ========================
# Función para compilar y generar Markdown
# ========================


def compile_markdown(info, artist, album, output_file="reporte.md"):
    md_lines = []
    md_lines.append(f"# Reporte sobre **{album}** de **{artist}**\n")
    md_lines.append(f"Generado el {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    md_lines.append("---\n")
    
    # Wikipedia - Artista
    md_lines.append("## Wikipedia - Artista\n")
    if info.get("wikipedia", {}).get("artist", {}).get("content"):
        artist_wiki = info["wikipedia"]["artist"]
        md_lines.append(f"**Título:** {artist_wiki.get('title', 'N/A')}\n")
        md_lines.append(f"**Contenido completo:**\n\n{artist_wiki.get('content', 'N/A')}\n")
        md_lines.append(f"**URL:** {artist_wiki.get('url', 'N/A')}\n")
    else:
        md_lines.append("No se encontró información completa de Wikipedia para el artista.\n")
    
    # Wikipedia - Álbum
    md_lines.append("\n## Wikipedia - Álbum\n")
    if info.get("wikipedia", {}).get("album", {}).get("content"):
        album_wiki = info["wikipedia"]["album"]
        md_lines.append(f"**Título:** {album_wiki.get('title', 'N/A')}\n")
        md_lines.append(f"**Contenido completo:**\n\n{album_wiki.get('content', 'N/A')}\n")
        md_lines.append(f"**URL:** {album_wiki.get('url', 'N/A')}\n")
    else:
        md_lines.append("No se encontró información completa de Wikipedia para el álbum.\n")
    
    # WhoSampled
    md_lines.append("\n## WhoSampled\n")
    if info.get("whosampled", {}).get("tracks"):
        for idx, track in enumerate(info["whosampled"]["tracks"], 1):
            md_lines.append(f"### Track {idx}: {track.get('track_title', 'N/A')}\n")
            md_lines.append(f"- **Tipo de conexión:** {track.get('connection_type', 'N/A')}\n")
            if track.get("connections"):
                md_lines.append(f"- **Conexiones:**")
                for conn in track["connections"]:
                    md_lines.append(f"  - {conn}")
            md_lines.append("\n")
    else:
        md_lines.append("No se encontró información de WhoSampled.\n")
    
    # Se pueden añadir las demás secciones (Last.fm, Spotify, etc.)...
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    print(f"Reporte guardado en {output_file}")

# ========================
# Función principal
# ========================

def main():
    artist = input("Ingresa el nombre del artista: ").strip()
    album = input("Ingresa el nombre del álbum: ").strip()

    info = {}

    print("Recopilando información de Wikipedia...")
    info["wikipedia"] = get_wikipedia_data(artist, album)

    print("Recopilando información de Last.fm...")
    info["lastfm"] = get_lastfm_data(artist, album)

    print("Recopilando información de Spotify...")
    info["spotify"] = get_spotify_data(artist, album)

    print("Recopilando información de AllMusic...")
    info["allmusic"] = get_allmusic_data(artist, album)

    print("Recopilando información de WhoSampled...")
    info["whosampled"] = get_whosampled_data(album)

    print("Recopilando información sobre Gear...")
    info["gear"] = get_gear_info(artist, album)

    print("Buscando entrevistas...")
    info["interviews"] = get_interviews(artist, album)

    print("Buscando reviews...")
    info["reviews"] = get_reviews(artist, album)

    compile_markdown(info, artist, album)

if __name__ == "__main__":
    main()
