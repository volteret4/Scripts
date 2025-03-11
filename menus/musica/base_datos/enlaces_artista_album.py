#!/usr/bin/env python
#
# Script Name: db_musica_links.py
# Description: Complementa db_musica.py añadiendo enlaces a servicios externos (Spotify, YouTube, MusicBrainz, Discogs, RateYourMusic)
#              para artistas y álbumes en la base de datos musical.
# Author: basado en el trabajo de volteret4
# Dependencies: - python3, sqlite3, dotenv, spotipy, musicbrainzngs, discogs_client, google-api-python-client

import os
import json
import logging
import sqlite3
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv
import argparse

# APIs específicas
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import musicbrainzngs
import discogs_client
from googleapiclient.discovery import build


# Adaptador personalizado para datetime
def adapt_datetime(dt):
    return dt.isoformat()

# Registrar el adaptador
sqlite3.register_adapter(datetime, adapt_datetime)
load_dotenv()

class MusicLinksManager:
    def __init__(self, db_path: str, disabled_services=None, rate_limit=0.5):
        self.db_path = Path(db_path).resolve()
        self.disabled_services = disabled_services or []
        self.rate_limit = rate_limit  # Tiempo en segundos entre solicitudes API
        
        # Logging configuration
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Inicialización de APIs
        self._init_apis()
        
        # Inicialización de base de datos
        self._update_database_schema()
    
    def _init_apis(self):
        """Inicializa las conexiones a las APIs externas"""
        # Spotify
        if 'spotify' not in self.disabled_services:
            try:
                spotify_client_id = os.getenv("SPOTIFY_CLIENT_ID")
                spotify_client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
                
                if spotify_client_id and spotify_client_secret:
                    client_credentials_manager = SpotifyClientCredentials(
                        client_id=spotify_client_id, 
                        client_secret=spotify_client_secret
                    )
                    self.spotify = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
                    self.logger.info("Spotify API initialized successfully")
                else:
                    self.spotify = None
                    self.logger.warning("Spotify API credentials not found")
            except Exception as e:
                self.spotify = None
                self.logger.error(f"Failed to initialize Spotify API: {str(e)}")
        else:
            self.spotify = None
            self.logger.info("Spotify service disabled")
        
        # MusicBrainz
        if 'musicbrainz' not in self.disabled_services:
            try:
                # Configurar el agente de usuario para MusicBrainz
                musicbrainzngs.set_useragent(
                    "Python Music Library Links Manager",
                    "0.1",
                    "https://github.com/volteret4/"
                )
                # Configurar el logger de MusicBrainz para suprimir mensajes informativos
                mb_logger = logging.getLogger("musicbrainzngs")
                mb_logger.setLevel(logging.ERROR)  # Solo mostrar errores, no advertencias o info
                # Crear un manejador que no haga nada con los mensajes
                null_handler = logging.NullHandler()
                mb_logger.addHandler(null_handler)
                # Quitar todos los demás manejadores que pudieran existir
                for handler in mb_logger.handlers[:]:
                    if not isinstance(handler, logging.NullHandler):
                        mb_logger.removeHandler(handler)
                self.logger.info("MusicBrainz API initialized successfully")
            except Exception as e:
                self.logger.error(f"Failed to initialize MusicBrainz API: {str(e)}")
        else:
            self.logger.info("MusicBrainz service disabled")
        
        # Discogs
        if 'discogs' not in self.disabled_services:
            try:
                discogs_token = os.getenv("DISCOGS_TOKEN")
                if discogs_token:
                    self.discogs = discogs_client.Client('MusicLibraryLinksManager/0.1', user_token=discogs_token)
                    self.logger.info("Discogs API initialized successfully")
                else:
                    self.discogs = None
                    self.logger.warning("Discogs API token not found")
            except Exception as e:
                self.discogs = None
                self.logger.error(f"Failed to initialize Discogs API: {str(e)}")
        else:
            self.discogs = None
            self.logger.info("Discogs service disabled")
        
        # YouTube
        if 'youtube' not in self.disabled_services:
            try:
                youtube_api_key = os.getenv("YOUTUBE_API_KEY")
                if youtube_api_key:
                    self.youtube = build('youtube', 'v3', developerKey=youtube_api_key)
                    self.logger.info("YouTube API initialized successfully")
                else:
                    self.youtube = None
                    self.logger.warning("YouTube API key not found")
            except Exception as e:
                self.youtube = None
                self.logger.error(f"Failed to initialize YouTube API: {str(e)}")
        else:
            self.youtube = None
            self.logger.info("YouTube service disabled")
        
        # RateYourMusic no necesita API, pero registramos si está deshabilitado
        if 'rateyourmusic' in self.disabled_services:
            self.rateyourmusic_enabled = False
            self.logger.info("RateYourMusic service disabled")
        else:
            self.rateyourmusic_enabled = True
    
    def _update_database_schema(self):
        """Actualiza el esquema de la base de datos para incluir columnas de enlaces"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Añadir columna MBID a artistas si no existe
        c.execute("PRAGMA table_info(artists)")
        artist_columns = {col[1] for col in c.fetchall()}
        
        if 'mbid' not in artist_columns:
            c.execute("ALTER TABLE artists ADD COLUMN mbid TEXT")
        
        # Añadir columna MBID a álbumes si no existe
        c.execute("PRAGMA table_info(albums)")
        album_columns = {col[1] for col in c.fetchall()}
        
        if 'mbid' not in album_columns:
            c.execute("ALTER TABLE albums ADD COLUMN mbid TEXT")
        
        # Verificar la existencia de la tabla song_links y sus columnas
        c.execute("PRAGMA table_info(song_links)")
        existing_song_link_columns = {col[1] for col in c.fetchall()}
        
        # Si la tabla no existe, crearla con todas las columnas necesarias
        if not existing_song_link_columns:
            c.execute("""
                CREATE TABLE IF NOT EXISTS song_links (
                    id INTEGER PRIMARY KEY,
                    song_id INTEGER,
                    spotify_url TEXT,
                    spotify_id TEXT,
                    youtube_url TEXT,
                    musicbrainz_url TEXT,
                    musicbrainz_recording_id TEXT,
                    lastfm_url TEXT,
                    links_updated TIMESTAMP,
                    FOREIGN KEY(song_id) REFERENCES songs(id)
                )
            """)
        else:
            # Si la tabla existe, añadir columnas faltantes
            columns_to_add = {
                'youtube_url': "ALTER TABLE song_links ADD COLUMN youtube_url TEXT",
                'spotify_url': "ALTER TABLE song_links ADD COLUMN spotify_url TEXT",
                'spotify_id': "ALTER TABLE song_links ADD COLUMN spotify_id TEXT",
                'musicbrainz_url': "ALTER TABLE song_links ADD COLUMN musicbrainz_url TEXT",
                'musicbrainz_recording_id': "ALTER TABLE song_links ADD COLUMN musicbrainz_recording_id TEXT",
                'lastfm_url': "ALTER TABLE song_links ADD COLUMN lastfm_url TEXT",
                'links_updated': "ALTER TABLE song_links ADD COLUMN links_updated TIMESTAMP"
            }
            
            for column, alter_query in columns_to_add.items():
                if column not in existing_song_link_columns:
                    try:
                        c.execute(alter_query)
                    except sqlite3.OperationalError as e:
                        self.logger.warning(f"Could not add column {column}: {e}")
        
        conn.commit()
        conn.close()
        self.logger.info("Database schema updated with new link columns")

    def _check_tables_exist(self):
        """Verifica qué tablas existen en la base de datos"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in c.fetchall()}
        conn.close()
        return tables
    
    def get_table_counts(self):
        """Obtiene el número de registros en cada tabla relevante"""
        counts = {}
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        tables = self._check_tables_exist()
        
        if 'artists' in tables:
            c.execute("SELECT COUNT(*) FROM artists")
            counts['artists'] = c.fetchone()[0]
        
        if 'albums' in tables:
            c.execute("SELECT COUNT(*) FROM albums")
            counts['albums'] = c.fetchone()[0]
        
        if 'tracks' in tables:
            c.execute("SELECT COUNT(*) FROM tracks")
            counts['tracks'] = c.fetchone()[0]
            
        conn.close()
        return counts
  
    def update_links(self, days_threshold=30, force_update=False, recent_only=True, missing_only=False):
        """
        Actualiza los enlaces externos para artistas, álbumes y canciones.
        Prioriza la búsqueda de MBID antes que otros enlaces.
        """
        # Primero actualizar los MBID
        self.update_missing_mbids()
        
        # Resto de la lógica de actualización de enlaces
        conn = sqlite3.connect(self.db_path)
        try:
            self.update_artist_links(days_threshold, force_update, recent_only, missing_only)
            self.update_album_and_track_links(days_threshold, force_update, recent_only, missing_only)
            self.update_song_links(days_threshold, force_update, recent_only, missing_only)
        finally:
            conn.close()

            
    def update_song_links(self, days_threshold=30, force_update=False, recent_only=True, missing_only=False):
        """
        Actualiza los enlaces externos para canciones
        
        Args:
            days_threshold: Umbral de días para filtrar registros
            force_update: Forzar actualización de todos los registros
            recent_only: Si es True, actualiza solo registros recientes; si es False, actualiza los antiguos
            missing_only: Si es True, actualiza solo registros con enlaces faltantes
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Construir consulta base para seleccionar canciones
        if force_update:
            c.execute("SELECT id, title, artist, album FROM songs")
        elif missing_only:
            # Verificar qué columnas existen en la tabla song_links
            c.execute("PRAGMA table_info(song_links)")
            link_columns = {col[1] for col in c.fetchall()}
            
            # Construir condiciones para enlaces faltantes
            missing_conditions = []
            if 'spotify_url' in link_columns:
                missing_conditions.append("song_links.spotify_url IS NULL")
            if 'youtube_url' in link_columns:
                missing_conditions.append("song_links.youtube_url IS NULL")
            if 'musicbrainz_url' in link_columns:
                missing_conditions.append("song_links.musicbrainz_url IS NULL")
            
            # Buscar canciones sin enlaces en song_links
            if missing_conditions:
                query = f"""
                    SELECT songs.id, songs.title, songs.artist, songs.album 
                    FROM songs 
                    LEFT JOIN song_links ON songs.id = song_links.song_id 
                    WHERE song_links.id IS NULL OR ({' OR '.join(missing_conditions)})
                """
                c.execute(query)
            else:
                # Si no hay columnas de enlaces definidas, obtener canciones sin registro en song_links
                c.execute("""
                    SELECT songs.id, songs.title, songs.artist, songs.album 
                    FROM songs 
                    LEFT JOIN song_links ON songs.id = song_links.song_id 
                    WHERE song_links.id IS NULL
                """)
        else:
            # Lógica para seleccionar canciones basada en fecha
            if recent_only:
                c.execute("""
                    SELECT id, title, artist, album 
                    FROM songs 
                    WHERE last_modified > datetime('now', ?)
                """, (f'-{days_threshold} days',))
            else:
                c.execute("""
                    SELECT songs.id, songs.title, songs.artist, songs.album 
                    FROM songs
                    LEFT JOIN song_links ON songs.id = song_links.song_id
                    WHERE song_links.links_updated IS NULL 
                    OR datetime(song_links.links_updated) < datetime('now', ?)
                """, (f'-{days_threshold} days',))
        
        songs = c.fetchall()
        total_songs = len(songs)
        self.logger.info(f"Found {total_songs} songs to update links")
        
        for idx, (song_id, title, artist, album) in enumerate(songs, 1):
            self.logger.info(f"Processing song {idx}/{total_songs}: {title} by {artist}")
            
            # Obtener o crear registro en song_links
            c.execute("SELECT id FROM song_links WHERE song_id = ?", (song_id,))
            song_link_record = c.fetchone()
            
            # Verificar qué servicios están habilitados y qué columnas existen
            c.execute("PRAGMA table_info(song_links)")
            available_columns = {col[1] for col in c.fetchall()}
            
            links = {}
            
            # Solo agregar enlaces si las columnas existen y los servicios están habilitados
            if 'spotify_url' in available_columns and self.spotify:
                links['spotify_url'] = self._get_spotify_track_url(artist, title, album)
            
            if 'spotify_id' in available_columns and self.spotify:
                links['spotify_id'] = self._get_spotify_track_id(artist, title, album) if hasattr(self, '_get_spotify_track_id') else None
            
            if 'youtube_url' in available_columns and self.youtube:
                links['youtube_url'] = self._get_youtube_track_url(artist, title)
            
            if 'musicbrainz_url' in available_columns and 'musicbrainz' not in self.disabled_services:
                links['musicbrainz_url'] = self._get_musicbrainz_recording_url(artist, title, album)
            
            if 'musicbrainz_recording_id' in available_columns and 'musicbrainz' not in self.disabled_services:
                links['musicbrainz_recording_id'] = self._get_musicbrainz_recording_mbid(artist, title, album)
            
            # Agregar timestamp de actualización
            links['links_updated'] = datetime.now()
            
            if song_link_record:
                # Construir la consulta de actualización dinámica basada en las columnas disponibles
                update_fields = ", ".join([f"{key} = ?" for key in links.keys()])
                update_query = f"""
                    UPDATE song_links SET {update_fields}
                    WHERE song_id = ?
                """
                
                # Preparar los valores para la consulta, incluyendo el song_id al final
                update_values = list(links.values())
                update_values.append(song_id)
                
                c.execute(update_query, update_values)
            else:
                # Construir la consulta de inserción dinámica basada en las columnas disponibles
                columns = ['song_id'] + list(links.keys())
                placeholders = ",".join(["?"] * (len(columns)))
                
                insert_query = f"""
                    INSERT INTO song_links (
                        {", ".join(columns)}
                    ) VALUES ({placeholders})
                """
                
                # Preparar los valores para la consulta, incluyendo el song_id al principio
                insert_values = [song_id] + list(links.values())
                
                c.execute(insert_query, insert_values)
            
            conn.commit()
            self._rate_limit_pause()
        
        conn.close()
        self.logger.info(f"Updated links for {total_songs} songs")


    def _name_similarity_score(self, name1, name2):
        """
        Calcula un puntaje de similitud entre dos nombres de pistas
        
        Args:
            name1: Primer nombre de pista
            name2: Segundo nombre de pista
        
        Returns:
            Float entre 0 y 1, donde 1 es coincidencia perfecta
        """
        # Normalizar nombres: quitar caracteres especiales, convertir a minúsculas
        import re
        import difflib
        
        def normalize(name):
            # Eliminar caracteres entre paréntesis y corchetes (remix, versión, etc.)
            name = re.sub(r'\([^)]*\)|\[[^\]]*\]', '', name)
            # Convertir a minúsculas y eliminar caracteres especiales
            name = re.sub(r'[^\w\s]', '', name.lower())
            # Eliminar palabras comunes que no aportan al significado
            common_words = {'the', 'a', 'an', 'feat', 'featuring', 'ft', 'prod', 'by'}
            return ' '.join(word for word in name.split() if word not in common_words).strip()
        
        norm1 = normalize(name1)
        norm2 = normalize(name2)
        
        # Si alguno está vacío después de normalizar, usar los nombres originales
        if not norm1 or not norm2:
            norm1 = name1.lower()
            norm2 = name2.lower()
        
        # Calcular similitud usando difflib
        sequence_matcher = difflib.SequenceMatcher(None, norm1, norm2)
        return sequence_matcher.ratio()

    def update_artist_links(self, days_threshold=30, force_update=False, recent_only=True, missing_only=False):
        """
        Actualiza los enlaces externos para artistas
        
        Args:
            days_threshold: Umbral de días para filtrar registros
            force_update: Forzar actualización de todos los registros
            recent_only: Si es True, actualiza solo registros recientes; si es False, actualiza los antiguos
            missing_only: Si es True, actualiza solo registros con enlaces faltantes
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        if force_update:
            c.execute("SELECT id, name FROM artists")
        elif missing_only:
            # Construir consulta para encontrar artistas con enlaces faltantes
            missing_conditions = []
            if self.spotify:
                missing_conditions.append("spotify_url IS NULL")
            if self.youtube:
                missing_conditions.append("youtube_url IS NULL")
            if 'musicbrainz' not in self.disabled_services:
                missing_conditions.append("musicbrainz_url IS NULL")
            if self.discogs:
                missing_conditions.append("discogs_url IS NULL")
            if self.rateyourmusic_enabled:
                missing_conditions.append("rateyourmusic_url IS NULL")
            
            if missing_conditions:
                query = f"SELECT id, name FROM artists WHERE {' OR '.join(missing_conditions)}"
                c.execute(query)
            else:
                # Si todos los servicios están deshabilitados, no hay nada que actualizar
                c.execute("SELECT id, name FROM artists WHERE 0=1")  # Consulta vacía
        else:
            if recent_only:
                # Filtrar registros recientes (creados/modificados en los últimos X días)
                c.execute("""
                    SELECT id, name FROM artists 
                    WHERE datetime(last_updated) > datetime('now', ?)
                    OR last_updated IS NULL
                """, (f'-{days_threshold} days',))
            else:
                # Filtrar por fecha de actualización de enlaces (antiguos)
                c.execute("""
                    SELECT id, name FROM artists 
                    WHERE links_updated IS NULL 
                    OR datetime(links_updated) < datetime('now', ?)
                """, (f'-{days_threshold} days',))
        
        artists = c.fetchall()
        total_artists = len(artists)
        self.logger.info(f"Found {total_artists} artists to update links")
        
        for idx, (artist_id, artist_name) in enumerate(artists, 1):
            self.logger.info(f"Processing artist {idx}/{total_artists}: {artist_name}")
            
            # Obtener los enlaces actuales para no solicitar API si ya existen
            if missing_only:
                c.execute("""
                    SELECT spotify_url, youtube_url, musicbrainz_url, 
                        discogs_url, rateyourmusic_url 
                    FROM artists WHERE id = ?
                """, (artist_id,))
                current_links = dict(zip(
                    ['spotify_url', 'youtube_url', 'musicbrainz_url', 'discogs_url', 'rateyourmusic_url'], 
                    c.fetchone()
                ))
            else:
                current_links = {
                    'spotify_url': None, 
                    'youtube_url': None, 
                    'musicbrainz_url': None, 
                    'discogs_url': None, 
                    'rateyourmusic_url': None
                }
            
            links = {
                'spotify_url': (self._get_spotify_artist_url(artist_name) if self.spotify and current_links['spotify_url'] is None else current_links['spotify_url']), 
                'youtube_url': (self._get_youtube_artist_url(artist_name) if self.youtube and current_links['youtube_url'] is None else current_links['youtube_url']),
                'musicbrainz_url': (self._get_musicbrainz_artist_url(artist_name) if 'musicbrainz' not in self.disabled_services and current_links['musicbrainz_url'] is None else current_links['musicbrainz_url']),
                'discogs_url': (self._get_discogs_artist_url(artist_name) if self.discogs and current_links['discogs_url'] is None else current_links['discogs_url']),
                'rateyourmusic_url': (self._get_rateyourmusic_artist_url(artist_name) if self.rateyourmusic_enabled and current_links['rateyourmusic_url'] is None else current_links['rateyourmusic_url']),
                'links_updated': datetime.now()
            }
            
            # Actualizar enlaces en la base de datos
            update_query = """
                UPDATE artists SET 
                spotify_url = ?, youtube_url = ?, musicbrainz_url = ?, 
                discogs_url = ?, rateyourmusic_url = ?, links_updated = ?
                WHERE id = ?
            """
            c.execute(update_query, (
                links['spotify_url'], links['youtube_url'], links['musicbrainz_url'],
                links['discogs_url'], links['rateyourmusic_url'], links['links_updated'],
                artist_id
            ))
            
            conn.commit()
            
            # Pausa usando el rate limiter
            self._rate_limit_pause()
        
        conn.close()
        self.logger.info(f"Updated links for {total_artists} artists")
        

    def update_album_and_track_links(self, days_threshold=30, force_update=False, recent_only=True, missing_only=False):
        """
        Actualiza los enlaces externos para álbumes y sus pistas
        
        Args:
            days_threshold: Umbral de días para filtrar registros
            force_update: Forzar actualización de todos los registros
            recent_only: Si es True, actualiza solo registros recientes; si es False, actualiza los antiguos
            missing_only: Si es True, actualiza solo registros con enlaces faltantes
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        tables = self._check_tables_exist()
        has_tracks_table = 'tracks' in tables
        
        if force_update:
            c.execute("""
                SELECT albums.id, albums.name, artists.name 
                FROM albums JOIN artists ON albums.artist_id = artists.id
            """)
        elif missing_only:
            # Construir consulta para encontrar álbumes con enlaces faltantes
            missing_conditions = []
            if self.spotify:
                missing_conditions.append("albums.spotify_url IS NULL")
            if self.youtube:
                missing_conditions.append("albums.youtube_url IS NULL")
            if 'musicbrainz' not in self.disabled_services:
                missing_conditions.append("albums.musicbrainz_url IS NULL")
            if self.discogs:
                missing_conditions.append("albums.discogs_url IS NULL")
            if self.rateyourmusic_enabled:
                missing_conditions.append("albums.rateyourmusic_url IS NULL")
            
            if missing_conditions:
                query = f"""
                    SELECT albums.id, albums.name, artists.name 
                    FROM albums JOIN artists ON albums.artist_id = artists.id
                    WHERE {' OR '.join(missing_conditions)}
                """
                c.execute(query)
            else:
                # Si todos los servicios están deshabilitados, no hay nada que actualizar
                c.execute("SELECT id, name, '' FROM albums WHERE 0=1")  # Consulta vacía
        else:
            if recent_only:
                # Filtrar registros recientes (creados/modificados en los últimos X días)
                c.execute("""
                    SELECT albums.id, albums.name, artists.name 
                    FROM albums JOIN artists ON albums.artist_id = artists.id
                    WHERE datetime(albums.last_updated) > datetime('now', ?)
                    OR albums.last_updated IS NULL
                """, (f'-{days_threshold} days',))
            else:
                # Filtrar por fecha de actualización de enlaces (antiguos)
                c.execute("""
                    SELECT albums.id, albums.name, artists.name 
                    FROM albums JOIN artists ON albums.artist_id = artists.id
                    WHERE albums.links_updated IS NULL 
                    OR datetime(albums.links_updated) < datetime('now', ?)
                """, (f'-{days_threshold} days',))
        
        albums = c.fetchall()
        total_albums = len(albums)
        self.logger.info(f"Found {total_albums} albums to update links")
        
        for idx, (album_id, album_name, artist_name) in enumerate(albums, 1):
            self.logger.info(f"Processing album {idx}/{total_albums}: {album_name} by {artist_name}")
            
            # Obtener los enlaces actuales para no solicitar API si ya existen
            if missing_only:
                c.execute("""
                    SELECT spotify_url, spotify_id, youtube_url, musicbrainz_url, 
                        discogs_url, rateyourmusic_url 
                    FROM albums WHERE id = ?
                """, (album_id,))
                current_links = dict(zip(
                    ['spotify_url', 'spotify_id', 'youtube_url', 'musicbrainz_url', 'discogs_url', 'rateyourmusic_url'], 
                    c.fetchone()
                ))
            else:
                current_links = {
                    'spotify_url': None, 
                    'spotify_id': None,
                    'youtube_url': None, 
                    'musicbrainz_url': None, 
                    'discogs_url': None, 
                    'rateyourmusic_url': None
                }
            
            # Obtener los enlaces del álbum
            album_links = {
                'spotify_url': current_links['spotify_url'],
                'spotify_id': current_links['spotify_id'],
                'youtube_url': (self._get_youtube_album_url(artist_name, album_name) if self.youtube and current_links['youtube_url'] is None else current_links['youtube_url']),
                'musicbrainz_url': (self._get_musicbrainz_album_url(artist_name, album_name) if 'musicbrainz' not in self.disabled_services and current_links['musicbrainz_url'] is None else current_links['musicbrainz_url']),
                'discogs_url': (self._get_discogs_album_url(artist_name, album_name) if self.discogs and current_links['discogs_url'] is None else current_links['discogs_url']),
                'rateyourmusic_url': (self._get_rateyourmusic_album_url(artist_name, album_name) if self.rateyourmusic_enabled and current_links['rateyourmusic_url'] is None else current_links['rateyourmusic_url']),
                'links_updated': datetime.now()
            }
            
            # Obtener información de Spotify para el álbum y sus pistas
            if self.spotify and current_links['spotify_url'] is None:
                spotify_data = self._get_spotify_album_data(artist_name, album_name)
                if spotify_data:
                    album_links['spotify_url'] = spotify_data['album_url']
                    album_links['spotify_id'] = spotify_data['album_id']
                    
                    # Si existe la tabla de tracks, actualizar las pistas
                    if has_tracks_table and spotify_data['tracks']:
                        self._update_track_links(conn, album_id, spotify_data['tracks'], missing_only)
            
            # Actualizar enlaces en la base de datos
            update_query = """
                UPDATE albums SET 
                spotify_url = ?, spotify_id = ?, youtube_url = ?, musicbrainz_url = ?, 
                discogs_url = ?, rateyourmusic_url = ?, links_updated = ?
                WHERE id = ?
            """
            c.execute(update_query, (
                album_links['spotify_url'], album_links['spotify_id'], album_links['youtube_url'], 
                album_links['musicbrainz_url'], album_links['discogs_url'], 
                album_links['rateyourmusic_url'], album_links['links_updated'],
                album_id
            ))
            
            conn.commit()
            
            # Pausa usando el rate limiter
            self._rate_limit_pause()
        
        conn.close()
        self.logger.info(f"Updated links for {total_albums} albums")
    
    def _rate_limit_pause(self):
        """Realiza una pausa según la configuración del rate limiter"""
        time.sleep(self.rate_limit)

    def _update_track_links(self, conn, album_id, spotify_tracks, missing_only=False):
        """
        Actualiza los enlaces de pistas para un álbum específico
        
        Args:
            conn: Conexión a la base de datos
            album_id: ID del álbum
            spotify_tracks: Lista de pistas de Spotify
            missing_only: Si es True, actualiza solo pistas con enlaces faltantes
        """
        c = conn.cursor()
        
        # Obtener todas las pistas del álbum
        if missing_only:
            c.execute("SELECT id, name, number, spotify_url, spotify_id FROM tracks WHERE album_id = ? ORDER BY number", (album_id,))
            db_tracks = c.fetchall()
        else:
            c.execute("SELECT id, name, number FROM tracks WHERE album_id = ? ORDER BY number", (album_id,))
            db_tracks = c.fetchall()
        
        if not db_tracks:
            return
        
        # Mapear nombres de pistas de Spotify con la base de datos
        for db_track in db_tracks:
            if missing_only:
                track_id, track_name, track_number, current_spotify_url, current_spotify_id = db_track
                # Si ya tiene enlaces y estamos en modo missing_only, saltamos
                if current_spotify_url is not None and current_spotify_id is not None:
                    continue
            else:
                track_id, track_name, track_number = db_track
            
            # Intentar encontrar la pista correspondiente en Spotify
            spotify_track = None
            
            # Primero intentar por número de pista
            if 1 <= track_number <= len(spotify_tracks):
                spotify_track = spotify_tracks[track_number - 1]
            else:
                # Si no coincide por número, intentar por nombre
                for sp_track in spotify_tracks:
                    # Comparación simple de nombres
                    if self._similar_names(track_name, sp_track['name']):
                        spotify_track = sp_track
                        break
            
            if spotify_track:
                c.execute("""
                    UPDATE tracks 
                    SET spotify_url = ?, spotify_id = ?
                    WHERE id = ?
                """, (spotify_track['url'], spotify_track['id'], track_id))
    
    def _similar_names(self, name1, name2):
        """Compara si dos nombres son similares (ignorando caso, espacios, etc.)"""
        # Normalizar nombres: convertir a minúsculas, eliminar espacios extras
        n1 = re.sub(r'\s+', ' ', name1.lower().strip())
        n2 = re.sub(r'\s+', ' ', name2.lower().strip())
        
        # Comprobar exactitud
        if n1 == n2:
            return True
        
        # Eliminar caracteres especiales y comparar
        n1_clean = re.sub(r'[^\w\s]', '', n1)
        n2_clean = re.sub(r'[^\w\s]', '', n2)
        
        return n1_clean == n2_clean
    

    def count_missing_mbids(self):
        """
        Cuenta los registros sin MBID en artistas, álbumes y canciones.
        
        Returns:
            Dict con el número de registros sin MBID en cada tabla
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        missing_mbids = {
            'artists': 0,
            'albums': 0,
            'songs': 0
        }
        
        # Contar artistas sin MBID
        c.execute("SELECT COUNT(*) FROM artists WHERE mbid IS NULL")
        missing_mbids['artists'] = c.fetchone()[0]
        
        # Contar álbumes sin MBID
        c.execute("SELECT COUNT(*) FROM albums WHERE mbid IS NULL")
        missing_mbids['albums'] = c.fetchone()[0]
        
        # Contar canciones sin MBID (si la tabla existe)
        tables = self._check_tables_exist()
        if 'songs' in tables:
            c.execute("SELECT COUNT(*) FROM songs WHERE mbid IS NULL")
            missing_mbids['songs'] = c.fetchone()[0]
        
        conn.close()
        return missing_mbids



    def update_missing_mbids(self):
        """
        Actualiza los MBID faltantes en artistas, álbumes y canciones.
        Prioriza obtener MBID antes que otros tipos de enlaces.
        """
        before_mbids = self.count_missing_mbids()
        self.logger.info("Missing MBIDs before update:")
        for table, count in before_mbids.items():
            self.logger.info(f"{table.capitalize()}: {count}")
        
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()


        # Actualizar MBID de artistas
        c.execute("SELECT id, name FROM artists WHERE mbid IS NULL")
        artists_without_mbid = c.fetchall()
        
        for artist_id, artist_name in artists_without_mbid:
            try:
                mbid = self._get_musicbrainz_artist_mbid(artist_name)
                if mbid:
                    c.execute("UPDATE artists SET mbid = ? WHERE id = ?", (mbid, artist_id))
                    conn.commit()
                    self.logger.info(f"Found MBID for artist: {artist_name}")
                    self._rate_limit_pause()
            except Exception as e:
                self.logger.error(f"Error finding MBID for artist {artist_name}: {e}")

        # Actualizar MBID de álbumes
        c.execute("""
            SELECT albums.id, albums.name, artists.name 
            FROM albums 
            JOIN artists ON albums.artist_id = artists.id 
            WHERE albums.mbid IS NULL
        """)
        albums_without_mbid = c.fetchall()
        
        for album_id, album_name, artist_name in albums_without_mbid:
            try:
                mbid = self._get_musicbrainz_album_mbid(artist_name, album_name)
                if mbid:
                    c.execute("UPDATE albums SET mbid = ? WHERE id = ?", (mbid, album_id))
                    conn.commit()
                    self.logger.info(f"Found MBID for album: {album_name}")
                    self._rate_limit_pause()
            except Exception as e:
                self.logger.error(f"Error finding MBID for album {album_name}: {e}")

        # Actualizar MBID de canciones (opcional, dependiendo de tu estructura)
        c.execute("""
            SELECT id, title, artist, album 
            FROM songs 
            WHERE mbid IS NULL
        """)
        songs_without_mbid = c.fetchall()
        
        for song_id, title, artist, album in songs_without_mbid:
            try:
                mbid = self._get_musicbrainz_recording_mbid(artist, title, album)
                if mbid:
                    c.execute("UPDATE songs SET mbid = ? WHERE id = ?", (mbid, song_id))
                    conn.commit()
                    self.logger.info(f"Found MBID for song: {title}")
                    self._rate_limit_pause()
            except Exception as e:
                self.logger.error(f"Error finding MBID for song {title}: {e}")

        conn.close()
        # Contar registros sin MBID después de la actualización
        after_mbids = self.count_missing_mbids()
        self.logger.info("Missing MBIDs after update:")
        for table, count in after_mbids.items():
            self.logger.info(f"{table.capitalize()}: {count}")
            
        # Calcular y registrar cuántos MBID se encontraron
        mbids_found = {
            table: before_count - after_count 
            for table, (before_count, after_count) in zip(
                before_mbids.keys(), 
                zip(before_mbids.values(), after_mbids.values())
            )
        }
        
        self.logger.info("MBIDs found during update:")
        for table, count in mbids_found.items():
            self.logger.info(f"{table.capitalize()}: {count}")

    def _get_musicbrainz_artist_mbid(self, artist_name: str) -> Optional[str]:
        """Obtiene el MBID de un artista desde MusicBrainz"""
        if 'musicbrainz' in self.disabled_services:
            return None
        
        try:
            result = musicbrainzngs.search_artists(artist=artist_name, limit=1)
            
            if result['artist-list'] and len(result['artist-list']) > 0:
                return result['artist-list'][0]['id']
        except Exception as e:
            self.logger.error(f"MusicBrainz artist MBID search error for {artist_name}: {str(e)}")
        
        return None



    def _get_musicbrainz_album_mbid(self, artist_name: str, album_name: str) -> Optional[str]:
        """Obtiene el MBID de un álbum desde MusicBrainz"""
        if 'musicbrainz' in self.disabled_services:
            return None
        
        try:
            result = musicbrainzngs.search_releases(artist=artist_name, release=album_name, limit=1)
            
            if result['release-list'] and len(result['release-list']) > 0:
                return result['release-list'][0]['id']
        except Exception as e:
            self.logger.error(f"MusicBrainz album MBID search error for {album_name}: {str(e)}")
        
        return None



    def _get_musicbrainz_recording_mbid(self, artist: str, title: str, album: str) -> Optional[str]:
        """Obtiene el MBID de una grabación desde MusicBrainz"""
        if 'musicbrainz' in self.disabled_services:
            return None
        
        try:
            result = musicbrainzngs.search_recordings(
                artist=artist, 
                recording=title, 
                release=album, 
                limit=1
            )
            
            if result['recording-list'] and len(result['recording-list']) > 0:
                return result['recording-list'][0]['id']
        except Exception as e:
            self.logger.error(f"MusicBrainz recording MBID search error for {title}: {str(e)}")
        
        return None


    def _get_lastfm_track_url(self, artist: str, title: str) -> Optional[str]:
        """Genera URL de LastFM para una pista"""
        artist_slug = artist.lower().replace(' ', '-')
        track_slug = title.lower().replace(' ', '-')
        return f"https://www.last.fm/music/{artist_slug}/_/{track_slug}"


    def _get_spotify_artist_url(self, artist_name: str) -> Optional[str]:
        """Obtiene la URL del artista en Spotify"""
        if not self.spotify:
            return None
        
        try:
            results = self.spotify.search(q=f'artist:{artist_name}', type='artist', limit=1)
            
            if results and results['artists']['items']:
                return results['artists']['items'][0]['external_urls']['spotify']
        except Exception as e:
            self.logger.error(f"Spotify artist search error for {artist_name}: {str(e)}")
        
        return None
    
    def _get_spotify_album_data(self, artist_name: str, album_name: str) -> Optional[Dict]:
        """Obtiene datos completos del álbum en Spotify, incluyendo pistas"""
        if not self.spotify:
            return None
        
        try:
            # Primero buscar el álbum
            query = f'artist:{artist_name} album:{album_name}'
            results = self.spotify.search(q=query, type='album', limit=1)
            
            if not (results and results['albums']['items']):
                return None
            
            album = results['albums']['items'][0]
            album_id = album['id']
            album_url = album['external_urls']['spotify']
            
            # Obtener las pistas del álbum
            tracks_result = self.spotify.album_tracks(album_id)
            tracks = []
            
            for track in tracks_result['items']:
                tracks.append({
                    'name': track['name'],
                    'id': track['id'],
                    'url': track['external_urls']['spotify'],
                    'number': track['track_number']
                })
            
            return {
                'album_id': album_id,
                'album_url': album_url,
                'tracks': tracks
            }
            
        except Exception as e:
            self.logger.error(f"Spotify album data fetch error for {album_name} by {artist_name}: {str(e)}")
        
        return None
    
    def _get_youtube_artist_url(self, artist_name: str) -> Optional[str]:
        """Obtiene la URL del canal/tópico del artista en YouTube"""
        if not self.youtube:
            return None
        
        try:
            search_response = self.youtube.search().list(
                q=f"{artist_name} topic",
                part="snippet",
                maxResults=1,
                type="channel"
            ).execute()
            
            if search_response['items']:
                channel_id = search_response['items'][0]['id']['channelId']
                return f"https://www.youtube.com/channel/{channel_id}"
        except Exception as e:
            self.logger.error(f"YouTube artist search error for {artist_name}: {str(e)}")
        
        return None
    
    def _get_spotify_track_url(self, artist: str, title: str, album: str) -> Optional[str]:
        """Obtiene URL de pista en Spotify"""
        if not self.spotify:
            return None
        
        try:
            query = f"track:{title} artist:{artist} album:{album}"
            results = self.spotify.search(q=query, type='track', limit=1)
            
            if results and results['tracks']['items']:
                return results['tracks']['items'][0]['external_urls']['spotify']
        except Exception as e:
            self.logger.error(f"Spotify track search error for {title}: {str(e)}")
        
        return None

    def _get_youtube_track_url(self, artist: str, title: str) -> Optional[str]:
        """Obtiene URL de búsqueda de pista en YouTube"""
        if not self.youtube:
            return None
        
        try:
            query = f"{artist} {title}"
            query_encoded = query.replace(' ', '+')
            return f"https://www.youtube.com/results?search_query={query_encoded}"
        except Exception as e:
            self.logger.error(f"YouTube track search error for {title}: {str(e)}")
        
        return None


    def _get_youtube_album_url(self, artist_name: str, album_name: str) -> Optional[str]:
        """Obtiene la URL de resultados de búsqueda del álbum en YouTube"""
        if not self.youtube:
            return None
        
        try:
            query = f"{artist_name} {album_name} album"
            search_response = self.youtube.search().list(
                q=query,
                part="snippet",
                maxResults=1,
                type="playlist"
            ).execute()
            
            if search_response['items']:
                playlist_id = search_response['items'][0]['id']['playlistId']
                return f"https://www.youtube.com/playlist?list={playlist_id}"
            else:
                # Si no hay playlist, devolver un enlace de búsqueda
                query_encoded = query.replace(' ', '+')
                return f"https://www.youtube.com/results?search_query={query_encoded}"
        except Exception as e:
            self.logger.error(f"YouTube album search error for {album_name} by {artist_name}: {str(e)}")
        
        return None



    
    def _get_musicbrainz_artist_url(self, artist_name: str) -> Optional[str]:
        """Obtiene la URL del artista en MusicBrainz"""
        if 'musicbrainz' in self.disabled_services:
            return None
            
        try:
            result = musicbrainzngs.search_artists(artist=artist_name, limit=1)
            
            if result['artist-list'] and len(result['artist-list']) > 0:
                artist_id = result['artist-list'][0]['id']
                return f"https://musicbrainz.org/artist/{artist_id}"
        except Exception as e:
            self.logger.error(f"MusicBrainz artist search error for {artist_name}: {str(e)}")
        
        return None
    
    def _get_musicbrainz_album_url(self, artist_name: str, album_name: str) -> Optional[str]:
        """Obtiene la URL del álbum en MusicBrainz"""
        if 'musicbrainz' in self.disabled_services:
            return None
            
        try:
            result = musicbrainzngs.search_releases(artist=artist_name, release=album_name, limit=1)
            
            if result['release-list'] and len(result['release-list']) > 0:
                release_id = result['release-list'][0]['id']
                return f"https://musicbrainz.org/release/{release_id}"
        except Exception as e:
            self.logger.error(f"MusicBrainz album search error for {album_name} by {artist_name}: {str(e)}")
        
        return None
    
   
    def _get_musicbrainz_recording_url(self, artist: str, title: str, album: str) -> Optional[str]:
        """Obtiene URL de grabación en MusicBrainz"""
        if 'musicbrainz' in self.disabled_services:
            return None
        
        try:
            result = musicbrainzngs.search_recordings(
                artist=artist, 
                recording=title, 
                release=album, 
                limit=1
            )
            
            if result['recording-list'] and len(result['recording-list']) > 0:
                recording_id = result['recording-list'][0]['id']
                return f"https://musicbrainz.org/recording/{recording_id}"
        except Exception as e:
            self.logger.error(f"MusicBrainz recording search error for {title}: {str(e)}")
        
        return None


    def _get_discogs_artist_url(self, artist_name: str) -> Optional[str]:
        """Obtiene la URL del artista en Discogs"""
        if not self.discogs:
            return None
        
        try:
            results = self.discogs.search(artist_name, type='artist')
            
            if results and len(results) > 0:
                artist_id = results[0].id
                return f"https://www.discogs.com/artist/{artist_id}"
        except Exception as e:
            self.logger.error(f"Discogs artist search error for {artist_name}: {str(e)}")
        
        return None
    
    def _get_discogs_album_url(self, artist_name: str, album_name: str) -> Optional[str]:
        """Obtiene la URL del álbum en Discogs"""
        if not self.discogs:
            return None
        
        try:
            # Buscar artista primero para mejorar precisión
            artist_results = self.discogs.search(artist_name, type='artist')
            
            if artist_results and len(artist_results) > 0:
                artist_id = artist_results[0].id
                
                # Buscar álbum del artista
                album_results = self.discogs.search(f"{artist_name} - {album_name}", type='release')
                
                if album_results and len(album_results) > 0:
                    release_id = album_results[0].id
                    return f"https://www.discogs.com/release/{release_id}"
        except Exception as e:
            self.logger.error(f"Discogs album search error for {album_name} by {artist_name}: {str(e)}")
        
        return None
    
    def _get_rateyourmusic_artist_url(self, artist_name: str) -> Optional[str]:
        """Genera la URL del artista en RateYourMusic"""
        if not self.rateyourmusic_enabled:
            return None
            
        # RateYourMusic no tiene API, así que generamos la URL directamente
        artist_slug = artist_name.lower().replace(' ', '-')
        # Eliminar caracteres especiales
        artist_slug = re.sub(r'[^a-z0-9-]', '', artist_slug)
        return f"https://rateyourmusic.com/artist/{artist_slug}"
    
    def _get_rateyourmusic_album_url(self, artist_name: str, album_name: str) -> Optional[str]:
        """Genera la URL del álbum en RateYourMusic"""
        if not self.rateyourmusic_enabled:
            return None
            
        # RateYourMusic no tiene API, así que generamos la URL directamente
        artist_slug = artist_name.lower().replace(' ', '-')
        album_slug = album_name.lower().replace(' ', '-')
        # Eliminar caracteres especiales
        artist_slug = re.sub(r'[^a-z0-9-]', '', artist_slug)
        album_slug = re.sub(r'[^a-z0-9-]', '', album_slug)
        return f"https://rateyourmusic.com/release/album/{artist_slug}/{album_slug}/"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Music Library External Links Manager')
    parser.add_argument('db_path', help='Path to SQLite database')
    parser.add_argument('--force-update', action='store_true', help='Force update all records')
    parser.add_argument('--artist', help='Artist name to find MBID')
    parser.add_argument('--days', type=int, default=30, help='Update records based on threshold of days')
    parser.add_argument('--disable-services', nargs='+', choices=['spotify', 'youtube', 'musicbrainz', 'discogs', 'rateyourmusic'], 
                        help='Disable specific services')
    parser.add_argument('--summary-only', action='store_true', help='Only show summary information without updating')
    parser.add_argument('--rate-limit', type=float, default=0.5, help='Rate limit in seconds between API requests')
    parser.add_argument('--older-only', action='store_true', 
                        help='Update only older records (default is newer records)')
    parser.add_argument('--missing-only', action='store_true',
                        help='Update only records with missing links')
    
    args = parser.parse_args()
    
    manager = MusicLinksManager(args.db_path, disabled_services=args.disable_services or [], rate_limit=args.rate_limit)

    # Si se proporciona un nombre de artista, buscar su MBID
    if args.artist:
        mbid = manager._get_musicbrainz_artist_mbid(args.artist)
        if mbid:
            print(mbid)
        else:
            print(f"None")


    if args.summary_only:
        counts = manager.get_table_counts()
        missing_mbids = manager.count_missing_mbids()
        
        print("Table Record Counts:")
        for table, count in counts.items():
            print(f"{table.capitalize()}: {count}")
        
        print("\nMissing MBIDs:")
        for table, count in missing_mbids.items():
            print(f"{table.capitalize()}: {count}")
    else:
        manager.update_links(
            days_threshold=args.days, 
            force_update=args.force_update, 
            recent_only=not args.older_only,
            missing_only=args.missing_only
        )