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


reproductor = 'deadbeef'
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
            't:': 'title',
            'aa:': 'album_artist',
            'br:': 'bitrate',
            'd:': 'date'
        }
    
    def parse_query(self, query: str) -> Dict:
        """Parsea la query y devuelve diccionario con filtros y término general."""
        filters = {}
        general_terms = []
        current_term = ''
        i = 0
        
        while i < len(query):
            # Buscar si hay un filtro al inicio de esta parte
            found_filter = False
            for prefix, field in self.filters.items():
                if query[i:].startswith(prefix):
                    # Si hay un término acumulado, añadirlo a términos generales
                    if current_term.strip():
                        general_terms.append(current_term.strip())
                        current_term = ''
                    
                    # Avanzar más allá del prefijo
                    i += len(prefix)
                    # Recoger el valor hasta el siguiente filtro o fin de cadena
                    value = ''
                    while i < len(query):
                        # Comprobar si empieza otro filtro
                        next_filter = False
                        for next_prefix in self.filters:
                            if query[i:].startswith(next_prefix):
                                next_filter = True
                                break
                        if next_filter:
                            break
                        value += query[i]
                        i += 1
                    
                    value = value.strip()
                    if value:
                        filters[field] = value
                    found_filter = True
                    break
            
            if not found_filter and i < len(query):
                current_term += query[i]
                i += 1
        
        # Añadir el último término si existe
        if current_term.strip():
            general_terms.append(current_term.strip())
        
        return {
            'filters': filters,
            'general': ' '.join(general_terms)
        }

    def build_sql_conditions(self, parsed_query: Dict) -> tuple:
        """Construye las condiciones SQL y parámetros basados en la query parseada."""
        conditions = []
        params = []
        
        # Procesar filtros específicos
        for field, value in parsed_query['filters'].items():
            if field == 'bitrate':
                # Manejar rangos de bitrate (>192, <192, =192)
                if value.startswith('>'):
                    conditions.append(f"s.{field} > ?")
                    params.append(int(value[1:]))
                elif value.startswith('<'):
                    conditions.append(f"s.{field} < ?")
                    params.append(int(value[1:]))
                else:
                    conditions.append(f"s.{field} = ?")
                    params.append(int(value))
            else:
                conditions.append(f"s.{field} LIKE ?")
                params.append(f"%{value}%")
        
        # Procesar términos generales
        if parsed_query['general']:
            general_fields = ['artist', 'title', 'album', 'genre', 'label', 'album_artist']
            general_conditions = []
            for field in general_fields:
                general_conditions.append(f"s.{field} LIKE ?")
                params.append(f"%{parsed_query['general']}%")
            if general_conditions:
                conditions.append(f"({' OR '.join(general_conditions)})")
        
        return conditions, params

