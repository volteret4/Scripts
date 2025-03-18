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



class MusicLinkUpdater():
    def __init__(self, db_path: str, checkpoint_path: str, services: Set[str], 
                spotify_client_id: Optional[str] = None, 
                spotify_client_secret: Optional[str] = None,
                google_api_key: Optional[str] = None,
                google_cx: Optional[str] = None,
                lastfm_api_key: Optional[str] = None,
                limit: Optional[int] = None,
                force_update: bool = False,
                delete_old: bool = False,
                **kwargs):

        """
        Inicializa el actualizador de enlaces para canciones.
        
        Args:
            db_path: Ruta al archivo de la base de datos SQLite
            checkpoint_path: Archivo JSON para guardar el progreso
            services: Conjunto de servicios a buscar ('youtube', 'spotify', 'bandcamp', 'soundcloud', 'boomkat')
            spotify_client_id: Client ID para la API de Spotify
            spotify_client_secret: Client Secret para la API de Spotify
            limit: Límite de canciones a procesar (None para procesar todas)
            force_update: Si es True, actualiza los enlaces incluso si ya existen
            delete_old: Si es True y force_update es True, elimina los enlaces existentes si no se encuentra uno nuevo
        """
        self.db_path = db_path
        self.checkpoint_path = checkpoint_path
        self.services = services
        self.limit = limit
        self.spotify_client_id = spotify_client_id
        self.spotify_client_secret = spotify_client_secret
        self.lastfm_api_key = lastfm_api_key
        self.google_api_key = google_api_key
        self.google_cx = google_cx
        self.force_update = force_update
        self.delete_old = delete_old
        print(f"spotify_client_id: {spotify_client_id}")
        print(f"spotify_secret_id: {spotify_client_secret}")

        self.spotify = None
        if 'spotify' in services:
            self._init_spotify_api()

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
        self.log(f"Archivo de checkpoint: {checkpoint_path}")
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
            

    def _init_spotify_api(self):
        """Inicializa la conexión a la API de Spotify"""
        try:
            # Usar credenciales proporcionadas o buscar en variables de entorno
            client_id = self.spotify_client_id or os.getenv("SPOTIFY_CLIENT_ID")
            client_secret = self.spotify_client_secret or os.getenv("SPOTIFY_CLIENT_SECRET")
            
            if client_id and client_secret:
                from spotipy.oauth2 import SpotifyClientCredentials
                import spotipy
                
                client_credentials_manager = SpotifyClientCredentials(
                    client_id=client_id, 
                    client_secret=client_secret
                )
                self.spotify = spotipy.Spotify(
                    client_credentials_manager=client_credentials_manager,
                    retries=3,
                    requests_timeout=20
                )
                # Verificar que funciona con una consulta simple
                self.spotify.search(q="test", limit=1)
                self.log("API de Spotify inicializada correctamente")
            else:
                self.log("ADVERTENCIA: No se encontraron credenciales para la API de Spotify")
        except Exception as e:
            self.spotify = None
            self.log(f"Error al inicializar la API de Spotify: {str(e)}")


    def _load_checkpoint(self) -> int:
        """Carga el último ID procesado desde el archivo de checkpoint."""
        if not os.path.exists(self.checkpoint_path):
            return 0
            
        try:
            with open(self.checkpoint_path, 'r') as f:
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
        
        with open(self.checkpoint_path, 'w') as f:
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
        
        # Verificar que tenemos la información necesaria
        required_fields = ['artist', 'title']
        for field in required_fields:
            if not song.get(field):
                self.log(f"Error: Falta campo requerido en la canción: {field}")
                return (None, None)
        
        self.log(f"Buscando en Spotify: {song['artist']} - {song['title']}")
        
        # Verificar credenciales
        if not spotify_client_id or not spotify_client_secret:
            # Intentar obtener credenciales del entorno
            import os
            env_client_id = os.environ.get('SPOTIPY_CLIENT_ID')
            env_client_secret = os.environ.get('SPOTIPY_CLIENT_SECRET')
            
            if env_client_id and env_client_secret:
                self.log("Usando credenciales de Spotify desde variables de entorno")
                spotify_client_id = env_client_id
                spotify_client_secret = env_client_secret
            else:
                self.log("Error: Se requieren credenciales de Spotify (client_id y client_secret)")
                return (None, None)
        
        # Asegurar que las credenciales son strings y eliminar espacios
        spotify_client_id = str(spotify_client_id).strip()
        spotify_client_secret = str(spotify_client_secret).strip()
        
        # Verificar que las credenciales no están vacías después de limpiar
        if not spotify_client_id or not spotify_client_secret:
            self.log("Error: Las credenciales de Spotify están vacías después de eliminar espacios")
            return (None, None)
        
        try:
            # Configurar autenticación con manejo de cache
            auth_manager = None
            
            try:
                # Configurar el administrador de autenticación con cache
                import os
                cache_path = os.path.join(os.path.expanduser("~"), ".cache-spotify")
                
                self.log(f"Intentando autenticación Spotify (client_id: {spotify_client_id[:5]}...)")
                auth_manager = SpotifyClientCredentials(
                    client_id=spotify_client_id,
                    client_secret=spotify_client_secret,
                    cache_handler=spotipy.cache_handler.CacheFileHandler(cache_path=cache_path)
                )
                
                # Crear cliente con retry y timeout configurados
                sp = spotipy.Spotify(
                    client_credentials_manager=auth_manager,
                    retries=3,  # Reintentos automáticos
                    requests_timeout=20,  # Timeout en segundos
                    status_retries=3,
                    status_forcelist=(429, 500, 502, 503, 504)  # Códigos de error para reintentar
                )
                
                # Verificar conexión con una consulta simple
                sp.search(q="test", limit=1)
                self.log("Autenticación Spotify exitosa")
                
            except spotipy.exceptions.SpotifyException as auth_error:
                self.log(f"Error de autenticación Spotify: {auth_error}")
                
                # Si el error es de credenciales inválidas, mostrar más información
                if "invalid_client" in str(auth_error):
                    self.log("Las credenciales proporcionadas son inválidas. Verifique client_id y client_secret.")
                    self.log("Tip: Asegúrese de que las credenciales están activas en el Dashboard de Spotify")
                    return (None, None)
                else:
                    # Intentar un método alternativo: usar variables de entorno temporalmente
                    import os
                    self.log("Intentando método alternativo con variables de entorno...")
                    
                    # Guardar variables originales
                    old_client_id = os.environ.get('SPOTIPY_CLIENT_ID')
                    old_client_secret = os.environ.get('SPOTIPY_CLIENT_SECRET')
                    
                    try:
                        # Establecer variables temporales
                        os.environ['SPOTIPY_CLIENT_ID'] = spotify_client_id
                        os.environ['SPOTIPY_CLIENT_SECRET'] = spotify_client_secret
                        
                        # Crear cliente sin autenticación explícita (usará las variables de entorno)
                        sp = spotipy.Spotify(retries=3, requests_timeout=20)
                        sp.search(q="test", limit=1)
                        self.log("Autenticación exitosa usando variables de entorno")
                        
                    except Exception as env_error:
                        self.log(f"Falló método alternativo: {env_error}")
                        return (None, None)
                    finally:
                        # Restaurar variables originales
                        if old_client_id:
                            os.environ['SPOTIPY_CLIENT_ID'] = old_client_id
                        else:
                            os.environ.pop('SPOTIPY_CLIENT_ID', None)
                            
                        if old_client_secret:
                            os.environ['SPOTIPY_CLIENT_SECRET'] = old_client_secret
                        else:
                            os.environ.pop('SPOTIPY_CLIENT_SECRET', None)
            
            if not self.spotify:
                self.log("Error: Cliente de Spotify no inicializado")
                return (None, None)
            
            # Verificar que tenemos la información necesaria
            required_fields = ['artist', 'title']
            for field in required_fields:
                if not song.get(field):
                    self.log(f"Error: Falta campo requerido en la canción: {field}")
                    return (None, None)

            # Construir la consulta de búsqueda de manera inteligente
            try:
                # Construir la consulta de búsqueda
                query_parts = []
                
                # Incluir artista y título
                artist_query = f"artist:{song['artist']}"
                title_query = f"track:{song['title']}"
                
                query_parts = [artist_query, title_query]
                
                # Agregar album si está disponible
                if song.get('album'):
                    album_query = f"album:{song['album']}"
                    query_parts.append(album_query)
                
                # Construir query principal y alternativo
                primary_query = " ".join(query_parts)
                
                # También crear una consulta alternativa más permisiva
                alt_query = f"{song['artist']} {song['title']}"
                
                # Realizar la búsqueda primero con la consulta formal
                self.log(f"Ejecutando consulta Spotify: {primary_query}")
                results = self.spotify.search(q=primary_query, type='track', limit=5)
                
                # Si no hay resultados, intentar con la consulta alternativa
                if not results.get('tracks', {}).get('items'):
                    self.log(f"Sin resultados. Intentando consulta alternativa: {alt_query}")
                    results = self.spotify.search(q=alt_query, type='track', limit=5)
                
                # Verificar resultados
                if not results.get('tracks', {}).get('items'):
                    self.log("No se encontraron resultados en Spotify")
                    return (None, None)

            except Exception as e:
                self.log(f"Error al buscar en Spotify: {e}")
                import traceback
                self.log(f"Detalles del error: {traceback.format_exc()}")
                return (None, None)
                
                # Tomar el primer resultado
            
            # Función para normalizar texto y calcular similitud
            def normalize_text(text):
                import re
                if not text:
                    return ""
                # Convertir a minúsculas y eliminar caracteres especiales
                text = text.lower()
                text = re.sub(r'[^\w\s]', '', text)
                text = re.sub(r'\s+', ' ', text).strip()
                return text
            
            def similarity_score(text1, text2):
                text1 = normalize_text(text1)
                text2 = normalize_text(text2)
                
                # Si alguno está vacío, no hay similitud
                if not text1 or not text2:
                    return 0
                    
                # Verificar inclusión directa
                if text1 in text2 or text2 in text1:
                    return 0.9
                
                # Calcular similitud de palabras comunes
                words1 = set(text1.split())
                words2 = set(text2.split())
                common_words = words1.intersection(words2)
                
                if not words1 or not words2:
                    return 0
                    
                return len(common_words) / max(len(words1), len(words2))
            
            # Evaluar cada resultado con un sistema de puntuación
            best_match = None
            best_score = 0
            
            for track in results['tracks']['items']:
                # Calcular puntuación para este track
                artist_score = max([similarity_score(song['artist'], artist['name']) for artist in track['artists']])
                title_score = similarity_score(song['title'], track['name'])
                
                # Calcular puntuación de álbum si está disponible
                album_score = 0
                if song.get('album') and track.get('album', {}).get('name'):
                    album_score = similarity_score(song['album'], track['album']['name'])
                
                # Calcular puntuación total (dar más peso al artista y título)
                total_score = (artist_score * 0.5) + (title_score * 0.4) + (album_score * 0.1)
                
                # Registrar para depuración
                self.log(f"Candidato: {track['artists'][0]['name']} - {track['name']} (Score: {total_score:.2f})")
                
                # Actualizar mejor coincidencia si es necesario
                if total_score > best_score:
                    best_score = total_score
                    best_match = track
            
            # Determinar si tenemos una buena coincidencia
            if best_match and best_score > 0.4:  # Umbral ajustable
                track_id = best_match['id']
                track_url = best_match['external_urls']['spotify']
                artist_name = best_match['artists'][0]['name']
                
                self.log(f"Encontrado en Spotify: {best_match['name']} por {artist_name} (Score: {best_score:.2f})")
                return (track_url, track_id)
            else:
                self.log(f"No se encontró coincidencia suficientemente buena en Spotify (Mejor score: {best_score:.2f})")
                return (None, None)
        
        except Exception as e:
            self.log(f"Error al buscar en Spotify: {e}")
            # Registrar detalles adicionales para depuración
            import traceback
            self.log(f"Detalles del error: {traceback.format_exc()}")
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

