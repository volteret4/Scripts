import os
import sys
import json
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk  # Necesitamos añadir esta importación
import subprocess
import platform
import re
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen import File 
import sqlite3
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, List, Dict
import discogs_client
import time
import musicbrainzngs as mb
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import wikipedia
import requests

# Cargar las variables de entorno desde el archivo .env
load_dotenv()

# Configuración
MUSIC_LIBRARY_DB = "/home/huan/Scripts/.content/musica.db"
#MUSIC_LIBRARY_DB = "/home/huan/Música/flac/musica.db"
RATE_LIMIT_DELAY = 0.2
LASTFM_API_KEY = os.getenv('LASTFM_API_KEY')
RUTA_LIBRERIA = "/mnt/NFS/moode/moode"
#RUTA_LIBRERIA = "/mnt/NFS/moode/moode/I/"

@dataclass
class Album:
    artist: str
    album: str
    date: str
    label: str
    path: str
    discs: List[str]
    last_modified: float

@dataclass
class DiscogsMetadata:
    artist_id: int
    album_id: int
    genres: List[str]
    styles: List[str]
    country: str
    year: str
    personnel: List[Dict[str, str]]
    labels: List[str]
    format: str
    credits: List[Dict[str, str]]
def update_descriptions(db, artist_name, album_path):
    """Actualizar todas las descripciones disponibles para un artista y álbum."""
    # Inicializar clientes
    lastfm_client = LastFMClient(LASTFM_API_KEY)
    wiki_client = WikipediaClient()
    allmusic_client = AllMusicClient()
    
    # Obtener información del artista
    artist_lastfm = lastfm_client.get_artist_info(artist_name)
    if artist_lastfm:
        db.update_artist_description(artist_name, 'lastfm', artist_lastfm)
        time.sleep(RATE_LIMIT_DELAY)
    
    artist_wiki = wiki_client.get_artist_info(artist_name)
    if artist_wiki:
        db.update_artist_description(artist_name, 'wikipedia', artist_wiki)
        time.sleep(RATE_LIMIT_DELAY)
    
    artist_allmusic = allmusic_client.get_artist_info(artist_name)
    if artist_allmusic:
        db.update_artist_description(artist_name, 'allmusic', artist_allmusic)
        time.sleep(RATE_LIMIT_DELAY)
    
    # Obtener información del álbum si tenemos la ruta
    if album_path:
        album_name = os.path.basename(os.path.dirname(album_path))
        
        album_lastfm = lastfm_client.get_album_info(artist_name, album_name)
        if album_lastfm:
            db.update_album_description(album_path, 'lastfm', album_lastfm)
            time.sleep(RATE_LIMIT_DELAY)
        
        album_wiki = wiki_client.get_album_info(artist_name, album_name)
        if album_wiki:
            db.update_album_description(album_path, 'wikipedia', album_wiki)
            time.sleep(RATE_LIMIT_DELAY)
        
        album_allmusic = allmusic_client.get_album_info(artist_name, album_name)
        if album_allmusic:
            db.update_album_description(album_path, 'allmusic', album_allmusic)
            time.sleep(RATE_LIMIT_DELAY)

class WikipediaClient:
    def __init__(self):
        wikipedia.set_lang('es')
    
    def _is_exact_artist_match(self, page_title, artist_name):
        """Verifica si el título de la página coincide exactamente con el nombre del artista."""
        # Normaliza ambas cadenas: convierte a minúsculas y elimina espacios extras
        page_title = ' '.join(page_title.lower().split())
        artist_name = ' '.join(artist_name.lower().split())
        
        # Lista de palabras comunes que pueden aparecer en títulos de Wikipedia
        common_suffixes = [
            'musician', 'singer', 'artist', 'band', 
            'músico', 'cantante', 'artista', 'grupo musical'
        ]
        
        # Elimina los sufijos comunes del título de la página
        clean_title = page_title
        for suffix in common_suffixes:
            clean_title = clean_title.replace(f" ({suffix})", "")
            clean_title = clean_title.replace(f" {suffix}", "")
        
        return clean_title == artist_name

    def get_artist_info(self, artist_name):
        """Obtener información del artista desde Wikipedia con coincidencia exacta."""
        try:
            # Buscar más resultados para tener mayor probabilidad de encontrar la coincidencia exacta
            search_results = wikipedia.search(f"{artist_name} musician", results=5)
            
            for result in search_results:
                if self._is_exact_artist_match(result, artist_name):
                    page = wikipedia.page(result, auto_suggest=False)
                    return page.content[:1500]
            
            return None
        except Exception as e:
            print(f"Error getting Wikipedia artist info: {e}")
            return None
    
    def get_album_info(self, artist_name, album_name):
        """Obtener información del álbum desde Wikipedia con validación mejorada."""
        try:
            search_query = f"{artist_name} {album_name} album"
            search_results = wikipedia.search(search_query, results=5)
            
            # Normaliza los nombres para la comparación
            artist_name_norm = ' '.join(artist_name.lower().split())
            album_name_norm = ' '.join(album_name.lower().split())
            
            for result in search_results:
                result_lower = result.lower()
                # Verifica que tanto el nombre del artista como del álbum estén en el título
                if (artist_name_norm in result_lower and 
                    album_name_norm in result_lower and 
                    'album' in result_lower):
                    page = wikipedia.page(result, auto_suggest=False)
                    return page.content[:1500]
            
            return None
        except Exception as e:
            print(f"Error getting Wikipedia album info: {e}")
            return None

class AllMusicClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def _search_url(self, query):
        """Genera URL de búsqueda para AllMusic."""
        return f"https://www.allmusic.com/search/all/{query.replace(' ', '%20')}"
    
    def get_artist_info(self, artist_name):
        """Obtener información del artista desde AllMusic."""
        try:
            # Buscar artista
            search_url = self._search_url(artist_name)
            response = self.session.get(search_url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Buscar primer resultado de artista
            artist_link = soup.find('div', class_='artist')
            if artist_link and artist_link.find('a'):
                artist_url = artist_link.find('a')['href']
                
                # Obtener página del artista
                response = self.session.get(artist_url)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Buscar biografía
                bio = soup.find('div', class_='biography')
                if bio:
                    return bio.get_text().strip()
            return None
        except Exception as e:
            print(f"Error getting AllMusic artist info: {e}")
            return None
    
    def get_album_info(self, artist_name, album_name):
        """Obtener información del álbum desde AllMusic."""
        try:
            # Buscar álbum
            search_url = self._search_url(f"{artist_name} {album_name}")
            response = self.session.get(search_url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Buscar primer resultado de álbum
            album_link = soup.find('div', class_='album')
            if album_link and album_link.find('a'):
                album_url = album_link.find('a')['href']
                
                # Obtener página del álbum
                response = self.session.get(album_url)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Buscar reseña
                review = soup.find('div', class_='review')
                if review:
                    return review.get_text().strip()
            return None
        except Exception as e:
            print(f"Error getting AllMusic album info: {e}")
            return None

class MusicBrainzUpdater:
    def __init__(self):
        self.db = MusicLibraryDB(MUSIC_LIBRARY_DB)
        self.total_albums = 0
        self.current_album = 0
        self.skipped = 0
        self.processed = 0
        self.errors = 0

    def _get_artist_description(self, artist_id: str) -> str:
        """Get artist description from MusicBrainz."""
        try:
            artist_info = mb.get_artist_by_id(artist_id, includes=['url-rels'])
            # MusicBrainz devuelve las relaciones en 'relations', no en 'relation-list'
            for relation in artist_info.get('relations', []):
                if relation.get('type') == 'wikipedia':
                    return relation.get('url', {}).get('resource', '')
            return ''
        except Exception as e:
            print(f"Error getting artist description: {e}")
            return ''

    def _get_release_info(self, release_id: str) -> dict:
        """Get detailed release information."""
        try:
            release_info = mb.get_release_by_id(
                release_id,
                includes=['recordings', 'artists', 'artist-credits', 'work-rels', 
                        'recording-rels', 'artist-rels']
            )
            return release_info
        except Exception as e:
            print(f"Error getting release info: {e}")
            return {}

    def _extract_collaborators(self, release_info: dict) -> list:
        """Extract collaborators and their roles from a release."""
        collaborators = []
        try:
            # Iterar sobre los mediums
            for medium in release_info.get('medium-list', []):
                for track in medium.get('track-list', []):
                    if 'recording' not in track:
                        continue
                        
                    # Las relaciones están en la grabación
                    for relation in track['recording'].get('relation-list', []):
                        if relation.get('type') in ['conductor', 'producer', 'mix', 'recording', 'performing orchestra']:
                            artist = relation.get('artist', {})
                            # Construir la información del colaborador
                            collaborator = {
                                'name': artist.get('name'),
                                'role': relation.get('type'),
                                'date_begin': relation.get('begin', ''),
                                'date_end': relation.get('end', ''),
                                'disambiguation': artist.get('disambiguation', '')
                            }
                            collaborators.append(collaborator)
        except Exception as e:
            print(f"Error extracting collaborators: {e}")
        
        return collaborators

    def _extract_instruments(self, release_info: dict) -> list:
        """Extract instruments used in the release."""
        instruments = set()
        try:
            for medium in release_info.get('medium-list', []):
                for track in medium.get('track-list', []):
                    if 'recording' not in track:
                        continue
                        
                    # Buscar relaciones de tipo instrumento en la grabación
                    recording = track['recording']
                    if 'relation-list' in recording:
                        for relation in recording['relation-list']:
                            if 'type' in relation and relation['type'] == 'instrument':
                                if 'instrument' in relation:
                                    instruments.add(relation['instrument'].get('name', ''))
                                # También buscar en los atributos si existen
                                if 'attributes' in relation:
                                    instruments.update(relation['attributes'])
                                    
        except Exception as e:
            print(f"Error extracting instruments: {e}")
        
        return list(instruments)

    def search_and_update(self, artist: str, album: str, album_path: str):
        self.current_album += 1
        try:
            # Verificar si ya existe en la base de datos
            cursor = self.db.conn.execute("""
                SELECT artist_mbid FROM musicbrainz_metadata WHERE album_path = ?
            """, (album_path,))
            if cursor.fetchone():
                self.skipped += 1
                print(f"[{self.current_album}/{self.total_albums}] Saltando {artist} - {album} (ya existe)")
                return None

            print(f"[{self.current_album}/{self.total_albums}] Buscando {artist} - {album}...")
            
            # Buscar artista
            result = mb.search_artists(artist=artist, limit=1)
            if result['artist-list']:
                artist_data = result['artist-list'][0]
                artist_id = artist_data['id']
                print(f"  ✓ Artista encontrado: {artist_data.get('name')}")
                
                # Obtener descripción del artista
                artist_description = self._get_artist_description(artist_id)
                time.sleep(RATE_LIMIT_DELAY)
                
                # Buscar álbum
                album_result = mb.search_releases(artist=artist, release=album, limit=1)
                release_info = None
                if album_result['release-list']:
                    release_data = album_result['release-list'][0]
                    release_id = release_data['id']
                    print(f"  ✓ Álbum encontrado: {release_data.get('title')}")
                    
                    # Obtener información detallada del release
                    release_info = self._get_release_info(release_id)
                    time.sleep(RATE_LIMIT_DELAY)
                    
                    # Extraer información adicional
                    instruments = self._extract_instruments(release_info)
                    collaborators = self._extract_collaborators(release_info)
                    
                    # Preparar metadata
                    metadata = {
                        'artist_mbid': artist_id,
                        'album_mbid': release_id,
                        'artist_type': artist_data.get('type', 'Unknown'),
                        'artist_country': artist_data.get('country', 'Unknown'),
                        'artist_begin': artist_data.get('life-span', {}).get('begin', 'Unknown'),
                        'artist_end': artist_data.get('life-span', {}).get('ended', 'No'),
                        'artist_tags': ','.join([t['name'] for t in artist_data.get('tag-list', [])]),
                        'artist_description': artist_description,
                        'album_info': release_info.get('annotation', ''),
                        'instruments': ','.join(instruments),
                        'collaborators': json.dumps(collaborators)
                    }
                    
                    # Actualizar base de datos
                    self.db.conn.execute("""
                        INSERT OR REPLACE INTO musicbrainz_metadata 
                        (album_path, artist_mbid, album_mbid, artist_type, artist_country, 
                        artist_begin, artist_end, artist_tags, artist_description, 
                        album_info, instruments, collaborators)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (album_path, metadata['artist_mbid'], metadata['album_mbid'],
                        metadata['artist_type'], metadata['artist_country'],
                        metadata['artist_begin'], metadata['artist_end'],
                        metadata['artist_tags'], metadata['artist_description'],
                        metadata['album_info'], metadata['instruments'],
                        metadata['collaborators']))
                    self.db.conn.commit()
                    
                    self.processed += 1
                    return metadata
                else:
                    print(f"  ✗ Álbum no encontrado")
                    self.errors += 1
            else:
                print(f"  ✗ Artista no encontrado")
                self.errors += 1
            return None
        except Exception as e:
            self.errors += 1
            print(f"  ✗ Error en MusicBrainz para {artist} - {album}: {e}")
            return None

class LastFMClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.session = requests.Session()
        self.base_url = "http://ws.audioscrobbler.com/2.0/"
    
    def get_artist_info(self, artist_name):
        params = {
            'method': 'artist.getinfo',
            'artist': artist_name,
            'api_key': self.api_key,
            'format': 'json',
            'lang': 'es'  # Preferimos descripción en español
        }
        
        try:
            response = self.session.get(self.base_url, params=params)
            data = response.json()
            if 'artist' in data:
                return data['artist'].get('bio', {}).get('content', '')
            return None
        except Exception as e:
            print(f"Error getting Last.fm artist info: {e}")
            return None
    
    def get_album_info(self, artist_name, album_name):
        params = {
            'method': 'album.getinfo',
            'artist': artist_name,
            'album': album_name,
            'api_key': self.api_key,
            'format': 'json',
            'lang': 'es'  # Preferimos descripción en español
        }
        
        try:
            response = self.session.get(self.base_url, params=params)
            data = response.json()
            if 'album' in data:
                return data['album'].get('wiki', {}).get('content', '')
            return None
        except Exception as e:
            print(f"Error getting Last.fm album info: {e}")
            return None


class MusicLibraryDB:
    def __init__(self, MUSIC_LIBRARY_DB: str):
        self.conn = sqlite3.connect(MUSIC_LIBRARY_DB)
        self.create_tables()
    
    def create_tables(self):
        self.conn.executescript('''
            -- Tabla principal de álbumes
            CREATE TABLE IF NOT EXISTS albums (
                path TEXT PRIMARY KEY,
                artist TEXT,
                album TEXT,
                date TEXT,
                label TEXT,
                last_modified REAL
            );
            
            -- Tabla de discos por álbum
            CREATE TABLE IF NOT EXISTS discs (
                album_path TEXT,
                disc_number TEXT,
                FOREIGN KEY(album_path) REFERENCES albums(path),
                PRIMARY KEY(album_path, disc_number)
            );
            
            -- Tabla de metadata de MusicBrainz
            CREATE TABLE IF NOT EXISTS musicbrainz_metadata (
                album_path TEXT PRIMARY KEY,
                artist_mbid TEXT,
                album_mbid TEXT,
                artist_type TEXT,
                artist_country TEXT,
                artist_begin TEXT,
                artist_end TEXT,
                artist_tags TEXT,
                artist_description TEXT,
                album_info TEXT,
                instruments TEXT,
                collaborators TEXT,
                FOREIGN KEY(album_path) REFERENCES albums(path)
            );

            -- Tabla principal de metadata de Discogs
            CREATE TABLE IF NOT EXISTS discogs_metadata (
                album_path TEXT PRIMARY KEY,
                artist_id INTEGER,
                album_id INTEGER,
                country TEXT,
                year TEXT,
                format TEXT,
                FOREIGN KEY(album_path) REFERENCES albums(path)
            );

            -- Tabla de géneros
            CREATE TABLE IF NOT EXISTS genres (
                album_path TEXT,
                genre TEXT,
                FOREIGN KEY(album_path) REFERENCES albums(path),
                PRIMARY KEY(album_path, genre)
            );

            -- Tabla de estilos
            CREATE TABLE IF NOT EXISTS styles (
                album_path TEXT,
                style TEXT,
                FOREIGN KEY(album_path) REFERENCES albums(path),
                PRIMARY KEY(album_path, style)
            );

            -- Tabla de personal
            CREATE TABLE IF NOT EXISTS personnel (
                album_path TEXT,
                name TEXT,
                role TEXT,
                FOREIGN KEY(album_path) REFERENCES albums(path),
                PRIMARY KEY(album_path, name, role)
            );

            -- Tabla de créditos
            CREATE TABLE IF NOT EXISTS credits (
                album_path TEXT,
                type TEXT,
                name TEXT,
                FOREIGN KEY(album_path) REFERENCES albums(path),
                PRIMARY KEY(album_path, type, name)
            );

            -- Tabla para descripciones de artistas
            CREATE TABLE IF NOT EXISTS artist_descriptions (
                artist_name TEXT PRIMARY KEY,
                wikipedia_desc TEXT,
                lastfm_desc TEXT,
                allmusic_desc TEXT,
                last_updated TIMESTAMP
            );
            
            -- Tabla para descripciones de álbumes
            CREATE TABLE IF NOT EXISTS album_descriptions (
                album_path TEXT PRIMARY KEY,
                wikipedia_desc TEXT,
                lastfm_desc TEXT,
                allmusic_desc TEXT,
                last_updated TIMESTAMP,
                FOREIGN KEY(album_path) REFERENCES albums(path)
            );
        ''')
        self.conn.commit()


    def update_artist_description(self, artist_name, source, description):
        """Update artist description from a specific source."""
        try:
            self.conn.execute(f"""
                INSERT INTO artist_descriptions (artist_name, {source}_desc, last_updated)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(artist_name) DO UPDATE SET
                    {source}_desc = ?,
                    last_updated = CURRENT_TIMESTAMP
            """, (artist_name, description, description))
            self.conn.commit()
        except Exception as e:
            print(f"Error updating {source} artist description: {e}")
    
    def update_album_description(self, album_path, source, description):
        """Update album description from a specific source."""
        try:
            self.conn.execute(f"""
                INSERT INTO album_descriptions (album_path, {source}_desc, last_updated)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(album_path) DO UPDATE SET
                    {source}_desc = ?,
                    last_updated = CURRENT_TIMESTAMP
            """, (album_path, description, description))
            self.conn.commit()
        except Exception as e:
            print(f"Error updating {source} album description: {e}")
    
    def get_artist_descriptions(self, artist_name):
        """Get all available descriptions for an artist."""
        cursor = self.conn.execute("""
            SELECT wikipedia_desc, lastfm_desc, allmusic_desc, last_updated
            FROM artist_descriptions
            WHERE artist_name = ?
        """, (artist_name,))
        return cursor.fetchone()
    
    def get_album_descriptions(self, album_path):
        """Get all available descriptions for an album."""
        cursor = self.conn.execute("""
            SELECT wikipedia_desc, lastfm_desc, allmusic_desc, last_updated
            FROM album_descriptions
            WHERE album_path = ?
        """, (album_path,))
        return cursor.fetchone()

    def get_all_albums(self) -> List[Dict]:
        cursor = self.conn.execute('''
            SELECT a.*, GROUP_CONCAT(d.disc_number) as discs 
            FROM albums a 
            LEFT JOIN discs d ON a.path = d.album_path 
            GROUP BY a.path
        ''')
        albums = []
        for row in cursor.fetchall():
            album = {
                'artist': row[1],
                'album': row[2],
                'date': row[3],
                'label': row[4],
                'path': row[0],
                'discs': row[6].split(',') if row[6] else []
            }
            albums.append(album)
        return albums

    def search_albums(self, query: str) -> List[Dict]:
        query = f"%{query.lower()}%"
        cursor = self.conn.execute('''
            SELECT a.*, GROUP_CONCAT(d.disc_number) as discs 
            FROM albums a 
            LEFT JOIN discs d ON a.path = d.album_path 
            WHERE LOWER(artist) LIKE ? OR LOWER(album) LIKE ? 
            GROUP BY a.path
        ''', (query, query))
        return [dict(zip(['path', 'artist', 'album', 'date', 'label', '_', 'discs'], row)) 
                for row in cursor.fetchall()]

    def update_album(self, album: Album):
        self.conn.execute('''
            INSERT OR REPLACE INTO albums VALUES (?, ?, ?, ?, ?, ?)
        ''', (album.path, album.artist, album.album, album.date, 
              album.label, album.last_modified))
        
        self.conn.execute("DELETE FROM discs WHERE album_path = ?", (album.path,))
        self.conn.executemany('''
            INSERT INTO discs VALUES (?, ?)
        ''', [(album.path, disc) for disc in album.discs])
        
        self.conn.commit()

    def scan_library(self, force_update=True):
        for root, dirs, files in os.walk(RUTA_LIBRERIA):
            if os.path.basename(root).startswith("Disc "):
                try:
                    flac_files = [f for f in files if f.lower().endswith('.flac')]
                    if not flac_files:
                        continue
                    
                    album_dir = os.path.dirname(root)
                    last_modified = os.path.getmtime(root)
                    
                    # Skip if not forced and already up to date
                    if not force_update:
                        cursor = self.conn.execute(
                            "SELECT last_modified FROM albums WHERE path = ?", 
                            (album_dir,))
                        result = cursor.fetchone()
                        if result and result[0] >= last_modified:
                            continue
                    
                    audio = FLAC(os.path.join(root, flac_files[0]))
                    album = Album(
                        artist=audio.get('artist', ['Unknown'])[0],
                        album=audio.get('album', ['Unknown'])[0],
                        date=audio.get('date', ['Unknown'])[0],
                        label=audio.get('label', ['Unknown'])[0],
                        path=album_dir,
                        discs=[os.path.basename(root).split()[1]],
                        last_modified=last_modified
                    )
                    self.update_album(album)
                    
                except Exception as e:
                    print(f"Error processing {root}: {e}")

    def update_discogs_metadata(self, album_path: str, metadata: DiscogsMetadata):
        try:
            self.conn.execute('''
                INSERT OR REPLACE INTO discogs_metadata VALUES (?, ?, ?, ?, ?, ?)
            ''', (album_path, metadata.artist_id, metadata.album_id, 
                 metadata.country, metadata.year, metadata.format))
            
            # Update genres
            self.conn.execute("DELETE FROM genres WHERE album_path = ?", (album_path,))
            self.conn.executemany('''
                INSERT INTO genres VALUES (?, ?)
            ''', [(album_path, genre) for genre in metadata.genres])
            
            # Update styles
            self.conn.execute("DELETE FROM styles WHERE album_path = ?", (album_path,))
            self.conn.executemany('''
                INSERT INTO styles VALUES (?, ?)
            ''', [(album_path, style) for style in metadata.styles])
            
            # Update personnel
            self.conn.execute("DELETE FROM personnel WHERE album_path = ?", (album_path,))
            self.conn.executemany('''
                INSERT INTO personnel VALUES (?, ?, ?)
            ''', [(album_path, p['name'], p['role']) for p in metadata.personnel])
            
            # Update credits
            self.conn.execute("DELETE FROM credits WHERE album_path = ?", (album_path,))
            self.conn.executemany('''
                INSERT INTO credits VALUES (?, ?, ?)
            ''', [(album_path, c['type'], c['name']) for c in metadata.credits])
            
            self.conn.commit()
            
        except Exception as e:
            print(f"Error updating Discogs metadata for {album_path}: {e}")
            self.conn.rollback()


    def get_discogs_metadata(self, album_path: str) -> Optional[Dict]:
        cursor = self.conn.execute("""
            SELECT d.*, GROUP_CONCAT(g.genre) as genres, GROUP_CONCAT(s.style) as styles
            FROM discogs_metadata d
            LEFT JOIN genres g ON d.album_path = g.album_path
            LEFT JOIN styles s ON d.album_path = s.album_path
            WHERE d.album_path = ?
            GROUP BY d.album_path
        """, (album_path,))
        row = cursor.fetchone()
        if row:
            return {
                'artist_id': row[1],
                'album_id': row[2],
                'country': row[3],
                'year': row[4],
                'format': row[5],
                'genres': row[6].split(',') if row[6] else [],
                'styles': row[7].split(',') if row[7] else []
            }
        return None

    def get_musicbrainz_metadata(self, album_path: str) -> Optional[Dict]:
        """Get MusicBrainz metadata for an album."""
        try:
            cursor = self.conn.execute("""
                SELECT artist_mbid, album_mbid, artist_type, artist_country,
                    artist_begin, artist_end, artist_tags, artist_description,
                    album_info, instruments, collaborators
                FROM musicbrainz_metadata 
                WHERE album_path = ?
            """, (album_path,))
            row = cursor.fetchone()
            if row:
                return {
                    'artist_mbid': row[0],
                    'album_mbid': row[1],
                    'artist_type': row[2] if row[2] else 'Unknown',
                    'artist_country': row[3] if row[3] else 'Unknown',
                    'artist_begin': row[4] if row[4] else 'Unknown',
                    'artist_end': row[5] if row[5] else 'N/A',
                    'artist_tags': row[6].split(',') if row[6] else [],
                    'artist_description': row[7] if row[7] else '',
                    'album_info': row[8] if row[8] else '',
                    'instruments': row[9].split(',') if row[9] else [],
                    'collaborators': json.loads(row[10]) if row[10] else []
                }
            return None
        except Exception as e:
            print(f"Error getting MusicBrainz metadata: {e}")
            return None


class DiscogsUpdater:
    def __init__(self, token: str):
        self.client = discogs_client.Client('MusicLibrary/1.0', user_token=token)
        self.db = MusicLibraryDB(MUSIC_LIBRARY_DB)

    def _extract_personnel(self, release) -> List[Dict[str, str]]:
        """Extract personnel information safely handling missing attributes."""
        personnel = []
        
        try:
            # Extraer de tracklist credits si existen
            if hasattr(release, 'tracklist'):
                for track in release.tracklist:
                    if hasattr(track, 'extraartists'):
                        for artist in track.extraartists:
                            if hasattr(artist, 'name') and hasattr(artist, 'role'):
                                personnel.append({
                                    'name': artist.name,
                                    'role': artist.role
                                })
            
            # Extraer de release credits si existen
            if hasattr(release, 'extraartists'):
                for artist in release.extraartists:
                    if hasattr(artist, 'name') and hasattr(artist, 'role'):
                        personnel.append({
                            'name': artist.name,
                            'role': artist.role
                        })
        except Exception as e:
            print(f"Warning: Error extracting personnel: {e}")
        
        return personnel

    def _extract_credits(self, release) -> List[Dict[str, str]]:
        """Extract credits information safely handling missing attributes."""
        credits = []
        
        try:
            if hasattr(release, 'credits'):
                for credit in release.credits:
                    if hasattr(credit, 'name') and hasattr(credit, 'role'):
                        credits.append({
                            'type': credit.role,
                            'name': credit.name
                        })
        except Exception as e:
            print(f"Warning: Error extracting credits: {e}")
            
        return credits

    def _remove_duplicates(self, items: List[str]) -> List[str]:
        """Remove duplicates while preserving order."""
        seen = set()
        return [x for x in items if not (x.lower() in seen or seen.add(x.lower()))]

    def search_release(self, artist: str, album: str) -> Optional[DiscogsMetadata]:
        """Search for a release in Discogs with better error handling."""
        try:
            results = self.client.search(f"{artist} - {album}", type='release')
            if not results:
                print(f"No Discogs results found for {artist} - {album}")
                return None
            
            release = results[0]
            time.sleep(RATE_LIMIT_DELAY)
            
            # Obtener release completo
            full_release = self.client.release(release.id)
            
            # Extraer y limpiar géneros y estilos
            genres = self._remove_duplicates(getattr(full_release, 'genres', []))
            styles = self._remove_duplicates(getattr(full_release, 'styles', []))
            
            # Extraer datos con manejo seguro de atributos
            metadata = DiscogsMetadata(
                artist_id=full_release.artists[0].id if full_release.artists else 0,
                album_id=full_release.id,
                genres=genres,
                styles=styles,
                country=getattr(full_release, 'country', 'Unknown'),
                year=str(getattr(full_release, 'year', 'Unknown')),
                format=full_release.formats[0]['name'] if full_release.formats else 'Unknown',
                personnel=self._extract_personnel(full_release),
                labels=[l.name for l in full_release.labels] if hasattr(full_release, 'labels') else [],
                credits=self._extract_credits(full_release)
            )
            
            return metadata
            
        except Exception as e:
            print(f"Error en Discogs para {artist} - {album}: {e}")
            return None

    def has_discogs_data(self, album_path: str) -> bool:
        """Check if an album already has Discogs data."""
        try:
            cursor = self.db.conn.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM discogs_metadata 
                    WHERE album_path = ? 
                    AND album_id IS NOT NULL
                )
            """, (album_path,))
            return bool(cursor.fetchone()[0])
        except Exception as e:
            print(f"Error checking Discogs data: {e}")
            return False
    
    def update_library(self):
        cursor = self.db.conn.execute("""
            SELECT artist, album, path 
            FROM albums 
            WHERE path NOT IN (SELECT album_path FROM discogs_metadata)
        """)
        
        for artist, album, path in cursor:
            try:
                metadata = self.search_release(artist, album)
                if metadata:
                    self.db.update_discogs_metadata(path, metadata)
                    print(f"✓ {artist} - {album}")
                else:
                    print(f"✗ No Discogs match: {artist} - {album}")
                time.sleep(RATE_LIMIT_DELAY)
            except Exception as e:
                print(f"Error processing {artist} - {album}: {e}")
                continue


# Define preferred applications (can be customized)
MUSIC_PLAYERS = {
    'Linux': ['deadbeef', 'rhythmbox', 'audacious', 'vlc'],
    'Windows': ['wmplayer', 'musicbee', 'foobar2000'],
    'Darwin': ['iTunes', 'Music']
}

FILE_MANAGERS = {
    'Linux': ['thunar', 'nautilus', 'dolphin', 'pcmanfm'],
    'Windows': ['explorer'],
    'Darwin': ['Finder']
}

def find_available_app(app_list):
    """Find the first available application from the list."""
    for app in app_list:
        try:
            # Check if the application is available in the system path
            subprocess.call([app, '--help'], 
                            stdout=subprocess.DEVNULL, 
                            stderr=subprocess.DEVNULL)
            return app
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    return None

def open_with_default_app(path, is_folder=False):
    """
    Open file or folder using the most appropriate method for the current platform.
    
    :param path: Path to the file or folder to open
    :param is_folder: True if path is a folder, False if it's a file
    """
    system = platform.system()
    
    # Ensure path exists
    if not os.path.exists(path):
        print(f"Path does not exist: {path}")
        return False
    
    try:
        # Platform-specific opening methods
        if system == 'Darwin':  # macOS
            if is_folder:
                subprocess.call(['open', path])
            else:
                subprocess.call(['open', '-a', 'Music', path])
            return True
        
        elif system == 'Windows':
            if is_folder:
                os.startfile(path)
            else:
                # Try to find a default music player
                music_player = find_available_app(MUSIC_PLAYERS['Windows'])
                if music_player:
                    subprocess.Popen([music_player, path])
                else:
                    os.startfile(path)
            return True
        
        elif system == 'Linux':
            # Find appropriate applications
            if is_folder:
                file_manager = find_available_app(FILE_MANAGERS['Linux'])
                if file_manager:
                    subprocess.Popen([file_manager, path])
                else:
                    subprocess.Popen(['xdg-open', path])
            else:
                music_player = find_available_app(MUSIC_PLAYERS['Linux'])
                if music_player:
                    subprocess.Popen([music_player, path])
                else:
                    subprocess.Popen(['xdg-open', path])
            return True
        
        else:
            print(f"Unsupported operating system: {system}")
            return False
    
    except Exception as e:
        print(f"Error opening {path}: {e}")
        return False


    
    # return music_index
class MusicLibrarySearchApp:
    def __init__(self, root):
        self.root = root
        self.db = MusicLibraryDB(MUSIC_LIBRARY_DB)
        self.discogs_updater = DiscogsUpdater('cVyFrzzUgWFORRCZfXErXrHygsUDIaqJNFJBfGgL')
        self.musicbrainz_updater = MusicBrainzUpdater()
        self.root.title("Music Library Search")
        self.root.geometry("1600x800")
        self.root.configure(bg='#14141e')

        # Create main container
        self.main_container = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bg='#14141e')
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left side container
        self.left_container = tk.Frame(self.main_container, bg='#14141e')
        self.main_container.add(self.left_container, width=800)

        # Right side container
        self.right_container = tk.Frame(self.main_container, bg='#14141e')
        self.main_container.add(self.right_container, width=800)

        # Load music library
        self.load_library()

        # Create search frame (in left container)
        self.create_search_frame()

        # Create results listbox (in left container)
        self.create_results_list()

        # Create details frame (in right container)
        self.create_details_frame()

        # Keyboard shortcuts
        self.add_keyboard_shortcuts()

        # Focus on search entry when opening
        self.search_entry.focus_set()

        # Variable para mantener referencia a la imagen
        self.current_photo = None


    def load_library(self):
        """Load the music library from SQLite database."""
        try:
            # Scan for updates if needed
            last_scan = os.path.getmtime(MUSIC_LIBRARY_DB) if os.path.exists(MUSIC_LIBRARY_DB) else 0
            if last_scan < datetime.now().timestamp() - 86400:  # 24 hours
                print("Updating library index...")
                self.db.scan_library()
            
            # Load all albums
            self.library = self.db.get_all_albums()
            self.library.sort(key=lambda x: f"{x['artist'].lower()} - {x['album'].lower()}")
            
        except Exception as e:
            print(f"Error loading library: {e}")
            self.library = []
    
    def update_results(self, event=None):
        """Update search results using SQLite search."""
        query = self.search_entry.get()
        self.result_list.delete(0, tk.END)
        
        if query:
            results = self.db.search_albums(query)
        else:
            results = self.db.get_all_albums()
        
        results.sort(key=lambda x: f"{x['artist'].lower()} - {x['album'].lower()}")
        
        for album in results:
            display = f"{album['artist']} - {album['album']} ({album.get('date', 'No date')})"
            self.result_list.insert(tk.END, display)
   
    def create_search_frame(self):
        """Create search input frame."""
        search_frame = tk.Frame(self.left_container, bg='#14141e')
        search_frame.pack(pady=(0, 10), fill=tk.X)

        # Buttons container
        buttons_frame = tk.Frame(search_frame, bg='#14141e')
        buttons_frame.pack(fill=tk.X, pady=(0, 5))

        # Play button
        play_button = tk.Button(buttons_frame, 
                              text="▶ Reproducir", 
                              command=self.play_selected_album, 
                              bg='#1974D2', 
                              fg='white',
                              width=15)
        play_button.pack(side=tk.LEFT, padx=5)

        # Open Folder button
        open_folder_button = tk.Button(buttons_frame, 
                                     text="📁 Abrir Carpeta", 
                                     command=self.open_selected_folder, 
                                     bg='#f8bd9a', 
                                     fg='black',
                                     width=15)
        open_folder_button.pack(side=tk.LEFT, padx=5)

        # Search entry in its own frame
        search_container = tk.Frame(search_frame, bg='#14141e')
        search_container.pack(fill=tk.X, pady=(5, 0))

        self.search_entry = tk.Entry(search_container, 
                                   bg='#cba6f7', 
                                   fg='black', 
                                   font=('Arial', 12), 
                                   insertbackground='black')
        self.search_entry.pack(fill=tk.X, padx=5)
        
        # Bind events
        self.search_entry.bind("<KeyRelease>", self.update_results)
        self.search_entry.bind("<Return>", self.update_results)
        


    def create_results_list(self):
        """Create results listbox."""
        # Create frame for listbox with scrollbar
        list_frame = tk.Frame(self.left_container, bg='#14141e')
        list_frame.pack(fill=tk.BOTH, expand=True)

        # Scrollbar
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Listbox
        self.result_list = tk.Listbox(list_frame, 
                                    font=('Arial', 12), 
                                    bg='#14141e', 
                                    fg='white',
                                    selectmode=tk.SINGLE,
                                    activestyle='none',
                                    selectbackground='#1974D2',
                                    selectforeground='white')
        self.result_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Configure scrollbar
        scrollbar.config(command=self.result_list.yview)
        self.result_list.config(yscrollcommand=scrollbar.set)
        
        # Bind selection event
        self.result_list.bind("<<ListboxSelect>>", self.on_select)




    def create_details_frame(self):
        """Create frame for details and cover art."""
        # Cover frame
        self.cover_frame = tk.Label(self.right_container, bg='#14141e')
        self.cover_frame.pack(pady=10, padx=10)

        # Create frame for details with scrollbar
        details_container = tk.Frame(self.right_container, bg='#14141e')
        details_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Scrollbar for details
        details_scrollbar = tk.Scrollbar(details_container)
        details_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Details text widget
        self.details_text = tk.Text(details_container,
                                  wrap=tk.WORD,
                                  bg='#14141e',
                                  fg='white',
                                  font=('Arial', 12),
                                  padx=10,
                                  pady=10)
        self.details_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Configure scrollbar
        details_scrollbar.config(command=self.details_text.yview)
        self.details_text.config(yscrollcommand=details_scrollbar.set)

        # Make details text read-only
        self.details_text.config(state=tk.DISABLED)

    def find_cover_image(self, album_path):
        """Find cover image in album directory."""
        try:
            # Primero buscar en el directorio del álbum
            cover_names = ['cover', 'folder', 'front', 'artwork', 'albumart']
            image_extensions = ['.jpg', '.jpeg', '.png']

            # Buscar en el directorio del álbum y en sus subdirectorios inmediatos
            search_paths = [album_path]
            # Añadir subdirectorios que empiecen con "Disc"
            for item in os.listdir(album_path):
                if item.startswith("Disc ") and os.path.isdir(os.path.join(album_path, item)):
                    search_paths.append(os.path.join(album_path, item))

            # Buscar en todas las rutas
            for search_path in search_paths:
                # Primero buscar nombres específicos
                for name in cover_names:
                    for ext in image_extensions:
                        file_path = os.path.join(search_path, name + ext)
                        if os.path.exists(file_path):
                            print(f"Found cover image: {file_path}")  # Debug
                            return file_path

                # Si no se encuentra, buscar cualquier imagen
                for file in os.listdir(search_path):
                    if any(file.lower().endswith(ext) for ext in image_extensions):
                        file_path = os.path.join(search_path, file)
                        print(f"Found generic image: {file_path}")  # Debug
                        return file_path

            print("No cover image found")  # Debug
            return None
        except Exception as e:
            print(f"Error finding cover image: {e}")
            return None

    def display_cover_image(self, image_path):
        """Display cover image in the cover frame."""
        try:
            if image_path and os.path.exists(image_path):
                print(f"Loading image from: {image_path}")  # Debug
                # Cargar y redimensionar la imagen
                image = Image.open(image_path)
                
                # Obtener dimensiones originales
                width, height = image.size
                print(f"Original dimensions: {width}x{height}")  # Debug
                
                # Calcular nueva dimensión manteniendo proporción
                max_size = (500, 500)
                ratio = min(max_size[0]/width, max_size[1]/height)
                new_size = (int(width * ratio), int(height * ratio))
                print(f"New dimensions: {new_size}")  # Debug
                
                # Redimensionar
                image = image.resize(new_size, Image.Resampling.LANCZOS)
                
                # Convertir a PhotoImage
                photo = ImageTk.PhotoImage(image)
                
                # Mantener referencia a la imagen
                self.current_photo = photo
                
                # Mostrar la imagen
                self.cover_frame.configure(image=photo)
                print("Image displayed successfully")  # Debug
            else:
                print(f"Invalid image path: {image_path}")  # Debug
                self.cover_frame.configure(image='')
                self.current_photo = None
        except Exception as e:
            print(f"Error displaying cover image: {e}")
            self.cover_frame.configure(image='')
            self.current_photo = None

    def get_selected_album(self):
        """Get the selected album from the results list."""
        selection = self.result_list.curselection()
        if not selection:
            return None

        # Get the selected item's text
        selected_text = self.result_list.get(selection[0])
        
        # Find the corresponding album
        for album in self.library:
            display_text = f"{album['artist']} - {album['album']} ({album.get('date', 'No date')})"
            if display_text == selected_text:
                return album
        
        return None

    def play_selected_album(self):
        """Play the selected album using the system's default music player."""
        album = self.get_selected_album()
        if album and 'path' in album:
            # Try to open the album's path
            open_with_default_app(album['path'], is_folder=False)

    def open_selected_folder(self):
        """Open the folder of the selected album in the file manager."""
        album = self.get_selected_album()
        if album and 'path' in album:
            # Open the directory containing the album
            folder_path = os.path.dirname(album['path'])
            open_with_default_app(folder_path, is_folder=True)

    def on_select(self, event):
        """Display details of selected album."""
        album = self.get_selected_album()
        if album:
            # Enable text widget for updating
            self.details_text.config(state=tk.NORMAL)
            
            # Clear previous details
            self.details_text.delete(1.0, tk.END)
            
            # Format basic album details
            details = f"""{"="*50}
    ALBUM DETAILS
    {"="*50}

    Artist: {album['artist']}
    Album:  {album['album']}
    Date:   {album.get('date', 'Unknown')}
    Label:  {album.get('label', 'Unknown')}

    Location: {album.get('path', 'Unknown')}

    """
            
            # Add MusicBrainz metadata if available
            mb_data = self.db.get_musicbrainz_metadata(album['path'])
            if mb_data:
                details += f"""{"="*50}
    MUSICBRAINZ INFORMATION
    {"="*50}

    Artist Type:    {mb_data.get('artist_type', 'Unknown')}
    Artist Country: {mb_data.get('artist_country', 'Unknown')}
    Career Start:   {mb_data.get('artist_begin', 'Unknown')}
    Career End:     {mb_data.get('artist_end', 'N/A')}

    Tags: {', '.join(mb_data.get('artist_tags', ['None']))}\n"""

            # Add Discogs metadata if available
            discogs_data = self.db.get_discogs_metadata(album['path'])
            if discogs_data:
                details += f"""\n{"="*50}
    DISCOGS INFORMATION
    {"="*50}

    Country:  {discogs_data.get('country', 'Unknown')}
    Year:     {discogs_data.get('year', 'Unknown')}
    Format:   {discogs_data.get('format', 'Unknown')}

    Genres:   {', '.join(discogs_data.get('genres', ['None']))}
    Styles:   {', '.join(discogs_data.get('styles', ['None']))}\n"""

                # Get personnel information
                cursor = self.db.conn.execute("""
                    SELECT name, role FROM personnel 
                    WHERE album_path = ? 
                    ORDER BY role, name
                """, (album['path'],))
                personnel = cursor.fetchall()
                
                if personnel:
                    details += "\nPERSONNEL:\n"
                    current_role = None
                    for name, role in personnel:
                        if role != current_role:
                            details += f"\n{role}:\n"
                            current_role = role
                        details += f"- {name}\n"

                # Get credits information
                cursor = self.db.conn.execute("""
                    SELECT type, name FROM credits 
                    WHERE album_path = ? 
                    ORDER BY type, name
                """, (album['path'],))
                credits = cursor.fetchall()
                
                if credits:
                    details += "\nCREDITS:\n"
                    current_type = None
                    for credit_type, name in credits:
                        if credit_type != current_type:
                            details += f"\n{credit_type}:\n"
                            current_type = credit_type
                        details += f"- {name}\n"
            
            # Formato básico del álbum...
            
            # Obtener descripciones del artista
            artist_desc = self.db.get_artist_descriptions(album['artist'])
            if artist_desc:
                details += f"""\n{"="*50}
    ARTIST INFORMATION
    {"="*50}\n"""
                if artist_desc[0]:  # Wikipedia
                    details += f"\nWIKIPEDIA:\n{artist_desc[0]}\n"
                if artist_desc[1]:  # Last.fm
                    details += f"\nLAST.FM:\n{artist_desc[1]}\n"
                if artist_desc[2]:  # AllMusic
                    details += f"\nALLMUSIC:\n{artist_desc[2]}\n"
            
            # Obtener descripciones del álbum
            album_desc = self.db.get_album_descriptions(album['path'])
            if album_desc:
                details += f"""\n{"="*50}
    ALBUM INFORMATION
    {"="*50}\n"""
                if album_desc[0]:  # Wikipedia
                    details += f"\nWIKIPEDIA:\n{album_desc[0]}\n"
                if album_desc[1]:  # Last.fm
                    details += f"\nLAST.FM:\n{album_desc[1]}\n"
                if album_desc[2]:  # AllMusic
                    details += f"\nALLMUSIC:\n{album_desc[2]}\n"
            
            # Insert formatted text
            self.details_text.insert(tk.END, details)
            
            # Make text widget read-only again
            self.details_text.config(state=tk.DISABLED)
            
            # Show cover image
            if 'path' in album:
                cover_path = self.find_cover_image(album['path'])
                self.display_cover_image(cover_path)


    def add_keyboard_shortcuts(self):
        """Add keyboard shortcuts."""
        # Atajos existentes
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.root.bind("<Control-f>", lambda e: self.search_entry.focus_set())
        self.root.bind("<Control-o>", lambda e: self.open_selected_folder())
        self.root.bind("<Control-a>", self.select_all)
        
        # Navegación mejorada
        self.search_entry.bind("<Tab>", self.move_focus_to_list)
        self.search_entry.bind("<Return>", self.move_focus_to_list)
        
        # Atajos para el listbox
        self.result_list.bind("<Return>", lambda e: self.play_selected_album())
        self.result_list.bind("<Double-Button-1>", lambda e: self.play_selected_album())
        self.result_list.bind("<space>", lambda e: self.play_selected_album())
        
        # Permitir que las flechas funcionen en el listbox
        self.result_list.bind("<Up>", lambda e: self.on_select(None))
        self.result_list.bind("<Down>", lambda e: self.on_select(None))

    def move_focus_to_list(self, event=None):
        """Move focus to the results list and select first item if available."""
        if self.result_list.size() > 0:
            self.result_list.focus_set()
            self.result_list.selection_clear(0, tk.END)
            self.result_list.selection_set(0)
            self.result_list.see(0)
            self.result_list.event_generate('<<ListboxSelect>>')  # Esto es crucial
            return "break"  # Esto evita que el evento se propague


    def select_all(self, event=None):
        """Select all text in the search entry."""
        self.search_entry.select_range(0, tk.END)
        return "break"


 

def main():
    """Función principal con mejor manejo de metadata"""
    # Configurar MusicBrainz
    mb.set_useragent("MusicLibraryApp", "1.0", "frodobolson@disroot.org")
    
    # Inicializar base de datos
    db = MusicLibraryDB(MUSIC_LIBRARY_DB)
    
    # Realizar escaneo inicial si es necesario
    cursor = db.conn.execute("SELECT COUNT(*) FROM albums")
    if cursor.fetchone()[0] == 0:
        print("Base de datos vacía, realizando escaneo inicial...")
        db.scan_library(force_update=True)
    
    # Verificar y actualizar metadata faltante
    print("\nVerificando metadata...")
    albums = db.get_all_albums()
    total_albums = len(albums)
    
    # Inicializar actualizadores
    discogs_updater = DiscogsUpdater('cVyFrzzUgWFORRCZfXErXrHygsUDIaqJNFJBfGgL')
    mb_updater = MusicBrainzUpdater()
    mb_updater.total_albums = total_albums
    
    for i, album in enumerate(albums, 1):
        print(f"\nProcesando álbum {i}/{total_albums}: {album['artist']} - {album['album']}")
        
        # Verificar y actualizar Discogs
        if not discogs_updater.has_discogs_data(album['path']):
            print("Buscando en Discogs...")
            metadata = discogs_updater.search_release(album['artist'], album['album'])
            if metadata:
                db.update_discogs_metadata(album['path'], metadata)
                print("✓ Metadata de Discogs actualizada")
            time.sleep(RATE_LIMIT_DELAY)
        
        # Verificar y actualizar MusicBrainz
        cursor = db.conn.execute(
            "SELECT 1 FROM musicbrainz_metadata WHERE album_path = ?", 
            (album['path'],)
        )
        if not cursor.fetchone():
            print("Buscando en MusicBrainz...")
            mb_updater.search_and_update(album['artist'], album['album'], album['path'])
            time.sleep(RATE_LIMIT_DELAY)
            
        # Verificar si ya existe descripción para este álbum
        cursor = db.conn.execute(
            "SELECT 1 FROM album_descriptions WHERE album_path = ?",
            (album['path'],)
        )
        if not cursor.fetchone():
            print("Actualizando descripción...")
            update_descriptions(db, album['artist'], album['path'])
    
    print("\nActualización de metadata completada")
    print(f"Total de álbumes procesados: {total_albums}")
    print(f"Errores en MusicBrainz: {mb_updater.errors}")
    
    # Iniciar interfaz gráfica
    root = tk.Tk()
    app = MusicLibrarySearchApp(root)
    root.mainloop()
    
if __name__ == "__main__":
    main()