class MusicBrowser(QMainWindow):
    def __init__(self, db_path: str, font_family="Inter"):
        self.font_family = font_family
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
        layout.setSpacing(5)
        layout.setContentsMargins(10, 10, 10, 10)

        # Contenedor superior con altura máxima
        top_container = QWidget()
        top_container.setMaximumHeight(100)
        top_layout = QVBoxLayout(top_container)
        top_layout.setSpacing(5)
        
        # Barra de búsqueda
        search_layout = QHBoxLayout()
        
        # Búsqueda
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText('Buscar...')
        self.search_box.textChanged.connect(self.search)
        search_layout.addWidget(self.search_box)

        # Botones
        self.play_button = QPushButton('Reproducir')
        self.folder_button = QPushButton('Abrir Carpeta')
        self.custom_button1 = QPushButton('Script 1')
        self.custom_button2 = QPushButton('Script 2')
        self.custom_button3 = QPushButton('Script 3')

        for button in [self.play_button, self.folder_button, 
                      self.custom_button1, self.custom_button2, self.custom_button3]:
            button.setFixedWidth(100)
            search_layout.addWidget(button)

        top_layout.addLayout(search_layout)

        # Leyenda de argumentos
        legend_label = QLabel(
            '<span style="color: #7aa2f7;">'
            'Filtros: a:artista -   b:álbum -    g:género -   l:sello -    t:título -   aa:album-artist  -   br:bitrate  -    d:fecha'
            '</span>'
        )
        legend_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        top_layout.addWidget(legend_label)

        layout.addWidget(top_container)

        # Splitter principal
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Panel izquierdo (resultados)
        self.results_list = QListWidget()
        self.results_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.results_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.results_list.currentItemChanged.connect(self.show_details)
        splitter.addWidget(self.results_list)

        # Panel derecho (detalles)
        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        details_layout.setContentsMargins(0, 0, 0, 0)
        
        # Imagen
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(300, 300)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        details_layout.addWidget(self.cover_label)

        # Información
        self.info_scroll = QScrollArea()
        self.info_scroll.setWidgetResizable(True)
        self.info_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.info_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
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

        # Aplicar la fuente a toda la aplicación
        self.setStyleSheet(f"""
            * {{
                font-family: {self.font_family};
            }}
            QLabel {{
                font-size: 12px;
            }}
            QLineEdit {{
                font-size: 13px;
            }}
            QPushButton {{
                font-size: 12px;
            }}
            QListWidget {{
                font-size: 12px;
            }}
        """)
    def setup_shortcuts(self):
        # Enter para reproducir
        QShortcut(QKeySequence(Qt.Key.Key_Return), self, self.play_item)
        # Ctrl+O para abrir carpeta
        QShortcut(QKeySequence("Ctrl+O"), self, self.open_folder)
        # Ctrl+F para focus en búsqueda
        QShortcut(QKeySequence("Ctrl+F"), self, self.search_box.setFocus)

    def apply_theme(self):
        self.setStyleSheet(self.styleSheet() + f"""
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
                padding: 5px;
            }}
            
            QListWidget::item:selected {{
                background-color: {THEME['selection']};
            }}
            
            QScrollArea {{
                border: 1px solid {THEME['border']};
                border-radius: 3px;
            }}

            QScrollBar:vertical {{
                border: none;
                background: {THEME['secondary_bg']};
                width: 10px;
                margin: 0px;
            }}

            QScrollBar::handle:vertical {{
                background-color: {THEME['border']};
                border-radius: 5px;
                min-height: 20px;
            }}

            QScrollBar::handle:vertical:hover {{
                background-color: {THEME['accent']};
            }}

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {{
                height: 0px;
                background: none;
            }}
        """)

    def search(self):
        query = self.search_box.text()
        parsed = self.search_parser.parse_query(query)
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Consulta base
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
        """
        
        conditions = []
        params = []

        # Procesar filtros específicos
        for field, value in parsed['filters'].items():
            if field == 'bitrate':
                # Manejar rangos de bitrate (>192, <192, =192)
                if value.startswith('>'):
                    conditions.append(f"s.{field} > ?")
                    params.append(int(value[1:]))
                elif value.startswith('<'):
                    conditions.append(f"s.{field} < ?")
                    params.append(int(value[1:]))
                else:
                    conditions.append(f"s.{field} = ?")
                    try:
                        params.append(int(value))
                    except ValueError:
                        print(f"Error: valor de bitrate inválido: {value}")
                        continue
            else:
                conditions.append(f"s.{field} LIKE ?")
                params.append(f"%{value}%")

        # Procesar términos generales
        if parsed['general']:
            general_fields = ['artist', 'title', 'album', 'genre', 'label', 'album_artist']
            general_conditions = []
            for field in general_fields:
                general_conditions.append(f"s.{field} LIKE ?")
                params.append(f"%{parsed['general']}%")
            if general_conditions:
                conditions.append(f"({' OR '.join(general_conditions)})")

        # Añadir WHERE si hay condiciones
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        # Añadir ORDER BY para una presentación consistente
        sql += " ORDER BY s.artist, s.album, s.title"
        
        try:
            c.execute(sql, params)
            results = c.fetchall()
            
            self.results_list.clear()
            for row in results:
                # Asegurarse de que los campos no sean None
                artist = row[3] if row[3] else "Sin artista"
                album = row[5] if row[5] else "Sin álbum"
                title = row[2] if row[2] else "Sin título"
                
                # Nuevo formato: artista - álbum - canción
                display_text = f"{artist} - {album} - {title}"
                
                self.results_list.addItem(display_text)
                self.results_list.item(self.results_list.count() - 1).setData(
                    Qt.ItemDataRole.UserRole, row)
                
        except Exception as e:
            print(f"Error en la búsqueda: {e}")
            import traceback
            traceback.print_exc()
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
            subprocess.Popen([reproductor, file_path])

    def open_folder(self):
        current = self.results_list.currentItem()
        if current:
            file_path = current.data(Qt.ItemDataRole.UserRole)[1]
            folder_path = str(Path(file_path).parent)
            subprocess.Popen(['thunar', folder_path])

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
    parser.add_argument('--font', default='Inter', help='Fuente a usar en la interfaz')
    
    args = parser.parse_args()
    
    app = QApplication(sys.argv)
    browser = MusicBrowser(args.db_path, font_family=args.font)
    browser.show()
    sys.exit(app.exec())