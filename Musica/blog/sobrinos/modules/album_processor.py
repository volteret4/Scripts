"""
Módulo para procesamiento de álbumes
Extrae información de archivos de música usando mutagen
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
import mimetypes

try:
    from mutagen import File
    from mutagen.id3 import ID3NoHeaderError
except ImportError:
    print("Error: mutagen no está instalado. Instala con: pip install mutagen")
    exit(1)

logger = logging.getLogger(__name__)


class AlbumProcessor:
    """Procesador de álbumes para extraer metadatos"""

    def __init__(self):
        """Inicializar procesador"""
        # Extensiones de audio soportadas
        self.audio_extensions = {
            '.mp3', '.flac', '.m4a', '.aac', '.ogg', '.wma',
            '.wav', '.opus', '.mp4', '.m4p', '.m4b'
        }

    def extract_album_info(self, folder_path: str) -> Dict[str, Any]:
        """
        Extraer información completa del álbum

        Args:
            folder_path: Ruta a la carpeta del álbum

        Returns:
            Diccionario con información del álbum
        """
        folder_path = Path(folder_path)

        # Encontrar archivos de audio
        audio_files = self._find_audio_files(folder_path)

        if not audio_files:
            raise ValueError("No se encontraron archivos de audio en la carpeta")

        # Extraer información básica
        album_info = self._extract_basic_info(audio_files)

        # Extraer lista de pistas
        album_info['tracks'] = self._extract_tracks_info(audio_files)

        # Buscar archivos de portada
        album_info['local_cover'] = self._find_local_cover(folder_path)

        logger.info(f"Información extraída: {album_info['artist']} - {album_info['title']}")
        return album_info

    def _find_audio_files(self, folder_path: Path) -> List[Path]:
        """
        Encontrar archivos de audio en la carpeta

        Args:
            folder_path: Ruta a la carpeta

        Returns:
            Lista de archivos de audio
        """
        audio_files = []

        for file_path in folder_path.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in self.audio_extensions:
                audio_files.append(file_path)

        # Ordenar por nombre para mantener orden consistente
        audio_files.sort()

        logger.debug(f"Encontrados {len(audio_files)} archivos de audio")
        return audio_files

    def _extract_basic_info(self, audio_files: List[Path]) -> Dict[str, Any]:
        """
        Extraer información básica del álbum del primer archivo válido

        Args:
            audio_files: Lista de archivos de audio

        Returns:
            Diccionario con información básica
        """
        album_info = {
            'title': 'Álbum Desconocido',
            'artist': 'Artista Desconocido',
            'album_artist': None,
            'date': None,
            'year': None,
            'genre': [],
            'label': None,
            'mbid': None,
            'mbid_album': None,
            'total_tracks': 0,
            'total_discs': 1
        }

        # Intentar extraer información del primer archivo
        for file_path in audio_files:
            try:
                audio_file = File(file_path)
                if audio_file is None:
                    continue

                tags = audio_file.tags
                if tags is None:
                    continue

                # Extraer información básica
                album_info['title'] = self._get_tag_value(tags, ['TALB', 'album', 'ALBUM']) or album_info['title']
                album_info['artist'] = self._get_tag_value(tags, ['TPE1', 'artist', 'ARTIST']) or album_info['artist']
                album_info['album_artist'] = self._get_tag_value(tags, ['TPE2', 'albumartist', 'ALBUMARTIST'])
                album_info['date'] = self._get_tag_value(tags, ['TDRC', 'date', 'DATE'])
                album_info['year'] = self._get_tag_value(tags, ['TYER', 'year', 'YEAR'])
                album_info['label'] = self._get_tag_value(tags, ['TPUB', 'label', 'LABEL'])

                # Géneros (pueden ser múltiples)
                genre_value = self._get_tag_value(tags, ['TCON', 'genre', 'GENRE'])
                if genre_value:
                    if isinstance(genre_value, list):
                        album_info['genre'] = genre_value
                    else:
                        album_info['genre'] = [g.strip() for g in str(genre_value).split(';')]

                # MusicBrainz IDs
                album_info['mbid'] = self._get_tag_value(tags, ['TXXX:MusicBrainz Artist Id', 'musicbrainz_artistid'])
                album_info['mbid_album'] = self._get_tag_value(tags, ['TXXX:MusicBrainz Album Id', 'musicbrainz_albumid'])

                # Total de pistas y discos
                total_tracks = self._get_tag_value(tags, ['TRCK', 'track', 'TRACK'])
                if total_tracks and '/' in str(total_tracks):
                    album_info['total_tracks'] = int(str(total_tracks).split('/')[1])

                total_discs = self._get_tag_value(tags, ['TPOS', 'disc', 'DISC'])
                if total_discs and '/' in str(total_discs):
                    album_info['total_discs'] = int(str(total_discs).split('/')[1])

                # Si encontramos información válida, usamos este archivo como referencia
                if album_info['title'] != 'Álbum Desconocido':
                    break

            except Exception as e:
                logger.warning(f"Error procesando {file_path}: {e}")
                continue

        # Si no se encontró total de pistas, usar el número de archivos
        if album_info['total_tracks'] == 0:
            album_info['total_tracks'] = len(audio_files)

        return album_info

    def _extract_tracks_info(self, audio_files: List[Path]) -> List[Dict[str, Any]]:
        """
        Extraer información de todas las pistas

        Args:
            audio_files: Lista de archivos de audio

        Returns:
            Lista con información de pistas
        """
        tracks = []

        for file_path in audio_files:
            try:
                audio_file = File(file_path)
                if audio_file is None:
                    continue

                tags = audio_file.tags
                track_info = {
                    'filename': file_path.name,
                    'title': 'Pista Sin Título',
                    'artist': None,
                    'track_number': 0,
                    'disc_number': 1,
                    'duration': getattr(audio_file.info, 'length', 0),
                    'mbid': None
                }

                if tags:
                    track_info['title'] = self._get_tag_value(tags, ['TIT2', 'title', 'TITLE']) or track_info['title']
                    track_info['artist'] = self._get_tag_value(tags, ['TPE1', 'artist', 'ARTIST'])

                    # Número de pista
                    track_num = self._get_tag_value(tags, ['TRCK', 'track', 'TRACK'])
                    if track_num:
                        try:
                            track_info['track_number'] = int(str(track_num).split('/')[0])
                        except (ValueError, IndexError):
                            pass

                    # Número de disco
                    disc_num = self._get_tag_value(tags, ['TPOS', 'disc', 'DISC'])
                    if disc_num:
                        try:
                            track_info['disc_number'] = int(str(disc_num).split('/')[0])
                        except (ValueError, IndexError):
                            pass

                    # MusicBrainz ID de la pista
                    track_info['mbid'] = self._get_tag_value(tags, ['TXXX:MusicBrainz Track Id', 'musicbrainz_trackid'])

                tracks.append(track_info)

            except Exception as e:
                logger.warning(f"Error procesando pista {file_path}: {e}")
                continue

        # Ordenar por disco y número de pista
        tracks.sort(key=lambda t: (t['disc_number'], t['track_number'], t['filename']))

        logger.debug(f"Extraída información de {len(tracks)} pistas")
        return tracks

    def _get_tag_value(self, tags: Any, possible_keys: List[str]) -> Optional[str]:
        """
        Obtener valor de una etiqueta probando múltiples claves

        Args:
            tags: Objeto de etiquetas del archivo
            possible_keys: Lista de claves posibles

        Returns:
            Valor encontrado o None
        """
        for key in possible_keys:
            try:
                if hasattr(tags, 'get'):
                    value = tags.get(key)
                else:
                    value = tags.get(key, [None])[0] if key in tags else None

                if value is not None:
                    if isinstance(value, list) and len(value) > 0:
                        return str(value[0])
                    elif hasattr(value, 'text') and value.text:
                        return str(value.text[0]) if isinstance(value.text, list) else str(value.text)
                    elif value:
                        return str(value)
            except (AttributeError, IndexError, KeyError):
                continue

        return None

    def _find_local_cover(self, folder_path: Path) -> Optional[str]:
        """
        Buscar archivo de portada local en la carpeta

        Args:
            folder_path: Ruta a la carpeta del álbum

        Returns:
            Ruta al archivo de portada o None
        """
        # Nombres comunes de archivos de portada
        cover_names = [
            'cover', 'folder', 'front', 'album', 'albumart',
            'Cover', 'Folder', 'Front', 'Album', 'AlbumArt'
        ]

        # Extensiones de imagen
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp']

        # Buscar archivos de portada
        for cover_name in cover_names:
            for ext in image_extensions:
                cover_path = folder_path / f"{cover_name}{ext}"
                if cover_path.exists():
                    logger.debug(f"Portada local encontrada: {cover_path}")
                    return str(cover_path)

        # Buscar cualquier imagen en la carpeta
        for file_path in folder_path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in image_extensions:
                logger.debug(f"Imagen encontrada: {file_path}")
                return str(file_path)

        return None

    def format_duration(self, seconds: float) -> str:
        """
        Formatear duración en formato MM:SS

        Args:
            seconds: Duración en segundos

        Returns:
            Duración formateada
        """
        if not seconds or seconds <= 0:
            return "0:00"

        minutes = int(seconds // 60)
        seconds = int(seconds % 60)

        return f"{minutes}:{seconds:02d}"
