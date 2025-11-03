"""
Script Name: mover_mix_playerctl.py
Description: Mover canción sonando actualmente a subcarpeta de la ruta establecida en Mix
Author: volteret4
Repository: https://github.com/volteret4/
License:
TODO:
Notes:
    La idea de este script es poder tener, en una carpeta aparte separada, una selección de música con otro criterio (género por ej.)
"""
from PyQt6 import uic
import os
import sys
import subprocess
import time
import shutil
import sqlite3
import json
import requests
import hashlib
import random
import string
from pathlib import Path
from dotenv import load_dotenv

import re

from PyQt6.QtWidgets import (QWidget, QApplication, QDialog, QVBoxLayout, QHBoxLayout,
                            QLineEdit, QLabel, QPushButton, QMessageBox,
                            QInputDialog, QGridLayout, QScrollArea)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QPixmap, QPalette, QColor

# Configuración de Airsonic Advanced
load_dotenv()
AIRSONIC_URL = os.getenv("AIRSONIC_URL")  # CAMBIAR POR TU URL
AIRSONIC_USERNAME = os.getenv("AIRSONIC_USERNAME")          # CAMBIAR POR TU USUARIO
AIRSONIC_PASSWORD = os.getenv("AIRSONIC_PASSWORD")         # CAMBIAR POR TU PASSWORD
AIRSONIC_CLIENT = "mover_mix_script"



