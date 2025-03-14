import sys
import os
import re
from typing import Optional, List, Dict, Tuple
from pathlib import Path
import sqlite3
import json
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLineEdit, QPushButton, QListWidget,
                            QListWidgetItem, QLabel, QScrollArea, QSplitter,
                            QAbstractItemView, QSpinBox, QComboBox, QSizePolicy,
                            QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
                            QCheckBox)
from PyQt6.QtGui import QPixmap, QShortcut, QKeySequence, QColor
from PyQt6.QtCore import Qt, QSize, QDate
import subprocess
import importlib.util
from base_module import BaseModule, THEMES  # Importar la clase base
import glob
import random
import urllib.parse
import time

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
            # self.setBackground(QColor(THEMES['secondary_bg']))
            # self.setForeground(QColor(THEMES['accent']))
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
        
        # Caché simple para consultas frecuentes
        self.cache = {}
        self.cache_size = 20

    def build_sql_conditions(self, parsed_query: dict) -> tuple:
        """Construye las condiciones SQL y parámetros basados en la query parseada."""
        if not parsed_query:
            return [], []
            
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
    
    def parse_query(self, query: str) -> dict:
        """Parsea la query y devuelve diccionario con filtros y término general."""
        # Verificar caché
        if query in self.cache:
            return self.cache[query]
            
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
        
        result = {
            'filters': filters,
            'general': ' '.join(general_terms)
        }
        
        # Actualizar caché
        if len(self.cache) >= self.cache_size:
            # Eliminar el primero si está lleno
            self.cache.pop(next(iter(self.cache)))
        self.cache[query] = result
        
        return result

