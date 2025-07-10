#!/usr/bin/env python3
"""
Script para sincronizar scrobbles de Last.fm con Airsonic-Advanced
Requiere: requests, python-dotenv
Instalar con: pip install requests python-dotenv
"""

import requests
import json
import time
import hashlib
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

class LastFmClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "http://ws.audioscrobbler.com/2.0/"
    
    def get_user_scrobbles(self, username: str, limit: int = 200, page: int = 1, from_timestamp: Optional[int] = None) -> Dict:
        """Obtiene scrobbles del usuario desde Last.fm"""
        params = {
            'method': 'user.getRecentTracks',
            'user': username,
            'api_key': self.api_key,
            'format': 'json',
            'limit': limit,
            'page': page,
            'extended': 1  # Para obtener más metadatos incluyendo MBID
        }
        
        if from_timestamp:
            params['from'] = from_timestamp
            
        try:
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error obteniendo datos de Last.fm: {e}")
            return {}

class AirsonicClient:
    def __init__(self, server_url: str, username: str, password: str):
        self.server_url = server_url.rstrip('/')
        self.username = username
        self.password = password
        self.salt = self._generate_salt()
        self.token = self._generate_token()
    
    def _generate_salt(self) -> str:
        """Genera salt para autenticación"""
        return hashlib.md5(str(time.time()).encode()).hexdigest()[:6]
    
    def _generate_token(self) -> str:
        """Genera token MD5 para autenticación"""
        return hashlib.md5((self.password + self.salt).encode()).hexdigest()
    
    def _make_request(self, endpoint: str, params: Dict) -> Optional[Dict]:
        """Hace petición a la API de Airsonic"""
        base_params = {
            'u': self.username,
            't': self.token,
            's': self.salt,
            'v': '1.16.1',
            'c': 'lastfm-sync',
            'f': 'json'
        }
        base_params.update(params)
        
        url = f"{self.server_url}/rest/{endpoint}"
        
        try:
            response = requests.get(url, params=base_params)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error en petición a Airsonic ({endpoint}): {e}")
            return None
    
    def search_song(self, artist: str, title: str, album: str = None, debug: bool = False) -> Optional[str]:
        """Busca una canción en Airsonic y devuelve su ID"""
        # Limpiar y normalizar strings
        artist_clean = self._clean_string(artist)
        title_clean = self._clean_string(title)
        
        # Múltiples estrategias de búsqueda
        search_queries = [
            f"{artist_clean} {title_clean}",  # Completo
            f"{artist_clean}",  # Solo artista
            f"{title_clean}",   # Solo título
            f'"{artist_clean}" "{title_clean}"',  # Con comillas
        ]
        
        for query in search_queries:
            if debug:
                print(f"   🔍 Buscando: '{query}'")
                
            result = self._search_with_query(query, debug)
            if result:
                song_id = self._find_best_match(result, artist_clean, title_clean, debug)
                if song_id:
                    return song_id
        
        return None
    
    def _clean_string(self, text: str) -> str:
        """Limpia y normaliza strings para búsqueda"""
        if not text:
            return ""
        # Remover caracteres problemáticos
        import re
        text = re.sub(r'[^\w\s\-\']', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _search_with_query(self, query: str, debug: bool = False) -> Optional[List]:
        """Ejecuta búsqueda con una query específica"""
        params = {
            'query': query,
            'songCount': 20,
            'artistCount': 5,
            'albumCount': 5
        }
        
        result = self._make_request('search3', params)
        if not result or 'subsonic-response' not in result:
            return None
            
        response = result['subsonic-response']
        if response.get('status') != 'ok':
            if debug:
                print(f"   ❌ Error en búsqueda: {response.get('error', {})}")
            return None
            
        if 'searchResult3' not in response:
            return None
            
        songs = response['searchResult3'].get('song', [])
        if not isinstance(songs, list):
            songs = [songs] if songs else []
            
        if debug:
            print(f"   📊 Encontrados {len(songs)} resultados")
            
        return songs
    
    def _find_best_match(self, songs: List, artist: str, title: str, debug: bool = False) -> Optional[str]:
        """Encuentra la mejor coincidencia entre los resultados"""
        if not songs:
            return None
            
        best_match = None
        best_score = 0
        
        for song in songs:
            song_artist = self._clean_string(song.get('artist', ''))
            song_title = self._clean_string(song.get('title', ''))
            
            if debug:
                print(f"   🎵 Comparando: '{song_artist}' - '{song_title}'")
            
            # Calcular score de similaridad
            score = self._calculate_similarity(artist, title, song_artist, song_title)
            
            if debug:
                print(f"   📊 Score: {score}")
                
            if score > best_score and score > 0.6:  # Umbral mínimo
                best_score = score
                best_match = song.get('id')
                
        if debug and best_match:
            print(f"   ✅ Mejor match con score: {best_score}")
            
        return best_match
    
    def _calculate_similarity(self, artist1: str, title1: str, artist2: str, title2: str) -> float:
        """Calcula similaridad entre dos canciones"""
        def similarity(s1: str, s2: str) -> float:
            if not s1 or not s2:
                return 0
            s1, s2 = s1.lower(), s2.lower()
            if s1 == s2:
                return 1.0
            if s1 in s2 or s2 in s1:
                return 0.8
            # Similaridad básica por palabras comunes
            words1 = set(s1.split())
            words2 = set(s2.split())
            if not words1 or not words2:
                return 0
            intersection = len(words1 & words2)
            union = len(words1 | words2)
            return intersection / union if union > 0 else 0
        
        artist_sim = similarity(artist1, artist2)
        title_sim = similarity(title1, title2)
        
        # Peso: título más importante que artista
        return (artist_sim * 0.4) + (title_sim * 0.6)
    
    def scrobble(self, song_id: str, timestamp: int) -> bool:
        """Añade un scrobble a Airsonic"""
        params = {
            'id': song_id,
            'time': timestamp * 1000,  # Airsonic espera milisegundos
            'submission': 'true'
        }
        
        result = self._make_request('scrobble', params)
        if result and result.get('subsonic-response', {}).get('status') == 'ok':
            return True
        return False

class ScrobbleDB:
    def __init__(self, db_path: str = 'scrobbles.db'):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Inicializa la base de datos local para tracking"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS synced_scrobbles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lastfm_timestamp INTEGER UNIQUE,
                artist TEXT,
                title TEXT,
                album TEXT,
                airsonic_song_id TEXT,
                sync_timestamp INTEGER,
                UNIQUE(lastfm_timestamp, artist, title)
            )
        ''')
        conn.commit()
        conn.close()
    
    def is_scrobble_synced(self, timestamp: int, artist: str, title: str) -> bool:
        """Verifica si un scrobble ya fue sincronizado"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT 1 FROM synced_scrobbles WHERE lastfm_timestamp = ? AND artist = ? AND title = ?',
            (timestamp, artist, title)
        )
        result = cursor.fetchone()
        conn.close()
        return result is not None
    
    def add_synced_scrobble(self, timestamp: int, artist: str, title: str, album: str, song_id: str):
        """Marca un scrobble como sincronizado"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO synced_scrobbles 
                (lastfm_timestamp, artist, title, album, airsonic_song_id, sync_timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (timestamp, artist, title, album, song_id, int(time.time())))
            conn.commit()
        except sqlite3.Error as e:
            print(f"Error guardando en DB: {e}")
        finally:
            conn.close()
    
    def get_last_sync_timestamp(self) -> int:
        """Obtiene el timestamp del último scrobble sincronizado"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT MAX(lastfm_timestamp) FROM synced_scrobbles')
        result = cursor.fetchone()
        conn.close()
        return result[0] if result[0] else 0

class LastFmAirsonicSync:
    def __init__(self):
        # Configuración desde variables de entorno
        self.lastfm_api_key = os.getenv('LASTFM_API_KEY')
        self.lastfm_username = os.getenv('LASTFM_USERNAME')
        self.airsonic_url = os.getenv('AIRSONIC_URL')
        self.airsonic_username = os.getenv('AIRSONIC_USERNAME')
        self.airsonic_password = os.getenv('AIRSONIC_PASSWORD')
        
        if not all([self.lastfm_api_key, self.lastfm_username, self.airsonic_url, 
                   self.airsonic_username, self.airsonic_password]):
            raise ValueError("Faltan variables de entorno requeridas")
        
        self.lastfm = LastFmClient(self.lastfm_api_key)
        self.airsonic = AirsonicClient(self.airsonic_url, self.airsonic_username, self.airsonic_password)
        self.db = ScrobbleDB()
    
    def sync_scrobbles(self, incremental: bool = True, limit_pages: int = 10, debug: bool = False):
        """Sincroniza scrobbles de Last.fm a Airsonic"""
        print("🎵 Iniciando sincronización Last.fm → Airsonic-Advanced")
        
        # Obtener timestamp del último sync si es incremental
        from_timestamp = self.db.get_last_sync_timestamp() if incremental else None
        if from_timestamp:
            print(f"📅 Sincronización incremental desde: {datetime.fromtimestamp(from_timestamp)}")
        
        total_processed = 0
        total_synced = 0
        total_not_found = 0
        total_errors = 0
        page = 1
        
        while page <= limit_pages:
            print(f"📄 Procesando página {page}...")
            
            # Obtener scrobbles de Last.fm
            data = self.lastfm.get_user_scrobbles(
                self.lastfm_username, 
                limit=200, 
                page=page,
                from_timestamp=from_timestamp
            )
            
            if not data or 'recenttracks' not in data:
                print("❌ No se pudieron obtener datos de Last.fm")
                break
                
            tracks = data['recenttracks'].get('track', [])
            if not tracks:
                print("✅ No hay más tracks para procesar")
                break
                
            # Procesar cada track
            for track in tracks:
                # Saltar tracks que se están reproduciendo ahora
                if track.get('@attr', {}).get('nowplaying'):
                    continue
                    
                total_processed += 1
                
                # Extraer metadatos
                artist = track.get('artist', {}).get('#text', '') if isinstance(track.get('artist'), dict) else str(track.get('artist', ''))
                title = track.get('name', '')
                album = track.get('album', {}).get('#text', '') if isinstance(track.get('album'), dict) else str(track.get('album', ''))
                timestamp = int(track.get('date', {}).get('uts', 0))
                mbid = track.get('mbid', '')
                
                if not artist or not title or not timestamp:
                    continue
                
                # Verificar si ya está sincronizado
                if self.db.is_scrobble_synced(timestamp, artist, title):
                    if debug:
                        print(f"⏭️  Ya sincronizado: {artist} - {title}")
                    continue
                
                if debug:
                    print(f"\n🔍 Procesando: {artist} - {title}")
                    if mbid:
                        print(f"   🎯 MBID: {mbid}")
                
                # Buscar canción en Airsonic
                song_id = self.airsonic.search_song(artist, title, album, debug=debug)
                if not song_id:
                    total_not_found += 1
                    print(f"❓ No encontrado en Airsonic: {artist} - {title}")
                    # Guardar como no encontrado para no buscar de nuevo
                    self.db.add_synced_scrobble(timestamp, artist, title, album, "NOT_FOUND")
                    continue
                
                # Scrobble en Airsonic
                if self.airsonic.scrobble(song_id, timestamp):
                    self.db.add_synced_scrobble(timestamp, artist, title, album, song_id)
                    total_synced += 1
                    print(f"✅ Sincronizado: {artist} - {title}")
                else:
                    total_errors += 1
                    print(f"❌ Error al scrobble: {artist} - {title}")
                
                # Pausa para evitar rate limiting
                time.sleep(0.1)
                
                # Mostrar progreso cada 50 tracks
                if total_processed % 50 == 0:
                    print(f"📊 Progreso: {total_processed} procesados, {total_synced} sincronizados")
            
            # Verificar si hay más páginas
            total_pages = int(data['recenttracks']['@attr'].get('totalPages', 1))
            if page >= total_pages:
                break
                
            page += 1
            time.sleep(0.5)  # Pausa entre páginas
        
        print(f"\n🎉 Sincronización completada:")
        print(f"   📊 Tracks procesados: {total_processed}")
        print(f"   ✅ Scrobbles sincronizados: {total_synced}")
        print(f"   ❓ No encontrados: {total_not_found}")
        print(f"   ❌ Errores: {total_errors}")
        
        if total_not_found > 0:
            print(f"\n💡 Sugerencias para mejorar coincidencias:")
            print(f"   - Verifica que la música esté en tu servidor Airsonic")
            print(f"   - Revisa los metadatos (artista/título) en tu biblioteca")
            print(f"   - Prueba ejecutar con debug=True para más detalles")

def main():
    """Función principal"""
    print("🎵 Sincronizador Last.fm → Airsonic-Advanced")
    print("=" * 50)
    
    # Verificar archivo .env
    if not os.path.exists('.env'):
        print("❌ No se encontró archivo .env")
        print("\nCrea un archivo .env con:")
        print("LASTFM_API_KEY=tu_api_key")
        print("LASTFM_USERNAME=tu_username")
        print("AIRSONIC_URL=http://tu-servidor:puerto")
        print("AIRSONIC_USERNAME=tu_usuario")
        print("AIRSONIC_PASSWORD=tu_password")
        return
    
    try:
        sync = LastFmAirsonicSync()
        
        # Menú de opciones
        print("\nOpciones disponibles:")
        print("1. Sincronización incremental (recomendado)")
        print("2. Sincronización completa")
        print("3. Modo debug (muestra detalles de búsqueda)")
        print("4. Test de conexión")
        
        choice = input("\nSelecciona opción (1-4): ").strip()
        
        if choice == "4":
            # Test de conexión
            print("\n🔧 Probando conexiones...")
            
            # Test Last.fm
            data = sync.lastfm.get_user_scrobbles(sync.lastfm_username, limit=1)
            if data and 'recenttracks' in data:
                print("✅ Conexión a Last.fm: OK")
                tracks = data['recenttracks'].get('track', [])
                if tracks:
                    track = tracks[0] if isinstance(tracks, list) else tracks
                    artist = track.get('artist', {}).get('#text', '') if isinstance(track.get('artist'), dict) else str(track.get('artist', ''))
                    title = track.get('name', '')
                    print(f"   📀 Último track: {artist} - {title}")
            else:
                print("❌ Conexión a Last.fm: FALLO")
                return
                
            # Test Airsonic
            test_result = sync.airsonic._make_request('ping', {})
            if test_result and test_result.get('subsonic-response', {}).get('status') == 'ok':
                print("✅ Conexión a Airsonic: OK")
                version = test_result['subsonic-response'].get('version', 'desconocida')
                print(f"   🏠 Versión servidor: {version}")
            else:
                print("❌ Conexión a Airsonic: FALLO")
                return
                
            # Test búsqueda
            if tracks:
                print(f"\n🔍 Probando búsqueda para: {artist} - {title}")
                song_id = sync.airsonic.search_song(artist, title, debug=True)
                if song_id:
                    print(f"✅ Canción encontrada con ID: {song_id}")
                else:
                    print("❌ Canción no encontrada")
                    
            return
        
        # Configurar parámetros
        incremental = choice != "2"
        debug = choice == "3"
        
        # Permitir configurar límite de páginas
        if debug:
            pages_input = input("Número máximo de páginas a procesar (1 para debug): ").strip()
            max_pages = int(pages_input) if pages_input.isdigit() else 1
        else:
            pages_input = input("Número máximo de páginas a procesar (10): ").strip()
            max_pages = int(pages_input) if pages_input.isdigit() else 10
        
        sync.sync_scrobbles(incremental=incremental, limit_pages=max_pages, debug=debug)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()