#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Script Name: odesli.py
# Description: Script unificado para obtener enlaces de Odesli desde DeaDBeeF o Airsonic
#              SIN dependencia de Spotify. Usa MusicBrainz → Deezer → YouTube Music como fallback.
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# Notes:
#   Dependencies: - python3, requests, dotenv, subprocess, hashlib
#                - deadbeef reproductor (opcional)
#                - airsonic-advanced server (opcional)
#                - dunst para notificaciones
#                - copyq para portapapeles
#
# FUENTES DE URL (en orden de prioridad):
#   1. MusicBrainz  → gratuito, sin API key, muy completo
#   2. Deezer       → gratuito, sin API key para búsqueda
#   3. YouTube Music → búsqueda por nombre, no requiere API key
#
# ODESLI: define ODESLI_API_KEY en .env para autenticarte con la API
#
# IMPORTANTE - Configuración de Airsonic-Advanced:
#   AUTENTICACIÓN: Por defecto usa password en texto plano (parámetro 'p')
#   Si tu servidor requiere token+salt, configura AIRSONIC_USE_PLAIN_PASSWORD=false en .env
#
#   Para autenticación con token+salt (más seguro):
#   El usuario debe estar configurado con un método de encriptación "decodable"
#   (como AES, no bcrypt). Para cambiar esto:
#   1. Ve a Settings > Users en Airsonic-Advanced
#   2. Edita el usuario que usarás para la API
#   3. En "Credential encryption", selecciona "AES" (o cualquier opción decodable)
#   4. Guarda y vuelve a configurar la contraseña del usuario

import os
import sys
import subprocess
import requests
import re
import hashlib
import time
import secrets
import urllib.parse
from pathlib import Path
from dotenv import load_dotenv