class AirsonicClient:
    def __init__(self, url, username, password, client_name=AIRSONIC_CLIENT):
        self.url = url.rstrip('/')
        self.username = username
        self.password = password
        self.client_name = client_name
        self.api_version = "1.15.0"  # Cambiado para coincidir con tu servidor

    def _generate_salt(self):
        """Generar salt aleatorio para autenticación"""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

    def _get_auth_params(self):
        """Obtener parámetros de autenticación para la API"""
        salt = self._generate_salt()
        token = hashlib.md5((self.password + salt).encode()).hexdigest()

        return {
            'u': self.username,
            't': token,
            's': salt,
            'v': self.api_version,
            'c': self.client_name,
            'f': 'json'
        }

    def _make_request(self, endpoint, params=None):
        """Hacer petición a la API de Airsonic"""
        auth_params = self._get_auth_params()
        if params:
            auth_params.update(params)

        # Usar .view al final del endpoint según la documentación
        url = f"{self.url}/rest/{endpoint}.view"
        print(f"[DEBUG] Haciendo petición a: {url}")
        print(f"[DEBUG] Parámetros: {auth_params}")

        try:
            response = requests.get(url, params=auth_params, timeout=30)
            print(f"[DEBUG] Código de respuesta: {response.status_code}")

            if response.status_code != 200:
                print(f"[DEBUG] Error HTTP: {response.text}")

            response.raise_for_status()
            json_response = response.json()
            print(f"[DEBUG] Respuesta JSON recibida correctamente")
            return json_response

        except requests.exceptions.RequestException as e:
            print(f"[DEBUG] Error de conexión: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"[DEBUG] Error decodificando JSON: {e}")
            print(f"[DEBUG] Respuesta raw: {response.text}")
            return None
        except Exception as e:
            print(f"[DEBUG] Error inesperado en petición: {e}")
            return None

    def test_connection(self):
        """Probar conexión con ping"""
        print(f"[DEBUG] === PROBANDO CONEXIÓN CON AIRSONIC ===")
        print(f"[DEBUG] URL: {self.url}")
        print(f"[DEBUG] Usuario: {self.username}")

        result = self._make_request('ping')
        if result:
            print(f"[DEBUG] Ping exitoso: {result}")
            return True
        else:
            print(f"[DEBUG] Ping falló")
            return False

    def _make_request(self, endpoint, params=None):
        """Hacer petición a la API de Airsonic"""
        auth_params = self._get_auth_params()
        if params:
            auth_params.update(params)

        url = f"{self.url}/rest/{endpoint}"
        print(f"[DEBUG] Haciendo petición a: {url}")
        print(f"[DEBUG] Parámetros: {auth_params}")

        try:
            response = requests.get(url, params=auth_params, timeout=30)
            print(f"[DEBUG] Código de respuesta: {response.status_code}")

            if response.status_code != 200:
                print(f"[DEBUG] Error HTTP: {response.text}")

            response.raise_for_status()
            json_response = response.json()
            print(f"[DEBUG] Respuesta JSON recibida correctamente")
            return json_response

        except requests.exceptions.RequestException as e:
            print(f"[DEBUG] Error de conexión: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"[DEBUG] Error decodificando JSON: {e}")
            print(f"[DEBUG] Respuesta raw: {response.text}")
            return None
        except Exception as e:
            print(f"[DEBUG] Error inesperado en petición: {e}")
            return None

    def search_song(self, artist, title, album=None):
        """Buscar canción en Airsonic"""
        print(f"[DEBUG] Buscando: artista='{artist}', título='{title}', álbum='{album}'")

        # Buscar por artista y título
        query = f"{artist} {title}"
        if album:
            query += f" {album}"

        print(f"[DEBUG] Query de búsqueda: '{query}'")

        params = {
            'query': query,
            'songCount': 20,
            'artistCount': 0,
            'albumCount': 0
        }

        result = self._make_request('search3', params)
        print(f"[DEBUG] Respuesta raw de Airsonic: {json.dumps(result, indent=2) if result else 'None'}")

        if not result or 'subsonic-response' not in result:
            print("[DEBUG] No hay respuesta válida de Airsonic")
            return None

        response = result['subsonic-response']
        if response.get('status') != 'ok':
            error_msg = response.get('error', {}).get('message', 'Error desconocido')
            print(f"[DEBUG] Error en respuesta de Airsonic: {error_msg}")
            return None

        if 'searchResult3' not in response:
            print("[DEBUG] No hay resultados de búsqueda")
            return None

        songs = response['searchResult3'].get('song', [])
        print(f"[DEBUG] Número de canciones encontradas: {len(songs)}")

        if not songs:
            print("[DEBUG] No se encontraron canciones")
            return None

        # Mostrar todas las canciones encontradas
        for i, song in enumerate(songs):
            print(f"[DEBUG] Canción {i+1}: {song.get('artist', 'N/A')} - {song.get('title', 'N/A')} (álbum: {song.get('album', 'N/A')})")

        # Buscar la mejor coincidencia
        best_match = None
        best_score = 0

        for song in songs:
            score = 0
            song_artist = song.get('artist', '').lower()
            song_title = song.get('title', '').lower()
            song_album = song.get('album', '').lower()

            print(f"[DEBUG] Evaluando: '{song_artist}' - '{song_title}'")

            # Puntuación por coincidencia de artista
            if artist.lower() in song_artist or song_artist in artist.lower():
                score += 50
                print(f"[DEBUG] Coincidencia de artista (+50): {score}")

            # Puntuación por coincidencia de título
            if title.lower() in song_title or song_title in title.lower():
                score += 50
                print(f"[DEBUG] Coincidencia de título (+50): {score}")

            # Puntuación por coincidencia de álbum
            if album and (album.lower() in song_album or song_album in album.lower()):
                score += 20
                print(f"[DEBUG] Coincidencia de álbum (+20): {score}")

            print(f"[DEBUG] Puntuación final para esta canción: {score}")

            if score > best_score:
                best_score = score
                best_match = song

        print(f"[DEBUG] Mejor coincidencia: puntuación {best_score}, canción: {best_match.get('artist', 'N/A') if best_match else 'None'} - {best_match.get('title', 'N/A') if best_match else 'None'}")

        return best_match if best_score >= 50 else None

    def download_song(self, song_id, download_path):
        """Descargar canción desde Airsonic"""
        print(f"[DEBUG] Intentando descargar canción con ID: {song_id}")
        print(f"[DEBUG] Carpeta de descarga: {download_path}")

        params = {'id': song_id}
        auth_params = self._get_auth_params()
        auth_params.update(params)

        # Usar .view para download también
        url = f"{self.url}/rest/download.view"
        print(f"[DEBUG] URL de descarga: {url}")
        print(f"[DEBUG] Parámetros: {auth_params}")

        try:
            response = requests.get(url, params=auth_params, stream=True, timeout=60)
            print(f"[DEBUG] Código de respuesta HTTP: {response.status_code}")
            print(f"[DEBUG] Headers de respuesta: {dict(response.headers)}")

            response.raise_for_status()

            # Obtener nombre de archivo desde headers o usar ID
            filename = f"song_{song_id}.mp3"  # Extensión por defecto

            if 'content-disposition' in response.headers:
                cd = response.headers['content-disposition']
                print(f"[DEBUG] Content-Disposition: {cd}")
                if 'filename=' in cd:
                    filename = cd.split('filename=')[1].strip('"').strip("'")
                    print(f"[DEBUG] Filename extraído: {filename}")

            # Si no hay extensión, intentar detectarla del content-type
            if '.' not in filename:
                content_type = response.headers.get('content-type', '')
                print(f"[DEBUG] Content-Type: {content_type}")
                if 'audio/mpeg' in content_type or 'mp3' in content_type:
                    filename += '.mp3'
                elif 'audio/flac' in content_type:
                    filename += '.flac'
                elif 'audio/ogg' in content_type:
                    filename += '.ogg'
                elif 'audio/wav' in content_type:
                    filename += '.wav'

            file_path = os.path.join(download_path, filename)
            print(f"[DEBUG] Ruta completa del archivo: {file_path}")

            # Asegurar que la carpeta existe
            os.makedirs(download_path, exist_ok=True)

            downloaded_size = 0
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)

            print(f"[DEBUG] Descarga completada. Tamaño: {downloaded_size} bytes")

            # Verificar que el archivo se descargó correctamente
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                print(f"[DEBUG] Archivo descargado exitosamente: {file_path}")
                return file_path
            else:
                print("[DEBUG] El archivo descargado está vacío o no existe")
                return None

        except Exception as e:
            print(f"[DEBUG] Error descargando canción: {e}")
            import traceback
            traceback.print_exc()
            return None


class MusicMover:
    def __init__(self):
        self.mixxx_path = "/mnt/windows/Mix"  # CHANGE!!
        self.db_path = os.environ.get('MFUZZ_DB')
        self.temp_download_path = "/tmp/airsonic_downloads"  # Carpeta temporal para descargas

        # Crear carpeta temporal si no existe
        os.makedirs(self.temp_download_path, exist_ok=True)

        # Inicializar cliente Airsonic
        self.airsonic = AirsonicClient(AIRSONIC_URL, AIRSONIC_USERNAME, AIRSONIC_PASSWORD)

    def get_database_info(self, artist_name, title, album_name=""):
        """Obtener información del artista y álbum desde la base de datos"""
        if not self.db_path or not os.path.exists(self.db_path):
            return None, None

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Buscar artista
            artist_info = None
            cursor.execute("SELECT id, name, img, img_paths FROM artists WHERE name LIKE ?", (f"%{artist_name}%",))
            artist_row = cursor.fetchone()
            if artist_row:
                artist_info = {
                    'id': artist_row[0],
                    'name': artist_row[1],
                    'img': artist_row[2],
                    'img_paths': artist_row[3]
                }

            # Buscar álbum
            album_info = None
            if album_name and artist_info:
                cursor.execute("""
                    SELECT id, name, album_art_path, year
                    FROM albums
                    WHERE artist_id = ? AND name LIKE ?
                """, (artist_info['id'], f"%{album_name}%"))
                album_row = cursor.fetchone()
                if album_row:
                    album_info = {
                        'id': album_row[0],
                        'name': album_row[1],
                        'album_art_path': album_row[2],
                        'year': album_row[3]
                    }

            conn.close()
            return artist_info, album_info

        except Exception as e:
            print(f"Error accediendo a la base de datos: {e}")
            return None, None

    def add_to_lastfm_loved(self, artist, title):
        """Añadir canción a las loved tracks de Last.fm usando la API"""
        try:
            # Cargar credenciales de Last.fm desde .env
            load_dotenv()
            LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")
            LASTFM_API_SECRET = os.getenv("LASTFM_API_SECRET")
            LASTFM_USERNAME = os.getenv("LASTFM_USERNAME")
            LASTFM_PASSWORD = os.getenv("LASTFM_PASSWORD")

            if not all([LASTFM_API_KEY, LASTFM_API_SECRET, LASTFM_USERNAME, LASTFM_PASSWORD]):
                print("Faltan credenciales de Last.fm en el archivo .env")
                return False

            # Obtener token de autenticación
            auth_url = "https://ws.audioscrobbler.com/2.0/"
            auth_params = {
                "method": "auth.getMobileSession",
                "username": LASTFM_USERNAME,
                "password": LASTFM_PASSWORD,
                "api_key": LASTFM_API_KEY,
                "format": "json"
            }

            # Crear firma para autenticación
            signature = self._create_lastfm_signature(auth_params, LASTFM_API_SECRET)
            auth_params["api_sig"] = signature

            # Realizar petición de autenticación
            auth_response = requests.post(auth_url, data=auth_params)

            if auth_response.status_code != 200:
                print(f"Error de autenticación en Last.fm: {auth_response.text}")
                return False

            session_key = auth_response.json().get("session", {}).get("key")

            if not session_key:
                print("No se pudo obtener session key de Last.fm")
                return False

            # Añadir canción a loved tracks
            love_params = {
                "method": "track.love",
                "artist": artist,
                "track": title,
                "api_key": LASTFM_API_KEY,
                "sk": session_key,
                "format": "json"
            }

            # Crear firma para petición love
            love_signature = self._create_lastfm_signature(love_params, LASTFM_API_SECRET)
            love_params["api_sig"] = love_signature

            # Realizar petición para marcar como loved
            love_response = requests.post(auth_url, data=love_params)

            if love_response.status_code != 200:
                print(f"Error añadiendo canción a loved tracks: {love_response.text}")
                return False

            print(f"Canción '{artist} - {title}' añadida a loved tracks de Last.fm")
            return True

        except Exception as e:
            print(f"Error añadiendo canción a Last.fm: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _create_lastfm_signature(self, params, api_secret):
        """Crear firma para peticiones a Last.fm API"""
        # Ordenar parámetros alfabéticamente y crear string para firma
        sorted_params = sorted(params.items())
        signature_string = ""

        for name, value in sorted_params:
            if name != "format":  # Excluir format de la firma
                signature_string += name + str(value)

        # Añadir clave secreta
        signature_string += api_secret

        # Calcular MD5
        return hashlib.md5(signature_string.encode("utf-8")).hexdigest()

    def download_from_airsonic(self, artist, title, album=None):
        """Descargar canción desde Airsonic Advanced"""
        try:
            print(f"Buscando en Airsonic: {artist} - {title}")

            # Buscar la canción en Airsonic
            song = self.airsonic.search_song(artist, title, album)
            if not song:
                print("Canción no encontrada en Airsonic")
                return None

            print(f"Canción encontrada: {song.get('artist')} - {song.get('title')}")

            # Descargar la canción
            song_id = song.get('id')
            if not song_id:
                print("ID de canción no válido")
                return None

            downloaded_file = self.airsonic.download_song(song_id, self.temp_download_path)
            if not downloaded_file:
                print("Error descargando archivo")
                return None

            # Generar información de track para el archivo descargado
            track_info = {
                'path': downloaded_file,
                'filename': os.path.basename(downloaded_file),
                'song_name': f"{artist} - {title}",
                'artist': artist,
                'title': title,
                'album': album or song.get('album', ''),
                'folder': 'airsonic_download',
                'is_airsonic_download': True
            }

            print(f"Archivo descargado: {downloaded_file}")
            return track_info

        except Exception as e:
            print(f"Error descargando desde Airsonic: {e}")
            return None

    def get_current_track_info(self):
        """Obtener información de la canción en reproducción"""
        try:
            # Probar playerctl primero
            try:
                # Verificar qué reproductor está activo
                players_result = subprocess.run(
                    ['playerctl', '--list-all'],
                    capture_output=True, text=True
                )
                active_players = players_result.stdout.strip().split('\n') if players_result.stdout.strip() else []

                # Buscar supersonic entre los reproductores activos
                supersonic_player = None
                for player in active_players:
                    if 'supersonic' in player.lower():
                        supersonic_player = player
                        break

                # Si supersonic está activo, manejar caso especial
                if supersonic_player:
                    print("Detectado reproductor Supersonic")

                    # Obtener metadatos con supersonic
                    title = subprocess.run(
                        ['playerctl', '-p', supersonic_player, 'metadata', 'title'],
                        capture_output=True, text=True
                    ).stdout.strip()

                    artist = subprocess.run(
                        ['playerctl', '-p', supersonic_player, 'metadata', 'artist'],
                        capture_output=True, text=True
                    ).stdout.strip()

                    album = subprocess.run(
                        ['playerctl', '-p', supersonic_player, 'metadata', 'album'],
                        capture_output=True, text=True
                    ).stdout.strip()

                    if title and artist:
                        # Intentar descargar desde Airsonic
                        track_info = self.download_from_airsonic(artist, title, album)
                        if track_info:
                            return track_info
                        else:
                            # Si falla la descarga, crear info básica
                            return {
                                'path': '',
                                'filename': f"{artist} - {title}",
                                'song_name': f"{artist} - {title}",
                                'artist': artist,
                                'title': title,
                                'album': album,
                                'folder': 'supersonic_stream',
                                'is_stream': True
                            }

                # Para otros reproductores, usar lógica normal de playerctl
                url = subprocess.run(
                    ['playerctl', 'metadata', 'xesam:url'],
                    capture_output=True, text=True
                ).stdout.strip()

                if url:
                    # Usar playerctl normal
                    path = unquote(url.replace('file://', ''))
                    filename = os.path.basename(path)

                    # Limpiar caracteres especiales del filename
                    filename = re.sub(r'[":]+', '', filename)

                    title = subprocess.run(
                        ['playerctl', 'metadata', 'title'],
                        capture_output=True, text=True
                    ).stdout.strip()

                    artist = subprocess.run(
                        ['playerctl', 'metadata', 'artist'],
                        capture_output=True, text=True
                    ).stdout.strip()

                    album = subprocess.run(
                        ['playerctl', 'metadata', 'album'],
                        capture_output=True, text=True
                    ).stdout.strip()

                    song_name = f"{artist} - {title}" if artist and title else (title if title else filename)

                    return {
                        'path': path,
                        'filename': filename,
                        'song_name': song_name,
                        'artist': artist,
                        'title': title,
                        'album': album,
                        'folder': os.path.basename(os.path.dirname(path))
                    }
                else:
                    raise Exception("Playerctl no devolvió URL")

            except Exception as e:
                print(f"Error con playerctl: {e}")
                # Si playerctl falla, probar deadbeef
                deadbeef_artist = subprocess.run(
                    ['deadbeef', '--nowplaying-tf', '%artist%'],
                    capture_output=True, text=True
                ).stdout.strip()

                if deadbeef_artist:
                    # Usar deadbeef
                    path = subprocess.run(
                        ['deadbeef', '--nowplaying-tf', '%path%'],
                        capture_output=True, text=True
                    ).stdout.strip()

                    filename = subprocess.run(
                        ['deadbeef', '--nowplaying-tf', '%filename_ext%'],
                        capture_output=True, text=True
                    ).stdout.strip()

                    artist = subprocess.run(
                        ['deadbeef', '--nowplaying-tf', '%artist%'],
                        capture_output=True, text=True
                    ).stdout.strip()

                    title = subprocess.run(
                        ['deadbeef', '--nowplaying-tf', '%title%'],
                        capture_output=True, text=True
                    ).stdout.strip()

                    album = subprocess.run(
                        ['deadbeef', '--nowplaying-tf', '%album%'],
                        capture_output=True, text=True
                    ).stdout.strip()

                    song_name = f"{artist} - {title}"

                    return {
                        'path': path,
                        'filename': filename,
                        'song_name': song_name,
                        'artist': artist,
                        'title': title,
                        'album': album,
                        'folder': os.path.basename(os.path.dirname(path))
                    }
                else:
                    raise Exception("No hay reproductor activo")

        except Exception as e:
            raise Exception(f"Error obteniendo información de la canción: {e}")

    def cleanup_temp_files(self):
        """Limpiar archivos temporales descargados"""
        try:
            if os.path.exists(self.temp_download_path):
                shutil.rmtree(self.temp_download_path)
                os.makedirs(self.temp_download_path, exist_ok=True)
        except Exception as e:
            print(f"Error limpiando archivos temporales: {e}")

    def find_duplicates(self, song_name, artist="", title=""):
        """Buscar duplicados en todas las subcarpetas de Mix"""
        duplicates = []

        # Buscar por nombre completo de canción
        if song_name:
            cmd = ['find', self.mixxx_path, '-iname', f"*{song_name}*"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.stdout.strip():
                duplicates.extend(result.stdout.strip().split('\n'))

        # Buscar también por título si existe
        if title:
            cmd = ['find', self.mixxx_path, '-iname', f"*{title}*"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.stdout.strip():
                for dup in result.stdout.strip().split('\n'):
                    if dup not in duplicates:
                        duplicates.append(dup)

        # Filtrar archivos válidos y eliminar duplicados
        valid_duplicates = []
        for dup in duplicates:
            if os.path.isfile(dup) and dup not in valid_duplicates:
                valid_duplicates.append(dup)

        return valid_duplicates

    def get_subfolders(self):
        """Obtener subcarpetas del directorio Mix"""
        subfolders = []
        try:
            for item in os.listdir(self.mixxx_path):
                item_path = os.path.join(self.mixxx_path, item)
                if os.path.isdir(item_path) and item != ".stfolder":
                    subfolders.append(item)
            return sorted(subfolders)
        except Exception as e:
            print(f"Error obteniendo subcarpetas: {e}")
            return []

    def copy_file(self, source, destination_folder):
        """Copiar archivo al destino"""
        dest_path = os.path.join(self.mixxx_path, destination_folder)
        if not os.path.exists(dest_path):
            os.makedirs(dest_path)

        dest_file = os.path.join(dest_path, os.path.basename(source))
        shutil.copy2(source, dest_file)
        return dest_file

    def move_file(self, source, destination_folder):
        """Mover archivo al destino"""
        dest_path = os.path.join(self.mixxx_path, destination_folder)
        if not os.path.exists(dest_path):
            os.makedirs(dest_path)

        dest_file = os.path.join(dest_path, os.path.basename(source))
        shutil.move(source, dest_file)
        return dest_file

    def set_tags(self, file_path, comment="", rename=True):
        """Establecer tags y renombrar archivo con formato extendido"""
        try:
            # Obtener directorio y extensión del archivo
            dir_path = os.path.dirname(file_path)
            file_ext = os.path.splitext(file_path)[1].lower()

            # Intentar leer metadatos con ffprobe primero
            try:
                # Verificar si ffprobe está disponible
                subprocess.run(['ffprobe', '-version'], capture_output=True, check=True)

                # Leer metadatos
                metadata_result = subprocess.run(
                    ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', file_path],
                    capture_output=True, text=True, check=True
                )
                metadata = json.loads(metadata_result.stdout)

                # Extraer metadatos
                tags = metadata.get('format', {}).get('tags', {})
                artist = tags.get('artist', tags.get('ARTIST', ''))
                title = tags.get('title', tags.get('TITLE', ''))
                album = tags.get('album', tags.get('ALBUM', ''))
                date = tags.get('date', tags.get('DATE', ''))
                if not date:
                    date = tags.get('year', tags.get('YEAR', ''))
                label = tags.get('label', tags.get('LABEL', tags.get('publisher', tags.get('PUBLISHER', ''))))

                # Si se especifica un comentario, añadirlo usando ffmpeg
                if comment:
                    # Crear archivo temporal
                    temp_file = f"{file_path}.temp{file_ext}"

                    # Añadir comentario con ffmpeg
                    subprocess.run([
                        'ffmpeg', '-i', file_path, '-map_metadata', '0',
                        '-metadata', f'comment={comment}', '-c', 'copy', temp_file
                    ], check=True)

                    # Reemplazar archivo original
                    os.replace(temp_file, file_path)

            except (subprocess.SubprocessError, json.JSONDecodeError, FileNotFoundError):
                # Si ffprobe falla, intentar con exiftool
                try:
                    # Verificar si exiftool está disponible
                    subprocess.run(['exiftool', '-ver'], capture_output=True, check=True)

                    # Leer metadatos
                    artist_result = subprocess.run(['exiftool', '-Artist', '-s3', file_path],
                                                capture_output=True, text=True)
                    artist = artist_result.stdout.strip()

                    title_result = subprocess.run(['exiftool', '-Title', '-s3', file_path],
                                                capture_output=True, text=True)
                    title = title_result.stdout.strip()

                    album_result = subprocess.run(['exiftool', '-Album', '-s3', file_path],
                                                capture_output=True, text=True)
                    album = album_result.stdout.strip()

                    date_result = subprocess.run(['exiftool', '-Year', '-s3', file_path],
                                              capture_output=True, text=True)
                    date = date_result.stdout.strip()

                    label_result = subprocess.run(['exiftool', '-Label', '-s3', file_path],
                                               capture_output=True, text=True)
                    label = label_result.stdout.strip()

                    # Si se especifica un comentario, añadirlo usando exiftool
                    if comment:
                        subprocess.run(['exiftool', f'-Comment={comment}', '-overwrite_original', file_path],
                                     check=True)

                except (subprocess.SubprocessError, FileNotFoundError):
                    # Si exiftool también falla, usar información del track_info
                    print("No se pudieron leer los metadatos. Usando información básica disponible.")
                    artist = self.track_info.get('artist', '')
                    title = self.track_info.get('title', '')
                    album = self.track_info.get('album', '')
                    date = ''
                    label = ''

            if rename:
                # Usar información extraída para renombrar
                if not artist and not title:
                    # Si no hay metadatos suficientes, usar el nombre original
                    return file_path

                # Construir nuevo nombre de archivo
                new_filename = f"{artist} - {title}"

                # Añadir date y album si están disponibles
                if date or album:
                    date_album_part = ""
                    if date:
                        date_album_part += date
                    if album:
                        if date_album_part:
                            date_album_part += " "
                        date_album_part += album

                    new_filename += f" ({date_album_part})"

                # Añadir label si está disponible
                if label:
                    new_filename += f" [{label}]"

                # Limpiar caracteres problemáticos del nombre de archivo
                new_filename = re.sub(r'[/\\?%*:|"<>]', '-', new_filename)

                # Añadir extensión
                new_filename += file_ext

                # Ruta completa del nuevo archivo
                new_file_path = os.path.join(dir_path, new_filename)

                print(f"Renombrando: {file_path} -> {new_file_path}")

                # Renombrar usando os.rename
                os.rename(file_path, new_file_path)

                return new_file_path

            return file_path

        except Exception as e:
            print(f"Error estableciendo tags o renombrando: {e}")
            import traceback
            traceback.print_exc()
            return file_path

    def get_existing_comment(self, file_path):
        """Obtener comentario existente de un archivo"""
        try:
            result = subprocess.run(['tagutil', 'print', file_path], capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if 'comment:' in line:
                    return line.split('comment: ', 1)[1] if 'comment: ' in line else ''
            return ""
        except:
            return ""

    def update_playlists(self):
        """Actualizar playlists de Mixxx"""
        try:
            # Eliminar playlists existentes
            for m3u_file in Path(self.mixxx_path).glob("*.m3u"):
                m3u_file.unlink()

            # Crear nuevas playlists
            for subfolder in self.get_subfolders():
                subfolder_path = os.path.join(self.mixxx_path, subfolder)
                playlist_file = os.path.join(self.mixxx_path, f"{subfolder}.m3u")

                with open(playlist_file, 'w') as f:
                    for root, dirs, files in os.walk(subfolder_path):
                        for file in files:
                            if file.lower().endswith(('.mp3', '.flac', '.ogg', '.wav', '.m4a')):
                                file_path = os.path.join(root, file)
                                # Escribir ruta relativa
                                rel_path = os.path.relpath(file_path, self.mixxx_path)
                                f.write(f"{rel_path}\n")

        except Exception as e:
            print(f"Error actualizando playlists: {e}")






class FolderSelectionDialog(QDialog):
    def __init__(self, folders, track_info, duplicates=None, artist_info=None, album_info=None, parent=None):
        super().__init__(parent)
        self.folders = folders
        self.track_info = track_info
        self.duplicates = duplicates or []
        self.artist_info = artist_info
        self.album_info = album_info
        self.selected_folder = None
        self.action = None  # 'copy', 'move', 'cancel'

        # Cargar UI desde archivo
        self.load_ui()
        self.setup_ui_connections()
        self.populate_ui()

    def load_ui(self):
        """Cargar interfaz desde archivo .ui"""
        # Obtener ruta del archivo .ui (en el mismo directorio que el script)
        ui_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "copy_mix_playerctl.ui")

        if os.path.exists(ui_file):
            uic.loadUi(ui_file, self)
        else:
            # Si no existe el archivo .ui, crear UI programáticamente como fallback
            self.create_fallback_ui()

    def create_fallback_ui(self):
        """Crear UI programáticamente si no existe el archivo .ui"""
        self.setWindowTitle("Mover música - Tokyo Night")
        self.setModal(True)
        self.setMinimumWidth(1000)
        self.setMinimumHeight(570)

        # Crear layout principal
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # Widget de información
        self.infoWidget = QWidget()
        info_layout = QHBoxLayout(self.infoWidget)
        info_layout.setSpacing(15)

        # Imagen
        self.imageLabel = QLabel()
        self.imageLabel.setFixedSize(120, 120)
        self.imageLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_layout.addWidget(self.imageLabel)

        # Layout de texto
        text_layout = QVBoxLayout()
        self.titleLabel = QLabel()
        self.artistLabel = QLabel()
        self.albumLabel = QLabel()
        self.folderLabel = QLabel()

        text_layout.addWidget(self.titleLabel)
        text_layout.addWidget(self.artistLabel)
        text_layout.addWidget(self.albumLabel)
        text_layout.addWidget(self.folderLabel)
        text_layout.addStretch()

        info_layout.addLayout(text_layout)
        main_layout.addWidget(self.infoWidget)

        # Widget de duplicados
        self.duplicatesWidget = QWidget()
        self.duplicatesLayout = QVBoxLayout(self.duplicatesWidget)
        self.duplicatesWidget.setVisible(False)
        main_layout.addWidget(self.duplicatesWidget)

        # ScrollArea para carpetas
        self.foldersScrollArea = QScrollArea()
        self.foldersScrollArea.setWidgetResizable(True)
        self.foldersScrollArea.setMinimumHeight(200)
        self.foldersScrollArea.setMaximumHeight(9950)

        self.foldersScrollAreaWidgetContents = QWidget()
        self.foldersGridLayout = QGridLayout(self.foldersScrollAreaWidgetContents)
        self.foldersScrollArea.setWidget(self.foldersScrollAreaWidgetContents)
        main_layout.addWidget(self.foldersScrollArea)

        # Widget de botones
        self.buttonsWidget = QWidget()
        buttons_layout = QHBoxLayout(self.buttonsWidget)

        self.newFolderButton = QPushButton("Nueva carpeta")
        self.copyButton = QPushButton("Copiar a otra carpeta")
        self.moveButton = QPushButton("Mover a otra carpeta")
        self.cancelButton = QPushButton("Cancelar")

        self.copyButton.setVisible(False)
        self.moveButton.setVisible(False)

        buttons_layout.addWidget(self.newFolderButton)
        buttons_layout.addWidget(self.copyButton)
        buttons_layout.addWidget(self.moveButton)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.cancelButton)

        main_layout.addWidget(self.buttonsWidget)
        self.setLayout(main_layout)

    def setup_ui_connections(self):
        """Configurar conexiones de señales y shortcuts"""
        from PyQt6.QtGui import QShortcut

        # Configurar hotkey ESC para cerrar
        esc_shortcut = QShortcut(QKeySequence("Escape"), self)
        esc_shortcut.activated.connect(self.reject)

        # Conectar botones
        self.newFolderButton.clicked.connect(self.create_new_folder)
        self.copyButton.clicked.connect(lambda: self.set_action('copy'))
        self.moveButton.clicked.connect(lambda: self.set_action('move'))
        self.cancelButton.clicked.connect(self.reject)

        # Aplicar object names para estilos
        self.titleLabel.setObjectName("title")
        self.artistLabel.setObjectName("artist")
        self.albumLabel.setObjectName("album")
        self.newFolderButton.setObjectName("primary")
        self.copyButton.setObjectName("primary")
        self.moveButton.setObjectName("warning")
        self.cancelButton.setObjectName("danger")

        # Establecer estilos específicos
        self.imageLabel.setStyleSheet("""
            border: 2px solid #1e1e2e;
            border-radius: 8px;
            background-color: #414868;
            color: #565f89;
            font-size: 14px;
            font-weight: bold;
        """)

        self.folderLabel.setStyleSheet("""
            color: #7dcfff;
            font-size: 11px;
            margin-top: 5px;
            background-color: transparent;
        """)

        self.infoWidget.setStyleSheet("background-color: #414868;")
        self.duplicatesWidget.setStyleSheet("background-color: #414868;")

    def populate_ui(self):
        """Poblar la UI con datos"""
        # Cargar imagen
        self.load_image()

        # Establecer información de la canción
        self.titleLabel.setText(self.track_info.get('title', 'Título desconocido'))
        self.artistLabel.setText(f"por {self.track_info.get('artist', 'Artista desconocido')}")
        self.folderLabel.setText(f"Carpeta: {self.track_info.get('folder', 'Carpeta desconocida')}")

        # Álbum si existe
        if self.track_info.get('album'):
            album_text = self.track_info['album']
            if self.album_info and self.album_info.get('year'):
                album_text += f" ({self.album_info['year']})"
            self.albumLabel.setText(f"de {album_text}")
            self.albumLabel.setVisible(True)
        else:
            self.albumLabel.setVisible(False)

        # Configurar duplicados si existen
        if self.duplicates:
            self.setup_duplicates()

        # Poblar carpetas
        self.populate_folders()

    def load_image(self):
        """Cargar imagen del artista/álbum"""
        image_loaded = False

        # Intentar cargar imagen del álbum primero
        if self.album_info and self.album_info.get('album_art_path'):
            album_art_path = self.album_info['album_art_path']
            if album_art_path and os.path.exists(album_art_path):
                try:
                    pixmap = QPixmap(album_art_path)
                    if not pixmap.isNull():
                        scaled_pixmap = pixmap.scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        self.imageLabel.setPixmap(scaled_pixmap)
                        image_loaded = True
                except Exception as e:
                    print(f"Error cargando imagen del álbum: {e}")

        # Si no se cargó la imagen del álbum, intentar con la del artista
        if not image_loaded and self.artist_info:
            # Intentar con img primero
            if self.artist_info.get('img'):
                img_path = self.artist_info['img']
                if img_path and os.path.exists(img_path):
                    try:
                        pixmap = QPixmap(img_path)
                        if not pixmap.isNull():
                            scaled_pixmap = pixmap.scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                            self.imageLabel.setPixmap(scaled_pixmap)
                            image_loaded = True
                    except Exception as e:
                        print(f"Error cargando imagen del artista (img): {e}")

            # Intentar con img_paths si img no funcionó
            if not image_loaded and self.artist_info.get('img_paths'):
                try:
                    import json
                    img_paths_str = self.artist_info['img_paths']
                    if img_paths_str:
                        img_paths = json.loads(img_paths_str)
                        if img_paths and isinstance(img_paths, list):
                            for img_path in img_paths:
                                if img_path and os.path.exists(img_path):
                                    try:
                                        pixmap = QPixmap(img_path)
                                        if not pixmap.isNull():
                                            scaled_pixmap = pixmap.scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                                            self.imageLabel.setPixmap(scaled_pixmap)
                                            image_loaded = True
                                            break
                                    except Exception as e:
                                        print(f"Error cargando imagen {img_path}: {e}")
                except Exception as e:
                    print(f"Error procesando img_paths: {e}")

        # Si no se pudo cargar ninguna imagen, mostrar placeholder
        if not image_loaded:
            self.imageLabel.setText("♪\nSin\nImagen")
            self.imageLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def setup_ui_connections(self):
        """Configurar conexiones de señales y shortcuts"""
        from PyQt6.QtGui import QShortcut

        # Configurar hotkey ESC para cerrar
        esc_shortcut = QShortcut(QKeySequence("Escape"), self)
        esc_shortcut.activated.connect(self.reject)

        # Conectar botones
        self.newFolderButton.clicked.connect(self.create_new_folder)
        self.copyButton.clicked.connect(lambda: self.set_action('copy'))
        self.moveButton.clicked.connect(lambda: self.set_action('move'))
        self.cancelButton.clicked.connect(self.reject)

        # Aplicar object names para estilos
        self.titleLabel.setObjectName("title")
        self.artistLabel.setObjectName("artist")
        self.albumLabel.setObjectName("album")
        self.newFolderButton.setObjectName("primary")
        self.copyButton.setObjectName("primary")
        self.moveButton.setObjectName("warning")
        self.cancelButton.setObjectName("danger")

        # Establecer estilos específicos
        self.imageLabel.setStyleSheet("""
            border: 2px solid #1e1e2e;
            border-radius: 8px;
            background-color: #414868;
            color: #565f89;
            font-size: 14px;
            font-weight: bold;
        """)

        self.folderLabel.setStyleSheet("""
            color: #7dcfff;
            font-size: 11px;
            margin-top: 5px;
            background-color: transparent;
        """)

        self.infoWidget.setStyleSheet("background-color: #414868;")
        self.duplicatesWidget.setStyleSheet("background-color: #414868;")




    def setup_duplicates(self):
        """Configurar UI para duplicados"""
        self.duplicatesWidget.setVisible(True)

        # Limpiar layout de duplicados
        while self.duplicatesLayout.count():
            child = self.duplicatesLayout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Añadir labels de duplicados
        for dup in self.duplicates:
            dup_label = QLabel(f"Canción encontrada en: {dup}")
            dup_label.setObjectName("duplicate_path")
            dup_label.setWordWrap(True)
            dup_label.setStyleSheet("""
                color: #e0af68;
                font-size: 12px;
                font-weight: bold;
                background-color: transparent;
                padding: 8px;
                border: 1px solid #414868;
                border-radius: 6px;
                margin: 5px 0px;
            """)
            self.duplicatesLayout.addWidget(dup_label)

        # Mostrar botones de copiar/mover, ocultar nueva carpeta
        self.newFolderButton.setVisible(False)
        self.copyButton.setVisible(True)
        self.moveButton.setVisible(True)

    def populate_folders(self):
        """Poblar el grid de carpetas"""
        # Limpiar layout de carpetas
        while self.foldersGridLayout.count():
            child = self.foldersGridLayout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        row, col = 0, 0
        max_cols = 4

        for folder in self.folders:
            hotkey = folder[0].upper()
            btn = QPushButton(f"{folder} ({hotkey})")
            btn.clicked.connect(lambda checked, f=folder: self.select_folder(f))
            btn.setMinimumHeight(50)
            btn.setMinimumWidth(120)

            # Configurar hotkey
            btn.setShortcut(QKeySequence(hotkey))

            self.foldersGridLayout.addWidget(btn, row, col)

            col += 1
            if col >= max_cols:
                col = 0
                row += 1


    def populate_ui(self):
        """Poblar la UI con datos"""
        # Cargar imagen
        self.load_image()

        # Establecer información de la canción
        self.titleLabel.setText(self.track_info.get('title', 'Título desconocido'))
        self.artistLabel.setText(f"por {self.track_info.get('artist', 'Artista desconocido')}")
        self.folderLabel.setText(f"Carpeta: {self.track_info.get('folder', 'Carpeta desconocida')}")

        # Álbum si existe
        if self.track_info.get('album'):
            album_text = self.track_info['album']
            if self.album_info and self.album_info.get('year'):
                album_text += f" ({self.album_info['year']})"
            self.albumLabel.setText(f"de {album_text}")
            self.albumLabel.setVisible(True)
        else:
            self.albumLabel.setVisible(False)

        # Configurar duplicados si existen
        if self.duplicates:
            self.setup_duplicates()

        # Poblar carpetas
        self.populate_folders()


    def create_info_widget(self):
        """Crear widget con información de la canción (imagen + texto)"""
        info_widget = QDialog()
        info_widget.setStyleSheet("background-color: #414868;")
        info_layout = QHBoxLayout(info_widget)
        info_layout.setSpacing(15)
        info_layout.setContentsMargins(0, 0, 0, 0)

        # Imagen del artista/álbum
        image_label = QLabel()
        image_label.setFixedSize(120, 120)
        image_label.setStyleSheet("""
            border: 2px solid #1e1e2e;
            border-radius: 8px;
            background-color: #414868;
        """)
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Cargar imagen
        self.load_image(image_label)
        info_layout.addWidget(image_label)

        # Información textual
        text_layout = QVBoxLayout()
        text_layout.setSpacing(8)
        text_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Título
        title_label = QLabel(self.track_info.get('title', 'Título desconocido'))
        title_label.setObjectName("title")
        title_label.setWordWrap(True)
        text_layout.addWidget(title_label)

        # Artista
        artist_label = QLabel(f"por {self.track_info.get('artist', 'Artista desconocido')}")
        artist_label.setObjectName("artist")
        artist_label.setWordWrap(True)
        text_layout.addWidget(artist_label)

        # Álbum si existe
        album_text = ""
        if self.track_info.get('album'):
            album_text = self.track_info['album']
            if self.album_info and self.album_info.get('year'):
                album_text += f" ({self.album_info['year']})"
            album_label = QLabel(f"de {album_text}")
            album_label.setObjectName("album")
            album_label.setWordWrap(True)
            text_layout.addWidget(album_label)

        # Carpeta actual
        folder_label = QLabel(f"Carpeta: {self.track_info.get('folder', 'Carpeta desconocida')}")
        folder_label.setStyleSheet("color: #7dcfff; font-size: 11px; margin-top: 5px; background-color: transparent;")
        text_layout.addWidget(folder_label)

        text_layout.addStretch()
        info_layout.addLayout(text_layout)

        return info_widget

    def create_duplicates_widget(self):
        """Crear widget que muestra información de duplicados"""
        duplicates_widget = QDialog()
        duplicates_widget.setStyleSheet("background-color: #414868;")
        duplicates_layout = QVBoxLayout(duplicates_widget)
        duplicates_layout.setContentsMargins(0, 0, 0, 0)

        for dup in self.duplicates:
            dup_label = QLabel(f"Canción encontrada en: {dup}")
            dup_label.setObjectName("duplicate_path")
            dup_label.setWordWrap(True)
            duplicates_layout.addWidget(dup_label)

        return duplicates_widget

    def create_buttons_widget(self, is_duplicates=False):
        """Crear widget con botones de acción"""
        buttons_widget = QDialog()
        buttons_widget.setStyleSheet("background-color: #414868;")
        buttons_layout = QHBoxLayout(buttons_widget)
        buttons_layout.setContentsMargins(0, 0, 0, 0)

        if is_duplicates:
            copy_btn = QPushButton("Copiar a otra carpeta")
            copy_btn.setObjectName("primary")
            copy_btn.clicked.connect(lambda: self.set_action('copy'))
            buttons_layout.addWidget(copy_btn)

            move_btn = QPushButton("Mover a otra carpeta")
            move_btn.setObjectName("warning")
            move_btn.clicked.connect(lambda: self.set_action('move'))
            buttons_layout.addWidget(move_btn)
        else:
            new_folder_btn = QPushButton("Nueva carpeta")
            new_folder_btn.setObjectName("primary")
            new_folder_btn.clicked.connect(self.create_new_folder)
            buttons_layout.addWidget(new_folder_btn)
            buttons_layout.addStretch()

        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setObjectName("danger")
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn)

        return buttons_widget

    def setup_duplicates_ui(self, main_layout):
        """Configurar UI específica para cuando hay duplicados"""
        # 1. Widget horizontal: imagen a la izquierda + texto a la derecha
        info_horizontal_widget = QDialog()
        info_horizontal_widget.setStyleSheet("background-color: #414868;")
        info_horizontal_layout = QHBoxLayout(info_horizontal_widget)
        info_horizontal_layout.setSpacing(15)
        info_horizontal_layout.setContentsMargins(0, 0, 0, 0)

        # Imagen del artista/álbum
        image_label = QLabel()
        image_label.setFixedSize(120, 120)
        image_label.setStyleSheet("""
            border: 2px solid #1e1e2e;
            border-radius: 8px;
            background-color: #414868;
        """)
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Cargar imagen
        self.load_image(image_label)
        info_horizontal_layout.addWidget(image_label)

        # Información textual a la derecha
        text_layout = QVBoxLayout()
        text_layout.setSpacing(8)
        text_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Título
        title_label = QLabel(self.track_info.get('title', 'Título desconocido'))
        title_label.setObjectName("title")
        title_label.setWordWrap(True)
        text_layout.addWidget(title_label)

        # Artista
        artist_label = QLabel(f"por {self.track_info.get('artist', 'Artista desconocido')}")
        artist_label.setObjectName("artist")
        artist_label.setWordWrap(True)
        text_layout.addWidget(artist_label)

        # Álbum si existe
        if self.track_info.get('album'):
            album_text = self.track_info['album']
            if self.album_info and self.album_info.get('year'):
                album_text += f" ({self.album_info['year']})"
            album_label = QLabel(f"de {album_text}")
            album_label.setObjectName("album")
            album_label.setWordWrap(True)
            text_layout.addWidget(album_label)

        # Carpeta actual
        folder_label = QLabel(f"Carpeta: {self.track_info.get('folder', 'Carpeta desconocida')}")
        folder_label.setStyleSheet("color: #7dcfff; font-size: 11px; margin-top: 5px; background-color: transparent;")
        text_layout.addWidget(folder_label)

        text_layout.addStretch()
        info_horizontal_layout.addLayout(text_layout)

        main_layout.addWidget(info_horizontal_widget)

        # 2. Widget medio: rutas completas de duplicados
        duplicates_widget = QDialog()
        duplicates_widget.setStyleSheet("background-color: #414868;")
        duplicates_layout = QVBoxLayout(duplicates_widget)
        duplicates_layout.setContentsMargins(0, 0, 0, 0)

        for dup in self.duplicates:
            dup_label = QLabel(f"Canción encontrada en: {dup}")
            dup_label.setObjectName("duplicate_path")
            dup_label.setWordWrap(True)
            duplicates_layout.addWidget(dup_label)

        main_layout.addWidget(duplicates_widget)

        # 3. Widget inferior: botones de acción
        buttons_widget = self.create_buttons_widget(is_duplicates=True)
        main_layout.addWidget(buttons_widget)

    def set_action(self, action):
        """Establecer acción y actualizar UI"""
        self.action = action
        # Ocultar duplicados y mostrar solo selección de carpetas
        self.duplicatesWidget.setVisible(False)
        self.copyButton.setVisible(False)
        self.moveButton.setVisible(False)
        self.newFolderButton.setVisible(True)

    def select_folder(self, folder):
        """Seleccionar carpeta y cerrar diálogo"""
        self.selected_folder = folder
        self.accept()

    def create_new_folder(self):
        """Crear nueva carpeta"""
        folder_name, ok = QInputDialog.getText(self, "Nueva carpeta", "Nombre de la nueva carpeta:")
        if ok and folder_name:
            # Crear la carpeta
            new_folder_path = os.path.join("/mnt/windows/Mix", folder_name)
            os.makedirs(new_folder_path, exist_ok=True)
            self.selected_folder = folder_name
            self.accept()

    def setup_ui(self):
        """Configurar UI principal del diálogo"""
        from PyQt6.QtGui import QShortcut

        self.setWindowTitle("Mover música - Tokyo Night")
        self.setModal(True)
        self.setMinimumWidth(700)
        self.setMinimumHeight(800)

        # Configurar hotkey ESC para cerrar
        esc_shortcut = QShortcut(QKeySequence("Escape"), self)
        esc_shortcut.activated.connect(self.reject)

        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)  # Reducido a la mitad
        main_layout.setContentsMargins(12, 12, 12, 12)  # Reducido a la mitad

        # Si hay duplicados, usar estructura específica
        if self.duplicates:
            self.setup_duplicates_ui(main_layout)
        else:
            # Sin duplicados, mostrar directamente las carpetas con info arriba
            # 1. Widget de información (imagen + texto)
            info_widget = self.create_info_widget()
            main_layout.addWidget(info_widget)

            # Mostrar selección de carpetas (sin label)
            self.show_folder_selection(main_layout)

        self.setLayout(main_layout)

    def clear_layout(self):
        """Limpiar completamente el layout"""
        while self.layout().count():
            child = self.layout().takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def show_folder_selection(self, layout):
        """Mostrar selección de carpetas sin label"""
        # Crear scroll area para las carpetas
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMaximumHeight(250)
        scroll_area.setMinimumHeight(200)

        scroll_widget = QDialog()
        scroll_widget.setStyleSheet("background-color: #414868;")
        scroll_layout = QGridLayout(scroll_widget)
        scroll_layout.setSpacing(8)

        row, col = 0, 0
        max_cols = 4  # Cambiado a 4 columnas

        for folder in self.folders:
            hotkey = folder[0].upper()  # Primera letra como hotkey
            btn = QPushButton(f"{folder} ({hotkey})")  # Todo en una línea sin iconos
            btn.clicked.connect(lambda checked, f=folder: self.select_folder(f))
            btn.setMinimumHeight(50)
            btn.setMinimumWidth(120)

            # Configurar hotkey
            btn.setShortcut(QKeySequence(hotkey))

            scroll_layout.addWidget(btn, row, col)

            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)

        # Botones de acción con margen reducido
        buttons_widget = self.create_buttons_widget(is_duplicates=False)
        layout.addWidget(buttons_widget)

    def select_folder(self, folder):
        self.selected_folder = folder
        self.accept()

    def create_new_folder(self):
        folder_name, ok = QInputDialog.getText(self, "Nueva carpeta", "Nombre de la nueva carpeta:")
        if ok and folder_name:
            # Crear la carpeta
            new_folder_path = os.path.join("/mnt/windows/Mix", folder_name)
            os.makedirs(new_folder_path, exist_ok=True)
            self.selected_folder = folder_name
            self.accept()




