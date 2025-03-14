import sys
import json
import traceback
import sqlite3
import requests
import time
from urllib.parse import quote_plus
from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                            QTableView, QHeaderView, QLabel, QSplitter, QFrame,
                            QScrollArea, QDialog, QGridLayout, QTextEdit)
from PyQt6.QtCore import Qt, QAbstractTableModel, pyqtSignal, QSortFilterProxyModel, QTimer, QUrl, QEvent
from PyQt6.QtGui import QFont, QColor, QDesktopServices, QIcon
import logging

from base_module import BaseModule, THEMES, PROJECT_ROOT

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LastFMModule(BaseModule):
    """
    Módulo para visualizar datos de LastFM y la canción actual desde una base de datos.
    Muestra información de la canción en reproducción y un historial de scrobbles.
    """
    
    def __init__(self, lastfm_api_key, username, database_path, listenbrainz_user, track_limit=50):
        # Primero asignamos las propiedades
        self.lastfm_api_key = lastfm_api_key
        self.listenbrainz_user = listenbrainz_user
        self.username = username
        self.database_path = database_path
        self.track_limit = track_limit
        self.scrobbles_data = []
        self.current_song = {}  # Inicializar como diccionario vacío
        
        # Luego llamamos al constructor base
        super().__init__()
        
        # Inicializamos la UI
        self.init_ui()
        
        # Cargamos los datos iniciales
        self.load_data()
        
        # Guardamos scrobbles al iniciar
        self.save_scrobbles_to_json()
        
        # Temporizador para actualización periódica
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.load_data)
        self.update_timer.start(60000)  # 60 segundos
    
    # CONFIGURACIÓN DE LA INTERFAZ
    def init_ui(self):
        """Configuración de la interfaz de usuario con dos paneles."""
        # Asegurarnos de que no haya elementos previos en el layout
        if hasattr(self, 'layout') and self.layout() is not None:
            # Limpiar cualquier widget existente
            while self.layout().count():
                item = self.layout().takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        else:
            # Si no hay layout, crear uno
            main_layout = QVBoxLayout()
            self.setLayout(main_layout)
        
        # Crear un splitter para dividir la pantalla
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Panel izquierdo (info de canción actual)
        self.left_panel = QFrame()
        self.left_panel.setFrameShape(QFrame.Shape.StyledPanel)
        left_layout = QVBoxLayout(self.left_panel)
        
        # Título
        self.current_title = QLabel("Última canción")
        self.current_title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        left_layout.addWidget(self.current_title)
        
        # Info de la canción
        self.song_info_layout = QVBoxLayout()
        self.song_title = QLabel("Título: -")
        self.song_artist = QLabel("Artista: -")
        self.song_album = QLabel("Álbum: -")
        self.song_duration = QLabel("Duración: -")
        self.song_playcount = QLabel("Reproducciones: -")
        
        self.song_info_layout.addWidget(self.song_title)
        self.song_info_layout.addWidget(self.song_artist)
        self.song_info_layout.addWidget(self.song_album)
        if 'genre' in self.current_song:
            tech_layout.addWidget(QLabel(f"Género: {self.current_song.get('genre', '-')}"))
        self.song_info_layout.addWidget(self.song_duration)
        self.song_info_layout.addWidget(self.song_playcount)
        
        # Crear un separador horizontal
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        self.song_info_layout.addWidget(separator)
        
        # Sección de botones para información adicional
        self.info_buttons_layout = QVBoxLayout()
        
        # Título para la sección
        info_title = QLabel("Información Adicional")
        info_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.info_buttons_layout.addWidget(info_title)
        
        # Layout para organizar botones en fila
        buttons_row = QHBoxLayout()
        
        # Botón para ver letras
        self.lyrics_button = QPushButton("Ver Letras")
        self.lyrics_button.setEnabled(False)  # Deshabilitar hasta que haya una canción con letras
        self.lyrics_button.clicked.connect(lambda: self.show_lyrics(self.current_song.get('song_id')))
        buttons_row.addWidget(self.lyrics_button)
        
        # Botón para info de artista en Wikipedia
        self.artist_wiki_button = QPushButton("Info del Artista")
        self.artist_wiki_button.setEnabled(False)  # Deshabilitar hasta que haya datos disponibles
        self.artist_wiki_button.clicked.connect(lambda: self.display_artist_info(self.current_song.get('artist_details', {})))
        buttons_row.addWidget(self.artist_wiki_button)
        
        # Botón para info de álbum en Wikipedia
        self.album_wiki_button = QPushButton("Info del Álbum")
        self.album_wiki_button.setEnabled(False)  # Deshabilitar hasta que haya datos disponibles
        self.album_wiki_button.clicked.connect(lambda: self.display_album_info(self.current_song.get('album_details', {})))
        buttons_row.addWidget(self.album_wiki_button)
        
        # Añadir el layout de botones al layout de info
        self.info_buttons_layout.addLayout(buttons_row)
        self.song_info_layout.addLayout(self.info_buttons_layout)
        
        left_layout.addLayout(self.song_info_layout)
        left_layout.addStretch()
        
        # Panel derecho (tabla de scrobbles)
        self.right_panel = QFrame()
        self.right_panel.setFrameShape(QFrame.Shape.StyledPanel)
        right_layout = QVBoxLayout(self.right_panel)
        
        # Título
        self.history_title = QLabel(f"Historial de Scrobbles ({self.username})")
        self.history_title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        right_layout.addWidget(self.history_title)
        
        # Tabla de scrobbles
        self.scrobbles_table = QTableView()
        self.scrobbles_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.scrobbles_table.horizontalHeader().setSectionsMovable(True)
        self.scrobbles_table.verticalHeader().setVisible(False)
        
        # Inicializar modelo de tabla
        self.init_table_model()
        
        right_layout.addWidget(self.scrobbles_table)
        
        # Botón de actualización
        self.update_button = QPushButton("Actualizar Datos")
        self.update_button.clicked.connect(self.load_data)
        right_layout.addWidget(self.update_button)
        
        # Añadir paneles al splitter
        self.splitter.addWidget(self.left_panel)
        self.splitter.addWidget(self.right_panel)
        self.splitter.setSizes([1, 2])  # Proporción 1:2
        
        # Añadir el splitter al layout principal
        self.layout().addWidget(self.splitter)
        

         # ACTUALIZACIÓN DE LA INTERFAZ
    def update_ui(self):
        """Actualiza los elementos de la interfaz con los datos cargados, incluyendo información extendida
        de artista, álbum y enlaces a servicios."""
        # Limpiar el panel izquierdo antes de reconstruirlo
        if hasattr(self, 'song_info_scroll_area'):
            self.song_info_scroll_area.deleteLater()
        
        # Crear un área de desplazamiento para el panel izquierdo
        self.song_info_scroll_area = QScrollArea()
        self.song_info_scroll_area.setWidgetResizable(True)
        self.song_info_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.song_info_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.song_info_scroll_area.setFrameShape(QFrame.Shape.NoFrame)  # Elimina el borde
        
        # Contenedor para toda la información
        info_container = QWidget()
        info_layout = QVBoxLayout(info_container)
        info_layout.setContentsMargins(0, 0, 0, 0)
        
        # Sección básica de información de canción
        basic_info_widget = QWidget()
        basic_info_layout = QVBoxLayout(basic_info_widget)
        
        # Título de la sección
        self.current_title = QLabel("Canción Actual")
        self.current_title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        basic_info_layout.addWidget(self.current_title)
        
        # Información básica
        self.song_title = QLabel(f"Título: {self.current_song['title']}")
        self.song_artist = QLabel(f"Artista: {self.current_song['artist']}")
        self.song_album = QLabel(f"Álbum: {self.current_song['album']}")
        self.song_duration = QLabel(f"Duración: {self.current_song['duration']}")
        self.song_playcount = QLabel(f"Reproducciones: {self.current_song['play_count']}")
        
        basic_info_layout.addWidget(self.song_title)
        basic_info_layout.addWidget(self.song_artist)
        basic_info_layout.addWidget(self.song_album)
        basic_info_layout.addWidget(self.song_duration)
        basic_info_layout.addWidget(self.song_playcount)
        
        # Advertencia si no está en la base de datos
        if not self.current_song.get('in_database', False):
            warning_style = "background-color: rgba(255, 255, 0, 0.3); padding: 5px; border-radius: 3px;"
            self.song_title.setStyleSheet(warning_style)
            self.song_artist.setStyleSheet(warning_style)
            self.song_album.setStyleSheet(warning_style)
            
            self.db_warning_label = QLabel("⚠️ Datos no encontrados en la base de datos")
            self.db_warning_label.setStyleSheet("color: #B7950B; font-weight: bold;")
            basic_info_layout.insertWidget(1, self.db_warning_label)
        
        info_layout.addWidget(basic_info_widget)
        
        # Sección de botones para paneles de información
        if self.current_song.get('in_database', False):
            # Separador
            separator = QFrame()
            separator.setFrameShape(QFrame.Shape.HLine)
            separator.setFrameShadow(QFrame.Shadow.Sunken)
            info_layout.addWidget(separator)
            
            # Título para la sección de paneles
            panels_title = QLabel("Paneles de Información")
            panels_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            info_layout.addWidget(panels_title)
            
            # Layout para los botones de paneles principales
            panels_layout = QHBoxLayout()
            
            # Botón para ver panel del artista
            has_artist_info = 'artist_details' in self.current_song
            self.artist_panel_button = QPushButton(self.current_song['artist'])
            self.artist_panel_button.setEnabled(has_artist_info)
            if has_artist_info:
                self.artist_panel_button.clicked.connect(
                    lambda: self.display_artist_info(self.current_song.get('artist_details', {}))
                )
            panels_layout.addWidget(self.artist_panel_button)
            
            # Botón para ver panel del álbum
            has_album_info = 'album_details' in self.current_song
            self.album_panel_button = QPushButton(self.current_song['album'])
            self.album_panel_button.setEnabled(has_album_info)
            if has_album_info:
                self.album_panel_button.clicked.connect(
                    lambda: self.display_album_info(self.current_song.get('album_details', {}))
                )
            panels_layout.addWidget(self.album_panel_button)
            
            # Botón para ver letras
            has_lyrics = self.current_song.get('has_lyrics', False)
            self.lyrics_button = QPushButton("Ver Letras")
            self.lyrics_button.setEnabled(has_lyrics)
            if has_lyrics:
                self.lyrics_button.clicked.connect(
                    lambda: self.show_lyrics(self.current_song.get('song_id'))
                )
            panels_layout.addWidget(self.lyrics_button)
            
            info_layout.addLayout(panels_layout)
        
        # Sección de información técnica si está disponible
        if self.current_song.get('in_database', False):
            # Separador
            separator2 = QFrame()
            separator2.setFrameShape(QFrame.Shape.HLine)
            separator2.setFrameShadow(QFrame.Shadow.Sunken)
            info_layout.addWidget(separator2)
            
            # # Sección técnica
            # tech_widget = QWidget()
            # tech_layout = QVBoxLayout(tech_widget)
            
            # tech_title = QLabel("Información Técnica")
            # tech_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            # tech_layout.addWidget(tech_title)
            
            # if 'genre' in self.current_song:
            #     tech_layout.addWidget(QLabel(f"Género: {self.current_song.get('genre', '-')}"))
            # if 'bitrate' in self.current_song:
            #     tech_layout.addWidget(QLabel(f"Bitrate: {self.current_song.get('bitrate', '-')} kbps"))
            # if 'sample_rate' in self.current_song:
            #     tech_layout.addWidget(QLabel(f"Sample Rate: {self.current_song.get('sample_rate', '-')} Hz"))
            # if 'bit_depth' in self.current_song:
            #     tech_layout.addWidget(QLabel(f"Bit Depth: {self.current_song.get('bit_depth', '-')} bits"))
            
            # info_layout.addWidget(tech_widget)
            
            ##Enlaces para la canción
            # separator3 = QFrame()
            # separator3.setFrameShape(QFrame.Shape.HLine)
            # separator3.setFrameShadow(QFrame.Shadow.Sunken)
            # info_layout.addWidget(separator3)
            
            # Sección de enlaces
            links_widget = QWidget()
            links_layout = QVBoxLayout(links_widget)
            
            # links_title = QLabel("Enlaces")
            # links_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            # links_layout.addWidget(links_title)
            
            # Botones para enlaces de la canción
            links_song_layout = QHBoxLayout()
            
            if 'spotify_url' in self.current_song and self.current_song['spotify_url'] != '-':
                spotify_button = QPushButton("Spotify")
                spotify_button.clicked.connect(lambda: self.open_url(self.current_song.get('spotify_url')))
                links_song_layout.addWidget(spotify_button)
                
            if 'lastfm_url' in self.current_song and self.current_song['lastfm_url'] != '-':
                lastfm_button = QPushButton("Last.fm")
                lastfm_button.clicked.connect(lambda: self.open_url(self.current_song.get('lastfm_url')))
                links_song_layout.addWidget(lastfm_button)
                
            if 'youtube_url' in self.current_song and self.current_song['youtube_url'] != '-':
                youtube_button = QPushButton("YouTube")
                youtube_button.clicked.connect(lambda: self.open_url(self.current_song.get('youtube_url')))
                links_song_layout.addWidget(youtube_button)
                
            if 'musicbrainz_url' in self.current_song and self.current_song['musicbrainz_url'] != '-':
                mb_button = QPushButton("MusicBrainz")
                mb_button.clicked.connect(lambda: self.open_url(self.current_song.get('musicbrainz_url')))
                links_song_layout.addWidget(mb_button)
            
            links_layout.addLayout(links_song_layout)
            
            info_layout.addWidget(links_widget)
        
        # Espacio flexible al final para que todo quede en la parte superior
        info_layout.addStretch()
        
        # Establecer el widget en el área de desplazamiento
        self.song_info_scroll_area.setWidget(info_container)
        
        # Reemplazar el contenido del panel izquierdo con el área de desplazamiento
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.song_info_scroll_area)
        
        # Eliminar el layout anterior y aplicar el nuevo
        QWidget().setLayout(self.left_panel.layout())  # Truco para eliminar el layout anterior
        self.left_panel.setLayout(left_layout)
        
        # Actualizar el título del historial
        self.history_title.setText(f"Historial de Scrobbles ({self.username}) - {len(self.scrobbles_data)} entradas")

    # Agregar este método para mostrar un panel con la información del artista
    def display_artist_info(self, artist_details):
        """Muestra toda la información disponible del artista en una ventana separada."""
        if not artist_details:
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Información de {artist_details.get('name', 'Artista')}")
        dialog.resize(600, 500)
        
        layout = QVBoxLayout(dialog)
        
        # Área de desplazamiento para el contenido
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        # Título
        artist_name = QLabel(artist_details.get('name', 'Artista'))
        artist_name.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        content_layout.addWidget(artist_name)
        
        # Detalles básicos
        details_layout = QGridLayout()
        row = 0
        
        if artist_details.get('formed_year', '-') != '-':
            details_layout.addWidget(QLabel("Formado en:"), row, 0)
            details_layout.addWidget(QLabel(artist_details['formed_year']), row, 1)
            row += 1
        
        if artist_details.get('origin', '-') != '-':
            details_layout.addWidget(QLabel("Origen:"), row, 0)
            details_layout.addWidget(QLabel(artist_details['origin']), row, 1)
            row += 1
        
        if artist_details.get('genres', '-') != '-':
            details_layout.addWidget(QLabel("Géneros:"), row, 0)
            details_layout.addWidget(QLabel(artist_details['genres']), row, 1)
            row += 1
        
        content_layout.addLayout(details_layout)
        
        # Biografía
        if artist_details.get('bio', '-') != '-':
            bio_title = QLabel("Biografía")
            bio_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            content_layout.addWidget(bio_title)
            
            bio_text = QTextEdit()
            bio_text.setReadOnly(True)
            bio_text.setMinimumHeight(150)
            bio_text.setText(artist_details['bio'])
            content_layout.addWidget(bio_text)
        
        # Contenido de Wikipedia
        if artist_details.get('wikipedia_content', '-') != '-':
            wiki_title = QLabel("Información de Wikipedia")
            wiki_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            content_layout.addWidget(wiki_title)
            
            wiki_text = QTextEdit()
            wiki_text.setReadOnly(True)
            wiki_text.setMinimumHeight(150)
            wiki_text.setText(artist_details['wikipedia_content'])
            content_layout.addWidget(wiki_text)
        
        # Enlaces
        links_exist = any(key in artist_details and artist_details[key] != '-' for key in 
                        ['spotify_url', 'youtube_url', 'musicbrainz_url', 'wikipedia_url', 
                        'rateyourmusic_url', 'discogs_url'])
        
        if links_exist:
            links_title = QLabel("Enlaces")
            links_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            content_layout.addWidget(links_title)
            
            links_layout = QHBoxLayout()
            
            if artist_details.get('spotify_url', '-') != '-':
                spotify_button = QPushButton("Spotify")
                spotify_button.clicked.connect(lambda: self.open_url(artist_details.get('spotify_url')))
                links_layout.addWidget(spotify_button)
            
            if artist_details.get('youtube_url', '-') != '-':
                youtube_button = QPushButton("YouTube")
                youtube_button.clicked.connect(lambda: self.open_url(artist_details.get('youtube_url')))
                links_layout.addWidget(youtube_button)
            
            if artist_details.get('wikipedia_url', '-') != '-':
                wiki_button = QPushButton("Wikipedia")
                wiki_button.clicked.connect(lambda: self.open_url(artist_details.get('wikipedia_url')))
                links_layout.addWidget(wiki_button)
            
            if artist_details.get('musicbrainz_url', '-') != '-':
                mb_button = QPushButton("MusicBrainz")
                mb_button.clicked.connect(lambda: self.open_url(artist_details.get('musicbrainz_url')))
                links_layout.addWidget(mb_button)
            
            if artist_details.get('rateyourmusic_url', '-') != '-':
                rym_button = QPushButton("RYM")
                rym_button.clicked.connect(lambda: self.open_url(artist_details.get('rateyourmusic_url')))
                links_layout.addWidget(rym_button)
            
            if artist_details.get('discogs_url', '-') != '-':
                discogs_button = QPushButton("Discogs")
                discogs_button.clicked.connect(lambda: self.open_url(artist_details.get('discogs_url')))
                links_layout.addWidget(discogs_button)
            
            content_layout.addLayout(links_layout)
        
        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)
        
        # Botón para cerrar
        close_button = QPushButton("Cerrar")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)
        
        dialog.exec()

    # Agregar este método para mostrar un panel con la información del álbum
    def display_album_info(self, album_details):
        """Muestra toda la información disponible del álbum en una ventana separada."""
        if not album_details:
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Información de {album_details.get('title', 'Álbum')}")
        dialog.resize(600, 500)
        
        layout = QVBoxLayout(dialog)
        
        # Área de desplazamiento para el contenido
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        # Título
        album_title = QLabel(album_details.get('title', 'Álbum'))
        album_title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        content_layout.addWidget(album_title)
        
        # Artista
        if album_details.get('artist', '-') != '-':
            artist_label = QLabel(f"Artista: {album_details.get('artist', '-')}")
            content_layout.addWidget(artist_label)
        
        # Detalles básicos
        details_layout = QGridLayout()
        row = 0
        
        if album_details.get('year', '-') != '-':
            details_layout.addWidget(QLabel("Año:"), row, 0)
            details_layout.addWidget(QLabel(album_details['year']), row, 1)
            row += 1
        
        if album_details.get('label', '-') != '-':
            details_layout.addWidget(QLabel("Sello:"), row, 0)
            details_layout.addWidget(QLabel(album_details['label']), row, 1)
            row += 1
        
        if album_details.get('genre', '-') != '-':
            details_layout.addWidget(QLabel("Género:"), row, 0)
            details_layout.addWidget(QLabel(album_details['genre']), row, 1)
            row += 1
        
        if album_details.get('total_tracks', '-') != '-':
            details_layout.addWidget(QLabel("Pistas:"), row, 0)
            details_layout.addWidget(QLabel(str(album_details['total_tracks'])), row, 1)
            row += 1
        
        content_layout.addLayout(details_layout)
        
        # Contenido de Wikipedia
        if album_details.get('wikipedia_content', '-') != '-':
            wiki_title = QLabel("Información de Wikipedia")
            wiki_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            content_layout.addWidget(wiki_title)
            
            wiki_text = QTextEdit()
            wiki_text.setReadOnly(True)
            wiki_text.setMinimumHeight(150)
            wiki_text.setText(album_details['wikipedia_content'])
            content_layout.addWidget(wiki_text)
        
        # Enlaces
        links_exist = any(key in album_details and album_details[key] != '-' for key in 
                        ['spotify_url', 'youtube_url', 'musicbrainz_url', 'wikipedia_url', 
                        'rateyourmusic_url', 'discogs_url'])
        
        if links_exist:
            links_title = QLabel("Enlaces")
            links_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            content_layout.addWidget(links_title)
            
            links_layout = QHBoxLayout()
            
            if album_details.get('spotify_url', '-') != '-':
                spotify_button = QPushButton("Spotify")
                spotify_button.clicked.connect(lambda: self.open_url(album_details.get('spotify_url')))
                links_layout.addWidget(spotify_button)
            
            if album_details.get('youtube_url', '-') != '-':
                youtube_button = QPushButton("YouTube")
                youtube_button.clicked.connect(lambda: self.open_url(album_details.get('youtube_url')))
                links_layout.addWidget(youtube_button)
            
            if album_details.get('wikipedia_url', '-') != '-':
                wiki_button = QPushButton("Wikipedia")
                wiki_button.clicked.connect(lambda: self.open_url(album_details.get('wikipedia_url')))
                links_layout.addWidget(wiki_button)
            
            if album_details.get('musicbrainz_url', '-') != '-':
                mb_button = QPushButton("MusicBrainz")
                mb_button.clicked.connect(lambda: self.open_url(album_details.get('musicbrainz_url')))
                links_layout.addWidget(mb_button)
            
            if album_details.get('rateyourmusic_url', '-') != '-':
                rym_button = QPushButton("RYM")
                rym_button.clicked.connect(lambda: self.open_url(album_details.get('rateyourmusic_url')))
                links_layout.addWidget(rym_button)
            
            if album_details.get('discogs_url', '-') != '-':
                discogs_button = QPushButton("Discogs")
                discogs_button.clicked.connect(lambda: self.open_url(album_details.get('discogs_url')))
                links_layout.addWidget(discogs_button)
            
            content_layout.addLayout(links_layout)
        
        # Lista de canciones si está disponible
        if 'tracks' in album_details and album_details['tracks']:
            tracks_title = QLabel("Lista de canciones")
            tracks_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            content_layout.addWidget(tracks_title)
            
            tracks_list = QListWidget()
            for track in album_details['tracks']:
                tracks_list.addItem(f"{track.get('position', '-')}. {track.get('title', '-')} ({track.get('duration', '-')})")
            
            tracks_list.setMaximumHeight(150)
            content_layout.addWidget(tracks_list)
        
        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)
        
        # Botón para cerrar
        close_button = QPushButton("Cerrar")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)
        
        dialog.exec()

    # Función auxiliar para abrir URLs (asegúrate de que esta función exista)
    def open_url(self, url):
        """Abre una URL en el navegador predeterminado del sistema."""
        if url and url != '-':
            QDesktopServices.openUrl(QUrl(url))



        
    def show_lyrics(self, song_id):
        """Muestra las letras de la canción en un diálogo."""
        if not song_id:
            return
            
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            query = """
            SELECT l.lyrics, s.title, s.artist 
            FROM lyrics l
            JOIN songs s ON l.track_id = s.id
            WHERE l.track_id = ?
            """
            
            cursor.execute(query, (song_id,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                from PyQt6.QtWidgets import QDialog, QTextEdit, QVBoxLayout, QLabel
                
                dialog = QDialog(self)
                dialog.setWindowTitle(f"Letras - {result[1]} ({result[2]})")
                dialog.resize(500, 600)
                
                layout = QVBoxLayout()
                
                # Título
                title_label = QLabel(f"{result[1]} - {result[2]}")
                title_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
                layout.addWidget(title_label)
                
                # Texto de las letras
                lyrics_edit = QTextEdit()
                lyrics_edit.setReadOnly(True)
                lyrics_edit.setPlainText(result[0])
                layout.addWidget(lyrics_edit)
                
                dialog.setLayout(layout)
                dialog.exec()
            else:
                print(f"No se encontraron letras para la canción con ID {song_id}")
                
        except Exception as e:
            print(f"Error al mostrar letras: {e}")
            traceback.print_exc()




    def load_data(self):
        """Carga datos desde LastFM y la base de datos."""
        try:
            # Cargar datos de LastFM
            self.fetch_lastfm_data()
            
            # Cargar datos de la canción actual desde la base de datos
            self.load_current_song()
            
            # Actualizar la interfaz
            self.update_ui()
            
            # Guardar datos de scrobbles a JSON
            self.save_scrobbles_to_json()
            
            # Actualizar la información de scrobbles solo para canciones nuevas
            new_tracks = [track for track in self.scrobbles_data if track.get('is_new', False)]
            
            if new_tracks:
                print(f"Encontrados {len(new_tracks)} nuevos scrobbles, actualizando información...")
                
                # Crear el hilo solo si hay nuevas canciones
                self.update_thread = ScrobblesUpdateThread(self)
                self.update_thread.finished.connect(self.on_scrobbles_updated)
                self.update_thread.start()
            
        except Exception as e:
            print(f"Error al cargar datos: {e}")
            traceback.print_exc()

    def on_scrobbles_updated(self):
        """Manejador para cuando se completa la actualización de scrobbles."""
        # Actualizar el modelo de la tabla solo si es necesario
        if hasattr(self, 'table_model'):
            self.table_model.update_data(self.scrobbles_data)
        
        # Contar cuántas canciones tienen información de scrobbles
        tracks_with_scrobbles = sum(1 for track in self.scrobbles_data if 'scrobbles_count' in track)
        
        print(f"Actualización de scrobbles completada. {tracks_with_scrobbles}/{len(self.scrobbles_data)} canciones con información de scrobbles.")
    
    def fetch_lastfm_data(self):
        """Obtiene datos recientes de LastFM a través de su API."""
        try:
            print(f"Intentando obtener datos de LastFM para {self.username}")
            url = "http://ws.audioscrobbler.com/2.0/"
            params = {
                'method': 'user.getrecenttracks',
                'user': self.username,
                'api_key': self.lastfm_api_key,
                'format': 'json',
                'limit': self.track_limit
            }
            
            print(f"Haciendo petición a LastFM con parámetros: {params}")
            response = requests.get(url, params=params, timeout=10)  # Añadido timeout
            print(f"Respuesta de LastFM: Código {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                # Verificar si hay mensajes de error en la respuesta
                if 'error' in data:
                    print(f"Error de LastFM: {data['error']} - {data.get('message', 'Sin mensaje')}")
                    self.scrobbles_data = []
                    return
                    
                # Verificar la estructura de recenttracks
                if 'recenttracks' not in data or 'track' not in data['recenttracks']:
                    print("Estructura de datos de LastFM inesperada")
                    print(f"Datos recibidos: {data}")
                    return
                    
                tracks = data['recenttracks']['track']
                if not isinstance(tracks, list):
                    tracks = [tracks]  # Si solo hay un track, convertirlo a lista
                    
                print(f"Tracks recibidos: {len(tracks)}")
                
                new_scrobbles_data = []
                for track in tracks:
                    # Comprobar si es una canción actual o un scrobble pasado
                    is_now_playing = '@attr' in track and track['@attr'].get('nowplaying') == 'true'
                    
                    if is_now_playing:
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        status = "Reproduciendo"
                    else:
                        # Verificar que existe 'date' y 'uts'
                        if 'date' not in track or 'uts' not in track['date']:
                            print(f"Track sin fecha: {track}")
                            continue
                            
                        # Convertir timestamp Unix a formato legible
                        timestamp = datetime.fromtimestamp(int(track['date']['uts']))
                        timestamp = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                        status = "Scrobbled"
                    
                    # Verificar que existen todos los campos necesarios
                    if 'name' not in track or 'artist' not in track or '#text' not in track['artist']:
                        print(f"Track con datos faltantes: {track}")
                        continue
                        
                    # Verificar si la canción está en la base de datos
                    in_database = self.check_track_in_database(track['name'], track['artist']['#text'])
                    
                    track_data = {
                        'timestamp': timestamp,
                        'title': track['name'],
                        'artist': track['artist']['#text'],
                        'album': track['album']['#text'] if 'album' in track and '#text' in track['album'] else "-",
                        'status': status,
                        'in_database': in_database
                    }
                    
                    new_scrobbles_data.append(track_data)
                
                # Actualizar datos y modelo solo si tenemos datos válidos
                if new_scrobbles_data:
                    self.scrobbles_data = new_scrobbles_data
                    
                    # Actualizar el modelo de tabla
                    if hasattr(self, 'table_model'):
                        self.table_model.update_data(self.scrobbles_data)
                        
                        # Forzar actualización visual
                        if hasattr(self, 'scrobbles_table'):
                            self.scrobbles_table.reset()
                            self.scrobbles_table.update()
                    
                    print(f"Datos actualizados en el modelo, {len(self.scrobbles_data)} scrobbles")
                else:
                    print("No se pudieron extraer datos de tracks válidos")
                
            else:
                print(f"Error al obtener datos de LastFM: Código {response.status_code}")
                print(f"Respuesta: {response.text}")
            
        except requests.exceptions.RequestException as e:
            print(f"Error de conexión a LastFM: {e}")
            traceback.print_exc()
        except Exception as e:
            print(f"Error en fetch_lastfm_data: {e}")
            traceback.print_exc()

    # Cuando se obtienen nuevos scrobbles, marca cada uno como 'nuevo'
        for scrobble in new_scrobbles:
            scrobble['is_new'] = True
        
        # Añadir los nuevos scrobbles a los existentes
        if not hasattr(self, 'scrobbles_data') or self.scrobbles_data is None:
            self.scrobbles_data = new_scrobbles
        else:
            # Añadir solo los scrobbles que no existen ya
            existing_ids = {(s.get('artist', ''), s.get('title', ''), s.get('timestamp', '')) 
                            for s in self.scrobbles_data}
            
            for scrobble in new_scrobbles:
                scrobble_id = (scrobble.get('artist', ''), scrobble.get('title', ''), scrobble.get('timestamp', ''))
                if scrobble_id not in existing_ids:
                    self.scrobbles_data.append(scrobble)
                    existing_ids.add(scrobble_id)
        
        # Actualizar el modelo
        if hasattr(self, 'table_model'):
            self.table_model.update_data(self.scrobbles_data)


    # GESTIÓN DE SCROBBLES
    def save_scrobbles_to_json(self):
        """Guarda los datos de scrobbles en un archivo JSON."""
        try:
            # Usar directorio home del usuario
            data_dir = PROJECT_ROOT / '.content' / 'cache' / 'lastfm_scrobbler'
            print(f"Intentando guardar datos de scrobbles en {data_dir}")
            
            # Crear directorio si no existe
            data_dir.mkdir(exist_ok=True)
            
            # Crear archivo JSON con los scrobbles
            scrobbles_file = data_dir / 'recent_tracks.json'
            print(f"Guardando scrobbles en {scrobbles_file}")
            
            with open(scrobbles_file, 'w') as f:
                json.dump(self.scrobbles_data, f, indent=4)
            
            print(f"Datos de scrobbles guardados correctamente en {scrobbles_file}")
            
        except Exception as e:
            print(f"Error al guardar los datos de scrobbles: {e}")
            traceback.print_exc()


    def load_current_song(self):
        """Carga información de la canción actual desde LastFM y busca información adicional 
        en la base de datos, incluyendo detalles del artista y álbum con contenido de Wikipedia."""
        try:
            # Primero, buscar la canción en reproducción actual en los datos de LastFM
            now_playing = None
            if hasattr(self, 'scrobbles_data') and self.scrobbles_data:
                now_playing = next((track for track in self.scrobbles_data 
                                if track.get('status') == 'Reproduciendo'), None)
                
                if not now_playing and self.scrobbles_data:
                    # Si no hay canción en reproducción, usar la más reciente
                    now_playing = self.scrobbles_data[0]
            
            if not now_playing:
                self.current_song = {
                    'title': 'No hay datos en reproducción',
                    'artist': '-',
                    'album': '-',
                    'duration': '-',
                    'play_count': '-',
                    'in_database': False
                }
                return
                
            # Ahora tenemos información básica de la canción
            title = now_playing['title']
            artist = now_playing['artist']
            album = now_playing.get('album', '-')
                
            # Inicializar el objeto current_song con los datos de LastFM
            self.current_song = {
                'title': title,
                'artist': artist,
                'album': album,
                'duration': '-',
                'play_count': '-',
                'in_database': False
            }
            
            # Verificar si el archivo de la base de datos existe
            if not Path(self.database_path).exists():
                print(f"Base de datos no encontrada: {self.database_path}")
                return
                    
            # Intentar obtener información adicional de la base de datos
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            # Consulta para obtener información detallada de la canción usando título y artista
            query = """
            SELECT s.id, s.title, s.artist, s.album, s.duration, 
                s.genre, s.album_artist, s.date, s.bitrate,
                s.sample_rate, s.bit_depth, s.mbid, s.has_lyrics,
                s.added_week, s.added_year, s.album_year, 
                s.album_art_path_denorm, s.label
            FROM songs s
            WHERE s.title LIKE ? AND s.artist LIKE ?
            LIMIT 1
            """
            
            cursor.execute(query, (f"%{title}%", f"%{artist}%"))
            result = cursor.fetchone()
            
            if result:
                # Actualizar con datos de la base de datos
                self.current_song.update({
                    'song_id': result[0],
                    'title': result[1],
                    'artist': result[2],
                    'album': result[3],
                    'duration': result[4],
                    'genre': result[5] or '-',
                    'album_artist': result[6] or '-',
                    'date': result[7] or '-',
                    'bitrate': result[8] or '-',
                    'sample_rate': result[9] or '-',
                    'bit_depth': result[10] or '-',
                    'mbid': result[11] or '-',
                    'has_lyrics': bool(result[12]),
                    'added_week': result[13] or '-',
                    'added_year': result[14] or '-',
                    'album_year': result[15] or '-',
                    'album_art_path': result[16] or '-',
                    'label': result[17] or '-',
                    'in_database': True
                })
                
                # Intentar obtener enlaces relacionados con la canción
                links_query = """
                SELECT spotify_url, lastfm_url, youtube_url, musicbrainz_url 
                FROM song_links 
                WHERE song_id = ?
                """
                cursor.execute(links_query, (self.current_song['song_id'],))
                links_result = cursor.fetchone()
                
                if links_result:
                    self.current_song.update({
                        'spotify_url': links_result[0] or '-',
                        'lastfm_url': links_result[1] or '-',
                        'youtube_url': links_result[2] or '-',
                        'musicbrainz_url': links_result[3] or '-'
                    })
                
                # NUEVO: Obtener información detallada del artista, incluyendo contenido de Wikipedia
                artist_query = """
                SELECT a.id, a.bio, a.tags, a.origin, a.formed_year, 
                    a.total_albums, a.spotify_url, a.youtube_url, 
                    a.musicbrainz_url, a.wikipedia_url, a.wikipedia_content, a.mbid,
                    a.formed_year, a.bio, a.origin, a.rateyourmusic_url, a.discogs_url,
                    a.similar_artists
                FROM artists a
                WHERE a.name LIKE ?
                LIMIT 1
                """
                cursor.execute(artist_query, (f"%{self.current_song['artist']}%",))
                artist_result = cursor.fetchone()
                
                if artist_result:
                    self.current_song['artist_details'] = {
                        'id': artist_result[0],
                        'bio': artist_result[1] or '-',
                        'tags': artist_result[2] or '-',
                        'origin': artist_result[3] or '-',
                        'formed_year': artist_result[4] or '-',
                        'total_albums': artist_result[5] or '-',
                        'spotify_url': artist_result[6] or '-',
                        'youtube_url': artist_result[7] or '-',
                        'musicbrainz_url': artist_result[8] or '-',
                        'wikipedia_url': artist_result[9] or '-',
                        'wikipedia_content': artist_result[10] or '-',  # Contenido de Wikipedia
                        'mbid': artist_result[11] or '-',
                        'formed_year': artist_result[12] or '-',
                        'bio': artist_result[13] or '-',
                        'origin': artist_result[14] or '-',
                        'rateyourmusic_url': artist_result[15] or '-',
                        'discogs_url': artist_result[16] or '-',
                        'similar_artists': artist_result[17] or '-'
                    }
                
                # NUEVO: Obtener información detallada del álbum, incluyendo contenido de Wikipedia
                album_query = """
                SELECT alb.id, alb.year, alb.label, alb.genre, 
                    alb.total_tracks, alb.album_art_path, 
                    alb.spotify_url, alb.youtube_url, alb.musicbrainz_url, 
                    alb.wikipedia_url, alb.wikipedia_content, alb.mbid, alb.folder_path,
                    alb.rateyourmusic_url, alb.discogs_url
                FROM albums alb
                WHERE alb.name LIKE ? AND alb.artist_id = (
                    SELECT a.id FROM artists a WHERE a.name LIKE ?
                )
                LIMIT 1
                """
                
                cursor.execute(album_query, (f"%{self.current_song['album']}%", f"%{self.current_song['artist']}%"))
                album_result = cursor.fetchone()
                
                if album_result:
                    self.current_song['album_details'] = {
                        'id': album_result[0],
                        'year': album_result[1] or '-',
                        'label': album_result[2] or '-',
                        'genre': album_result[3] or '-',
                        'total_tracks': album_result[4] or '-',
                        'album_art_path': album_result[5] or '-',
                        'spotify_url': album_result[6] or '-',
                        'youtube_url': album_result[7] or '-',
                        'musicbrainz_url': album_result[8] or '-',
                        'wikipedia_url': album_result[9] or '-',
                        'wikipedia_content': album_result[10] or '-',  # Contenido de Wikipedia
                        'mbid': album_result[11] or '-',
                        'folder_path': album_result[12] or '-',
                        'rateyourmusic_url': album_result[13] or '-',
                        'discogs_url': album_result[14] or '-'
                    }
                
                # Búsqueda alternativa del álbum si no se encuentra con el método anterior
                if not album_result and 'album' in self.current_song and self.current_song['album'] != '-':
                    alt_album_query = """
                    SELECT alb.id, alb.year, alb.label, alb.genre, 
                        alb.total_tracks, alb.album_art_path, 
                        alb.spotify_url, alb.youtube_url, alb.musicbrainz_url, 
                        alb.wikipedia_url, alb.wikipedia_content, alb.mbid, alb.folder_path,
                        alb.rateyourmusic_url, alb.discogs_url
                    FROM albums alb
                    WHERE alb.name LIKE ?
                    LIMIT 1
                    """
                    cursor.execute(alt_album_query, (f"%{self.current_song['album']}%",))
                    album_result = cursor.fetchone()
                    
                    if album_result:
                        self.current_song['album_details'] = {
                            'id': album_result[0],
                            'year': album_result[1] or '-',
                            'label': album_result[2] or '-',
                            'genre': album_result[3] or '-',
                            'total_tracks': album_result[4] or '-',
                            'album_art_path': album_result[5] or '-',
                            'spotify_url': album_result[6] or '-',
                            'youtube_url': album_result[7] or '-',
                            'musicbrainz_url': album_result[8] or '-',
                            'wikipedia_url': album_result[9] or '-',
                            'wikipedia_content': album_result[10] or '-',  # Contenido de Wikipedia
                            'mbid': album_result[11] or '-',
                            'folder_path': album_result[12] or '-',
                            'rateyourmusic_url': album_result[13] or '-',
                            'discogs_url': album_result[14] or '-'
                        }
            
            conn.close()
            
        except sqlite3.OperationalError as e:
            print(f"Error de SQLite al cargar la canción actual: {e}")
            if not hasattr(self, 'current_song') or not self.current_song:
                self.current_song = {
                    'title': 'Error en la base de datos',
                    'artist': str(e),
                    'album': '-',
                    'duration': '-',
                    'play_count': '-',
                    'in_database': False
                }
        except Exception as e:
            print(f"Error al cargar la canción actual: {e}")
            traceback.print_exc()
            if not hasattr(self, 'current_song') or not self.current_song:
                self.current_song = {
                    'title': 'Error',
                    'artist': str(e),
                    'album': '-',
                    'duration': '-',
                    'play_count': '-',
                    'in_database': False
                }
    
   


    def check_track_in_database(self, track_title, artist_name):
        """Verifica si una canción existe en la base de datos con búsqueda mejorada."""
        try:
            if not Path(self.database_path).exists():
                return False
                
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            # Consulta mejorada usando LIKE para coincidencias parciales
            # y consulta a la tabla song_fts para búsqueda de texto completo
            query = """
            SELECT COUNT(*) FROM songs 
            WHERE title LIKE ? AND artist LIKE ?
            """
            
            cursor.execute(query, (f"%{track_title}%", f"%{artist_name}%"))
            result = cursor.fetchone()
            
            # Si no encontramos resultados con LIKE, intentamos con FTS
            if result[0] == 0:
                fts_query = """
                SELECT COUNT(*) FROM song_fts 
                WHERE song_fts MATCH ? AND song_fts MATCH ?
                """
                cursor.execute(fts_query, (track_title, artist_name))
                result = cursor.fetchone()
                
            conn.close()
            
            return result[0] > 0
        except Exception as e:
            print(f"Error al verificar canción en base de datos: {e}")
            traceback.print_exc()
            return False


    def get_lastfm_scrobbles(self, artist, track, album=None):
        """Obtiene los scrobbles de una canción desde LastFM."""
        if not hasattr(self, 'lastfm_api_key') or not self.lastfm_api_key:
            print("Error: No se ha configurado la API key de LastFM")
            return None
        
        # Parámetros para la petición a LastFM
        params = {
            'method': 'track.getInfo',
            'api_key': self.lastfm_api_key,
            'artist': artist,
            'track': track,
            'format': 'json'
        }
        
        if album:
            params['album'] = album
        
        try:
            response = requests.get('http://ws.audioscrobbler.com/2.0/', params=params)
            if response.status_code == 200:
                data = response.json()
                if 'track' in data:
                    track_info = data['track']
                    
                    # Obtener enlaces a LastFM
                    track_url = track_info.get('url', '')
                    artist_url = track_info.get('artist', {}).get('url', '')
                    album_url = track_info.get('album', {}).get('url', '')
                    
                    # Obtener número de scrobbles (playcount)
                    playcount = int(track_info.get('playcount', 0))
                    
                    return {
                        'scrobbles': playcount,
                        'lastfm_track_url': track_url,
                        'lastfm_artist_url': artist_url,
                        'lastfm_album_url': album_url
                    }
            
            return {'scrobbles': 0, 'lastfm_track_url': '', 'lastfm_artist_url': '', 'lastfm_album_url': ''}
        
        except Exception as e:
            print(f"Error al obtener scrobbles de LastFM: {e}")
            return {'scrobbles': 0, 'lastfm_track_url': '', 'lastfm_artist_url': '', 'lastfm_album_url': ''}

    def get_listenbrainz_scrobbles(self, artist, track):
        """Obtiene los scrobbles de una canción desde ListenBrainz."""
        if not hasattr(self, 'listenbrainz_user') or not self.listenbrainz_user:
            print("Error: No se ha configurado el usuario de ListenBrainz")
            return 0
        
        # URL para la API de ListenBrainz
        url = f"https://api.listenbrainz.org/1/count/recordingmbid?user_name={quote_plus(self.listenbrainz_user)}"
        
        # Parámetros para la consulta
        params = {
            'artist_name': artist,
            'recording_name': track
        }
        
        try:
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                # Obtener el conteo de scrobbles
                listen_count = data.get('payload', {}).get('count', 0)
                return listen_count
            
            return 0
        
        except Exception as e:
            print(f"Error al obtener scrobbles de ListenBrainz: {e}")
            return 0

    def update_scrobbles_data(self):
        """Actualiza los datos de scrobbles solo para canciones nuevas sin información."""
        if not self.scrobbles_data:
            return
        
        # Contar cuántas canciones necesitan actualización
        tracks_to_update = [track for track in self.scrobbles_data 
                            if 'scrobbles_count' not in track or 
                            not track.get('lastfm_track_url', '') or 
                            not track.get('lastfm_artist_url', '') or 
                            not track.get('lastfm_album_url', '')]
        
        print(f"Actualizando información de scrobbles para {len(tracks_to_update)} canciones nuevas")
        
        for track in tracks_to_update:
            artist = track.get('artist', '')
            title = track.get('title', '')
            album = track.get('album', '')
            
            # Obtener datos de LastFM
            lastfm_data = self.get_lastfm_scrobbles(artist, title, album)
            
            # Obtener datos de ListenBrainz
            listenbrainz_count = self.get_listenbrainz_scrobbles(artist, title)
            
            # Combinar los contadores de scrobbles
            total_scrobbles = (lastfm_data.get('scrobbles', 0) if lastfm_data else 0) + listenbrainz_count
            
            # Actualizar los datos del track
            track['scrobbles_count'] = total_scrobbles
            
            # Añadir URLs de LastFM
            if lastfm_data:
                track['lastfm_track_url'] = lastfm_data.get('lastfm_track_url', '')
                track['lastfm_artist_url'] = lastfm_data.get('lastfm_artist_url', '')
                track['lastfm_album_url'] = lastfm_data.get('lastfm_album_url', '')
            
            # Esperar un poco para no sobrecargar las APIs
            time.sleep(0.2)
        
        # Solo actualizar el modelo si hubo cambios
        if tracks_to_update:
            # Actualizar el modelo de tabla
            self.table_model.update_data(self.scrobbles_data)

    def load_scrobbles(self, scrobbles_data):
        """Carga los scrobbles en la tabla y actualiza los datos con información adicional."""
        if not scrobbles_data:
            return
        
        # Actualizar los datos de scrobbles
        self.scrobbles_data = scrobbles_data
        
        # Actualizar la tabla
        self.table_model.update_data(self.scrobbles_data)
        
        # Obtener información adicional de LastFM y ListenBrainz
        # Esto podría ser un proceso lento, considerar hacerlo en un hilo separado
        self.update_scrobbles_data()
        
        # Actualizar el contador en la interfaz
        self.update_scrobbles_counter()


    def debug_table_data(self):
        """Función para depurar el contenido de la tabla y modelo de datos."""
        print("\n===== DEBUGGING TABLE DATA =====")
        print(f"Número de scrobbles en self.scrobbles_data: {len(self.scrobbles_data)}")
        print(f"Modelo: Filas según rowCount(): {self.table_model.rowCount()}")
        print(f"Modelo: Columnas según columnCount(): {self.table_model.columnCount()}")
        
        # Verificar si la tabla está usando el modelo proxy correctamente
        print(f"Tabla: Modelo usado: {type(self.scrobbles_table.model()).__name__}")
        print(f"Modelo proxy: Filas según rowCount(): {self.proxy_model.rowCount()}")
        
        # Verificar algunos datos de ejemplo
        if self.scrobbles_data:
            print("\nPrimeros 2 elementos en self.scrobbles_data:")
            for i, item in enumerate(self.scrobbles_data[:2]):
                print(f"  {i}: {item}")
        
        print("================================\n")
    
 

    def on_table_clicked(self, index):
        """Maneja clics en la tabla de scrobbles."""
        # Obtener la columna y la fila del índice
        column = index.column()
        proxy_row = index.row()
        
        # Convertir índice del modelo proxy al índice del modelo fuente
        source_index = self.proxy_model.mapToSource(index)
        source_row = source_index.row()
        
        track_data = self.scrobbles_data[source_row]
        
        # Manejar clics en columnas clickables
        if column == 1 and 'lastfm_track_url' in track_data and track_data['lastfm_track_url']:
            # Clic en canción - abrir URL de LastFM para la canción
            QDesktopServices.openUrl(QUrl(track_data['lastfm_track_url']))
        
        elif column == 2 and 'lastfm_album_url' in track_data and track_data['lastfm_album_url']:
            # Clic en álbum - abrir URL de LastFM para el álbum
            QDesktopServices.openUrl(QUrl(track_data['lastfm_album_url']))
        
        elif column == 3 and 'lastfm_artist_url' in track_data and track_data['lastfm_artist_url']:
            # Clic en artista - abrir URL de LastFM para el artista
            QDesktopServices.openUrl(QUrl(track_data['lastfm_artist_url']))
        
        elif column == 6:  # Columna "En Base de Datos"
            print(f"Click en columna DB para canción: {track_data['title']}")
            # Llamar al método para cambiar a la pestaña Music Browser
            self.switch_tab("Music Browser", "set_search_text", f"t:{track_data.get('title')}")

    
    def init_table_model(self):
        """Inicializa el modelo de tabla con la configuración correcta."""
        # Asegurarse de que scrobbles_data tenga al menos una estructura vacía
        if not hasattr(self, 'scrobbles_data') or self.scrobbles_data is None:
            self.scrobbles_data = []
        
        # Crear el modelo de tabla
        self.table_model = ScrobblesTableModel(self.scrobbles_data)
        
        # Configurar el modelo proxy
        self.proxy_model = QSortFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.table_model)
        
        # Asignar el modelo proxy a la tabla
        self.scrobbles_table.setModel(self.proxy_model)
        
        # Configurar cabeceras de la tabla
        self.scrobbles_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        # Configurar clic en celda
        self.scrobbles_table.clicked.connect(self.on_table_clicked)
        
        # Establecer el ancho preferido para la columna de scrobbles
        self.scrobbles_table.setColumnWidth(5, 100)
        
        # Permitir el sorting
        self.scrobbles_table.setSortingEnabled(True)

        # Configurar cabeceras de la tabla
        self.scrobbles_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        # Configurar clic en celda
        self.scrobbles_table.clicked.connect(self.on_table_clicked)
        
        # Permitir el sorting
        self.scrobbles_table.setSortingEnabled(True)
        
        # Cambiar el cursor al pasar sobre celdas clickables
        self.scrobbles_table.setMouseTracking(True)
        self.scrobbles_table.viewport().installEventFilter(self)


    def eventFilter(self, obj, event):
        """Filtro de eventos para cambiar el cursor al pasar sobre celdas clickables."""
        if obj is self.scrobbles_table.viewport() and event.type() == QEvent.Type.MouseMove:
            pos = event.pos()
            index = self.scrobbles_table.indexAt(pos)
            if index.isValid():
                # Convertir al índice del modelo fuente
                source_index = self.proxy_model.mapToSource(index)
                row = source_index.row()
                col = source_index.column()
                
                # Verificar si la celda es clickable
                is_clickable = False
                if 0 <= row < len(self.scrobbles_data):
                    if col == 1 and 'lastfm_track_url' in self.scrobbles_data[row] and self.scrobbles_data[row]['lastfm_track_url']:
                        is_clickable = True
                    elif col == 2 and 'lastfm_album_url' in self.scrobbles_data[row] and self.scrobbles_data[row]['lastfm_album_url']:
                        is_clickable = True
                    elif col == 3 and 'lastfm_artist_url' in self.scrobbles_data[row] and self.scrobbles_data[row]['lastfm_artist_url']:
                        is_clickable = True
                    elif col == 6:  # Columna "En Base de Datos"
                        is_clickable = True
                
                # Cambiar el cursor según corresponda
                if is_clickable:
                    self.scrobbles_table.setCursor(Qt.CursorShape.PointingHandCursor)
                else:
                    self.scrobbles_table.setCursor(Qt.CursorShape.ArrowCursor)
        
        return super().eventFilter(obj, event)



class ScrobblesTableModel(QAbstractTableModel):
    """Modelo de datos para la tabla de scrobbles."""
    
    def __init__(self, data):
        super().__init__()
        self._data = data if data else []
        # Mantener las columnas originales más la de scrobbles
        self._headers = ["Fecha/Hora", "Canción", "Álbum", "Artista", "Estado", "Scrobbles", "En Base de Datos"]
    
    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._data)):
            return None
        
        row = index.row()
        col = index.column()
        
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return self._data[row]['timestamp']
            elif col == 1:
                return self._data[row]['title']
            elif col == 2:
                return self._data[row]['album']
            elif col == 3:
                return self._data[row]['artist']
            elif col == 4:
                return self._data[row]['status']
            elif col == 5:
                # Columna de scrobbles
                return str(self._data[row].get('scrobbles_count', 0))
            elif col == 6:
                return "✓" if self._data[row].get('in_database', False) else "➕"
        
        # Agregar estilos por rol
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col == 5:  # Centrar la columna de Scrobbles
                return int(Qt.AlignmentFlag.AlignCenter)
            if col == 6:  # Centrar la columna de Base de Datos
                return int(Qt.AlignmentFlag.AlignCenter)
        
        elif role == Qt.ItemDataRole.ForegroundRole:
            # Cambiar el color de texto para indicar que es clickable
            if col == 1 and 'lastfm_track_url' in self._data[row] and self._data[row]['lastfm_track_url']:
                return QColor('#1565C0')  # Azul para enlaces
            elif col == 2 and 'lastfm_album_url' in self._data[row] and self._data[row]['lastfm_album_url']:
                return QColor('#1565C0')  # Azul para enlaces
            elif col == 3 and 'lastfm_artist_url' in self._data[row] and self._data[row]['lastfm_artist_url']:
                return QColor('#1565C0')  # Azul para enlaces
            elif col == 6:
                # Verde para los que están en la base de datos, azul para los que no
                if self._data[row].get('in_database', False):
                    return QColor('#2E7D32')  # Verde oscuro
                else:
                    return QColor('#1976D2')  # Azul
        
        elif role == Qt.ItemDataRole.ToolTipRole:
            if col == 1 and 'lastfm_track_url' in self._data[row]:  # Tooltip para la canción
                return f"Clic para abrir en LastFM: {self._data[row]['title']}"
            elif col == 2 and 'lastfm_album_url' in self._data[row]:  # Tooltip para el álbum
                return f"Clic para abrir en LastFM: {self._data[row]['album']}"
            elif col == 3 and 'lastfm_artist_url' in self._data[row]:  # Tooltip para el artista
                return f"Clic para abrir en LastFM: {self._data[row]['artist']}"
            elif col == 5:
                return f"Total de scrobbles: {self._data[row].get('scrobbles_count', 0)}"
            elif col == 6:
                if self._data[row].get('in_database', False):
                    return "Esta canción existe en la base de datos"
                else:
                    return "Haz clic para buscar esta canción en la base de datos"
        
        # Opcional: Añadir un estilo para mostrar que es clickable (cursor de mano)
        elif role == Qt.ItemDataRole.DecorationRole:
            if (col == 1 and 'lastfm_track_url' in self._data[row]) or \
               (col == 2 and 'lastfm_album_url' in self._data[row]) or \
               (col == 3 and 'lastfm_artist_url' in self._data[row]):
                return QIcon.fromTheme("emblem-web")  # Pequeño icono web, si está disponible
        
        return None
    
    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self._headers[section]
        
        return None
    
    def update_data(self, data):
        """Actualiza los datos del modelo con notificación explícita."""
        # Verificar que data no sea None
        data_to_use = data if data is not None else []
        
        # Notificar a las vistas que empezamos a resetear el modelo
        self.beginResetModel()
        
        # Actualizar los datos
        self._data = data_to_use.copy()
        
        # Notificar a las vistas que terminamos de resetear el modelo
        self.endResetModel()