class OdesliManager:
    def __init__(self):
        # Cargar variables de entorno
        load_dotenv(dotenv_path="/home/huan/Scripts/utilities/open_search_links/music_player/.env")

        # Configuración de Airsonic-Advanced
        self.airsonic_url = os.getenv('AIRSONIC_URL', 'http://localhost:4040')
        self.airsonic_user = os.getenv('AIRSONIC_USER')
        self.airsonic_password = os.getenv('AIRSONIC_PASSWORD')
        self.airsonic_client = os.getenv('AIRSONIC_CLIENT', 'odesli-script')
        self.airsonic_use_plain = os.getenv('AIRSONIC_USE_PLAIN_PASSWORD', 'true').lower() == 'true'

        # Configuración de Odesli
        self.odesli_api_key = os.getenv('ODESLI_API_KEY')

        # Variables para almacenar información del track
        self.artist = ""
        self.album = ""
        self.title = ""
        self.artist_formatted = ""
        self.album_formatted = ""
        self.artist_for_search = ""
        self.path_album = ""
        self.source = ""

    # ──────────────────────────────────────────────
    #  OBTENER INFO DEL TRACK
    # ──────────────────────────────────────────────

    def get_current_track_info(self):
        """Obtiene información del track actual desde DeaDBeeF o Airsonic"""
        if self._get_deadbeef_info():
            self.source = "deadbeef"
            return True

        print("DeaDBeeF no está reproduciendo, intentando con Airsonic...")
        if self._get_airsonic_info():
            self.source = "airsonic"
            return True

        self.notify_error("Error", "No hay reproducción activa en DeaDBeeF ni Airsonic")
        return False

    def _get_deadbeef_info(self):
        """Obtiene información del track actual desde DeaDBeeF"""
        try:
            result_artist = subprocess.run(['deadbeef', '--nowplaying', '%a'],
                                           capture_output=True, text=True, timeout=2)
            result_album  = subprocess.run(['deadbeef', '--nowplaying', '%b'],
                                           capture_output=True, text=True, timeout=2)
            result_title  = subprocess.run(['deadbeef', '--nowplaying', '%t'],
                                           capture_output=True, text=True, timeout=2)
            result_path   = subprocess.run(['deadbeef', '--nowplaying-tf', '%path%'],
                                           capture_output=True, text=True, timeout=2)

            if result_artist.returncode != 0 or result_album.returncode != 0:
                return False

            self.artist = result_artist.stdout.strip()
            self.album  = result_album.stdout.strip()
            self.title  = result_title.stdout.strip()

            track_path = result_path.stdout.strip()
            if track_path:
                self.path_album = str(Path(track_path).parent)

            if not self.artist or not self.album \
                    or 'nothing' in self.artist.lower() \
                    or 'nothing' in self.album.lower():
                return False

            print(f"[DeaDBeeF] Artista: {self.artist}")
            print(f"[DeaDBeeF] Álbum:   {self.album}")
            print(f"[DeaDBeeF] Título:  {self.title}")
            print(f"[DeaDBeeF] Ruta:    {self.path_album}")
            return True

        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            print(f"DeaDBeeF no disponible: {e}", file=sys.stderr)
            return False

    def _get_airsonic_info(self):
        """Obtiene información del track actual desde Airsonic-Advanced"""
        if not self.airsonic_url or not self.airsonic_user or not self.airsonic_password:
            print("Configuración de Airsonic incompleta", file=sys.stderr)
            return False

        try:
            params = {
                'u': self.airsonic_user,
                'v': '1.15.0',
                'c': self.airsonic_client,
                'f': 'json'
            }

            if self.airsonic_use_plain:
                print("[Airsonic] Usando autenticación con password en texto plano")
                params['p'] = self.airsonic_password
            else:
                print("[Airsonic] Usando autenticación con token+salt")
                salt = self._generate_salt()
                token = hashlib.md5((self.airsonic_password + salt).encode()).hexdigest()
                params['t'] = token
                params['s'] = salt

            url = f"{self.airsonic_url}/rest/getNowPlaying.view"
            print(f"[Airsonic] Conectando a: {url}")

            response = requests.get(url, params=params, timeout=5)

            if response.status_code != 200:
                print(f"Error en petición a Airsonic: HTTP {response.status_code}", file=sys.stderr)
                return False

            data = response.json()

            if 'subsonic-response' not in data:
                print("Respuesta de Airsonic inválida", file=sys.stderr)
                return False

            subsonic_response = data['subsonic-response']

            if subsonic_response.get('status') != 'ok':
                error = subsonic_response.get('error', {})
                error_code    = error.get('code', 'unknown')
                error_message = error.get('message', 'Unknown error')
                print(f"Error de Airsonic: [{error_code}] {error_message}", file=sys.stderr)

                if error_code in (40, '40'):
                    print("\n⚠️  ERROR DE AUTENTICACIÓN ⚠️", file=sys.stderr)
                    print("Posibles soluciones:", file=sys.stderr)
                    print("1. Verifica usuario y contraseña en .env", file=sys.stderr)
                    print("2. En Airsonic-Advanced: Settings > Users > [tu usuario]", file=sys.stderr)
                    print("3. Cambia 'Credential encryption' a 'AES'", file=sys.stderr)
                return False

            now_playing = subsonic_response.get('nowPlaying', {}).get('entry', [])

            if not now_playing:
                print("No hay nada reproduciéndose en Airsonic", file=sys.stderr)
                return False

            track = now_playing[0] if isinstance(now_playing, list) else now_playing

            self.artist = track.get('artist', '')
            self.album  = track.get('album', '')
            self.title  = track.get('title', '')

            if not self.artist or not self.album:
                print("Información incompleta de Airsonic", file=sys.stderr)
                return False

            print(f"[Airsonic] Artista: {self.artist}")
            print(f"[Airsonic] Álbum:   {self.album}")
            print(f"[Airsonic] Título:  {self.title}")
            self.path_album = ""
            return True

        except requests.exceptions.Timeout:
            print(f"Timeout conectando a Airsonic ({self.airsonic_url})", file=sys.stderr)
            return False
        except requests.exceptions.ConnectionError:
            print(f"Error de conexión a Airsonic ({self.airsonic_url})", file=sys.stderr)
            return False
        except Exception as e:
            print(f"Error obteniendo info de Airsonic: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return False

    def _generate_salt(self):
        """Genera un salt aleatorio para autenticación Subsonic"""
        return secrets.token_hex(8)

    # ──────────────────────────────────────────────
    #  FORMATEO DE TÉRMINOS
    # ──────────────────────────────────────────────

    def format_search_terms(self):
        """Formatea los términos de búsqueda para diferentes propósitos"""

        def format_for_filename(text):
            text = text.replace(' ', '-')
            replacements = {
                'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
                'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U',
                'ñ': 'n', 'Ñ': 'N',
                "'": '-', '"': '-', '`': '-', ',': '-', ';': '-',
                ':': '-', '&': 'and'
            }
            for old, new in replacements.items():
                text = text.replace(old, new)
            return text

        def format_for_search(text):
            if 'and' in text.lower():
                text = re.sub(r'\band\b', '&', text, flags=re.IGNORECASE)
            return text

        self.artist_formatted  = format_for_filename(self.artist)
        self.album_formatted   = format_for_filename(self.album)
        self.artist_for_search = format_for_search(self.artist)

        print(f"Artista formateado (archivo): {self.artist_formatted}")
        print(f"Álbum formateado (archivo):   {self.album_formatted}")
        print(f"Artista para búsqueda:        {self.artist_for_search}")

    # ──────────────────────────────────────────────
    #  BÚSQUEDA DE URL EN PLATAFORMAS (sin Spotify)
    # ──────────────────────────────────────────────

    def get_platform_url(self):
        """
        Intenta obtener una URL de plataforma de música en este orden:
          1. MusicBrainz  (gratuito, sin API key)
          2. Deezer       (gratuito, sin API key)
          3. YouTube Music (búsqueda web, sin API key)
        Devuelve (url, platform_name) o (None, None) si todo falla.
        """
        # 1 — MusicBrainz
        url = self._get_musicbrainz_url()
        if url:
            return url, "musicbrainz"

        # 2 — Deezer
        url = self._get_deezer_url()
        if url:
            return url, "deezer"

        # 3 — YouTube Music
        url = self._get_youtube_music_url()
        if url:
            return url, "youtubeMusic"

        return None, None

    def _get_musicbrainz_url(self):
        """
        Busca el álbum en MusicBrainz y devuelve su URL canónica.
        MusicBrainz no requiere API key; solo pide un User-Agent descriptivo.
        """
        try:
            headers = {
                'User-Agent': 'odesli-script/1.0 (https://github.com/volteret4/)'
            }
            # Búsqueda por artista + álbum
            query = f'artist:"{self.artist_for_search}" AND release:"{self.album}"'
            params = {
                'query': query,
                'fmt': 'json',
                'limit': 1
            }
            print(f"[MusicBrainz] Buscando: {query}")
            resp = requests.get(
                'https://musicbrainz.org/ws/2/release/',
                params=params,
                headers=headers,
                timeout=10
            )

            # MusicBrainz pide máximo 1 req/s
            time.sleep(1)

            if resp.status_code != 200:
                print(f"[MusicBrainz] HTTP {resp.status_code}", file=sys.stderr)
                return None

            data = resp.json()
            releases = data.get('releases', [])

            if not releases:
                print("[MusicBrainz] Sin resultados", file=sys.stderr)
                return None

            mbid = releases[0].get('id')
            if not mbid:
                return None

            mb_url = f"https://musicbrainz.org/release/{mbid}"
            print(f"[MusicBrainz] URL encontrada: {mb_url}")
            return mb_url

        except Exception as e:
            print(f"[MusicBrainz] Error: {e}", file=sys.stderr)
            return None

    def _get_deezer_url(self):
        """
        Busca el álbum en Deezer (API pública, sin autenticación).
        """
        try:
            query = f'{self.artist_for_search} {self.album}'
            print(f"[Deezer] Buscando: {query}")
            params = {
                'q': query,
                'limit': 1
            }
            resp = requests.get(
                'https://api.deezer.com/search/album',
                params=params,
                timeout=10
            )

            if resp.status_code != 200:
                print(f"[Deezer] HTTP {resp.status_code}", file=sys.stderr)
                return None

            data = resp.json()
            items = data.get('data', [])

            if not items:
                print("[Deezer] Sin resultados", file=sys.stderr)
                return None

            deezer_url = items[0].get('link')
            if not deezer_url:
                return None

            print(f"[Deezer] URL encontrada: {deezer_url}")
            return deezer_url

        except Exception as e:
            print(f"[Deezer] Error: {e}", file=sys.stderr)
            return None

    def _get_youtube_music_url(self):
        """
        Construye una URL de búsqueda de YouTube Music.
        No requiere API key: genera la URL de búsqueda directamente.
        Odesli acepta URLs de youtubeMusic para resolver el pageUrl.
        """
        try:
            search_term = f"{self.artist_for_search} {self.album} full album"
            encoded = urllib.parse.quote_plus(search_term)
            yt_url = f"https://music.youtube.com/search?q={encoded}"
            print(f"[YouTubeMusic] URL de búsqueda: {yt_url}")
            return yt_url
        except Exception as e:
            print(f"[YouTubeMusic] Error: {e}", file=sys.stderr)
            return None

    # ──────────────────────────────────────────────
    #  ODESLI
    # ──────────────────────────────────────────────

    def get_odesli_url(self, platform_url, platform="musicbrainz"):
        """
        Obtiene la URL de Odesli a partir de una URL de plataforma.
        Si la plataforma no es reconocida directamente por Odesli, intenta
        hacer la búsqueda por artista+álbum usando el endpoint de Odesli.
        """
        try:
            api_endpoint = "https://api.odesli.co/v1-alpha.1/links"

            # MusicBrainz no es una plataforma soportada directamente por Odesli,
            # así que si viene de ahí usamos búsqueda por título+artista como fallback
            if platform == "musicbrainz":
                print("[Odesli] MusicBrainz no es plataforma directa; intentando con Deezer/YTMusic como entrada...")
                # Reintentar con Deezer o YouTube Music para pasarle a Odesli una URL que sí reconozca
                deezer_url = self._get_deezer_url()
                if deezer_url:
                    platform_url = deezer_url
                    platform = "deezer"
                else:
                    yt_url = self._get_youtube_music_url()
                    if yt_url:
                        platform_url = yt_url
                        platform = "youtubeMusic"
                    else:
                        raise Exception("No se encontró URL en plataforma compatible con Odesli")

            params = {"url": platform_url}
            if self.odesli_api_key:
                params["key"] = self.odesli_api_key
            else:
                print("[Odesli] ODESLI_API_KEY no configurada; usando acceso sin clave", file=sys.stderr)
            print(f"[Odesli] Consultando con URL de {platform}: {platform_url}")
            response = requests.get(api_endpoint, params=params, timeout=15)

            if response.status_code == 200:
                data = response.json()
                page_url = data.get("pageUrl")
                if page_url:
                    print(f"[Odesli] URL obtenida: {page_url}")
                    return page_url
                else:
                    raise Exception("No se obtuvo pageUrl de la respuesta")
            elif response.status_code == 429:
                raise Exception("Límite horario de peticiones a Odesli excedido (429 Too Many Requests)")
            else:
                raise Exception(f"Error en la solicitud a Odesli: {response.status_code} — {response.text}")

        except Exception as e:
            print(f"Error obteniendo URL de Odesli: {e}", file=sys.stderr)
            return None

    # ──────────────────────────────────────────────
    #  PORTADA, PORTAPAPELES Y NOTIFICACIONES
    # ──────────────────────────────────────────────

    def find_cover_image(self):
        """Busca la imagen de portada en el directorio del álbum"""
        if self.source == "airsonic" or not self.path_album:
            print("No hay ruta local de álbum (fuente: Airsonic)")
            return None

        try:
            album_path = Path(self.path_album)

            for pattern in ("cover.*", "folder.*"):
                for f in album_path.glob(pattern):
                    if f.suffix.lower() in ('.png', '.jpg', '.jpeg'):
                        print(f"Portada encontrada: {f}")
                        return str(f)

            print("No se encontró imagen de portada")
            return None

        except Exception as e:
            print(f"Error buscando portada: {e}", file=sys.stderr)
            return None

    def copy_to_clipboard(self, odesli_url):
        """Copia el contenido al portapapeles usando CopyQ"""
        try:
            artist_f = self.artist_formatted.replace("-", " ")
            album_f  = self.album_formatted.replace("-", " ")
            contenido = f"*{artist_f}* - {album_f}: {odesli_url}"
            subprocess.run(["copyq", "add", contenido], check=True)
            print(f"Copiado al portapapeles: {contenido}")
            return True
        except Exception as e:
            print(f"Error copiando al portapapeles: {e}", file=sys.stderr)
            return False

    def send_notification(self, odesli_url, cover_path=None):
        """Envía notificación usando dunst"""
        try:
            cmd = ["dunstify", "-a", "Odesli", "-t", "5000"]  # sin carátula, dunst pone el icono de Odesli
            if cover_path:
                cmd.extend(["-i", cover_path])

            source_emoji = "🎵" if self.source == "deadbeef" else "☁️"
            title   = f"<b>{source_emoji} {self.artist} - {self.album}</b>"
            message = f"{title} \n {odesli_url}"
            cmd.append(message)

            env = os.environ.copy()
            env["DISPLAY"] = ":0"
            subprocess.run(cmd, env=env, check=True)
            print("Notificación enviada")
            return True

        except Exception as e:
            print(f"Error enviando notificación: {e}", file=sys.stderr)
            return False

    def notify_error(self, title, message):
        """Envía notificación de error"""
        try:
            env = os.environ.copy()
            env["DISPLAY"] = ":0"
            subprocess.run(["dunstify", "-a", "Odesli", "-t", "5000", title, message], env=env)
        except Exception:
            pass

    # ──────────────────────────────────────────────
    #  PUNTO DE ENTRADA PRINCIPAL
    # ──────────────────────────────────────────────

    def run(self):
        """Ejecuta el proceso completo"""
        print("=== Iniciando proceso de obtención de enlace Odesli ===")

        # 1. Obtener información del track (DeaDBeeF o Airsonic)
        if not self.get_current_track_info():
            return False

        print(f"Fuente de información: {self.source}")

        # 2. Formatear términos de búsqueda
        self.format_search_terms()

        # 3. Buscar URL en plataformas (MusicBrainz → Deezer → YouTube Music)
        platform_url, platform = self.get_platform_url()
        if not platform_url:
            self.notify_error("Error búsqueda", "No se encontró el álbum en ninguna plataforma")
            return False

        print(f"URL de plataforma obtenida ({platform}): {platform_url}")

        # 4. Obtener URL de Odesli
        odesli_url = self.get_odesli_url(platform_url, platform)
        if not odesli_url:
            self.notify_error("Error Odesli", "No se pudo obtener la URL de Odesli")
            return False

        # 5. Buscar portada (solo DeaDBeeF)
        cover_path = self.find_cover_image()

        # 6. Copiar al portapapeles
        self.copy_to_clipboard(odesli_url)

        # 7. Enviar notificación
        self.send_notification(odesli_url, cover_path)

        print("=== Proceso completado exitosamente ===")
        return True


def main():
    manager = OdesliManager()
    success = manager.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