class CommentDialog(QDialog):
    def __init__(self, track_info, existing_comment="", parent=None):
        super().__init__(parent)
        self.track_info = track_info
        self.comment = ""
        self.setup_ui(existing_comment)
        self.setup_hotkeys()

    def setup_hotkeys(self):
        """Configurar hotkeys para el diálogo de comentarios"""
        from PyQt6.QtGui import QShortcut

        # ESC: Cerrar diálogo
        esc_shortcut = QShortcut(QKeySequence("Escape"), self)
        esc_shortcut.activated.connect(self.reject)

        # Enter: Aceptar
        enter_shortcut = QShortcut(QKeySequence("Return"), self)
        enter_shortcut.activated.connect(self.accept_comment)

    def setup_ui(self, existing_comment):
        self.setWindowTitle("Añadir comentario")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setMinimumHeight(200)

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)

        title_label = QLabel("Comentario para:")
        title_label.setStyleSheet("color: #c0caf5; font-size: 14px; background-color: transparent;")
        layout.addWidget(title_label)

        song_info = f"{self.track_info.get('artist', 'Artista desconocido')} - {self.track_info.get('title', 'Título desconocido')}"
        song_label = QLabel(song_info)
        song_label.setObjectName("title")
        layout.addWidget(song_label)

        self.comment_edit = QLineEdit()
        if existing_comment:
            self.comment_edit.setText(f"{existing_comment}, ")
        self.comment_edit.setPlaceholderText("Escribe un comentario...")
        self.comment_edit.setFocus()
        layout.addWidget(self.comment_edit)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        ok_btn = QPushButton("Aceptar")
        ok_btn.setObjectName("primary")
        ok_btn.clicked.connect(self.accept_comment)
        ok_btn.setDefault(True)
        button_layout.addWidget(ok_btn)

        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setObjectName("danger")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def accept_comment(self):
        self.comment = self.comment_edit.text()
        self.accept()


