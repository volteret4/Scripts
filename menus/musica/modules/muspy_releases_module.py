import sys
import os
import subprocess
import requests
import logging
import datetime
from base_module import BaseModule, THEMES
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, 
                             QLabel, QLineEdit, QMessageBox, QApplication, QFileDialog, QTableWidget, 
                             QTableWidgetItem, QHeaderView)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor, QTextDocument



# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MuspyArtistModule(BaseModule):
    def __init__(self, 
                muspy_username=None, 
                muspy_api_key=None, 
                muspy_id=None,
                artists_file=None,
                query_db_script_path=None,
                search_mbid_script_path=None,
                lastfm_username=None,
                parent=None, 
                db_path='music_database.db',
                theme='Tokyo Night', 
                *args, **kwargs):
        """
        Initialize the Muspy Artist Management Module
        
        Args:
            muspy_username (str, optional): Muspy username
            muspy_api_key (str, optional): Muspy API key
            artists_file (str, optional): Path to artists file
            query_db_script_path (str, optional): Path to MBID query script
            search_mbid_script_path (str, optional): Path to MBID search script
            parent (QWidget, optional): Parent widget
            theme (str, optional): UI theme
        """
        self.muspy_username = muspy_username
        self.muspy_api_key = muspy_api_key
        self.muspy_id = muspy_id
        # Intentar obtener el Muspy ID si no está configurado
        if not self.muspy_id or self.muspy_id == '' or self.muspy_id == 'None':
            self.get_muspy_id()
        self.base_url = "https://muspy.com/api/1"
        self.artists_file = artists_file
        self.query_db_script_path = query_db_script_path
        self.lastfm_username = lastfm_username
        self.db_path = db_path

        self.available_themes = kwargs.pop('temas', [])
        self.selected_theme = kwargs.pop('tema_seleccionado', theme)        
        
        super().__init__(parent, theme)
        

    def init_ui(self):
        """Initialize the user interface for Muspy artist management"""
        # Main vertical layout
        main_layout = QVBoxLayout(self)

        # Top section with search
        top_layout = QHBoxLayout()
        
        self.artist_input = QLineEdit()
        self.artist_input.setPlaceholderText("Enter artist name")
        self.artist_input.returnPressed.connect(self.search_and_get_releases)
        top_layout.addWidget(self.artist_input)

        self.search_button = QPushButton("Search Releases")
        self.search_button.clicked.connect(self.search_and_get_releases)
        top_layout.addWidget(self.search_button)

        main_layout.addLayout(top_layout)

        # Results area (will be replaced by table when getting releases)
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        main_layout.addWidget(self.results_text)

        # Bottom buttons layout
        bottom_layout = QHBoxLayout()
        
        self.load_artists_button = QPushButton("Load Artists")
        self.load_artists_button.clicked.connect(self.load_artists_from_file)
        bottom_layout.addWidget(self.load_artists_button)

        self.sync_artists_button = QPushButton("Sync Artists")
        self.sync_artists_button.clicked.connect(self.sync_artists_with_muspy)
        bottom_layout.addWidget(self.sync_artists_button)

        self.sync_lastfm_button = QPushButton("Sync Lastfm")
        self.sync_lastfm_button.clicked.connect(self.sync_lastfm_muspy)
        bottom_layout.addWidget(self.sync_lastfm_button)
        
        self.get_releases_button = QPushButton("Get My Releases")
        self.get_releases_button.clicked.connect(self.get_muspy_releases)
        bottom_layout.addWidget(self.get_releases_button)
        
        self.get_new_releases_button = QPushButton("Get New Releases")
        self.get_new_releases_button.clicked.connect(self.get_new_releases)
        bottom_layout.addWidget(self.get_new_releases_button)
        
        self.get_my_releases_button = QPushButton("Get All My Releases")
        self.get_my_releases_button.clicked.connect(self.get_all_my_releases)
        bottom_layout.addWidget(self.get_my_releases_button)

        main_layout.addLayout(bottom_layout)


    def get_muspy_id(self):
        """
        Obtiene el ID de usuario de Muspy si no está configurado
        
        Returns:
            str: ID de usuario de Muspy
        """
        if not self.muspy_id and self.muspy_username and self.muspy_api_key:
            try:
                url = f"{self.base_url}/user"
                auth = (self.muspy_username, self.muspy_api_key)
                
                response = requests.get(url, auth=auth)
                
                if response.status_code == 200:
                    # La API devuelve información del usuario en el formato JSON
                    # Intentamos obtener el ID directamente de la respuesta
                    user_info_url = f"{self.base_url}/user"
                    user_response = requests.get(user_info_url, auth=auth)
                    
                    if user_response.status_code == 200:
                        user_data = user_response.json()
                        if 'userid' in user_data:
                            self.muspy_id = user_data['userid']
                            print(f"Muspy ID obtenido: {self.muspy_id}")
                            return self.muspy_id
                        else:
                            logger.error("No se encontró 'userid' en la respuesta JSON")
                    else:
                        logger.error(f"Error al obtener información del usuario: {user_response.status_code}")
                else:
                    logger.error(f"Error en la llamada a la API de Muspy: {response.status_code}")
            except Exception as e:
                logger.error(f"Error al obtener Muspy ID: {e}")
        
        return self.muspy_id


    def load_artists_from_file(self):
        """Load artists from a text file"""
        if not self.artists_file:
            self.artists_file = QFileDialog.getOpenFileName(self, "Select Artists File", "", "Text Files (*.txt)")[0]
        
        if not self.artists_file:
            return

        try:
            with open(self.artists_file, 'r', encoding='utf-8') as f:
                self.artists = [line.strip() for line in f if line.strip()]
            
            self.results_text.clear()
            self.results_text.append(f"Loaded {len(self.artists)} artists from {self.artists_file}\n")

        except Exception as e:
            self.results_text.append(f"Error loading file: {e}\n")


    def search_and_get_releases(self):
        """Search for artist releases without adding to Muspy"""
        artist_name = self.artist_input.text().strip()
        if not artist_name:
            QMessageBox.warning(self, "Error", "Please enter an artist name")
            return

        # Ensure results_text is visible
        self.results_text.show()

        # Get MBID for the artist
        mbid = self.get_mbid_artist_searched(artist_name)
        
        if not mbid:
            QMessageBox.warning(self, "Error", f"Could not find MBID for {artist_name}")
            return
        
        # Get releases for the artist
        self.get_artist_releases(mbid, artist_name)
        
        # Store the current artist for possible addition later
        self.current_artist = {"name": artist_name, "mbid": mbid}

    def get_artist_releases(self, mbid, artist_name=None):
        """
        Get future releases for a specific artist by MBID
        
        Args:
            mbid (str): MusicBrainz ID of the artist
            artist_name (str, optional): Name of the artist for display
        """
        if not self.muspy_username or not self.muspy_api_key:
            QMessageBox.warning(self, "Error", "Muspy configuration not available")
            return

        try:
            url = f"{self.base_url}/releases"
            params = {"mbid": mbid}
            auth = (self.muspy_username, self.muspy_api_key)
            
            response = requests.get(url, auth=auth, params=params)
            
            if response.status_code == 200:
                all_releases = response.json()
                
                # Filter for future releases
                today = datetime.date.today().strftime("%Y-%m-%d")
                future_releases = [release for release in all_releases if release.get('date', '0000-00-00') >= today]
                
                if not future_releases:
                    self.results_text.append(f"No future releases found for {artist_name or 'Unknown'}")
                    return
                
                # Log releases for debugging
                logger.info(f"Received {len(future_releases)} future releases out of {len(all_releases)} total")
                if future_releases:
                    logger.info(f"Sample release data: {future_releases[0]}")
                
                # Display releases in table
                table = self.display_releases_table(future_releases)
                
                # Add a button to follow this artist
                self.add_follow_button = QPushButton(f"Follow {artist_name}")
                self.add_follow_button.clicked.connect(self.follow_current_artist)
                self.layout().insertWidget(self.layout().count() - 1, self.add_follow_button)
            else:
                self.results_text.append(f"Error retrieving releases: {response.status_code} - {response.text}")
        
        except Exception as e:
            self.results_text.append(f"Connection error with Muspy: {e}")
            logger.error(f"Error getting releases: {e}")

    def follow_current_artist(self):
        """Follow the currently displayed artist"""
        if hasattr(self, 'current_artist') and self.current_artist:
            success = self.add_artist_to_muspy(self.current_artist["mbid"], self.current_artist["name"])
            if success:
                self.add_follow_button.setText(f"Following {self.current_artist['name']}")
                self.add_follow_button.setEnabled(False)
        else:
            QMessageBox.warning(self, "Error", "No artist currently selected")

    def get_new_releases(self):
        """
        Retrieve new releases using the Muspy API endpoint for all users
        
        Displays new releases in a QTableWidget
        """
        try:
            # This endpoint doesn't require authentication for general releases
            url = f"{self.base_url}/releases"
            
            response = requests.get(url)
            
            if response.status_code == 200:
                all_releases = response.json()
                
                # Filter for future releases
                today = datetime.date.today().strftime("%Y-%m-%d")
                future_releases = [release for release in all_releases if release.get('date', '0000-00-00') >= today]
                
                if not future_releases:
                    QMessageBox.information(self, "No New Releases", "No new releases available")
                    return
                
                # Display releases in table
                self.display_releases_table(future_releases)
            else:
                QMessageBox.warning(self, "Error", f"Error retrieving new releases: {response.text}")
        
        except Exception as e:
            QMessageBox.warning(self, "Connection Error", f"Connection error with Muspy: {e}")

    def sync_artists_with_muspy(self):
        """Synchronize artists from file with Muspy"""
        if not hasattr(self, 'artists') or not self.artists:
            QMessageBox.warning(self, "Error", "No artists loaded. First load a file.")
            return

        # Limpiar solo una vez al principio
        self.results_text.clear()
        self.results_text.append("Comenzando sincronización de artistas...\n")
        
        # Mostrar una barra de progreso simple
        total_artists = len(self.artists)
        self.results_text.append(f"Total artistas a sincronizar: {total_artists}\n")
        self.results_text.append("Progreso: [" + "-" * 50 + "]\n")
        
        # Variables para llevar el conteo
        successful_adds = 0
        failed_adds = 0
        duplicates = 0
        
        # Procesar por lotes para no sobrecargar la interfaz
        for i, artist_name in enumerate(self.artists):
            try:
                # Obtener el MBID
                mbid = self.get_mbid_artist_searched(artist_name)
                
                # Intentar añadir el artista si se encontró el MBID
                if mbid:
                    response = self.add_artist_to_muspy_silent(mbid, artist_name)
                    if response == 1:
                        successful_adds += 1
                    elif response == 0:
                        duplicates += 1
                    else:
                        failed_adds += 1
                else:
                    failed_adds += 1
                
                # Actualizar la barra de progreso cada 5 artistas o al final
                if (i + 1) % 5 == 0 or i == total_artists - 1:
                    progress = int((i + 1) / total_artists * 50)
                    self.results_text.clear()
                    self.results_text.append(f"Sincronizando artistas... {i + 1}/{total_artists}\n")
                    self.results_text.append(f"Progreso: [" + "#" * progress + "-" * (50 - progress) + "]\n")
                    self.results_text.append(f"Añadidos: {successful_adds}, Duplicados: {duplicates}, Fallos: {failed_adds}\n")
                    QApplication.processEvents()  # Permite que la interfaz se actualice
            
            except Exception as e:
                logger.error(f"Error al sincronizar artista {artist_name}: {e}")
                failed_adds += 1
        
        # Mostrar el resumen final
        self.results_text.clear()
        self.results_text.append(f"Sincronización completada\n")
        self.results_text.append(f"Total artistas procesados: {total_artists}\n")
        self.results_text.append(f"Añadidos correctamente: {successful_adds}\n")
        self.results_text.append(f"Duplicados (ya existían): {duplicates}\n")
        self.results_text.append(f"Fallos: {failed_adds}\n")

    def add_artist_to_muspy_silent(self, mbid=None, artist_name=None):
        """
        Versión silenciosa de add_artist_to_muspy que no escribe en la interfaz
        
        Args:
            mbid (str, optional): MusicBrainz ID of the artist
            artist_name (str, optional): Name of the artist for logging
        
        Returns:
            int: 1 para éxito, 0 para duplicado, -1 para error
        """
        if not self.muspy_username or not self.muspy_api_key or not self.muspy_id:
            return -1

        if not mbid or not (len(mbid) == 36 and mbid.count('-') == 4):
            return -1

        try:
            # Follow artist by MBID
            url = f"{self.base_url}/artists/{self.muspy_id}/{mbid}"
            auth = (self.muspy_username, self.muspy_api_key)
            
            response = requests.put(url, auth=auth)
            
            if response.status_code in [200, 201]:
                # Verificar si ya existía el artista
                if "already exists" in response.text.lower():
                    return 0  # Duplicado
                return 1  # Éxito
            else:
                return -1  # Error
        except Exception:
            return -1  # Error

    def get_mbid_artist_searched(self, artist_name):
        """
        Retrieve the MusicBrainz ID for a given artist
        
        Args:
            artist_name (str): Name of the artist to search
        
        Returns:
            str or None: MusicBrainz ID of the artist
        """
        if artist_name is None:
            return None
        
        try:
            #First attempt: query existing database
            if self.query_db_script_path:
                # Add full absolute paths
                full_db_path = os.path.expanduser(self.db_path) if self.db_path else None
                full_script_path = os.path.expanduser(self.query_db_script_path)
                
                # Print out the actual paths being used
                self.results_text.append(f"Consultando base de datos para {artist_name}...")
                logger.info(f"Script Path: {full_script_path}")
                logger.info(f"DB Path: {full_db_path}")
                logger.info(f"Artist: {artist_name}")

                mbid_result = subprocess.run(
                    ['python', full_script_path, "--db", full_db_path, "--artist", artist_name, "--mbid"], 
                    capture_output=True, 
                    text=True
                )
                
                # Check if the output contains an error message
                if "Error: no such table" in mbid_result.stderr:
                    self.results_text.append("Error: La tabla 'artists' no existe en la base de datos.")
                    logger.error(f"Database error: {mbid_result.stderr}")
                elif mbid_result.returncode != 0:
                    self.results_text.append(f"Error en la consulta: {mbid_result.stderr}")
                    logger.error(f"Query error: {mbid_result.stderr}")
                elif mbid_result.stdout.strip():
                    # Limpiar el resultado eliminando comillas y espacios en blanco
                    mbid = mbid_result.stdout.strip().strip('"\'')
                    # Verify that the MBID looks valid (should be a UUID)
                    if len(mbid) == 36 and mbid.count('-') == 4:
                        self.results_text.append(f"MBID encontrado en la base de datos: {mbid}")
                        return mbid
                    else:
                        self.results_text.append(f"MBID inválido encontrado: {mbid}")
                        logger.warning(f"Invalid MBID format: {mbid}")
                else:
                    self.results_text.append("No se encontró MBID en la base de datos.")
            
            # Second attempt: search for MBID if first method fails
            # if self.query_db_script_path:
            #     self.results_text.append(f"Buscando MBID para {artist_name} en MusicBrainz...")
            #     full_search_script_path = os.path.expanduser(self.query_db_script_path)
                
            #     mbid_search_result = subprocess.run(
            #         ['python', full_search_script_path, "--db", full_db_path if full_db_path else "", "--artist", artist_name, "--mbid"], 
            #         capture_output=True, 
            #         text=True
            #     )
                
            #     if mbid_search_result.returncode == 0 and mbid_search_result.stdout.strip():
            #         # Limpiar el resultado eliminando comillas y espacios en blanco
            #         mbid = mbid_search_result.stdout.strip().strip('"\'')
            #         if len(mbid) == 38 and mbid.count('-') == 4:
            #             self.results_text.append(f"MBID encontrado en MusicBrainz: {mbid}")
            #             return mbid
            #         else:
            #             self.results_text.append(f"MBID inválido recibido de MusicBrainz: {mbid}")
            #             logger.warning(f"Invalid MBID format from search: {mbid}")
            #     else:
            #         self.results_text.append(f"No se pudo encontrar MBID: {mbid_search_result.stderr}")
            #         logger.error(f"MBID search error: {mbid_search_result.stderr}")
            
            # self.results_text.append(f"No se pudo encontrar MBID para {artist_name}")
            # return None
        
        except subprocess.TimeoutExpired:
            self.results_text.append("La ejecución del script expiró")
            logger.error("Script execution timed out")
        except PermissionError:
            self.results_text.append(f"Permiso denegado al ejecutar el script")
            logger.error(f"Permission denied running script: {self.query_db_script_path}")
        except FileNotFoundError as e:
            self.results_text.append(f"Script o base de datos no encontrados: {e}")
            logger.error(f"File not found: {e}")
        except Exception as e:
            self.results_text.append(f"Error inesperado: {e}")
            logger.error(f"Unexpected error getting MBID for {artist_name}: {e}")
        
        return None
 
    def add_artist_to_muspy(self, mbid=None, artist_name=None):
        """
        Add/Follow an artist to Muspy using their MBID or name
        
        Args:
            mbid (str, optional): MusicBrainz ID of the artist
            artist_name (str, optional): Name of the artist for logging
        
        Returns:
            bool: True if artist was successfully added, False otherwise
        """
        if not self.muspy_username or not self.muspy_api_key:
            QMessageBox.warning(self, "Error", "Configuración de Muspy no disponible")
            return False

        if not mbid:
            message = f"No se pudo agregar {artist_name or 'Desconocido'} a Muspy: MBID no disponible"
            self.results_text.append(message)
            logger.error(message)
            return False

        # Validate MBID format (should be a UUID)
        if not (len(mbid) == 36 and mbid.count('-') == 4):
            message = f"MBID inválido para {artist_name or 'Desconocido'}: {mbid}"
            self.results_text.append(message)
            logger.error(message)
            return False

        try:
            # Ensure results_text is visible
            self.results_text.show()

            # Follow artist by MBID
            url = f"{self.base_url}/artists/{self.muspy_id}/{mbid}"
            
            # Usar autenticación básica en lugar de token
            auth = (self.muspy_username, self.muspy_api_key)
            
            logger.info(f"Agregando artista a Muspy: {artist_name} (MBID: {mbid})")
            response = requests.put(url, auth=auth)
            
            if response.status_code in [200, 201]:
                message = f"Artista {artist_name or 'Desconocido'} agregado a Muspy"
                self.results_text.append(message)
                logger.info(message)
                return True
            else:
                message = f"No se pudo agregar {artist_name or 'Desconocido'} a Muspy: {response.status_code} - {response.text}"
                self.results_text.append(message)
                logger.error(message)
                return False
        except Exception as e:
            message = f"Error al agregar a Muspy: {e}"
            self.results_text.append(message)
            logger.error(message)
            return False

    def sync_lastfm_muspy(self):
        """Synchronize Last.fm artists with Muspy"""
        if not self.lastfm_username:
            QMessageBox.warning(self, "Error", "Last.fm username not configured")
            return

        try:
            # Import artists via last.fm
            url = f"{self.base_url}/{self.muspy_username}"
            method = 'PUT'
            data = {
                'import': 'last.fm',
                'username': self.lastfm_username,
                'count': 10,
                'period': 'overall'
            }

            # Usar autenticación básica en lugar de token
            auth = (self.muspy_username, self.muspy_api_key)
            
            # Use the appropriate request method
            if method == 'PUT':
                response = requests.put(url, auth=auth, json=data)
            else:
                response = requests.post(url, auth=auth, json=data)
            
            if response.status_code in [200, 201]:
                self.results_text.append(f"Synchronized artists from Last.fm account {self.lastfm_username}\n")
                return True
            else:
                self.results_text.append(f"Could not sync Last.fm artists: {response.text}\n")
                return False
        except Exception as e:
            self.results_text.append(f"Error syncing with Muspy: {e}\n")
            return False

    def get_muspy_releases(self):
        """
        Retrieve future releases from Muspy for the current user
        
        Displays future releases in a QTableWidget
        """
        if not self.muspy_username or not self.muspy_api_key:
            QMessageBox.warning(self, "Error", "Muspy configuration not available")
            return

        try:
            url = f"{self.base_url}/releases"
            # Usar autenticación básica en lugar de token
            auth = (self.muspy_username, self.muspy_api_key)
            
            response = requests.get(url, auth=auth)
            
            if response.status_code == 200:
                all_releases = response.json()
                
                # Filter for future releases
                today = datetime.date.today().strftime("%Y-%m-%d")
                future_releases = [release for release in all_releases if release.get('date', '0000-00-00') >= today]
                
                if not future_releases:
                    QMessageBox.information(self, "No Future Releases", "No upcoming releases in Muspy")
                    return
                
                # Display releases in table
                self.display_releases_table(future_releases)
            else:
                QMessageBox.warning(self, "Error", f"Error retrieving releases: {response.text}")
        
        except Exception as e:
            QMessageBox.warning(self, "Connection Error", f"Connection error with Muspy: {e}")
   
   
   
    def get_all_my_releases(self):
        """
        Retrieve all releases for the user's artists using the user ID
        
        Handles pagination to get all releases even when there are many artists
        """
        if not self.muspy_id:
            QMessageBox.warning(self, "Error", "Muspy ID not available. Please check your configuration.")
            return

        try:
            # Show progress in the text area
            self.results_text.clear()
            self.results_text.show()
            self.results_text.append("Fetching your releases... This might take a while.")
            QApplication.processEvents()  # Update UI
            
            all_releases = []
            offset = 0
            limit = 100  # Maximum allowed by API
            more_releases = True
            
            while more_releases:
                # Create URL with user ID, offset, and limit
                url = f"{self.base_url}/releases/{self.muspy_id}"
                params = {
                    "offset": offset,
                    "limit": limit
                }
                
                self.results_text.append(f"Fetching releases {offset+1}-{offset+limit}...")
                QApplication.processEvents()  # Update UI
                
                # Make the request
                response = requests.get(url, params=params)
                
                if response.status_code == 200:
                    batch_releases = response.json()
                    
                    if not batch_releases:
                        # No more releases to fetch
                        more_releases = False
                    else:
                        # Add to our collection and update offset
                        all_releases.extend(batch_releases)
                        offset += limit
                        
                        # Progress update
                        self.results_text.append(f"Found {len(all_releases)} releases so far.")
                        QApplication.processEvents()  # Update UI
                        
                        # If we got fewer than the limit, we've reached the end
                        if len(batch_releases) < limit:
                            more_releases = False
                else:
                    self.results_text.append(f"Error retrieving releases: {response.status_code} - {response.text}")
                    more_releases = False
            
            # Filter for future releases
            today = datetime.date.today().strftime("%Y-%m-%d")
            future_releases = [release for release in all_releases if release.get('date', '0000-00-00') >= today]
            
            self.results_text.append(f"Processing complete! Found {len(future_releases)} upcoming releases out of {len(all_releases)} total releases.")
            
            if not future_releases:
                self.results_text.append("No upcoming releases found for your artists.")
                return
            
            # Sort releases by date
            future_releases.sort(key=lambda x: x.get('date', '9999-99-99'))
            
            # Display releases in table
            self.display_releases_table(future_releases)
        
        except Exception as e:
            self.results_text.append(f"Connection error with Muspy: {str(e)}")
            logger.error(f"Error getting all releases: {e}")



    def display_releases_table(self, releases):
        """
        Display releases in a QTableWidget for better rendering
        
        Args:
            releases (list): List of release dictionaries to display
        """
        # First, clear any existing table and follow button
        for i in reversed(range(self.layout().count())): 
            item = self.layout().itemAt(i)
            if item is not None:
                widget = item.widget()
                if widget is not None and (isinstance(widget, QTableWidget) or (hasattr(self, 'add_follow_button') and widget == self.add_follow_button)):
                    self.layout().removeItem(item)
                    widget.deleteLater()

        # Create the table
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(['Artist', 'Release Title', 'Type', 'Date', 'Details'])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        # Add a label showing how many releases we're displaying
        count_label = QLabel(f"Showing {len(releases)} upcoming releases")
        self.layout().insertWidget(self.layout().count() - 1, count_label)
        
        # Configure number of rows
        table.setRowCount(len(releases))
        
        # Fill the table
        for row, release in enumerate(releases):
            artist = release.get('artist', {})
            
            # Create items for each column
            artist_name_item = QTableWidgetItem(artist.get('name', 'Unknown'))
            if artist.get('disambiguation'):
                artist_name_item.setToolTip(artist.get('disambiguation'))
            table.setItem(row, 0, artist_name_item)
            
            # Title with proper casing and full information
            title_item = QTableWidgetItem(release.get('title', 'Untitled'))
            if release.get('comments'):
                title_item.setToolTip(release.get('comments'))
            table.setItem(row, 1, title_item)
            
            # Release type (Album, EP, etc.)
            type_item = QTableWidgetItem(release.get('type', 'Unknown').title())
            table.setItem(row, 2, type_item)
            
            # Date with color highlighting for upcoming releases
            date_str = release.get('date', 'No date')
            date_item = QTableWidgetItem(date_str)
            
            # Highlight dates that are within the next month
            try:
                release_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                today = datetime.date.today()
                one_month = today + datetime.timedelta(days=30)
                
                if release_date <= today + datetime.timedelta(days=7):
                    # Coming very soon - red
                    date_item.setBackground(QColor(255, 200, 200))
                elif release_date <= one_month:
                    # Coming in a month - yellow
                    date_item.setBackground(QColor(255, 255, 200))
            except ValueError:
                # If date parsing fails, don't color
                pass
                
            table.setItem(row, 3, date_item)
            
            # Additional details
            details = []
            if release.get('format'):
                details.append(f"Format: {release.get('format')}")
            if release.get('tracks'):
                details.append(f"Tracks: {release.get('tracks')}")
            if release.get('country'):
                details.append(f"Country: {release.get('country')}")
            
            details_item = QTableWidgetItem("; ".join(details) if details else "")
            table.setItem(row, 4, details_item)
        
        # Resize rows to content
        table.resizeRowsToContents()
        
        # Make the table sortable
        table.setSortingEnabled(True)
        
        # Hide the text edit and add the table to the layout
        self.results_text.hide()
        # Insert the table just above the bottom buttons
        self.layout().insertWidget(self.layout().count() - 1, table)
        return table



