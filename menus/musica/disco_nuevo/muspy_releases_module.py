import sys
import os
from base_module import BaseModule, THEMES
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, 
                             QLabel, QLineEdit, QMessageBox, QApplication, QFileDialog, QTableWidget, 
                             QTableWidgetItem, QHeaderView)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor
import requests
import musicbrainzngs
import logging
from datetime import datetime, date
# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MusicReleasesModule(BaseModule):
    def __init__(self, 
                 muspy_username=None, 
                 muspy_api_key=None, 
                 artists_file=None,
                 parent = None,
                 theme = 'Tokyo Night',
                 query_db_script_path=None,
                 search_mbid_script_path=None, 
                 *args, **kwargs):
        self.muspy_username = muspy_username
        self.muspy_api_key = muspy_api_key
        self.artists_file = artists_file
        # Store script paths as instance attributes
        self.query_db_script_path = query_db_script_path
        self.search_mbid_script_path = search_mbid_script_path

        # Configurar MusicBrainz
        musicbrainzngs.set_useragent("MusicReleasesTracker", "1.0", "your_email@example.com")
        
        super().__init__(parent, theme)

    def apply_theme(self, theme_name=None):
        super().apply_theme(theme_name)

    def init_ui(self):
        """Método para inicializar la interfaz de usuario"""
        layout = QVBoxLayout(self)

        # Agregar QTextEdit para mostrar resultados
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)  # Hacer que sea solo de lectura
        layout.addWidget(self.results_text)

        # Fila de búsqueda manual
        manual_search_layout = QHBoxLayout()
        
        self.artist_input = QLineEdit()
        self.artist_input.setPlaceholderText("Introduce nombre del artista")
        
        # Añadir evento de Enter para buscar
        self.artist_input.returnPressed.connect(self.search_manual_artist)
        manual_search_layout.addWidget(self.artist_input)

        # Botón de búsqueda manual
        self.search_button = QPushButton("Buscar Artista")
        self.search_button.clicked.connect(self.search_manual_artist)
        manual_search_layout.addWidget(self.search_button)

        # Botón de guardar artista
        self.save_artist_button = QPushButton("Guardar Artista")
        self.save_artist_button.clicked.connect(
            lambda: self.add_artist_to_muspy(
                self.get_mbid_artist_searched(self.artist_input.text())
            )
        )
        manual_search_layout.addWidget(self.save_artist_button)

        layout.addLayout(manual_search_layout)

        # Tabla para mostrar resultados
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(6)  # Título, Fecha, Tipo, Sello, Botón 1, Botón 2, URL
        self.results_table.setHorizontalHeaderLabels(["Título", "Fecha", "Tipo", "Sello Discográfico", "Acción 1", "Acción 2", "URL"])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.results_table)

        # Botón para obtener releases de Muspy
        self.muspy_releases_button = QPushButton("Obtener Releases de Muspy")
        self.muspy_releases_button.clicked.connect(self.get_muspy_releases)
        layout.addWidget(self.muspy_releases_button)

        # Botón para cargar artistas desde archivo
        self.load_artists_button = QPushButton("Cargar Artistas desde Archivo")
        self.load_artists_button.clicked.connect(self.load_artists_from_file)
        layout.addWidget(self.load_artists_button)
    def load_artists_from_file(self):
        """Cargar artistas desde un archivo de texto"""
        # Si no se ha especificado un archivo, abrir selector de archivos
        if not self.artists_file:
            self.artists_file = QFileDialog.getOpenFileName(self, "Seleccionar archivo de artistas", "", "Text Files (*.txt)")[0]
        
        if not self.artists_file:
            return

        try:
            with open(self.artists_file, 'r', encoding='utf-8') as f:
                self.artists = [line.strip() for line in f if line.strip()]
            
            # Limpiar resultados anteriores
            self.results_text.clear()
            self.results_text.append(f"Cargados {len(self.artists)} artistas desde {self.artists_file}\n")

        except Exception as e:
            self.results_text.append(f"Error al cargar archivo: {e}\n")

    def search_manual_artist(self):
        """Búsqueda manual de artista y sus releases"""
        artist_name = self.artist_input.text().strip()
        if not artist_name:
            QMessageBox.warning(self, "Error", "Por favor introduce un nombre de artista")
            return

        # Buscar en MusicBrainz
        mb_releases = self.search_musicbrainz_releases(artist_name)
        
        # Mostrar resultados
        self.display_releases(artist_name, mb_releases)

    def search_artists_from_file(self):
        """Buscar releases para artistas cargados desde archivo"""
        # Verificar si hay artistas cargados
        if not hasattr(self, 'artists') or not self.artists:
            QMessageBox.warning(self, "Error", "No hay artistas cargados. Primero cargue un archivo.")
            return

        # Limpiar resultados anteriores
        self.results_text.clear()

        # Procesar cada artista
        for artist_name in self.artists:
            self.results_text.append(f"Procesando artista: {artist_name}\n")
            
            # Añadir a Muspy
            #self.add_artist_to_muspy(artist_name)
            
            # Buscar releases en MusicBrainz
            mb_releases = self.search_musicbrainz_releases(artist_name)
            
            # Mostrar resultados
            self.display_releases(artist_name, mb_releases)

    def add_artist_to_muspy(self, artist_name, mbid=None):
        """
        Add/Follow an artist to Muspy using their MBID or name
        
        Args:
            artist_name (str): Name of the artist
            mbid (str, optional): MusicBrainz ID of the artist. Defaults to None.
        
        Returns:
            bool: True if artist was successfully added, False otherwise
        """
        if not self.muspy_username or not self.muspy_api_key:
            self.results_text.append("Configuración de Muspy no disponible\n")
            return False

        try:
            # Determine the URL based on whether MBID is provided
            if mbid:
                # Follow a specific artist by MBID
                url = f"https://muspy.com/api/1/artists/{self.muspy_username}/{mbid}"
                method = 'PUT'
                data = {}
            else:
                # Import artists via last.fm or other method (requires modify the code)
                url = f"https://muspy.com/api/1/artists/{self.muspy_username}"
                method = 'PUT'
                data = {
                    'import': 'last.fm',  # or adjust as needed
                    'username': self.muspy_username,
                    'count': 500,
                    'period': 'overall'
                }

            headers = {
                'Authorization': f'Token {self.muspy_api_key}',
                'Content-Type': 'application/json'
            }
            
            # Use the appropriate request method
            if method == 'PUT':
                response = requests.put(url, headers=headers, json=data)
            else:
                response = requests.post(url, headers=headers, json=data)
            
            if response.status_code in [200, 201]:
                self.results_text.append(f"Artista {artist_name} añadido a Muspy\n")
                return True
            else:
                self.results_text.append(f"No se pudo añadir {artist_name} a Muspy: {response.text}\n")
                return False
        except Exception as e:
            self.results_text.append(f"Error añadiendo a Muspy: {e}\n")
            return False

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
            # First attempt: query existing database
            mbid_result = subprocess.run(
                ['python', self.query_db_script_path, artist_name, "--mbid"], 
                capture_output=True, 
                text=True
            )
            
            if mbid_result.returncode == 0 and mbid_result.stdout.strip():
                return mbid_result.stdout.strip()
            
            # Second attempt: search for MBID if first method fails
            mbid_search_result = subprocess.run(
                ['python', self.search_mbid_script_path, "--artist", artist_name], 
                capture_output=True, 
                text=True
            )
            
            if mbid_search_result.returncode == 0 and mbid_search_result.stdout.strip():
                return mbid_search_result.stdout.strip()
            
            return artist_name
        
        except Exception as e:
            logging.error(f"Error getting MBID for {artist_name}: {e}")
            return None



    def search_musicbrainz_releases(self, artist_name):
        """Buscar próximos releases en MusicBrainz"""
        try:
            # Buscar ID del artista
            result = musicbrainzngs.search_artists(artist=artist_name)
            
            if not result['artist-list']:
                QMessageBox.warning(self, "Error", f"Artista {artist_name} no encontrado en MusicBrainz")
                return []

            artist_id = result['artist-list'][0]['id']

            # Buscar releases
            releases = musicbrainzngs.search_releases(artist=artist_name)
            
            formatted_releases = []
            for release in releases.get('release-list', []):
                # Obtener sello discográfico
                labels = [label.get('name', 'Desconocido') for label in release.get('label-info-list', [])]
                
                formatted_releases.append({
                    'title': release.get('title', 'Título desconocido'),
                    'date': release.get('date', 'Fecha no confirmada'),
                    'type': release.get('release-group', {}).get('type', 'Tipo desconocido'),
                    'label': ', '.join(labels) if labels else 'Sello no especificado',
                    'url': release.get('url-rels', [{}])[0].get('target', '') if release.get('url-rels') else ''
                })
            
            return formatted_releases

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error buscando en MusicBrainz: {e}")
            return []

    def get_muspy_releases(self):
        """Obtener releases de Muspy para el usuario"""
        if not self.muspy_username or not self.muspy_api_key:
            QMessageBox.warning(self, "Error", "Configuración de Muspy no disponible")
            return

        try:
            url = f"https://muspy.com/api/1/releases/upcoming"
            headers = {
                'Authorization': f'Token {self.muspy_api_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                releases = response.json()
                self.results_text.clear()
                
                if not releases:
                    self.results_text.append("No hay releases pendientes en Muspy\n")
                    return
                
                for release in releases:
                    release_info = (
                        f"Artista: {release.get('artist', 'Desconocido')}\n"
                        f"Título: {release.get('title', 'Sin título')}\n"
                        f"Fecha: {release.get('date', 'Sin fecha')}\n"
                        f"Tipo: {release.get('type', 'Desconocido')}\n"
                        "---\n"
                    )
                    self.results_text.append(release_info)
            else:
                self.results_text.append(f"Error obteniendo releases: {response.text}\n")
        
        except Exception as e:
            self.results_text.append(f"Error de conexión con Muspy: {e}\n")


    def display_releases(self, artist_name, releases):
        """Mostrar releases en la tabla"""
        # Limpiar tabla existente
        self.results_table.setRowCount(0)

        if not releases:
            QMessageBox.information(self, "Sin Resultados", f"No se encontraron releases para {artist_name}")
            return

        # Configurar número de filas
        self.results_table.setRowCount(len(releases))

        # Fecha actual para comparación
        today = date.today()

        for row, release in enumerate(releases):
            # Título
            titulo_item = QTableWidgetItem(release.get('title', 'Sin título'))
            
            # Fecha
            fecha_str = release.get('date', 'Sin fecha')
            fecha_item = QTableWidgetItem(fecha_str)
            
            # Tipo
            tipo_item = QTableWidgetItem(release.get('type', 'Desconocido'))
            
            # Sello discográfico
            sello_item = QTableWidgetItem(release.get('label', 'Sello no especificado'))
            
            # Verificar si la fecha es futura para resaltar
            try:
                if fecha_str != 'Sin fecha':
                    release_date = datetime.strptime(fecha_str, "%Y-%m-%d").date()
                    if release_date > today:
                        # Resaltar en verde los no publicados
                        titulo_item.setBackground(QColor(200, 255, 200))
                        fecha_item.setBackground(QColor(200, 255, 200))
                        tipo_item.setBackground(QColor(200, 255, 200))
                        sello_item.setBackground(QColor(200, 255, 200))
            except ValueError:
                # Manejar fechas con formato no esperado
                pass

            # Botones de acción (por definir)
            accion1_item = QTableWidgetItem("Acción 1")
            accion2_item = QTableWidgetItem("Acción 2")
            
            # Botón para abrir URL
            url_item = QTableWidgetItem("Abrir URL")

            # Añadir items a la tabla
            self.results_table.setItem(row, 0, titulo_item)
            self.results_table.setItem(row, 1, fecha_item)
            self.results_table.setItem(row, 2, tipo_item)
            self.results_table.setItem(row, 3, sello_item)
            self.results_table.setItem(row, 4, accion1_item)
            self.results_table.setItem(row, 5, accion2_item)
            self.results_table.setItem(row, 6, url_item)

def main():
    """Función principal para ejecutar la aplicación"""
    app = QApplication(sys.argv)
    
    # Configurar argumentos
    muspy_username = None
    muspy_api_key = None
    artists_file = None
    
    # Procesar argumentos de línea de comandos
    for arg in sys.argv[1:]:
        if arg.startswith('--muspy-username='):
            muspy_username = arg.split('=')[1]
        elif arg.startswith('--muspy-api-key='):
            muspy_api_key = arg.split('=')[1]
        elif arg.startswith('--artists-file='):
            artists_file = arg.split('=')[1]
        elif arg.startswith('--query-db-script-path='):
            query_db_script_path = arg.split('=')[1]
        elif arg.startswith('--search-mbid-script-path='):
            search_mbid_script_path = arg.split('=')[1]

    # Crear instancia del módulo
    module = MusicReleasesModule(
        muspy_username=muspy_username, 
        muspy_api_key=muspy_api_key,
        artists_file=artists_file,
        query_db_script_path=query_db_script_path,
        search_mbid_script_path=search_mbid_script_path
    )
    module.show()
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()