def show_notification(title, message, urgent=False):
    """Mostrar notificación del sistema"""
    try:
        urgency = "-u critical" if urgent else ""
        subprocess.run(f'notify-send {urgency} -t 3000 "{title}" "{message}"', shell=True)
    except:
        pass

def apply_tokyo_night_theme(app):
    """Aplicar tema Tokyo Night a toda la aplicación"""
    palette = app.palette()

    # Colores Tokyo Night - usando el fondo solicitado
    bg_primary = QColor("#181825")      # Fondo principal
    bg_secondary = QColor("#24283b")    # Fondo secundario
    bg_tertiary = QColor("#414868")     # Fondo terciario
    text_primary = QColor("#c0caf5")    # Texto principal
    text_secondary = QColor("#a9b1d6")  # Texto secundario
    accent = QColor("#7aa2f7")          # Acento azul
    danger = QColor("#f7768e")          # Rojo
    warning = QColor("#e0af68")         # Amarillo
    success = QColor("#9ece6a")         # Verde

    # Aplicar colores al palette
    palette.setColor(QPalette.ColorRole.Window, bg_primary)
    palette.setColor(QPalette.ColorRole.WindowText, text_primary)
    palette.setColor(QPalette.ColorRole.Base, bg_secondary)
    palette.setColor(QPalette.ColorRole.AlternateBase, bg_tertiary)
    palette.setColor(QPalette.ColorRole.Text, text_primary)
    palette.setColor(QPalette.ColorRole.Button, bg_primary)  # Cambiado a bg_primary
    palette.setColor(QPalette.ColorRole.ButtonText, text_primary)
    palette.setColor(QPalette.ColorRole.Highlight, accent)
    palette.setColor(QPalette.ColorRole.HighlightedText, bg_primary)

    app.setPalette(palette)

    # Stylesheet global mejorado con más especificidad
    app.setStyleSheet("""
        * {
            background-color: #414868;
            color: #c0caf5;
            border: none;
        }

        QApplication {
            background-color: #181825;
            color: #c0caf5;
            font-family: 'Segoe UI', 'Ubuntu', sans-serif;
        }

        QDialog {
            background-color: #181825;
            color: #c0caf5;
            border: none;
        }

        QWidget {
            background-color: #181825;
            color: #c0caf5;
            border: none;
        }

        QWidget[objectName="infoWidget"] {
            background-color: #414868;
            border: 2px solid #414868;
            border-radius: 8px;
        }

        QWidget[objectName="duplicatesWidget"] {
            background-color: #414868;
            border: 2px solid #414868;
            border-radius: 8px;
        }

        QWidget[objectName="buttonsWidget"] {
            background-color: #181825;
            border: none;
        }

        QLabel {
            color: #c0caf5;
            background-color: transparent;
            font-size: 12px;
            border: none;
        }

        QLabel#title {
            color: #7aa2f7;
            font-size: 16px;
            font-weight: bold;
            padding: 5px;
            background-color: transparent;
            border: none;
        }

        QLabel#artist {
            color: #bb9af7;
            font-size: 14px;
            font-weight: bold;
            background-color: transparent;
            border: none;
        }

        QLabel#album {
            color: #9ece6a;
            font-size: 12px;
            background-color: transparent;
            border: none;
        }

        QLabel#duplicate_path {
            color: #e0af68;
            font-size: 12px;
            font-weight: bold;
            background-color: transparent;
            padding: 8px;
            border: 1px solid #414868;
            border-radius: 6px;
            margin: 5px 0px;
        }

        QLabel[objectName="imageLabel"] {
            border: 2px solid #414868;
            border-radius: 8px;
            background-color: #414868;
            color: #565f89;
            font-size: 14px;
            font-weight: bold;
        }

        QLabel[objectName="folderLabel"] {
            color: #7dcfff;
            font-size: 11px;
            margin-top: 5px;
            background-color: transparent;
            border: none;
        }

        QPushButton {
            background-color: #414868;
            color: #c0caf5;
            border: 2px solid #565f89;
            border-radius: 8px;
            padding: 10px 20px;
            font-size: 12px;
            font-weight: 500;
            min-height: 20px;
        }

        QPushButton:hover {
            background-color: #565f89;
            border-color: #7aa2f7;
        }

        QPushButton:pressed {
            background-color: #3d59a1;
        }

        QPushButton#primary, QPushButton[objectName="newFolderButton"], QPushButton[objectName="copyButton"] {
            background-color: #7aa2f7;
            color: #181825;
            border: 2px solid #7aa2f7;
            font-weight: bold;
        }

        QPushButton#primary:hover, QPushButton[objectName="newFolderButton"]:hover, QPushButton[objectName="copyButton"]:hover {
            background-color: #89b4fa;
            border-color: #89b4fa;
        }

        QPushButton#danger, QPushButton[objectName="cancelButton"] {
            background-color: #f7768e;
            color: #181825;
            border: 2px solid #f7768e;
            font-weight: bold;
        }

        QPushButton#danger:hover, QPushButton[objectName="cancelButton"]:hover {
            background-color: #ff9fb1;
            border-color: #ff9fb1;
        }

        QPushButton#warning, QPushButton[objectName="moveButton"] {
            background-color: #e0af68;
            color: #181825;
            border: 2px solid #e0af68;
            font-weight: bold;
        }

        QPushButton#warning:hover, QPushButton[objectName="moveButton"]:hover {
            background-color: #f7c982;
            border-color: #f7c982;
        }

        QLineEdit {
            background-color: #414868;
            color: #c0caf5;
            border: 2px solid #414868;
            border-radius: 6px;
            padding: 10px;
            font-size: 12px;
            selection-background-color: #7aa2f7;
        }

        QLineEdit:focus {
            border-color: #7aa2f7;
        }

        QScrollArea {
            background-color: #181825;
            border: 2px solid #414868;
            border-radius: 8px;
        }

        QScrollArea > QWidget {
            background-color: #181825;
        }

        QScrollArea QWidget {
            background-color: #181825;
        }

        QScrollArea::corner {
            background-color: #181825;
        }

        QScrollBar:vertical {
            background-color: #181825;
            border: none;
            width: 12px;
        }

        QScrollBar::handle:vertical {
            background-color: #414868;
            border-radius: 6px;
            min-height: 20px;
        }

        QScrollBar::handle:vertical:hover {
            background-color: #565f89;
        }

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            border: none;
            background: none;
        }

        QMessageBox {
            background-color: #181825;
            color: #c0caf5;
            border: 2px solid #414868;
        }

        QMessageBox QLabel {
            color: #c0caf5;
            background-color: transparent;
            border: none;
        }

        QMessageBox QPushButton {
            background-color: #414868;
            color: #c0caf5;
            border: 2px solid #565f89;
            border-radius: 6px;
            padding: 8px 16px;
            min-width: 80px;
        }

        QMessageBox QPushButton:hover {
            background-color: #565f89;
            border-color: #7aa2f7;
        }

        QInputDialog {
            background-color: #181825;
            color: #c0caf5;
            border: none;
        }

        QInputDialog QLabel {
            background-color: transparent;
            color: #c0caf5;
            border: none;
        }

        QInputDialog QLineEdit {
            background-color: #414868;
            color: #c0caf5;
            border: 2px solid #414868;
            border-radius: 6px;
            padding: 8px;
        }

        QInputDialog QPushButton {
            background-color: #414868;
            color: #c0caf5;
            border: 2px solid #565f89;
            border-radius: 6px;
            padding: 8px 16px;
            min-width: 80px;
        }

        QInputDialog QPushButton:hover {
            background-color: #565f89;
            border-color: #7aa2f7;
        }
    """)

