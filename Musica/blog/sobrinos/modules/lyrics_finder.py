"""
Módulo para búsqueda de letras
Busca letras de canciones en diferentes fuentes como Genius, LyricFind, etc.
"""

import logging
import requests
import time
from typing import Dict, List, Optional, Any
import urllib.parse
import re

logger = logging.getLogger(__name__)


class LyricsFinder:
    """Buscador de letras de canciones"""

    def __init__(self):
        """Inicializar buscador de letras"""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'AlbumWebGenerator/1.0 (https://github.com/example/album-web-generator)'
        })

        # Cache para evitar búsquedas repetidas
        self._cache = {}

        # Rate limiting
        self._last_request_time = 0
        self._min_request_interval = 1  # segundo entre requests

    def find_lyrics(self, artist: str, tracks: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Buscar letras para todas las canciones del álbum

        Args:
            artist: Nombre del artista principal
            tracks: Lista de información de pistas

        Returns:
            Diccionario con letras de las canciones
        """
        lyrics_data = {}

        for track in tracks:
            track_title = track.get('title', '')
            track_artist = track.get('artist', artist)  # Usar artista del track o del álbum

            if not track_title or track_title == 'Pista Sin Título':
                continue

            logger.info(f"Buscando letras para: {track_artist} - {track_title}")

            lyrics_info = self._search_lyrics(track_artist, track_title)
            if lyrics_info:
                lyrics_data[track_title] = lyrics_info
            else:
                # Crear entrada vacía para canciones sin letras encontradas
                lyrics_data[track_title] = {
                    'lyrics': None,
                    'source': None,
                    'url': None,
                    'error': 'No se encontraron letras'
                }

        logger.info(f"Letras encontradas para {len([l for l in lyrics_data.values() if l['lyrics']])} de {len(lyrics_data)} canciones")
        return lyrics_data

    def _search_lyrics(self, artist: str, title: str) -> Optional[Dict[str, Any]]:
        """
        Buscar letras de una canción específica

        Args:
            artist: Nombre del artista
            title: Título de la canción

        Returns:
            Diccionario con información de las letras o None
        """
        cache_key = f"{artist}_{title}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        lyrics_info = None

        # 1. Intentar con Genius (método básico sin API)
        lyrics_info = self._search_genius_scraping(artist, title)

        # 2. Si no funciona, intentar con AZLyrics
        if not lyrics_info:
            lyrics_info = self._search_azlyrics(artist, title)

        # 3. Como último recurso, intentar con Lyrics.ovh
        if not lyrics_info:
            lyrics_info = self._search_lyrics_ovh(artist, title)

        self._cache[cache_key] = lyrics_info
        return lyrics_info

    def _search_genius_scraping(self, artist: str, title: str) -> Optional[Dict[str, Any]]:
        """
        Buscar letras en Genius usando scraping básico
        Nota: Esto es para demostración. En producción sería mejor usar la API oficial.
        """
        try:
            self._rate_limit()

            # Construir URL de búsqueda
            query = f"{artist} {title}".lower()
            query = re.sub(r'[^a-z0-9\s]', '', query)  # Limpiar caracteres especiales
            query = ' '.join(query.split())  # Normalizar espacios

            # Nota: Genius tiene medidas anti-scraping
            # Esta implementación es básica y puede no funcionar
            search_url = f"https://genius.com/search?q={urllib.parse.quote(query)}"

            logger.debug(f"Buscando en Genius (scraping no recomendado en producción)")

            # En un entorno real, se debería:
            # 1. Usar la API oficial de Genius con token
            # 2. Respetar robots.txt y términos de servicio
            # 3. Implementar manejo robusto de errores

            return None  # Deshabilitado por defecto

        except Exception as e:
            logger.warning(f"Error buscando en Genius: {e}")
            return None

    def _search_azlyrics(self, artist: str, title: str) -> Optional[Dict[str, Any]]:
        """
        Buscar letras en AZLyrics
        Nota: AZLyrics también tiene restricciones de scraping
        """
        try:
            self._rate_limit()

            # Limpiar nombres para URL de AZLyrics
            artist_clean = re.sub(r'[^a-z0-9]', '', artist.lower())
            title_clean = re.sub(r'[^a-z0-9]', '', title.lower())

            url = f"https://www.azlyrics.com/lyrics/{artist_clean}/{title_clean}.html"

            logger.debug(f"AZLyrics scraping no implementado (requiere manejo cuidadoso)")

            # Similar a Genius, el scraping de AZLyrics requiere:
            # 1. Respetar términos de servicio
            # 2. Manejo robusto de anti-bot measures
            # 3. Rate limiting adecuado

            return None  # Deshabilitado por defecto

        except Exception as e:
            logger.warning(f"Error buscando en AZLyrics: {e}")
            return None

    def _search_lyrics_ovh(self, artist: str, title: str) -> Optional[Dict[str, Any]]:
        """
        Buscar letras usando la API de lyrics.ovh
        """
        try:
            self._rate_limit()

            url = f"https://api.lyrics.ovh/v1/{urllib.parse.quote(artist)}/{urllib.parse.quote(title)}"

            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'lyrics' in data and data['lyrics']:
                    return {
                        'lyrics': data['lyrics'].strip(),
                        'source': 'lyrics.ovh',
                        'url': None,
                        'confidence': 'medium'
                    }

        except Exception as e:
            logger.warning(f"Error buscando en lyrics.ovh: {e}")

        return None

    def _search_musixmatch(self, artist: str, title: str) -> Optional[Dict[str, Any]]:
        """
        Buscar letras en Musixmatch
        Requiere API key para funcionalidad completa
        """
        try:
            self._rate_limit()

            # Musixmatch requiere API key para acceso completo
            # La versión gratuita tiene limitaciones
            logger.debug("Musixmatch requiere API key para búsqueda de letras")

            return None

        except Exception as e:
            logger.warning(f"Error buscando en Musixmatch: {e}")
            return None

    def _rate_limit(self):
        """Implementar rate limiting para las APIs"""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time

        if time_since_last < self._min_request_interval:
            sleep_time = self._min_request_interval - time_since_last
            time.sleep(sleep_time)

        self._last_request_time = time.time()

    def clean_lyrics(self, lyrics: str) -> str:
        """
        Limpiar y formatear letras

        Args:
            lyrics: Letras sin procesar

        Returns:
            Letras limpias y formateadas
        """
        if not lyrics:
            return ""

        # Limpiar líneas vacías múltiples
        lyrics = re.sub(r'\n\s*\n\s*\n', '\n\n', lyrics)

        # Limpiar espacios al inicio y final de líneas
        lines = [line.strip() for line in lyrics.split('\n')]
        lyrics = '\n'.join(lines)

        # Eliminar líneas que parecen ser metadata o publicidad
        lines = []
        for line in lyrics.split('\n'):
            line_lower = line.lower()
            # Filtrar líneas comunes de metadata
            if not any(phrase in line_lower for phrase in [
                'lyrics provided by', 'powered by', 'visit', 'copyright',
                'all rights reserved', 'unauthorized reproduction'
            ]):
                lines.append(line)

        return '\n'.join(lines).strip()

    def format_lyrics_for_web(self, lyrics: str) -> str:
        """
        Formatear letras para mostrar en web

        Args:
            lyrics: Letras limpias

        Returns:
            Letras formateadas para HTML
        """
        if not lyrics:
            return "<p>Letras no disponibles</p>"

        # Escapar HTML básico
        import html
        lyrics = html.escape(lyrics)

        # Convertir saltos de línea a <br>
        lyrics = lyrics.replace('\n\n', '</p><p>').replace('\n', '<br>')

        # Envolver en párrafos
        return f"<p>{lyrics}</p>"

    def get_lyrics_sources_info(self) -> Dict[str, Dict[str, str]]:
        """
        Obtener información sobre las fuentes de letras disponibles

        Returns:
            Diccionario con información de fuentes
        """
        return {
            'lyrics_ovh': {
                'name': 'Lyrics.ovh',
                'description': 'API gratuita de letras',
                'website': 'https://lyrics.ovh',
                'requires_key': False,
                'status': 'available'
            },
            'genius': {
                'name': 'Genius',
                'description': 'Base de datos de letras y anotaciones',
                'website': 'https://genius.com',
                'requires_key': True,
                'status': 'requires_api_key'
            },
            'musixmatch': {
                'name': 'Musixmatch',
                'description': 'Plataforma global de letras',
                'website': 'https://www.musixmatch.com',
                'requires_key': True,
                'status': 'requires_api_key'
            },
            'azlyrics': {
                'name': 'AZLyrics',
                'description': 'Base de datos de letras',
                'website': 'https://www.azlyrics.com',
                'requires_key': False,
                'status': 'scraping_restricted'
            }
        }
