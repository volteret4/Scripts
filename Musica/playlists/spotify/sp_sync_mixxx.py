#!/usr/bin/env python3
"""
Sincronizador de Playlists M3U a Spotify (Compatible con Cron)
Sincroniza playlists locales .m3u con Spotify usando sincronización incremental.
Solo añade canciones nuevas y elimina las que ya no existen.
"""

import os
import re
import sqlite3
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
from pathlib import Path
import logging
import time
import json
import hashlib
import argparse
from typing import List, Dict, Optional, Set
import sys
from datetime import datetime

# Configuración de rutas
script_dir = Path(__file__).parent.absolute()
project_root = script_dir.parent

# Cargar variables de entorno
env_file = project_root / ".env"
if env_file.exists():
    load_dotenv(env_file)
else:
    print(f"Error: No se encontró .env en {env_file}", file=sys.stderr)
    sys.exit(1)

# Rutas estándar del proyecto
CACHE_DIR = project_root / ".content/cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Variables de entorno
CLIENT_ID = os.getenv('SPOTIFY_CLIENT')
CLIENT_SECRET = os.getenv('SPOTIFY_SECRET')
REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT')

class PlaylistSyncer:
    def __init__(self, db_path: str, interactive: bool = True):
        """
        Inicializa el sincronizador de playlists.
        
        Args:
            db_path: Ruta a la base de datos SQLite
            interactive: Si False, no solicita input del usuario (para cron)
        """
        self.db_path = db_path
        self.interactive = interactive
        self.sync_state_file = CACHE_DIR / "playlist_sync_state.json"
        
        # Configurar logging según el modo
        log_level = logging.INFO if interactive else logging.WARNING
        log_handlers = [logging.FileHandler(CACHE_DIR / 'playlist_sync.log')]
        if interactive:
            log_handlers.append(logging.StreamHandler())
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=log_handlers,
            force=True
        )
        self.logger = logging.getLogger(__name__)
        
        # Verificar credenciales
        if not CLIENT_ID or not CLIENT_SECRET:
            self.logger.error("Error: SPOTIFY_CLIENT y SPOTIFY_SECRET deben estar configurados en .env")
            sys.exit(1)
        
        # Configurar Spotify
        self._setup_spotify()
        
        # Cargar estado de sincronización anterior
        self.sync_state = self._load_sync_state()
    
    def _setup_spotify(self):
        """Configura la conexión con Spotify"""
        scope = "playlist-modify-public playlist-modify-private playlist-read-private"
        cache_path = CACHE_DIR / "sync_token.txt"
        
        self.sp_oauth = SpotifyOAuth(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            redirect_uri=REDIRECT_URI,
            scope=scope,
            open_browser=False,
            cache_path=str(cache_path)
        )
        
        # Obtener token
        token_info = self._get_valid_token()
        if not token_info:
            if self.interactive:
                self.logger.error("No se pudo obtener token de acceso")
            sys.exit(1)
        
        self.sp = spotipy.Spotify(auth=token_info['access_token'])
        
        # Obtener información del usuario
        try:
            user = self.sp.current_user()
            self.user_id = user['id']
            self.logger.info(f"Conectado como: {user.get('display_name', user['id'])}")
        except Exception as e:
            self.logger.error(f"Error obteniendo información del usuario: {e}")
            sys.exit(1)
    
    def _get_valid_token(self):
        """Obtener token válido, compatible con modo no interactivo"""
        try:
            # Intentar obtener token desde caché
            token_info = self.sp_oauth.get_cached_token()
            if token_info:
                self.logger.debug("Token obtenido desde caché")
                return token_info
        except Exception as e:
            self.logger.warning(f"Error leyendo token desde caché: {e}")
        
        # Si no hay token y estamos en modo no interactivo (cron), fallar
        if not self.interactive:
            self.logger.error("No hay token válido y el script está en modo no interactivo")
            self.logger.error("Ejecuta el script manualmente una vez para autorizar")
            return None
        
        # Modo interactivo: solicitar autorización
        try:
            auth_url = self.sp_oauth.get_authorize_url()
            print(f"\n🔗 Visita esta URL para autorizar la aplicación:")
            print(f"{auth_url}")
            print(f"\nDespués de autorizar, serás redirigido a una URL que empieza con:")
            print(f"{REDIRECT_URI}")
            print(f"\nCopia el código de la URL y pégalo aquí.")
            
            code = input("\n📋 Pega el código de autorización: ").strip()
            
            if not code:
                self.logger.error("No se proporcionó código de autorización")
                return None
            
            token_info = self.sp_oauth.get_access_token(code, as_dict=True, check_cache=False)
            self.logger.info("✅ Token obtenido exitosamente")
            return token_info
            
        except Exception as e:
            self.logger.error(f"Error en proceso de autorización: {e}")
            return None
    
    def _load_sync_state(self) -> Dict:
        """Carga el estado de sincronización anterior"""
        if self.sync_state_file.exists():
            try:
                with open(self.sync_state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Error cargando estado de sincronización: {e}")
        
        return {"playlists": {}, "last_sync": None}
    
    def _save_sync_state(self):
        """Guarda el estado de sincronización"""
        try:
            self.sync_state["last_sync"] = datetime.now().isoformat()
            with open(self.sync_state_file, 'w', encoding='utf-8') as f:
                json.dump(self.sync_state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Error guardando estado de sincronización: {e}")
    
    def _get_m3u_hash(self, m3u_path: str) -> str:
        """Genera hash del contenido del archivo M3U para detectar cambios"""
        try:
            with open(m3u_path, 'rb') as f:
                content = f.read()
            return hashlib.md5(content).hexdigest()
        except Exception as e:
            self.logger.error(f"Error generando hash para {m3u_path}: {e}")
            return ""
    
    def parse_m3u_file(self, m3u_path: str) -> List[Dict[str, str]]:
        """Parsea un archivo M3U y extrae información de las canciones."""
        tracks = []
        
        try:
            with open(m3u_path, 'r', encoding='utf-8') as file:
                for line in file:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        track_info = self._parse_track_filename(line)
                        if track_info:
                            tracks.append(track_info)
                            
        except Exception as e:
            self.logger.error(f"Error leyendo archivo M3U {m3u_path}: {e}")
            
        return tracks
    
    def _parse_track_filename(self, filename: str) -> Optional[Dict[str, str]]:
        """Parsea el nombre de archivo para extraer información de la canción."""
        pattern = r'([^/]+)/([^-]+)\s*-\s*([^[]+)\s*\[([^-]+)\s*-\s*([^\]]+)\]\.(\w+)'
        match = re.match(pattern, filename)
        
        if match:
            genre, artist, title, year, album, extension = match.groups()
            return {
                'genre': genre.strip(),
                'artist': artist.strip(),
                'title': title.strip(),
                'year': year.strip(),
                'album': album.strip(),
                'filename': filename,
                'file_path': filename
            }
        else:
            self.logger.warning(f"No se pudo parsear: {filename}")
            return None
    
    def find_track_in_db(self, track_info: Dict[str, str]) -> Optional[Dict[str, any]]:
        """Busca una canción en la base de datos local."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = """
            SELECT s.*, a.name as artist_name, al.name as album_name
            FROM songs s
            LEFT JOIN artists a ON s.artist = a.name
            LEFT JOIN albums al ON s.album = al.name
            WHERE LOWER(s.artist) LIKE LOWER(?) 
            AND LOWER(s.title) LIKE LOWER(?)
            ORDER BY 
                CASE 
                    WHEN LOWER(s.artist) = LOWER(?) AND LOWER(s.title) = LOWER(?) THEN 1
                    ELSE 2
                END
            LIMIT 1
            """
            
            artist = track_info['artist'].strip()
            title = track_info['title'].strip()
            
            cursor.execute(query, (f"%{artist}%", f"%{title}%", artist, title))
            result = cursor.fetchone()
            
            if result:
                return dict(result)
            
            # Búsqueda FTS alternativa
            try:
                fts_query = """
                SELECT s.*, a.name as artist_name, al.name as album_name
                FROM song_fts 
                JOIN songs s ON song_fts.id = s.id
                LEFT JOIN artists a ON s.artist = a.name
                LEFT JOIN albums al ON s.album = al.name
                WHERE song_fts MATCH ?
                LIMIT 1
                """
                search_term = f'"{artist}" "{title}"'
                cursor.execute(fts_query, (search_term,))
                result = cursor.fetchone()
                
                if result:
                    return dict(result)
            except:
                pass
                    
            return None
            
        except Exception as e:
            self.logger.error(f"Error buscando en DB: {e}")
            return None
        finally:
            if conn:
                conn.close()
    
    def search_track_on_spotify(self, track_info: Dict[str, str], db_track: Optional[Dict] = None) -> Optional[str]:
        """Busca una canción en Spotify y retorna su URI."""
        try:
            if db_track:
                artist = db_track.get('artist', track_info['artist'])
                title = db_track.get('title', track_info['title'])
                album = db_track.get('album', track_info['album'])
            else:
                artist = track_info['artist']
                title = track_info['title']
                album = track_info['album']
            
            # Limpiar strings
            artist = self._clean_search_string(artist)
            title = self._clean_search_string(title)
            album = self._clean_search_string(album)
            
            # Estrategias de búsqueda
            search_queries = [
                f'track:"{title}" artist:"{artist}" album:"{album}"',
                f'track:"{title}" artist:"{artist}"',
                f'"{title}" "{artist}"',
                f'{title} {artist}'
            ]
            
            for query in search_queries:
                results = self.sp.search(q=query, type='track', limit=10)
                
                if results['tracks']['items']:
                    best_match = self._find_best_match(results['tracks']['items'], artist, title, album)
                    if best_match:
                        self.logger.debug(f"Encontrado en Spotify: {artist} - {title}")
                        return best_match['uri']
            
            self.logger.debug(f"No encontrado en Spotify: {artist} - {title}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error buscando en Spotify: {e}")
            return None
    
    def _clean_search_string(self, text: str) -> str:
        """Limpia strings para mejorar las búsquedas en Spotify."""
        text = re.sub(r'\([^)]*\)', '', text)
        text = re.sub(r'\[[^\]]*\]', '', text)
        text = re.sub(r'\s+(feat\.?|featuring|ft\.?)\s+.*$', '', text, flags=re.IGNORECASE)
        return text.strip()
    
    def _find_best_match(self, tracks: List[Dict], target_artist: str, target_title: str, target_album: str) -> Optional[Dict]:
        """Encuentra la mejor coincidencia entre los resultados de Spotify."""
        best_score = 0
        best_track = None
        
        for track in tracks:
            score = 0
            track_artists = [artist['name'].lower() for artist in track['artists']]
            track_title = track['name'].lower()
            track_album = track['album']['name'].lower()
            
            if any(target_artist.lower() in artist for artist in track_artists):
                score += 3
            
            if target_title.lower() in track_title or track_title in target_title.lower():
                score += 3
            
            if target_album.lower() in track_album or track_album in target_album.lower():
                score += 1
            
            if score > best_score:
                best_score = score
                best_track = track
        
        return best_track if best_score >= 3 else None
    
    def get_spotify_playlist_tracks(self, playlist_id: str) -> Set[str]:
        """Obtiene todas las canciones de una playlist de Spotify."""
        try:
            tracks = set()
            results = self.sp.playlist_tracks(playlist_id)
            
            while results:
                for item in results['items']:
                    if item['track'] and item['track']['uri']:
                        tracks.add(item['track']['uri'])
                
                if results['next']:
                    results = self.sp.next(results)
                else:
                    break
            
            return tracks
        except Exception as e:
            self.logger.error(f"Error obteniendo canciones de playlist {playlist_id}: {e}")
            return set()
    
    def sync_playlist_incremental(self, playlist_name: str, new_track_uris: Set[str], existing_playlist_id: Optional[str] = None) -> Optional[str]:
        """
        Sincroniza una playlist de forma incremental.
        Añade solo las canciones nuevas y elimina las que ya no existen.
        """
        try:
            # Buscar playlist existente si no se proporciona ID
            if not existing_playlist_id:
                playlists = self.sp.current_user_playlists(limit=50)
                all_playlists = playlists['items']
                
                while playlists['next']:
                    playlists = self.sp.next(playlists)
                    all_playlists.extend(playlists['items'])
                
                for playlist in all_playlists:
                    if playlist['name'] == playlist_name and playlist['owner']['id'] == self.user_id:
                        existing_playlist_id = playlist['id']
                        break
            
            # Si no existe la playlist, crearla
            if not existing_playlist_id:
                self.logger.info(f"Creando nueva playlist: {playlist_name}")
                description = f"Sincronizada automáticamente | {len(new_track_uris)} canciones"
                playlist = self.sp.user_playlist_create(
                    user=self.user_id,
                    name=playlist_name,
                    public=False,
                    description=description
                )
                existing_playlist_id = playlist['id']
                
                # Añadir todas las canciones (es nueva)
                if new_track_uris:
                    track_list = list(new_track_uris)
                    batch_size = 100
                    for i in range(0, len(track_list), batch_size):
                        batch = track_list[i:i + batch_size]
                        self.sp.playlist_add_items(existing_playlist_id, batch)
                        time.sleep(0.1)
                    
                    self.logger.info(f"Playlist creada con {len(new_track_uris)} canciones")
                
                return existing_playlist_id
            
            # Playlist existe - sincronización incremental
            self.logger.info(f"Sincronizando playlist existente: {playlist_name}")
            
            # Obtener canciones actuales en Spotify
            current_spotify_tracks = self.get_spotify_playlist_tracks(existing_playlist_id)
            
            # Calcular diferencias
            tracks_to_add = new_track_uris - current_spotify_tracks
            tracks_to_remove = current_spotify_tracks - new_track_uris
            
            changes_made = False
            
            # Eliminar canciones que ya no están en el M3U
            if tracks_to_remove:
                try:
                    # Convertir URIs a formato requerido para eliminación
                    tracks_to_remove_formatted = [{"uri": uri} for uri in tracks_to_remove]
                    
                    # Eliminar en lotes
                    batch_size = 100
                    remove_list = list(tracks_to_remove_formatted)
                    for i in range(0, len(remove_list), batch_size):
                        batch = remove_list[i:i + batch_size]
                        self.sp.playlist_remove_all_occurrences_of_items(existing_playlist_id, [item["uri"] for item in batch])
                        time.sleep(0.1)
                    
                    self.logger.info(f"Eliminadas {len(tracks_to_remove)} canciones")
                    changes_made = True
                except Exception as e:
                    self.logger.error(f"Error eliminando canciones: {e}")
            
            # Añadir canciones nuevas
            if tracks_to_add:
                try:
                    track_list = list(tracks_to_add)
                    batch_size = 100
                    for i in range(0, len(track_list), batch_size):
                        batch = track_list[i:i + batch_size]
                        self.sp.playlist_add_items(existing_playlist_id, batch)
                        time.sleep(0.1)
                    
                    self.logger.info(f"Añadidas {len(tracks_to_add)} canciones nuevas")
                    changes_made = True
                except Exception as e:
                    self.logger.error(f"Error añadiendo canciones: {e}")
            
            # Actualizar descripción
            if changes_made or not current_spotify_tracks:
                try:
                    description = f"Sincronizada automáticamente | {len(new_track_uris)} canciones | Última sync: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                    self.sp.playlist_change_details(existing_playlist_id, description=description)
                except Exception as e:
                    self.logger.warning(f"Error actualizando descripción: {e}")
            
            if not changes_made and current_spotify_tracks:
                self.logger.info("No hay cambios que sincronizar")
            else:
                self.logger.info(f"Sincronización incremental completada: +{len(tracks_to_add)} -{len(tracks_to_remove)}")
            
            return existing_playlist_id
            
        except Exception as e:
            self.logger.error(f"Error en sincronización incremental: {e}")
            return None
    
    def sync_m3u_to_spotify(self, m3u_path: str, playlist_name: Optional[str] = None, force_full_sync: bool = False) -> bool:
        """
        Sincroniza un archivo M3U con Spotify usando sincronización incremental.
        """
        if not os.path.exists(m3u_path):
            self.logger.error(f"Archivo M3U no encontrado: {m3u_path}")
            return False
        
        if not playlist_name:
            playlist_name = Path(m3u_path).stem
        
        # Verificar si el archivo ha cambiado
        current_hash = self._get_m3u_hash(m3u_path)
        playlist_state = self.sync_state["playlists"].get(playlist_name, {})
        last_hash = playlist_state.get("hash", "")
        
        if not force_full_sync and current_hash == last_hash:
            self.logger.info(f"No hay cambios en {playlist_name}, omitiendo sincronización")
            return True
        
        self.logger.info(f"Iniciando sincronización de {playlist_name}")
        
        # Parsear M3U
        tracks = self.parse_m3u_file(m3u_path)
        self.logger.info(f"Encontradas {len(tracks)} canciones en el archivo M3U")
        
        # Buscar canciones en Spotify
        spotify_uris = set()
        not_found = []
        
        for i, track_info in enumerate(tracks, 1):
            if self.interactive:
                self.logger.info(f"Procesando {i}/{len(tracks)}: {track_info['artist']} - {track_info['title']}")
            
            # Buscar en base de datos local
            db_track = self.find_track_in_db(track_info)
            
            # Buscar en Spotify
            spotify_uri = self.search_track_on_spotify(track_info, db_track)
            
            if spotify_uri:
                spotify_uris.add(spotify_uri)
            else:
                not_found.append(f"{track_info['artist']} - {track_info['title']}")
            
            time.sleep(0.1)  # Rate limiting
        
        # Sincronizar con Spotify
        if spotify_uris or force_full_sync:
            playlist_id = self.sync_playlist_incremental(
                playlist_name, 
                spotify_uris, 
                playlist_state.get("spotify_id")
            )
            
            if playlist_id:
                # Actualizar estado
                self.sync_state["playlists"][playlist_name] = {
                    "hash": current_hash,
                    "spotify_id": playlist_id,
                    "last_sync": datetime.now().isoformat(),
                    "tracks_found": len(spotify_uris),
                    "tracks_total": len(tracks)
                }
                self._save_sync_state()
                
                success_rate = len(spotify_uris) / len(tracks) * 100 if tracks else 0
                self.logger.info(f"✅ Sincronización completada: {len(spotify_uris)}/{len(tracks)} canciones ({success_rate:.1f}%)")
                
                if not_found and self.interactive:
                    self.logger.warning(f"❌ Canciones no encontradas ({len(not_found)}):")
                    for track in not_found[:5]:
                        self.logger.warning(f"  - {track}")
                    if len(not_found) > 5:
                        self.logger.warning(f"  ... y {len(not_found) - 5} más")
                
                return True
            else:
                self.logger.error("Error en la sincronización")
                return False
        else:
            self.logger.warning("No se encontraron canciones válidas para sincronizar")
            return False

def main():
    """Función principal"""
    parser = argparse.ArgumentParser(description='Sincronizador de Playlists M3U a Spotify')
    parser.add_argument('--cron', action='store_true', help='Modo no interactivo para cron')
    parser.add_argument('--force', action='store_true', help='Forzar sincronización completa')
    parser.add_argument('--playlist', type=str, help='Sincronizar solo una playlist específica')
    parser.add_argument('--db-path', type=str, help='Ruta a la base de datos SQLite')
    parser.add_argument('--m3u-folder', type=str, help='Carpeta con archivos M3U')
    
    args = parser.parse_args()
    
    # Configuración de rutas
    DB_PATH = Path(args.db_path) if args.db_path else project_root / "music.db"
    M3U_FOLDER = Path(args.m3u_folder) if args.m3u_folder else project_root
    
    if not args.cron:
        print("🎵 SINCRONIZADOR DE PLAYLISTS M3U -> SPOTIFY")
        print("=" * 50)
    
    # Verificar base de datos
    if not DB_PATH.exists():
        print(f"❌ Error: Base de datos no encontrada: {DB_PATH}")
        sys.exit(1)
    
    try:
        # Inicializar sincronizador
        syncer = PlaylistSyncer(str(DB_PATH), interactive=not args.cron)
        
        # Buscar archivos M3U
        if args.playlist:
            # Sincronizar playlist específica
            m3u_path = M3U_FOLDER / f"{args.playlist}.m3u"
            if not m3u_path.exists():
                syncer.logger.error(f"Archivo no encontrado: {m3u_path}")
                sys.exit(1)
            files_to_sync = [m3u_path]
        else:
            # Buscar todos los archivos M3U
            files_to_sync = list(M3U_FOLDER.glob("*.m3u"))
            
            if not files_to_sync:
                syncer.logger.error(f"No se encontraron archivos .m3u en {M3U_FOLDER}")
                sys.exit(1)
        
        if not args.cron:
            print(f"📁 Encontrados {len(files_to_sync)} archivos M3U:")
            for f in files_to_sync:
                print(f"  - {f.name}")
        
        # Sincronizar archivos
        successful = 0
        for m3u_file in files_to_sync:
            if not args.cron:
                print(f"\n🎵 Sincronizando {m3u_file.name}...")
            
            if syncer.sync_m3u_to_spotify(str(m3u_file), force_full_sync=args.force):
                successful += 1
        
        syncer.logger.info(f"Sincronización completada: {successful}/{len(files_to_sync)} playlists")
        
        if not args.cron:
            print(f"\n✅ Sincronización completada: {successful}/{len(files_to_sync)} playlists")
        
    except KeyboardInterrupt:
        if not args.cron:
            print("\n\nProceso interrumpido por el usuario")
        sys.exit(0)
    except Exception as e:
        logging.error(f"Error general: {e}")
        if not args.cron:
            print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()