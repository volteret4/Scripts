import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
import mutagen
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
import pylast
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv
import argparse

load_dotenv()

class MusicLibraryManager:
    def __init__(self, root_path: str, db_path: str):
        self.root_path = Path(root_path).resolve()
        self.db_path = Path(db_path).resolve()
        self.supported_formats = ('.mp3', '.flac', '.m4a', '.wav')
        
        # Logging configuration
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # LastFM initialization
        self.network = pylast.LastFMNetwork(
            api_key=os.getenv("LASTFM_API_KEY")
        )
        
        # Initialize database
        self.init_database()

    def init_database(self):
        """Initialize SQLite database with comprehensive tables."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Songs table
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
                last_modified TIMESTAMP,
                duration REAL
            )
        ''')
        
        # Artists table with more comprehensive information
        c.execute('''
            CREATE TABLE IF NOT EXISTS artists (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE,
                bio TEXT,
                tags TEXT,
                similar_artists TEXT,
                last_updated TIMESTAMP,
                origin TEXT,
                formed_year INTEGER,
                total_albums INTEGER
            )
        ''')
        
        # Albums table
        c.execute('''
            CREATE TABLE IF NOT EXISTS albums (
                id INTEGER PRIMARY KEY,
                artist_id INTEGER,
                name TEXT,
                year TEXT,
                label TEXT,
                genre TEXT,
                total_tracks INTEGER,
                album_art_path TEXT,
                last_updated TIMESTAMP,
                FOREIGN KEY(artist_id) REFERENCES artists(id)
            )
        ''')
        
        # Genres table
        c.execute('''
            CREATE TABLE IF NOT EXISTS genres (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE,
                description TEXT,
                related_genres TEXT,
                origin_year INTEGER
            )
        ''')
        
        conn.commit()
        conn.close()

    def get_audio_metadata(self, file_path: Path) -> Optional[Dict]:
        """Extract comprehensive audio metadata."""
        try:
            audio = None
            audio_tech = None
            track_number = '0'
            
            # Handle different audio formats
            if file_path.suffix.lower() in ['.mp3', '.m4a']:
                audio = EasyID3(file_path)
                audio_tech = mutagen.File(file_path)
                track_number = audio.get('tracknumber', ['0'])[0].split('/')[0]
            elif file_path.suffix.lower() == '.flac':
                audio = FLAC(file_path)
                audio_tech = audio
                track_number = str(audio.get('tracknumber', ['0'])[0]).split('/')[0]
            
            if not audio or not audio_tech:
                return None

            metadata = {
                'file_path': str(file_path),
                'title': audio.get('title', ['Untitled'])[0],
                'track_number': int(track_number) if track_number.isdigit() else 0,
                'artist': audio.get('artist', ['Unknown Artist'])[0],
                'album_artist': audio.get('albumartist', [''])[0],
                'album': audio.get('album', ['Unknown Album'])[0],
                'date': audio.get('date', [''])[0],
                'genre': audio.get('genre', ['Unknown'])[0],
                'label': audio.get('organization', [''])[0],
                'mbid': audio.get('musicbrainz_trackid', [''])[0],
                'last_modified': datetime.fromtimestamp(os.path.getmtime(file_path))
            }

            # Technical information
            if hasattr(audio_tech, 'info'):
                metadata['bitrate'] = getattr(audio_tech.info, 'bitrate', 0)
                metadata['sample_rate'] = getattr(audio_tech.info, 'sample_rate', 0)
                metadata['bit_depth'] = getattr(audio_tech.info, 'bits_per_sample', 0)
                metadata['duration'] = getattr(audio_tech.info, 'length', 0)

            return metadata

        except Exception as e:
            self.logger.error(f"Metadata extraction error for {file_path}: {str(e)}")
            return None

    def get_lastfm_artist_info(self, artist_name: str) -> Optional[Dict]:
        """Retrieve comprehensive LastFM artist information."""
        try:
            artist = self.network.get_artist(artist_name)
            
            return {
                'name': artist_name,
                'bio': artist.get_bio_summary(),
                'tags': json.dumps([tag.item.name for tag in artist.get_top_tags()]),
                'similar_artists': json.dumps([similar.item.name for similar in artist.get_similar()]),
                'last_updated': datetime.now(),
                'origin': None,  # LastFM doesn't directly provide this
                'formed_year': None  # LastFM doesn't directly provide this
            }
        except Exception as e:
            self.logger.error(f"LastFM artist info error for {artist_name}: {str(e)}")
            return None

    def scan_library(self, force_update=False):
        """Comprehensive library scanning with selective updates."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        error_log_path = self.root_path / 'music_library_scan_errors.log'
        error_logger = logging.getLogger('error_log')
        error_logger.setLevel(logging.ERROR)
        error_handler = logging.FileHandler(error_log_path, encoding='utf-8')
        error_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        error_handler.setFormatter(error_formatter)
        error_logger.addHandler(error_handler)
        
        processed_files = 0
        error_files = 0
        
        try:
            for file_path in self.root_path.rglob('*'):
                if file_path.suffix.lower() in self.supported_formats:
                    abs_path = str(file_path.absolute())
                    
                    try:
                        last_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
                        
                        # Check if file needs processing
                        c.execute("SELECT last_modified FROM songs WHERE file_path = ?", (abs_path,))
                        existing_record = c.fetchone()
                        
                        if force_update or not existing_record or last_modified > existing_record[0]:
                            metadata = self.get_audio_metadata(file_path)
                            
                            if metadata:
                                # Insert or update song
                                c.execute('''
                                    INSERT OR REPLACE INTO songs 
                                    (file_path, title, track_number, artist, album_artist, 
                                    album, date, genre, label, mbid, bitrate, 
                                    bit_depth, sample_rate, last_modified, duration)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                ''', (
                                    metadata['file_path'], metadata['title'], metadata['track_number'], 
                                    metadata['artist'], metadata['album_artist'], metadata['album'], 
                                    metadata['date'], metadata['genre'], metadata['label'], 
                                    metadata['mbid'], metadata.get('bitrate'), metadata.get('bit_depth'),
                                    metadata.get('sample_rate'), metadata['last_modified'], 
                                    metadata.get('duration')
                                ))
                                processed_files += 1
                                
                                # Update/insert artist information
                                self._update_artist_info(c, metadata['artist'])
                                
                                # Update/insert album information
                                self._update_album_info(c, metadata)
                                
                                # Update/insert genre information
                                self._update_genre_info(c, metadata['genre'])
                            
                            else:
                                error_files += 1
                                error_logger.error(f"Metadata extraction failed: {abs_path}")
                        
                        conn.commit()
                    
                    except Exception as file_error:
                        error_files += 1
                        error_logger.error(f"File processing error {abs_path}: {str(file_error)}")
        
        except Exception as scan_error:
            self.logger.error(f"Library scan error: {str(scan_error)}")
        
        finally:
            conn.close()
            error_logger.removeHandler(error_handler)
            error_handler.close()
            
            self.logger.info("Library scan completed")
            self.logger.info(f"Files processed: {processed_files}")
            self.logger.info(f"Files with errors: {error_files}")

    def _update_artist_info(self, cursor, artist_name):
        """Update artist information selectively."""
        cursor.execute("SELECT last_updated FROM artists WHERE name = ?", (artist_name,))
        existing_artist = cursor.fetchone()
        
        # Only update if no existing record or older than 30 days
        if not existing_artist or (datetime.now() - datetime.strptime(existing_artist[0], '%Y-%m-%d %H:%M:%S.%f')) > timedelta(days=30):
            lastfm_info = self.get_lastfm_artist_info(artist_name)
            
            if lastfm_info:
                cursor.execute('''
                    INSERT OR REPLACE INTO artists 
                    (name, bio, tags, similar_artists, last_updated)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    lastfm_info['name'], lastfm_info['bio'], 
                    lastfm_info['tags'], lastfm_info['similar_artists'], 
                    lastfm_info['last_updated']
                ))

    def _update_album_info(self, cursor, metadata):
        """Update album information selectively."""
        cursor.execute('''
            INSERT OR REPLACE INTO albums 
            (artist_id, name, year, label, genre, last_updated)
            VALUES (
                (SELECT id FROM artists WHERE name = ?),
                ?, ?, ?, ?, ?
            )
        ''', (
            metadata['artist'], metadata['album'], 
            metadata['date'], metadata['label'], 
            metadata['genre'], datetime.now()
        ))

    def _update_genre_info(self, cursor, genre_name):
        """Update genre information if not exists."""
        cursor.execute("SELECT * FROM genres WHERE name = ?", (genre_name,))
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO genres (name) VALUES (?)
            ''', (genre_name,))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Music Library Manager')
    parser.add_argument('root_path', help='Root directory of music library')
    parser.add_argument('db_path', help='Path to SQLite database')
    parser.add_argument('--force-update', action='store_true', help='Force update all files')
    
    args = parser.parse_args()
    
    manager = MusicLibraryManager(args.root_path, args.db_path)
    manager.scan_library(force_update=args.force_update)