class ScrobblesTableModel(QAbstractTableModel):
    """Modelo de datos para la tabla de scrobbles."""
    
    def __init__(self, data):
        super().__init__()
        self._data = data if data else []
        self._headers = ["Fecha/Hora", "Canción", "Álbum", "Artista", "Estado", "En Base de Datos"]
    
    def rowCount(self, parent=None):
        return len(self._data)
    
    def columnCount(self, parent=None):
        return len(self._headers)
    
    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._data)):
            return None
        
        row = index.row()
        col = index.column()
        
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return self._data[row]['timestamp']
            elif col == 1:
                return self._data[row]['title']
            elif col == 2:
                return self._data[row]['album']
            elif col == 3:
                return self._data[row]['artist']
            elif col == 4:
                return self._data[row]['status']
            elif col == 5:
                return "✓" if self._data[row].get('in_database', False) else "➕"
        
        # Agregar estilos por rol
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col == 5:  # Centrar la columna de Base de Datos
                return int(Qt.AlignmentFlag.AlignCenter)
        
        elif role == Qt.ItemDataRole.ForegroundRole:
            if col == 5:
                # Verde para los que están en la base de datos, azul para los que no
                if self._data[row].get('in_database', False):
                    return QColor('#2E7D32')  # Verde oscuro
                else:
                    return QColor('#1976D2')  # Azul
        
        elif role == Qt.ItemDataRole.ToolTipRole:
            if col == 5:
                if self._data[row].get('in_database', False):
                    return "Esta canción existe en la base de datos"
                else:
                    return "Haz clic para buscar esta canción en la base de datos"
        
        return None
    
    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self._headers[section]
        
        return None
    
    def update_data(self, data):
        """Actualiza los datos del modelo con notificación explícita."""
        # Verificar que data no sea None
        data_to_use = data if data is not None else []
        
        # Notificar a las vistas que empezamos a resetear el modelo
        self.beginResetModel()
        
        # Actualizar los datos
        self._data = data_to_use.copy()
        
        # Notificar a las vistas que terminamos de resetear el modelo
        self.endResetModel()