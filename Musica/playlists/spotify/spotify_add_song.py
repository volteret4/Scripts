#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script Name: spotify_add_song.py
Description: Añade la canción actualmente en reproducción a una playlist de Spotify
Author: volteret4
"""

import os
import sys
import json
import yaml
import time
import logging
import subprocess
from pathlib import Path
from datetime import datetime

# Importar módulos de PyQt6
try:
    from PyQt6.QtWidgets import (QApplication, QDialog, QVBoxLayout, 
                                QLabel, QPushButton, QHBoxLayout, QWidget)
    from PyQt6.QtCore import Qt, QSize
    from PyQt6.QtGui import QFont, QKeySequence, QShortcut
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False
    logging.error("PyQt6 no está instalado. No se puede mostrar el menú gráfico.")

# Importar Spotipy
try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    SPOTIPY_AVAILABLE = True
except ImportError:
    SPOTIPY_AVAILABLE = False
    logging.error("Spotipy no está instalado. La funcionalidad de Spotify será limitada.")

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("spotify_add_song")

# Definir ruta del script actual
SCRIPT_DIR = Path("/home/huan/gits/pollo/music-fuzzy/tools")
PROJECT_ROOT = Path(os.path.dirname(os.path.abspath(SCRIPT_DIR)))

# Definir la ruta del token
TOKEN_PATH = os.environ.get('SPOTIFY_TOKEN', str(PROJECT_ROOT / '.content' / 'cache' / 'spotify_token.txt'))

# Definir hotkeys (números + teclas QWERTY)
HOTKEYS = "0123456789qwertyuiopasdfghjklzxcvbnm"
SPOTIFY_GREEN = "#1DB954"  # Color verde de Spotify
DARK_BG = "#14141e"       # Fondo oscuro

class SpotifyAddSong:
    def __init__(self):
        self.config = self.load_config()
        self.spotify = None
        self.current_track = None
        self.playlists = []
    
    def load_config(self):
        """Carga la configuración desde config.yml"""
        try:
            config_path = PROJECT_ROOT / "config" / "config.yml"
            if not config_path.exists():
                config_path = PROJECT_ROOT / "config.yml"
                
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            return config
        except Exception as e:
            logger.error(f"Error cargando configuración: {e}")
            return {}

    def get_spotify_credentials(self):
        """Obtiene las credenciales de Spotify desde la configuración"""
        spotify_config = self.config.get('global_theme_config', {})
        credentials = {
            'client_id': spotify_config.get('spotify_client_id'),
            'client_secret': spotify_config.get('spotify_client_secret'),
            'redirect_uri': spotify_config.get('spotify_redirect_uri', 'http://localhost:8998'),
            'username': spotify_config.get('spotify_user')
        }
        return credentials
    
    def load_token(self):
        """Carga el token desde el archivo especificado"""
        try:
            if os.path.exists(TOKEN_PATH):
                with open(TOKEN_PATH, 'r') as f:
                    token_info = json.load(f)
                logger.info(f"Token cargado desde {TOKEN_PATH}")
                return token_info
            else:
                logger.warning(f"Archivo de token no encontrado en {TOKEN_PATH}")
                return None
        except Exception as e:
            logger.error(f"Error cargando token: {e}")
            return None
    
    def is_token_valid(self, token_info):
        """Verifica si el token sigue siendo válido"""
        if not token_info:
            return False
        
        now = int(time.time())
        return token_info.get('expires_at', 0) > now + 60  # Margen de 60 segundos
    
    def refresh_token(self):
        """Intenta renovar el token usando spotify_login.py"""
        try:
            # Encuentra el módulo spotify_login.py
            spotify_login_path = SCRIPT_DIR / "spotify_login.py"
            if not spotify_login_path.exists():
                # Buscar el módulo en otras ubicaciones
                for potential_path in [PROJECT_ROOT, PROJECT_ROOT / "modules", PROJECT_ROOT / "utils"]:
                    test_path = potential_path / "spotify_login.py"
                    if test_path.exists():
                        spotify_login_path = test_path
                        break
            
            if not spotify_login_path.exists():
                logger.error("No se pudo encontrar spotify_login.py")
                return False
            
            logger.info(f"Ejecutando {spotify_login_path} para renovar token")
            
            # Obtener credenciales
            creds = self.get_spotify_credentials()
            
            # Implementar la renovación del token
            from importlib.util import spec_from_file_location, module_from_spec
            
            # Cargar el módulo dinámicamente
            spec = spec_from_file_location("spotify_login", spotify_login_path)
            spotify_login_module = module_from_spec(spec)
            spec.loader.exec_module(spotify_login_module)
            
            # Crear instancia del SpotifyAuthManager
            auth_manager = spotify_login_module.SpotifyAuthManager(
                client_id=creds['client_id'],
                client_secret=creds['client_secret'],
                redirect_uri=creds['redirect_uri'],
                cache_path=TOKEN_PATH
            )
            
            # Autenticar
            success = auth_manager.authenticate()
            
            if success:
                logger.info("Token renovado correctamente")
                return True
            else:
                logger.error("No se pudo renovar el token")
                return False
                
        except Exception as e:
            logger.error(f"Error renovando token: {e}")
            return False
    
    def initialize_spotify(self):
        """Inicializa la conexión con Spotify"""
        if not SPOTIPY_AVAILABLE:
            logger.error("Spotipy no está disponible")
            return False
        
        # Cargar el token
        token_info = self.load_token()
        
        # Verificar si el token es válido
        if not self.is_token_valid(token_info):
            logger.info("Token no válido o expirado, intentando renovar")
            if not self.refresh_token():
                logger.error("No se pudo renovar el token")
                return False
            token_info = self.load_token()  # Recargar token después de renovar
        
        # Crear cliente de Spotify
        try:
            creds = self.get_spotify_credentials()
            self.spotify = spotipy.Spotify(auth=token_info['access_token'])
            
            # Verificar si el cliente está conectado correctamente
            user = self.spotify.current_user()
            logger.info(f"Conectado a Spotify como: {user.get('display_name', user.get('id'))}")
            return True
        except Exception as e:
            logger.error(f"Error inicializando Spotify: {e}")
            return False
    
    def get_current_track(self):
        """Obtiene información de la canción actualmente en reproducción"""
        try:
            # Ejecutar comandos para obtener información de la canción
            # Primero intentar con playerctl
            try:
                title = subprocess.check_output(["playerctl", "metadata", "title"], text=True).strip()
                artist = subprocess.check_output(["playerctl", "metadata", "artist"], text=True).strip()
                self.current_track = {"title": title, "artist": artist}
                logger.info(f"Canción actual (playerctl): {artist} - {title}")
                return True
            except:
                pass
                
            # Intentar con deadbeef
            try:
                artist = subprocess.check_output(["deadbeef", "--nowplaying-tf", "%artist%"], text=True).strip()
                title = subprocess.check_output(["deadbeef", "--nowplaying-tf", "%title%"], text=True).strip()
                if artist and title:
                    self.current_track = {"title": title, "artist": artist}
                    logger.info(f"Canción actual (deadbeef): {artist} - {title}")
                    return True
            except:
                pass
            
            # Si no se encontró con reproductores, intentar buscar en reproducciones recientes de Spotify
            if self.spotify:
                try:
                    recent = self.spotify.current_user_recently_played(limit=1)
                    if recent and recent.get('items'):
                        track = recent['items'][0]['track']
                        self.current_track = {
                            'title': track['name'],
                            'artist': track['artists'][0]['name'],
                            'uri': track['uri']
                        }
                        logger.info(f"Canción reciente (Spotify): {self.current_track['artist']} - {self.current_track['title']}")
                        return True
                except Exception as e:
                    logger.error(f"Error obteniendo reproducciones recientes: {e}")
            
            logger.warning("No se pudo obtener información de la canción actual")
            return False
            
        except Exception as e:
            logger.error(f"Error obteniendo canción actual: {e}")
            return False
    
    def get_track_uri(self):
        """Busca en Spotify la URI de la canción actual"""
        if not self.current_track:
            logger.error("No hay información de pista actual para buscar")
            return None
        
        if 'uri' in self.current_track:
            return self.current_track['uri']
        
        try:
            # Buscar la canción en Spotify
            query = f"track:{self.current_track['title']} artist:{self.current_track['artist']}"
            results = self.spotify.search(q=query, type='track', limit=1)
            
            if results and results.get('tracks', {}).get('items'):
                track_uri = results['tracks']['items'][0]['uri']
                self.current_track['uri'] = track_uri
                logger.info(f"URI de pista encontrada: {track_uri}")
                return track_uri
            else:
                logger.warning(f"No se encontró la pista en Spotify: {self.current_track['artist']} - {self.current_track['title']}")
                return None
        except Exception as e:
            logger.error(f"Error buscando URI de pista: {e}")
            return None
    
    def get_user_playlists(self):
        """Obtiene las playlists del usuario"""
        if not self.spotify:
            logger.error("Cliente de Spotify no inicializado")
            return []
        
        try:
            # Obtener usuario desde configuración
            username = self.get_spotify_credentials().get('username')
            if not username:
                user = self.spotify.current_user()
                username = user['id']
            
            # Obtener playlists
            playlists = []
            results = self.spotify.user_playlists(username)
            
            while results:
                playlists.extend(results['items'])
                if results['next']:
                    results = self.spotify.next(results)
                else:
                    break
            
            logger.info(f"Se encontraron {len(playlists)} playlists")
            self.playlists = playlists
            return playlists
        except Exception as e:
            logger.error(f"Error obteniendo playlists: {e}")
            return []
    
    def add_track_to_playlist(self, playlist_id):
        """Añade la canción actual a la playlist seleccionada"""
        if not self.spotify or not self.current_track:
            logger.error("Cliente de Spotify no inicializado o no hay pista actual")
            return False
        
        track_uri = self.get_track_uri()
        if not track_uri:
            logger.error("No se pudo obtener URI de la pista")
            return False
        
        try:
            # Añadir la pista a la playlist
            self.spotify.playlist_add_items(playlist_id, [track_uri])
            
            # Obtener nombre de la playlist para el mensaje
            playlist_name = "playlist desconocida"
            for playlist in self.playlists:
                if playlist['id'] == playlist_id:
                    playlist_name = playlist['name']
                    break
            
            logger.info(f"Pista añadida a la playlist '{playlist_name}'")
            return True
        except Exception as e:
            logger.error(f"Error añadiendo pista a playlist: {e}")
            return False


class PlaylistSelectorDialog(QDialog):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        
        self.manager = manager
        self.playlists = manager.playlists
        self.selected_playlist = None
        self.spotify = manager.spotify
        
        self.init_ui()
    
    def init_ui(self):
        """Inicializa la interfaz de usuario"""
        self.setWindowTitle("Seleccionar Playlist de Spotify")
        self.setMinimumWidth(600)
        
        # Aplicar estilo oscuro a todo el diálogo
        self.setStyleSheet(f"""
            QDialog {{ 
                background-color: {DARK_BG}; 
                color: white;
            }}
            QLabel {{ 
                color: white; 
            }}
            QPushButton {{ 
                background-color: #282836; 
                color: white; 
                border: 1px solid #3a3a4e;
                border-radius: 4px;
                padding: 5px;
            }}
            QPushButton:hover {{ 
                background-color: #33333f; 
                border: 1px solid {SPOTIFY_GREEN};
            }}
        """)
        
        # Layout principal
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # Título
        title_label = QLabel("Añadir a playlist de Spotify:")
        title_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        main_layout.addWidget(title_label)
        
        # Información de la canción
        if self.manager.current_track:
            track_info = f"{self.manager.current_track['artist']} - {self.manager.current_track['title']}"
            track_label = QLabel(track_info)
            track_label.setFont(QFont("Arial", 10))
            track_label.setStyleSheet(f"color: {SPOTIFY_GREEN};")
            main_layout.addWidget(track_label)
        
        # Separador
        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #3a3a4e;")
        main_layout.addWidget(line)
        
        # Grid para los botones (4 columnas)
        from PyQt6.QtWidgets import QGridLayout
        grid_layout = QGridLayout()
        grid_layout.setSpacing(8)
        
        # Botón para crear nueva playlist (siempre con hotkey "0")
        create_layout = QHBoxLayout()
        
        hotkey_label = QLabel("[0]")
        hotkey_label.setFixedWidth(30)
        hotkey_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hotkey_label.setStyleSheet(f"font-weight: bold; color: {SPOTIFY_GREEN};")
        create_layout.addWidget(hotkey_label)
        
        create_button = QPushButton("Crear nueva playlist")
        create_button.setStyleSheet(f"""
            QPushButton {{ 
                background-color: #282836; 
                color: {SPOTIFY_GREEN}; 
                border: 1px solid {SPOTIFY_GREEN};
                border-radius: 4px;
                padding: 5px;
                font-weight: bold;
            }}
            QPushButton:hover {{ 
                background-color: #33333f; 
            }}
        """)
        create_button.clicked.connect(self.create_new_playlist)
        create_layout.addWidget(create_button)
        
        # Atajo de teclado para crear nueva playlist
        shortcut = QShortcut(QKeySequence("0"), self)
        shortcut.activated.connect(self.create_new_playlist)
        
        # Añadir botón de crear al layout principal
        main_layout.addLayout(create_layout)
        
        # Separador
        line2 = QWidget()
        line2.setFixedHeight(1)
        line2.setStyleSheet("background-color: #3a3a4e;")
        main_layout.addWidget(line2)
        
        # Crear botones para las playlists en grid
        for i, playlist in enumerate(self.playlists):
            # Posición en el grid (4 columnas)
            row = i // 4
            col = i % 4
            
            # Calcular el índice de hotkey (empezando desde 1 ya que 0 es para crear)
            hotkey_idx = i + 1
            
            if hotkey_idx < len(HOTKEYS):  # Asignar hotkey solo si hay tecla disponible
                hotkey = HOTKEYS[hotkey_idx].upper()
                
                # Crear widget contenedor
                container = QWidget()
                container_layout = QHBoxLayout(container)
                container_layout.setContentsMargins(0, 0, 0, 0)
                container_layout.setSpacing(2)
                
                # Botón de hotkey
                hotkey_label = QLabel(f"[{hotkey}]")
                hotkey_label.setFixedWidth(25)
                hotkey_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                hotkey_label.setStyleSheet(f"font-weight: bold; color: {SPOTIFY_GREEN};")
                container_layout.addWidget(hotkey_label)
                
                # Botón de playlist
                button = QPushButton(playlist['name'])
                button.clicked.connect(lambda checked, pid=playlist['id']: self.select_playlist(pid))
                container_layout.addWidget(button)
                
                # Añadir al grid
                grid_layout.addWidget(container, row, col)
                
                # Añadir atajo de teclado
                shortcut = QShortcut(QKeySequence(hotkey), self)
                shortcut.activated.connect(lambda pid=playlist['id']: self.select_playlist(pid))
            else:
                # Sin hotkey para playlists adicionales
                button = QPushButton(playlist['name'])
                button.clicked.connect(lambda checked, pid=playlist['id']: self.select_playlist(pid))
                grid_layout.addWidget(button, row, col)
        
        # Añadir grid al layout principal
        main_layout.addLayout(grid_layout)
        
        # Espacio flexible
        main_layout.addStretch()
        
        # Botón de cancelar
        cancel_button = QPushButton("Cancelar")
        cancel_button.clicked.connect(self.reject)
        cancel_button.setStyleSheet("""
            QPushButton { 
                background-color: #282828; 
                color: #f0f0f0; 
                border: 1px solid #444444;
                padding: 8px;
            }
        """)
        main_layout.addWidget(cancel_button)
        
        # Configurar layout
        self.setLayout(main_layout)
    
    def create_new_playlist(self):
        """Crea una nueva playlist"""
        try:
            from PyQt6.QtWidgets import QInputDialog, QMessageBox
            
            # Solicitar nombre de la playlist
            playlist_name, ok = QInputDialog.getText(
                self, 
                "Crear nueva playlist", 
                "Nombre de la nueva playlist:"
            )
            
            if not ok or not playlist_name.strip():
                return
            
            # Crear la playlist
            if self.spotify:
                user = self.spotify.current_user()
                result = self.spotify.user_playlist_create(
                    user=user['id'],
                    name=playlist_name,
                    public=False,
                    description=f"Playlist creada el {datetime.now().strftime('%d/%m/%Y')} con spotify_add_song.py"
                )
                
                if result and 'id' in result:
                    # Añadir la canción a la nueva playlist
                    self.select_playlist(result['id'])
                    
                    # Mostrar confirmación
                    QMessageBox.information(
                        self,
                        "Playlist creada",
                        f"Playlist '{playlist_name}' creada correctamente y canción añadida"
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "Error",
                        "No se pudo crear la playlist"
                    )
            else:
                QMessageBox.warning(
                    self,
                    "Error",
                    "Cliente de Spotify no disponible"
                )
        
        except Exception as e:
            logger.error(f"Error creando playlist: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "Error",
                f"Error creando playlist: {str(e)}"
            )
    
    def select_playlist(self, playlist_id):
        """Selecciona una playlist y cierra el diálogo"""
        self.selected_playlist = playlist_id
        self.accept()


def main():
    """Función principal"""
    # Inicializar el gestor
    manager = SpotifyAddSong()
    
    # Inicializar Spotify
    if not manager.initialize_spotify():
        logger.error("No se pudo inicializar Spotify")
        return 1
    
    # Obtener información de la canción actual
    if not manager.get_current_track():
        logger.error("No se pudo obtener información de la canción actual")
        return 1
    
    # Obtener playlists
    playlists = manager.get_user_playlists()
    if not playlists:
        logger.error("No se encontraron playlists")
        return 1
    
    # Verificar si PyQt está disponible
    if not QT_AVAILABLE:
        logger.error("PyQt6 no está disponible, usando modo texto")
        # Implementar selección por consola como alternativa
        print("Selecciona una playlist para añadir la canción:")
        for i, playlist in enumerate(playlists):
            print(f"{i+1}. {playlist['name']}")
        
        try:
            selection = int(input("Número de playlist: ")) - 1
            if 0 <= selection < len(playlists):
                manager.add_track_to_playlist(playlists[selection]['id'])
                print(f"Canción añadida a '{playlists[selection]['name']}'")
            else:
                print("Selección no válida")
        except (ValueError, IndexError):
            print("Entrada no válida")
        
        return 0
    
    # Mostrar diálogo de selección
    app = QApplication(sys.argv)
    dialog = PlaylistSelectorDialog(manager)
    
    # Ejecutar el diálogo
    result = dialog.exec()
    
    # Procesar el resultado
    if result == QDialog.DialogCode.Accepted and dialog.selected_playlist:
        success = manager.add_track_to_playlist(dialog.selected_playlist)
        
        # Mostrar mensaje de resultado (podría ser una notificación o diálogo)
        if success:
            # Encontrar el nombre de la playlist
            playlist_name = "playlist seleccionada"
            for playlist in playlists:
                if playlist['id'] == dialog.selected_playlist:
                    playlist_name = playlist['name']
                    break
            
            # Usar notify-send si está disponible
            try:
                subprocess.run(["notify-send", "-u", "normal", "-t", "3000", 
                               f"Añadido a Spotify", 
                               f"{manager.current_track['artist']} - {manager.current_track['title']}\nAñadido a: {playlist_name}"])
            except:
                print(f"Canción añadida a '{playlist_name}'")
        else:
            # Notificar error
            try:
                subprocess.run(["notify-send", "-u", "critical", "-t", "3000", 
                               "Error", "No se pudo añadir la canción a la playlist"])
            except:
                print("Error: No se pudo añadir la canción a la playlist")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())