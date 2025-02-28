import os
import sys
import logging
import sqlite3
import argparse
import json
from datetime import datetime
import lyricsgenius
from dotenv import load_dotenv
load_dotenv()

class LyricsManager:
    def __init__(self, db_path, batch_size=1000):
        self.db_path = db_path
        self.batch_size = batch_size
        
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
        
        # Archivo de estado para pausar/continuar
        self.state_file = "lyrics_update_state.json"
        
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
                    track_id INTEGER UNIQUE,
                    lyrics TEXT,
                    source TEXT DEFAULT 'Genius',
                    last_updated TIMESTAMP,
                    FOREIGN KEY(track_id) REFERENCES songs(id)
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
    
    def save_state(self, song_ids, current_index, processed, success):
        """Guarda el estado actual del proceso para continuar más tarde."""
        state = {
            "song_ids": song_ids,
            "current_index": current_index,
            "processed": processed,
            "success": success,
            "timestamp": datetime.now().isoformat()
        }
        
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"Estado guardado: procesadas {processed} canciones, {success} actualizadas correctamente")
    
    def load_state(self):
        """Carga el estado anterior si existe."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                self.logger.info(f"Estado cargado: continuando desde canción {state['current_index']} de {len(state['song_ids'])}")
                return state
            except Exception as e:
                self.logger.error(f"Error cargando estado: {str(e)}")
        return None
    
    def get_songs_to_update(self, force_update=False):
        """Obtiene la lista de canciones para actualizar."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        if force_update:
            # Usamos los datos directos de la tabla songs
            c.execute("""
                SELECT id, artist, title 
                FROM songs
                WHERE artist IS NOT NULL AND title IS NOT NULL
            """)
        else:
            # Obtener solo canciones sin letras
            c.execute("""
                SELECT songs.id, songs.artist, songs.title 
                FROM songs 
                LEFT JOIN lyrics ON songs.id = lyrics.track_id 
                WHERE lyrics.id IS NULL AND songs.artist IS NOT NULL AND songs.title IS NOT NULL
            """)
        
        songs = c.fetchall()
        conn.close()
        return songs
    
    def update_lyrics(self, force_update=False, resume=True):
        """Actualiza las letras de las canciones en la base de datos, con soporte para pausar/continuar."""
        # Verificar si hay un estado guardado para continuar
        state = None
        if resume:
            state = self.load_state()
        
        if state:
            # Continuamos desde el estado guardado
            song_ids = state["song_ids"]
            current_index = state["current_index"]
            processed = state["processed"]
            success = state["success"]
        else:
            # Comenzamos un nuevo proceso
            songs_to_update = self.get_songs_to_update(force_update)
            song_ids = [(song_id, artist, title) for song_id, artist, title in songs_to_update]
            current_index = 0
            processed = 0
            success = 0
        
        total_songs = len(song_ids)
        self.logger.info(f"Total de canciones para procesar: {total_songs}")
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        error_log_path = 'lyrics_update_errors.log'
        error_logger = logging.getLogger('error_log')
        error_logger.setLevel(logging.ERROR)
        error_handler = logging.FileHandler(error_log_path, encoding='utf-8')
        error_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        error_handler.setFormatter(error_formatter)
        error_logger.addHandler(error_handler)
        
        try:
            batch_start = current_index
            
            for i in range(current_index, total_songs):
                song_id, artist, title = song_ids[i]
                
                try:
                    processed += 1
                    
                    # Si el artista principal no está disponible, intentamos usar album_artist
                    if not artist:
                        c.execute("SELECT album_artist FROM songs WHERE id = ?", (song_id,))
                        album_artist_result = c.fetchone()
                        if album_artist_result and album_artist_result[0]:
                            artist = album_artist_result[0]
                    
                    if not title or not artist:
                        error_logger.error(f"Falta información para song_id {song_id}: artist={artist}, title={title}")
                        continue
                    
                    lyrics = self.get_song_lyrics(artist, title)
                    if lyrics:
                        # Insertar o actualizar letra usando track_id
                        c.execute("""
                            INSERT OR REPLACE INTO lyrics (track_id, lyrics, last_updated) 
                            VALUES (?, ?, ?)
                        """, (song_id, lyrics, datetime.now()))
                        
                        # Actualizar referencia en songs
                        c.execute("""
                            UPDATE songs SET lyrics_id = (SELECT id FROM lyrics WHERE track_id = ?) 
                            WHERE id = ?
                        """, (song_id, song_id))
                        
                        conn.commit()
                        success += 1
                    else:
                        error_logger.error(f"No se encontró letra para: {artist} - {title}")
                
                except Exception as e:
                    error_logger.error(f"Error procesando {artist} - {title}: {str(e)}")
                    conn.rollback()
                
                # Mostrar progreso y guardar estado cada cierto número de canciones
                if processed % 10 == 0 or (i - batch_start) == self.batch_size:
                    self.logger.info(f"Progreso: {processed}/{total_songs} canciones procesadas ({success} actualizadas)")
                
                # Guardar estado y salir después de cada lote
                if (i - batch_start + 1) >= self.batch_size:
                    self.save_state(song_ids, i + 1, processed, success)
                    self.logger.info(f"Lote completado. Procesando siguiente lote en la próxima ejecución.")
                    break
        
        except KeyboardInterrupt:
            self.logger.info("Proceso interrumpido por el usuario. Guardando estado...")
            self.save_state(song_ids, i, processed, success)
        
        finally:
            # Si hemos terminado todo el proceso, eliminar el archivo de estado
            if current_index + self.batch_size >= total_songs:
                if os.path.exists(self.state_file):
                    os.remove(self.state_file)
                self.logger.info(f"Proceso completo: {processed} canciones procesadas, {success} actualizadas correctamente")
            
            error_logger.removeHandler(error_handler)
            error_handler.close()
            conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Actualizador de letras para biblioteca musical')
    parser.add_argument('db_path', help='Ruta a la base de datos SQLite')
    parser.add_argument('--force-update', action='store_true', help='Forzar actualización de todas las letras')
    parser.add_argument('--batch-size', type=int, default=1000, help='Número de canciones a procesar por lote')
    parser.add_argument('--no-resume', action='store_true', help='No continuar desde el último punto guardado')
    
    args = parser.parse_args()
    
    manager = LyricsManager(args.db_path, batch_size=args.batch_size)
    manager.update_lyrics(force_update=args.force_update, resume=not args.no_resume)