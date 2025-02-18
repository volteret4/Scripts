#!/usr/bin/env python
#
# Script Name: db_musica_lyrics.py
# Description: Lee la base de datos creada por db_musica.py y busca las letras 
#              de las canciones en Genius, añadiéndolas a la base de datos.
# Author: [Tu nombre]
# Repository: https://github.com/[tu_usuario]/
# Dependencies: python3, lyricsgenius, sqlite3
# Usage: python db_musica_lyrics.py <db_path>

import os
import sys
import logging
import sqlite3
import argparse
from datetime import datetime
import lyricsgenius
from dotenv import load_dotenv

load_dotenv()

class LyricsManager:
    def __init__(self, db_path):
        self.db_path = db_path
        
        # Logging configuration
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Genius API initialization
        genius_token = os.getenv("GENIUS_ACCESS_TOKEN")
        if not genius_token:
            self.logger.error("GENIUS_ACCESS_TOKEN not found in .env file")
            sys.exit(1)
        
        self.genius = lyricsgenius.Genius(genius_token, timeout=10, sleep_time=0.5)
        self.genius.verbose = False  # No mostrar mensajes de Genius
        
        # Initialize database
        self.init_database()
    
    def init_database(self):
        """Verifica y prepara la base de datos para almacenar letras."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Verificar si la tabla lyrics existe
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lyrics'")
        if not c.fetchone():
            # Crear tabla de letras
            c.execute('''
                CREATE TABLE lyrics (
                    id INTEGER PRIMARY KEY,
                    song_id INTEGER UNIQUE,
                    lyrics TEXT,
                    source TEXT DEFAULT 'Genius',
                    last_updated TIMESTAMP,
                    FOREIGN KEY(song_id) REFERENCES songs(id)
                )
            ''')
            self.logger.info("Tabla 'lyrics' creada exitosamente")
        
        # Verificar si la columna lyrics_id existe en la tabla songs
        c.execute("PRAGMA table_info(songs)")
        columns = {col[1] for col in c.fetchall()}
        if 'lyrics_id' not in columns:
            c.execute("ALTER TABLE songs ADD COLUMN lyrics_id INTEGER")
            self.logger.info("Columna 'lyrics_id' añadida a la tabla 'songs'")
        
        conn.commit()
        conn.close()
    
    def get_song_lyrics(self, artist, title):
        """Busca la letra de una canción en Genius."""
        try:
            song = self.genius.search_song(title, artist)
            if song:
                return song.lyrics
            return None
        except Exception as e:
            self.logger.error(f"Error al buscar letra para {artist} - {title}: {str(e)}")
            return None
    
    def update_lyrics(self, force_update=False):
        """Actualiza las letras de las canciones en la base de datos."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Obtener canciones sin letra o que necesitan actualización
        if force_update:
            c.execute("SELECT id, artist, title FROM songs")
        else:
            c.execute("""
                SELECT songs.id, songs.artist, songs.title 
                FROM songs 
                LEFT JOIN lyrics ON songs.id = lyrics.song_id 
                WHERE lyrics.id IS NULL
            """)
        
        songs_to_update = c.fetchall()
        total_songs = len(songs_to_update)
        self.logger.info(f"Encontradas {total_songs} canciones para actualizar letras")
        
        processed = 0
        success = 0
        error_log_path = 'lyrics_update_errors.log'
        error_logger = logging.getLogger('error_log')
        error_logger.setLevel(logging.ERROR)
        error_handler = logging.FileHandler(error_log_path, encoding='utf-8')
        error_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        error_handler.setFormatter(error_formatter)
        error_logger.addHandler(error_handler)
        
        for song_id, artist, title in songs_to_update:
            try:
                processed += 1
                if processed % 10 == 0:
                    self.logger.info(f"Procesando: {processed}/{total_songs}")
                
                lyrics = self.get_song_lyrics(artist, title)
                if lyrics:
                    # Insertar o actualizar letra
                    c.execute("""
                        INSERT OR REPLACE INTO lyrics (song_id, lyrics, last_updated) 
                        VALUES (?, ?, ?)
                    """, (song_id, lyrics, datetime.now()))
                    
                    # Actualizar referencia en songs
                    c.execute("""
                        UPDATE songs SET lyrics_id = (SELECT id FROM lyrics WHERE song_id = ?) 
                        WHERE id = ?
                    """, (song_id, song_id))
                    
                    conn.commit()
                    success += 1
                else:
                    error_logger.error(f"No se encontró letra para: {artist} - {title}")
            
            except Exception as e:
                error_logger.error(f"Error procesando {artist} - {title}: {str(e)}")
        
        error_logger.removeHandler(error_handler)
        error_handler.close()
        
        self.logger.info(f"Actualización de letras completada: {success} de {processed} actualizadas")
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Actualizador de letras para biblioteca musical')
    parser.add_argument('db_path', help='Ruta a la base de datos SQLite')
    parser.add_argument('--force-update', action='store_true', help='Forzar actualización de todas las letras')
    
    args = parser.parse_args()
    
    manager = LyricsManager(args.db_path)
    manager.update_lyrics(force_update=args.force_update)