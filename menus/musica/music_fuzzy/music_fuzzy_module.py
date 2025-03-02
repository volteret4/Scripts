import sys
import os
from typing import Optional, List, Dict
from pathlib import Path
import sqlite3
import json
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLineEdit, QPushButton, QListWidget,
                            QListWidgetItem, QLabel, QScrollArea, QSplitter,
                            QAbstractItemView, QSpinBox, QComboBox, QSizePolicy)
from PyQt6.QtGui import QPixmap, QShortcut, QKeySequence, QColor
from PyQt6.QtCore import Qt, QSize, QDate
import subprocess
import importlib.util
from base_module import BaseModule, THEME  # Importar la clase base
import glob
import random

reproductor = 'deadbeef'


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
    pass

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
            'd:': 'date',
            'w:': 'weeks',      # Últimas X semanas
            'm:': 'months',     # Últimos X meses
            'y:': 'years',      # Últimos X años
            'am:': 'added_month', # Añadido en mes X del año Y
            'ay:': 'added_year'   # Añadido en año Z
        }

    def build_sql_conditions(self, parsed_query: Dict) -> tuple:
        """Construye las condiciones SQL y parámetros basados en la query parseada."""
        conditions = []
        params = []
        
        # Procesar filtros específicos
        for field, value in parsed_query['filters'].items():
            if field in ['weeks', 'months', 'years']:
                try:
                    value = int(value)
                    if field == 'weeks':
                        conditions.append("s.last_modified >= datetime('now', '-' || ? || ' weeks')")
                    elif field == 'months':
                        conditions.append("s.last_modified >= datetime('now', '-' || ? || ' months')")
                    else:  # years
                        conditions.append("s.last_modified >= datetime('now', '-' || ? || ' years')")
                    params.append(value)
                except ValueError:
                    print(f"Valor inválido para {field}: {value}")
                    continue
            elif field == 'added_month':
                try:
                    month, year = value.split('/')
                    month = int(month)
                    year = int(year)
                    conditions.append("strftime('%m', s.last_modified) = ? AND strftime('%Y', s.last_modified) = ?")
                    params.extend([f"{month:02d}", str(year)])
                except (ValueError, TypeError):
                    print(f"Formato inválido para mes/año: {value}")
                    continue
            elif field == 'added_year':
                try:
                    year = int(value)
                    conditions.append("strftime('%Y', s.last_modified) = ?")
                    params.append(str(year))
                except ValueError:
                    print(f"Año inválido: {value}")
                    continue
            elif field == 'bitrate':
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

