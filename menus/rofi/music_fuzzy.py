import sys
import os
from typing import Optional, List, Dict
from pathlib import Path
import sqlite3
import json
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLineEdit, QPushButton, QListWidget,
                            QLabel, QScrollArea, QSplitter)
from PyQt6.QtGui import QPixmap, QShortcut, QKeySequence
from PyQt6.QtCore import Qt, QSize
import subprocess

# Tema Tokyo Night
THEME = {
    'bg': '#1a1b26',
    'fg': '#a9b1d6',
    'accent': '#7aa2f7',
    'secondary_bg': '#24283b',
    'border': '#414868',
    'selection': '#364A82',
    'button_hover': '#3d59a1'
}

class SearchParser:
    def __init__(self):
        self.filters = {
            'a:': 'artist',
            'b:': 'album',
            'g:': 'genre',
            'l:': 'label',
            'aa:': 'album_artist',
            'br:': 'bitrate'
        }
    
    def parse_query(self, query: str) -> Dict:
        """Parsea la query y devuelve diccionario con filtros y término general."""
        parts = query.split()
        filters = {}
        general_terms = []

        i = 0
        while i < len(parts):
            part = parts[i]
            matched = False
            
            for prefix, field in self.filters.items():
                if part.startswith(prefix):
                    value = part[len(prefix):]
                    # Si el valor está vacío, tomar la siguiente palabra
                    if not value and i + 1 < len(parts):
                        value = parts[i + 1]
                        i += 1
                    filters[field] = value
                    matched = True
                    break
            
            if not matched:
                general_terms.append(part)
            i += 1

        return {
            'filters': filters,
            'general': ' '.join(general_terms)
        }

