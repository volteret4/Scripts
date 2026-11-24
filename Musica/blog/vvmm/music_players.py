#!/usr/bin/env python3
"""
Módulo de detección de reproductores de música
Soporta: Airsonic/Subsonic, Spotify Web API, playerctl (reproductores locales)
"""

import os
import logging
import subprocess
from typing import Dict, Optional, List
from abc import ABC, abstractmethod
import hashlib
import requests


class MusicPlayer(ABC):
    """Clase base para reproductores de música"""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    @abstractmethod
    def is_available(self) -> bool:
        """Verificar si el reproductor está disponible"""
        pass

    @abstractmethod
    def get_now_playing(self) -> Optional[Dict[str, str]]:
        """Obtener metadata de la canción en reproducción"""
        pass


class AirsonicPlayer(MusicPlayer):
    """Reproductor Airsonic/Subsonic/Navidrome"""

    def __init__(self, logger: logging.Logger):
        super().__init__(logger)
        self.enabled = os.getenv('AIRSONIC_ENABLED', 'false').lower() == 'true'
        self.url = os.getenv('AIRSONIC_URL', '').rstrip('/')
        self.username = os.getenv('AIRSONIC_USERNAME', '')
        self.password = os.getenv('AIRSONIC_PASSWORD', '')
        self.token = os.getenv('AIRSONIC_TOKEN', '')
        self.client = os.getenv('AIRSONIC_CLIENT', 'VVMM_Post_Creator')
        self.api_version = '1.16.1'

    def _get_auth_params(self) -> Dict[str, str]:
        """Generar parámetros de autenticación"""
        params = {
            'u': self.username,
            'c': self.client,
            'v': self.api_version,
            'f': 'json'
        }

        # Preferir token si está disponible
        if self.token:
            params['t'] = self.token
            # Generar salt aleatorio
            import random
            import string
            salt = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
            params['s'] = salt
        else:
            # Usar password con MD5
            import random
            import string
            salt = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
            token = hashlib.md5((self.password + salt).encode()).hexdigest()
            params['t'] = token
            params['s'] = salt

        return params

    def is_available(self) -> bool:
        """Verificar si Airsonic está disponible"""
        if not self.enabled or not self.url or not self.username:
            return False

        if not self.token and not self.password:
            self.logger.warning("Airsonic: No hay token ni password configurado")
            return False

        try:
            # Ping al servidor
            params = self._get_auth_params()
            response = requests.get(
                f"{self.url}/rest/ping",
                params=params,
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('subsonic-response', {}).get('status') == 'ok':
                    self.logger.debug("Airsonic: Servidor disponible")
                    return True
        except Exception as e:
            self.logger.debug(f"Airsonic no disponible: {e}")

        return False

    def get_now_playing(self) -> Optional[Dict[str, str]]:
        """Obtener canción en reproducción desde Airsonic"""
        try:
            params = self._get_auth_params()
            response = requests.get(
                f"{self.url}/rest/getNowPlaying",
                params=params,
                timeout=10
            )

            if response.status_code != 200:
                self.logger.warning(f"Airsonic: Error HTTP {response.status_code}")
                return None

            data = response.json()
            subsonic_response = data.get('subsonic-response', {})

            if subsonic_response.get('status') != 'ok':
                error = subsonic_response.get('error', {})
                self.logger.warning(f"Airsonic: Error en respuesta - {error}")
                return None

            now_playing = subsonic_response.get('nowPlaying', {}).get('entry', [])

            if not now_playing:
                self.logger.info("Airsonic: No hay música reproduciéndose")
                return None

            # Tomar el primer elemento (el más reciente)
            song = now_playing[0] if isinstance(now_playing, list) else now_playing

            # Extraer metadata
            metadata = {
                'source': 'airsonic',
                'artist_raw': song.get('artist', ''),
                'album_raw': song.get('album', ''),
                'title_raw': song.get('title', ''),
                'year': str(song.get('year', '')),
                'genre': song.get('genre', ''),
                'track_number': str(song.get('track', '')),
                'disc_number': str(song.get('discNumber', 1)),
                'duration': str(song.get('duration', 0)),
                'bitrate': str(song.get('bitRate', '')),
                'player': song.get('username', 'airsonic'),
                'cover_art_id': song.get('coverArt', ''),
            }

            # Validar que tengamos información mínima
            if not metadata['artist_raw'] or not metadata['title_raw']:
                self.logger.warning("Airsonic: Metadata incompleta")
                return None

            # Si no hay álbum, usar título
            if not metadata['album_raw']:
                metadata['album_raw'] = metadata['title_raw']

            self.logger.info(f"✅ Airsonic: {metadata['artist_raw']} - {metadata['title_raw']}")
            return metadata

        except Exception as e:
            self.logger.error(f"Error obteniendo música de Airsonic: {e}")
            return None

    def get_cover_art_url(self, cover_art_id: str) -> Optional[str]:
        """Obtener URL de la carátula del álbum"""
        if not cover_art_id:
            return None

        try:
            params = self._get_auth_params()
            params['id'] = cover_art_id
            params['size'] = '500'  # Tamaño de la imagen

            # Construir URL de la carátula
            param_str = '&'.join([f"{k}={v}" for k, v in params.items()])
            return f"{self.url}/rest/getCoverArt?{param_str}"
        except Exception as e:
            self.logger.error(f"Error generando URL de carátula: {e}")
            return None


class SpotifyWebPlayer(MusicPlayer):
    """Reproductor Spotify Web API (detección de reproducción actual)"""

    def __init__(self, logger: logging.Logger):
        super().__init__(logger)
        self.enabled = os.getenv('SPOTIFY_DETECT_ENABLED', 'false').lower() == 'true'

        if not self.enabled:
            return

        try:
            import spotipy
            from spotipy.oauth2 import SpotifyOAuth

            self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
                client_id=os.getenv('SPOTIFY_CLIENT'),
                client_secret=os.getenv('SPOTIFY_SECRET'),
                redirect_uri=os.getenv('SPOTIFY_REDIRECT_URI', 'http://localhost:8888/callback'),
                scope='user-read-currently-playing user-read-playback-state'
            ))
        except ImportError:
            self.logger.warning("Spotipy no instalado para detección de Spotify")
            self.enabled = False
        except Exception as e:
            self.logger.warning(f"Error inicializando Spotify Web API: {e}")
            self.enabled = False

    def is_available(self) -> bool:
        """Verificar si Spotify Web API está disponible"""
        return self.enabled and hasattr(self, 'sp')

    def get_now_playing(self) -> Optional[Dict[str, str]]:
        """Obtener canción en reproducción desde Spotify"""
        if not self.is_available():
            return None

        try:
            current = self.sp.current_playback()

            if not current or not current.get('is_playing'):
                self.logger.info("Spotify: No hay música reproduciéndose")
                return None

            item = current.get('item', {})

            metadata = {
                'source': 'spotify_web',
                'artist_raw': ', '.join([artist['name'] for artist in item.get('artists', [])]),
                'album_raw': item.get('album', {}).get('name', ''),
                'title_raw': item.get('name', ''),
                'year': item.get('album', {}).get('release_date', '')[:4],
                'duration': str(item.get('duration_ms', 0) // 1000),
                'track_number': str(item.get('track_number', '')),
                'disc_number': str(item.get('disc_number', 1)),
                'spotify_uri': item.get('uri', ''),
                'player': current.get('device', {}).get('name', 'spotify'),
            }

            if not metadata['artist_raw'] or not metadata['title_raw']:
                return None

            self.logger.info(f"✅ Spotify Web: {metadata['artist_raw']} - {metadata['title_raw']}")
            return metadata

        except Exception as e:
            self.logger.error(f"Error obteniendo música de Spotify Web: {e}")
            return None


class PlayerctlPlayer(MusicPlayer):
    """Reproductores locales vía playerctl (deadbeef, VLC, etc.)"""

    def is_available(self) -> bool:
        """Verificar si playerctl está disponible"""
        try:
            result = subprocess.run(
                ['playerctl', '-l'],
                capture_output=True,
                text=True,
                check=True
            )
            players = result.stdout.strip().split('\n')
            return bool(players and players != [''])
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def get_now_playing(self) -> Optional[Dict[str, str]]:
        """Obtener canción en reproducción desde playerctl"""
        try:
            # Obtener reproductores disponibles
            result = subprocess.run(
                ['playerctl', '-l'],
                capture_output=True,
                text=True,
                check=True
            )
            players = result.stdout.strip().split('\n')

            if not players or players == ['']:
                return None

            # Buscar reproductor activo
            active_player = None
            for player in players:
                try:
                    status = subprocess.run(
                        ['playerctl', '-p', player, 'status'],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    if status.stdout.strip() == 'Playing':
                        active_player = player
                        break
                except subprocess.CalledProcessError:
                    continue

            if not active_player:
                active_player = players[0]

            # Obtener metadata
            def get_metadata(field):
                try:
                    result = subprocess.run(
                        ['playerctl', '-p', active_player, 'metadata', field],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    return result.stdout.strip().replace('"', '').replace(':', '')
                except subprocess.CalledProcessError:
                    return ""

            artist = get_metadata('artist')
            album = get_metadata('album')
            title = get_metadata('title')

            if not artist or not title:
                return None

            if not album:
                album = title

            metadata = {
                'source': 'playerctl',
                'artist_raw': artist,
                'album_raw': album,
                'title_raw': title,
                'player': active_player,
            }

            self.logger.info(f"✅ Playerctl ({active_player}): {artist} - {title}")
            return metadata

        except Exception as e:
            self.logger.error(f"Error obteniendo música de playerctl: {e}")
            return None


class LastFMPlayer(MusicPlayer):
    """Detección vía Last.fm (último scrobble)"""

    def __init__(self, logger: logging.Logger):
        super().__init__(logger)
        self.enabled = os.getenv('LASTFM_ENABLED', 'false').lower() == 'true'
        self.api_key = os.getenv('LASTFM_API_KEY', '')
        self.username = os.getenv('LASTFM_USERNAME', '')

    def is_available(self) -> bool:
        """Verificar si Last.fm está disponible"""
        return self.enabled and bool(self.api_key) and bool(self.username)

    def get_now_playing(self) -> Optional[Dict[str, str]]:
        """Obtener última canción escuchada desde Last.fm"""
        if not self.is_available():
            return None

        try:
            url = "http://ws.audioscrobbler.com/2.0/"
            params = {
                'method': 'user.getrecenttracks',
                'user': self.username,
                'api_key': self.api_key,
                'format': 'json',
                'limit': 1
            }

            response = requests.get(url, params=params, timeout=10)

            if response.status_code != 200:
                return None

            data = response.json()
            tracks = data.get('recenttracks', {}).get('track', [])

            if not tracks:
                return None

            track = tracks[0] if isinstance(tracks, list) else tracks

            # Verificar si está sonando ahora
            if not track.get('@attr', {}).get('nowplaying'):
                self.logger.info("Last.fm: Último track no está sonando ahora")
                return None

            metadata = {
                'source': 'lastfm',
                'artist_raw': track.get('artist', {}).get('#text', ''),
                'album_raw': track.get('album', {}).get('#text', ''),
                'title_raw': track.get('name', ''),
                'player': 'last.fm',
            }

            if not metadata['artist_raw'] or not metadata['title_raw']:
                return None

            if not metadata['album_raw']:
                metadata['album_raw'] = metadata['title_raw']

            self.logger.info(f"✅ Last.fm: {metadata['artist_raw']} - {metadata['title_raw']}")
            return metadata

        except Exception as e:
            self.logger.error(f"Error obteniendo música de Last.fm: {e}")
            return None


class PlayerManager:
    """Gestor de reproductores de música"""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

        # Inicializar reproductores
        self.players: List[MusicPlayer] = [
            AirsonicPlayer(logger),
            SpotifyWebPlayer(logger),
            PlayerctlPlayer(logger),
            LastFMPlayer(logger),
        ]

        # Leer prioridad del .env
        priority_str = os.getenv('PLAYER_PRIORITY', 'airsonic,playerctl')
        self.priority = [p.strip() for p in priority_str.split(',')]

    def _sort_players_by_priority(self) -> List[MusicPlayer]:
        """Ordenar reproductores según prioridad configurada"""
        priority_map = {
            'airsonic': AirsonicPlayer,
            'spotify': SpotifyWebPlayer,
            'playerctl': PlayerctlPlayer,
            'lastfm': LastFMPlayer,
        }

        sorted_players = []

        # Añadir según prioridad
        for priority_name in self.priority:
            player_class = priority_map.get(priority_name.lower())
            if player_class:
                for player in self.players:
                    if isinstance(player, player_class):
                        sorted_players.append(player)
                        break

        # Añadir los que no están en la prioridad al final
        for player in self.players:
            if player not in sorted_players:
                sorted_players.append(player)

        return sorted_players

    def get_now_playing(self) -> Optional[Dict[str, str]]:
        """Obtener música en reproducción de cualquier fuente disponible"""
        self.logger.info("🔍 Detectando reproducción de música...")

        sorted_players = self._sort_players_by_priority()

        for player in sorted_players:
            player_name = player.__class__.__name__.replace('Player', '')

            if not player.is_available():
                self.logger.debug(f"⏭️  {player_name}: No disponible")
                continue

            self.logger.info(f"🎵 Intentando {player_name}...")
            metadata = player.get_now_playing()

            if metadata:
                self.logger.info(f"✅ Detectado desde {player_name}")
                return metadata

        self.logger.warning("❌ No se detectó música en reproducción en ninguna fuente")
        return None

    def get_available_players(self) -> List[str]:
        """Obtener lista de reproductores disponibles"""
        available = []
        for player in self.players:
            if player.is_available():
                player_name = player.__class__.__name__.replace('Player', '')
                available.append(player_name)
        return available
