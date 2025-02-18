from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                            QLineEdit, QListWidget, QComboBox, QMessageBox,
                            QListWidgetItem)
from PyQt6.QtCore import Qt
from base_module import BaseModule
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from typing import Dict
import webbrowser
import os
from pathlib import Path
import traceback
import json

class SpotifyPlaylistManager(BaseModule):
    def __init__(self, client_id: str, client_secret: str, cache_path: str = None):
        super().__init__()
        
        if cache_path is None:
            cache_path = str(Path.home() / ".cache" / "spotify_token.txt")
            
        self.setup_spotify(client_id, client_secret, cache_path)
        self.playlists = {}
        
        # Inicializar la UI después de la configuración básica
        self.init_ui()
        self.load_playlists()


    def setup_spotify(self, client_id: str, client_secret: str, cache_path: str):
        """Configurar cliente de Spotify con manejo de token"""
        try:
            scope = "playlist-modify-public playlist-modify-private playlist-read-private playlist-read-collaborative"
            self.sp_oauth = SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri='http://127.0.0.1:8090',
                scope=scope,
                open_browser=False,
                cache_path=cache_path
            )
            
            # Intentar obtener token existente
            token_info = self.sp_oauth.get_cached_token()
            
            if not token_info:
                auth_url = self.sp_oauth.get_authorize_url()
                QMessageBox.information(
                    self,
                    "Autorización Spotify",
                    f"Por favor visita esta URL para autorizar la aplicación:\n\n{auth_url}\n\n"
                    "Después de autorizar, copia la URL completa aquí:"
                )
                
                response_url = input("Pega la URL completa aquí: ").strip()
                code = self.sp_oauth.parse_response_code(response_url)
                token_info = self.sp_oauth.get_access_token(code)
            
            self.sp = spotipy.Spotify(auth=token_info['access_token'])
            self.user_id = self.sp.current_user()['id']
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error de autenticación con Spotify: {str(e)}")
            raise



    def refresh_token(self):
        """Renovar token si es necesario"""
        try:
            token_info = self.sp_oauth.get_cached_token()
            if self.sp_oauth.is_token_expired(token_info):
                token_info = self.sp_oauth.refresh_access_token(token_info['refresh_token'])
                self.sp = spotipy.Spotify(auth=token_info['access_token'])
                return True
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error renovando token: {str(e)}")
            return False


    def api_call_with_retry(self, func, *args, **kwargs):
        """Ejecutar llamada API con reintento si el token expira"""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if "token" in str(e).lower() and self.refresh_token():
                return func(*args, **kwargs)
            raise



    def init_ui(self):
        """Initialize the user interface"""
        # Verificar si los widgets ya existen
        if hasattr(self, 'playlist_list'):
            print("La UI ya está inicializada, saltando init_ui()")
            return
        
        layout = self.layout()
        if not layout:
            layout = QVBoxLayout()
            self.setLayout(layout)
        
        # Playlists section
        print("Creando playlist_list")
        self.playlist_list = QListWidget(self)
        self.playlist_list.setMinimumHeight(200)
        layout.addWidget(self.playlist_list)
        
        # Search section
        search_container = QWidget(self)
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        
        self.search_input = QLineEdit(search_container)
        self.search_input.setPlaceholderText("Buscar canción o artista...")
        self.search_button = QPushButton("Buscar", search_container)
        
        self.search_button.clicked.connect(self.search_tracks)
        self.search_input.returnPressed.connect(self.search_tracks)
        
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_button)
        layout.addWidget(search_container)
        
        # Search results
        self.search_results = QListWidget(self)
        self.search_results.setMinimumHeight(200)
        layout.addWidget(self.search_results)
        
        # New playlist section
        playlist_container = QWidget(self)
        new_playlist_layout = QHBoxLayout(playlist_container)
        new_playlist_layout.setContentsMargins(0, 0, 0, 0)
        
        self.new_playlist_input = QLineEdit(playlist_container)
        self.new_playlist_input.setPlaceholderText("Nueva playlist...")
        self.new_playlist_button = QPushButton("Crear Playlist", playlist_container)
        
        self.new_playlist_button.clicked.connect(self.create_playlist)
        self.new_playlist_input.returnPressed.connect(self.create_playlist)
        
        new_playlist_layout.addWidget(self.new_playlist_input)
        new_playlist_layout.addWidget(self.new_playlist_button)
        layout.addWidget(playlist_container)
        
        # Playlist selector
        selector_container = QWidget(self)
        add_to_playlist_layout = QHBoxLayout(selector_container)
        add_to_playlist_layout.setContentsMargins(0, 0, 0, 0)
        
        self.playlist_selector = QComboBox(selector_container)
        self.add_song_button = QPushButton("Añadir a Playlist", selector_container)
        self.add_song_button.clicked.connect(self.add_selected_song)
        
        add_to_playlist_layout.addWidget(self.playlist_selector)
        add_to_playlist_layout.addWidget(self.add_song_button)
        layout.addWidget(selector_container)

    def load_playlists(self):
        """Load user playlists from Spotify"""
        print("Comenzando carga de playlists...")
        try:
            results = self.api_call_with_retry(self.sp.current_user_playlists)
            
            self.playlist_list.clear()
            self.playlist_selector.clear()
            self.playlists.clear()
            
            for playlist in results['items']:
                self.playlists[playlist['name']] = playlist['id']
                
                # Create widget for playlist item
                item_widget = QWidget(self.playlist_list)  # Establecer padre
                item_layout = QHBoxLayout(item_widget)
                item_layout.setContentsMargins(5, 5, 5, 5)
                
                # Create playlist button
                playlist_button = QPushButton(playlist['name'], item_widget)  # Establecer padre
                playlist_button.setStyleSheet("""
                    QPushButton {
                        text-align: left;
                        border: none;
                        padding: 5px;
                    }
                    QPushButton:hover {
                        background-color: rgba(255, 255, 255, 0.1);
                    }
                """)
                
                playlist_url = playlist['external_urls']['spotify']
                # Crear una función de cierre para mantener la referencia
                def create_open_handler(url=playlist_url):
                    return lambda: self.open_spotify_url(url)
                
                playlist_button.clicked.connect(create_open_handler())
                
                # Create delete button
                delete_button = QPushButton("✖", item_widget)  # Establecer padre
                delete_button.setFixedWidth(30)
                delete_button.setStyleSheet("""
                    QPushButton {
                        border: none;
                        padding: 5px;
                    }
                    QPushButton:hover {
                        background-color: rgba(255, 0, 0, 0.2);
                    }
                """)
                
                # Crear una función de cierre para mantener la referencia
                def create_delete_handler(pid=playlist['id']):
                    return lambda: self.delete_playlist(pid)
                
                delete_button.clicked.connect(create_delete_handler())
                
                item_layout.addWidget(playlist_button, stretch=1)
                item_layout.addWidget(delete_button)
                
                # Add to list widget
                item = QListWidgetItem(self.playlist_list)  # Establecer padre
                item.setSizeHint(item_widget.sizeHint())
                self.playlist_list.addItem(item)
                self.playlist_list.setItemWidget(item, item_widget)
                
                # Add to combo box
                self.playlist_selector.addItem(playlist['name'])
                
            print(f"Playlists cargadas: {len(self.playlists)}")
            
        except Exception as e:
            print(f"Error cargando playlists: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            QMessageBox.critical(self, "Error", f"Error cargando playlists: {str(e)}")

    def open_spotify_url(self, url):
        """Open URL using xdg-open"""
        try:
            import subprocess
            subprocess.Popen(['xdg-open', url])
        except Exception as e:
            print(f"Error abriendo URL: {str(e)}")
            QMessageBox.critical(self, "Error", f"Error abriendo URL: {str(e)}")

    def search_tracks(self):
        """Search for tracks on Spotify"""
        print("Iniciando búsqueda...")  # Debug
        query = self.search_input.text()
        query = query.strip()
        print(f"Término de búsqueda: '{query}'")  # Debug con comillas para ver espacios
        
        if not query:
            print("Búsqueda vacía, retornando")  # Debug
            return
            
        try:
            print(f"Realizando búsqueda en Spotify para: {query}")  # Debug
            results = self.api_call_with_retry(self.sp.search, q=query, type='track', limit=10)
            
            if not results or 'tracks' not in results:
                print("No se encontraron resultados")  # Debug
                return
                
            self.search_results.clear()
            print(f"Encontrados {len(results['tracks']['items'])} resultados")  # Debug
            
            for track in results['tracks']['items']:
                artist_names = ", ".join(artist['name'] for artist in track['artists'])
                display_text = f"{track['name']} - {artist_names}"
                
                item = QListWidgetItem(display_text)
                item.setData(Qt.ItemDataRole.UserRole, track['id'])
                self.search_results.addItem(item)
                print(f"Añadido: {display_text}")  # Debug
                
        except Exception as e:
            print(f"Error en búsqueda: {str(e)}")  # Debug
            QMessageBox.critical(self, "Error", f"Error en la búsqueda: {str(e)}")

    def create_playlist(self):
        """Create a new Spotify playlist"""
        print("Botón crear playlist clickeado")  # Debug
        name = self.new_playlist_input.text().strip()
        print(f"Intentando crear playlist con nombre: [{name}]")  # Debug
        if not name:
            QMessageBox.warning(self, "Error", "Por favor introduce un nombre para la playlist")
            return
            
        try:
            self.sp.user_playlist_create(
                user=self.user_id,
                name=name,
                public=False,
                description="Creada desde Playlist Manager"
            )
            
            self.new_playlist_input.clear()
            self.load_playlists()
            QMessageBox.information(self, "Éxito", "Playlist creada correctamente")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error creando playlist: {str(e)}")


    def delete_playlist(self, playlist_id: str):
        """Delete a Spotify playlist"""
        try:
            self.sp.current_user_unfollow_playlist(playlist_id)
            self.load_playlists()
            QMessageBox.information(self, "Éxito", "Playlist eliminada correctamente")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error eliminando playlist: {str(e)}")

    def add_selected_song(self):
        """Add selected song to chosen playlist"""
        selected_items = self.search_results.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Error", "Por favor selecciona una canción")
            return
            
        track_id = selected_items[0].data(Qt.ItemDataRole.UserRole)
        playlist_name = self.playlist_selector.currentText()
        playlist_id = self.playlists.get(playlist_name)
        
        if not playlist_id:
            QMessageBox.warning(self, "Error", "Por favor selecciona una playlist")
            return
            
        try:
            self.sp.playlist_add_items(playlist_id, [f"spotify:track:{track_id}"])
            QMessageBox.information(self, "Éxito", "Canción añadida correctamente")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error añadiendo canción: {str(e)}")