import sys
import os
from typing import Optional, List, Dict
from pathlib import Path
import sqlite3
import json
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLineEdit, QPushButton, QListWidget,
                            QListWidgetItem, QLabel, QScrollArea, QSplitter)
from PyQt6.QtGui import QPixmap, QShortcut, QKeySequence, QColor
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

class GroupedListItem(QListWidgetItem):
    def __init__(self, text, is_header=False, paths=None):
        super().__init__(text)
        self.is_header = is_header
        self.paths = paths or []
        if is_header:
            font = self.font()
            font.setBold(True)
            font.setPointSize(font.pointSize() + 2)
            self.setFont(font)
            self.setBackground(QColor(THEME['secondary_bg']))
            self.setForeground(QColor(THEME['accent']))

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
        self.search_box.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        search_layout.addWidget(self.search_box)

        # Botones
        self.play_button = QPushButton('Reproducir')
        self.folder_button = QPushButton('Abrir Carpeta')
        self.custom_button1 = QPushButton('Script 1')
        self.custom_button2 = QPushButton('Script 2')
        self.custom_button3 = QPushButton('Script 3')

        # Configurar políticas de foco para los botones
        for button in [self.play_button, self.folder_button, 
                    self.custom_button1, self.custom_button2, self.custom_button3]:
            button.setFixedWidth(100)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
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
        self.results_list.itemClicked.connect(self.handle_item_click)
        self.results_list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
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

    def handle_item_click(self, item):
        if item.is_header:
            self.show_album_info(item)

    def show_album_info(self, header_item):
        # Obtener artista y álbum del texto del header
        album_info = header_item.text().replace("📀 ", "").split(" - ")
        if len(album_info) != 2:
            return
            
        artist, album = album_info
        
        # Contar canciones y obtener información del álbum
        total_tracks = 0
        total_duration = 0
        album_paths = []
        
        # Recorrer los items después del header hasta el siguiente header
        index = self.results_list.row(header_item) + 1
        while index < self.results_list.count():
            item = self.results_list.item(index)
            if item.is_header:
                break
                
            data = item.data(Qt.ItemDataRole.UserRole)
            if data:
                total_tracks += 1
                if len(data) > 15:  # Asegurarse de que existe el campo duration
                    try:
                        total_duration += float(data[15])
                    except (ValueError, TypeError):
                        pass
                album_paths.extend(item.paths)
            index += 1
        
        # Guardar las rutas en el header para usarlas en play_album y open_album_folder
        header_item.paths = album_paths
        
        # Formatear la duración total
        hours = int(total_duration // 3600)
        minutes = int((total_duration % 3600) // 60)
        seconds = int(total_duration % 60)
        
        # Mostrar la información en el panel de detalles
        album_info = f"""
            <b>Álbum:</b> {album}<br>
            <b>Artista:</b> {artist}<br>
            <b>Pistas:</b> {total_tracks}<br>
            <b>Duración total:</b> {hours:02d}:{minutes:02d}:{seconds:02d}<br>
            <br>
            <i>Presiona Enter para reproducir el álbum completo</i><br>
            <i>Presiona Ctrl+O para abrir la carpeta del álbum</i>
        """
        self.metadata_label.setText(album_info)


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
        
        # Consulta base modificada para usar la tabla artists en lugar de artist_info
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
                a.bio,
                s.track_number
            FROM songs s
            LEFT JOIN artists a ON s.artist = a.name
        """
        
        conditions = []
        params = []

        # Procesar filtros específicos
        for field, value in parsed['filters'].items():
            if field == 'bitrate':
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

        # Ordenar por artista, álbum y número de pista
        sql += " ORDER BY s.artist, s.album, CAST(s.track_number AS INTEGER)"
        
        try:
            c.execute(sql, params)
            results = c.fetchall()
            
            self.results_list.clear()
            current_album = None
            
            for row in results:
                artist = row[3] if row[3] else "Sin artista"
                album = row[5] if row[5] else "Sin álbum"
                title = row[2] if row[2] else "Sin título"
                track_number = row[15] if row[15] else "0"
                
                # Si cambiamos de álbum, añadir header
                album_key = f"{artist} - {album}"
                if album_key != current_album:
                    header_item = GroupedListItem(f"📀 {album_key}", is_header=True)
                    self.results_list.addItem(header_item)
                    current_album = album_key
                
                # Añadir la canción con su número de pista
                try:
                    track_num = int(track_number)
                    display_text = f"    {track_num:02d}. {title}"
                except (ValueError, TypeError):
                    display_text = f"    --. {title}"
                
                item = GroupedListItem(display_text, paths=[row[1]])
                item.setData(Qt.ItemDataRole.UserRole, row)
                self.results_list.addItem(item)
                
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
        """Muestra los detalles del ítem seleccionado."""
        if not current:
            self.clear_details()
            return

        data = current.data(Qt.ItemDataRole.UserRole)
        if not data:
            self.clear_details()
            return

        try:
            # Mostrar carátula
            if len(data) > 1:
                cover_path = self.find_cover_image(data[1])
                if cover_path:
                    pixmap = QPixmap(cover_path)
                    pixmap = pixmap.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio)
                    self.cover_label.setPixmap(pixmap)
                else:
                    self.cover_label.setText("No imagen")
            else:
                self.cover_label.setText("No imagen")

            # Mostrar info de LastFM
            lastfm_text = data[-1] if len(data) > 14 and data[-1] else "No hay información de LastFM disponible"
            self.lastfm_label.setText(f"<b>Información del Artista:</b><br>{lastfm_text}")

            # Mostrar metadata si hay suficientes datos
            if len(data) > 12:
                metadata = f"""
                    <b>Título:</b> {data[2] or 'N/A'}<br>
                    <b>Artista:</b> {data[3] or 'N/A'}<br>
                    <b>Album Artist:</b> {data[4] or 'N/A'}<br>
                    <b>Álbum:</b> {data[5] or 'N/A'}<br>
                    <b>Fecha:</b> {data[6] or 'N/A'}<br>
                    <b>Género:</b> {data[7] or 'N/A'}<br>
                    <b>Sello:</b> {data[8] or 'N/A'}<br>
                    <b>MBID:</b> {data[9] or 'N/A'}<br>
                    <b>Bitrate:</b> {data[10] or 'N/A'} kbps<br>
                    <b>Profundidad:</b> {data[11] or 'N/A'} bits<br>
                    <b>Frecuencia:</b> {data[12] or 'N/A'} Hz<br>
                """
                self.metadata_label.setText(metadata)
            else:
                self.metadata_label.setText("No hay suficientes datos de metadata")
                
        except Exception as e:
            print(f"Error al mostrar detalles: {e}")
            self.clear_details()

    def clear_details(self):
        """Limpia todos los campos de detalles."""
        self.cover_label.setText("No imagen")
        self.lastfm_label.setText("")
        self.metadata_label.setText("")

    def play_item(self):
        """Reproduce el ítem seleccionado con verificaciones de seguridad."""
        current = self.results_list.currentItem()
        if not current:
            print("No hay ítem seleccionado")
            return
            
        # Verificar si es un header
        if getattr(current, 'is_header', False):
            self.play_album()
            return
            
        # Obtener los datos del ítem
        data = current.data(Qt.ItemDataRole.UserRole)
        if not data:
            print("No hay datos asociados al ítem")
            return
            
        try:
            file_path = data[1]  # Índice 1 contiene file_path
            if not file_path or not os.path.exists(file_path):
                print(f"Ruta de archivo no válida: {file_path}")
                return
                
            subprocess.Popen([reproductor, file_path])
        except (IndexError, TypeError) as e:
            print(f"Error al acceder a los datos del ítem: {e}")
        except Exception as e:
            print(f"Error al reproducir el archivo: {e}")

    def play_album(self):
        """Reproduce todo el álbum del ítem seleccionado."""
        current_item = self.results_list.currentItem()
        if not current_item:
            return
            
        if not getattr(current_item, 'is_header', False):
            return
            
        try:
            # Recolectar todas las rutas de archivo del álbum
            album_paths = []
            index = self.results_list.row(current_item) + 1
            
            while index < self.results_list.count():
                item = self.results_list.item(index)
                if not item or getattr(item, 'is_header', False):
                    break
                    
                data = item.data(Qt.ItemDataRole.UserRole)
                if data and len(data) > 1:
                    file_path = data[1]
                    if file_path and os.path.exists(file_path):
                        album_paths.append(file_path)
                index += 1
            
            if album_paths:
                subprocess.Popen([reproductor] + album_paths)
            else:
                print("No se encontraron archivos válidos para reproducir")
                
        except Exception as e:
            print(f"Error al reproducir el álbum: {e}")

    def open_folder(self):
        """Abre la carpeta del ítem seleccionado."""
        current = self.results_list.currentItem()
        if not current:
            return
            
        try:
            if getattr(current, 'is_header', False):
                # Si es un header, abrir la carpeta del primer archivo del álbum
                index = self.results_list.row(current) + 1
                if index < self.results_list.count():
                    item = self.results_list.item(index)
                    if item:
                        data = item.data(Qt.ItemDataRole.UserRole)
                        if data and len(data) > 1:
                            file_path = data[1]
                        else:
                            return
                else:
                    return
            else:
                # Si es una canción individual
                data = current.data(Qt.ItemDataRole.UserRole)
                if not data or len(data) <= 1:
                    return
                file_path = data[1]
            
            if file_path and os.path.exists(file_path):
                folder_path = str(Path(file_path).parent)
                subprocess.Popen(['thunar', folder_path])
            else:
                print(f"Ruta no válida: {file_path}")
                
        except Exception as e:
            print(f"Error al abrir la carpeta: {e}")

    def open_album_folder(self):
        current_item = self.results_list.currentItem()
        if current_item and current_item.is_header and hasattr(current_item, 'paths') and current_item.paths:
            # Abrir la carpeta del primer archivo del álbum
            folder_path = str(Path(current_item.paths[0]).parent)
            subprocess.Popen(['thunar', folder_path])

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Tab:
            # Alternar entre la caja de búsqueda y la lista de resultados
            if self.search_box.hasFocus():
                self.results_list.setFocus()
            else:
                self.search_box.setFocus()
            event.accept()
            return
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