def main():


    app = QApplication(sys.argv)
    apply_tokyo_night_theme(app)

    try:
        mover = MusicMover()

        # Obtener información de la canción actual
        track_info = mover.get_current_track_info()

        # Buscar información en la base de datos
        artist_info, album_info = mover.get_database_info(
            track_info.get('artist', ''),
            track_info.get('title', ''),
            track_info.get('album', '')
        )

        # Buscar duplicados
        duplicates = mover.find_duplicates(
            track_info['song_name'],
            track_info.get('artist', ''),
            track_info.get('title', '')
        )

        # Obtener subcarpetas
        folders = mover.get_subfolders()

        if not folders:
            QMessageBox.critical(None, "Error", "No se encontraron subcarpetas en el directorio Mix")
            return

        # Mostrar diálogo de selección
        dialog = FolderSelectionDialog(folders, track_info, duplicates, artist_info, album_info)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            if not dialog.selected_folder:
                return

            # Solicitar comentario
            existing_comment = ""
            if duplicates and dialog.action in ['move', 'copy']:
                # Si hay duplicados y vamos a copiar/mover, obtener comentario existente
                existing_comment = mover.get_existing_comment(duplicates[0])

            comment_dialog = CommentDialog(track_info, existing_comment)

            if comment_dialog.exec() == QDialog.DialogCode.Accepted:
                comment = comment_dialog.comment

                try:
                    if duplicates and dialog.action == 'move':
                        # Mover archivo existente
                        new_file = mover.move_file(duplicates[0], dialog.selected_folder)
                        show_notification("Archivo movido", f"Movido a {dialog.selected_folder}")

                        # Actualizar comentario
                        mover.set_tags(new_file, comment, rename=False)

                    elif duplicates and dialog.action == 'copy':
                        # Copiar archivo original a nueva ubicación
                        new_file = mover.copy_file(track_info['path'], dialog.selected_folder)
                        show_notification("Archivo copiado", f"Copiado a {dialog.selected_folder}")

                        # Establecer tags
                        time.sleep(2)  # Esperar a que se complete la copia
                        new_file = mover.set_tags(new_file, comment, rename=True)

                        success = mover.add_to_lastfm_loved(track_info['artist'], track_info['title'])
                        if success:
                            show_notification("Last.fm", "Canción añadida a loved tracks")
                        else:
                            show_notification("Last.fm", "Error al añadir canción a loved tracks", urgent=True)

                    else:
                        # No hay duplicados, copiar normalmente
                        new_file = mover.copy_file(track_info['path'], dialog.selected_folder)
                        show_notification("Archivo copiado", f"Copiado a {dialog.selected_folder}")

                        # Establecer tags
                        time.sleep(2)  # Esperar a que se complete la copia
                        new_file = mover.set_tags(new_file, comment, rename=True)

                        success = mover.add_to_lastfm_loved(track_info['artist'], track_info['title'])
                        if success:
                            show_notification("Last.fm", "Canción añadida a loved tracks")
                        else:
                            show_notification("Last.fm", "Error al añadir canción a loved tracks", urgent=True)

                    # Actualizar playlists
                    mover.update_playlists()

                    # Llamar al script de Spotify si existe
                    try:
                        spotify_script = os.path.expanduser("~/Scripts/Musica/playlists/spotify/spotify_add_song.py")
                        if os.path.exists(spotify_script):
                            venv_activate = os.path.expanduser("~/Scripts/python_venv/bin/activate")
                            subprocess.run(f'source "{venv_activate}" && python "{spotify_script}"', shell=True)
                    except:
                        pass

                except Exception as e:
                    QMessageBox.critical(None, "Error", f"Error procesando archivo: {e}")
            else:
                show_notification("Cancelado", "Operación cancelada", urgent=True)
        else:
            show_notification("Cancelado", "Operación cancelada", urgent=True)

    except Exception as e:
        QMessageBox.critical(None, "Error", str(e))

    sys.exit()


if __name__ == "__main__":
    main()
