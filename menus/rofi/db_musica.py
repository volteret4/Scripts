import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
import mutagen
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
import pylast  # Para LastFM
import sqlite3
from datetime import datetime
from dotenv import load_dotenv


load_dotenv()

lastfm_api_key = os.getenv("LASTFM_API_KEY")
#lastfm_secret = os.getenv("LASTFM_SECRET")


class MusicLibraryManager:
    def __init__(self, root_path: str, db_path: str):
        self.root_path = Path(root_path).resolve()
        self.db_path = Path(db_path).resolve()
        self.supported_formats = ('.mp3', '.flac', '.m4a', '.wav')
        
        # Configurar logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Inicializar LastFM
        self.network = pylast.LastFMNetwork(
            api_key=lastfm_api_key,
            #api_secret=lastfm_api_secret
        )
        
        # Inicializar base de datos
        self.init_database()

    def init_database(self):
        """Inicializa la base de datos SQLite con las tablas necesarias."""
        self.logger.info("Inicializando base de datos...")
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Tabla de canciones
        c.execute('''
            CREATE TABLE IF NOT EXISTS songs (
                id INTEGER PRIMARY KEY,
                file_path TEXT UNIQUE,
                title TEXT,
                track_number INTEGER,
                artist TEXT,
                album_artist TEXT,
                album TEXT,
                date TEXT,
                genre TEXT,
                label TEXT,
                mbid TEXT,
                bitrate INTEGER,
                bit_depth INTEGER,
                sample_rate INTEGER,
                last_modified TIMESTAMP
            )
        ''')
        
        # Tabla de información de artistas (LastFM)
        c.execute('''
            CREATE TABLE IF NOT EXISTS artist_info (
                artist TEXT PRIMARY KEY,
                bio TEXT,
                tags TEXT,
                similar_artists TEXT,
                last_updated TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()

    def get_audio_metadata(self, file_path: Path) -> Optional[Dict]:
        """Extrae metadata de un archivo de audio."""
        try:
            if file_path.suffix.lower() == '.mp3':
                audio = EasyID3(file_path)
                # Para obtener información técnica necesitamos también el objeto MP3
                audio_tech = mutagen.File(file_path)
                track_number = audio.get('tracknumber', ['0'])[0].split('/')[0]
            elif file_path.suffix.lower() == '.flac':
                audio = FLAC(file_path)
                audio_tech = audio
                track_number = str(audio.get('tracknumber', ['0'])[0]).split('/')[0]
            else:
                self.logger.warning(f"Formato no soportado para metadata: {file_path}")
                return None

            metadata = {
                'file_path': str(file_path),
                'title': audio.get('title', [''])[0],
                'track_number': int(track_number) if track_number.isdigit() else 0,
                'artist': audio.get('artist', [''])[0],
                'album_artist': audio.get('albumartist', [''])[0],
                'album': audio.get('album', [''])[0],
                'date': audio.get('date', [''])[0],
                'genre': audio.get('genre', [''])[0],
                'label': audio.get('organization', [''])[0],
                'mbid': audio.get('musicbrainz_trackid', [''])[0],
                'last_modified': datetime.fromtimestamp(os.path.getmtime(file_path))
            }

            # Información técnica
            if hasattr(audio_tech, 'info'):
                metadata['bitrate'] = getattr(audio_tech.info, 'bitrate', 0)
                metadata['sample_rate'] = getattr(audio_tech.info, 'sample_rate', 0)
                metadata['bit_depth'] = getattr(audio_tech.info, 'bits_per_sample', 0)

            return metadata

        except Exception as e:
            self.logger.error(f"Error al procesar {file_path}: {str(e)}")
            return None

    def get_lastfm_artist_info(self, artist_name: str) -> Optional[Dict]:
        """Obtiene información del artista desde LastFM."""
        try:
            artist = self.network.get_artist(artist_name)
            bio = artist.get_bio_summary()
            tags = [tag.item.name for tag in artist.get_top_tags()]
            similar = [similar.item.name for similar in artist.get_similar()]
            
            return {
                'artist': artist_name,
                'bio': bio,
                'tags': json.dumps(tags),
                'similar_artists': json.dumps(similar),
                'last_updated': datetime.now()
            }
        except Exception as e:
            self.logger.error(f"Error obteniendo info de LastFM para {artist_name}: {str(e)}")
            return None

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
import mutagen
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
import pylast  # Para LastFM
import sqlite3
from datetime import datetime
from dotenv import load_dotenv


load_dotenv()

lastfm_api_key = os.getenv("LASTFM_API_KEY")
#lastfm_secret = os.getenv("LASTFM_SECRET")


class MusicLibraryManager:
    def __init__(self, root_path: str, db_path: str):
        self.root_path = Path(root_path).resolve()
        self.db_path = Path(db_path).resolve()
        self.supported_formats = ('.mp3', '.flac', '.m4a', '.wav')
        
        # Configurar logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Inicializar LastFM
        self.network = pylast.LastFMNetwork(
            api_key=lastfm_api_key,
            #api_secret=lastfm_api_secret
        )
        
        # Inicializar base de datos
        self.init_database()

    def init_database(self):
        """Inicializa la base de datos SQLite con las tablas necesarias."""
        self.logger.info("Inicializando base de datos...")
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Tabla de canciones
        c.execute('''
            CREATE TABLE IF NOT EXISTS songs (
                id INTEGER PRIMARY KEY,
                file_path TEXT UNIQUE,
                title TEXT,
                track_number INTEGER,
                artist TEXT,
                album_artist TEXT,
                album TEXT,
                date TEXT,
                genre TEXT,
                label TEXT,
                mbid TEXT,
                bitrate INTEGER,
                bit_depth INTEGER,
                sample_rate INTEGER,
                last_modified TIMESTAMP
            )
        ''')
        
        # Tabla de información de artistas (LastFM)
        c.execute('''
            CREATE TABLE IF NOT EXISTS artist_info (
                artist TEXT PRIMARY KEY,
                bio TEXT,
                tags TEXT,
                similar_artists TEXT,
                last_updated TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()

    def get_audio_metadata(self, file_path: Path) -> Optional[Dict]:
        """Extrae metadata de un archivo de audio."""
        try:
            if file_path.suffix.lower() == '.mp3':
                audio = EasyID3(file_path)
                # Para obtener información técnica necesitamos también el objeto MP3
                audio_tech = mutagen.File(file_path)
                track_number = audio.get('tracknumber', ['0'])[0].split('/')[0]
            elif file_path.suffix.lower() == '.flac':
                audio = FLAC(file_path)
                audio_tech = audio
                track_number = str(audio.get('tracknumber', ['0'])[0]).split('/')[0]
            else:
                self.logger.warning(f"Formato no soportado para metadata: {file_path}")
                return None

            metadata = {
                'file_path': str(file_path),
                'title': audio.get('title', [''])[0],
                'track_number': int(track_number) if track_number.isdigit() else 0,
                'artist': audio.get('artist', [''])[0],
                'album_artist': audio.get('albumartist', [''])[0],
                'album': audio.get('album', [''])[0],
                'date': audio.get('date', [''])[0],
                'genre': audio.get('genre', [''])[0],
                'label': audio.get('organization', [''])[0],
                'mbid': audio.get('musicbrainz_trackid', [''])[0],
                'last_modified': datetime.fromtimestamp(os.path.getmtime(file_path))
            }

            # Información técnica
            if hasattr(audio_tech, 'info'):
                metadata['bitrate'] = getattr(audio_tech.info, 'bitrate', 0)
                metadata['sample_rate'] = getattr(audio_tech.info, 'sample_rate', 0)
                metadata['bit_depth'] = getattr(audio_tech.info, 'bits_per_sample', 0)

            return metadata

        except Exception as e:
            self.logger.error(f"Error al procesar {file_path}: {str(e)}")
            return None

    def get_lastfm_artist_info(self, artist_name: str) -> Optional[Dict]:
        """Obtiene información del artista desde LastFM."""
        try:
            artist = self.network.get_artist(artist_name)
            bio = artist.get_bio_summary()
            tags = [tag.item.name for tag in artist.get_top_tags()]
            similar = [similar.item.name for similar in artist.get_similar()]
            
            return {
                'artist': artist_name,
                'bio': bio,
                'tags': json.dumps(tags),
                'similar_artists': json.dumps(similar),
                'last_updated': datetime.now()
            }
        except Exception as e:
            self.logger.error(f"Error obteniendo info de LastFM para {artist_name}: {str(e)}")
            return None

    def scan_library(self):
        """Escanea la biblioteca y actualiza la base de datos, manejando errores de permisos."""
        # Configurar logging de archivos erróneos
        error_log_path = self.root_path / 'music_library_scan_errors.log'
        error_logger = logging.getLogger('error_log')
        error_logger.setLevel(logging.ERROR)
        error_handler = logging.FileHandler(error_log_path, encoding='utf-8')
        error_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        error_handler.setFormatter(error_formatter)
        error_logger.addHandler(error_handler)
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Obtener archivos existentes en la base de datos
        c.execute("SELECT file_path, last_modified FROM songs")
        existing_files = {row[0]: row[1] for row in c.fetchall()}
        
        processed_files = 0
        error_files = 0
        permission_errors = 0
        
        try:
            for file_path in self.root_path.rglob('*'):
                if file_path.suffix.lower() in self.supported_formats:
                    abs_path = str(file_path.absolute())
                    
                    try:
                        # Verificar si el archivo es legible y accesible
                        try:
                            last_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
                        except PermissionError:
                            error_logger.error(f"Error de permisos: {abs_path}")
                            permission_errors += 1
                            continue
                        
                        # Verificar si el archivo es nuevo o ha sido modificado
                        if abs_path not in existing_files or last_modified > existing_files[abs_path]:
                            self.logger.info(f"Procesando: {abs_path}")
                            
                            # Intentar obtener metadata
                            metadata = self.get_audio_metadata(file_path)
                            
                            if metadata:
                                # Actualizar o insertar metadata de la canción
                                c.execute('''
                                    INSERT OR REPLACE INTO songs 
                                    (file_path, title, track_number, artist, album_artist, album, date, genre, 
                                    label, mbid, bitrate, bit_depth, sample_rate, last_modified)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                ''', (
                                    metadata['file_path'], metadata['title'], metadata['track_number'], metadata['artist'],
                                    metadata['album_artist'], metadata['album'], metadata['date'],
                                    metadata['genre'], metadata['label'], metadata['mbid'],
                                    metadata.get('bitrate'), metadata.get('bit_depth'),
                                    metadata.get('sample_rate'), metadata['last_modified']
                                ))
                                processed_files += 1
                                
                                # Actualizar información del artista si es necesario
                                if metadata['artist']:
                                    c.execute(
                                        "SELECT last_updated FROM artist_info WHERE artist = ?",
                                        (metadata['artist'],)
                                    )
                                    artist_info = c.fetchone()
                                    
                                    # Actualizar info del artista si no existe o tiene más de 30 días
                                    if not artist_info:
                                        lastfm_info = self.get_lastfm_artist_info(metadata['artist'])
                                        if lastfm_info:
                                            c.execute('''
                                                INSERT OR REPLACE INTO artist_info
                                                (artist, bio, tags, similar_artists, last_updated)
                                                VALUES (?, ?, ?, ?, ?)
                                            ''', (
                                                lastfm_info['artist'], lastfm_info['bio'],
                                                lastfm_info['tags'], lastfm_info['similar_artists'],
                                                lastfm_info['last_updated']
                                            ))
                            else:
                                # No se pudo obtener metadata
                                error_files += 1
                                error_logger.error(f"No se pudo procesar el archivo: {abs_path}")
                        
                        conn.commit()
                    
                    except Exception as file_error:
                        # Capturar cualquier otro error específico del archivo
                        error_files += 1
                        error_logger.error(f"Error procesando {abs_path}: {str(file_error)}")
                        continue
        
        except Exception as scan_error:
            self.logger.error(f"Error durante el escaneo: {str(scan_error)}")
        
        finally:
            conn.close()
            # Cerrar el manejador de logging de errores
            error_logger.removeHandler(error_handler)
            error_handler.close()
            
            # Resumen del escaneo
            self.logger.info(f"Escaneo de biblioteca completado")
            self.logger.info(f"Archivos procesados: {processed_files}")
            self.logger.info(f"Archivos con errores de procesamiento: {error_files}")
            self.logger.info(f"Archivos con errores de permisos: {permission_errors}")
            self.logger.info(f"Log de errores guardado en: {error_log_path}")

    def query_by_artist(self, artist: str) -> List[Dict]:
        """Obtiene todos los álbumes de un artista."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            SELECT DISTINCT album, date, label
            FROM songs
            WHERE artist LIKE ?
            ORDER BY date
        ''', (f"%{artist}%",))
        
        albums = [{
            'album': row[0],
            'date': row[1],
            'label': row[2]
        } for row in c.fetchall()]
        
        conn.close()
        return albums

    def query_by_album(self, album: str) -> Dict:
        """Obtiene información detallada de un álbum."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            SELECT title, track_number, artist, album_artist, date, genre, label,
                   bitrate, bit_depth, sample_rate
            FROM songs
            WHERE album LIKE ?
        ''', (f"%{album}%",))
        
        songs = [{
            'title': row[0],
            'artist': row[1],
            'album_artist': row[2],
            'date': row[3],
            'genre': row[4],
            'label': row[5],
            'bitrate': row[6],
            'bit_depth': row[7],
            'sample_rate': row[8],
            'track_number': row[9]
        } for row in c.fetchall()]
        
        conn.close()
        return {
            'album': album,
            'songs': songs
        }

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Gestor de biblioteca musical')
    parser.add_argument('root_path', help='Ruta a la carpeta raíz de la biblioteca')
    parser.add_argument('db_path', help='Ruta para la base de datos SQLite')
    # parser.add_argument('--lastfm-key', required=True, help='API Key de LastFM')
    # parser.add_argument('--lastfm-secret', required=True, help='API Secret de LastFM')
    
    args = parser.parse_args()
    
    manager = MusicLibraryManager(
        args.root_path,
        args.db_path
        # args.lastfm_key,
        # args.lastfm_secret
    )
    
    manager.scan_library()



