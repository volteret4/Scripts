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
import html
import email.header
import urllib.parse

from PyQt6.QtWidgets import (QWidget, QApplication, QDialog, QVBoxLayout, QHBoxLayout,
                            QLineEdit, QLabel, QPushButton, QMessageBox,
                            QInputDialog, QGridLayout, QScrollArea, QCheckBox, QSizePolicy)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeySequence, QPixmap, QPalette, QColor

# Configuración de Airsonic Advanced
load_dotenv()
AIRSONIC_URL = os.getenv("AIRSONIC_URL")  # CAMBIAR POR TU URL
AIRSONIC_USERNAME = os.getenv("AIRSONIC_USERNAME")          # CAMBIAR POR TU USUARIO
AIRSONIC_PASSWORD = os.getenv("AIRSONIC_PASSWORD")         # CAMBIAR POR TU PASSWORD
AIRSONIC_CLIENT = "mover_mix_script"

# Activar solo con yt_sync_mixxx.py actualizado en pepecono: la versión anterior
# no conoce #AGREGADA y subiría estas listas a YouTube en su pasada nocturna
AGREGADAS_ACTIVAS = False

# Playlists y cajones que juntan varias carpetas de Mix, con sus subcarpetas
PLAYLISTS_AGREGADAS = {
    "ELECTRONICA": ["Techno", "6_house", "idm", "N_DnB", "breaks", "dance", "Electro",
                    "uk garage", "big beat", "keet", "udub",
                    "Pop/pop_synthpop", "Pop/pop_dance"],
}


def copy_sin_permisos(src, dst):
    """Copiar contenido y fechas, sin permisos: exFAT no admite chmod con bits
    como setgid (p.ej. archivos del NFS) y copy2 falla con EPERM."""
    shutil.copyfile(src, dst)
    st = os.stat(src)
    os.utime(dst, ns=(st.st_atime_ns, st.st_mtime_ns))
    return dst


def caratula_pista(path):
    """Ruta de la miniatura de la carátula de una pista (embebida o de su carpeta), o None."""
    if not path:
        return None
    script = os.path.expanduser("~/Scripts/Musica/deadbeef/caratula_pista.sh")
    try:
        r = subprocess.run(['bash', script, path], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"Error buscando carátula: {e}")
        return None
    return r.stdout.strip() or None


def etiquetar_en_segundo_plano(path):
    """BPM y ReplayGain con etiquetar_mix.sh, sin esperar: analizar el audio tarda."""
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "etiquetar_mix.sh")
    log_path = os.path.expanduser("~/.local/state/etiquetador/etiquetar.log")
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, 'a') as log:
            subprocess.Popen(['bash', script, path], stdout=log, stderr=log,
                             stdin=subprocess.DEVNULL, start_new_session=True)
    except OSError as e:
        print(f"Error lanzando el etiquetador: {e}")


