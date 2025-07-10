import json
import os
import subprocess
import shutil
import argparse
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth
import re
from tabulate import tabulate
import sys
import time
import re






def authenticate_spotify_simple(spotify_client_id, spotify_client_secret):
    """
    Autentica con Spotify usando el método manual, comprobando primero si existe un token válido
    """
    try:
        # Configurar autenticación de Spotify
        scope = "user-library-read playlist-read-private playlist-read-collaborative"
        redirect_uri = "http://127.0.0.1:8888"
        
        # Inicializar el objeto SpotifyOAuth
        auth_manager = SpotifyOAuth(
            client_id=spotify_client_id,
            client_secret=spotify_client_secret,
            redirect_uri=redirect_uri,
            scope=scope,
            open_browser=False
        )
        
        # Comprobar si ya existe un token en caché
        token_info = auth_manager.get_cached_token()
        
        # Verificar si el token es válido y no está caducado
        if token_info:
            # Si el token existe, comprobar si está caducado
            if not auth_manager.is_token_expired(token_info):
                print("Token existente válido encontrado. No es necesario autenticar de nuevo.")
                if isinstance(token_info, dict):
                    access_token = token_info['access_token']
                else:
                    access_token = token_info
                    
                return spotipy.Spotify(auth=access_token)
            else:
                print("Token existente caducado. Se requiere renovación.")
                if 'refresh_token' in token_info:
                    print("Renovando token automáticamente...")
                    try:
                        token_info = auth_manager.refresh_access_token(token_info['refresh_token'])
                        if isinstance(token_info, dict):
                            access_token = token_info['access_token']
                        else:
                            access_token = token_info
                            
                        return spotipy.Spotify(auth=access_token)
                    except Exception as e:
                        print(f"Error al renovar el token: {e}")
                        print("Se procederá con la autenticación manual.")
        else:
            print("No se encontró token en caché. Se requiere autenticación.")
        
        # Si llegamos aquí, necesitamos autenticación manual
        # Obtener URL de autorización
        auth_url = auth_manager.get_authorize_url()
        print("\n==== AUTENTICACIÓN DE SPOTIFY ====")
        print("\nSigue estos pasos para autenticar con Spotify:")
        print(f"1. Abre este enlace en tu navegador: {auth_url}")
        print("2. Autoriza la aplicación.")
        print("3. Serás redirigido a una URL. Copia toda la URL y pégala aquí.")
        print("   (Debe comenzar con 'http://127.0.0.1:8888?code=...')")
        
        # Preguntar si queremos abrir el navegador automáticamente
        open_browser_response = input("\n¿Quieres abrir automáticamente el navegador? (s/n): ").lower()
        if open_browser_response in ['s', 'si', 'sí', 'y', 'yes']:
            import webbrowser
            webbrowser.open(auth_url)
        
        # Solicitar la URL de redirección al usuario
        while True:
            redirect_url = input("\nPega la URL completa de redirección aquí: ")
            try:
                # Manejar casos donde la URL puede venir con ? o con &
                if "?code=" in redirect_url:
                    code = redirect_url.split("?code=")[1].split("&")[0]
                elif "&code=" in redirect_url:
                    code = redirect_url.split("&code=")[1].split("&")[0]
                else:
                    print("La URL proporcionada no contiene el código de autorización.")
                    continue
                
                if code:
                    # Procesar el código de autorización y guardar el token
                    token_info = auth_manager.get_access_token(code, as_dict=True)
                    
                    if token_info:
                        if isinstance(token_info, dict):
                            access_token = token_info['access_token']
                        else:
                            access_token = token_info
                            
                        sp = spotipy.Spotify(auth=access_token)
                        print("Autenticación completada correctamente.")
                        return sp
                    else:
                        print("No se pudo obtener el token de acceso.")
                else:
                    print("No se pudo extraer el código de autorización.")
            except Exception as e:
                print(f"Error al procesar la URL: {e}")
                print("Asegúrate de que la URL comienza con 'http://127.0.0.1:8888?code='")
                retry = input("¿Quieres intentarlo de nuevo? (s/n): ").lower()
                if retry not in ['s', 'si', 'sí', 'y', 'yes']:
                    print("Autenticación cancelada.")
                    sys.exit(1)
    
    except Exception as e:
        print(f"Error durante la autenticación: {e}")
        sys.exit(1)

