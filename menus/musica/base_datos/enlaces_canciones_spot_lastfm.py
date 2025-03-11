#!/usr/bin/env python3
import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

class MusicLinkUpdater:
    def __init__(self, db_path: str, checkpoint_file: str, services: Set[str], limit: Optional[int] = None):
        """
        Inicializa el actualizador de enlaces para canciones.
        
        Args:
            db_path: Ruta al archivo de la base de datos SQLite
            checkpoint_file: Archivo JSON para guardar el progreso
            services: Conjunto de servicios a buscar ('youtube', 'spotify', 'bandcamp')
            limit: Límite de canciones a procesar (None para procesar todas)
        """
        self.db_path = db_path
        self.checkpoint_file = checkpoint_file
        self.services = services
        self.limit = limit
        
        # Estadísticas
        self.stats = {
            "processed": 0,
            "skipped": 0,
            "updated": 0,
            "failed": 0,
            "by_service": {
                "youtube": 0,
                "spotify": 0,
                "bandcamp": 0
            },
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "last_processed_id": 0
        }
        
        # Cargar punto de control si existe
        self.last_processed_id = self._load_checkpoint()
        
        # Conectar a la base de datos
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        
        self.log(f"Iniciando actualizador de enlaces para servicios: {', '.join(services)}")
        self.log(f"Base de datos: {db_path}")
        self.log(f"Archivo de checkpoint: {checkpoint_file}")
        if limit:
            self.log(f"Límite de canciones: {limit}")
        self.log(f"Último ID procesado: {self.last_processed_id}")
        
    def _load_checkpoint(self) -> int:
        """Carga el último ID procesado desde el archivo de checkpoint."""
        if not os.path.exists(self.checkpoint_file):
            return 0
            
        try:
            with open(self.checkpoint_file, 'r') as f:
                data = json.load(f)
                if "last_processed_id" in data:
                    self.stats = data
                    return data["last_processed_id"]
        except (json.JSONDecodeError, FileNotFoundError):
            pass
            
        return 0
        
    def _save_checkpoint(self) -> None:
        """Guarda el progreso actual en el archivo de checkpoint."""
        self.stats["end_time"] = datetime.now().isoformat()
        
        with open(self.checkpoint_file, 'w') as f:
            json.dump(self.stats, f, indent=2)
            
    def log(self, message: str) -> None:
        """Registra un mensaje en stdout con marca de tiempo."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}")
        
    def get_songs_to_process(self) -> List[Dict]:
        """Obtiene la lista de canciones a procesar desde la base de datos."""
        query = """
        SELECT s.id, s.title, s.artist, s.album
        FROM songs s
        LEFT JOIN song_links sl ON s.id = sl.song_id
        WHERE s.id > ?
        ORDER BY s.id ASC
        """
        
        if self.limit:
            query += f" LIMIT {self.limit}"
            
        self.cursor.execute(query, (self.last_processed_id,))
        return [dict(row) for row in self.cursor.fetchall()]
        
    def search_youtube(self, song: Dict) -> Optional[str]:
        """
        Simula la búsqueda de una canción en YouTube.
        En un caso real, utilizarías la API de YouTube para buscar.
        
        Args:
            song: Diccionario con información de la canción
            
        Returns:
            URL de YouTube o None si no se encuentra
        """
        # Simulación: en una implementación real se usaría la API de YouTube
        self.log(f"Buscando en YouTube: {song['artist']} - {song['title']}")
        # Simular éxito con probabilidad del 90%
        if hash(f"{song['id']}youtube") % 10 != 0:
            video_id = hash(f"{song['artist']}{song['title']}tube") % 1000000
            return f"https://youtube.com/watch?v={video_id}"
        return None
        
    def search_spotify(self, song: Dict) -> Tuple[Optional[str], Optional[str]]:
        """
        Simula la búsqueda de una canción en Spotify.
        En un caso real, utilizarías la API de Spotify para buscar.
        
        Args:
            song: Diccionario con información de la canción
            
        Returns:
            Tupla (URL de Spotify, ID de Spotify) o (None, None) si no se encuentra
        """
        # Simulación: en una implementación real se usaría la API de Spotify
        self.log(f"Buscando en Spotify: {song['artist']} - {song['title']}")
        # Simular éxito con probabilidad del 85%
        if hash(f"{song['id']}spotify") % 100 < 85:
            track_id = f"{hash(song['artist'] + song['title']) % 10000000:07x}"
            return (f"https://open.spotify.com/track/{track_id}", track_id)
        return (None, None)
        
    def search_bandcamp(self, song: Dict) -> Optional[str]:
        """
        Simula la búsqueda de una canción en Bandcamp.
        En un caso real, utilizarías web scraping o una API no oficial para buscar.
        
        Args:
            song: Diccionario con información de la canción
            
        Returns:
            URL de Bandcamp o None si no se encuentra
        """
        # Simulación: en una implementación real se usaría web scraping o una API no oficial
        self.log(f"Buscando en Bandcamp: {song['artist']} - {song['title']}")
        # Simular éxito con probabilidad del 60%
        if hash(f"{song['id']}bandcamp") % 100 < 60:
            artist_slug = song['artist'].lower().replace(' ', '-')
            song_slug = song['title'].lower().replace(' ', '-')
            return f"https://{artist_slug}.bandcamp.com/track/{song_slug}"
        return None
        
    def update_song_links(self, song_id: int, youtube_url: Optional[str] = None, 
                         spotify_url: Optional[str] = None, spotify_id: Optional[str] = None,
                         bandcamp_url: Optional[str] = None) -> bool:
        """
        Actualiza los enlaces de una canción en la base de datos.
        
        Args:
            song_id: ID de la canción
            youtube_url: URL de YouTube
            spotify_url: URL de Spotify
            spotify_id: ID de Spotify
            bandcamp_url: URL de Bandcamp
            
        Returns:
            True si se actualizó correctamente, False en caso contrario
        """
        try:
            # Verificar si ya existe un registro en song_links
            self.cursor.execute("SELECT id FROM song_links WHERE song_id = ?", (song_id,))
            result = self.cursor.fetchone()
            
            current_time = datetime.now().isoformat()
            
            if result:
                # Actualizar registro existente
                update_fields = []
                params = []
                
                if youtube_url is not None:
                    update_fields.append("youtube_url = ?")
                    params.append(youtube_url)
                    
                if spotify_url is not None:
                    update_fields.append("spotify_url = ?")
                    params.append(spotify_url)
                    
                if spotify_id is not None:
                    update_fields.append("spotify_id = ?")
                    params.append(spotify_id)
                    
                if bandcamp_url is not None:
                    # Asumimos que añadimos este campo a la tabla
                    update_fields.append("bandcamp_url = ?")
                    params.append(bandcamp_url)
                
                if update_fields:
                    update_fields.append("links_updated = ?")
                    params.append(current_time)
                    params.append(song_id)
                    
                    query = f"UPDATE song_links SET {', '.join(update_fields)} WHERE song_id = ?"
                    self.cursor.execute(query, params)
            else:
                # Crear nuevo registro
                fields = ["song_id", "links_updated"]
                values = [song_id, current_time]
                placeholders = ["?", "?"]
                
                if youtube_url is not None:
                    fields.append("youtube_url")
                    values.append(youtube_url)
                    placeholders.append("?")
                    
                if spotify_url is not None:
                    fields.append("spotify_url")
                    values.append(spotify_url)
                    placeholders.append("?")
                    
                if spotify_id is not None:
                    fields.append("spotify_id")
                    values.append(spotify_id)
                    placeholders.append("?")
                    
                if bandcamp_url is not None:
                    # Asumimos que añadimos este campo a la tabla
                    fields.append("bandcamp_url")
                    values.append(bandcamp_url)
                    placeholders.append("?")
                
                query = f"INSERT INTO song_links ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
                self.cursor.execute(query, values)
                
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            self.log(f"Error al actualizar enlaces para canción {song_id}: {e}")
            self.conn.rollback()
            return False
            
    def process_song(self, song: Dict) -> bool:
        """
        Procesa una canción para actualizar sus enlaces.
        
        Args:
            song: Diccionario con información de la canción
            
        Returns:
            True si se actualizó correctamente, False en caso contrario
        """
        self.log(f"Procesando canción ID {song['id']}: {song['artist']} - {song['title']}")
        song_id = song['id']
        self.stats["processed"] += 1
        
        youtube_url = None
        spotify_url = None
        spotify_id = None
        bandcamp_url = None
        
        updated = False
        
        # Buscar en YouTube
        if 'youtube' in self.services:
            youtube_url = self.search_youtube(song)
            if youtube_url:
                self.stats["by_service"]["youtube"] += 1
                updated = True
                
        # Buscar en Spotify
        if 'spotify' in self.services:
            spotify_url, spotify_id = self.search_spotify(song)
            if spotify_url:
                self.stats["by_service"]["spotify"] += 1
                updated = True
                
        # Buscar en Bandcamp
        if 'bandcamp' in self.services:
            bandcamp_url = self.search_bandcamp(song)
            if bandcamp_url:
                self.stats["by_service"]["bandcamp"] += 1
                updated = True
                
        # Actualizar la base de datos
        if updated:
            success = self.update_song_links(
                song_id, youtube_url, spotify_url, spotify_id, bandcamp_url
            )
            
            if success:
                self.stats["updated"] += 1
                self.log(f"Enlaces actualizados para canción ID {song_id}")
            else:
                self.stats["failed"] += 1
                self.log(f"Error al actualizar enlaces para canción ID {song_id}")
                
            return success
        else:
            self.stats["skipped"] += 1
            self.log(f"No se encontraron enlaces para canción ID {song_id}")
            return False
            
    def run(self) -> Dict:
        """
        Ejecuta el proceso de actualización de enlaces.
        
        Returns:
            Diccionario con estadísticas del proceso
        """
        try:
            # Verificar si existe la tabla song_links
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='song_links'")
            if not self.cursor.fetchone():
                self.log("Creando tabla song_links...")
                self.cursor.execute("""
                CREATE TABLE song_links (
                    id INTEGER PRIMARY KEY,
                    song_id INTEGER,
                    spotify_url TEXT,
                    spotify_id TEXT,
                    lastfm_url TEXT,
                    links_updated TIMESTAMP,
                    youtube_url TEXT,
                    musicbrainz_url TEXT,
                    musicbrainz_recording_id TEXT,
                    bandcamp_url TEXT
                )
                """)
                self.conn.commit()
            else:
                # Verificar si bandcamp_url existe en la tabla
                self.cursor.execute("PRAGMA table_info(song_links)")
                columns = [col[1] for col in self.cursor.fetchall()]
                
                if "bandcamp_url" not in columns:
                    self.log("Añadiendo columna bandcamp_url a la tabla song_links...")
                    self.cursor.execute("ALTER TABLE song_links ADD COLUMN bandcamp_url TEXT")
                    self.conn.commit()
            
            # Obtener canciones a procesar
            songs = self.get_songs_to_process()
            total_songs = len(songs)
            self.log(f"Se encontraron {total_songs} canciones para procesar")
            
            if total_songs == 0:
                self.log("No hay canciones para procesar. Finalizando.")
                return self.stats
                
            # Procesar canciones
            for i, song in enumerate(songs):
                self.process_song(song)
                self.stats["last_processed_id"] = song["id"]
                
                # Guardar checkpoint cada 100 canciones
                if (i + 1) % 100 == 0:
                    self._save_checkpoint()
                    self.log(f"Progreso: {i + 1}/{total_songs} canciones procesadas")
                    
                # Pequeña pausa para no saturar APIs
                time.sleep(0.1)
                
            # Guardar estadísticas finales
            self._save_checkpoint()
            
            # Mostrar estadísticas
            self.log("\n--- Estadísticas finales ---")
            self.log(f"Total de canciones procesadas: {self.stats['processed']}")
            self.log(f"Canciones actualizadas: {self.stats['updated']}")
            self.log(f"Canciones omitidas: {self.stats['skipped']}")
            self.log(f"Errores: {self.stats['failed']}")
            self.log("Enlaces por servicio:")
            for service, count in self.stats["by_service"].items():
                if service in self.services:
                    self.log(f"  - {service}: {count}")
                    
            return self.stats
            
        except Exception as e:
            self.log(f"Error inesperado: {e}")
            raise
        finally:
            self.conn.close()

def main():
    parser = argparse.ArgumentParser(description="Actualiza enlaces de canciones para servicios de streaming")
    parser.add_argument("db_path", help="Ruta al archivo de base de datos SQLite")
    parser.add_argument("--checkpoint", default="music_links_checkpoint.json", 
                      help="Archivo JSON para guardar el progreso (por defecto: music_links_checkpoint.json)")
    parser.add_argument("--services", default="youtube,spotify,bandcamp",
                      help="Servicios a buscar, separados por comas (por defecto: youtube,spotify,bandcamp)")
    parser.add_argument("--limit", type=int, help="Límite de canciones a procesar")
    
    args = parser.parse_args()
    
    # Validar la ruta de la base de datos
    if not os.path.exists(args.db_path):
        print(f"Error: La base de datos '{args.db_path}' no existe")
        sys.exit(1)
        
    # Obtener servicios solicitados
    services = set(args.services.split(","))
    valid_services = {"youtube", "spotify", "bandcamp"}
    
    invalid_services = services - valid_services
    if invalid_services:
        print(f"Error: Servicios inválidos: {', '.join(invalid_services)}")
        print(f"Servicios válidos: {', '.join(valid_services)}")
        sys.exit(1)
        
    # Iniciar el actualizador
    updater = MusicLinkUpdater(args.db_path, args.checkpoint, services, args.limit)
    
    try:
        updater.run()
    except KeyboardInterrupt:
        print("\nProceso interrumpido por el usuario")
        updater._save_checkpoint()
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()