def nombre_mix(artist, title, album="", date="", label=""):
    """Nombre de archivo en Mix (sin extensión): «Artista - Título (año álbum) [sello]».
    None si falta artista o título."""
    artist, title = (artist or "").strip(), (title or "").strip()
    if not artist or not title:
        return None
    name = f"{artist} - {title}"
    date_album = " ".join(p for p in ((date or "").strip(), (album or "").strip()) if p)
    if date_album:
        name += f" ({date_album})"
    label = (label or "").strip()
    if label and label.lower() not in ("[no label]", "no label", "not on label"):
        name += f" [{label}]"
    # Caracteres problemáticos y espacios repetidos
    name = re.sub(r'[/\\?%*:|"<>]', '-', name)
    return re.sub(r'\s+', ' ', name).strip()


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
        """Obtener parámetros de autenticación para la API (contraseña en texto plano)"""
        return {
            'u': self.username,
            'p': self.password,
            'v': self.api_version,
            'c': self.client_name,
            'f': 'json'
        }

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
                # Prioridad: filename* (RFC 5987) > filename (RFC 2047 o literal)
                m_star = re.search(r"filename\*=UTF-8''([^;]+)", cd, re.IGNORECASE)
                m_plain = re.search(r'filename="?([^";]+)"?', cd)
                if m_star:
                    filename = urllib.parse.unquote(m_star.group(1).strip())
                elif m_plain:
                    raw = m_plain.group(1).strip()
                    # Decodificar RFC 2047 (=?UTF-8?Q?...?=)
                    parts = email.header.decode_header(raw)
                    filename = ''.join(
                        p.decode(enc or 'utf-8') if isinstance(p, bytes) else p
                        for p, enc in parts
                    )
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
        self.db_path = self._newest_mfuzz_db()
        self.temp_download_path = "/tmp/airsonic_downloads"  # Carpeta temporal para descargas

        # Crear carpeta temporal si no existe
        os.makedirs(self.temp_download_path, exist_ok=True)

        # Inicializar cliente Airsonic
        self.airsonic = AirsonicClient(AIRSONIC_URL, AIRSONIC_USERNAME, AIRSONIC_PASSWORD)

    # Instantánea que Syncthing trae de pepecono: la db instalada (MFUZZ_DB) solo
    # se renueva con «actualizar_db.py traer» con la app cerrada, así que suele
    # ser más vieja. Se lee la más reciente de las dos, en solo lectura.
    MFUZZ_SNAPSHOT = os.path.expanduser("~/gits/pollo/music-fuzzy/db/sqlite/sync/musica_local.sqlite")

    @classmethod
    def _newest_mfuzz_db(cls):
        candidates = [p for p in (os.environ.get('MFUZZ_DB'), cls.MFUZZ_SNAPSHOT) if p and os.path.exists(p)]
        return max(candidates, key=os.path.getmtime) if candidates else None

    def _connect_db(self):
        return sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)

    @staticmethod
    def _album_artist_name(artist):
        """Igual que db_musica_path: así se guarda el artista del álbum en la db."""
        return (artist or '').split('feat.')[0].split('with')[0].split('&')[0].strip()

    def find_album_row(self, track_info):
        """Fila de albums del disco que suena, o None.

        Primero por la ruta del archivo (songs.file_path → su álbum y artista),
        que no confunde discos homónimos; si no está (p. ej. ya en Mix), por
        nombre exacto de artista y álbum."""
        if not self.db_path:
            return None
        try:
            conn = self._connect_db()
            conn.row_factory = sqlite3.Row
            columns = {r[1] for r in conn.execute("PRAGMA table_info(albums)")}
            path = track_info.get('path') or ''
            candidates = []
            if path:
                song = conn.execute("SELECT album, artist, album_artist FROM songs WHERE file_path = ?",
                                    (path,)).fetchone()
                if song:
                    candidates = [(self._album_artist_name(song['album_artist']), song['album']),
                                  (self._album_artist_name(song['artist']), song['album'])]
            if track_info.get('album'):
                candidates.append((self._album_artist_name(track_info.get('artist', '')), track_info['album']))
            row = None
            for artist, album in candidates:
                if not artist or not album:
                    continue
                row = conn.execute("""
                    SELECT al.* FROM albums al JOIN artists ar ON ar.id = al.artist_id
                    WHERE lower(ar.name) = lower(?) AND lower(al.name) = lower(?)
                    ORDER BY al.origen = 'local' DESC LIMIT 1
                """, (artist, album)).fetchone()
                if row:
                    break
            conn.close()
            return {k: row[k] for k in columns} if row else None
        except sqlite3.Error as e:
            print(f"Error buscando el álbum en la db: {e}")
            return None

    @staticmethod
    def album_genres(album_row):
        """[(fuente, 'género, género'), ...] de lo que la db tenga del álbum."""
        if not album_row:
            return []
        discogs = ", ".join(x for x in (album_row.get('discogs_genres'), album_row.get('discogs_styles')) if x)
        sources = [("Etiquetas", album_row.get('genre')), ("Discogs", discogs),
                   ("MusicBrainz", album_row.get('mb_genres')), ("Last.fm", album_row.get('lastfm_tags'))]
        return [(name, value) for name, value in sources
                if value and value.strip().lower() not in ('unknown', 'none', 'other')]

    # Roles de Discogs agrupados para el diálogo, en este orden
    CREDIT_GROUPS = [
        ("Producción", ("produc",), ("co-produc", "executive")),
        ("Mezcla", ("mixed by", "mix"), ("remix",)),
        ("Masterización", ("master",), ()),
        ("Ingeniería", ("engineer", "recorded"), ("master", "mix")),
        ("Composición", ("written", "composed", "music by", "lyrics"), ()),
        ("Arreglos", ("arranged",), ()),
    ]

    @classmethod
    def album_credits(cls, album_row):
        """[(grupo, 'nombre, nombre'), ...] de los créditos de Discogs del álbum."""
        if not album_row:
            return []
        try:
            credits = json.loads(album_row.get('credits') or '{}')
        except ValueError:
            credits = {}
        if not isinstance(credits, dict):
            credits = {}
        result = []
        for label, include, exclude in cls.CREDIT_GROUPS:
            names = []
            for role, people in credits.items():
                role = role.lower()
                if any(i in role for i in include) and not any(e in role for e in exclude):
                    names += [re.sub(r'\s*\(\d+\)$', '', n) for n in people if isinstance(n, str)]
            names = list(dict.fromkeys(names))
            if names:
                result.append((label, ", ".join(names[:5]) + (f" (+{len(names) - 5})" if len(names) > 5 else "")))
        # Sin créditos detallados: las columnas resumidas
        if not result:
            for label, column in (("Producción", 'producers'), ("Ingeniería", 'engineers'),
                                  ("Masterización", 'mastering_engineers')):
                if album_row.get(column):
                    result.append((label, re.sub(r'\s*\(\d+\)', '', album_row[column])))
        return result

    def get_database_info(self, artist_name, title, album_name=""):
        """Obtener información del artista y álbum desde la base de datos"""
        if not self.db_path or not os.path.exists(self.db_path):
            return None, None

        try:
            conn = self._connect_db()
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

    def set_lastfm_obsession(self, artist, title):
        """Marcar la canción como «current obsession» en Last.fm.

        No hay API para esto: inicia sesión en la web con LASTFM_USERNAME/PASSWORD,
        envía el formulario «Set as current obsession» de la página de la canción y,
        si Last.fm responde con el modal de confirmación, envía también ese formulario.
        """
        import lxml.html
        load_dotenv()
        user = os.getenv("LASTFM_USERNAME")
        password = os.getenv("LASTFM_PASSWORD")
        if not (user and password):
            print("Faltan LASTFM_USERNAME/LASTFM_PASSWORD en el .env")
            return False

        base = "https://www.last.fm"
        s = requests.Session()
        s.headers["User-Agent"] = "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0"

        def call(method, url, **kw):
            # la web de Last.fm corta a veces la conexión: reintentar
            last = None
            headers = {"Connection": "close", **kw.pop("headers", {})}
            for _ in range(4):
                try:
                    return s.request(method, url, timeout=20, headers=headers, **kw)
                except requests.RequestException as e:
                    last = e
                    time.sleep(1.5)
            raise last

        def form_fields(form):
            data = {}
            for el in form.xpath(".//input[@name] | .//textarea[@name] | .//select[@name]"):
                if el.tag == "input" and el.get("type") in ("checkbox", "radio") and el.get("checked") is None:
                    continue
                data[el.get("name")] = el.value or ""
            return data

        try:
            call("GET", f"{base}/login")
            r = call("POST", f"{base}/login",
                     data={"csrfmiddlewaretoken": s.cookies.get("csrftoken", ""),
                           "username_or_email": user, "password": password},
                     headers={"Referer": f"{base}/login"})
            if "sessionid" not in s.cookies.get_dict():
                print("Last.fm: no se pudo iniciar sesión en la web")
                return False

            track_url = f"{base}/music/{urllib.parse.quote_plus(artist)}/_/{urllib.parse.quote_plus(title)}"
            page = lxml.html.fromstring(call("GET", track_url).text)
            forms = page.xpath('//form[contains(@action, "/obsessions")]')
            if not forms:
                print(f"Last.fm: la página de la canción no tiene «Set as current obsession» ({track_url})")
                return False
            action = urllib.parse.urljoin(base, forms[0].get("action"))
            r = call("POST", action, data=form_fields(forms[0]),
                     headers={"Referer": track_url, "X-Requested-With": "XMLHttpRequest"})
            if r.status_code >= 400:
                print(f"Last.fm: error {r.status_code} al marcar obsesión")
                return False

            # data-submit-to-modal: puede devolver un modal con un segundo formulario (motivo opcional)
            if "<form" in r.text:
                modal = lxml.html.fromstring(r.text)
                confirm = modal.xpath('//form[contains(@action, "/obsessions")]')
                if confirm:
                    action2 = urllib.parse.urljoin(base, confirm[0].get("action"))
                    r = call("POST", action2, data=form_fields(confirm[0]),
                             headers={"Referer": track_url, "X-Requested-With": "XMLHttpRequest"})
                    if r.status_code >= 400:
                        print(f"Last.fm: error {r.status_code} al confirmar la obsesión")
                        return False
            print(f"Obsesión en Last.fm: {artist} - {title}")
            return True
        except Exception as e:
            print(f"Error marcando obsesión en Last.fm: {e}")
            return False

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
                        # Sin descarga: pepecono (mover_mix) la busca en Navidrome por artista/título
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
                    path = urllib.parse.unquote(url.replace('file://', ''))
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

                    tracknumber = subprocess.run(
                        ['playerctl', 'metadata', 'xesam:trackNumber'],
                        capture_output=True, text=True
                    ).stdout.strip()

                    # mpris:length viene en microsegundos
                    length = subprocess.run(
                        ['playerctl', 'metadata', 'mpris:length'],
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
                        'tracknumber': tracknumber,
                        'length': int(length) / 1e6 if length.isdigit() else None,
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

                    tracknumber = subprocess.run(
                        ['deadbeef', '--nowplaying-tf', '%tracknumber%'],
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
                        'tracknumber': tracknumber,
                        'length': None,
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

    def get_folder_tree(self):
        """Árbol de un nivel de las carpetas de Mix: {carpeta: subcarpetas o None}.

        Una carpeta se considera "supergénero" (p.ej. TECHNO, HOUSE) cuando
        contiene a su vez subcarpetas (los subgéneros, tipo "techno_trance");
        esto se detecta por estructura, no por nombre, así que cualquier
        carpeta futura que se organice igual se reconoce sin tocar el script.
        """
        tree = {}
        try:
            # Alfabético sin distinguir mayúsculas: si no, "Techno" va antes que "breaks"
            for item in sorted(os.listdir(self.mixxx_path), key=str.casefold):
                if item.startswith('.'):
                    continue
                item_path = os.path.join(self.mixxx_path, item)
                if not os.path.isdir(item_path):
                    continue
                children = sorted(
                    (d for d in os.listdir(item_path)
                     if os.path.isdir(os.path.join(item_path, d)) and not d.startswith('.')),
                    key=str.casefold
                )
                tree[item] = children or None
        except Exception as e:
            print(f"Error obteniendo árbol de carpetas: {e}")
        return tree

    def get_subfolders(self):
        """Obtener carpetas de nivel superior del directorio Mix"""
        return list(self.get_folder_tree().keys())

    # --- Qué hay ya en Mix del artista y del sello ---

    AUDIO_EXTS = ('.mp3', '.flac', '.m4a', '.wav', '.aiff', '.aif', '.ogg', '.opus')
    INDEX_CACHE = os.path.expanduser("~/.cache/mover_mix/indice.json")

    @staticmethod
    def _read_artist_label(path):
        """(artista, sello) de las etiquetas de un archivo; cadenas vacías si no hay."""
        try:
            import mutagen
            audio = mutagen.File(path, easy=True)
        except Exception:
            return "", ""
        tags = (audio.tags if audio else None) or {}

        def first(*keys):
            for k in keys:
                try:
                    v = tags.get(k)
                except Exception:
                    v = None
                if v:
                    return str(v[0] if isinstance(v, list) else v).strip()
            return ""
        return first('artist', 'albumartist'), first('label', 'organization', 'publisher')

    def mix_index(self):
        """[(carpeta relativa a Mix, ruta, artista, sello)] de todo Mix.

        Las etiquetas se guardan en caché por fecha de modificación: solo se
        leen las de archivos nuevos o cambiados (leer todo Mix tarda unos 6 s).
        """
        try:
            with open(self.INDEX_CACHE) as f:
                cache = json.load(f)
        except (OSError, ValueError):
            cache = {}

        index, fresh = [], {}
        for root, dirs, files in os.walk(self.mixxx_path):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            rel = os.path.relpath(root, self.mixxx_path)
            for name in files:
                if os.path.splitext(name)[1].lower() not in self.AUDIO_EXTS:
                    continue
                path = os.path.join(root, name)
                try:
                    mtime = os.path.getmtime(path)
                except OSError:
                    continue
                cached = cache.get(path)
                if cached and cached[0] == mtime:
                    artist, label = cached[1], cached[2]
                else:
                    artist, label = self._read_artist_label(path)
                fresh[path] = [mtime, artist, label]
                index.append((rel, path, artist, label))

        try:
            os.makedirs(os.path.dirname(self.INDEX_CACHE), exist_ok=True)
            with open(self.INDEX_CACHE, 'w') as f:
                json.dump(fresh, f)
        except OSError:
            pass
        return index

    @staticmethod
    def _artist_names(artist):
        """Nombres de un crédito: 'Joe Goddard (feat. Alexis Taylor)' -> {'joe goddard', 'alexis taylor'}."""
        artist = re.sub(r'[()\[\]]', ' ', artist or '')
        parts = re.split(r'\s*(?:,|;|/|&|\bfeat\.?|\bft\.?|\bfeaturing\b|\bvs\.?|\bx\b)\s*', artist, flags=re.I)
        return {p.strip().casefold() for p in parts if p.strip()}

    def mix_stats(self, artist, label, exclude_path=None):
        """Canciones ya en Mix del artista y del sello, por carpeta.

        {'artist': [(carpeta, n), ...], 'label': [...]} con las carpetas
        ordenadas de más a menos canciones."""
        from collections import Counter
        wanted_artists = self._artist_names(artist)
        wanted_label = (label or '').strip().casefold()
        if wanted_label in ('[no label]', 'no label', 'not on label'):
            wanted_label = ''

        by_artist, by_label = Counter(), Counter()
        exclude = os.path.normcase(os.path.normpath(exclude_path)) if exclude_path else None
        for rel, path, file_artist, file_label in self.mix_index():
            if exclude and os.path.normcase(os.path.normpath(path)) == exclude:
                continue
            if wanted_artists and wanted_artists & self._artist_names(file_artist):
                by_artist[rel] += 1
            if wanted_label and file_label.strip().casefold() == wanted_label:
                by_label[rel] += 1
        return {'artist': by_artist.most_common(), 'label': by_label.most_common()}

    def count_songs(self, folder, recursive=False):
        """Número de canciones en una carpeta de Mix."""
        path = os.path.join(self.mixxx_path, folder)
        if recursive:
            return sum(1 for _, _, files in os.walk(path) for f in files
                       if os.path.splitext(f)[1].lower() in self.AUDIO_EXTS)
        try:
            return sum(1 for f in os.listdir(path)
                       if os.path.splitext(f)[1].lower() in self.AUDIO_EXTS
                       and os.path.isfile(os.path.join(path, f)))
        except OSError:
            return 0

    def folder_summary(self, folder):
        """'pop_synthpop (32), Pop (145)': la carpeta destino y, si es un
        subgénero, el total del supergénero (con todos sus subgéneros)."""
        folder = os.path.normpath(folder)
        parts = folder.split(os.sep)
        summary = [f"{parts[-1]} ({self.count_songs(folder)})"]
        if len(parts) > 1:
            summary.append(f"{parts[0]} ({self.count_songs(parts[0], recursive=True)})")
        elif os.path.isdir(os.path.join(self.mixxx_path, folder)) and any(
                os.path.isdir(os.path.join(self.mixxx_path, folder, d))
                for d in os.listdir(os.path.join(self.mixxx_path, folder))):
            # Supergénero: 'Techno (2 sueltas, 324 con subgéneros)'
            summary = [f"{parts[-1]} ({self.count_songs(folder)} sueltas, "
                       f"{self.count_songs(folder, recursive=True)} con subgéneros)"]
        return ", ".join(summary)

    # --- Discos con cue (embebido en el tag CUESHEET o .cue al lado) ---

    LOSSLESS_EXTS = ('.flac', '.wav', '.ape', '.wv', '.tta', '.aiff', '.aif')

    def _read_cuesheet(self, path):
        """Devolver (texto_cue, embebido) del archivo de audio, o (None, False).

        Primero mira el tag CUESHEET embebido; si no hay, busca un .cue en la
        misma carpeta (mismo nombre, nombre.ext.cue o cualquiera cuyo FILE
        apunte a este archivo).
        """
        try:
            result = subprocess.run(
                ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', path],
                capture_output=True, text=True
            )
            tags = json.loads(result.stdout or '{}').get('format', {}).get('tags', {})
            for key, value in tags.items():
                if key.lower() == 'cuesheet' and 'TRACK' in value:
                    return value, True
        except Exception as e:
            print(f"Error leyendo CUESHEET embebido: {e}")

        folder = os.path.dirname(path)
        base = os.path.basename(path)
        stem = os.path.splitext(base)[0]
        try:
            cue_files = [f for f in os.listdir(folder) if f.lower().endswith('.cue')]
        except OSError:
            return None, False
        preferred = [f for f in cue_files if os.path.splitext(f)[0] in (stem, base)]
        for cue_name in preferred + [f for f in cue_files if f not in preferred]:
            text = None
            raw = open(os.path.join(folder, cue_name), 'rb').read()
            for enc in ('utf-8-sig', 'cp1252', 'latin-1'):
                try:
                    text = raw.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            if not text:
                continue
            if cue_name in preferred:
                return text, False
            # Un .cue con otro nombre solo vale si su FILE apunta a este archivo
            for m in re.finditer(r'^\s*FILE\s+"?(.+?)"?\s+\w+\s*$', text, re.M):
                if os.path.splitext(os.path.basename(m.group(1)))[0] == stem:
                    return text, False
        return None, False

    @staticmethod
    def _cue_time(value):
        """MM:SS:FF (75 frames por segundo) -> segundos"""
        m, s, f = (int(x) for x in value.split(':'))
        return m * 60 + s + f / 75

    def _parse_cue(self, text, audio_path, embedded):
        """Parsear un cuesheet. Devuelve (info_disco, [pistas]).

        Cada pista: number, title, performer, start, end (None = hasta el
        final), gain, peak. Si el cue tiene varios FILE, solo se quedan las
        pistas del FILE que corresponde a audio_path.
        """
        disc = {}
        tracks = []
        files = []
        current = None
        stem = os.path.splitext(os.path.basename(audio_path))[0]

        def unq(v):
            return v.strip().strip('"')

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            word, _, rest = line.partition(' ')
            word = word.upper()
            if word == 'FILE':
                m = re.match(r'"?(.+?)"?\s+\w+$', rest)
                files.append(os.path.splitext(os.path.basename(m.group(1) if m else rest))[0])
                current = None
            elif word == 'TRACK':
                current = {'number': int(rest.split()[0]), 'file_idx': len(files) - 1}
                tracks.append(current)
            elif word in ('TITLE', 'PERFORMER'):
                (current if current is not None else disc)[word.lower()] = unq(rest)
            elif word == 'INDEX' and current is not None:
                idx, _, t = rest.partition(' ')
                current['index' + idx.strip()[-1]] = self._cue_time(t.strip())
            elif word == 'REM':
                key, _, val = rest.partition(' ')
                key = key.upper()
                if current is None and key in ('DATE', 'GENRE'):
                    disc[key.lower()] = unq(val)
                elif current is not None and key == 'REPLAYGAIN_TRACK_GAIN':
                    current['gain'] = unq(val)
                elif current is not None and key == 'REPLAYGAIN_TRACK_PEAK':
                    current['peak'] = unq(val)

        if len(set(files)) > 1 and not embedded:
            idx = [i for i, f in enumerate(files) if f == stem]
            if not idx:
                return disc, []
            tracks = [t for t in tracks if t['file_idx'] in idx]

        tracks = [t for t in tracks if 'index1' in t]
        for i, t in enumerate(tracks):
            t['start'] = t['index1']
            if i + 1 < len(tracks):
                nxt = tracks[i + 1]
                t['end'] = nxt.get('index0', nxt['index1'])
            else:
                t['end'] = None
        return disc, tracks

    def resolve_cue_track(self, track_info):
        """Si la canción sale de un disco con cue, identificar qué pista es.

        Añade track_info['cue'] con la pista elegida (y corrige artista/título
        con los del cue). Se identifica por título, luego número de pista,
        luego duración; si nada encaja se pregunta.
        """
        path = track_info.get('path') or ''
        if not path or not os.path.isfile(path):
            return track_info

        text, embedded = self._read_cuesheet(path)
        if not text:
            return track_info
        disc, tracks = self._parse_cue(text, path, embedded)
        if len(tracks) < 2:
            return track_info

        print(f"Detectado disco con cue ({'embebido' if embedded else 'archivo .cue'}): {len(tracks)} pistas")

        def norm(s):
            return re.sub(r'\W+', '', (s or '').lower())

        chosen = None
        title = norm(track_info.get('title'))
        if title:
            matches = [t for t in tracks if norm(t.get('title')) == title]
            if len(matches) == 1:
                chosen = matches[0]

        if not chosen:
            num = (track_info.get('tracknumber') or '').split('/')[0].strip()
            if num.isdigit():
                chosen = next((t for t in tracks if t['number'] == int(num)), None)

        if not chosen and track_info.get('length'):
            total = None
            try:
                total = float(subprocess.run(
                    ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                     '-of', 'default=nw=1:nk=1', path],
                    capture_output=True, text=True
                ).stdout.strip())
            except ValueError:
                pass
            length = track_info['length']
            # Si el reproductor da la duración del disco entero no sirve para elegir
            if not total or length < total - 2:
                matches = [t for t in tracks
                           if t['end'] is not None and abs((t['end'] - t['start']) - length) < 1.5
                           or t['end'] is None and total and abs((total - t['start']) - length) < 1.5]
                if len(matches) == 1:
                    chosen = matches[0]

        if not chosen:
            def fmt(t):
                dur = f" ({int((t['end'] - t['start']) // 60)}:{int((t['end'] - t['start']) % 60):02d})" if t['end'] else ""
                return f"{t['number']:02d}. {t.get('title', '')}{dur}"
            whole = "— Copiar el disco entero —"
            items = [fmt(t) for t in tracks] + [whole]
            item, ok = QInputDialog.getItem(
                None, "Disco con cue",
                f"{os.path.basename(path)}\nno se pudo saber qué pista suena. Elige:",
                items, 0, False
            )
            if not ok:
                raise Exception("Operación cancelada")
            if item == whole:
                return track_info
            chosen = tracks[items.index(item)]

        artist = chosen.get('performer') or disc.get('performer') or track_info.get('artist', '')
        title = chosen.get('title') or track_info.get('title', '')
        album = disc.get('title') or track_info.get('album', '')
        print(f"Pista del cue: {chosen['number']:02d}. {artist} - {title}")

        track_info.update({
            'artist': artist,
            'title': title,
            'album': album,
            'song_name': f"{artist} - {title}",
            'filename': re.sub(r'[/\\?%*:|"<>]', '-', f"{artist} - {title}") + os.path.splitext(path)[1],
            'cue': dict(chosen, artist=artist, album=album,
                        date=disc.get('date', ''), genre=disc.get('genre', ''),
                        total_tracks=len(tracks)),
        })
        return track_info

    def extract_cue_track(self, source, cue, dest_path):
        """Cortar la pista del cue con ffmpeg y dejarla en dest_path"""
        ext = os.path.splitext(source)[1].lower()
        if ext in self.LOSSLESS_EXTS:
            out_ext, codec = '.flac', ['-c:a', 'flac']
        else:
            out_ext, codec = ext, ['-c:a', 'copy']

        name = re.sub(r'[/\\?%*:|"<>]', '-', f"{cue['artist']} - {cue['title']}") + out_ext
        dest_file = os.path.join(dest_path, name)

        cmd = ['ffmpeg', '-y', '-v', 'error', '-ss', f"{cue['start']:.3f}", '-i', source]
        if cue['end'] is not None:
            cmd += ['-t', f"{cue['end'] - cue['start']:.3f}"]
        cmd += ['-map', '0:a:0', *codec, '-map_metadata', '0']
        # Un valor vacío borra el tag: fuera el cue y lo que era del disco entero
        metadata = {
            'CUESHEET': '', 'BPM': '', 'INITIALKEY': '',
            'TITLE': cue['title'], 'ARTIST': cue['artist'], 'ALBUM': cue['album'],
            'TRACKNUMBER': f"{cue['number']}/{cue['total_tracks']}",
            'REPLAYGAIN_TRACK_GAIN': cue.get('gain', ''),
            'REPLAYGAIN_TRACK_PEAK': cue.get('peak', ''),
        }
        if cue.get('date'):
            metadata['DATE'] = cue['date']
        if cue.get('genre'):
            metadata['GENRE'] = cue['genre']
        for key, value in metadata.items():
            cmd += ['-metadata', f"{key}={value}"]
        cmd.append(dest_file)

        print(f"Cortando pista {cue['number']} del cue: {source} -> {dest_file}")
        subprocess.run(cmd, check=True)
        return dest_file

    def copy_file(self, source, destination_folder, cue=None):
        """Copiar archivo al destino (o solo la pista, si viene de un cue)"""
        dest_path = os.path.join(self.mixxx_path, destination_folder)
        if not os.path.exists(dest_path):
            os.makedirs(dest_path)

        if cue:
            dest_file = self.extract_cue_track(source, cue, dest_path)
        else:
            dest_file = os.path.join(dest_path, os.path.basename(source))
            copy_sin_permisos(source, dest_file)

        # Analizar y convertir si es necesario
        dest_file = self.analyze_and_convert_flac(dest_file)

        self.add_caratula(dest_file)
        self.fecha_original(dest_file)

        return dest_file

    def fecha_original(self, dest_file):
        """Poner en DATE la fecha de lanzamiento original (no la del remaster o recopilatorio), con
        fecha_original_mix.py: así set_tags ya renombra con ella y no hay que corregirla luego en lote.
        Solo el archivo: Mixxx aún no lo tiene en su base de datos."""
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fecha_original_mix.py")
        try:
            r = subprocess.run([sys.executable, script_path, "--apply", "--solo-archivo", "--quiet", dest_file],
                               capture_output=True, text=True, timeout=120)
            print(r.stdout.strip() or r.stderr.strip())
        except (OSError, subprocess.TimeoutExpired) as e:
            print(f"Fecha original: {e}")
        return dest_file

    def add_caratula(self, dest_file):
        """Añadir carátula al destino"""
        script_path = os.path.expanduser("~/Scripts/Musica/playlists/mixxx/embeed_cover.py")
        subprocess.run([sys.executable, script_path, dest_file], check=True)
        print(f"Añadida carátula a {dest_file}")

        return dest_file



    def move_file(self, source, destination_folder):
        """Mover archivo al destino"""
        dest_path = os.path.join(self.mixxx_path, destination_folder)
        if not os.path.exists(dest_path):
            os.makedirs(dest_path)

        dest_file = os.path.join(dest_path, os.path.basename(source))
        shutil.move(source, dest_file, copy_function=copy_sin_permisos)
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
                # Claves en minúsculas: hay archivos con 'Artist', 'Title'... y no se encontraban
                tags = {k.lower(): v for k, v in metadata.get('format', {}).get('tags', {}).items()}
                artist = tags.get('artist') or tags.get('album_artist') or tags.get('album artist', '')
                title = tags.get('title', '')
                album = tags.get('album', '')
                date = tags.get('date') or tags.get('year', '')
                label = tags.get('label') or tags.get('publisher') or tags.get('organization', '')

                # Si se especifica un comentario, añadirlo usando ffmpeg
                if comment:
                    # Crear archivo temporal
                    temp_file = f"{file_path}.temp{file_ext}"

                    # Añadir comentario con ffmpeg
                    subprocess.run([
                        'ffmpeg', '-y', '-i', file_path, '-map_metadata', '0',
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
                new_filename = nombre_mix(artist, title, album, date, label)
                if not new_filename:
                    # Sin artista o sin título: mejor el nombre original que " - Título" o "Artista - "
                    print(f"Sin artista/título en los tags, no se renombra: {file_path}")
                    return file_path

                new_file_path = os.path.join(dir_path, new_filename + file_ext)
                if new_file_path == file_path:
                    return file_path

                print(f"Renombrando: {file_path} -> {new_file_path}")
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

    def _write_playlist(self, name, folder_path, recursive=True):
        """Escribir un .m3u con las canciones de folder_path.

        recursive=True (por defecto): recorre subcarpetas también (así
        funcionan hoy las playlists de subgénero, que son carpetas planas).
        recursive=False: solo los ficheros que cuelgan directamente de
        folder_path, ignorando cualquier subcarpeta -- para la playlist de un
        supergénero (TECHNO), que no debe incluir lo que ya vive en sus
        subgéneros (techno_acid, techno_dub...), cada uno con su propia
        playlist aparte.
        """
        playlist_file = os.path.join(self.mixxx_path, f"{name}.m3u")
        with open(playlist_file, 'w') as f:
            if recursive:
                walker = os.walk(folder_path)
            else:
                try:
                    entries = sorted(os.listdir(folder_path))
                except OSError:
                    entries = []
                files_only = [e for e in entries if os.path.isfile(os.path.join(folder_path, e))]
                walker = [(folder_path, [], files_only)]
            for root, dirs, files in walker:
                for file in sorted(files):
                    # Los ocultos pueden ser temporales del etiquetador (.etiquetador-*.flac)
                    if not file.startswith('.') and file.lower().endswith(('.mp3', '.flac', '.ogg', '.wav', '.m4a')):
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, self.mixxx_path)
                        f.write(f"{rel_path}\n")

    def _write_aggregate(self, name, folders):
        """Escribir un .m3u que junta varias carpetas de Mix con todo lo que tienen dentro.

        La marca #AGREGADA de la primera línea la usa yt_sync_mixxx.py para no
        subirla a YouTube; los demás lectores de .m3u ignoran los comentarios.
        """
        tracks = set()
        for folder in folders:
            folder_path = os.path.join(self.mixxx_path, folder)
            if not os.path.isdir(folder_path):
                print(f"Playlist {name}: no existe la carpeta {folder}")
                continue
            for root, _dirs, files in os.walk(folder_path):
                tracks.update(
                    os.path.relpath(os.path.join(root, file), self.mixxx_path)
                    for file in files
                    if not file.startswith('.') and file.lower().endswith(('.mp3', '.flac', '.ogg', '.wav', '.m4a'))
                )
        with open(os.path.join(self.mixxx_path, f"{name}.m3u"), 'w') as f:
            f.write("#AGREGADA\n")
            f.writelines(f"{track}\n" for track in sorted(tracks))

    def update_playlists(self):
        """Actualizar playlists de Mixxx.

        Para una carpeta plana (sin subcarpetas) se crea una única playlist,
        como siempre. Para un supergénero (con subcarpetas de subgénero) se
        crea la playlist del supergénero con solo lo que cuelga directamente
        de él (sin bajar a los subgéneros) y, además, una playlist por cada
        subgénero -- cada canción cae en una sola playlist de "género", nunca
        en dos a la vez.

        Aparte están las agregadas, donde una canción sí se repite: <supergénero>_todo
        con el supergénero entero y las de PLAYLISTS_AGREGADAS.
        """
        try:
            # Eliminar playlists existentes
            for m3u_file in Path(self.mixxx_path).glob("*.m3u"):
                m3u_file.unlink()

            for top, children in self.get_folder_tree().items():
                top_path = os.path.join(self.mixxx_path, top)
                self._write_playlist(top, top_path, recursive=not children)
                if children:
                    for child in children:
                        self._write_playlist(child, os.path.join(top_path, child))
                    if AGREGADAS_ACTIVAS:
                        self._write_aggregate(f"{top}_todo", [top])

            if AGREGADAS_ACTIVAS:
                for name, folders in PLAYLISTS_AGREGADAS.items():
                    self._write_aggregate(name, folders)

        except Exception as e:
            print(f"Error actualizando playlists: {e}")

    def analyze_and_convert_flac(self, file_path):
        """Analiza un archivo FLAC y lo convierte a 16 bits / 44100 Hz si excede esos valores"""
        if not file_path.lower().endswith(".flac"):
            return file_path  # solo flac

        try:
            # Obtener info con ffprobe
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "a:0",
                 "-show_entries", "stream=bit_rate,sample_rate,bits_per_sample",
                 "-of", "json", file_path],
                capture_output=True, text=True, check=True
            )
            data = json.loads(result.stdout)
            stream = data.get("streams", [{}])[0]
            sample_rate = int(stream.get("sample_rate", 0))
            bits_per_sample = int(stream.get("bits_per_sample", 0))

            print(f"[DEBUG] Análisis: {bits_per_sample} bits, {sample_rate} Hz")

            if bits_per_sample > 16 or sample_rate > 44100:
                print(f"[DEBUG] Convirtiendo {file_path} a 16 bits / 44100 Hz")

                # Archivo temporal
                tmp_file = f"{file_path}.tmp.flac"

                subprocess.run([
                    "ffmpeg", "-y", "-i", file_path,
                    "-ar", "44100", "-sample_fmt", "s16",
                    tmp_file
                ], check=True)

                # Reemplazar el original
                os.replace(tmp_file, file_path)
                print(f"[DEBUG] Archivo convertido correctamente.")
            else:
                print(f"[DEBUG] No requiere conversión.")

        except Exception as e:
            print(f"[DEBUG] Error analizando/convirtiendo {file_path}: {e}")

        return file_path