def main():
    """Main function to run the Muspy Artist Management Module"""
    app = QApplication(sys.argv)
    
    # Parse command-line arguments
    muspy_username = None
    muspy_api_key = None
    artists_file = None
    query_db_script_path = None
    #search_mbid_script_path = None
    db_path = None
    for arg in sys.argv[1:]:
        if arg.startswith('--muspy-username='):
            muspy_username = arg.split('=')[1]
        elif arg.startswith('--muspy-api-key='):
            muspy_api_key = arg.split('=')[1]
        elif arg.startswith('--artists-file='):
            artists_file = arg.split('=')[1]
        elif arg.startswith('--query-db-script-path='):
            query_db_script_path = arg.split('=')[1]
        # elif arg.startswith('--search-mbid-script-path='):
        #     search_mbid_script_path = arg.split('=')[1]
        elif arg.startswith('--lastfm-username='):
            lastfm_username = arg.split('=')[1]
        elif arg.startswith('--db-path='):
            db_path = arg.split('=')[1]

    # Create module instance
    module = MuspyArtistModule(
        muspy_username=muspy_username, 
        muspy_api_key=muspy_api_key,
        artists_file=artists_file,
        query_db_script_path=query_db_script_path,
        #search_mbid_script_path=search_mbid_script_path,
        lastfm_username=lastfm_username,
        db_path=db_path
    )
    module.show()
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()






    