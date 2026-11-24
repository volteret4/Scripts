"""
Módulo para búsqueda de imágenes
Busca imágenes de álbumes y artistas usando MusicBrainz, Spotify y otras fuentes
"""

import logging
import requests
from typing import Optional, Dict, Any
import time
import urllib.parse

try:
    import musicbrainzngs
    musicbrainzngs.set_useragent("AlbumWebGenerator", "1.0", "https://github.com/example/album-web-generator")
except ImportError:
    print("Error: musicbrainzngs no está instalado. Instala con: pip install musicbrainzngs")
    exit(1)

logger = logging.getLogger(__name__)


class ImageFinder:
    """Buscador de imágenes de álbumes y artistas"""

    def __init__(self):
        """Inicializar buscador de imágenes"""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'AlbumWebGenerator/1.0 (https://github.com/example/album-web-generator)'
        })

        # Cache para evitar búsquedas repetidas
        self._cache = {}

        # Rate limiting
        self._last_request_time = 0
        self._min_request_interval = 1  # segundo entre requests

    def find_album_image(self, artist: str, album: str) -> Optional[Dict[str, str]]:
        """
        Buscar imagen de portada del álbum

        Args:
            artist: Nombre del artista
            album: Título del álbum

        Returns:
            Diccionario con información de la imagen o None
        """
        cache_key = f"album_{artist}_{album}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        logger.info(f"Buscando imagen del álbum: {artist} - {album}")

        # Intentar diferentes fuentes
        image_info = None

        # 1. MusicBrainz Cover Art Archive
        image_info = self._search_musicbrainz_album(artist, album)

        # 2. Si no se encuentra, intentar con Last.fm
        if not image_info:
            image_info = self._search_lastfm_album(artist, album)

        # 3. Como último recurso, buscar en Discogs
        if not image_info:
            image_info = self._search_discogs_album(artist, album)

        self._cache[cache_key] = image_info
        return image_info

    def find_artist_image(self, artist: str) -> Optional[Dict[str, str]]:
        """
        Buscar imagen del artista

        Args:
            artist: Nombre del artista

        Returns:
            Diccionario con información de la imagen o None
        """
        cache_key = f"artist_{artist}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        logger.info(f"Buscando imagen del artista: {artist}")

        # Intentar diferentes fuentes
        image_info = None

        # 1. MusicBrainz
        image_info = self._search_musicbrainz_artist(artist)

        # 2. Last.fm
        if not image_info:
            image_info = self._search_lastfm_artist(artist)

        self._cache[cache_key] = image_info
        return image_info

    def _search_musicbrainz_album(self, artist: str, album: str) -> Optional[Dict[str, str]]:
        """Buscar imagen del álbum en MusicBrainz Cover Art Archive"""
        try:
            self._rate_limit()

            # Buscar release en MusicBrainz
            result = musicbrainzngs.search_releases(
                artist=artist,
                release=album,
                limit=1
            )

            if result['release-list']:
                release = result['release-list'][0]
                release_id = release['id']

                # Obtener portada del Cover Art Archive
                try:
                    cover_art = musicbrainzngs.get_image_list(release_id)
                    if cover_art['images']:
                        # Buscar imagen frontal o la primera disponible
                        front_image = None
                        for image in cover_art['images']:
                            if 'Front' in image.get('types', []):
                                front_image = image
                                break

                        if not front_image:
                            front_image = cover_art['images'][0]

                        return {
                            'url': front_image['image'],
                            'source': 'MusicBrainz Cover Art Archive',
                            'size': 'large',
                            'mbid': release_id
                        }

                except musicbrainzngs.ResponseError:
                    pass  # No hay cover art disponible

        except Exception as e:
            logger.warning(f"Error buscando en MusicBrainz: {e}")

        return None

    def _search_musicbrainz_artist(self, artist: str) -> Optional[Dict[str, str]]:
        """Buscar imagen del artista en MusicBrainz"""
        try:
            self._rate_limit()

            # Buscar artista en MusicBrainz
            result = musicbrainzngs.search_artists(artist=artist, limit=1)

            if result['artist-list']:
                artist_data = result['artist-list'][0]
                artist_id = artist_data['id']

                # MusicBrainz no tiene imágenes de artistas directamente
                # Pero podemos obtener el MBID para usar en otras APIs
                return {
                    'mbid': artist_id,
                    'source': 'MusicBrainz'
                }

        except Exception as e:
            logger.warning(f"Error buscando artista en MusicBrainz: {e}")

        return None

    def _search_lastfm_album(self, artist: str, album: str) -> Optional[Dict[str, str]]:
        """Buscar imagen del álbum en Last.fm"""
        try:
            self._rate_limit()

            # Last.fm requiere API key, implementación básica sin key
            # En un entorno real, se necesitaría registrar para obtener una API key
            url = "http://ws.audioscrobbler.com/2.0/"
            params = {
                'method': 'album.getinfo',
                'artist': artist,
                'album': album,
                'format': 'json'
            }

            # Sin API key, esto no funcionará, pero dejo la estructura
            # response = self.session.get(url, params=params)
            # if response.status_code == 200:
            #     data = response.json()
            #     if 'album' in data and 'image' in data['album']:
            #         images = data['album']['image']
            #         for img in reversed(images):  # Empezar por la más grande
            #             if img['#text']:
            #                 return {
            #                     'url': img['#text'],
            #                     'source': 'Last.fm',
            #                     'size': img['size']
            #                 }

            logger.debug("Last.fm requiere API key para buscar imágenes")

        except Exception as e:
            logger.warning(f"Error buscando en Last.fm: {e}")

        return None

    def _search_lastfm_artist(self, artist: str) -> Optional[Dict[str, str]]:
        """Buscar imagen del artista en Last.fm"""
        try:
            self._rate_limit()

            # Similar a _search_lastfm_album, requiere API key
            logger.debug("Last.fm requiere API key para buscar imágenes de artistas")

        except Exception as e:
            logger.warning(f"Error buscando artista en Last.fm: {e}")

        return None

    def _search_discogs_album(self, artist: str, album: str) -> Optional[Dict[str, str]]:
        """Buscar imagen del álbum en Discogs"""
        try:
            self._rate_limit()

            # Discogs API básica sin autenticación (limitada)
            url = "https://api.discogs.com/database/search"
            params = {
                'q': f"{artist} {album}",
                'type': 'release',
                'per_page': 1
            }

            response = self.session.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                if data['results']:
                    result = data['results'][0]
                    if 'cover_image' in result and result['cover_image']:
                        return {
                            'url': result['cover_image'],
                            'source': 'Discogs',
                            'size': 'medium'
                        }

        except Exception as e:
            logger.warning(f"Error buscando en Discogs: {e}")

        return None

    def _rate_limit(self):
        """Implementar rate limiting para las APIs"""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time

        if time_since_last < self._min_request_interval:
            sleep_time = self._min_request_interval - time_since_last
            time.sleep(sleep_time)

        self._last_request_time = time.time()

    def download_image(self, image_info: Dict[str, str], output_path: str) -> bool:
        """
        Descargar una imagen

        Args:
            image_info: Información de la imagen
            output_path: Ruta donde guardar la imagen

        Returns:
            True si se descargó correctamente
        """
        try:
            if 'url' not in image_info:
                return False

            self._rate_limit()

            response = self.session.get(image_info['url'], stream=True)
            if response.status_code == 200:
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                logger.info(f"Imagen descargada: {output_path}")
                return True

        except Exception as e:
            logger.error(f"Error descargando imagen: {e}")

        return False

    def get_placeholder_image_url(self, image_type: str = 'album') -> str:
        """
        Obtener URL de imagen placeholder

        Args:
            image_type: Tipo de imagen ('album' o 'artist')

        Returns:
            URL de imagen placeholder
        """
        if image_type == 'album':
            # Imagen placeholder para álbumes
            return "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='300' height='300' viewBox='0 0 300 300'%3E%3Crect width='300' height='300' fill='%23ddd'/%3E%3Ctext x='50%25' y='50%25' text-anchor='middle' dy='.3em' font-family='Arial, sans-serif' font-size='18' fill='%23999'%3EÁlbum%3C/text%3E%3C/svg%3E"
        else:
            # Imagen placeholder para artistas
            return "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='300' height='300' viewBox='0 0 300 300'%3E%3Ccircle cx='150' cy='150' r='150' fill='%23ddd'/%3E%3Ctext x='50%25' y='50%25' text-anchor='middle' dy='.3em' font-family='Arial, sans-serif' font-size='18' fill='%23999'%3EArtista%3C/text%3E%3C/svg%3E"