def load_config_from_json(json_file):
    """
    Carga la configuración desde un archivo JSON
    """
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config
    except Exception as e:
        print(f"Error al cargar el archivo de configuración {json_file}: {e}")
        return None

def extract_playlist_id_from_url(url):
    """
    Extrae el ID de playlist de una URL de Spotify
    Formatos soportados:
    - https://open.spotify.com/playlist/37i9dQZF1DX4sWSpwq3LiO
    - https://open.spotify.com/playlist/37i9dQZF1DX4sWSpwq3LiO?si=abcdef
    """
    pattern = r'spotify\.com/playlist/([a-zA-Z0-9]+)'
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    return None

def get_user_playlists(username, sp):
    """
    Obtiene todas las playlists de un usuario de Spotify usando una instancia autenticada
    """
    try:
        playlists = []
        
        # Si el username coincide con el usuario autenticado, obtener sus playlists
        current_user = sp.current_user()
        if current_user['id'].lower() == username.lower():
            print(f"Obteniendo playlists del usuario autenticado: {username}")
            results = sp.current_user_playlists(limit=50)
            playlists.extend(results['items'])
            
            while results['next']:
                results = sp.next(results)
                playlists.extend(results['items'])
        
        # Si no se obtuvieron playlists o se busca otro usuario, intentar con usuario público
        if not playlists:
            print(f"Obteniendo playlists públicas del usuario: {username}")
            results = sp.user_playlists(username, limit=50)
            playlists = results['items']
            
            while results['next']:
                results = sp.next(results)
                playlists.extend(results['items'])
        
        if not playlists:
            print(f"No se encontraron playlists para el usuario {username}")
    
        return playlists
    except Exception as e:
        print(f"Error al obtener playlists del usuario {username}: {e}")
        return []

def display_playlists_table(playlists):
    """
    Muestra una tabla con todas las playlists del usuario
    """
    table_data = []
    for i, playlist in enumerate(playlists, 1):
        table_data.append([
            i, 
            playlist['name'], 
            playlist['id'],
            playlist['tracks']['total']
        ])
    
    headers = ["Núm.", "Nombre de la Playlist", "ID de Playlist", "Canciones"]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))
    
    return table_data

def get_spotify_playlist_tracks(playlist_id, sp):
    """
    Obtiene todas las canciones de una playlist de Spotify
    """
    try:
        results = sp.playlist_tracks(playlist_id)
        tracks = results['items']
        
        # Obtener todas las pistas en caso de playlists grandes
        while results['next']:
            results = sp.next(results)
            tracks.extend(results['items'])
        
        tracks_info = []
        for track in tracks:
            # Verificar si la pista existe (puede ser None en algunos casos)
            if not track['track']:
                continue
                
            track_info = track['track']
            tracks_info.append({
                'cancion': track_info['name'],
                'album': track_info['album']['name'],
                'artista': track_info['artists'][0]['name']
            })
        
        return tracks_info
    except Exception as e:
        print(f"Error al obtener canciones de la playlist {playlist_id}: {e}")
        return []



def organize_tracks_by_album_artist(tracks):
    """
    Organiza las canciones agrupándolas por artista y álbum
    """
    # Crear diccionario para agrupar
    grouped = {}
    
    for track in tracks:
        artista = track['artista']
        album = track['album']
        key = f"{artista}|{album}"
        
        if key not in grouped:
            grouped[key] = {
                'artista': artista,
                'album': album,
                'canciones': []
            }
        
        grouped[key]['canciones'].append(track['cancion'])
    
    # Convertir a lista
    result = []
    for group in grouped.values():
        result.append(group)
    
    return result