class MusicBrowser(QMainWindow):
    def __init__(self, db_path: str):
        super().__init__()
        self.db_path = db_path
        self.search_parser = SearchParser()
        self.init_ui()
        self.apply_theme()
        self.setup_shortcuts()

    def init_ui(self):
        self.setWindowTitle('Navegador Musical')
        self.setMinimumSize(1200, 800)

        # Widget principal
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # Barra superior
        top_bar = QWidget()
        top_layout = QHBoxLayout(top_bar)
        
        # Búsqueda
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText('Buscar (usa a: artista, b: album, g: género...)')
        self.search_box.textChanged.connect(self.search)
        top_layout.addWidget(self.search_box)

        # Establecer una altura fija para la barra superior
        top_bar.setFixedHeight(50)  # Ajusta esta altura según sea necesario
        
        # Botones
        self.play_button = QPushButton('Reproducir')
        self.folder_button = QPushButton('Abrir Carpeta')
        self.custom_button1 = QPushButton('Script 1')
        self.custom_button2 = QPushButton('Script 2')
        self.custom_button3 = QPushButton('Script 3')

        for button in [self.play_button, self.folder_button, 
                      self.custom_button1, self.custom_button2, self.custom_button3]:
            button.setFixedWidth(100)
            top_layout.addWidget(button)

        layout.addWidget(top_bar)

        # Splitter principal
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Panel izquierdo (resultados)
        self.results_list = QListWidget()
        self.results_list.currentItemChanged.connect(self.show_details)
        splitter.addWidget(self.results_list)

        # Panel derecho (detalles)
        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        
        # Imagen
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(300, 300)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        details_layout.addWidget(self.cover_label)

        # Información
        self.info_scroll = QScrollArea()
        self.info_scroll.setWidgetResizable(True)
        self.info_widget = QWidget()
        self.info_layout = QVBoxLayout(self.info_widget)
        
        self.lastfm_label = QLabel()
        self.lastfm_label.setWordWrap(True)
        self.info_layout.addWidget(self.lastfm_label)
        
        self.metadata_label = QLabel()
        self.metadata_label.setWordWrap(True)
        self.info_layout.addWidget(self.metadata_label)
        
        self.info_scroll.setWidget(self.info_widget)
        details_layout.addWidget(self.info_scroll)

        splitter.addWidget(details_widget)
        layout.addWidget(splitter)

        # Conectar señales
        self.play_button.clicked.connect(self.play_item)
        self.folder_button.clicked.connect(self.open_folder)
        self.custom_button1.clicked.connect(lambda: self.run_custom_script(1))
        self.custom_button2.clicked.connect(lambda: self.run_custom_script(2))
        self.custom_button3.clicked.connect(lambda: self.run_custom_script(3))

        # Dar focus inicial al búscador
        self.search_box.setFocus()

    def setup_shortcuts(self):
        # Enter para reproducir
        QShortcut(QKeySequence(Qt.Key.Key_Return), self, self.play_item)
        # Ctrl+O para abrir carpeta
        QShortcut(QKeySequence("Ctrl+O"), self, self.open_folder)
        # Ctrl+F para focus en búsqueda
        QShortcut(QKeySequence("Ctrl+F"), self, self.search_box.setFocus)

    def apply_theme(self):
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background-color: {THEME['bg']};
                color: {THEME['fg']};
            }}
            
            QLineEdit {{
                background-color: {THEME['secondary_bg']};
                border: 1px solid {THEME['border']};
                padding: 5px;
                border-radius: 3px;
            }}
            
            QPushButton {{
                background-color: {THEME['secondary_bg']};
                border: 1px solid {THEME['border']};
                padding: 5px 10px;
                border-radius: 3px;
            }}
            
            QPushButton:hover {{
                background-color: {THEME['button_hover']};
            }}
            
            QListWidget {{
                background-color: {THEME['secondary_bg']};
                border: 1px solid {THEME['border']};
                border-radius: 3px;
            }}
            
            QListWidget::item:selected {{
                background-color: {THEME['selection']};
            }}
            
            QScrollArea {{
                border: 1px solid {THEME['border']};
                border-radius: 3px;
            }}
        """)

    def search(self):
        query = self.search_box.text()
        parsed = self.search_parser.parse_query(query)
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Construir la query SQL con referencias explícitas a las tablas
        sql = """
            SELECT DISTINCT 
                s.id,
                s.file_path,
                s.title,
                s.artist,
                s.album_artist,
                s.album,
                s.date,
                s.genre,
                s.label,
                s.mbid,
                s.bitrate,
                s.bit_depth,
                s.sample_rate,
                s.last_modified,
                ai.bio
            FROM songs s
            LEFT JOIN artist_info ai ON s.artist = ai.artist
            WHERE 1=1
        """
        params = []

        # Aplicar filtros específicos
        for field, value in parsed['filters'].items():
            if field == 'bitrate':
                # Manejar rangos de bitrate (ej: br:>192)
                if value.startswith('>'):
                    sql += f" AND s.{field} > ?"
                    params.append(int(value[1:]))
                elif value.startswith('<'):
                    sql += f" AND s.{field} < ?"
                    params.append(int(value[1:]))
                else:
                    sql += f" AND s.{field} = ?"
                    params.append(int(value))
            else:
                sql += f" AND s.{field} LIKE ?"
                params.append(f"%{value}%")

        # Búsqueda general
        if parsed['general']:
            general_fields = ['artist', 'title', 'album', 'genre', 'label', 'album_artist']
            general_conditions = [f"s.{field} LIKE ?" for field in general_fields]
            sql += f" AND ({' OR '.join(general_conditions)})"
            params.extend([f"%{parsed['general']}%"] * len(general_fields))

        try:
            c.execute(sql, params)
            results = c.fetchall()
            
            self.results_list.clear()
            for row in results:
                # Crear un texto representativo para mostrar
                # Asegurarse de que los campos no sean None antes de mostrarlos
                title = row[2] or "Sin título"
                artist = row[3] or "Sin artista"
                album = row[5] or "Sin álbum"
                display_text = f"{title} - {artist} - {album}"
                
                item = self.results_list.addItem(display_text)
                # Guardar los datos completos como datos del item
                self.results_list.item(self.results_list.count() - 1).setData(
                    Qt.ItemDataRole.UserRole, row)

        except Exception as e:
            print(f"Error en la búsqueda: {e}")
            import traceback
            traceback.print_exc()  # Esto nos dará más detalles sobre el error
        finally:
            conn.close()

    def find_cover_image(self, file_path: str) -> Optional[str]:
        """Busca la carátula en la carpeta del archivo."""
        dir_path = Path(file_path).parent
        cover_names = ['cover', 'folder', 'front', 'album']
        image_extensions = ['.jpg', '.jpeg', '.png']

        # Primero buscar nombres específicos
        for name in cover_names:
            for ext in image_extensions:
                cover_path = dir_path / f"{name}{ext}"
                if cover_path.exists():
                    return str(cover_path)

        # Si no se encuentra, buscar cualquier imagen
        for file in dir_path.glob('*'):
            if file.suffix.lower() in image_extensions:
                return str(file)

        return None

    def show_details(self, current, previous):
        if not current:
            return

        data = current.data(Qt.ItemDataRole.UserRole)
        
        # Mostrar carátula
        cover_path = self.find_cover_image(data[1])  # data[1] es file_path
        if cover_path:
            pixmap = QPixmap(cover_path)
            pixmap = pixmap.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio)
            self.cover_label.setPixmap(pixmap)
        else:
            # Carátula por defecto
            self.cover_label.setText("No imagen")

        # Mostrar info de LastFM
        lastfm_text = data[-1] if data[-1] else "No hay información de LastFM disponible"
        self.lastfm_label.setText(f"<b>Información del Artista:</b><br>{lastfm_text}")

        # Mostrar metadata
        metadata = f"""
            <b>Título:</b> {data[2]}<br>
            <b>Artista:</b> {data[3]}<br>
            <b>Album Artist:</b> {data[4]}<br>
            <b>Álbum:</b> {data[5]}<br>
            <b>Fecha:</b> {data[6]}<br>
            <b>Género:</b> {data[7]}<br>
            <b>Sello:</b> {data[8]}<br>
            <b>MBID:</b> {data[9]}<br>
            <b>Bitrate:</b> {data[10]} kbps<br>
            <b>Profundidad:</b> {data[11]} bits<br>
            <b>Frecuencia:</b> {data[12]} Hz<br>
        """
        self.metadata_label.setText(metadata)

    def play_item(self):
        current = self.results_list.currentItem()
        if current:
            file_path = current.data(Qt.ItemDataRole.UserRole)[1]
            subprocess.Popen(['xdg-open', file_path])

    def open_folder(self):
        current = self.results_list.currentItem()
        if current:
            file_path = current.data(Qt.ItemDataRole.UserRole)[1]
            folder_path = str(Path(file_path).parent)
            subprocess.Popen(['xdg-open', folder_path])

    def run_custom_script(self, script_num):
        current = self.results_list.currentItem()
        if not current:
            return

        data = current.data(Qt.ItemDataRole.UserRole)
        # Definir los scripts aquí o cargarlos desde configuración
        scripts = {
            1: '/path/to/script1.sh',
            2: '/path/to/script2.sh',
            3: '/path/to/script3.sh'
        }
        
        if script_num in scripts and os.path.exists(scripts[script_num]):
            subprocess.Popen([scripts[script_num], data[1]])

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Navegador de música')
    parser.add_argument('db_path', help='Ruta a la base de datos SQLite')
    
    args = parser.parse_args()
    
    app = QApplication(sys.argv)
    browser = MusicBrowser(args.db_path)
    browser.show()
    sys.exit(app.exec())