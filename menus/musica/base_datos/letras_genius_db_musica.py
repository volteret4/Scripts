import os
import sys
import logging
import sqlite3
import argparse
import json
import time
import requests
from datetime import datetime
import lyricsgenius
from dotenv import load_dotenv
load_dotenv()

class MultiLyricsManager:
    def __init__(self, db_path, batch_size=1000):
        self.db_path = db_path
        self.batch_size = batch_size
        
        # Logging configuration
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Genius API initialization (como backup)
        genius_token = os.getenv("GENIUS_ACCESS_TOKEN")
        if genius_token:
            self.genius = lyricsgenius.Genius(genius_token, timeout=10, sleep_time=1.0)
            self.genius.verbose = False
        else:
            self.genius = None
            self.logger.warning("GENIUS_ACCESS_TOKEN no encontrado. Genius no estará disponible como fuente de respaldo.")
        
        # Archivo de estado para pausar/continuar
        self.state_file = "lyrics_update_state.json"
        
        # Retry y backoff settings
        self.max_retries = 3
        self.retry_delay = 2  # segundos
        
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
                    source TEXT,
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
    
    def get_lyrics_from_ovh(self, artist, title):
        """Intenta obtener letras de lyrics.ovh API."""
        base_url = "https://api.lyrics.ovh/v1"
        
        for retry in range(self.max_retries):
            try:
                url = f"{base_url}/{artist.replace('/', '')}/{title.replace('/', '')}"
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if 'lyrics' in data and data['lyrics']:
                        return data['lyrics'], "lyrics.ovh"
                elif response.status_code == 429:  # Rate limit
                    wait_time = retry * self.retry_delay
                    self.logger.warning(f"Rate limit en lyrics.ovh. Esperando {wait_time}s antes de reintentar.")
                    time.sleep(wait_time)
                    continue
                
                # Si llegamos aquí, no se encontró pero no hay error
                break
                
            except Exception as e:
                self.logger.error(f"Error accediendo a lyrics.ovh: {str(e)}")
                time.sleep(retry * self.retry_delay)
        
        return None, None
    
    def get_lyrics_from_lyricsgenius(self, artist, title):
        """Intenta obtener letras usando Genius API."""
        if not self.genius:
            return None, None
            
        try:
            song = self.genius.search_song(title, artist)
            if song:
                return song.lyrics, "Genius"
        except Exception as e:
            self.logger.error(f"Error al buscar letra en Genius para {artist} - {title}: {str(e)}")
        
        return None, None
    
    def get_lyrics_from_happi(self, artist, title):
        """Intenta obtener letras usando Happi API."""
        happi_key = os.getenv("HAPPI_API_KEY")
        if not happi_key:
            return None, None
            
        base_url = "https://api.happi.dev/v1/music"
        
        try:
            # Primero buscamos la canción
            search_url = f"{base_url}/search/{title}"
            headers = {"x-happi-key": happi_key}
            params = {"q_artist": artist, "limit": 1}
            
            response = requests.get(search_url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and data.get('result') and len(data['result']) > 0:
                    track_id = data['result'][0].get('id_track')
                    if track_id:
                        # Ahora buscamos la letra con el ID de la canción
                        lyrics_url = f"{base_url}/artists/{data['result'][0]['id_artist']}/albums/{data['result'][0]['id_album']}/tracks/{track_id}/lyrics"
                        lyrics_response = requests.get(lyrics_url, headers=headers, timeout=10)
                        
                        if lyrics_response.status_code == 200:
                            lyrics_data = lyrics_response.json()
                            if lyrics_data.get('success') and lyrics_data.get('result') and lyrics_data['result'].get('lyrics'):
                                return lyrics_data['result']['lyrics'], "Happi"
        except Exception as e:
            self.logger.error(f"Error accediendo a Happi API: {str(e)}")
        
        return None, None
    
    def get_lyrics_from_musixmatch(self, artist, title):
        """Intenta obtener letras usando Musixmatch API."""
        musixmatch_key = os.getenv("MUSIXMATCH_API_KEY")
        if not musixmatch_key:
            return None, None
            
        base_url = "https://api.musixmatch.com/ws/1.1"
        
        try:
            # Buscar la canción
            search_url = f"{base_url}/matcher.lyrics.get"
            params = {
                "apikey": musixmatch_key,
                "q_track": title,
                "q_artist": artist,
                "format": "json"
            }
            
            response = requests.get(search_url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                message = data.get('message', {})
                body = message.get('body', {})
                lyrics = body.get('lyrics', {})
                lyrics_text = lyrics.get('lyrics_body')
                
                if lyrics_text:
                    # Musixmatch API free incluye un mensaje promocional al final
                    disclaimer_idx = lyrics_text.find("******* This Lyrics is NOT")
                    if disclaimer_idx > 0:
                        lyrics_text = lyrics_text[:disclaimer_idx].strip()
                    
                    return lyrics_text, "Musixmatch"
        except Exception as e:
            self.logger.error(f"Error accediendo a Musixmatch API: {str(e)}")
        
        return None, None
    
    def get_song_lyrics(self, artist, title):
        """Busca la letra de una canción en múltiples fuentes."""
        # Limpiar el título y artista para evitar problemas con caracteres especiales
        artist = artist.strip()
        title = title.strip()
        
        # Intentar con lyrics.ovh primero (sin API key, gratuito)
        lyrics, source = self.get_lyrics_from_ovh(artist, title)
        if lyrics:
            return lyrics, source
            
        # Intentar con Happi (necesita API key)
        lyrics, source = self.get_lyrics_from_happi(artist, title)
        if lyrics:
            return lyrics, source
            
        # Intentar con Musixmatch (necesita API key)
        lyrics, source = self.get_lyrics_from_musixmatch(artist, title)
        if lyrics:
            return lyrics, source
            
        # Intentar con Genius como último recurso (debido al rate limit)
        lyrics, source = self.get_lyrics_from_lyricsgenius(artist, title)
        if lyrics:
            return lyrics, source
        
        return None, None
    
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
        
        # Estadísticas de fuentes
        sources_stats = {}
        
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
                    
                    lyrics, source = self.get_song_lyrics(artist, title)
                    if lyrics:
                        # Actualizar estadísticas
                        sources_stats[source] = sources_stats.get(source, 0) + 1
                        
                        # Insertar o actualizar letra usando track_id
                        c.execute("""
                            INSERT OR REPLACE INTO lyrics (track_id, lyrics, source, last_updated) 
                            VALUES (?, ?, ?, ?)
                        """, (song_id, lyrics, source, datetime.now()))
                        
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
                    if sources_stats:
                        sources_log = ", ".join([f"{src}: {count}" for src, count in sources_stats.items()])
                        self.logger.info(f"Fuentes utilizadas: {sources_log}")
                
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
                if sources_stats:
                    sources_log = ", ".join([f"{src}: {count}" for src, count in sources_stats.items()])
                    self.logger.info(f"Resumen de fuentes utilizadas: {sources_log}")
            
            error_logger.removeHandler(error_handler)
            error_handler.close()
            conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Actualizador de letras para biblioteca musical con múltiples APIs')
    parser.add_argument('db_path', help='Ruta a la base de datos SQLite')
    parser.add_argument('--force-update', action='store_true', help='Forzar actualización de todas las letras')
    parser.add_argument('--batch-size', type=int, default=1000, help='Número de canciones a procesar por lote')
    parser.add_argument('--no-resume', action='store_true', help='No continuar desde el último punto guardado')
    
    args = parser.parse_args()
    
    manager = MultiLyricsManager(args.db_path, batch_size=args.batch_size)
    manager.update_lyrics(force_update=args.force_update, resume=not args.no_resume)