class MusicBrowser(BaseModule):

    def __init__(self, parent=None, theme='Tokyo Night', **kwargs):
        # Extraer los argumentos específicos de MusicBrowser
        """
        Inicializa el módulo de exploración de música.

        Args:
            parent (QWidget, optional): Widget padre. Defaults to None.
            theme (str, optional): Tema de la interfaz. Defaults to 'Tokyo Night'.
            db_path (str, optional): Ruta al archivo de la base de datos de
                música. Defaults to ''.
            font_family (str, optional): Familia de fuente para la interfaz.
                Defaults to 'Inter'.
            artist_images_dir (str, optional): Directorio para las imágenes de
                artistas. Defaults to ''.
        """
        self.db_path = kwargs.pop('db_path', '')
        self.font_family = kwargs.pop('font_family', 'Inter')
        self.artist_images_dir = kwargs.pop('artist_images_dir', '')
        
        self.available_themes = kwargs.pop('temas', [])
        self.selected_theme = kwargs.pop('tema_seleccionado', theme)
        self.boton_pulsado = 0  # Estado inicial



        # Llamar al constructor de la clase padre con los argumentos restantes
        super().__init__(parent=parent, theme=theme, **kwargs)
        
        # Inicializar componentes específicos de MusicBrowser
        self.search_parser = SearchParser()
        self.setup_shortcuts()

    def init_ui(self):
        """Inicializa la interfaz del módulo."""
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(10, 10, 10, 10)

        # Contenedor superior
        self.top_container = QWidget()
        self.top_container.setMaximumHeight(50)  # Aumentado para acomodar los nuevos controles
        top_layout = QVBoxLayout(self.top_container)
        top_layout.setSpacing(5)
        
        # Inicializar los botones antes de usarlos
        self.play_button = QPushButton('Reproducir')
        self.folder_button = QPushButton('Abrir Carpeta')
        self.custom_button1 = QPushButton('Reproduciendo')
        self.custom_button2 = QPushButton('Script 2')
        self.custom_button3 = QPushButton('Script 3')
        
        # Conectar botones
        self.play_button.clicked.connect(self.play_item)
        self.folder_button.clicked.connect(self.open_folder)
        self.custom_button1.clicked.connect(self.buscar_musica_en_reproduccion)

        # Barra de búsqueda y checkbox para ajustes avanzados
        search_layout = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText('a:artista - b:álbum - g:género - l:sello - t:título - aa:album-artist - br:bitrate - d:fecha - w:semanas - m:meses - y:años - am:mes/año - ay:año')
        self.search_box.textChanged.connect(self.search)
        self.search_box.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        search_layout.addWidget(self.search_box)

        # Botones básicos (siempre visibles)
        for button in [self.play_button, self.folder_button]:
            button.setFixedWidth(100)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            search_layout.addWidget(button)
        
        # Checkbox para ajustes avanzados
        self.advanced_settings_check = QCheckBox("Más")
        self.advanced_settings_check.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.advanced_settings_check.stateChanged.connect(self.toggle_advanced_settings)
        search_layout.addWidget(self.advanced_settings_check)
        
        # Botones avanzados (inicialmente ocultos)
        self.advanced_buttons = []
        for button in [self.custom_button1, self.custom_button2, self.custom_button3]:
            button.setFixedWidth(100)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.hide()  # Ocultar inicialmente
            search_layout.addWidget(button)
            self.advanced_buttons.append(button)

        top_layout.addLayout(search_layout)

        # Nuevo layout para filtros temporales
        self.time_filters_widget = QWidget()
        time_filters_layout = QHBoxLayout(self.time_filters_widget)
        time_filters_layout.setContentsMargins(0, 0, 0, 0)
        self.time_filters_widget.hide()  # Ocultar inicialmente

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

        top_layout.addWidget(self.time_filters_widget)
        layout.addWidget(self.top_container)

        # # Leyenda de filtros
        # legend_label = QLabel(
        #     '<span style="color: #7aa2f7;">'
        #     'Filtros: a:artista - b:álbum - g:género - l:sello - t:título - aa:album-artist - br:bitrate - d:fecha - '
        #     'w:semanas - m:meses - y:años - am:mes/año - ay:año'
        #     '</span>'
        # )
        # legend_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        # legend_label.setWordWrap(True)  # Permite que el texto se ajuste a múltiples líneas
        # legend_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        # top_layout.addWidget(legend_label)


        # Splitter principal: lista de resultados y panel de detalles
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Panel izquierdo (resultados)
        self.results_list = QListWidget()
        self.results_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.results_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.results_list.currentItemChanged.connect(self.handle_item_change)
        self.results_list.itemClicked.connect(self.handle_item_click)
        self.results_list.doubleClicked.connect(self.add_to_playlist)  # Conectar doble clic para añadir a playlist
        self.results_list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        main_splitter.addWidget(self.results_list)

        # Panel derecho (detalles)
        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Crear un TabWidget para los paneles de la derecha
        self.right_tabs = QTabWidget()
        
        # Primer tab (panel original de detalles)
        details_tab = QWidget()
        details_tab_layout = QVBoxLayout(details_tab)
        details_tab_layout.setContentsMargins(0, 0, 0, 0)
        
        # Splitter vertical para separar imágenes y texto
        details_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Contenedor superior para las imágenes (colocadas horizontalmente)
        images_container = QWidget()
        images_layout = QHBoxLayout(images_container)
        images_layout.setSpacing(10)
        images_layout.setContentsMargins(45, 5, 45, 5)
        images_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        # Cover del álbum
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(200, 200)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setStyleSheet("border: 1px solid #333;")
        images_layout.addWidget(self.cover_label)
        
        # Añadir margen entre las imagenes
        images_layout.addSpacing(60)  # Añade un espacio fijo de 20 píxeles

        # Imagen del artista
        self.artist_image_label = QLabel()
        self.artist_image_label.setFixedSize(200, 200)
        self.artist_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.artist_image_label.setStyleSheet("border: 1px solid #333;")
        images_layout.addWidget(self.artist_image_label)

        # Añadir contenedor de botones verticales a la derecha
        buttons_container = QWidget()
        buttons_layout = QVBoxLayout(buttons_container)
        buttons_layout.setSpacing(10)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        
        # Botón para enviar a Spotify
        self.spotify_button = QPushButton("Enviar a Spotify")
        self.spotify_button.setFixedWidth(120)
        self.spotify_button.clicked.connect(self.handle_spotify_button)
        buttons_layout.addWidget(self.spotify_button)
        
        buttons_layout.addStretch()
        
        # Añadir el contenedor de botones al layout de imágenes
        images_layout.addWidget(buttons_container)
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
        details_splitter.setSizes([200, 800])
        
        # Añadir el splitter vertical al layout del tab de detalles
        details_tab_layout.addWidget(details_splitter)
        
        # Segundo tab (Playlist)
        playlist_tab = QWidget()
        playlist_layout = QVBoxLayout(playlist_tab)
        playlist_layout.setContentsMargins(10, 10, 10, 10)
        
        # Tabla para la playlist
        self.playlist_table = QTableWidget()
        self.playlist_table.setColumnCount(5)
        self.playlist_table.setHorizontalHeaderLabels(["Artista", "Álbum", "Canción", "Sello", "Fecha"])
        self.playlist_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.playlist_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.playlist_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.playlist_table.verticalHeader().setVisible(False)
        playlist_layout.addWidget(self.playlist_table)
        
        # Contenedor para los botones de la playlist
        playlist_buttons_container = QWidget()
        playlist_buttons_layout = QHBoxLayout(playlist_buttons_container)
        playlist_buttons_layout.setSpacing(10)
        
        # Botones para la playlist
        self.clear_playlist_button = QPushButton("Vaciar Playlist")
        self.clear_playlist_button.clicked.connect(self.clear_playlist)
        playlist_buttons_layout.addWidget(self.clear_playlist_button)
        
        self.playlist_button1 = QPushButton("Función 1")
        self.playlist_button1.clicked.connect(self.playlist_function1)
        playlist_buttons_layout.addWidget(self.playlist_button1)
        
        self.playlist_button2 = QPushButton("Función 2")
        self.playlist_button2.clicked.connect(self.playlist_function2)
        playlist_buttons_layout.addWidget(self.playlist_button2)
        
        self.playlist_button3 = QPushButton("Función 3")
        self.playlist_button3.clicked.connect(self.playlist_function3)
        playlist_buttons_layout.addWidget(self.playlist_button3)
        
        self.playlist_button4 = QPushButton("Función 4")
        self.playlist_button4.clicked.connect(self.playlist_function4)
        playlist_buttons_layout.addWidget(self.playlist_button4)
        
        playlist_layout.addWidget(playlist_buttons_container)
        
        # Añadir los tabs al TabWidget
        self.right_tabs.addTab(details_tab, "Detalles")
        self.right_tabs.addTab(playlist_tab, "Playlist")
        
        # Añadir el TabWidget al layout de detalles
        details_layout.addWidget(self.right_tabs)
        
        # Añadir el panel de detalles al splitter principal
        main_splitter.addWidget(details_widget)
        
        # Configurar proporciones iniciales del splitter principal (lista/detalles)
        main_splitter.setSizes([400, 800])
        
        # Añadir el splitter principal al layout de la ventana
        layout.addWidget(main_splitter)
        
        # Aplicar el tema
        self.apply_theme()
        
        # Configurar evento para la tecla espacio
        self.setup_space_key()

    def setup_space_key(self):
        """Configura el evento para añadir a playlist al presionar espacio"""
        self.results_list.keyPressEvent = self.custom_key_press_event

    def custom_key_press_event(self, event):
        """Maneja eventos de teclado en la lista de resultados"""
        if event.key() == Qt.Key.Key_Space:
            self.add_to_playlist()
        # Llamar al método original para manejar otros eventos de teclado
        QListWidget.keyPressEvent(self.results_list, event)

    def toggle_advanced_settings(self, state):
        """Muestra u oculta los elementos de configuración avanzada según el estado del checkbox"""
        
        # Verificar el estado del checkbox
        is_visible = (state == 2)  # 2 es Qt.Checked
        
        
        # Mostrar/ocultar botones avanzados
        for button in self.advanced_buttons:
            button.setVisible(is_visible)
        
        
        # Mostrar/ocultar el widget de filtros temporales
        self.time_filters_widget.setVisible(is_visible)
        
        
        # Ajustar la altura del contenedor según corresponda
        if is_visible:
            self.top_container.setMaximumHeight(90)
        else:
            self.top_container.setMaximumHeight(50)
        
        # Forzar actualización
        self.repaint()
        QApplication.processEvents()

    def buscar_musica_en_reproduccion(self):
        """Busca la música en reproducción y rota la búsqueda"""
        artista = subprocess.run(['playerctl', 'metadata', '--format', '{{artist}}'], capture_output=True, text=True).stdout.strip()
        album = subprocess.run(['playerctl', 'metadata', '--format', '{{album}}'], capture_output=True, text=True).stdout.strip()
        cancion = subprocess.run(['playerctl', 'metadata', '--format', '{{title}}'], capture_output=True, text=True).stdout.strip()

        opciones = [cancion, album, artista]  # Lista cíclica
        self.boton_pulsado = (self.boton_pulsado + 1) % len(opciones)  # Rotar entre 0, 1, 2

        if opciones[self.boton_pulsado]:  # Evitar búsquedas vacías
            self.set_search_text(opciones[self.boton_pulsado])

        

    def add_to_playlist(self):
        """Añade el elemento seleccionado a la playlist"""
        current_item = self.results_list.currentItem()
        if current_item:
            # Obtener datos del elemento seleccionado
            item_data = current_item.data(Qt.ItemDataRole.UserRole)
            
            # Verificar si es un elemento de encabezado (artista/álbum) o una pista individual
            if hasattr(item_data, 'type') and item_data.type in ['artist', 'album']:
                print(f"556:item data type es: {item_data.type}")
                # Si es un encabezado, obtener todas las pistas asociadas
                tracks = self.get_tracks_for_header(item_data)
                print(f"559:tracks: {tracks}")
                for track in tracks:
                    self.add_track_to_playlist(track)
            else:
                # Si es una pista individual
                self.add_track_to_playlist(item_data)
            
            # Cambiar al tab de playlist automáticamente
            self.right_tabs.setCurrentIndex(1)

    def add_track_to_playlist(self, track_data):
        """Añade una pista individual a la playlist"""
        # Verificar si tenemos datos válidos
        if not track_data:
            print("No hay datos de pista para añadir")
            return
            
        # Para depuración
        #print(f"track_data: {track_data}, tipo: {type(track_data)}")
        
        # Extraer información de la pista según el tipo de datos
        if isinstance(track_data, dict):
            # Si los datos son un diccionario
            artist = track_data.get('artist', 'Desconocido')
            album = track_data.get('album', 'Desconocido')
            title = track_data.get('title', 'Desconocido')
            label = track_data.get('label', 'Desconocido')
            date = track_data.get('date', 'Desconocido')
        elif isinstance(track_data, tuple):
            # Si los datos son una tupla, extraer los valores según la estructura observada
            try:
                # Basado en el ejemplo que proporcionaste:
                # track_data: (1743, '/mnt/NFS/moode/moode/A/Arca/(2017) Arca (XL Recordings) (XLCD834)/Disc 1/04 - Urchin.flac', 'Urchin', 'Arca', 'Arca', 'Arca', '2017-04-07', 'Ambient', 'XL Recordings', ...)
                
                # Índices (ajustar según sea necesario):
                # 0: id, 1: path, 2: title, 3: artist, 4: album_artist, 5: album, 6: date, 7: genre, 8: label, ...
                
                # ID está en la posición 0
                title = track_data[2] if len(track_data) > 2 else 'Desconocido'
                artist = track_data[3] if len(track_data) > 3 else 'Desconocido'
                album = track_data[5] if len(track_data) > 5 else 'Desconocido'
                label = track_data[8] if len(track_data) > 8 else 'Desconocido'
                date = track_data[6] if len(track_data) > 6 else 'Desconocido'
            except IndexError:
                # Si hay problemas con los índices, usar valores por defecto
                print(f"Error al procesar la tupla: {track_data}")
                title = "Desconocido"
                artist = "Desconocido"
                album = "Desconocido"
                label = "Desconocido"
                date = "Desconocido"
        else:
            # Si los datos están en un objeto personalizado
            try:
                artist = getattr(track_data, 'artist', 'Desconocido')
                album = getattr(track_data, 'album', 'Desconocido')
                title = getattr(track_data, 'title', 'Desconocido')
                label = getattr(track_data, 'label', 'Desconocido')
                date = getattr(track_data, 'date', 'Desconocido')
            except AttributeError:
                # Si no podemos acceder a los atributos, usar texto del ítem actual
                current_item = self.results_list.currentItem()
                title = current_item.text() if current_item else "Elemento seleccionado"
                artist = "Artista (No disponible)"
                album = "Álbum (No disponible)"
                label = "Sello (No disponible)"
                date = "Fecha (No disponible)"
        
        # Para depuración
        print(f"Añadiendo pista: {artist} - {album} - {title} - {label} - {date}")
        
        # Añadir a la tabla de playlist
        row_position = self.playlist_table.rowCount()
        self.playlist_table.insertRow(row_position)
        self.playlist_table.setItem(row_position, 0, QTableWidgetItem(str(artist)))
        self.playlist_table.setItem(row_position, 1, QTableWidgetItem(str(album)))
        self.playlist_table.setItem(row_position, 2, QTableWidgetItem(str(title)))
        self.playlist_table.setItem(row_position, 3, QTableWidgetItem(str(label)))
        self.playlist_table.setItem(row_position, 4, QTableWidgetItem(str(date)))
        
        # Almacenar el elemento para referencia futura
        self.playlist_items.append({
            'artist': artist,
            'album': album,
            'title': title,
            'label': label,
            'date': date,
            'original_data': track_data  # Guarda los datos originales si los necesitas después
        })

    def get_tracks_for_header(self, header_data):
        """Obtiene todas las pistas asociadas a un encabezado (artista/álbum)"""
        tracks = []
        
        # Depuración
        print(f"Obteniendo pistas para encabezado: {header_data}")
        
        try:
            if hasattr(header_data, 'type'):
                header_type = header_data.type
                if header_type == 'artist':
                    # Lógica para obtener pistas de artista
                    artist_name = getattr(header_data, 'name', 'Desconocido')
                    # Aquí debería ir tu lógica para buscar pistas por artista
                    print(f"Buscando pistas para artista: {artist_name}")
                    
                    # Ejemplo: llamar a una función de la base de datos
                    # tracks = self.db.get_tracks_by_artist(artist_name)
                    
                elif header_type == 'album':
                    # Lógica para obtener pistas de álbum
                    album_name = getattr(header_data, 'name', 'Desconocido')
                    # Aquí debería ir tu lógica para buscar pistas por álbum
                    print(f"Buscando pistas para álbum: {album_name}")
                    
                    # Ejemplo: llamar a una función de la base de datos
                    # tracks = self.db.get_tracks_by_album(album_name)
        except Exception as e:
            print(f"Error al obtener pistas para encabezado: {e}")
        
        # Si no se encontraron pistas, imprimir mensaje de depuración
        if not tracks:
            print(f"No se encontraron pistas para el encabezado")
        else:
            print(f"Se encontraron {len(tracks)} pistas")
        
        return tracks

    def clear_playlist(self):
        """Vacía la playlist"""
        self.playlist_table.setRowCount(0)
        self.playlist_items = []

    def get_song_data_from_current_item(self):
        """Extrae los datos de canción del ítem actualmente seleccionado"""
        current_item = self.results_list.currentItem()
        if not current_item:
            return None
            
        # Intenta obtener los datos completos del ítem
        track_data = current_item.data(Qt.ItemDataRole.UserRole)
        
        # Si no hay datos adjuntos al ítem o son incorrectos, intentar 
        # obtener información del texto visible y metadatos disponibles
        if not track_data or not hasattr(track_data, 'artist'):
            # Extraer información de las etiquetas de metadatos
            # Suponiendo que esta información está disponible en algún lugar
            artist = self._extract_artist_from_ui()
            album = self._extract_album_from_ui()
            title = current_item.text()
            label = self._extract_label_from_ui()
            date = self._extract_date_from_ui()
            
            # Crear un objeto o diccionario con los datos extraídos
            track_data = {
                'artist': artist,
                'album': album,
                'title': title,
                'label': label,
                'date': date
            }
            
        return track_data
        
    def _extract_artist_from_ui(self):
        """Extrae información del artista desde la UI actual"""
        # Este es un método auxiliar para extraer el artista de la UI
        # Por ejemplo, podrías buscar en el texto de metadata_label o lastfm_label
        
        # Ejemplo muy básico:
        artist = "Desconocido"
        
        metadata_text = self.metadata_label.text()
        if "Artista:" in metadata_text:
            # Intenta extraer el artista usando expresiones regulares o parsing de texto
            import re
            match = re.search(r'Artista:\s*([^<]+)', metadata_text)
            if match:
                artist = match.group(1).strip()
                
        return artist
        
    def _extract_album_from_ui(self):
        """Extrae información del álbum desde la UI actual"""
        # Similar al método anterior, pero para el álbum
        album = "Desconocido"
        
        metadata_text = self.metadata_label.text()
        if "Álbum:" in metadata_text:
            import re
            match = re.search(r'Álbum:\s*([^<]+)', metadata_text)
            if match:
                album = match.group(1).strip()
                
        return album
        
    def _extract_label_from_ui(self):
        """Extrae información del sello desde la UI actual"""
        # Similar a los métodos anteriores, pero para el sello
        label = "Desconocido"
        
        metadata_text = self.metadata_label.text()
        if "Sello:" in metadata_text:
            import re
            match = re.search(r'Sello:\s*([^<]+)', metadata_text)
            if match:
                label = match.group(1).strip()
                
        return label
        
    def _extract_date_from_ui(self):
        """Extrae información de la fecha desde la UI actual"""
        # Similar a los métodos anteriores, pero para la fecha
        date = "Desconocido"
        
        metadata_text = self.metadata_label.text()
        if "Fecha:" in metadata_text:
            import re
            match = re.search(r'Fecha:\s*([^<]+)', metadata_text)
            if match:
                date = match.group(1).strip()
                
        return date
    def playlist_function1(self):
        """Función personalizada 1 para la playlist"""
        # Implementa tu función aquí
        pass

    def playlist_function2(self):
        """Función personalizada 2 para la playlist"""
        # Implementa tu función aquí
        pass

    def playlist_function3(self):
        """Función personalizada 3 para la playlist"""
        # Implementa tu función aquí
        pass

    def playlist_function4(self):
        """Función personalizada 4 para la playlist"""
        # Implementa tu función aquí
        pass





    def set_search_text(self, query):
        """
        Establece el texto en el cuadro de búsqueda y ejecuta la búsqueda.
        
        Args:
            query (str): El texto de búsqueda a establecer
        """
        self.search_box.setText(query)
        self.search()  # Ejecuta la búsqueda con el texto establecido



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
                pixmap = pixmap.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio)
                self.cover_label.setPixmap(pixmap)
            else:
                self.cover_label.setText("No imagen")
                
            # Nuevo: Mostrar la imagen del artista
            artist_image_path = self.find_artist_image(artist)
            if artist_image_path:
                artist_pixmap = QPixmap(artist_image_path)
                artist_pixmap = artist_pixmap.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio)
                self.artist_image_label.setPixmap(artist_pixmap)
            else:
                self.artist_image_label.setText("No imagen de artista")
        
        # Mostrar la información en el panel de detalles
        if first_track_data:
            # Crear el contenido para el panel de información (LastFM + Wikipedia)
            info_text = ""
            
            # Mostrar info de LastFM si está disponible
            artist_bio = first_track_data[15] if len(first_track_data) > 15 and first_track_data[15] else "No hay información del artista disponible"
            info_text += f"<h3>Información del Artista (LastFM):</h3><div style='white-space: pre-wrap;'>{artist_bio}</div><br><br>"
            
            # Mostrar info de Wikipedia del artista (índice 27)
            if len(first_track_data) > 27 and first_track_data[27]:
                info_text += f"<h3>Wikipedia - Artista:</h3><div style='white-space: pre-wrap;'>{first_track_data[27]}</div><br><br>"
            
            # Mostrar info de Wikipedia del álbum (índice 29)
            if len(first_track_data) > 29 and first_track_data[29]:
                info_text += f"<h3>Wikipedia - Álbum:</h3><div style='white-space: pre-wrap;'>{first_track_data[29]}</div><br><br>"
                
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
                    pixmap = pixmap.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio)
                    self.cover_label.setPixmap(pixmap)
                else:
                    self.cover_label.setText("No imagen")
                    
                # Mostrar imagen del artista usando el nombre extraído
                if artist:
                    artist_image_path = self.find_artist_image(artist)
                    if artist_image_path:
                        artist_pixmap = QPixmap(artist_image_path)
                        artist_pixmap = artist_pixmap.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio)
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
            info_text += f"<h3>Información del Artista (LastFM):</h3><div style='white-space: pre-wrap;'>{artist_bio}</div><br><br>"

            # Mostrar info de Wikipedia del artista (nuevos campos)
            if len(data) > 27:  # Verificar que los nuevos campos existen
                artist_wiki_content = data[27] if data[27] else "No hay información de Wikipedia disponible para este artista"
                info_text += f"<h3>Wikipedia - Artista:</h3><div style='white-space: pre-wrap;'>{artist_wiki_content}</div><br><br>"

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
            # manejar la excepción
            print(f"Error: {e}")

    def search(self):
        """
        Realiza una búsqueda en la base de datos según la consulta escrita en la caja de texto.
        
        Primero se intenta buscar en la tabla FTS (si se han proporcionado términos de texto libre).
        Si no se encuentran resultados, se vuelve a realizar la búsqueda en la tabla de canciones
        pero esta vez con condiciones específicas para cada campo.
        
        Se utiliza la clase SearchParser para construir las condiciones SQL y parámetros necesarios
        para la consulta.
        
        Se ordenan los resultados por artista, álbum y número de pista.
        
        Se limita el número de resultados a 1000 para evitar sobrecargar la interfaz.
        """
        query = self.search_box.text()
        parsed = self.search_parser.parse_query(query)
        
        # Conectar a la base de datos
        conn = sqlite3.connect(self.db_path)
        
        # Habilitar escritura a memoria para mejorar rendimiento
        conn.execute("PRAGMA temp_store = MEMORY")
        
        c = conn.cursor()
        
        # Determinar si hay términos de búsqueda de texto libre
        has_fts_terms = any(term['type'] == 'text' for term in parsed) if isinstance(parsed, list) else False
        
        # Preparar SQL base
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
        """
        
        # Si tenemos términos de búsqueda de texto, usar las tablas FTS
        if has_fts_terms:
            # Extraer términos de texto libre
            text_terms = [term['value'] for term in parsed if term['type'] == 'text']
            fts_query = ' '.join(text_terms)
            
            # Modificar SQL para incluir búsqueda FTS usando JOIN
            sql += """
                FROM songs s
                JOIN song_fts ON song_fts.id = s.id AND song_fts MATCH ?
                LEFT JOIN artists art ON s.artist = art.name
                LEFT JOIN albums alb ON s.album = alb.name 
                LEFT JOIN artists album_artist ON alb.artist_id = album_artist.id AND s.artist = album_artist.name
                LEFT JOIN lyrics lyr ON s.id = lyr.track_id
            """
            params = [fts_query]
            
            # Separar términos que no son de texto para condiciones adicionales
            non_text_terms = [term for term in parsed if term['type'] != 'text']
            
            # Añadir condiciones para términos que no son de texto
            if non_text_terms:
                # Modificar parsed para solo incluir términos que no son de texto
                conditions, additional_params = self.search_parser.build_sql_conditions(non_text_terms)
                if conditions:
                    sql += " WHERE " + " AND ".join(conditions)
                    params.extend(additional_params)
        else:
            # Usar la consulta tradicional para términos específicos
            sql += """
                FROM songs s
                LEFT JOIN artists art ON s.artist = art.name
                LEFT JOIN albums alb ON s.album = alb.name 
                LEFT JOIN artists album_artist ON alb.artist_id = album_artist.id AND s.artist = album_artist.name
                LEFT JOIN lyrics lyr ON s.id = lyr.track_id
            """
            
            # Usar build_sql_conditions desde SearchParser
            conditions, params = self.search_parser.build_sql_conditions(parsed)
            
            # Añadir cláusula WHERE si hay condiciones
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
        
        # Búsqueda en letras si está habilitada
        if hasattr(self, 'search_lyrics') and self.search_lyrics and has_fts_terms:
            # Si ya tenemos condiciones WHERE
            if 'WHERE' in sql:
                sql = sql.replace('JOIN song_fts ON song_fts.id = s.id AND song_fts MATCH ?',
                                'JOIN song_fts ON song_fts.id = s.id AND (song_fts MATCH ? OR EXISTS (SELECT 1 FROM lyrics_fts WHERE lyrics_fts.rowid = lyr.id AND lyrics_fts MATCH ?))')
                # Añadir el parámetro de búsqueda de letras
                params.insert(1, fts_query)  # Insertamos el mismo parámetro de búsqueda de nuevo
            else:
                sql += " WHERE EXISTS (SELECT 1 FROM lyrics_fts WHERE lyrics_fts.rowid = lyr.id AND lyrics_fts MATCH ?)"
                params.append(fts_query)
        
        # Ordenamiento
        sql += " ORDER BY s.artist, s.album, CAST(s.track_number AS INTEGER)"
        
        # Añadir un límite razonable para evitar cargar demasiados resultados
        sql += " LIMIT 1000"
        
        try:
            # Iniciar temporizador
            start_time = time.time()
            
            print(f"Ejecutando SQL: {sql}")
            print(f"Con parámetros: {params}")
            
            c.execute(sql, params)
            results = c.fetchall()
            
            # Terminar temporizador
            elapsed_time = time.time() - start_time
            print(f"Consulta completada en {elapsed_time:.3f} segundos. {len(results)} resultados encontrados.")
            
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

    def handle_spotify_button(self):
        """Manejador para el botón de Spotify que decide qué argumento pasar a enviar_spoti"""
        if not self.results_list.currentItem():
            return
            
        data = self.results_list.currentItem().data(Qt.ItemDataRole.UserRole)
        if not data:
            return
            
        # Buscar el enlace de Spotify - Índice 16 en los enlaces originales mostrados en show_details
        spotify_url = None
        
        # Primero verificamos si tenemos el ID de la canción para buscar en song_links
        if len(data) > 0 and data[0]:
            song_id = data[0]
            spotify_url = self.get_spotify_url_from_db(song_id)
        
        if spotify_url:
            # Si tenemos una URL de Spotify, la pasamos como argumento
            self.enviar_spoti(spotify_url)
        else:
            # Si no hay URL, creamos un string con "artista - título"
            artist = data[3] if len(data) > 3 and data[3] else ""
            title = data[2] if len(data) > 2 and data[2] else ""
            
            if artist and title:
                query = f"{artist} - {title}"
                self.enviar_spoti(query)
            else:
                # Mostrar mensaje si no hay suficiente información
                print("No hay suficiente información para buscar en Spotify")


    def enviar_spoti(self, arg):
        """Envía a Spotify basado en el argumento proporcionado
        
        Args:
            arg: Puede ser una URL de Spotify o una cadena con 'artista - título'
        """
        try:
            # Verificar si el argumento es una URL de Spotify
            if arg.startswith("https://open.spotify.com/") or arg.startswith("spotify:"):
                # Aquí la lógica para manejar URLs de Spotify directamente
                print(f"Enviando URL de Spotify al creador de listas: {arg}")
                self.switch_tab("Spotify Playlists", "add_track_by_url", arg)
            else:
                self.switch_tab("Spotify Playlists", "search_track_by_query", arg)
                print(f"Buscando en Spotify: {arg}")
                
        except Exception as e:
            print(f"Error al enviar a Spotify: {e}")


    def get_spotify_url_from_db(self, song_id):
        """Obtiene la URL de Spotify desde la base de datos para una canción específica"""
        try:
            # Conectar a la base de datos
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Consultar la URL de Spotify para el song_id proporcionado
            cursor.execute("SELECT spotify_url FROM song_links WHERE song_id = ?", (song_id,))
            result = cursor.fetchone()
            
            conn.close()
            
            # Devolver la URL si existe
            if result and result[0]:
                return result[0]
            return None
        except Exception as e:
            print(f"Error al obtener la URL de Spotify: {e}")
            return None


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

        if getattr(current, 'is_header', True):
            # Si es un header, abrir la carpeta del primer archivo del álbum
            self.open_album_folder()
            
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