def get_file_path(artista, album, cancion, db_path):
    """
    Obtiene la ruta del archivo directamente de la base de datos
    con soporte para coincidencias parciales en los nombres de álbumes
    """
    import sqlite3
    import re
    
    print(f"Consultando directamente en la base de datos: {db_path}")
    print(f"Buscando: Artista='{artista}', Album='{album}', Canción='{cancion}'")
    
    try:
        # Conectar a la base de datos
        conn = sqlite3.connect(db_path)
        conn.create_function("REGEXP", 2, lambda x, y: 1 if re.search(x, y, re.IGNORECASE) else 0)
        cursor = conn.cursor()
        
        # 1. Primero, veamos qué álbumes tenemos de este artista
        cursor.execute("""
            SELECT DISTINCT album FROM songs 
            WHERE LOWER(artist) = LOWER(?)
        """, (artista,))
        
        albums_in_db = cursor.fetchall()
        print(f"Álbumes encontrados para {artista}: {[a[0] for a in albums_in_db]}")
        
        # 2. Normalizar el nombre del álbum de Spotify (quitar paréntesis con ediciones)
        album_normalizado = re.sub(r'\s*\([^)]*(?:Edition|Deluxe|Remaster|Anniversary|Special|Bonus|Version|Expanded)[^)]*\)', '', album, flags=re.IGNORECASE)
        album_normalizado = album_normalizado.strip()
        print(f"Álbum normalizado: '{album_normalizado}'")
        
        # 3. Encontrar el mejor álbum coincidente
        best_album_match = None
        highest_similarity = 0
        
        for db_album in albums_in_db:
            db_album_name = db_album[0]
            # Normalizar también el álbum de la BD
            db_album_norm = re.sub(r'\s*\([^)]*(?:Edition|Deluxe|Remaster|Anniversary|Special|Bonus|Version|Expanded)[^)]*\)', '', db_album_name, flags=re.IGNORECASE)
            db_album_norm = db_album_norm.strip()
            
            # Calcular una similitud simple (considera coincidencia de substrings)
            if db_album_norm.lower() == album_normalizado.lower():
                similarity = 1.0  # Coincidencia exacta
            elif db_album_norm.lower() in album_normalizado.lower() or album_normalizado.lower() in db_album_norm.lower():
                # Calcular longitud relativa del substring coincidente
                similarity = len(min(db_album_norm, album_normalizado, key=len)) / len(max(db_album_norm, album_normalizado, key=len))
            else:
                # Contar cuántas palabras coinciden
                db_words = set(db_album_norm.lower().split())
                search_words = set(album_normalizado.lower().split())
                common_words = db_words.intersection(search_words)
                if common_words:
                    similarity = len(common_words) / max(len(db_words), len(search_words))
                else:
                    similarity = 0
            
            print(f"Álbum en BD: '{db_album_name}' (norm: '{db_album_norm}') - Similitud: {similarity:.2f}")
            
            if similarity > highest_similarity:
                highest_similarity = similarity
                best_album_match = db_album_name
        
        if not best_album_match or highest_similarity < 0.3:  # Umbral mínimo de similitud
            print(f"No se encontró ningún álbum similar a '{album}' para el artista '{artista}'")
            return None
        
        print(f"Mejor coincidencia de álbum: '{best_album_match}' (similitud: {highest_similarity:.2f})")
        
        # 4. Buscar la canción en el álbum seleccionado
        # Primero intentamos una coincidencia directa
        cursor.execute("""
            SELECT file_path FROM songs 
            WHERE LOWER(artist) = LOWER(?) 
            AND LOWER(album) = LOWER(?) 
            AND LOWER(title) = LOWER(?)
        """, (artista, best_album_match, cancion))
        
        result = cursor.fetchone()
        
        # Si no hay resultado, intentamos coincidencia parcial de título
        if not result:
            print(f"No se encontró coincidencia exacta para '{cancion}'. Intentando coincidencia parcial...")
            
            # Obtener todas las canciones del álbum
            cursor.execute("""
                SELECT title, file_path FROM songs 
                WHERE LOWER(artist) = LOWER(?) 
                AND LOWER(album) = LOWER(?)
            """, (artista, best_album_match))
            
            songs_in_album = cursor.fetchall()
            
            # Normalizar el nombre de la canción (quitar paréntesis, etc.)
            cancion_norm = re.sub(r'\s*\([^)]*\)', '', cancion, flags=re.IGNORECASE).strip()
            
            best_song_match = None
            best_path = None
            highest_song_similarity = 0
            
            for db_song, path in songs_in_album:
                # Normalizar el título de la canción en la BD
                db_song_norm = re.sub(r'\s*\([^)]*\)', '', db_song, flags=re.IGNORECASE).strip()
                
                # Calcular similitud
                if db_song_norm.lower() == cancion_norm.lower():
                    similarity = 1.0  # Coincidencia exacta
                elif db_song_norm.lower() in cancion_norm.lower() or cancion_norm.lower() in db_song_norm.lower():
                    # Substring
                    similarity = len(min(db_song_norm, cancion_norm, key=len)) / len(max(db_song_norm, cancion_norm, key=len))
                else:
                    # Palabras comunes
                    db_words = set(db_song_norm.lower().split())
                    search_words = set(cancion_norm.lower().split())
                    common_words = db_words.intersection(search_words)
                    if common_words:
                        similarity = len(common_words) / max(len(db_words), len(search_words))
                    else:
                        similarity = 0
                
                print(f"Canción en BD: '{db_song}' (norm: '{db_song_norm}') - Similitud: {similarity:.2f}")
                
                if similarity > highest_song_similarity:
                    highest_song_similarity = similarity
                    best_song_match = db_song
                    best_path = path
            
            if highest_song_similarity >= 0.5:  # Umbral para coincidencia de canción
                print(f"Mejor coincidencia de canción: '{best_song_match}' (similitud: {highest_song_similarity:.2f})")
                return best_path
            else:
                print(f"No se encontró una canción suficientemente similar a '{cancion}' en el álbum '{best_album_match}'")
                return None
        
        # Si llegamos aquí, es porque encontramos una coincidencia exacta de canción
        path = result[0]
        print(f"Ruta encontrada: {path}")

        # Ajustar la ruta encontrada
        adjusted_path = adjust_path(path)
        print(f"Ruta ajustada: {adjusted_path}")
        return adjusted_path
            
    except Exception as e:
        print(f"Error consultando la BD para {cancion} de {artista}: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        if 'conn' in locals():
            conn.close()

def adjust_path(original_path):
    """
    Reemplaza '/mnt/NFS/moode' por '/storage/popollo' en la ruta
    """
    print(f"original path: {original_path}")
    if original_path:
        print(f"original path corregido: {original_path}")
        return original_path.replace("/mnt/NFS/moode", "/storage/popollo")
    return None

def file_exists(path):
    """
    Verifica si un archivo existe utilizando una expresión más robusta
    """
    try:
        # Escapar comillas simples en la ruta para el comando shell
        escaped_path = path.replace("'", "'\\''")
        cmd = f"find '{escaped_path}' -type f -print -quit"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return bool(result.stdout.strip())
    except Exception as e:
        print(f"Error al verificar si existe el archivo: {e}")
        return False

def copy_file(source_path, destination_folder):
    """
    Copia el archivo a la carpeta de destino usando una expresión shell más segura
    """
    if not source_path:
        print("Ruta de origen vacía")
        return False
        
    if not file_exists(source_path):
        print(f"El archivo no existe en la ruta: {source_path}")
        return False
    
    # Crear directorio de destino si no existe
    if not os.path.exists(destination_folder):
        os.makedirs(destination_folder)
    
    # Obtener solo el nombre del archivo sin la ruta
    filename = os.path.basename(source_path)
    destination_path = os.path.join(destination_folder, filename)
    
    try:
        # Escapar comillas simples en las rutas
        escaped_source = source_path.replace("'", "'\\''")
        escaped_dest = destination_path.replace("'", "'\\''")
        cmd = f"cp '{escaped_source}' '{escaped_dest}'"
        
        print(f"Ejecutando comando: {cmd}")
        subprocess.run(cmd, shell=True, check=True)
        
        print(f"Copiado: {filename} a {destination_folder}")
        return True
    except Exception as e:
        print(f"Error al copiar {source_path}: {e}")
        return False


def launch_torrent_script(config_data):
    """
    Lanza el script de descarga de torrents como un módulo importado
    """
    cmd = [
        "python3",
        "2_get_torrents.py", 
        "--modo", config_data['modo'],
        "--carpeta-torrents-temporales", config_data['carpeta_torrents_temporales'],
        "--carpeta-watchfolder", config_data['carpeta_watchfolder'],
        "--carpeta-descargas-qbitorrent", config_data['carpeta_descargas_qbitorrent'],
        "--flac",  # This flag doesn't need a value
        "--json-file", config_data['json_file'],
        "--output-path", config_data['path_destino_flac'],
        "--lidarr-url", config_data['lidarr_url'],
        "--lidarr-api-key", config_data['lidarr_api_key'],
        "--jackett-url", config_data['jackett_url'],
        "--jackett-api-key", config_data['jackett_api_key']
    ]
    
    print("\nLanzando script de descarga de torrents:")
    print(" ".join(cmd))

    try:
        # Use subprocess.run with check=True to see output in real-time
        result = subprocess.run(cmd, check=True)
        
        if result.returncode != 0:
            print(f"El script de torrents terminó con código de error: {result.returncode}")
            return False
        
        print("Script de torrents completado exitosamente")
        return True
    except Exception as e:
        print(f"Error al ejecutar el script de torrents: {e}")
        return False


def main():
    # Configurar argumentos de línea de comandos
    parser = argparse.ArgumentParser(description='Copiar canciones de una playlist de Spotify')
    parser.add_argument('--config-file', help='Archivo JSON con la configuración')
    parser.add_argument('--db-path', help='Ruta al archivo de la base de datos SQLite')
    parser.add_argument('--playlist-id', help='ID de la playlist de Spotify')
    parser.add_argument('--playlist-url', help='URL de la playlist de Spotify')
    parser.add_argument('--spotify-user', help='Usuario de Spotify para listar sus playlists')
    parser.add_argument('--spotify-client-id', help='Client ID de Spotify API')
    parser.add_argument('--spotify-client-secret', help='Client Secret de Spotify API')
    parser.add_argument('--path-destino', default='./canciones', help='Carpeta donde copiar las canciones. Por defecto: ./canciones')
    parser.add_argument('--json-file', default='.content/playlist_songs.json', help='Archivo JSON para guardar la información')
    parser.add_argument('--debug', action='store_true', help='Activar modo debug para más información')
    # Argumentos segundo script
    parser.add_argument('--modo', choices=['interactivo', 'automatico'], default='interactivo', 
                        help='Modo de selección de torrents (por defecto: interactivo)')
    parser.add_argument('--carpeta-torrents-temporales', help='Carpeta donde se guardarán los torrents descargados (por defecto: ./torrents)')
    parser.add_argument('--carpeta-descargas-qbitorrent', help='Carpeta descargas de qbitorrent, donde descarga tus cositas')

    parser.add_argument('--carpeta-final', help='Carpeta final donde se copiarán todos los torrents (por defecto: ./torrents_final)')
    parser.add_argument('--flac', action='store_true', 
                        help='Filtrar resultados para mostrar solo archivos en formato FLAC')
    parser.add_argument('--lidarr-url', default='http://100.90.91.96:8686', 
                        help='URL de tu instancia de Lidarr (por defecto: http://100.90.91.96:8686)')
    parser.add_argument('--lidarr-api-key', default=None, 
                        help='API key de tu instancia de Lidarr (por defecto: None)')
    parser.add_argument('--jackett-url', default='http://100.90.91.96:9117', 
                        help='URL de tu instancia de Jackett (por defecto: http://100.90.91.96:9117)')
    parser.add_argument('--jackett-api-key', default=None, 
                        help='API key de tu instancia de Jackett (por defecto: None)')

    # Argumentos tercer script
    parser.add_argument('--output-path', 
                        help='Carpeta final donde se copiarán todos los torrents (alias para path-destino)')
    parser.add_argument('--skip-torrents', action='store_true',
                        help='Omitir la ejecución del script de torrents')
    parser.add_argument('--temp_server_port', type=int, default=8584, 
                        help='Puerto del servidor (por defecto: 8584)')
    # Parsear argumentos
    args = parser.parse_args()
    
    # Inicializar configuración
    config = {}
    
    # Si se proporciona un archivo de configuración, cargarlo
    if args.config_file:
        loaded_config = load_config_from_json(args.config_file)
        if loaded_config:
            config.update(loaded_config)
    
    # Actualizar la configuración con los argumentos de línea de comandos (si se proporcionan)
    # Esto permite que los argumentos de línea de comandos tengan prioridad sobre los del archivo JSON
    for arg_name, arg_value in vars(args).items():
        if arg_value is not None and arg_name != 'config_file':
            config[arg_name] = arg_value
    
    # Verificar parámetros requeridos
    required_params = ['db_path', 'spotify_client_id', 'spotify_client_secret', 'path_destino_flac', 'lidarr_url', 'lidarr_api_key', 'jackett_url', 'jackett_api_key']
    missing_params = [param for param in required_params if param not in config or not config[param]]
    
    if missing_params:
        print(f"Error: Faltan parámetros requeridos: {', '.join(missing_params)}")
        print("Por favor, proporciona estos parámetros en la línea de comandos o en el archivo de configuración.")
        sys.exit(1)
    
    # Asignar variables de configuración
    db_path = config['db_path']
    print(f"db path: {db_path}")
    debug = config.get('debug', False)
    json_file = config.get('json_file', 'playlist_songs.json')
    path_destino_flac_base = config.get('path_destino_flac', './canciones')
    modo = config.get('modo', 'interactivo')
    carpeta_torrents_temporales = config.get('carpeta_torrents_temporales', './torrents')
    carpeta_watchfolder = config.get('carpeta_watchfolder', './torrents_final')
    carpeta_descargas_qbitorrent = config.get('carpeta_descargas_qbitorrent')
    output_path = config.get('output_path', path_destino_flac_base)
    skip_torrents = config.get('skip_torrents', False)
    LIDARR_URL = config.get('lidarr_url', 'http://100.90.91.96:8686')
    LIDARR_API_KEY = config['lidarr_api_key']
    JACKETT_URL = config.get('jackett_url', 'http://100.90.91.96:9117')
    JACKETT_API_KEY = config['jackett_api_key']
    temp_server_port = config.get('temp_server_port', 8584)
    
    # Autenticar con Spotify (usando método simplificado)
    print("Iniciando autenticación con Spotify...")
    spotify = authenticate_spotify_simple(config['spotify_client_id'], config['spotify_client_secret'])
    if not spotify:
        print("Error: No se pudo autenticar con Spotify. Saliendo...")
        return None
    
    # Determinar la playlist a utilizar (prioridad: usuario > url > id)
    playlist_id = None
    playlist_name = None
    
    # Opción 1: Usuario proporcionado - mostrar lista y pedir selección
    if 'spotify_user' in config and config['spotify_user']:
        print(f"Obteniendo playlists del usuario {config['spotify_user']}...")
        playlists = get_user_playlists(config['spotify_user'], spotify)
        
        if not playlists:
            print(f"No se encontraron playlists para el usuario {config['spotify_user']}")
            return None
        
        # Mostrar tabla con las playlists
        table_data = display_playlists_table(playlists)
        
        # Pedir al usuario que seleccione una playlist
        while True:
            try:
                choice = int(input("\nSelecciona el número de la playlist que deseas usar: "))
                if 1 <= choice <= len(playlists):
                    playlist_id = playlists[choice-1]['id']
                    playlist_name = playlists[choice-1]['name']
                    print(f"Seleccionaste: {playlist_name} (ID: {playlist_id})")
                    break
                else:
                    print(f"Por favor, elige un número entre 1 y {len(playlists)}")
            except ValueError:
                print("Por favor, introduce un número válido")
    
    # Opción 2: URL proporcionada
    elif 'playlist_url' in config and config['playlist_url']:
        playlist_id = extract_playlist_id_from_url(config['playlist_url'])
        if not playlist_id:
            print(f"No se pudo extraer un ID de playlist válido de la URL: {config['playlist_url']}")
            return None
        print(f"Usando playlist ID {playlist_id} extraído de la URL")
        # Obtener el nombre de la playlist
        try:
            playlist_info = spotify.playlist(playlist_id)
            playlist_name = playlist_info['name']
            print(f"Nombre de la playlist: {playlist_name}")
        except Exception as e:
            print(f"Error al obtener el nombre de la playlist: {e}")
            playlist_name = f"playlist_{playlist_id}"
    
    # Opción 3: ID proporcionado directamente
    elif 'playlist_id' in config and config['playlist_id']:
        playlist_id = config['playlist_id']
        print(f"Usando playlist ID proporcionado: {playlist_id}")
        # Obtener el nombre de la playlist
        try:
            playlist_info = spotify.playlist(playlist_id)
            playlist_name = playlist_info['name']
            print(f"Nombre de la playlist: {playlist_name}")
        except Exception as e:
            print(f"Error al obtener el nombre de la playlist: {e}")
            playlist_name = f"playlist_{playlist_id}"
    
    # Si no se pudo determinar un playlist_id, salir
    if not playlist_id:
        print("Error: No se pudo determinar un ID de playlist. Por favor proporciona un usuario, URL o ID de playlist.")
        return None
    
    # Sanitizar el nombre de la playlist para usarlo como directorio
    if playlist_name:
        # Eliminar caracteres no válidos para nombres de directorios
        sanitized_name = re.sub(r'[\\/*?:"<>|]', '', playlist_name)
        # Reemplazar espacios con guiones bajos
        sanitized_name = sanitized_name.replace(' ', '_')
        # Crear la ruta completa
        path_destino_flac = os.path.join(path_destino_flac_base, sanitized_name)
    else:
        path_destino_flac = path_destino_flac_base
    
    print(f"Ruta de destino para los archivos: {path_destino_flac}")
    
    # Obtener información de las canciones de la playlist
    print(f"Obteniendo datos de la playlist {playlist_id}...")
    tracks = get_spotify_playlist_tracks(playlist_id, spotify)
    
    if not tracks:
        print(f"No se encontraron canciones en la playlist {playlist_id}")
        return None
    
    # Guardar la información en un archivo JSON
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(tracks, f, ensure_ascii=False, indent=4)
    
    print(f"Información guardada en {json_file}")
    
    # Procesar cada canción
    copied_tracks = []
    failed_tracks = []
    copied_count = 0

    # Crear directorio de destino si no existe
    if not os.path.exists(path_destino_flac):
        os.makedirs(path_destino_flac)
    
    # Convertir tracks a agrupados por álbum y artista para mejor procesamiento
    original_tracks = tracks.copy()  # Guarda una copia de la lista original para referencia

    for track in tracks:
        artista = track['artista']
        album = track['album']
        cancion = track['cancion']
        
        print(f"Procesando: {cancion} - {artista}")
        
        # Obtener la ruta del archivo original
        original_path = get_file_path(artista, album, cancion, db_path)
        if not original_path:
            print(f"No se encontró ruta para: {cancion} - {artista}")
            failed_tracks.append(track)
            continue
        
        print(f"Ruta original: {original_path}")
        
        # Verificar si el archivo original existe
        if debug:
            print(f"Verificando si existe: {original_path}")
            escaped_path = original_path.replace("'", "'\\''")
            cmd = f"ls -la '{escaped_path}'"
            print(f"Comando: {cmd}")
            os.system(cmd)
            
        if not file_exists(original_path):
            print(f"El archivo original no existe: {original_path}")
            failed_tracks.append(track)
            continue
            
        # Ajustar la ruta
        adjusted_path = adjust_path(original_path)
        if not adjusted_path:
            print(f"No se pudo ajustar la ruta: {original_path}")
            failed_tracks.append(track)
            continue
            
        print(f"Ruta ajustada: {adjusted_path}")
        
        # Comprobar que el archivo existe después de ajustar la ruta
        if debug:
            print(f"Verificando si existe la ruta ajustada: {adjusted_path}")
            escaped_adj_path = adjusted_path.replace("'", "'\\''")
            cmd = f"ls -la '{escaped_adj_path}'"
            print(f"Comando: {cmd}")
            os.system(cmd)
            
        if not file_exists(adjusted_path):
            print(f"El archivo no existe en la ruta ajustada: {adjusted_path}")
            # Intentar directamente con la ruta original
            print(f"Intentando con la ruta original...")
            if file_exists(original_path) and copy_file(original_path, path_destino_flac):
                copied_tracks.append(track)
                copied_count += 1
                continue
            else:
                failed_tracks.append(track)
                continue
        
        # Copiar el archivo
        if copy_file(adjusted_path, path_destino_flac):
            copied_tracks.append(track)
            copied_count += 1
        else:
            failed_tracks.append(track)

        # IMPORTANTE: Organizar las canciones fallidas por álbum y artista antes de guardar en JSON
    organized_failed_tracks = organize_tracks_by_album_artist(failed_tracks)
    
    # Guardar solo las canciones fallidas en el JSON, agrupadas por álbum y artista
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(organized_failed_tracks, f, ensure_ascii=False, indent=4)

    print(f"\nResumen:")
    print(f"Total de canciones en la playlist: {len(original_tracks)}")
    print(f"Canciones copiadas con éxito: {len(copied_tracks)}")
    print(f"Canciones copiadas con éxito (count): {copied_count}")
    print(f"Canciones no encontradas o con error: {len(failed_tracks)}")
    print(f"Grupos de álbum/artista en el JSON actualizado: {len(organized_failed_tracks)}")
    print(f"JSON actualizado con las canciones pendientes: {json_file}")
    
    # Preparar los datos de configuración para el script de torrents
    config_data = {
        'carpeta_torrents_temporales': carpeta_torrents_temporales,
        'carpeta_watchfolder': carpeta_watchfolder,
        'carpeta_descargas_qbitorrent': carpeta_descargas_qbitorrent,
        'modo': modo,
        'path_destino_flac': path_destino_flac,  # Ahora incluye el nombre de la playlist
        'json_file': json_file,
        'lidarr_url': LIDARR_URL,
        'lidarr_api_key': LIDARR_API_KEY,
        'jackett_url': JACKETT_URL,
        'jackett_api_key': JACKETT_API_KEY,
        'temp_server_port': temp_server_port
    }
    
    # Si hay canciones pendientes y no se debe omitir el script de torrents, lanzarlo
    if failed_tracks and not skip_torrents:
        print(f"\nHay {len(failed_tracks)} canciones pendientes, ejecutando script de torrents...")
        launch_torrent_script(config_data)
    elif skip_torrents:
        print("\nSe ha omitido la ejecución del script de torrents (--skip-torrents)")
    else:
        print("\nNo hay canciones pendientes, no es necesario ejecutar el script de torrents")
    
    return config_data

    
# Ejemplo de archivo de configuración JSON:
"""
{
    "db_path": "/ruta/a/tu/base/de/datos.db",
    "playlist_id": "",
    "playlist_url": "https://open.spotify.com/playlist/37i9dQZF1DX4sWSpwq3LiO",
    "spotify_user": "usuario_spotify",
    "spotify_client_id": "tu_client_id_de_spotify",
    "spotify_client_secret": "tu_client_secret_de_spotify",
    "path_destino_flac": "/ruta/donde/copiar/canciones",
    "json_file": "playlist_songs.json",
    "debug": false,
    "modo": "interactivo o automatico",
    "carpeta_torrents_temporales": "./torrents",
    "carpeta_watchfolder": "/watch folder qbitorrent",
    "carpeta_descargas_qbitorrent": "/downloads en qbitorrent",
    "skip_torrents": false
}
"""

if __name__ == "__main__":
    result = main()
