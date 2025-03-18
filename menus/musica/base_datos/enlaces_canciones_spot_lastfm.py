#!/usr/bin/env python3
import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
import requests
from bs4 import BeautifulSoup
from base_module import PROJECT_ROOT



class MusicLinkUpdater:
    def __init__(self, db_path: str, checkpoint_file: str, services: Set[str], 
                spotify_client_id: Optional[str] = None, 
                spotify_client_secret: Optional[str] = None,
                google_api_key: Optional[str] = None,
                google_cx: Optional[str] = None,
                lastfm_api_key: Optional[str] = None,
                limit: Optional[int] = None,
                force_update: bool = False,
                delete_old: bool = False):
        """
        Inicializa el actualizador de enlaces para canciones.
        
        Args:
            db_path: Ruta al archivo de la base de datos SQLite
            checkpoint_file: Archivo JSON para guardar el progreso
            services: Conjunto de servicios a buscar ('youtube', 'spotify', 'bandcamp', 'soundcloud', 'boomkat')
            spotify_client_id: Client ID para la API de Spotify
            spotify_client_secret: Client Secret para la API de Spotify
            limit: Límite de canciones a procesar (None para procesar todas)
            force_update: Si es True, actualiza los enlaces incluso si ya existen
            delete_old: Si es True y force_update es True, elimina los enlaces existentes si no se encuentra uno nuevo
        """
        self.db_path = db_path
        self.checkpoint_file = checkpoint_file
        self.services = services
        self.limit = limit
        self.spotify_client_id = spotify_client_id
        self.spotify_client_secret = spotify_client_secret
        self.lastfm_api_key = lastfm_api_key
        self.google_api_key = google_api_key
        self.google_cx = google_cx
        self.force_update = force_update
        self.delete_old = delete_old
        
        # Estadísticas
        self.stats = {
            "processed": 0,
            "skipped": 0,
            "updated": 0,
            "failed": 0,
            "deleted": 0,
            "by_service": {
                "youtube": 0,
                "spotify": 0,
                "bandcamp": 0,
                "soundcloud": 0,
                "boomkat": 0
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
        if 'spotify' in services:
            if spotify_client_id and spotify_client_secret:
                self.log("API de Spotify configurada correctamente")
            else:
                self.log("ADVERTENCIA: Se solicitó el servicio Spotify pero no se proporcionaron credenciales de API")
        self.log(f"Último ID procesado: {self.last_processed_id}")
        if force_update:
            self.log("Modo force-update activado: se actualizarán todos los enlaces aunque ya existan")
        if delete_old and force_update:
            self.log("Modo delete-old activado: se eliminarán los enlaces existentes si no se encuentra uno nuevo")


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
        if self.force_update:
            # Si force_update está activado, selecciona todas las canciones independientemente
            # de si ya tienen enlaces o no
            query = """
            SELECT s.id, s.title, s.artist, s.album
            FROM songs s
            WHERE s.id > ?
            ORDER BY s.id ASC
            """
        else:
            # Comportamiento original: solo procesa canciones sin procesar
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
        
    def get_album_songs(self, album_name: str, artist_name: str) -> List[Dict]:
        """
        Obtiene todas las canciones de un álbum específico.
        
        Args:
            album_name: Nombre del álbum
            artist_name: Nombre del artista
            
        Returns:
            Lista de canciones del álbum
        """
        query = """
        SELECT id, title, artist, album
        FROM songs
        WHERE album = ? AND artist = ?
        """
        
        self.cursor.execute(query, (album_name, artist_name))
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
        
    def search_spotify(self, song: Dict, spotify_client_id: str = None, spotify_client_secret: str = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Realiza una búsqueda de una canción en Spotify utilizando la API oficial a través de spotipy.
        
        Args:
            song: Diccionario con información de la canción
            spotify_client_id: Client ID de Spotify API
            spotify_client_secret: Client Secret de Spotify API
            
        Returns:
            Tupla (URL de Spotify, ID de Spotify) o (None, None) si no se encuentra
        """
        try:
            import spotipy
            from spotipy.oauth2 import SpotifyClientCredentials
        except ImportError:
            self.log("Error: No se pudo importar la biblioteca spotipy. Instálela con 'pip install spotipy'")
            return (None, None)
        
        self.log(f"Buscando en Spotify: {song['artist']} - {song['title']}")
        
        if not spotify_client_id or not spotify_client_secret:
            self.log("Error: Se requieren credenciales de Spotify (client_id y client_secret)")
            return (None, None)
        
        try:
            # Configurar autenticación de Spotify
            client_credentials_manager = SpotifyClientCredentials(
                client_id=spotify_client_id,
                client_secret=spotify_client_secret
            )
            sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
            
            # Construir la consulta de búsqueda
            query = f"artist:{song['artist']} track:{song['title']}"
            if song['album']:
                query += f" album:{song['album']}"
            
            # Realizar la búsqueda en Spotify
            self.log(f"Ejecutando consulta Spotify: {query}")
            results = sp.search(q=query, type='track', limit=5)
            
            # Verificar si hay resultados
            if results and results['tracks']['items']:
                # Obtener el primer resultado (el más relevante)
                track = results['tracks']['items'][0]
                track_id = track['id']
                track_url = track['external_urls']['spotify']
                
                # Verificar si el artista coincide aproximadamente
                track_artist = track['artists'][0]['name'].lower()
                our_artist = song['artist'].lower()
                
                # Verificar que el resultado sea relevante (correspondencia aproximada)
                if our_artist in track_artist or track_artist in our_artist:
                    self.log(f"Encontrado en Spotify: {track['name']} por {track['artists'][0]['name']}")
                    return (track_url, track_id)
                else:
                    self.log(f"Resultado descartado por no coincidir el artista: {track['artists'][0]['name']} vs {song['artist']}")
                    
                # Si llegamos aquí, el primer resultado no era adecuado
                # Podríamos intentar con los siguientes resultados
                for track in results['tracks']['items'][1:]:
                    track_artist = track['artists'][0]['name'].lower()
                    if our_artist in track_artist or track_artist in our_artist:
                        track_id = track['id']
                        track_url = track['external_urls']['spotify']
                        self.log(f"Encontrado en Spotify (resultado alternativo): {track['name']} por {track['artists'][0]['name']}")
                        return (track_url, track_id)
                
            self.log("No se encontró en Spotify o los resultados no coinciden lo suficiente")
            return (None, None)
            
        except Exception as e:
            self.log(f"Error al buscar en Spotify: {e}")
            return (None, None)
        
 
    def search_bandcamp(self, song: Dict) -> Optional[str]:
        """
        Realiza una búsqueda de una canción en Bandcamp mediante web scraping.
        
        Args:
            song: Diccionario con información de la canción
            
        Returns:
            URL de Bandcamp o None si no se encuentra
        """
        import requests
        from bs4 import BeautifulSoup
        import re
        import time
        
        self.log(f"Buscando en Bandcamp: {song['artist']} - {song['title']}")
        
        try:
            # Bandcamp no tiene API pública oficial, así que usamos web scraping
            # Construir la consulta de búsqueda
            query = f"{song['artist']} {song['title']}"
            if song['album']:
                query += f" {song['album']}"
                
            sanitized_query = query.replace(" ", "+")
            search_url = f"https://bandcamp.com/search?q={sanitized_query}"
            
            # Configurar encabezados HTTP para simular un navegador real
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Referer": "https://bandcamp.com/",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Cache-Control": "max-age=0"
            }
            
            # Realizar la solicitud HTTP
            self.log(f"Solicitando URL: {search_url}")
            response = requests.get(search_url, headers=headers, timeout=10)
            
            # Verificar si la solicitud fue exitosa
            if response.status_code == 200:
                # Parsear la página HTML
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Buscar resultados de canciones
                # El formato exacto dependería de la estructura actual de Bandcamp
                result_items = soup.select('.result-items li.searchresult')
                
                if result_items:
                    # Iterar sobre los resultados para encontrar el más relevante
                    for item in result_items:
                        # Buscar información en el resultado
                        title_elem = item.select_one('.heading')
                        artist_elem = item.select_one('.subhead a')
                        link_elem = item.select_one('.itemurl')
                        
                        if title_elem and artist_elem and link_elem:
                            result_title = title_elem.text.strip().lower()
                            result_artist = artist_elem.text.strip().lower()
                            result_url = link_elem.text.strip()
                            
                            # Verificar si coincide con lo que buscamos
                            song_title_lower = song['title'].lower()
                            song_artist_lower = song['artist'].lower()
                            
                            # Comprobar si el título y artista coinciden aproximadamente
                            title_match = song_title_lower in result_title or result_title in song_title_lower
                            artist_match = song_artist_lower in result_artist or result_artist in song_artist_lower
                            
                            if title_match and artist_match:
                                self.log(f"Encontrado en Bandcamp: {result_url}")
                                return result_url
                
                self.log("No se encontraron resultados relevantes en Bandcamp")
                return None
            else:
                self.log(f"Error al buscar en Bandcamp: Código de estado HTTP {response.status_code}")
                return None
                
        except Exception as e:
            self.log(f"Error al buscar en Bandcamp: {e}")
            return None
        
    def search_soundcloud(self, song: Dict) -> Optional[str]:
        """
        Busca una canción en SoundCloud usando la API de Google Search.
        
        Args:
            song: Diccionario con información de la canción
                
        Returns:
            URL de SoundCloud o None si no se encuentra
        """
        self.log(f"Buscando en SoundCloud: {song['artist']} - {song['title']}")
        
        # Configuración para la API de Google Custom Search
        api_key = self.google_api_key  # Asumiendo que tienes la clave almacenada en la clase
        search_engine_id = self.google_cx  # El ID de tu motor de búsqueda personalizado
        
        # Crear una consulta de búsqueda
        query = f"{song['artist']} {song['title']} site:soundcloud.com"
        
        try:
            # Realizar la búsqueda usando la API de Google
            search_url = "https://www.googleapis.com/customsearch/v1"
            params = {
                'key': api_key,
                'cx': search_engine_id,
                'q': query
            }
            
            response = requests.get(search_url, params=params)
            response.raise_for_status()
            results = response.json()
            
            # Verificar si hay resultados
            if 'items' in results and len(results['items']) > 0:
                # Tomar el primer resultado que sea de soundcloud.com
                for item in results['items']:
                    url = item['link']
                    if 'soundcloud.com' in url:
                        self.log(f"Encontrada URL de SoundCloud: {url}")
                        return url
            
            self.log("No se encontró la canción en SoundCloud")
            return None
        
        except Exception as e:
            self.log(f"Error al buscar en SoundCloud con API de Google: {str(e)}")
            return None


    # def search_soundcloud(self, song: Dict) -> Optional[str]:
    #     """
    #     Busca una canción en SoundCloud usando web scraping.
        
    #     Args:
    #         song: Diccionario con información de la canción
                
    #     Returns:
    #         URL de SoundCloud o None si no se encuentra
    #     """
    #     self.log(f"Buscando en SoundCloud: {song['artist']} - {song['title']}")
    #     sleep = "1"
    #     time.sleep(float(sleep))

    #     # Crear una consulta de búsqueda
    #     query = f"{song['artist']} {song['title']} site:soundcloud.com"
    #     search_url = f"https://www.google.com/search?q={requests.utils.quote(query)}"
        
    #     try:
    #         # Configurar headers para simular un navegador
    #         headers = {
    #             'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    #         }
            
    #         # Realizar la búsqueda en Google
    #         response = requests.get(search_url, headers=headers, timeout=10)
    #         response.raise_for_status()
            
    #         # Analizar el HTML de la respuesta
    #         soup = BeautifulSoup(response.text, 'html.parser')
            
    #         # Buscar enlaces a SoundCloud en los resultados
    #         links = soup.find_all('a')
    #         for link in links:
    #             href = link.get('href')
    #             if href and 'soundcloud.com' in href and not 'google' in href:
    #                 # Extraer la URL real de SoundCloud
    #                 if '/url?q=' in href:
    #                     # Google encapsula URLs, necesitamos extraer la URL real
    #                     real_url = href.split('/url?q=')[1].split('&')[0]
    #                 else:
    #                     real_url = href
                    
    #                 # Verificar que es una URL de SoundCloud válida
    #                 if real_url.startswith('https://soundcloud.com/'):
    #                     self.log(f"Encontrada URL de SoundCloud: {real_url}")
    #                     return real_url
            
    #         self.log("No se encontró la canción en SoundCloud")
    #         return None
        
    #     except Exception as e:
    #         self.log(f"Error al buscar en SoundCloud: {str(e)}")
    #         return None
        
    def search_boomkat(self, song: Dict) -> Optional[str]:
        """
        Simula la búsqueda de una canción en Boomkat.
        
        Args:
            song: Diccionario con información de la canción
            
        Returns:
            URL de Boomkat o None si no se encuentra
        """
        self.log(f"Buscando en Boomkat: {song['artist']} - {song['title']}")
        # Simular éxito con probabilidad del 40% (Boomkat es más especializado)
        if hash(f"{song['id']}boomkat") % 100 < 40:
            artist_slug = song['artist'].lower().replace(' ', '-')
            
            # Boomkat generalmente enlaza a álbumes, no a canciones individuales
            if song['album']:
                album_slug = song['album'].lower().replace(' ', '-')
                return f"https://boomkat.com/products/{album_slug}-{artist_slug}"
            else:
                # Si no hay álbum, usar el título de la canción como si fuera un single
                song_slug = song['title'].lower().replace(' ', '-')
                return f"https://boomkat.com/products/{song_slug}-{artist_slug}"
        return None
        

    def update_song_links(self, song_id: int, youtube_url: Optional[str] = None, 
                        spotify_url: Optional[str] = None, spotify_id: Optional[str] = None,
                        bandcamp_url: Optional[str] = None, soundcloud_url: Optional[str] = None,
                        boomkat_url: Optional[str] = None) -> bool:
        """
        Actualiza los enlaces de una canción en la base de datos.
        
        Args:
            song_id: ID de la canción
            youtube_url: URL de YouTube
            spotify_url: URL de Spotify
            spotify_id: ID de Spotify
            bandcamp_url: URL de Bandcamp
            soundcloud_url: URL de SoundCloud
            boomkat_url: URL de Boomkat
            
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
                
                # Utilizar la lógica de delete_old cuando está activado y estamos en modo force_update
                if self.force_update and self.delete_old:
                    # YouTube
                    if 'youtube' in self.services:
                        if youtube_url is not None:
                            update_fields.append("youtube_url = ?")
                            params.append(youtube_url)
                        else:
                            update_fields.append("youtube_url = NULL")
                    
                    # Spotify
                    if 'spotify' in self.services:
                        if spotify_url is not None:
                            update_fields.append("spotify_url = ?")
                            params.append(spotify_url)
                        else:
                            update_fields.append("spotify_url = NULL")
                        
                        if spotify_id is not None:
                            update_fields.append("spotify_id = ?")
                            params.append(spotify_id)
                        else:
                            update_fields.append("spotify_id = NULL")
                    
                    # Bandcamp
                    if 'bandcamp' in self.services:
                        if bandcamp_url is not None:
                            update_fields.append("bandcamp_url = ?")
                            params.append(bandcamp_url)
                        else:
                            update_fields.append("bandcamp_url = NULL")
                    
                    # SoundCloud
                    if 'soundcloud' in self.services:
                        if soundcloud_url is not None:
                            update_fields.append("soundcloud_url = ?")
                            params.append(soundcloud_url)
                        else:
                            update_fields.append("soundcloud_url = NULL")
                    
                    # Boomkat
                    if 'boomkat' in self.services:
                        if boomkat_url is not None:
                            update_fields.append("boomkat_url = ?")
                            params.append(boomkat_url)
                        else:
                            update_fields.append("boomkat_url = NULL")
                else:
                    # Comportamiento original sin delete_old
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
                        update_fields.append("bandcamp_url = ?")
                        params.append(bandcamp_url)
                    
                    if soundcloud_url is not None:
                        update_fields.append("soundcloud_url = ?")
                        params.append(soundcloud_url)
                    
                    if boomkat_url is not None:
                        update_fields.append("boomkat_url = ?")
                        params.append(boomkat_url)
                
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
                    fields.append("bandcamp_url")
                    values.append(bandcamp_url)
                    placeholders.append("?")
                
                if soundcloud_url is not None:
                    fields.append("soundcloud_url")
                    values.append(soundcloud_url)
                    placeholders.append("?")
                
                if boomkat_url is not None:
                    fields.append("boomkat_url")
                    values.append(boomkat_url)
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
        
        # Verificar si la canción ya tiene enlaces y si no estamos en modo force-update
        if not self.force_update:
            self.cursor.execute("SELECT * FROM song_links WHERE song_id = ?", (song_id,))
            existing_links = self.cursor.fetchone()
            if existing_links:
                has_all_services = True
                for service in self.services:
                    if service == 'youtube' and not existing_links['youtube_url']:
                        has_all_services = False
                        break
                    elif service == 'spotify' and not existing_links['spotify_url']:
                        has_all_services = False
                        break
                    elif service == 'bandcamp' and not existing_links['bandcamp_url']:
                        has_all_services = False
                        break
                    elif service == 'soundcloud' and not existing_links['soundcloud_url']:
                        has_all_services = False
                        break
                    elif service == 'boomkat' and not existing_links['boomkat_url']:
                        has_all_services = False
                        break
                
                if has_all_services:
                    self.log(f"Canción ID {song_id} ya tiene todos los enlaces solicitados. Omitiendo.")
                    self.stats["skipped"] += 1
                    return True
        
        # Obtener enlaces existentes si estamos en modo delete-old
        existing_links = {}
        if self.force_update and self.delete_old:
            self.cursor.execute("SELECT * FROM song_links WHERE song_id = ?", (song_id,))
            row = self.cursor.fetchone()
            if row:
                for service in self.services:
                    if service == 'youtube' and row['youtube_url']:
                        existing_links['youtube'] = True
                    elif service == 'spotify' and row['spotify_url']:
                        existing_links['spotify'] = True
                    elif service == 'bandcamp' and row['bandcamp_url']:
                        existing_links['bandcamp'] = True
                    elif service == 'soundcloud' and row['soundcloud_url']:
                        existing_links['soundcloud'] = True
                    elif service == 'boomkat' and row['boomkat_url']:
                        existing_links['boomkat'] = True
        
        youtube_url = None
        spotify_url = None
        spotify_id = None
        bandcamp_url = None
        soundcloud_url = None
        boomkat_url = None
        
        updated = False
        deleted = False
        
        # Buscar en YouTube
        if 'youtube' in self.services:
            youtube_url = self.search_youtube(song)
            if youtube_url:
                self.stats["by_service"]["youtube"] += 1
                updated = True
            elif self.force_update and self.delete_old and 'youtube' in existing_links:
                deleted = True
                self.log(f"Eliminando enlace de YouTube para canción ID {song_id}\n")
                
        # Buscar en Spotify
        if 'spotify' in self.services:
            spotify_url, spotify_id = self.search_spotify(song, self.spotify_client_id, self.spotify_client_secret)
            if spotify_url:
                self.stats["by_service"]["spotify"] += 1
                updated = True
            elif self.force_update and self.delete_old and 'spotify' in existing_links:
                deleted = True
                self.log(f"Eliminando enlace de Spotify para canción ID {song_id}\n")
                
        # Buscar en Bandcamp
        if 'bandcamp' in self.services:
            bandcamp_url = self.search_bandcamp(song)
            if bandcamp_url:
                self.stats["by_service"]["bandcamp"] += 1
                updated = True
            elif self.force_update and self.delete_old and 'bandcamp' in existing_links:
                deleted = True
                self.log(f"Eliminando enlace de Bandcamp para canción ID {song_id}\n")
                
        # Buscar en SoundCloud
        if 'soundcloud' in self.services:
            soundcloud_url = self.search_soundcloud(song)
            if soundcloud_url:
                self.stats["by_service"]["soundcloud"] += 1
                updated = True
            elif self.force_update and self.delete_old and 'soundcloud' in existing_links:
                deleted = True
                self.log(f"Eliminando enlace de SoundCloud para canción ID {song_id}\n")

        # Buscar en Boomkat
        if 'boomkat' in self.services:
            boomkat_url = self.search_boomkat(song)
            if boomkat_url:
                self.stats["by_service"]["boomkat"] += 1
                updated = True
            elif self.force_update and self.delete_old and 'boomkat' in existing_links:
                deleted = True
                self.log(f"Eliminando enlace de Boomkat para canción ID {song_id}\n")
                
        # Actualizar la base de datos
        if updated or deleted:
            success = self.update_song_links(
                song_id, youtube_url, spotify_url, spotify_id, bandcamp_url, soundcloud_url, boomkat_url
            )
            
            if success:
                if updated:
                    self.stats["updated"] += 1
                    self.log(f"Enlaces actualizados para canción ID {song_id}\n")
                if deleted:
                    self.stats["deleted"] += 1
                    self.log(f"Enlaces eliminados para canción ID {song_id}\n")
                return success
            else:
                self.stats["failed"] += 1
                self.log(f"Error al actualizar enlaces para canción ID {song_id}\n")
                return False
        else:
            self.stats["skipped"] += 1
            self.log(f"No se encontraron enlaces para canción ID {song_id}\n")
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
                    bandcamp_url TEXT,
                    soundcloud_url TEXT,
                    boomkat_url TEXT
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
            
                if "soundcloud_url" not in columns:
                    self.log("Añadiendo columna soundcloud_url a la tabla song_links...")
                    self.cursor.execute("ALTER TABLE song_links ADD COLUMN soundcloud_url TEXT")
                    self.conn.commit()

                if "boomkat_url" not in columns:
                    self.log("Añadiendo columna boomkat_url a la tabla song_links...")
                    self.cursor.execute("ALTER TABLE song_links ADD COLUMN boomkat_url TEXT")
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
            self.log(f"Enlaces eliminados: {self.stats['deleted']}")
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

    
    # Validar la ruta de la base de datos
    if not os.path.exists(args.db_path):
        print(f"Error: La base de datos '{args.db_path}' no existe")
        sys.exit(1)
    
    # Verificar que delete-old solo se use con force-update
    if args.delete_old and not args.force_update:
        print("Error: La opción --delete-old requiere --force-update")
        sys.exit(1)
        
    # Obtener servicios solicitados
    services = set(args.services.split(","))
    valid_services = {"youtube", "spotify", "bandcamp", "soundcloud", "lastfm", "boomkat", "musicbrainz"}
    
    invalid_services = services - valid_services
    if invalid_services:
        print(f"Error: Servicios inválidos: {', '.join(invalid_services)}")
        print(f"Servicios válidos: {', '.join(valid_services)}")
        sys.exit(1)
    
    # Verificar si los atributos existen antes de acceder a ellos
    spotify_client_id = getattr(args, 'spotify_client_id', None)
    spotify_client_secret = getattr(args, 'spotify_client_secret', None)
    
    # Verificar credenciales de Spotify si se seleccionó el servicio
    if 'spotify' in services and (not spotify_client_id or not spotify_client_secret):
        print("Advertencia: Se seleccionó el servicio Spotify pero no se proporcionaron credenciales.")
        print("Para utilizar la API de Spotify, proporcione --spotify-client-id y --spotify-client-secret")
        
    # Iniciar el actualizador
    updater = MusicLinkUpdater(
        args.db_path, 
        args.checkpoint, 
        services, 
        spotify_client_id=spotify_client_id,
        spotify_client_secret=spotify_client_secret,
        google_api_key=args.google_api_key,
        google_cx=args.google_cx,
        limit=args.limit,
        force_update=args.force_update,
        delete_old=args.delete_old,
        lastfm_api_key=args.lastfm_api_key
    )
    
    try:
        updater.run()
    except KeyboardInterrupt:
        print("\nProceso interrumpido por el usuario")
        updater._save_checkpoint()
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)



def load_config(config_file=None, required_args=None, script_name=None):
    """
    Carga configuración desde un archivo JSON y combina con argumentos de línea de comandos.
    
    Args:
        config_file: Ruta al archivo de configuración JSON.
        required_args: Lista de argumentos requeridos para este script específico.
        script_name: Nombre del script actual, para buscar configuración específica.
        
    Returns:
        args: Objeto con todos los argumentos combinados
    """
    # Crear el parser con argumentos comunes
    parser = argparse.ArgumentParser(description='Script con configuración JSON')
    parser.add_argument('--config', help='Ruta al archivo de configuración JSON')
    
    # Añadir todos los argumentos originales para mantener compatibilidad
    parser = argparse.ArgumentParser(description="Actualiza enlaces de canciones para servicios de streaming")
    parser.add_argument("db_path", help="Ruta al archivo de base de datos SQLite")
    parser.add_argument("--checkpoint", default="music_links_checkpoint.json", 
                      help="Archivo JSON para guardar el progreso (por defecto: music_links_checkpoint.json)")
    parser.add_argument("--services", default="youtube,spotify,bandcamp,soundcloud,boomkat",
                      help="Servicios a buscar, separados por comas (por defecto: youtube,spotify,bandcamp,soundcloud,boomkat)")
    parser.add_argument("--limit", type=int, help="Límite de canciones a procesar")
    parser.add_argument("--force-update", action="store_true", 
                      help="Actualizar todos los enlaces incluso si ya existen")
    parser.add_argument("--delete-old", action="store_true",
                      help="Eliminar enlaces existentes si no se encuentra uno nuevo (requiere --force-update)")
    parser.add_argument("--google-api-key", help="Api key para google")
    parser.add_argument("--google-cx", help="Cx para google. Busqueda  en google")
    parser.add_argument("--lastfm-api-key", help="API key de Last.fm")                  
    
    # Verificar si estos argumentos ya existen antes de añadirlos
    arg_dict = {action.option_strings[0] if action.option_strings else action.dest: action
                for action in parser._actions}
    
    if '--spotify-client-id' not in arg_dict:
        parser.add_argument("--spotify-client-id", help="Client ID para la API de Spotify")
    
    if '--spotify-client-secret' not in arg_dict:
        parser.add_argument("--spotify-client-secret", help="Client Secret para la API de Spotify")
    

    # Parsear argumentos de línea de comandos primero
    cmd_args = parser.parse_args()
    
    required_args.extend(["db_path", "--rate_limit"])
    # Inicializar con valores por defecto
    config = {
        "common": {
            "db_path": None,
            "rate_limit": 0.5,
            "days": 30
        },

    }
    


    
    # Usar archivo de configuración especificado en línea de comandos o el predeterminado
    config_path = cmd_args.config or config_file or "config.json"
    
    # Cargar configuración desde el archivo JSON si existe
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                file_config = json.load(f)
                config.update(file_config)
        except json.JSONDecodeError:
            print(f"Error: El archivo {config_path} no es un JSON válido")
        except Exception as e:
            print(f"Error al leer el archivo de configuración: {e}")
    
    # Crear objeto final de configuración
    final_config = {}
    
    # 1. Cargar valores comunes
    if "common" in config:
        final_config.update(config["common"])
    
    # 2. Cargar valores específicos del script actual
    if script_name and script_name in config:
        final_config.update(config[script_name])
    
    # 3. Sobrescribir con argumentos de línea de comandos (si no son None)
    for arg, value in vars(cmd_args).items():
        if value is not None and value is not False:
            # Convertir formato --arg-name a arg_name
            final_arg = arg.replace('-', '_')
            final_config[final_arg] = value
    
    # Verificar argumentos requeridos
    if required_args:
        missing = [arg for arg in required_args if arg not in final_config or final_config[arg] is None]
        if missing:
            print(f"Error: Faltan argumentos requeridos: {', '.join(missing)}")
            print(f"Configúralos en {config_path} o pásalos como parámetros")
            exit(1)
    
    # Convertir diccionario a objeto similar a los argumentos de argparse
    class Args:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)
        
        def __str__(self):
            return str(vars(self))
    
    return Args(**final_config)


if __name__ == "__main__":
    # Especificar argumentos requeridos para este script específico
    required_args = ["config"]
    

    # Cargar configuración
    args = load_config(
        config_file="config_database_creator.json",
        required_args=required_args,
        script_name="enlaces_canciones_spot_lastfm"
    )

    main()