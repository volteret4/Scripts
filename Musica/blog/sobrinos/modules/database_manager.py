"""
Módulo para gestión de base de datos SQLite
Maneja conexiones y consultas a la base de datos de enlaces
"""

import sqlite3
import logging
from typing import Optional, Dict, List, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Gestor de base de datos para enlaces de artistas y álbumes"""

    def __init__(self, db_path: Optional[str] = None):
        """
        Inicializar gestor de base de datos

        Args:
            db_path: Ruta a la base de datos SQLite
        """
        self.db_path = db_path
        self.connection = None

        if db_path and Path(db_path).exists():
            self._connect()
        elif db_path:
            logger.warning(f"Base de datos no encontrada: {db_path}")

    def _connect(self):
        """Establecer conexión con la base de datos"""
        try:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row
            logger.info(f"Conectado a la base de datos: {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"Error conectando a la base de datos: {e}")
            self.connection = None

    def find_artist_links(self, artist_name: str) -> Dict[str, str]:
        """
        Buscar enlaces de un artista en la base de datos

        Args:
            artist_name: Nombre del artista

        Returns:
            Diccionario con enlaces encontrados
        """
        if not self.connection:
            return {}

        try:
            cursor = self.connection.cursor()

            # Buscar artista en la tabla artists
            cursor.execute("""
                SELECT id, name, spotify_url, youtube_url, musicbrainz_url,
                       discogs_url, rateyourmusic_url, wikipedia_url,
                       bandcamp_url, lastfm_url, website, mbid
                FROM artists
                WHERE LOWER(name) = LOWER(?)
            """, (artist_name,))

            result = cursor.fetchone()

            if not result:
                # Buscar por coincidencia parcial
                cursor.execute("""
                    SELECT id, name, spotify_url, youtube_url, musicbrainz_url,
                           discogs_url, rateyourmusic_url, wikipedia_url,
                           bandcamp_url, lastfm_url, website, mbid
                    FROM artists
                    WHERE LOWER(name) LIKE LOWER(?)
                    LIMIT 1
                """, (f"%{artist_name}%",))
                result = cursor.fetchone()

            if not result:
                return {}

            # Mapear URLs a tipos de enlaces
            links = {}
            url_mapping = {
                'spotify_url': 'spotify',
                'youtube_url': 'youtube',
                'musicbrainz_url': 'musicbrainz',
                'discogs_url': 'discogs',
                'rateyourmusic_url': 'rateyourmusic',
                'wikipedia_url': 'wikipedia',
                'bandcamp_url': 'bandcamp',
                'lastfm_url': 'lastfm',
                'website': 'official_website'
            }

            for db_field, link_type in url_mapping.items():
                url = result[db_field]
                if url and url.strip():
                    links[link_type] = {
                        'url': url.strip(),
                        'description': f"{result['name']} en {link_type.replace('_', ' ').title()}"
                    }

            logger.debug(f"Encontrados {len(links)} enlaces para {artist_name}")
            return links

        except sqlite3.Error as e:
            logger.error(f"Error buscando enlaces del artista: {e}")
            return {}

    def find_album_links(self, artist_name: str, album_title: str) -> Dict[str, str]:
        """
        Buscar enlaces específicos de un álbum en la base de datos

        Args:
            artist_name: Nombre del artista
            album_title: Título del álbum

        Returns:
            Diccionario con enlaces encontrados
        """
        if not self.connection:
            return {}

        try:
            cursor = self.connection.cursor()

            # Primero buscar el artista
            cursor.execute("""
                SELECT id FROM artists
                WHERE LOWER(name) = LOWER(?)
            """, (artist_name,))

            artist_result = cursor.fetchone()
            if not artist_result:
                return {}

            artist_id = artist_result['id']

            # Buscar álbum específico
            cursor.execute("""
                SELECT id, name, spotify_url, spotify_id, youtube_url,
                       musicbrainz_url, discogs_url, rateyourmusic_url,
                       wikipedia_url, bandcamp_url, lastfm_url, mbid,
                       musicbrainz_albumid, musicbrainz_albumartistid,
                       musicbrainz_releasegroupid, album_art_urls
                FROM albums
                WHERE artist_id = ? AND LOWER(name) = LOWER(?)
            """, (artist_id, album_title))

            result = cursor.fetchone()

            if not result:
                # Buscar por coincidencia parcial
                cursor.execute("""
                    SELECT id, name, spotify_url, spotify_id, youtube_url,
                           musicbrainz_url, discogs_url, rateyourmusic_url,
                           wikipedia_url, bandcamp_url, lastfm_url, mbid,
                           musicbrainz_albumid, musicbrainz_albumartistid,
                           musicbrainz_releasegroupid, album_art_urls
                    FROM albums
                    WHERE artist_id = ? AND LOWER(name) LIKE LOWER(?)
                    LIMIT 1
                """, (artist_id, f"%{album_title}%"))
                result = cursor.fetchone()

            if not result:
                return {}

            # Mapear URLs a tipos de enlaces
            links = {}
            url_mapping = {
                'spotify_url': 'spotify',
                'youtube_url': 'youtube',
                'musicbrainz_url': 'musicbrainz',
                'discogs_url': 'discogs',
                'rateyourmusic_url': 'rateyourmusic',
                'wikipedia_url': 'wikipedia',
                'bandcamp_url': 'bandcamp',
                'lastfm_url': 'lastfm'
            }

            for db_field, link_type in url_mapping.items():
                url = result[db_field]
                if url and url.strip():
                    links[link_type] = {
                        'url': url.strip(),
                        'description': f"{result['name']} en {link_type.replace('_', ' ').title()}"
                    }

            # Agregar información específica de MusicBrainz si está disponible
            if result['musicbrainz_albumid']:
                links['musicbrainz_album'] = {
                    'url': f"https://musicbrainz.org/release/{result['musicbrainz_albumid']}",
                    'description': f"MusicBrainz - {result['name']}"
                }

            logger.debug(f"Encontrados {len(links)} enlaces para álbum {album_title}")
            return links

        except sqlite3.Error as e:
            logger.error(f"Error buscando enlaces del álbum: {e}")
            return {}

    def find_musicbrainz_data(self, mbid: Optional[str] = None, artist_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Buscar datos adicionales usando MusicBrainz ID o nombre de artista

        Args:
            mbid: MusicBrainz ID
            artist_name: Nombre del artista (alternativo)

        Returns:
            Diccionario con datos adicionales
        """
        if not self.connection:
            return {}

        try:
            cursor = self.connection.cursor()
            data = {}

            if mbid:
                # Buscar por MBID en artists
                cursor.execute("""
                    SELECT name, bio, tags, similar_artists, origin, formed_year,
                           total_albums, mbid
                    FROM artists
                    WHERE mbid = ?
                """, (mbid,))

                result = cursor.fetchone()
                if result:
                    data.update({
                        'artist_bio': result['bio'],
                        'artist_tags': result['tags'],
                        'similar_artists': result['similar_artists'],
                        'origin': result['origin'],
                        'formed_year': result['formed_year'],
                        'total_albums': result['total_albums']
                    })

                # Buscar álbumes del artista por MBID
                cursor.execute("""
                    SELECT a.name, a.year, a.label, a.genre, a.mbid as album_mbid
                    FROM albums a
                    JOIN artists ar ON a.artist_id = ar.id
                    WHERE ar.mbid = ?
                """, (mbid,))

                albums = cursor.fetchall()
                if albums:
                    data['albums'] = [dict(album) for album in albums]

            elif artist_name:
                # Buscar por nombre de artista
                cursor.execute("""
                    SELECT name, bio, tags, similar_artists, origin, formed_year,
                           total_albums, mbid
                    FROM artists
                    WHERE LOWER(name) = LOWER(?)
                """, (artist_name,))

                result = cursor.fetchone()
                if result:
                    data.update({
                        'artist_bio': result['bio'],
                        'artist_tags': result['tags'],
                        'similar_artists': result['similar_artists'],
                        'origin': result['origin'],
                        'formed_year': result['formed_year'],
                        'total_albums': result['total_albums'],
                        'mbid': result['mbid']
                    })

            return data

        except sqlite3.Error as e:
            logger.error(f"Error buscando datos de MusicBrainz: {e}")
            return {}

    def get_schema_info(self) -> Dict[str, List[str]]:
        """
        Obtener información del esquema de la base de datos

        Returns:
            Diccionario con tablas y columnas
        """
        if not self.connection:
            return {}

        try:
            cursor = self.connection.cursor()

            # Obtener lista de tablas
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            schema = {}
            for table in tables:
                cursor.execute(f"PRAGMA table_info({table})")
                columns = [row[1] for row in cursor.fetchall()]
                schema[table] = columns

            return schema

        except sqlite3.Error as e:
            logger.error(f"Error obteniendo esquema: {e}")
            return {}

    def close(self):
        """Cerrar conexión con la base de datos"""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.debug("Conexión con la base de datos cerrada")
