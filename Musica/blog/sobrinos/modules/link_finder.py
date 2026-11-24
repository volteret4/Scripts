"""
Módulo para búsqueda de enlaces
Busca enlaces relevantes en bases de datos locales y APIs externas
"""

import logging
import requests
import time
from typing import Dict, List, Optional, Any
import urllib.parse
from .database_manager import DatabaseManager

try:
    import musicbrainzngs
    musicbrainzngs.set_useragent("AlbumWebGenerator", "1.0", "https://github.com/example/album-web-generator")
except ImportError:
    print("Error: musicbrainzngs no está instalado. Instala con: pip install musicbrainzngs")
    exit(1)

logger = logging.getLogger(__name__)


class LinkFinder:
    """Buscador de enlaces relacionados con artistas y álbumes"""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """
        Inicializar buscador de enlaces

        Args:
            db_manager: Gestor de base de datos opcional
        """
        self.db_manager = db_manager
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'AlbumWebGenerator/1.0 (https://github.com/example/album-web-generator)'
        })

        # Cache para evitar búsquedas repetidas
        self._cache = {}

        # Rate limiting
        self._last_request_time = 0
        self._min_request_interval = 1  # segundo entre requests

    def find_links(self, artist: str, album: str, mbid: Optional[str] = None) -> Dict[str, Dict[str, str]]:
        """
        Buscar todos los enlaces relevantes para un artista y álbum

        Args:
            artist: Nombre del artista
            album: Título del álbum
            mbid: MusicBrainz ID (opcional)

        Returns:
            Diccionario con enlaces organizados por categoría
        """
        cache_key = f"{artist}_{album}_{mbid}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        logger.info(f"Buscando enlaces para: {artist} - {album}")

        all_links = {}

        # 1. Buscar en base de datos local primero
        if self.db_manager:
            db_links = self._search_database_links(artist, album)
            all_links.update(db_links)

        # 2. Buscar en MusicBrainz/Wikidata
        mb_links = self._search_musicbrainz_links(artist, album, mbid)
        all_links.update(mb_links)

        # 3. Completar con búsquedas automáticas
        auto_links = self._search_automatic_links(artist, album)
        for category, links in auto_links.items():
            if category not in all_links:
                all_links[category] = {}
            all_links[category].update(links)

        self._cache[cache_key] = all_links
        return all_links

    def _search_database_links(self, artist: str, album: str) -> Dict[str, Dict[str, str]]:
        """
        Buscar enlaces en la base de datos local

        Args:
            artist: Nombre del artista
            album: Título del álbum

        Returns:
            Enlaces encontrados en la base de datos
        """
        if not self.db_manager:
            return {}

        logger.debug("Buscando enlaces en base de datos local")

        # Buscar enlaces del artista
        artist_links = self.db_manager.find_artist_links(artist)

        # Buscar enlaces específicos del álbum
        album_links = self.db_manager.find_album_links(artist, album)

        # Organizar enlaces por categorías
        organized_links = {}

        # Procesar enlaces del artista
        for link_type, link_data in artist_links.items():
            category = self._categorize_link(link_type)
            if category not in organized_links:
                organized_links[category] = {}

            organized_links[category][link_type] = {
                'url': link_data['url'],
                'title': link_data['description'],
                'source': 'database'
            }

        # Procesar enlaces del álbum
        for link_type, link_data in album_links.items():
            category = self._categorize_link(link_type)
            if category not in organized_links:
                organized_links[category] = {}

            organized_links[category][f"album_{link_type}"] = {
                'url': link_data['url'],
                'title': link_data['description'],
                'source': 'database'
            }

        return organized_links

    def _search_musicbrainz_links(self, artist: str, album: str, mbid: Optional[str] = None) -> Dict[str, Dict[str, str]]:
        """
        Buscar enlaces usando MusicBrainz y relaciones

        Args:
            artist: Nombre del artista
            album: Título del álbum
            mbid: MusicBrainz ID

        Returns:
            Enlaces encontrados en MusicBrainz
        """
        links = {}

        try:
            self._rate_limit()

            # Si no tenemos MBID, buscar el artista
            artist_mbid = mbid
            if not artist_mbid:
                result = musicbrainzngs.search_artists(artist=artist, limit=1)
                if result['artist-list']:
                    artist_mbid = result['artist-list'][0]['id']

            if artist_mbid:
                # Obtener información detallada del artista con relaciones
                artist_info = musicbrainzngs.get_artist_by_id(
                    artist_mbid,
                    includes=['url-rels']
                )

                if 'url-relation-list' in artist_info['artist']:
                    links['official'] = {}
                    links['social'] = {}

                    for relation in artist_info['artist']['url-relation-list']:
                        rel_type = relation.get('type', '').lower()
                        url = relation.get('target', '')

                        if 'official' in rel_type or 'homepage' in rel_type:
                            links['official']['website'] = {
                                'url': url,
                                'title': 'Sitio web oficial',
                                'source': 'MusicBrainz'
                            }
                        elif 'discogs' in rel_type:
                            links['official']['discogs'] = {
                                'url': url,
                                'title': 'Discogs',
                                'source': 'MusicBrainz'
                            }
                        elif 'last.fm' in rel_type or 'lastfm' in rel_type:
                            links['streaming']['lastfm'] = {
                                'url': url,
                                'title': 'Last.fm',
                                'source': 'MusicBrainz'
                            }
                        elif any(social in rel_type for social in ['twitter', 'facebook', 'instagram']):
                            platform = rel_type.replace(' ', '_')
                            if 'social' not in links:
                                links['social'] = {}
                            links['social'][platform] = {
                                'url': url,
                                'title': f'{platform.title()}',
                                'source': 'MusicBrainz'
                            }

            # Buscar información del álbum
            release_result = musicbrainzngs.search_releases(
                artist=artist,
                release=album,
                limit=1
            )

            if release_result['release-list']:
                release_mbid = release_result['release-list'][0]['id']
                # Aquí se podrían buscar enlaces específicos del álbum

        except Exception as e:
            logger.warning(f"Error buscando enlaces en MusicBrainz: {e}")

        return links

    def _search_automatic_links(self, artist: str, album: str) -> Dict[str, Dict[str, str]]:
        """
        Generar enlaces automáticamente basados en patrones conocidos

        Args:
            artist: Nombre del artista
            album: Título del álbum

        Returns:
            Enlaces generados automáticamente
        """
        links = {
            'streaming': {},
            'info': {},
            'social': {}
        }

        # Limpiar nombres para URLs
        artist_clean = urllib.parse.quote(artist)
        album_clean = urllib.parse.quote(album)
        artist_search = urllib.parse.quote(f"{artist} {album}")

        # Enlaces de información
        links['info']['wikipedia'] = {
            'url': f"https://es.wikipedia.org/wiki/Special:Search?search={artist_search}",
            'title': 'Wikipedia (búsqueda)',
            'source': 'automatic'
        }

        links['info']['musicbrainz'] = {
            'url': f"https://musicbrainz.org/search?query={artist_search}&type=release",
            'title': 'MusicBrainz',
            'source': 'automatic'
        }

        # Enlaces de tiendas/streaming
        links['streaming']['spotify'] = {
            'url': f"https://open.spotify.com/search/{artist_search}",
            'title': 'Spotify (búsqueda)',
            'source': 'automatic'
        }

        links['streaming']['apple_music'] = {
            'url': f"https://music.apple.com/search?term={artist_search}",
            'title': 'Apple Music (búsqueda)',
            'source': 'automatic'
        }

        links['streaming']['youtube'] = {
            'url': f"https://www.youtube.com/results?search_query={artist_search}",
            'title': 'YouTube (búsqueda)',
            'source': 'automatic'
        }

        # Enlaces de información musical
        links['info']['discogs'] = {
            'url': f"https://www.discogs.com/search/?q={artist_search}&type=all",
            'title': 'Discogs (búsqueda)',
            'source': 'automatic'
        }

        links['info']['lastfm'] = {
            'url': f"https://www.last.fm/search?q={artist_search}",
            'title': 'Last.fm (búsqueda)',
            'source': 'automatic'
        }

        links['info']['genius'] = {
            'url': f"https://genius.com/search?q={artist_search}",
            'title': 'Genius (letras)',
            'source': 'automatic'
        }

        # Enlaces sociales (búsquedas)
        links['social']['twitter'] = {
            'url': f"https://twitter.com/search?q={urllib.parse.quote(artist)}",
            'title': 'Twitter (búsqueda)',
            'source': 'automatic'
        }

        links['social']['instagram'] = {
            'url': f"https://www.instagram.com/explore/tags/{urllib.parse.quote(artist.replace(' ', ''))}",
            'title': 'Instagram (búsqueda)',
            'source': 'automatic'
        }

        links['social']['facebook'] = {
            'url': f"https://www.facebook.com/search/top?q={artist_clean}",
            'title': 'Facebook (búsqueda)',
            'source': 'automatic'
        }

        # Nuevas redes sociales
        links['social']['bluesky'] = {
            'url': f"https://bsky.app/search?q={urllib.parse.quote(artist)}",
            'title': 'Bluesky (búsqueda)',
            'source': 'automatic'
        }

        return links

    def _categorize_link(self, link_type: str) -> str:
        """
        Categorizar un tipo de enlace

        Args:
            link_type: Tipo de enlace

        Returns:
            Categoría del enlace
        """
        link_type_lower = link_type.lower()

        if any(platform in link_type_lower for platform in ['twitter', 'facebook', 'instagram', 'bluesky', 'tiktok']):
            return 'social'
        elif any(platform in link_type_lower for platform in ['spotify', 'apple', 'youtube', 'bandcamp']):
            return 'streaming'
        elif any(platform in link_type_lower for platform in ['wikipedia', 'discogs', 'musicbrainz', 'lastfm', 'genius']):
            return 'info'
        elif any(word in link_type_lower for word in ['official', 'website', 'homepage']):
            return 'official'
        else:
            return 'other'

    def _rate_limit(self):
        """Implementar rate limiting para las APIs"""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time

        if time_since_last < self._min_request_interval:
            sleep_time = self._min_request_interval - time_since_last
            time.sleep(sleep_time)

        self._last_request_time = time.time()

    def verify_link(self, url: str) -> bool:
        """
        Verificar si un enlace es accesible

        Args:
            url: URL a verificar

        Returns:
            True si el enlace es accesible
        """
        try:
            self._rate_limit()

            response = self.session.head(url, timeout=10, allow_redirects=True)
            return response.status_code < 400

        except Exception:
            return False

    def get_link_categories(self) -> Dict[str, Dict[str, str]]:
        """
        Obtener información sobre las categorías de enlaces

        Returns:
            Diccionario con información de categorías
        """
        return {
            'official': {
                'name': 'Oficiales',
                'description': 'Sitios web oficiales del artista',
                'icon': '🌐'
            },
            'streaming': {
                'name': 'Streaming',
                'description': 'Plataformas de música digital',
                'icon': '🎵'
            },
            'social': {
                'name': 'Redes Sociales',
                'description': 'Perfiles en redes sociales',
                'icon': '📱'
            },
            'info': {
                'name': 'Información',
                'description': 'Bases de datos musicales',
                'icon': '📚'
            },
            'other': {
                'name': 'Otros',
                'description': 'Enlaces adicionales',
                'icon': '🔗'
            }
        }
