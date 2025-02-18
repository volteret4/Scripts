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
from typing import Dict, List, Optional
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
    def __init__(self, db_path: str):
        self.db_path = Path(db_path).resolve()
        
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
        
        # MusicBrainz
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
        
        # Discogs
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
        
        # YouTube
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
    
    def _update_database_schema(self):
        """Actualiza el esquema de la base de datos para incluir columnas de enlaces"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Verificar si las columnas existen en la tabla artists
        c.execute("PRAGMA table_info(artists)")
        artist_columns = {col[1] for col in c.fetchall()}
        
        # Añadir columnas para enlaces de artistas si no existen
        artist_links_columns = {
            'spotify_url': 'TEXT',
            'youtube_url': 'TEXT',
            'musicbrainz_url': 'TEXT',
            'discogs_url': 'TEXT',
            'rateyourmusic_url': 'TEXT',
            'links_updated': 'TIMESTAMP'
        }
        
        for col_name, col_type in artist_links_columns.items():
            if col_name not in artist_columns:
                c.execute(f"ALTER TABLE artists ADD COLUMN {col_name} {col_type}")
        
        # Verificar si las columnas existen en la tabla albums
        c.execute("PRAGMA table_info(albums)")
        album_columns = {col[1] for col in c.fetchall()}
        
        # Añadir columnas para enlaces de álbumes si no existen
        album_links_columns = {
            'spotify_url': 'TEXT',
            'youtube_url': 'TEXT',
            'musicbrainz_url': 'TEXT',
            'discogs_url': 'TEXT',
            'rateyourmusic_url': 'TEXT',
            'links_updated': 'TIMESTAMP'
        }
        
        for col_name, col_type in album_links_columns.items():
            if col_name not in album_columns:
                c.execute(f"ALTER TABLE albums ADD COLUMN {col_name} {col_type}")
        
        conn.commit()
        conn.close()
        self.logger.info("Database schema updated with external links columns")
    
    def update_links(self, days_threshold=30, force_update=False):
        """
        Actualiza los enlaces externos para artistas y álbumes
        
        Args:
            days_threshold: Actualizar solo registros más antiguos que estos días
            force_update: Forzar actualización de todos los registros independientemente de su fecha
        """
        self.update_artist_links(days_threshold, force_update)
        self.update_album_links(days_threshold, force_update)
    
    def update_artist_links(self, days_threshold=30, force_update=False):
        """Actualiza los enlaces externos para artistas"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        if force_update:
            c.execute("SELECT id, name FROM artists")
        else:
            # Filtrar por fecha de actualización de enlaces
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
            
            links = {
                'spotify_url': self._get_spotify_artist_url(artist_name),
                'youtube_url': self._get_youtube_artist_url(artist_name),
                'musicbrainz_url': self._get_musicbrainz_artist_url(artist_name),
                'discogs_url': self._get_discogs_artist_url(artist_name),
                'rateyourmusic_url': self._get_rateyourmusic_artist_url(artist_name),
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
            
            # Pausa para evitar límites de tasa en APIs
            time.sleep(0.5)
        
        conn.close()
        self.logger.info(f"Updated links for {total_artists} artists")
    
    def update_album_links(self, days_threshold=30, force_update=False):
        """Actualiza los enlaces externos para álbumes"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        if force_update:
            c.execute("""
                SELECT albums.id, albums.name, artists.name 
                FROM albums JOIN artists ON albums.artist_id = artists.id
            """)
        else:
            # Filtrar por fecha de actualización de enlaces
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
            
            links = {
                'spotify_url': self._get_spotify_album_url(artist_name, album_name),
                'youtube_url': self._get_youtube_album_url(artist_name, album_name),
                'musicbrainz_url': self._get_musicbrainz_album_url(artist_name, album_name),
                'discogs_url': self._get_discogs_album_url(artist_name, album_name),
                'rateyourmusic_url': self._get_rateyourmusic_album_url(artist_name, album_name),
                'links_updated': datetime.now()
            }
            
            # Actualizar enlaces en la base de datos
            update_query = """
                UPDATE albums SET 
                spotify_url = ?, youtube_url = ?, musicbrainz_url = ?, 
                discogs_url = ?, rateyourmusic_url = ?, links_updated = ?
                WHERE id = ?
            """
            c.execute(update_query, (
                links['spotify_url'], links['youtube_url'], links['musicbrainz_url'],
                links['discogs_url'], links['rateyourmusic_url'], links['links_updated'],
                album_id
            ))
            
            conn.commit()
            
            # Pausa para evitar límites de tasa en APIs
            time.sleep(0.5)
        
        conn.close()
        self.logger.info(f"Updated links for {total_albums} albums")
    
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
    
    def _get_spotify_album_url(self, artist_name: str, album_name: str) -> Optional[str]:
        """Obtiene la URL del álbum en Spotify"""
        if not self.spotify:
            return None
        
        try:
            query = f'artist:{artist_name} album:{album_name}'
            results = self.spotify.search(q=query, type='album', limit=1)
            
            if results and results['albums']['items']:
                return results['albums']['items'][0]['external_urls']['spotify']
        except Exception as e:
            self.logger.error(f"Spotify album search error for {album_name} by {artist_name}: {str(e)}")
        
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
        try:
            result = musicbrainzngs.search_releases(artist=artist_name, release=album_name, limit=1)
            
            if result['release-list'] and len(result['release-list']) > 0:
                release_id = result['release-list'][0]['id']
                return f"https://musicbrainz.org/release/{release_id}"
        except Exception as e:
            self.logger.error(f"MusicBrainz album search error for {album_name} by {artist_name}: {str(e)}")
        
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
    
    def _get_rateyourmusic_artist_url(self, artist_name: str) -> str:
        """Genera la URL del artista en RateYourMusic"""
        # RateYourMusic no tiene API, así que generamos la URL directamente
        artist_slug = artist_name.lower().replace(' ', '-')
        # Eliminar caracteres especiales
        artist_slug = re.sub(r'[^a-z0-9-]', '', artist_slug)
        return f"https://rateyourmusic.com/artist/{artist_slug}"
    
    def _get_rateyourmusic_album_url(self, artist_name: str, album_name: str) -> str:
        """Genera la URL del álbum en RateYourMusic"""
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
    parser.add_argument('--days', type=int, default=30, help='Update records older than this many days')
    
    args = parser.parse_args()
    
    manager = MusicLinksManager(args.db_path)
    manager.update_links(days_threshold=args.days, force_update=args.force_update)