#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Script Name: odesli_unified.py
# Description: Script unificado para obtener enlaces de Odesli desde información de DeaDBeeF
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# Notes:
#   Dependencies: - python3, requests, spotipy, dotenv, subprocess
#                - deadbeef reproductor
#                - dunst para notificaciones
#                - copyq para portapapeles
#                - spotify_login.py en el mismo directorio o PATH

import os
import sys
import subprocess
import requests
import re
from pathlib import Path
from dotenv import load_dotenv

# Importar el módulo de autenticación de Spotify
try:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from apis.spotify_login import SpotifyAuthManager
except ImportError:
    print("Error: No se puede importar spotify_login.py", file=sys.stderr)
    sys.exit(1)

class OdesliManager:
    def __init__(self):
        # Cargar variables de entorno
        load_dotenv(dotenv_path="/home/huan/Scripts/.env")
        
        # Configuración de Spotify
        self.client_id = os.getenv('SPOTIFY_CLIENT')
        self.client_secret = os.getenv('SPOTIFY_SECRET')
        self.redirect_uri = os.getenv('SPOTIFY_REDIRECT_URI', 'http://localhost:8998')
        
        # Ruta del caché desde variable de entorno o por defecto
        self.cache_path = os.getenv('SPOTIFY_CACHE', 
                                   os.path.join(os.environ.get("HOME", ""), 
                                              "gits", "pollo", "music-fuzzy", 
                                              ".content", "cache", "spotify_token.txt"))
        
        # Configurar autenticación de Spotify
        self.spotify_auth = SpotifyAuthManager(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            cache_path=self.cache_path,
            selected_scopes=['user-read-private']  # Solo necesitamos búsqueda
        )
        
        # Variables para almacenar información del track
        self.artist = ""
        self.album = ""
        self.artist_formatted = ""
        self.album_formatted = ""
        self.artist_for_search = ""
        self.path_album = ""
        
    def get_current_track_info(self):
        """Obtiene información del track actual desde DeaDBeeF"""
        try:
            # Obtener artista y álbum desde DeaDBeeF
            result_artist = subprocess.run(['deadbeef', '--nowplaying', '%a'], 
                                         capture_output=True, text=True)
            result_album = subprocess.run(['deadbeef', '--nowplaying', '%b'], 
                                        capture_output=True, text=True)
            result_path = subprocess.run(['deadbeef', '--nowplaying-tf', '%path%'], 
                                       capture_output=True, text=True)
            
            if result_artist.returncode != 0 or result_album.returncode != 0:
                raise Exception("Error al ejecutar deadbeef")
                
            self.artist = result_artist.stdout.strip()
            self.album = result_album.stdout.strip()
            
            # Obtener directorio del álbum
            track_path = result_path.stdout.strip()
            if track_path:
                self.path_album = str(Path(track_path).parent)
            
            # Validar que no estén vacíos
            if not self.artist or not self.album or 'nothing' in self.artist.lower() or 'nothing' in self.album.lower():
                raise Exception("El artista o álbum están vacíos o contienen 'nothing'")
                
            print(f"Artista: {self.artist}")
            print(f"Álbum: {self.album}")
            print(f"Ruta del álbum: {self.path_album}")
            
            return True
            
        except Exception as e:
            self.notify_error("Error obteniendo info de DeaDBeeF", str(e))
            return False
    
    def format_search_terms(self):
        """Formatea los términos de búsqueda para diferentes propósitos"""
        # Para formatear nombres de archivo (reemplazar caracteres especiales)
        def format_for_filename(text):
            # Reemplazar espacios por guiones
            text = text.replace(' ', '-')
            # Reemplazar caracteres especiales
            replacements = {
                'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
                "'": '-', '"': '-', '`': '-', ',': '-', ';': '-', 
                ':': '-', '&': 'and'
            }
            for old, new in replacements.items():
                text = text.replace(old, new)
            return text
        
        # Para formatear términos de búsqueda en Spotify (mantener & como &)
        def format_for_search(text):
            # Aquí mantenemos el & original para la búsqueda en Spotify
            # Solo reemplazamos si viene como "and" y queremos convertirlo de vuelta a &
            if 'and' in text.lower():
                # Reemplazar "and" por "&" para la búsqueda, pero solo si es una palabra completa
                text = re.sub(r'\band\b', '&', text, flags=re.IGNORECASE)
            return text
        
        # Formatear para nombres de archivo
        self.artist_formatted = format_for_filename(self.artist)
        self.album_formatted = format_for_filename(self.album)
        
        # Formatear para búsqueda (mantener & original)
        self.artist_for_search = format_for_search(self.artist)
        
        print(f"Artista formateado (archivo): {self.artist_formatted}")
        print(f"Álbum formateado (archivo): {self.album_formatted}")
        print(f"Artista para búsqueda: {self.artist_for_search}")
    
    def get_spotify_url(self):
        """Obtiene la URL de Spotify para el álbum"""
        try:
            # Obtener cliente autenticado
            spotify_client = self.spotify_auth.get_client()
            if not spotify_client:
                raise Exception("No se pudo autenticar con Spotify")
            
            # Construir query de búsqueda
            query = f"artist:{self.artist_for_search} album:{self.album}"
            print(f"Query de búsqueda: {query}")
            
            # Buscar el álbum
            resultados = spotify_client.search(query, type='album', limit=1)
            
            if resultados['albums']['items']:
                spotify_url = resultados['albums']['items'][0]['external_urls']['spotify']
                print(f"URL de Spotify encontrada: {spotify_url}")
                return spotify_url
            else:
                raise Exception("No se encontró el álbum en Spotify")
                
        except Exception as e:
            print(f"Error obteniendo URL de Spotify: {e}", file=sys.stderr)
            return None
    
    def get_odesli_url(self, spotify_url):
        """Obtiene la URL de Odesli a partir de la URL de Spotify"""
        try:
            api_endpoint = "https://api.song.link/v1-alpha.1/links"
            response = requests.get(api_endpoint, params={"url": spotify_url})
            
            if response.status_code == 200:
                data = response.json()
                page_url = data.get("pageUrl")
                
                if page_url:
                    print(f"URL de Odesli: {page_url}")
                    return page_url
                else:
                    raise Exception("No se obtuvo pageUrl de la respuesta")
            else:
                raise Exception(f"Error en la solicitud a Odesli: {response.status_code}")
                
        except Exception as e:
            print(f"Error obteniendo URL de Odesli: {e}", file=sys.stderr)
            return None
    
    def find_cover_image(self):
        """Busca la imagen de portada en el directorio del álbum"""
        if not self.path_album:
            return None
            
        try:
            album_path = Path(self.path_album)
            
            # Buscar cover.*
            cover_files = list(album_path.glob("cover.*"))
            if cover_files:
                # Filtrar por extensiones de imagen
                for cover in cover_files:
                    if cover.suffix.lower() in ['.png', '.jpg', '.jpeg']:
                        print(f"Cover encontrado: {cover}")
                        return str(cover)
            
            # Si no se encontró cover, buscar folder.*
            folder_files = list(album_path.glob("folder.*"))
            if folder_files:
                for folder in folder_files:
                    if folder.suffix.lower() in ['.png', '.jpg', '.jpeg']:
                        print(f"Folder encontrado: {folder}")
                        return str(folder)
            
            print("No se encontró imagen de portada")
            return None
            
        except Exception as e:
            print(f"Error buscando portada: {e}", file=sys.stderr)
            return None
    
    def copy_to_clipboard(self, odesli_url):
        """Copia el contenido al portapapeles usando CopyQ"""
        try:
            artist_formatted = self.artist_formatted.replace("-", " ")
            album_formatted = self.album_formatted.replace("-", " ")
            contenido = f"*{artist_formatted}* - {album_formatted}: {odesli_url}"
            subprocess.run(["copyq", "add", contenido], check=True)
            print(f"Copiado al portapapeles: {contenido}")
            return True
        except Exception as e:
            print(f"Error copiando al portapapeles: {e}", file=sys.stderr)
            return False
    
    def send_notification(self, odesli_url, cover_path=None):
        """Envía notificación usando dunst"""
        try:
            # Preparar el comando
            cmd = ["dunstify", "-t", "5000"]
            
            # Añadir icono si existe
            if cover_path:
                cmd.extend(["-i", cover_path])
            
            # Mensaje de la notificación
            title = f"<b>{self.artist} - {self.album}</b>"
            message = f"{title} \n {odesli_url}"
            cmd.append(message)
            
            # Establecer DISPLAY y ejecutar
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
            subprocess.run(["dunstify", "-t", "5000", title, message], env=env)
        except:
            pass
    
    def run(self):
        """Ejecuta el proceso completo"""
        print("=== Iniciando proceso de obtención de enlace Odesli ===")
        
        # 1. Obtener información del track actual
        if not self.get_current_track_info():
            return False
        
        # 2. Formatear términos de búsqueda
        self.format_search_terms()
        
        # 3. Obtener URL de Spotify
        spotify_url = self.get_spotify_url()
        if not spotify_url:
            self.notify_error("Error Spotify", "No se pudo obtener la URL de Spotify")
            return False
        
        # 4. Obtener URL de Odesli
        odesli_url = self.get_odesli_url(spotify_url)
        if not odesli_url:
            self.notify_error("Error Odesli", "No se pudo obtener la URL de Odesli")
            return False
        
        # 5. Buscar imagen de portada
        cover_path = self.find_cover_image()
        
        # 6. Copiar al portapapeles
        self.copy_to_clipboard(odesli_url)
        
        # 7. Enviar notificación
        self.send_notification(odesli_url, cover_path)
        
        print("=== Proceso completado exitosamente ===")
        return True

def main():
    """Función principal"""
    manager = OdesliManager()
    success = manager.run()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()