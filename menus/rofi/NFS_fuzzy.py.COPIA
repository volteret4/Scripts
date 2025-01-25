import sys
import os
import json
import subprocess
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, 
                             QVBoxLayout, QLineEdit, QListWidget, QPushButton, 
                             QLabel, QMessageBox)
from PyQt5.QtGui import QFont, QPalette, QColor, QKeySequence
from PyQt5.QtCore import Qt, QEvent
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen import File 

class MusicLibraryBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.index_file = os.path.expanduser('~/.music_library_index.json')
        self.base_paths = [
            '/mnt/NFS/moode/moode'
        ]
        self.music_index = []  # Añadido como atributo de la clase
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle('Explorador de Música')
        self.setGeometry(100, 100, 1000, 700)
        
        # Paleta de colores Catppuccin Mocha
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(30, 30, 46))  # Base
        palette.setColor(QPalette.WindowText, QColor(205, 214, 244))  # Text
        palette.setColor(QPalette.Base, QColor(24, 24, 37))  # Mantle
        palette.setColor(QPalette.AlternateBase, QColor(30, 30, 46))  # Surface0
        palette.setColor(QPalette.ToolTipBase, QColor(147, 153, 178))  # Overlay0
        palette.setColor(QPalette.ToolTipText, QColor(205, 214, 244))  # Text
        palette.setColor(QPalette.Text, QColor(205, 214, 244))  # Text
        palette.setColor(QPalette.Button, QColor(49, 50, 68))  # Surface1
        palette.setColor(QPalette.ButtonText, QColor(205, 214, 244))  # Text
        palette.setColor(QPalette.BrightText, QColor(243, 139, 168))  # Red
        palette.setColor(QPalette.Link, QColor(116, 199, 236))  # Blue
        palette.setColor(QPalette.Highlight, QColor(137, 180, 250))  # Lavender
        palette.setColor(QPalette.HighlightedText, QColor(30, 30, 46))  # Base

        self.setPalette(palette)
        
        # Estilo personalizado Catppuccin Mocha
        self.setStyleSheet("""
            QWidget {
                background-color: #1E1E2E;
                color: #CDD6F4;
            }
            QLineEdit {
                background-color: #181825;  /* Mantle */
                color: #CDD6F4;
                border: 1px solid #313244;  /* Surface1 */
                padding: 5px;
                border-radius: 4px;
            }
            QListWidget {
                background-color: #181825;  /* Mantle */
                color: #CDD6F4;
                border: 1px solid #313244;  /* Surface1 */
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #313244;  /* Surface1 */
            }
            QListWidget::item:selected {
                background-color: #494D64;  /* Surface2 */
                color: #CDD6F4;
            }
            QLabel {
                color: #CDD6F4;
                word-wrap: break-word;
            }
        """)
        
        # Widget central y layout principal
        central_widget = QWidget()
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        
        # Layout izquierdo - Búsqueda y Lista de Álbumes
        left_layout = QVBoxLayout()
        
        # Barra de búsqueda
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('Buscar artista o álbum...')
        self.search_input.textChanged.connect(self.search_albums)
        left_layout.addWidget(self.search_input)
        
        # Lista de álbumes
        self.album_list = QListWidget()
        self.album_list.itemClicked.connect(self.show_album_details)
        self.album_list.installEventFilter(self)
        # Establecer un ancho fijo para mantener proporción
        self.album_list.setMinimumWidth(300)
        left_layout.addWidget(self.album_list)
        
        # Layout derecho - Detalles del Álbum
        right_layout = QVBoxLayout()
        
        # Etiquetas de información
        self.album_info_label = QLabel('Selecciona un álbum')
        self.album_info_label.setFont(QFont('Arial', 12, QFont.Bold))
        self.album_info_label.setWordWrap(True)  # Permitir múltiples líneas
        right_layout.addWidget(self.album_info_label)
        
        # Contenido del álbum
        self.album_content = QListWidget()
        self.album_content.setMinimumWidth(400)  # Ancho fijo para mantener proporción
        right_layout.addWidget(self.album_content)
        
        # Añadir layouts al layout principal
        main_layout.addLayout(left_layout, 1)  # Proporción flexible
        main_layout.addLayout(right_layout, 2)  # Proporción flexible
        
        self.current_album_path = None
        
        # Configurar la selección inicial al primer elemento
        self.load_or_create_index()
        if self.album_list.count() > 0:
            self.album_list.setCurrentRow(0)
            self.show_album_details(self.album_list.currentItem())
        
        # Conectar eventos de teclado para navegación
        self.album_list.currentItemChanged.connect(self.on_album_selection_changed)
        
    def on_album_selection_changed(self, current_item, previous_item):
        """Mostrar detalles del álbum cuando se cambia la selección con flechas"""
        if current_item:
            self.show_album_details(current_item)
        
    def eventFilter(self, obj, event):
        """Manejar eventos de teclado para la lista de álbumes"""
        if obj is self.album_list:
            if event.type() == QEvent.KeyPress:
                # Enter: añadir a DeaDBeeF
                if event.key() == Qt.Key_Return and self.current_album_path:
                    self.add_to_playlist()
                    return True
                
                # Ctrl+O: abrir en Thunar
                if event.key() == Qt.Key_O and event.modifiers() & Qt.ControlModifier:
                    self.open_in_thunar()
                    return True
        
        return super().eventFilter(obj, event)
    
    def create_music_index(self):
        """Crear un índice de la biblioteca musical usando mutagen para extraer metadatos de los archivos FLAC"""
        print("Generando índice de música... (esto puede tardar unos minutos)")
        music_index = []
        
        for base_path in self.base_paths:
            # Buscar archivos FLAC en la estructura
            for root, dirs, files in os.walk(base_path):
                for file in files:
                    if file.lower().endswith('.flac'):
                        flac_file_path = os.path.join(root, file)
                        try:
                            # Usar mutagen para leer los metadatos del archivo FLAC
                            audio_file = FLAC(flac_file_path)
                            
                            # Extraer los metadatos: artista, álbum, fecha, sello discográfico
                            artist = audio_file.get('artist', ['Desconocido'])[0]
                            album = audio_file.get('album', ['Desconocido'])[0]
                            date = audio_file.get('date', ['Desconocida'])[0]
                            label = audio_file.get('label', ['Desconocido'])[0]
                            
                            # Verificar si ya existe en el índice
                            if not any(item['path'] == flac_file_path for item in music_index):
                                music_index.append({
                                    'artist': artist,
                                    'album': album,
                                    'date': date,
                                    'label': label,
                                    'path': flac_file_path
                                })
                        except Exception as e:
                            print(f"Error al procesar {flac_file_path}: {e}")
        
        # Guardar índice en el atributo de la clase
        self.music_index = music_index  # Guardamos el índice en self.music_index
        with open(self.index_file, 'w') as f:
            json.dump(music_index, f, indent=2)
        
        return music_index
    
    # def extract_metadata(self, file_path):
    #     """Extraer metadatos básicos de un archivo de música (MP3, FLAC, etc.)."""
    #     try:
    #         # Detectar tipo de archivo
    #         if file_path.lower().endswith(".mp3"):
    #             audio = MP3(file_path, ID3=EasyID3)
    #         elif file_path.lower().endswith(".flac"):
    #             audio = FLAC(file_path)
    #         else:
    #             # Intentar con mutagen.File para otros formatos
    #             audio = File(file_path)
    #             if audio is None:
    #                 raise ValueError("Formato no compatible o archivo corrupto")
            
    #         # Extraer metadatos estándar
    #         metadata = {
    #             "artist": audio.get("artist", ["Desconocido"])[0],
    #             "album": audio.get("album", ["Desconocido"])[0],
    #             "date": audio.get("date", ["Desconocido"])[0],
    #             "label": audio.get("label", ["Desconocido"])[0] if "label" in audio else "Desconocido"
    #         }
    #         return metadata

    #     except Exception as e:
    #         print(f"Error al leer metadatos de {file_path}: {e}")
    #         return None

    def show_album_details(self, item):
        """Mostrar detalles del álbum seleccionado usando los metadatos"""
        artist, album = item.text().split(' - ', 1)
        # Buscar el álbum en el índice
        album_info = next((a for a in self.music_index 
                           if a['artist'] == artist and a['album'] == album), None)
        
        if album_info:
            # Acceder a los metadatos desde self.music_index
            date = album_info.get('date', 'Desconocido')
            label = album_info.get('label', 'Desconocido')
            
            # Mostrar los detalles
            details = f"Artista: {album_info['artist']}\n" \
                      f"Álbum: {album_info['album']}\n" \
                      f"Año: {date}\n" \
                      f"Sello: {label}"
            self.album_info_label.setText(details)
            
            # Añadir archivos al contenido del álbum
            self.album_content.clear()
            for track in album_info.get('tracks', []):  # Asegurarse de que 'tracks' exista
                self.album_content.addItem(track)
            self.current_album_path = album_info['path']
        else:
            self.album_info_label.setText('No se encontraron detalles del álbum.')
            self.album_content.clear()
    

    def add_to_playlist(self):
        """Añadir álbum a la playlist actual de DeaDBeeF"""
        if self.current_album_path:
            try:
                subprocess.run(['deadbeef', '--add', self.current_album_path])
                self.close()  # Cerrar la ventana después de añadir
            except Exception as e:
                QMessageBox.warning(self, 'Error', f'No se pudo añadir a playlist: {e}')
        else:
            QMessageBox.warning(self, 'Error', 'Selecciona un álbum primero')
        
    def open_in_thunar(self):
        """Abrir la carpeta del álbum en Thunar"""
        if self.current_album_path:
            try:
                subprocess.Popen(['thunar', self.current_album_path])
                self.close()  # Cerrar la ventana después de abrir
            except Exception as e:
                QMessageBox.warning(self, 'Error', f'No se pudo abrir Thunar: {e}')
        else:
            QMessageBox.warning(self, 'Error', 'Selecciona un álbum primero')

    def load_or_create_index(self):
        """Cargar o crear índice de música"""
        try:
            # Intentar cargar índice existente
            with open(self.index_file, 'r') as f:
                self.music_index = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Si no existe, crear uno nuevo
            self.music_index = self.create_music_index()
        
        # Cargar álbumes en la lista
        self.album_list.clear()
        for item in self.music_index:
            # Mostrar artista y álbum
            self.album_list.addItem(f"{item['artist']} - {item['album']}")
        
    def search_albums(self, text):
        """Filtrar álbumes según el texto de búsqueda"""
        text = text.lower()
        self.album_list.clear()
        
        for item in self.music_index:
            # Buscar en artista o álbum
            if (text in item['artist'].lower() or 
                text in item['album'].lower()):
                self.album_list.addItem(f"{item['artist']} - {item['album']}")

def main():
    # Establecer el estilo Fusion explícitamente
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    browser = MusicLibraryBrowser()
    browser.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()