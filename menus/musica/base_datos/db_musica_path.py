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
        self.supported_formats = ('.mp3', '.flac', '.m4a')
        
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
        
        # Check for existing tables
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [table[0] for table in c.fetchall()]
        
        # Songs table
        if 'songs' not in existing_tables:
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
                    added_timestamp TIMESTAMP,
                    added_week INTEGER,
                    added_month INTEGER,
                    added_year INTEGER,
                    duration REAL,
                    lyrics_id INTEGER
                )
            ''')
        
        # Check existing columns in songs table
        c.execute("PRAGMA table_info(songs)")
        columns = {col[1] for col in c.fetchall()}
        
        # Add new columns if they don't exist
        new_columns = {
            'added_timestamp': 'TIMESTAMP',
            'added_week': 'INTEGER',
            'added_month': 'INTEGER',
            'added_year': 'INTEGER',
            'duration': 'REAL',
            'lyrics_id': 'INTEGER',
            'replay_gain_track_gain': 'REAL',
            'replay_gain_track_peak': 'REAL',
            'replay_gain_album_gain': 'REAL',
            'replay_gain_album_peak': 'REAL'
        }
        
        for col_name, col_type in new_columns.items():
            if col_name not in columns:
                c.execute(f"ALTER TABLE songs ADD COLUMN {col_name} {col_type}")
        
        # Artists table
        if 'artists' not in existing_tables:
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
                    total_albums INTEGER,
                    spotify_url TEXT,
                    youtube_url TEXT,
                    musicbrainz_url TEXT,
                    discogs_url TEXT,
                    rateyourmusic_url TEXT,
                    links_updated TIMESTAMP,
                    wikipedia_url TEXT,
                    wikipedia_content TEXT,
                    wikipedia_updated TIMESTAMP
                )
            ''')
        
        # Check existing columns in artists table
        if 'artists' in existing_tables:
            c.execute("PRAGMA table_info(artists)")
            artist_columns = {col[1] for col in c.fetchall()}
            
            # Add new columns if they don't exist
            new_artist_columns = {
                'spotify_url': 'TEXT',
                'youtube_url': 'TEXT',
                'musicbrainz_url': 'TEXT',
                'discogs_url': 'TEXT',
                'rateyourmusic_url': 'TEXT',
                'links_updated': 'TIMESTAMP',
                'wikipedia_url': 'TEXT',
                'wikipedia_content': 'TEXT',
                'wikipedia_updated': 'TIMESTAMP'
            }
            
            for col_name, col_type in new_artist_columns.items():
                if col_name not in artist_columns:
                    c.execute(f"ALTER TABLE artists ADD COLUMN {col_name} {col_type}")
        
        # Albums table
        if 'albums' not in existing_tables:
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
                    spotify_url TEXT,
                    spotify_id TEXT,
                    youtube_url TEXT,
                    musicbrainz_url TEXT,
                    discogs_url TEXT,
                    rateyourmusic_url TEXT,
                    links_updated TIMESTAMP,
                    wikipedia_url TEXT,
                    wikipedia_content TEXT,
                    wikipedia_updated TIMESTAMP,
                    FOREIGN KEY(artist_id) REFERENCES artists(id),
                    UNIQUE(artist_id, name)
                )
            ''')
        
        # Check existing columns in albums table
        if 'albums' in existing_tables:
            c.execute("PRAGMA table_info(albums)")
            album_columns = {col[1] for col in c.fetchall()}
            
            # Add new columns if they don't exist
            new_album_columns = {
                'spotify_url': 'TEXT',
                'spotify_id': 'TEXT',
                'youtube_url': 'TEXT',
                'musicbrainz_url': 'TEXT',
                'discogs_url': 'TEXT',
                'rateyourmusic_url': 'TEXT',
                'links_updated': 'TIMESTAMP',
                'wikipedia_url': 'TEXT',
                'wikipedia_content': 'TEXT',
                'wikipedia_updated': 'TIMESTAMP'
            }
            
            for col_name, col_type in new_album_columns.items():
                if col_name not in album_columns:
                    c.execute(f"ALTER TABLE albums ADD COLUMN {col_name} {col_type}")
        
        # Genres table
        if 'genres' not in existing_tables:
            c.execute('''
                CREATE TABLE IF NOT EXISTS genres (
                    id INTEGER PRIMARY KEY,
                    name TEXT UNIQUE,
                    description TEXT,
                    related_genres TEXT,
                    origin_year INTEGER
                )
            ''')
        
        # Lyrics table
        if 'lyrics' not in existing_tables:
            c.execute('''
                CREATE TABLE IF NOT EXISTS lyrics (
                    id INTEGER PRIMARY KEY,
                    track_id INTEGER,
                    lyrics TEXT,
                    source TEXT DEFAULT 'Genius',
                    last_updated TIMESTAMP,
                    FOREIGN KEY(track_id) REFERENCES songs(id)
                )
            ''')
            
        # Song Links table - NUEVA TABLA para almacenar los enlaces a servicios de música
        if 'song_links' not in existing_tables:
            c.execute('''
                CREATE TABLE IF NOT EXISTS song_links (
                    id INTEGER PRIMARY KEY,
                    song_id INTEGER,
                    spotify_url TEXT,
                    spotify_id TEXT,
                    lastfm_url TEXT,
                    youtube_url TEXT,
                    deezer_url TEXT,
                    apple_music_url TEXT,
                    tidal_url TEXT,
                    bandcamp_url TEXT,
                    soundcloud_url TEXT,
                    links_updated TIMESTAMP,
                    FOREIGN KEY(song_id) REFERENCES songs(id)
                )
            ''')

        conn.commit()
        conn.close()
        
    def get_audio_metadata(self, file_path: Path) -> Optional[Dict]:
        """Extract comprehensive audio metadata including replay gain."""
        try:
            audio = None
            audio_tech = None
            track_number = '0'
            
            # Handle different audio formats
            if file_path.suffix.lower() == '.mp3':
                audio = EasyID3(file_path)
                audio_tech = mutagen.File(file_path)
                track_number = audio.get('tracknumber', ['0'])[0].split('/')[0]
                
                # Get ID3 tags for replay gain (MP3)
                raw_audio = mutagen.File(file_path)
                
            elif file_path.suffix.lower() == '.flac':
                audio = FLAC(file_path)
                audio_tech = audio
                track_number = str(audio.get('tracknumber', ['0'])[0]).split('/')[0]
                
                # FLAC has direct access to replay gain
                raw_audio = audio
                
            elif file_path.suffix.lower() == '.m4a':
                audio = mutagen.File(file_path)
                audio_tech = audio
                track_number = audio.get('trkn', [[0, 0]])[0][0]
                
                # For M4A, tags are directly accessible
                raw_audio = audio
                
            if not audio or not audio_tech:
                return None

            current_time = datetime.now()
            
            metadata = {
                'file_path': str(file_path),
                'title': audio.get('title', ['Untitled'])[0],
                'track_number': int(track_number) if track_number and str(track_number).isdigit() else 0,
                'artist': audio.get('artist', ['Unknown Artist'])[0],
                'album_artist': audio.get('albumartist', [None])[0] or audio.get('album artist', [None])[0] or audio.get('artist', ['Unknown Artist'])[0],
                'album': audio.get('album', ['Unknown Album'])[0],
                'date': audio.get('date', [''])[0] or audio.get('year', [''])[0],
                'genre': audio.get('genre', ['Unknown'])[0],
                'label': audio.get('organization', [None])[0] or audio.get('label', [None])[0] or '',
                'mbid': audio.get('musicbrainz_trackid', [''])[0],
                'last_modified': datetime.fromtimestamp(os.path.getmtime(file_path)),
                'added_timestamp': current_time,
                'added_week': int(current_time.strftime('%V')),  # ISO week number
                'added_month': current_time.month,
                'added_year': current_time.year,
                'folder_path': str(file_path.parent)  # Add folder path for album grouping
            }

            # Technical information
            if hasattr(audio_tech, 'info'):
                metadata['bitrate'] = getattr(audio_tech.info, 'bitrate', 0)
                metadata['sample_rate'] = getattr(audio_tech.info, 'sample_rate', 0)
                metadata['bit_depth'] = getattr(audio_tech.info, 'bits_per_sample', 0)
                metadata['duration'] = getattr(audio_tech.info, 'length', 0)
            
            # Extract ReplayGain information based on file format
            # For FLAC files
            if file_path.suffix.lower() == '.flac':
                metadata['replay_gain_track_gain'] = self._extract_float_tag(raw_audio, 'replaygain_track_gain')
                metadata['replay_gain_track_peak'] = self._extract_float_tag(raw_audio, 'replaygain_track_peak')
                metadata['replay_gain_album_gain'] = self._extract_float_tag(raw_audio, 'replaygain_album_gain')
                metadata['replay_gain_album_peak'] = self._extract_float_tag(raw_audio, 'replaygain_album_peak')
            
            # For MP3 files - different tag formats exist, try multiple variants
            elif file_path.suffix.lower() == '.mp3':
                # Try to find replay gain info in raw ID3 tags
                metadata['replay_gain_track_gain'] = self._extract_mp3_replay_gain(raw_audio, 'TXXX:REPLAYGAIN_TRACK_GAIN', 'TXXX:replaygain_track_gain')
                metadata['replay_gain_track_peak'] = self._extract_mp3_replay_gain(raw_audio, 'TXXX:REPLAYGAIN_TRACK_PEAK', 'TXXX:replaygain_track_peak')
                metadata['replay_gain_album_gain'] = self._extract_mp3_replay_gain(raw_audio, 'TXXX:REPLAYGAIN_ALBUM_GAIN', 'TXXX:replaygain_album_gain')
                metadata['replay_gain_album_peak'] = self._extract_mp3_replay_gain(raw_audio, 'TXXX:REPLAYGAIN_ALBUM_PEAK', 'TXXX:replaygain_album_peak')
                
            # For M4A files
            elif file_path.suffix.lower() == '.m4a':
                # M4A usually has replay gain in ----:com.apple.iTunes:replaygain_track_gain format
                for tag in raw_audio:
                    if 'replaygain_track_gain' in tag.lower():
                        metadata['replay_gain_track_gain'] = self._parse_replay_gain_value(str(raw_audio[tag][0]))
                    if 'replaygain_track_peak' in tag.lower():
                        metadata['replay_gain_track_peak'] = self._parse_replay_gain_value(str(raw_audio[tag][0]))
                    if 'replaygain_album_gain' in tag.lower():
                        metadata['replay_gain_album_gain'] = self._parse_replay_gain_value(str(raw_audio[tag][0]))
                    if 'replaygain_album_peak' in tag.lower():
                        metadata['replay_gain_album_peak'] = self._parse_replay_gain_value(str(raw_audio[tag][0]))

            return metadata

        except Exception as e:
            self.logger.error(f"Metadata extraction error for {file_path}: {str(e)}")
            return None


    def _extract_float_tag(self, audio, tag_name):
        """Extract a float value from an audio tag, handling different formats."""
        if tag_name in audio:
            try:
                # Extract the numerical part and convert to float
                value = str(audio[tag_name][0])
                return self._parse_replay_gain_value(value)
            except (IndexError, ValueError, TypeError):
                return None
        return None

    def _extract_mp3_replay_gain(self, audio, *tag_names):
        """Try multiple possible tag names for MP3 replay gain."""
        for tag_name in tag_names:
            if tag_name in audio:
                try:
                    value = str(audio[tag_name].text[0])
                    return self._parse_replay_gain_value(value)
                except (IndexError, ValueError, AttributeError, TypeError):
                    continue
        return None

    def _parse_replay_gain_value(self, value_str):
        """Parse replay gain value from string, handling different formats."""
        try:
            # Strip 'dB' suffix and any whitespace
            value_str = value_str.replace('dB', '').strip()
            # Convert to float
            return float(value_str)
        except (ValueError, TypeError):
            return None


    def scan_library(self, force_update=False):
        """Comprehensive library scanning with selective updates."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        error_log_path = 'music_library_scan_errors.log'
        error_logger = logging.getLogger('error_log')
        error_logger.setLevel(logging.ERROR)
        error_handler = logging.FileHandler(error_log_path, encoding='utf-8')
        error_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        error_handler.setFormatter(error_formatter)
        error_logger.addHandler(error_handler)
        
        processed_files = 0
        error_files = 0
        
        # Dictionary to store folder metadata for album consistency
        folder_albums = {}
        
        try:
            # First pass: gather folder information to establish consistent album metadata
            for file_path in self.root_path.rglob('*'):
                if file_path.suffix.lower() in self.supported_formats:
                    try:
                        metadata = self.get_audio_metadata(file_path)
                        if metadata:
                            folder_path = metadata['folder_path']
                            if folder_path not in folder_albums:
                                # Use album artist if available, otherwise use primary artist
                                primary_artist = metadata['album_artist'] or metadata['artist'].split('feat.')[0].split('with')[0].split('&')[0].strip()
                                
                                folder_albums[folder_path] = {
                                    'album': metadata['album'],
                                    'primary_artist': primary_artist,
                                    'year': metadata['date'],
                                    'genre': metadata['genre'],
                                    'label': metadata['label']
                                }
                    except Exception as e:
                        error_logger.error(f"First pass error for {file_path}: {str(e)}")
            
            # Second pass: process files with consistent album metadata
            for file_path in self.root_path.rglob('*'):
                if file_path.suffix.lower() in self.supported_formats:
                    abs_path = str(file_path.absolute())
                    
                    try:
                        last_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
                        
                        # Check if file needs processing
                        c.execute("SELECT last_modified, added_timestamp FROM songs WHERE file_path = ?", (abs_path,))
                        existing_record = c.fetchone()
                        
                        # Convert database date to datetime
                        if existing_record:
                            try:
                                db_last_modified = datetime.strptime(existing_record[0], '%Y-%m-%d %H:%M:%S.%f')
                                original_added_timestamp = datetime.strptime(existing_record[1], '%Y-%m-%d %H:%M:%S.%f') if existing_record[1] else None
                            except ValueError:
                                # Try without the fraction of seconds
                                try:
                                    db_last_modified = datetime.strptime(existing_record[0], '%Y-%m-%d %H:%M:%S')
                                    original_added_timestamp = datetime.strptime(existing_record[1], '%Y-%m-%d %H:%M:%S') if existing_record[1] else None
                                except:
                                    db_last_modified = None
                                    original_added_timestamp = None
                        else:
                            db_last_modified = None
                            original_added_timestamp = None

                        if force_update or not db_last_modified or last_modified > db_last_modified:
                            metadata = self.get_audio_metadata(file_path)
                            
                            if metadata:
                                # Preserve original added_timestamp if it exists
                                if original_added_timestamp:
                                    metadata['added_timestamp'] = original_added_timestamp
                                    metadata['added_week'] = int(original_added_timestamp.strftime('%V'))
                                    metadata['added_month'] = original_added_timestamp.month
                                    metadata['added_year'] = original_added_timestamp.year
                                
                                # Use folder-based consistent album metadata
                                folder_path = metadata['folder_path']
                                if folder_path in folder_albums:
                                    folder_metadata = folder_albums[folder_path]
                                    consistent_album_artist = folder_metadata['primary_artist']
                                    
                                    # Insert or update song with consistent album metadata
                                    c.execute('''
                                        INSERT OR REPLACE INTO songs 
                                        (file_path, title, track_number, artist, album_artist, 
                                        album, date, genre, label, mbid, bitrate, 
                                        bit_depth, sample_rate, last_modified, duration,
                                        added_timestamp, added_week, added_month, added_year,
                                        replay_gain_track_gain, replay_gain_track_peak, 
                                        replay_gain_album_gain, replay_gain_album_peak)
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    ''', (
                                        metadata['file_path'], metadata['title'], metadata['track_number'], 
                                        metadata['artist'], consistent_album_artist, folder_metadata['album'], 
                                        folder_metadata['year'], folder_metadata['genre'], folder_metadata['label'], 
                                        metadata['mbid'], metadata.get('bitrate'), metadata.get('bit_depth'),
                                        metadata.get('sample_rate'), metadata['last_modified'], 
                                        metadata.get('duration'), metadata['added_timestamp'],
                                        metadata['added_week'], metadata['added_month'], metadata['added_year'],
                                        metadata.get('replay_gain_track_gain'), metadata.get('replay_gain_track_peak'),
                                        metadata.get('replay_gain_album_gain'), metadata.get('replay_gain_album_peak')
                                    ))
                                    
                                    # Asegurarse de que la canción también tenga entrada en song_links
                                    self._ensure_song_links_entry(c, metadata['file_path'])
                                    
                                    processed_files += 1
                                    
                                    # Update/insert artist information (using album artist for album relationship)
                                    self._update_artist_info(c, consistent_album_artist)
                                    
                                    # Update/insert album information using consistent album metadata
                                    self._update_album_info(c, {
                                        'artist': consistent_album_artist,
                                        'album': folder_metadata['album'],
                                        'date': folder_metadata['year'],
                                        'label': folder_metadata['label'],
                                        'genre': folder_metadata['genre']
                                    })
                                    
                                    # Update/insert genre information
                                    self._update_genre_info(c, folder_metadata['genre'])
                                else:
                                    # Fallback to original metadata if folder info not available
                                    c.execute('''
                                        INSERT OR REPLACE INTO songs 
                                        (file_path, title, track_number, artist, album_artist, 
                                        album, date, genre, label, mbid, bitrate, 
                                        bit_depth, sample_rate, last_modified, duration,
                                        added_timestamp, added_week, added_month, added_year,
                                        replay_gain_track_gain, replay_gain_track_peak, 
                                        replay_gain_album_gain, replay_gain_album_peak)
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    ''', (
                                        metadata['file_path'], metadata['title'], metadata['track_number'], 
                                        metadata['artist'], metadata['album_artist'], metadata['album'], 
                                        metadata['date'], metadata['genre'], metadata['label'], 
                                        metadata['mbid'], metadata.get('bitrate'), metadata.get('bit_depth'),
                                        metadata.get('sample_rate'), metadata['last_modified'], 
                                        metadata.get('duration'), metadata['added_timestamp'],
                                        metadata['added_week'], metadata['added_month'], metadata['added_year'],
                                        metadata.get('replay_gain_track_gain'), metadata.get('replay_gain_track_peak'),
                                        metadata.get('replay_gain_album_gain'), metadata.get('replay_gain_album_peak')
                                    ))
                                    
                                    # Asegurarse de que la canción también tenga entrada en song_links
                                    self._ensure_song_links_entry(c, metadata['file_path'])
                                    
                                    processed_files += 1
                                    
                                    # Update remaining tables
                                    self._update_artist_info(c, metadata['album_artist'] or metadata['artist'])
                                    self._update_album_info(c, metadata)
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

    def _ensure_song_links_entry(self, cursor, file_path):
        """Asegurarse de que existe una entrada en song_links para esta canción"""
        # Primero obtener el ID de la canción
        cursor.execute("SELECT id FROM songs WHERE file_path = ?", (file_path,))
        result = cursor.fetchone()
        if result:
            song_id = result[0]
            
            # Verificar si ya existe una entrada en song_links
            cursor.execute("SELECT id FROM song_links WHERE song_id = ?", (song_id,))
            if not cursor.fetchone():
                # Si no existe, crear una entrada vacía
                cursor.execute('''
                    INSERT INTO song_links 
                    (song_id, links_updated)
                    VALUES (?, ?)
                ''', (song_id, datetime.now()))

    def _update_artist_info(self, cursor, artist_name):
        """Update artist information selectively."""
        # Skip if artist name is None
        if not artist_name:
            return

        # Clean up artist name to remove featuring parts
        artist_name = artist_name.split('feat.')[0].split('with')[0].split('&')[0].strip()
        
        cursor.execute("SELECT last_updated FROM artists WHERE name = ?", (artist_name,))
        existing_artist = cursor.fetchone()
        
        # Only update if no existing record or older than 30 days
        if not existing_artist:
            cursor.execute('''
                INSERT INTO artists 
                (name, last_updated)
                VALUES (?, ?)
            ''', (artist_name, datetime.now()))
        elif existing_artist and (datetime.now() - self._parse_db_datetime(existing_artist[0])) > timedelta(days=30):
            lastfm_info = self.get_lastfm_artist_info(artist_name)
            
            if lastfm_info:
                cursor.execute('''
                    UPDATE artists 
                    SET bio = ?, tags = ?, similar_artists = ?, last_updated = ?
                    WHERE name = ?
                ''', (
                    lastfm_info['bio'], lastfm_info['tags'], 
                    lastfm_info['similar_artists'], lastfm_info['last_updated'],
                    artist_name
                ))

    def _update_album_info(self, cursor, metadata):
        """Update album information using folder-based consistency."""
        # Skip if invalid data
        if not metadata['artist'] or not metadata['album']:
            return
            
        # Clean up artist name (just in case)
        artist_name = metadata['artist'].split('feat.')[0].split('with')[0].split('&')[0].strip()
        
        # First check if artist exists
        cursor.execute("SELECT id FROM artists WHERE name = ?", (artist_name,))
        artist_result = cursor.fetchone()
        
        if not artist_result:
            # If artist doesn't exist, create it
            cursor.execute('''
                INSERT INTO artists (name, last_updated)
                VALUES (?, ?)
            ''', (artist_name, datetime.now()))
            cursor.execute("SELECT id FROM artists WHERE name = ?", (artist_name,))
            artist_result = cursor.fetchone()
            
        artist_id = artist_result[0]
        
        # Check if this album already exists for this artist
        cursor.execute('''
            SELECT id, last_updated 
            FROM albums 
            WHERE artist_id = ? AND name = ?
        ''', (artist_id, metadata['album']))
        
        existing_album = cursor.fetchone()
        
        # Insert or update based on existence and last updated time
        if not existing_album:
            cursor.execute('''
                INSERT INTO albums 
                (artist_id, name, year, label, genre, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                artist_id, metadata['album'], 
                metadata['date'], metadata['label'], 
                metadata['genre'], datetime.now()
            ))
        elif (datetime.now() - self._parse_db_datetime(existing_album[1])) > timedelta(days=30):
            cursor.execute('''
                UPDATE albums
                SET year = ?, label = ?, genre = ?, last_updated = ?
                WHERE id = ?
            ''', (
                metadata['date'], metadata['label'], 
                metadata['genre'], datetime.now(),
                existing_album[0]
            ))

    def _update_genre_info(self, cursor, genre_name):
        """Update genre information if not exists."""
        if not genre_name or genre_name == 'Unknown':
            return
            
        cursor.execute("SELECT * FROM genres WHERE name = ?", (genre_name,))
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO genres (name) VALUES (?)
            ''', (genre_name,))

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
            return {
                'name': artist_name,
                'bio': '',
                'tags': json.dumps([]),
                'similar_artists': json.dumps([]),
                'last_updated': datetime.now(),
                'origin': None,
                'formed_year': None
            }
    
    def _parse_db_datetime(self, datetime_str):
        """Safely parse datetime strings from database."""
        if not datetime_str:
            return datetime.now() - timedelta(days=365)  # Default to a year ago
            
        try:
            return datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S.%f')
        except ValueError:
            try:
                return datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                return datetime.now() - timedelta(days=365)  # Default to a year ago

    def update_replay_gain_only(self):
        """One-time update to extract replay gain for all files in the database."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            # Get all files in the database
            c.execute("SELECT file_path FROM songs")
            files = c.fetchall()
            
            updated_count = 0
            for file_path_tuple in files:
                file_path = file_path_tuple[0]
                path_obj = Path(file_path)
                
                if path_obj.exists() and path_obj.is_file():
                    try:
                        # Just extract the replay gain data
                        audio = None
                        if path_obj.suffix.lower() == '.flac':
                            audio = FLAC(path_obj)
                        elif path_obj.suffix.lower() == '.mp3':
                            audio = mutagen.File(path_obj)
                        elif path_obj.suffix.lower() == '.m4a':
                            audio = mutagen.File(path_obj)
                        
                        if audio:
                            # Extract replay gain using the methods you implemented
                            replay_gains = {
                                'replay_gain_track_gain': self._extract_float_tag(audio, 'replaygain_track_gain'),
                                'replay_gain_track_peak': self._extract_float_tag(audio, 'replaygain_track_peak'),
                                'replay_gain_album_gain': self._extract_float_tag(audio, 'replaygain_album_gain'),
                                'replay_gain_album_peak': self._extract_float_tag(audio, 'replaygain_album_peak')
                            }
                            
                            # Update the database with just the replay gain data
                            c.execute("""
                                UPDATE songs 
                                SET replay_gain_track_gain = ?,
                                    replay_gain_track_peak = ?,
                                    replay_gain_album_gain = ?,
                                    replay_gain_album_peak = ?
                                WHERE file_path = ?
                            """, (
                                replay_gains['replay_gain_track_gain'],
                                replay_gains['replay_gain_track_peak'],
                                replay_gains['replay_gain_album_gain'],
                                replay_gains['replay_gain_album_peak'],
                                file_path
                            ))
                            updated_count += 1
                            
                            if updated_count % 100 == 0:
                                conn.commit()
                                self.logger.info(f"Updated replay gain for {updated_count} files")
                                
                    except Exception as e:
                        self.logger.error(f"Error updating replay gain for {file_path}: {str(e)}")
            
            conn.commit()
            self.logger.info(f"Replay gain update completed. Updated {updated_count} files.")
        
        except Exception as e:
            self.logger.error(f"Replay gain update error: {str(e)}")
        
        finally:
            conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Music Library Manager')
    parser.add_argument('root_path', help='Root directory of music library')
    parser.add_argument('db_path', help='Path to SQLite database')
    parser.add_argument('--force-update', action='store_true', help='Force update all files')
    parser.add_argument('--update-replay-gain', action='store_true', help='Update replay gain information only')

    args = parser.parse_args()
    
    manager = MusicLibraryManager(args.db_path, args.root_path)
    
    if args.update_replay_gain:
        manager.update_replay_gain_only()
    
    
    manager.scan_library(force_update=args.force_update)