class FolderSelectionDialog(QDialog):
    def __init__(self, folders, track_info, duplicates=None, artist_info=None, album_info=None,
                 folder_tree=None, force_supergenre=None, reclassify=False,
                 mixxx_path="/mnt/windows/Mix", mix_stats=None, parent=None):
        super().__init__(parent)
        self.folders = folders
        self.track_info = track_info
        self.duplicates = duplicates or []
        self.mix_stats = mix_stats or {}
        self.artist_info = artist_info
        self.album_info = album_info
        self.selected_folder = None
        self.action = None  # 'copy', 'move', 'cancel'

        self.mixxx_path = mixxx_path
        self.folder_tree = folder_tree or {}
        self.current_level = 'sub' if force_supergenre else 'top'
        self.current_supergenre = force_supergenre
        self.reclassify_mode = reclassify or force_supergenre is not None

        # Estado del chord de teclas en curso (p.ej. tras pulsar "B" con
        # varias carpetas candidatas) y referencias para poder resaltarlas.
        self.pending_keys = ""
        self.current_hotkeys = {}
        self.current_buttons = {}

        # Cargar UI desde archivo
        self.load_ui()
        self.setup_ui_connections()
        self.populate_ui()

        if self.reclassify_mode:
            origen = f"de {force_supergenre}" if force_supergenre else "dentro de Mix"
            self.setWindowTitle(f"Mover música - reclasificar {origen}")

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()

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
        self.setMinimumWidth(1300)
        self.setMinimumHeight(800)

        # Crear layout principal
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # Widget de información
        self.infoWidget = QWidget()
        info_layout = QHBoxLayout(self.infoWidget)
        info_layout.setSpacing(15)

        # Tres columnas: carátula | título, artista, álbum | carpeta y lo que hay en Mix.
        # La carátula es cuadrada y tan alta como la 2ª columna (_fit_cover).
        self.imageLabel = QLabel()
        self.imageLabel.setFixedSize(120, 120)
        self.imageLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_layout.addWidget(self.imageLabel, 0, Qt.AlignmentFlag.AlignTop)

        self.trackTextWidget = QWidget()
        track_layout = QVBoxLayout(self.trackTextWidget)
        track_layout.setContentsMargins(0, 0, 0, 0)
        self.titleLabel = QLabel()
        self.artistLabel = QLabel()
        self.albumLabel = QLabel()
        for lbl in (self.titleLabel, self.artistLabel, self.albumLabel):
            lbl.setWordWrap(True)
            track_layout.addWidget(lbl)
        # Géneros según cada fuente (etiquetas, Discogs, MusicBrainz, Last.fm)
        self.genresLabel = QLabel()
        self.genresLabel.setWordWrap(True)
        self.genresLabel.setTextFormat(Qt.TextFormat.RichText)
        track_layout.addWidget(self.genresLabel)
        track_layout.addStretch()
        info_layout.addWidget(self.trackTextWidget, 2, Qt.AlignmentFlag.AlignTop)

        mix_widget = QWidget()
        mix_layout = QVBoxLayout(mix_widget)
        mix_layout.setContentsMargins(0, 0, 0, 0)
        self.folderLabel = QLabel()
        self.folderLabel.setWordWrap(True)
        mix_layout.addWidget(self.folderLabel)
        # Canciones del mismo artista y sello que ya hay en Mix
        self.mixStatsLabel = QLabel()
        self.mixStatsLabel.setWordWrap(True)
        self.mixStatsLabel.setTextFormat(Qt.TextFormat.RichText)
        mix_layout.addWidget(self.mixStatsLabel)
        # Créditos de Discogs: producción, mezcla, masterización...
        self.creditsLabel = QLabel()
        self.creditsLabel.setWordWrap(True)
        self.creditsLabel.setTextFormat(Qt.TextFormat.RichText)
        mix_layout.addWidget(self.creditsLabel)
        mix_layout.addStretch()
        info_layout.addWidget(mix_widget, 3, Qt.AlignmentFlag.AlignTop)

        # Arriba y en medio, solo lo que ocupan; el espacio sobrante para la rejilla de carpetas
        self.infoWidget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        main_layout.addWidget(self.infoWidget)

        # Nombre esperado y coincidencias en Mix. Las coincidencias van en un
        # scroll de altura limitada: sueltas en el layout, con varias se
        # aplastaban unas contra otras y no se leía ninguna.
        self.duplicatesWidget = QWidget()
        self.duplicatesLayout = QVBoxLayout(self.duplicatesWidget)
        self.duplicatesLayout.setContentsMargins(0, 0, 0, 0)
        self.duplicatesLayout.setSpacing(4)
        self.duplicatesWidget.setVisible(False)
        self.duplicatesWidget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        main_layout.addWidget(self.duplicatesWidget)

        # ScrollArea para carpetas
        self.foldersScrollArea = QScrollArea()
        self.foldersScrollArea.setWidgetResizable(True)
        self.foldersScrollArea.setMinimumHeight(420)
        self.foldersScrollArea.setMaximumHeight(9950)

        self.foldersScrollAreaWidgetContents = QWidget()
        self.foldersGridLayout = QGridLayout(self.foldersScrollAreaWidgetContents)
        self.foldersScrollArea.setWidget(self.foldersScrollAreaWidgetContents)
        main_layout.addWidget(self.foldersScrollArea, 1)

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
        # ESC y Backspace se gestionan en keyPressEvent (para poder cancelar
        # solo el chord en curso antes de cerrar/retroceder del todo).

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

        # Algo más grandes que en el tema, junto a la carátula
        self.titleLabel.setStyleSheet("color: #7aa2f7; font-size: 20px; font-weight: bold;"
                                      "padding: 4px 0px; background-color: transparent; border: none;")
        self.artistLabel.setStyleSheet("color: #bb9af7; font-size: 17px; font-weight: bold;"
                                       "padding: 2px 0px; background-color: transparent; border: none;")
        self.albumLabel.setStyleSheet("color: #9ece6a; font-size: 15px; padding: 2px 0px;"
                                      "background-color: transparent; border: none;")

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
            font-size: 13px;
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

        # Canciones del artista y del sello que ya hay en Mix
        self.setup_mix_stats()

        # Mostrar nombre esperado y posibles existentes en destino
        self.setup_filename_info()

        # Poblar carpetas
        self.populate_folders()

    def showEvent(self, event):
        super().showEvent(event)
        self._fit_cover()
        # El atajo (Alt+º) comparte Alt con deadbeef, que al soltar Alt abre su
        # menú y se queda el foco: durante los primeros 2 s se recupera si se pierde
        self._focus_checks = 10
        self._keep_focus()

    def _keep_focus(self):
        if not self.isVisible() or self._focus_checks <= 0:
            return
        self._focus_checks -= 1
        if not self.isActiveWindow():
            self.raise_()
            self.activateWindow()
        self.setFocus()
        QTimer.singleShot(200, self._keep_focus)

    def _fit_cover(self):
        """Carátula cuadrada con la altura de la columna título-artista-álbum, de 250 px como mínimo."""
        column = getattr(self, 'trackTextWidget', None)
        if column is None:
            return
        column.adjustSize()
        labels = (self.titleLabel, self.artistLabel, self.albumLabel)
        text_height = sum(l.sizeHint().height() for l in labels if l.isVisibleTo(self))
        side = max(text_height, 250)  # 250x250 como mínimo
        self.imageLabel.setFixedSize(side, side)
        pixmap = getattr(self, '_cover_pixmap', None)
        if pixmap is not None:
            self.imageLabel.setPixmap(pixmap.scaled(side - 4, side - 4, Qt.AspectRatioMode.KeepAspectRatio,
                                                    Qt.TransformationMode.SmoothTransformation))

    def load_image(self):
        """Cargar imagen del artista/álbum"""
        image_loaded = False

        # La carátula de la propia pista es la más fiable; la base de datos busca por nombre
        if self.track_info.get('cover'):
            pixmap = QPixmap(self.track_info['cover'])
            if not pixmap.isNull():
                self._cover_pixmap = pixmap  # original, para reescalarlo en _fit_cover
                self.imageLabel.setPixmap(pixmap.scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                image_loaded = True

        # Intentar cargar imagen del álbum
        if not image_loaded and self.album_info and self.album_info.get('album_art_path'):
            album_art_path = self.album_info['album_art_path']
            if album_art_path and os.path.exists(album_art_path):
                try:
                    pixmap = QPixmap(album_art_path)
                    if not pixmap.isNull():
                        self._cover_pixmap = pixmap  # original, para reescalarlo en _fit_cover
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
                            self._cover_pixmap = pixmap  # original, para reescalarlo en _fit_cover
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
                                            self._cover_pixmap = pixmap  # original, para reescalarlo en _fit_cover
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
        # ESC y Backspace se gestionan en keyPressEvent (para poder cancelar
        # solo el chord en curso antes de cerrar/retroceder del todo).

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

        # Algo más grandes que en el tema, junto a la carátula
        self.titleLabel.setStyleSheet("color: #7aa2f7; font-size: 20px; font-weight: bold;"
                                      "padding: 4px 0px; background-color: transparent; border: none;")
        self.artistLabel.setStyleSheet("color: #bb9af7; font-size: 17px; font-weight: bold;"
                                       "padding: 2px 0px; background-color: transparent; border: none;")
        self.albumLabel.setStyleSheet("color: #9ece6a; font-size: 15px; padding: 2px 0px;"
                                      "background-color: transparent; border: none;")

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
            font-size: 13px;
            margin-top: 5px;
            background-color: transparent;
        """)

        self.infoWidget.setStyleSheet("background-color: #414868;")
        self.duplicatesWidget.setStyleSheet("background-color: #414868;")




    def build_expected_filename(self):
        """Construir el nombre esperado del archivo destino a partir de los metadatos disponibles."""
        artist = self.track_info.get('artist', '')
        title  = self.track_info.get('title', '')
        album  = self.track_info.get('album', '')
        year   = str((self.album_info or {}).get('year', '')) if self.album_info else ''

        if not artist and not title:
            return ''

        name = f"{artist} - {title}" if artist else title

        date_album = ''
        if year:
            date_album = year
        if album:
            date_album = (date_album + ' ' if date_album else '') + album
        if date_album:
            name += f" ({date_album})"

        return re.sub(r'[/\\?%*:|"<>]', '-', name)

    def setup_filename_info(self):
        """Mostrar siempre el nombre esperado del archivo y, si existen, los paths en destino."""
        self.duplicatesWidget.setVisible(True)

        # Limpiar layout
        while self.duplicatesLayout.count():
            child = self.duplicatesLayout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Nombre esperado (siempre)
        expected = self.build_expected_filename()
        if expected:
            expected_label = QLabel(f"→ {expected}")
            expected_label.setWordWrap(True)
            expected_label.setStyleSheet("""
                color: #9ece6a;
                font-size: 13px;
                font-family: monospace;
                background-color: transparent;
                padding: 4px 8px;
            """)
            self.duplicatesLayout.addWidget(expected_label)

        # Existentes en Mix: cabecera con el número y una línea por archivo,
        # dentro de un scroll de altura limitada
        if self.duplicates:
            artist_names = MusicMover._artist_names(self.track_info.get('artist', ''))

            def same_artist(path):
                file_artist = os.path.basename(path).split(' - ')[0]
                return bool(artist_names & MusicMover._artist_names(file_artist))

            # Primero las del mismo artista: las otras suelen ser títulos parecidos
            ordered = sorted(self.duplicates, key=lambda p: (not same_artist(p), p.casefold()))
            n_same = sum(1 for p in ordered if same_artist(p))

            header = QLabel(f"Ya en Mix: {len(ordered)} coincidencia{'s' if len(ordered) != 1 else ''}"
                            + (f" ({n_same} del mismo artista)" if n_same and n_same != len(ordered) else ""))
            header.setStyleSheet("color: #e0af68; font-size: 14px; font-weight: bold;"
                                 "background-color: transparent; padding: 2px 8px;")
            self.duplicatesLayout.addWidget(header)

            list_widget = QWidget()
            list_layout = QVBoxLayout(list_widget)
            list_layout.setContentsMargins(8, 4, 8, 4)
            list_layout.setSpacing(2)
            for dup in ordered:
                rel = os.path.relpath(dup, self.mixxx_path)
                folder, name = os.path.split(rel)
                color = "#e0af68" if same_artist(dup) else "#a9b1d6"
                line = QLabel(f"<span style='color:#7dcfff'>{html.escape(folder)}/</span>"
                              f"<span style='color:{color}'>{html.escape(name)}</span>")
                line.setTextFormat(Qt.TextFormat.RichText)
                line.setToolTip(dup)
                line.setStyleSheet("font-size: 14px; font-family: monospace; background-color: transparent;")
                list_layout.addWidget(line)
            list_layout.addStretch()

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(list_widget)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            # Hasta ~6 líneas visibles; con más, scroll
            line_height = max(line.sizeHint().height(), 18) + 2
            scroll.setFixedHeight(min(len(ordered), 6) * line_height + 14)
            scroll.setStyleSheet("QScrollArea { border: 1px solid #565f89; border-radius: 6px; }")
            self.duplicatesLayout.addWidget(scroll)

        # Botones: si hay duplicados mostrar copiar/mover, si no mostrar nueva carpeta
        if self.duplicates:
            self.newFolderButton.setVisible(False)
            self.copyButton.setVisible(True)
            # Regla: solo se mueve lo que ya está en Mix (reordenar); los discos nunca se tocan
            self.moveButton.setVisible(self.reclassify_mode)

    def setup_mix_stats(self):
        """'Artista en Mix: techno_minimal (3), Disco (2)' y lo mismo del sello."""
        label = getattr(self, 'mixStatsLabel', None)
        if label is None:
            return

        def fmt(counts):
            return ", ".join(f"{html.escape(os.path.basename(folder) or folder)} ({n})" for folder, n in counts)

        lines = []
        artist_counts = self.mix_stats.get('artist') or []
        if artist_counts:
            total = sum(n for _, n in artist_counts)
            lines.append(f"<b>Artista en Mix ({total}):</b> {fmt(artist_counts)}")
        else:
            lines.append("<b>Artista en Mix:</b> nada todavía")
        label_name = self.mix_stats.get('label_name')
        if label_name:
            label_counts = self.mix_stats.get('label') or []
            if label_counts:
                total = sum(n for _, n in label_counts)
                lines.append(f"<b>Sello {html.escape(label_name)} en Mix ({total}):</b> {fmt(label_counts)}")
            else:
                lines.append(f"<b>Sello {html.escape(label_name)} en Mix:</b> nada todavía")
        label.setText("<br>".join(lines))
        label.setStyleSheet("color: #bb9af7; font-size: 14px; margin-top: 4px; background-color: transparent;")

        # Géneros (2ª columna) y créditos (3ª), de la db de music-fuzzy
        def rows(pairs, key_color):
            return "<br>".join(f"<span style='color:{key_color}'><b>{html.escape(k)}:</b></span> {html.escape(v)}"
                               for k, v in pairs)
        genres = getattr(self, 'genresLabel', None)
        if genres is not None:
            pairs = self.mix_stats.get('genres') or []
            genres.setText(rows(pairs, "#7dcfff") if pairs else "<i>Sin géneros en la db</i>")
            genres.setStyleSheet("color: #c0caf5; font-size: 14px; margin-top: 6px; background-color: transparent;")
        credits = getattr(self, 'creditsLabel', None)
        if credits is not None:
            pairs = self.mix_stats.get('credits') or []
            credits.setText(rows(pairs, "#e0af68") if pairs else "")
            credits.setVisible(bool(pairs))
            credits.setStyleSheet("color: #c0caf5; font-size: 14px; margin-top: 6px; background-color: transparent;")

    def get_display_items(self):
        """Nombres a mostrar en el nivel actual: supergéneros/géneros planos
        arriba, o los subgéneros del supergénero activo si hemos entrado."""
        if self.current_level == 'sub' and self.current_supergenre:
            return list(self.folder_tree.get(self.current_supergenre) or [])
        return list(self.folders)

    def compute_folder_hotkeys(self, items, strip_prefix=None):
        """Calcular el prefijo mínimo único (1, 2, 3... letras) de cada carpeta.

        Carpetas que comparten letras iniciales (p.ej. TECHNO/TRANCE) reciben
        tantas letras como hagan falta para distinguirse entre sí; el resto
        conserva un atajo de una sola letra. Se recalcula sobre `items`, así
        que carpetas futuras con el mismo problema se resuelven igual.

        Si `strip_prefix` viene dado (p.ej. "TECHNO"), se ignora el prefijo
        "techno_" de cada nombre al calcular el atajo, para no gastar teclas
        repitiendo el supergénero en el que ya estamos.
        """
        def key_source(name):
            if strip_prefix:
                low_prefix = strip_prefix.lower() + "_"
                if name.lower().startswith(low_prefix):
                    return name[len(strip_prefix) + 1:]
            return name

        hotkeys = {}
        for item in items:
            src = key_source(item) or item
            code = src.upper()
            for n in range(1, len(src) + 1):
                prefix = src[:n].upper()
                if sum(1 for f in items if key_source(f)[:n].upper() == prefix) == 1:
                    code = prefix
                    break
            hotkeys[item] = code
        return hotkeys

    def is_supergenre(self, name):
        return self.current_level == 'top' and bool(self.folder_tree.get(name))

    def activate_item(self, item):
        """Ejecutar la acción de una carpeta: entrar en ella (si tiene
        subgéneros) o seleccionarla como destino final."""
        if self.is_supergenre(item):
            self.enter_supergenre(item)
        else:
            self.select_folder(item)

    def enter_supergenre(self, name):
        """Cambiar el panel de supergéneros al de subgéneros de `name`."""
        self.current_level = 'sub'
        self.current_supergenre = name
        self.pending_keys = ""
        self.setWindowTitle(f"Mover música - {name}")
        self.populate_folders()

    def go_back_to_top(self):
        """Volver del panel de subgéneros al panel principal."""
        self.current_level = 'top'
        self.current_supergenre = None
        self.pending_keys = ""
        self.setWindowTitle("Mover música - Tokyo Night")
        self.populate_folders()

    def populate_folders(self):
        """Poblar el grid de carpetas del nivel actual (supergéneros o
        subgéneros de uno concreto)."""
        while self.foldersGridLayout.count():
            child = self.foldersGridLayout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self.pending_keys = ""
        self.current_buttons = {}

        items = self.get_display_items()
        strip_prefix = self.current_supergenre if self.current_level == 'sub' else None
        self.current_hotkeys = self.compute_folder_hotkeys(items, strip_prefix=strip_prefix)

        row, col = 0, 0
        max_cols = 5

        if self.current_level == 'sub':
            back_btn = QPushButton("<- Volver (Backspace)")
            back_btn.clicked.connect(self.go_back_to_top)
            back_btn.setMinimumHeight(50)
            back_btn.setMinimumWidth(140)
            self.foldersGridLayout.addWidget(back_btn, row, col)
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        for item in items:
            hotkey = self.current_hotkeys[item]
            label = f"{item} ({', '.join(hotkey) if len(hotkey) > 1 else hotkey})"
            if self.is_supergenre(item):
                label += " ->"
            btn = QPushButton(label)
            btn.clicked.connect(lambda checked, f=item: self.activate_item(f))
            btn.setMinimumHeight(50)
            btn.setMinimumWidth(130)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)

            self.foldersGridLayout.addWidget(btn, row, col)
            self.current_buttons[item] = btn

            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        self.setFocus()

    def refresh_hotkey_highlight(self):
        """Resaltar las carpetas aún alcanzables con el chord en curso y
        atenuar el resto, para ver por dónde seguir tras pulsar una tecla
        que varias carpetas comparten (p.ej. "B" en b_dub/breaks)."""
        for item, btn in self.current_buttons.items():
            code = self.current_hotkeys.get(item, "")
            if not self.pending_keys:
                btn.setStyleSheet("")
            elif code.startswith(self.pending_keys):
                btn.setStyleSheet(
                    "background-color: #565f89; border: 3px solid #7aa2f7;"
                    "border-radius: 8px; color: #ffffff; font-weight: bold;"
                )
            else:
                btn.setStyleSheet(
                    "background-color: #1a1b26; border: 2px solid #1a1b26;"
                    "border-radius: 8px; color: #565f89;"
                )

    def keyPressEvent(self, event):
        """Manejar los atajos de carpeta como un chord (tecla a tecla), con
        resaltado en vivo de las carpetas que siguen siendo alcanzables."""
        key = event.key()

        if key == Qt.Key.Key_Escape:
            if self.pending_keys:
                self.pending_keys = ""
                self.refresh_hotkey_highlight()
            else:
                self.reject()
            return

        if key == Qt.Key.Key_Backspace:
            if self.pending_keys:
                self.pending_keys = self.pending_keys[:-1]
                self.refresh_hotkey_highlight()
            elif self.current_level == 'sub':
                self.go_back_to_top()
            return

        text = event.text()
        if not text or not (text.isalnum() or text == "_"):
            super().keyPressEvent(event)
            return

        candidate = self.pending_keys + text.upper()
        matches = [item for item, code in self.current_hotkeys.items() if code.startswith(candidate)]

        if not matches:
            # Tecla que no lleva a ninguna carpeta: se ignora, sin romper
            # el chord que ya llevábamos escrito.
            return

        self.pending_keys = candidate

        if len(matches) == 1 and self.current_hotkeys[matches[0]] == candidate:
            item = matches[0]
            self.pending_keys = ""
            self.activate_item(item)
            return

        self.refresh_hotkey_highlight()


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

        # Canciones del artista y del sello que ya hay en Mix
        self.setup_mix_stats()

        # Mostrar nombre esperado y posibles existentes en destino
        self.setup_filename_info()

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

            if self.reclassify_mode:
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
        if self.current_level == 'sub' and self.current_supergenre:
            self.selected_folder = os.path.join(self.current_supergenre, folder)
        else:
            self.selected_folder = folder
        self.accept()

    def create_new_folder(self):
        if self.current_level == 'sub' and self.current_supergenre:
            # Nueva carpeta de subgénero dentro del supergénero actual: solo
            # se pide la parte del subgénero, el prefijo se añade solo.
            subgenre, ok = QInputDialog.getText(
                self, f"Nuevo subgénero de {self.current_supergenre}",
                "Nombre del subgénero (sin el prefijo):"
            )
            if ok and subgenre.strip():
                slug = subgenre.strip().lower().replace(" ", "_")
                folder_name = f"{self.current_supergenre.lower()}_{slug}"
                new_folder_path = os.path.join(self.mixxx_path, self.current_supergenre, folder_name)
                os.makedirs(new_folder_path, exist_ok=True)
                self.selected_folder = os.path.join(self.current_supergenre, folder_name)
                self.accept()
        else:
            folder_name, ok = QInputDialog.getText(self, "Nueva carpeta", "Nombre de la nueva carpeta:")
            if ok and folder_name:
                new_folder_path = os.path.join(self.mixxx_path, folder_name)
                os.makedirs(new_folder_path, exist_ok=True)
                self.selected_folder = folder_name
                self.accept()




class CommentDialog(QDialog):
    def __init__(self, track_info, existing_comment="", destination_folder="", parent=None):
        super().__init__(parent)
        self.track_info = track_info
        self.destination_folder = destination_folder
        self.comment = ""
        self.obsession = False
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

        # Shift+Enter / Ctrl+Enter: abrir relacionar_mix.py (relaciones de
        # mezcla) en vez de aceptar -- el diálogo de comentario se queda
        # abierto para poder aceptar normalmente después.
        shift_enter = QShortcut(QKeySequence("Shift+Return"), self)
        shift_enter.activated.connect(self.open_relations_tool)

        ctrl_enter = QShortcut(QKeySequence("Ctrl+Return"), self)
        ctrl_enter.activated.connect(self.open_relations_tool)

    def open_relations_tool(self):
        """Abrir relacionar_mix.py con la canción actual como principal."""
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "relacionar_mix.py")
        if not os.path.exists(script_path):
            show_notification("relacionar_mix.py no encontrado", script_path, urgent=True)
            return
        payload = {
            "artist": self.track_info.get("artist", ""),
            "title": self.track_info.get("title", ""),
            "album": self.track_info.get("album", ""),
            "path": self.track_info.get("path", ""),
        }
        subprocess.Popen([sys.executable, script_path, "--track", json.dumps(payload)])

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

        if self.destination_folder:
            dest_label = QLabel(f"→ se va a copiar a: {self.destination_folder}")
            dest_label.setWordWrap(True)
            dest_label.setStyleSheet(
                "color: #9ece6a; font-size: 12px; font-weight: bold;"
                "background-color: transparent; padding: 4px 0px;"
            )
            layout.addWidget(dest_label)

        self.comment_edit = QLineEdit()
        if existing_comment:
            self.comment_edit.setText(f"{existing_comment}, ")
        self.comment_edit.setPlaceholderText("Escribe un comentario...")
        self.comment_edit.setFocus()
        layout.addWidget(self.comment_edit)

        self.obsession_check = QCheckBox("Marcar como obsesión (fijar en ListenBrainz)")
        self.obsession_check.setStyleSheet("color: #c0caf5; font-size: 13px; background-color: transparent;")
        layout.addWidget(self.obsession_check)

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
        self.obsession = self.obsession_check.isChecked()
        self.accept()


def show_notification(title, message, urgent=False, icon=None):
    """Mostrar notificación del sistema, con la carátula si se pasa en icon"""
    cmd = ['notify-send', '-t', '3000']
    if urgent:
        cmd += ['-u', 'critical']
    if icon:
        cmd += ['-i', icon]
    try:
        subprocess.run([*cmd, '--', title, message])
    except OSError:
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
            font-size: 13px;
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

MOVER_MIX_URL = os.getenv("MOVER_MIX_URL", "http://192.168.1.133:8786").rstrip('/')
MOVER_MIX_TOKEN = os.getenv("MOVER_MIX_TOKEN", "")


def mover_api(method, path, **kw):
    """Llamada al servicio mover_mix de pepecono (repeat-one). Lanza Exception con el motivo."""
    r = requests.request(method, f"{MOVER_MIX_URL}{path}", headers={"X-Token": MOVER_MIX_TOKEN},
                         timeout=kw.pop('timeout', 180), **kw)
    if r.status_code >= 400:
        try:
            detail = r.json().get('detail', r.text)
        except ValueError:
            detail = r.text
        raise Exception(f"pepecono: {detail}")
    return r.json()


def esperar_local(rel_path, timeout=90):
    """Ruta local del archivo cuando Syncthing lo trae de pepecono, o None si no llega a tiempo."""
    local = os.path.join("/mnt/windows/Mix", rel_path)
    for _ in range(timeout):
        if os.path.isfile(local):
            return local
        time.sleep(1)
    return None


def main():
    """Copiar (o reclasificar dentro de Mix) la canción que suena.

    La lógica corre en pepecono (servicio mover_mix, la misma que usa DSub en el móvil): aquí
    solo se detecta qué suena, se enseñan los diálogos y, cuando Syncthing trae el archivo,
    se hace lo que es de este PC (etiquetador, cajones de Mixxx, YouTube).
    Regla: lo que no está en Mix solo se copia; mover es para reordenar dentro de Mix.
    """
    app = QApplication(sys.argv)
    apply_tokyo_night_theme(app)

    try:
        if not MOVER_MIX_TOKEN:
            raise Exception("Falta MOVER_MIX_TOKEN en el .env de MoverMusica")
        mover = MusicMover()
        track_info = mover.get_current_track_info()

        # Qué canción: ruta local (vale tal cual en pepecono) o, si es un stream, artista/título
        if track_info.get('path') and not track_info.get('is_stream'):
            ref = {'path': track_info['path']}
        else:
            ref = {'artist': track_info.get('artist', ''), 'title': track_info.get('title', ''),
                   'album': track_info.get('album', '')}
        params = dict(ref)
        if track_info.get('length'):
            params['length'] = track_info['length']

        a = mover_api('GET', '/api/analyze', params=params)
        cue = a.get('cue')
        cue_choice = None
        if cue and cue.get('chosen') is None:
            def fmt(t):
                d = t.get('duration')
                return f"{t['number']:02d}. {t.get('title', '')}" + (f" ({int(d // 60)}:{int(d % 60):02d})" if d else "")
            whole = "— Copiar el disco entero —"
            items = [fmt(t) for t in cue['tracks']] + [whole]
            item, ok = QInputDialog.getItem(None, "Disco con cue",
                                            f"{track_info.get('filename', '')}\nno se pudo saber qué pista suena. Elige:",
                                            items, 0, False)
            if not ok:
                raise Exception("Operación cancelada")
            cue_choice = 0 if item == whole else cue['tracks'][items.index(item)]['number']
            a = mover_api('GET', '/api/analyze', params={**params, 'cue': cue_choice})

        # La ruta real en pepecono (para streams, la que encontró en Navidrome)
        server_path = a['path']
        track_info.update({'artist': a.get('artist') or track_info.get('artist', ''),
                           'title': a.get('title') or track_info.get('title', ''),
                           'album': a.get('album') or track_info.get('album', '')})
        track_info['song_name'] = f"{track_info['artist']} - {track_info['title']}"
        if not track_info.get('path') or track_info.get('is_stream'):
            track_info['path'] = server_path  # misma ruta en este PC (NFS / Mix)

        reclassify = a['reclassify']
        folder_tree = {t['name']: [c['name'] for c in t['children']] or None for t in a['tree']}
        folders = list(folder_tree.keys())
        if not folders:
            QMessageBox.critical(None, "Error", "No se encontraron subcarpetas en el directorio Mix")
            return
        duplicates = [os.path.join(mover.mixxx_path, d['path']) for d in a['duplicates']]

        track_info['cover'] = caratula_pista(track_info.get('path'))
        cover = track_info['cover']

        # Solo para enseñar (foto del artista, carátula, año): base de datos local
        artist_info, album_info = mover.get_database_info(track_info.get('artist', ''), track_info.get('title', ''),
                                                          track_info.get('album', ''))
        album_row = mover.find_album_row(track_info)
        if album_row:
            album_info = {'id': album_row.get('id'), 'name': album_row.get('name'),
                          'album_art_path': album_row.get('album_art_path'), 'year': album_row.get('year')}

        st = a.get('stats', {})
        mix_stats = {'artist': [tuple(x) for x in st.get('artist', [])],
                     'label': [tuple(x) for x in st.get('label', [])],
                     'label_name': st.get('label_name', ''),
                     'genres': [tuple(x) for x in st.get('genres', [])],
                     'credits': [tuple(x) for x in st.get('credits', [])]}

        dialog = FolderSelectionDialog(
            folders, track_info, duplicates, artist_info, album_info,
            folder_tree=folder_tree, force_supergenre=a.get('force_supergenre'),
            reclassify=reclassify, mixxx_path=mover.mixxx_path, mix_stats=mix_stats
        )
        if reclassify:
            dialog.action = 'move'

        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.selected_folder:
            show_notification("Cancelado", "Operación cancelada", urgent=True)
            return

        comment_dialog = CommentDialog(track_info, a.get('existing_comment', ''), dialog.selected_folder)
        if comment_dialog.exec() != QDialog.DialogCode.Accepted:
            show_notification("Cancelado", "Operación cancelada", urgent=True)
            return

        req = {'path': server_path, 'folder': dialog.selected_folder, 'comment': comment_dialog.comment,
               'obsession': bool(comment_dialog.obsession), 'length': track_info.get('length'),
               'cue': cue_choice}
        job = mover_api('POST', '/api/move', json=req)['job']
        show_notification("Mix", f"Enviado a pepecono: {dialog.selected_folder}", icon=cover)
        st = {}
        for _ in range(600):
            time.sleep(1)
            st = mover_api('GET', f"/api/jobs/{job}")
            if st['state'] in ('done', 'error'):
                break
        if st.get('state') != 'done':
            raise Exception(st.get('error') or "pepecono no terminó a tiempo")

        msgs = st.get('messages', [])
        rel = msgs[-1] if msgs and msgs[-1].lower().endswith(MusicMover.AUDIO_EXTS) else None
        for m in (msgs[:-1] if rel else msgs):
            servicio = next((x for x in ("ListenBrainz", "Last.fm") if m.startswith(x)), None)
            show_notification(servicio or "Mix", m, icon=cover,
                              urgent=bool(servicio) and m.startswith(f"{servicio}: error"))

        # Lo que es de este PC, cuando Syncthing trae el archivo
        new_file = esperar_local(rel) if rel else None
        if new_file:
            etiquetar_en_segundo_plano(new_file)
        elif rel:
            show_notification("Mix", f"Syncthing aún no ha traído {rel}; los cajones se actualizarán luego", urgent=True)

        sync_crates = os.path.expanduser("~/Scripts/Musica/playlists/mixxx/sync_crates.py")
        if os.path.exists(sync_crates):
            subprocess.Popen(["python3", sync_crates, "--quiet", "--notify"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        yt_script = os.path.expanduser("~/Scripts/Musica/playlists/youtube/yt_sync_mixxx.py")
        venv_python = os.path.expanduser("~/Scripts/python_venv/bin/python")
        if os.path.exists(yt_script):
            yt_args = ["--only", os.path.basename(os.path.normpath(dialog.selected_folder))]
            if reclassify:
                yt_args += ["--only", os.path.basename(os.path.dirname(server_path))]
            subprocess.Popen([venv_python, yt_script, *yt_args, "--publish", "--no-auth", "--notify"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

    except Exception as e:
        QMessageBox.critical(None, "Error", str(e))

    sys.exit()


if __name__ == "__main__":
    main()