class MusicBrowser(BaseModule):
    def __init__(self, parent=None, **kwargs):
        # Extraer los argumentos específicos de MusicBrowser
        self.db_path = kwargs.pop('db_path', '')
        self.font_family = kwargs.pop('font_family', 'Inter')
        self.artist_images_dir = kwargs.pop('artist_images_dir', '')


        # Llamar al constructor de la clase padre con los argumentos restantes
        super().__init__(parent=parent, **kwargs)
        
        # Inicializar componentes específicos de MusicBrowser
        self.search_parser = SearchParser()
        self.setup_shortcuts()

    def init_ui(self):
        """Inicializa la interfaz del módulo."""
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(10, 10, 10, 10)

        # Contenedor superior
        top_container = QWidget()
        top_container.setMaximumHeight(150)  # Aumentado para acomodar los nuevos controles
        top_layout = QVBoxLayout(top_container)
        top_layout.setSpacing(5)
        
        # Inicializar los botones antes de usarlos
        self.play_button = QPushButton('Reproducir')
        self.folder_button = QPushButton('Abrir Carpeta')
        self.custom_button1 = QPushButton('Script 1')
        self.custom_button2 = QPushButton('Script 2')
        self.custom_button3 = QPushButton('Script 3')
        
        # Barra de búsqueda
        search_layout = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText('Buscar...')
        self.search_box.textChanged.connect(self.search)
        search_layout.addWidget(self.search_box)

        # Botones existentes
        for button in [self.play_button, self.folder_button, 
                    self.custom_button1, self.custom_button2, self.custom_button3]:
            button.setFixedWidth(100)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            search_layout.addWidget(button)

        top_layout.addLayout(search_layout)

        # Nuevo layout para filtros temporales
        time_filters_layout = QHBoxLayout()

        # Filtro de últimas X unidades de tiempo
        time_unit_layout = QHBoxLayout()
        self.time_value = QSpinBox()
        self.time_value.setRange(1, 999)
        self.time_value.setValue(1)
        time_unit_layout.addWidget(self.time_value)

        self.time_unit = QComboBox()
        self.time_unit.addItems(['Semanas', 'Meses', 'Años'])
        time_unit_layout.addWidget(self.time_unit)

        self.apply_time_filter = QPushButton('Aplicar')
        self.apply_time_filter.clicked.connect(self.apply_temporal_filter)
        time_unit_layout.addWidget(self.apply_time_filter)
        time_filters_layout.addLayout(time_unit_layout)

        # Separador
        time_filters_layout.addWidget(QLabel('|'))

        # Filtro de mes/año específico
        month_year_layout = QHBoxLayout()
        self.month_combo = QComboBox()
        self.month_combo.addItems([f"{i:02d}" for i in range(1, 13)])
        month_year_layout.addWidget(self.month_combo)

        self.year_spin = QSpinBox()
        self.year_spin.setRange(1900, 2100)
        self.year_spin.setValue(QDate.currentDate().year())
        month_year_layout.addWidget(self.year_spin)

        self.apply_month_year = QPushButton('Filtrar por Mes/Año')
        self.apply_month_year.clicked.connect(self.apply_month_year_filter)
        month_year_layout.addWidget(self.apply_month_year)
        time_filters_layout.addLayout(month_year_layout)

        # Separador
        time_filters_layout.addWidget(QLabel('|'))

        # Filtro de año específico
        year_layout = QHBoxLayout()
        self.year_only_spin = QSpinBox()
        self.year_only_spin.setRange(1900, 2100)
        self.year_only_spin.setValue(QDate.currentDate().year())
        year_layout.addWidget(self.year_only_spin)

        self.apply_year = QPushButton('Filtrar por Año')
        self.apply_year.clicked.connect(self.apply_year_filter)
        year_layout.addWidget(self.apply_year)
        time_filters_layout.addLayout(year_layout)

        top_layout.addLayout(time_filters_layout)

        # Leyenda de filtros
        legend_label = QLabel(
            '<span style="color: #7aa2f7;">'
            'Filtros: a:artista - b:álbum - g:género - l:sello - t:título - aa:album-artist - br:bitrate - d:fecha - '
            'w:semanas - m:meses - y:años - am:mes/año - ay:año'
            '</span>'
        )
        legend_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        top_layout.addWidget(legend_label)

        layout.addWidget(top_container)

        # Splitter principal: lista de resultados y panel de detalles
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Panel izquierdo (resultados)
        self.results_list = QListWidget()
        self.results_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.results_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.results_list.currentItemChanged.connect(self.handle_item_change)
        self.results_list.itemClicked.connect(self.handle_item_click)
        self.results_list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        main_splitter.addWidget(self.results_list)

        # Panel derecho (detalles)
        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Splitter vertical para separar imágenes y texto
        details_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Contenedor superior para las imágenes (colocadas horizontalmente)
        images_container = QWidget()
        images_layout = QHBoxLayout(images_container)
        images_layout.setSpacing(10)
        images_layout.setContentsMargins(5, 5, 5, 5)
        images_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        # Cover del álbum
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(300, 300)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setStyleSheet("border: 1px solid #333;")
        images_layout.addWidget(self.cover_label)
        
        # Imagen del artista
        self.artist_image_label = QLabel()
        self.artist_image_label.setFixedSize(300, 300)
        self.artist_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.artist_image_label.setStyleSheet("border: 1px solid #333;")
        images_layout.addWidget(self.artist_image_label)
        
        # Añadir el contenedor de imágenes al splitter vertical
        details_splitter.addWidget(images_container)
        
        # Contenedor para el scroll con la información
        info_container = QWidget()
        info_container_layout = QVBoxLayout(info_container)
        info_container_layout.setContentsMargins(5, 5, 5, 5)
        info_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        

        
        # ScrollArea para la información
        self.info_scroll = QScrollArea()
        self.info_scroll.setWidgetResizable(True)
        self.info_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.info_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.info_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.info_scroll.setMinimumWidth(max(self.cover_label.width() + self.artist_image_label.width() + 20, 800))
        
        # Widget interior del scroll
        self.info_widget = QWidget()
        self.info_layout = QVBoxLayout(self.info_widget)
        self.info_layout.setContentsMargins(5, 5, 5, 5)
        

        
        # Labels para la información
        self.lastfm_label = QLabel()
        self.lastfm_label.setWordWrap(True)
        self.lastfm_label.setTextFormat(Qt.TextFormat.RichText)
        self.lastfm_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.lastfm_label.setMinimumWidth(1600)  # Ajusta este valor según necesites

        self.metadata_label = QLabel()
        self.metadata_label.setWordWrap(True)
        self.metadata_label.setTextFormat(Qt.TextFormat.RichText)
        self.metadata_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.metadata_label.setMinimumWidth(1600)  # Ajusta este valor según necesites
        
        # Agregar las etiquetas al layout
        self.info_layout.addWidget(self.lastfm_label)
        self.info_layout.addWidget(self.metadata_label)
        self.info_layout.addStretch()
        
        # Configurar el ScrollArea
        self.info_scroll.setWidget(self.info_widget)
        info_container_layout.addWidget(self.info_scroll)
        
        # Añadir el contenedor de información al splitter vertical
        details_splitter.addWidget(info_container)
        
        # Configurar proporciones iniciales del splitter vertical (imágenes/información)
        details_splitter.setSizes([300, 800])
        
        # Añadir el splitter vertical al layout de detalles
        details_layout.addWidget(details_splitter)
        
        # Añadir el panel de detalles al splitter principal
        main_splitter.addWidget(details_widget)
        
        # Configurar proporciones iniciales del splitter principal (lista/detalles)
        main_splitter.setSizes([400, 800])
        
        # Añadir el splitter principal al layout de la ventana
        layout.addWidget(main_splitter)
        
        # Aplicar el tema
        self.apply_theme()



    def apply_temporal_filter(self):
        """Aplica el filtro de últimas X unidades de tiempo."""
        value = self.time_value.value()
        unit = self.time_unit.currentText()
        
        filter_map = {
            'Semanas': 'w',
            'Meses': 'm',
            'Años': 'y'
        }
        
        unit_code = filter_map.get(unit, 'w')
        self.search_box.setText(f"{unit_code}:{value}")
        self.search()

    def apply_month_year_filter(self):
        """Aplica el filtro de mes/año específico."""
        month = self.month_combo.currentText()
        year = self.year_spin.value()
        self.search_box.setText(f"am:{month}/{year}")
        self.search()

    def apply_year_filter(self):
        """Aplica el filtro de año específico."""
        year = self.year_only_spin.value()
        self.search_box.setText(f"ay:{year}")
        self.search()


    def handle_item_click(self, item):
        """Maneja el clic en un ítem. Ya no es necesario hacer nada aquí
        porque handle_item_change se encargará de todo."""
        pass  # La funcionalidad ahora está en handle_item_change


    def handle_item_change(self, current, previous):
        """Maneja el cambio de ítem seleccionado, ya sea por clic o navegación con teclado."""
        if not current:
            self.clear_details()
            return
            
        if current.is_header:
            self.clear_details()
            self.show_album_info(current)
        else:
            self.clear_details()
            self.show_details(current, previous)


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

    def find_artist_image(self, artist_name: str) -> Optional[str]:
        """Busca la imagen del artista en el directorio especificado y retorna una aleatoria si hay varias."""
        if not self.artist_images_dir or not artist_name:
            return None
        
        # Importar random para selección aleatoria
        import random
        
        # Normalizar el nombre del artista (quitar acentos, convertir a minúsculas)
        import unicodedata
        artist_name_norm = unicodedata.normalize('NFKD', artist_name.lower()) \
            .encode('ASCII', 'ignore').decode('utf-8')
        
        # Probar diferentes formatos de nombre
        name_formats = [
            artist_name,  # Original
            artist_name.replace(' ', '_'),  # Con guiones bajos
            artist_name.replace(' ', '-'),  # Con guiones
            artist_name_norm,  # Normalizado
            artist_name_norm.replace(' ', '_'),
            artist_name_norm.replace(' ', '-')
        ]
        
        # Extensiones comunes de imagen
        extensions = ['jpg', 'jpeg', 'png', 'webp', 'gif']
        
        # Lista para almacenar todas las imágenes encontradas
        all_matching_files = []
        
        # Probar todas las combinaciones
        for name in name_formats:
            # Búsqueda exacta con diferentes extensiones
            for ext in extensions:
                path = os.path.join(self.artist_images_dir, f"{name}.{ext}")
                if os.path.exists(path):
                    all_matching_files.append(path)
            
            # Búsqueda con patrón glob (para archivos que empiezan con el nombre)
            pattern = os.path.join(self.artist_images_dir, f"{name}*")
            matching_files = glob.glob(pattern)
            # Filtrar por extensiones válidas
            for file in matching_files:
                ext = file.lower().split('.')[-1]
                if ext in extensions:
                    all_matching_files.append(file)
        
        # Eliminar duplicados
        all_matching_files = list(set(all_matching_files))
        
        # Si se encontraron imágenes, devolver una aleatoria
        if all_matching_files:
            return random.choice(all_matching_files)
        
        return None

    # Modificar la función show_album_info para mostrar los enlaces del álbum
    def show_album_info(self, header_item):
        """Muestra la información del álbum."""
        # Obtener artista y álbum del texto del header
        album_info = header_item.text().replace("📀 ", "").split(" - ")
        if len(album_info) != 2:
            return
            
        artist, album = album_info
        
        # Contar canciones y obtener información del álbum
        total_tracks = 0
        total_duration = 0
        album_paths = []
        first_track_data = None
        
        # Recorrer los items después del header hasta el siguiente header
        index = self.results_list.row(header_item) + 1
        while index < self.results_list.count():
            item = self.results_list.item(index)
            if item.is_header:
                break
                
            data = item.data(Qt.ItemDataRole.UserRole)
            if data:
                if not first_track_data:
                    first_track_data = data
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
        
        # Buscar la carátula usando la ruta del primer track
        self.clear_details()  # Limpiar imágenes primero
        
        if first_track_data and len(first_track_data) > 1:
            # Mostrar la carátula del álbum
            cover_path = self.find_cover_image(first_track_data[1])
            if cover_path:
                pixmap = QPixmap(cover_path)
                pixmap = pixmap.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio)
                self.cover_label.setPixmap(pixmap)
            else:
                self.cover_label.setText("No imagen")
                
            # Nuevo: Mostrar la imagen del artista
            artist_image_path = self.find_artist_image(artist)
            if artist_image_path:
                artist_pixmap = QPixmap(artist_image_path)
                artist_pixmap = artist_pixmap.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio)
                self.artist_image_label.setPixmap(artist_pixmap)
            else:
                self.artist_image_label.setText("No imagen de artista")
        
        # Mostrar la información en el panel de detalles
        if first_track_data:
            # Crear el contenido para el panel de información (LastFM + Wikipedia)
            info_text = ""
            
            # Mostrar info de LastFM si está disponible
            artist_bio = first_track_data[15] if len(first_track_data) > 15 and first_track_data[15] else "No hay información del artista disponible"
            info_text += f"<h3>Información del Artista (LastFM):</h3>{artist_bio}<br><br>"
            
            # Mostrar info de Wikipedia del artista (índice 27)
            if len(first_track_data) > 27 and first_track_data[27]:
                info_text += f"<h3>Wikipedia - Artista:</h3>{first_track_data[27]}<br><br>"
            
            # Mostrar info de Wikipedia del álbum (índice 29)
            if len(first_track_data) > 29 and first_track_data[29]:
                info_text += f"<h3>Wikipedia - Álbum:</h3>{first_track_data[29]}<br><br>"
                
            self.lastfm_label.setText(info_text)
            
            # Construir la metadata básica del álbum
            metadata = f"""
                <b>Álbum:</b> {album}<br>
                <b>Artista:</b> {artist}<br>
                <b>Fecha:</b> {first_track_data[6] or 'N/A'}<br>
                <b>Género:</b> {first_track_data[7] or 'N/A'}<br>
                <b>Sello:</b> {first_track_data[8] or 'N/A'}<br>
                <b>Pistas:</b> {total_tracks}<br>
                <b>Duración total:</b> {hours:02d}:{minutes:02d}:{seconds:02d}<br>
                <b>Bitrate:</b> {first_track_data[10] or 'N/A'} kbps<br>
            """
            
            # Añadir enlaces externos del álbum si existen
            if len(first_track_data) > 21:
                metadata += "<br><b>Enlaces del Álbum:</b><br>"
                
                album_links = []
                if first_track_data[21]:  # album_spotify
                    album_links.append(f"<a href='{first_track_data[21]}'>Spotify</a>")
                if first_track_data[22]:  # album_youtube
                    album_links.append(f"<a href='{first_track_data[22]}'>YouTube</a>")
                if first_track_data[23]:  # album_musicbrainz
                    album_links.append(f"<a href='{first_track_data[23]}'>MusicBrainz</a>")
                if first_track_data[24]:  # album_discogs
                    album_links.append(f"<a href='{first_track_data[24]}'>Discogs</a>")
                if first_track_data[25]:  # album_rateyourmusic
                    album_links.append(f"<a href='{first_track_data[25]}'>RateYourMusic</a>")
                if first_track_data[28]:  # album_wikipedia_url (nuevo campo)
                    album_links.append(f"<a href='{first_track_data[28]}'>Wikipedia</a>")
                
                if album_links:
                    metadata += " | ".join(album_links)
                else:
                    metadata += "No hay enlaces disponibles."
            
            # Añadir enlaces externos del artista si existen
            if len(first_track_data) > 16:
                metadata += "<br><br><b>Enlaces del Artista:</b><br>"
                
                artist_links = []
                if first_track_data[16]:  # artist_spotify
                    artist_links.append(f"<a href='{first_track_data[16]}'>Spotify</a>")
                if first_track_data[17]:  # artist_youtube
                    artist_links.append(f"<a href='{first_track_data[17]}'>YouTube</a>")
                if first_track_data[18]:  # artist_musicbrainz
                    artist_links.append(f"<a href='{first_track_data[18]}'>MusicBrainz</a>")
                if first_track_data[19]:  # artist_discogs
                    artist_links.append(f"<a href='{first_track_data[19]}'>Discogs</a>")
                if first_track_data[20]:  # artist_rateyourmusic
                    artist_links.append(f"<a href='{first_track_data[20]}'>RateYourMusic</a>")
                if first_track_data[26]:  # artist_wikipedia_url (nuevo campo)
                    artist_links.append(f"<a href='{first_track_data[26]}'>Wikipedia</a>")
                
                if artist_links:
                    metadata += " | ".join(artist_links)
                else:
                    metadata += "No hay enlaces disponibles."
            
            metadata += "<br><br><i>Presiona Enter para reproducir el álbum completo</i><br>"
            metadata += "<i>Presiona Ctrl+O para abrir la carpeta del álbum</i>"
            
            self.metadata_label.setText(metadata)
            self.metadata_label.setOpenExternalLinks(True)
        else:
            self.clear_details()


    def setup_shortcuts(self):
        # Enter para reproducir
        QShortcut(QKeySequence(Qt.Key.Key_Return), self, self.play_item)
        # Ctrl+O para abrir carpeta
        QShortcut(QKeySequence("Ctrl+O"), self, self.open_folder)
        # Ctrl+F para focus en búsqueda
        QShortcut(QKeySequence("Ctrl+F"), self, self.search_box.setFocus)

    def apply_theme(self):
        """Aplica el tema específico del módulo."""
        self.setStyleSheet(f"""
            QLabel {{
                font-size: 12px;
                max-width: 100%;
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
            #lastfm_label, #metadata_label {{
                padding: 5px;
                min-width: 750px;
            }}
            QScrollArea {{
                border: none;
            }}
        """)
        
        # Set object names for the labels so the CSS can target them
        self.lastfm_label.setObjectName("lastfm_label")
        self.metadata_label.setObjectName("metadata_label")

        
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
            # Limpiar detalles anteriores
            self.clear_details()
            
            # Extraer el nombre del artista de los datos (índice 3)
            artist = data[3] if len(data) > 3 and data[3] else ""
            
            # Mostrar carátula
            if len(data) > 1:
                cover_path = self.find_cover_image(data[1])
                if cover_path:
                    pixmap = QPixmap(cover_path)
                    pixmap = pixmap.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio)
                    self.cover_label.setPixmap(pixmap)
                else:
                    self.cover_label.setText("No imagen")
                    
                # Mostrar imagen del artista usando el nombre extraído
                if artist:
                    artist_image_path = self.find_artist_image(artist)
                    if artist_image_path:
                        artist_pixmap = QPixmap(artist_image_path)
                        artist_pixmap = artist_pixmap.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio)
                        self.artist_image_label.setPixmap(artist_pixmap)
                    else:
                        self.artist_image_label.setText("No imagen de artista")
                else:
                    self.artist_image_label.setText("No imagen de artista")
            else:
                self.cover_label.setText("No imagen")
                self.artist_image_label.setText("No imagen de artista")

            # Mostrar información en el widget scrollable
            info_text = ""
            
            # Mostrar letra de la canción si está disponible (nuevos campos añadidos)
            lyrics = data[30] if len(data) > 30 and data[30] else None
            lyrics_source = data[31] if len(data) > 31 and data[31] else "Desconocida"
            
            if lyrics:
                info_text += f"<h3>Letra</h3><div style='white-space: pre-wrap;'>{lyrics}</div>"
                info_text += f"<p><i>Fuente: {lyrics_source}</i></p><hr>"
            
            # Mostrar info de LastFM (bio del artista)
            artist_bio = data[15] if len(data) > 15 and data[15] else "No hay información del artista disponible"
            info_text += f"<h3>Información del Artista (LastFM):</h3>{artist_bio}<br><br>"

            # Mostrar info de Wikipedia del artista (nuevos campos)
            if len(data) > 27:  # Verificar que los nuevos campos existen
                artist_wiki_content = data[27] if data[27] else "No hay información de Wikipedia disponible para este artista"
                info_text += f"<h3>Wikipedia - Artista:</h3>{artist_wiki_content}<br><br>"

            # Asignar el contenido actualizado
            self.lastfm_label.setText(info_text)

            # Mostrar metadata
            if len(data) >= 15:  # Aseguramos que tengamos todos los campos necesarios
                track_num = data[14] if data[14] else "N/A"  # track_number está en el índice 14
                
                # Construir la sección de metadata básica
                metadata = f"""
                    <b>Título:</b> {data[2] or 'N/A'}<br>
                    <b>Artista:</b> {artist or 'N/A'}<br>
                    <b>Album Artist:</b> {data[4] or 'N/A'}<br>
                    <b>Álbum:</b> {data[5] or 'N/A'}<br>
                    <b>Fecha:</b> {data[6] or 'N/A'}<br>
                    <b>Género:</b> {data[7] or 'N/A'}<br>
                    <b>Sello:</b> {data[8] or 'N/A'}<br>
                    <b>MBID:</b> {data[9] or 'N/A'}<br>
                    <b>Bitrate:</b> {data[10] or 'N/A'} kbps<br>
                    <b>Profundidad:</b> {data[11] or 'N/A'} bits<br>
                    <b>Frecuencia:</b> {data[12] or 'N/A'} Hz<br>
                    <b>Número de pista:</b> {track_num}<br>
                """
                
                # Añadir enlaces externos del artista si existen
                if len(data) > 16:
                    metadata += "<br><b>Enlaces del Artista:</b><br>"
                    
                    artist_links = []
                    if data[16]:  # spotify_url
                        artist_links.append(f"<a href='{data[16]}'>Spotify</a>")
                    if data[17]:  # youtube_url
                        artist_links.append(f"<a href='{data[17]}'>YouTube</a>")
                    if data[18]:  # musicbrainz_url
                        artist_links.append(f"<a href='{data[18]}'>MusicBrainz</a>")
                    if data[19]:  # discogs_url
                        artist_links.append(f"<a href='{data[19]}'>Discogs</a>")
                    if data[20]:  # rateyourmusic_url
                        artist_links.append(f"<a href='{data[20]}'>RateYourMusic</a>")
                    if data[26]:  # artist_wikipedia_url (nuevo campo)
                        artist_links.append(f"<a href='{data[26]}'>Wikipedia</a>")
                    
                    if artist_links:
                        metadata += " | ".join(artist_links)
                    else:
                        metadata += "No hay enlaces disponibles."
                
                self.metadata_label.setText(metadata)
                self.metadata_label.setOpenExternalLinks(True)
            else:
                self.metadata_label.setText("No hay suficientes datos de metadata")
                
        except Exception as e:
            print(f"Error al mostrar detalles: {e}")
            self.clear_details()

    def search(self):
        query = self.search_box.text()
        parsed = self.search_parser.parse_query(query)
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Base SQL query con join a tabla artists, albums y lyrics para obtener letras y otra información
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
                s.track_number,
                art.bio,
                art.spotify_url AS artist_spotify,
                art.youtube_url AS artist_youtube,
                art.musicbrainz_url AS artist_musicbrainz,
                art.discogs_url AS artist_discogs,
                art.rateyourmusic_url AS artist_rateyourmusic,
                alb.spotify_url AS album_spotify,
                alb.youtube_url AS album_youtube,
                alb.musicbrainz_url AS album_musicbrainz,
                alb.discogs_url AS album_discogs,
                alb.rateyourmusic_url AS album_rateyourmusic,
                art.wikipedia_url AS artist_wikipedia_url,
                art.wikipedia_content AS artist_wikipedia_content,
                alb.wikipedia_url AS album_wikipedia_url,
                alb.wikipedia_content AS album_wikipedia_content,
                lyr.lyrics,
                lyr.source AS lyrics_source
            FROM songs s
            LEFT JOIN artists art ON s.artist = art.name
            LEFT JOIN albums alb ON s.album = alb.name 
            LEFT JOIN artists album_artist ON alb.artist_id = album_artist.id AND s.artist = album_artist.name
            LEFT JOIN lyrics lyr ON s.id = lyr.track_id
        """
        
        # Use build_sql_conditions from SearchParser
        conditions, params = self.search_parser.build_sql_conditions(parsed)
        
        # Add WHERE clause if there are conditions
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        
        # Ordering
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
                track_number = row[14] if row[14] else "0"
                
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


    def clear_details(self):
        """Limpia todos los campos de detalles."""
        self.cover_label.clear()
        self.cover_label.setText("No imagen")

        self.lastfm_label.setText("")
        self.metadata_label.setText("")
        
        self.artist_image_label.clear()
        self.artist_image_label.setText("No imagen")

            # Forzar actualización visual
        self.cover_label.update()
        self.artist_image_label.update()

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
        
        # Solo procesar las flechas si la lista de resultados tiene el foco
        if self.results_list.hasFocus():
            if event.key() in [Qt.Key.Key_Left, Qt.Key.Key_Right]:
                self.navigate_headers(event.key())
                event.accept()
                return
                
        current_item = self.results_list.currentItem()
        if current_item and current_item.is_header:
            if event.key() == Qt.Key.Key_Return:
                self.play_album()
                event.accept()
                return
            elif event.key() == Qt.Key.Key_O and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                self.open_album_folder()
                event.accept()
                return
                
        super().keyPressEvent(event)

    def navigate_headers(self, key):
        """Navega entre los headers de álbumes usando las flechas izquierda/derecha."""
        current_row = self.results_list.currentRow()
        if current_row == -1:
            return
            
        total_items = self.results_list.count()
        header_positions = []
        
        # Encontrar todas las posiciones de los headers
        for i in range(total_items):
            item = self.results_list.item(i)
            if item and getattr(item, 'is_header', False):
                header_positions.append(i)
        
        if not header_positions:
            return
            
        # Encontrar el header actual o el más cercano
        current_header_index = -1
        for i, pos in enumerate(header_positions):
            if key == Qt.Key.Key_Right:
                # Para flecha derecha, buscar el siguiente header
                if pos > current_row:
                    current_header_index = i
                    break
            else:
                # Para flecha izquierda, buscar el header anterior
                if pos >= current_row:
                    current_header_index = i - 1
                    break
        
        # Si no encontramos un header siguiente, ir al primero
        if key == Qt.Key.Key_Right and current_header_index == -1:
            current_header_index = 0
        # Si no encontramos un header anterior, ir al último
        elif key == Qt.Key.Key_Left and current_header_index == -1:
            current_header_index = len(header_positions) - 1
        
        # Asegurarse de que el índice es válido
        if 0 <= current_header_index < len(header_positions):
            # Seleccionar el nuevo header
            new_row = header_positions[current_header_index]
            self.results_list.setCurrentRow(new_row)
            self.results_list.scrollToItem(
                self.results_list.item(new_row),
                QAbstractItemView.ScrollHint.PositionAtCenter
            )


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
    parser.add_argument('--artist-images-dir', help='Carpeta donde buscar las imágenes de los artistas')

    args = parser.parse_args()
    
    app = QApplication(sys.argv)
    browser = MusicBrowser(
        args.db_path,
        font_family=args.font,
        artist_images_dir=args.artist_images_dir
    )
    browser.show()
    sys.exit(app.exec())