def main(config=None):
    # Si el script se ejecuta directamente (no desde el padre)
    if config is None:
        parser = argparse.ArgumentParser(description='Actualizar enlaces de música')
        parser.add_argument('--db-path', help='Ruta a la base de datos SQLite')
        parser.add_argument('--checkpoint-path', help='Archivo de punto de control')
        parser.add_argument('--services', help='Servicios a buscar (separados por comas)')
        parser.add_argument('--limit', type=int, help='Límite de canciones a procesar')
        parser.add_argument('--force-update', action='store_true', help='Actualizar enlaces existentes')
        parser.add_argument('--delete-old', action='store_true', help='Eliminar enlaces antiguos')
        parser.add_argument('--spotify-client-id', help='ID de cliente de Spotify')
        parser.add_argument('--spotify-client-secret', help='Secreto de cliente de Spotify')
        parser.add_argument('--google-api-key', help='Clave de API de Google')
        parser.add_argument('--google-cx', help='ID de motor de búsqueda personalizado de Google')
        parser.add_argument('--lastfm-api-key', help='Clave de API de Last.fm')
        parser.add_argument('--config', help='Archivo de configuración JSON')
        
        args = parser.parse_args()
        
        # Inicializar la configuración
        final_config = {}
        
        # Si se proporcionó un archivo de configuración JSON en los argumentos, cargarlo
        if args.config:
            with open(args.config, 'r') as f:
                json_config = json.load(f)
                
            # Combinar configuraciones comunes y específicas
            final_config.update(json_config.get("common", {}))
            final_config.update(json_config.get("enlaces_canciones_spot_lastfm", {}))
        
        # Los argumentos de línea de comandos tienen mayor prioridad
        arg_dict = vars(args)
        for arg_name, arg_value in arg_dict.items():
            if arg_value is not None and arg_name != 'config':
                # Convertir nombres de argumentos con guiones a subrayados
                config_key = arg_name.replace('-', '_')
                final_config[config_key] = arg_value
    else:
        # El script se está ejecutando desde el padre y ya recibió la configuración filtrada
        final_config = config

    # Procesamiento común a ambos casos
    
    # Convertir 'limit' a int si es una cadena
    if 'limit' in final_config and isinstance(final_config['limit'], str):
        try:
            final_config['limit'] = int(final_config['limit']) if final_config['limit'] != '0' else None
        except ValueError:
            final_config['limit'] = None
    
    # Asegurarse de que checkpoint existe
    if 'checkpoint_path' not in final_config and 'checkpoint_path' in final_config:
        final_config['checkpoint_path'] = final_config['checkpoint_path']

    # Convertir services de string a set si viene como string
    if 'services' in final_config and isinstance(final_config['services'], str):
        final_config['services'] = set(final_config['services'].split(','))
    elif 'services' in final_config and isinstance(final_config['services'], list):
        final_config['services'] = set(final_config['services'])
    
    # Validaciones
    required_params = ['db_path', 'checkpoint_path', 'services']
    missing_params = [param for param in required_params if param not in final_config]
    if missing_params:
        print(f"Error: Faltan parámetros requeridos: {', '.join(missing_params)}")
        sys.exit(1)
    
    # Validar la ruta de la base de datos
    if not os.path.exists(final_config['db_path']):
        print(f"Error: La base de datos '{final_config['db_path']}' no existe")
        sys.exit(1)
    
    # Verificar que delete-old solo se use con force-update
    if final_config.get('delete_old') and not final_config.get('force_update'):
        print("Error: La opción delete_old requiere force_update")
        sys.exit(1)
    
    # Validar servicios
    services = final_config['services']
    valid_services = {"youtube", "spotify", "bandcamp", "soundcloud", "lastfm", "boomkat", "musicbrainz"}
    invalid_services = services - valid_services
    if invalid_services:
        print(f"Error: Servicios inválidos: {', '.join(invalid_services)}")
        print(f"Servicios válidos: {', '.join(valid_services)}")
        sys.exit(1)
    
    # Nota: No necesitamos filtrar aquí si ya se hizo en el script padre
    if config is None:
        # Filtrar los parámetros vacíos o falsos solo si no vinieron del padre
        filtered_config = {k: v for k, v in final_config.items() if v not in [False, "", [], {}, None, "0"]}
        
        # Restaurar los parámetros requeridos aunque estén vacíos
        for param in required_params:
            if param not in filtered_config and param in final_config:
                filtered_config[param] = final_config[param]
    else:
        # Si vino del padre, asumimos que ya están filtrados
        filtered_config = final_config
    
    # Iniciar el actualizador con los parámetros filtrados
    try:
        updater = MusicLinkUpdater(**filtered_config)
        updater.run()
    except KeyboardInterrupt:
        print("\nProceso interrumpido por el usuario")
        if hasattr(updater, '_save_checkpoint'):
            updater._save_checkpoint()
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()