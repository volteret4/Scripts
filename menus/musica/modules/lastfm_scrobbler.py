import sys
import json
import traceback
import sqlite3
import requests
from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                            QTableView, QHeaderView, QLabel, QSplitter, QFrame,
                            QScrollArea)
from PyQt6.QtCore import Qt, QAbstractTableModel, pyqtSignal, QSortFilterProxyModel, QTimer, QUrl
from PyQt6.QtGui import QFont, QColor, QDesktopServices

from base_module import BaseModule, THEMES, PROJECT_ROOT

class LastFMModule(BaseModule):
    """
    Módulo para visualizar datos de LastFM y la canción actual desde una base de datos.
    Muestra información de la canción en reproducción y un historial de scrobbles.
    """
    
    def __init__(self, api_key, username, database_path, track_limit=50):
        # Primero asignamos las propiedades
        self.api_key = api_key
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
        self.current_title = QLabel("Canción Actual")
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
        

    

    
# Actualización para inicializar la tabla con la nueva columna
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
        
        # Permitir el sorting
        self.scrobbles_table.setSortingEnabled(True)



    # CARGA DE DATOS
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
                
        except Exception as e:
            print(f"Error al cargar datos: {e}")
            traceback.print_exc()
    
    def fetch_lastfm_data(self):
        """Obtiene datos recientes de LastFM a través de su API."""
        try:
            print(f"Intentando obtener datos de LastFM para {self.username}")
            url = "http://ws.audioscrobbler.com/2.0/"
            params = {
                'method': 'user.getrecenttracks',
                'user': self.username,
                'api_key': self.api_key,
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
                    a.formed_year, a.bio, a.origin, a.rateyourmusic_url, a.discogs_url
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
        
        # Sección de información técnica si está disponible
        if self.current_song.get('in_database', False):
            
            # Separador
            separator = QFrame()
            separator.setFrameShape(QFrame.Shape.HLine)
            separator.setFrameShadow(QFrame.Shadow.Sunken)
            info_layout.addWidget(separator)
            
            # Sección técnica
            tech_widget = QWidget()
            tech_layout = QVBoxLayout(tech_widget)
            
            tech_title = QLabel("Información Técnica")
            tech_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            tech_layout.addWidget(tech_title)
            
            if 'genre' in self.current_song:
                tech_layout.addWidget(QLabel(f"Género: {self.current_song.get('genre', '-')}"))
            if 'bitrate' in self.current_song:
                tech_layout.addWidget(QLabel(f"Bitrate: {self.current_song.get('bitrate', '-')} kbps"))
            if 'sample_rate' in self.current_song:
                tech_layout.addWidget(QLabel(f"Sample Rate: {self.current_song.get('sample_rate', '-')} Hz"))
            if 'bit_depth' in self.current_song:
                tech_layout.addWidget(QLabel(f"Bit Depth: {self.current_song.get('bit_depth', '-')} bits"))
            
            info_layout.addWidget(tech_widget)
            
            # Enlaces para la canción
            separator2 = QFrame()
            separator2.setFrameShape(QFrame.Shape.HLine)
            separator2.setFrameShadow(QFrame.Shadow.Sunken)
            info_layout.addWidget(separator2)
            
            # Sección de enlaces
            links_widget = QWidget()
            links_layout = QVBoxLayout(links_widget)
            
            links_title = QLabel("Enlaces")
            links_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            links_layout.addWidget(links_title)
            
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
            
            # Letras
            if 'has_lyrics' in self.current_song and self.current_song['has_lyrics']:
                lyrics_button = QPushButton("Ver Letras")
                lyrics_button.clicked.connect(lambda: self.show_lyrics(self.current_song.get('song_id')))
                
    
                links_layout.addWidget(lyrics_button)
            
            info_layout.addWidget(links_widget)
            
            # Información del Artista
            if 'artist_details' in self.current_song:

                # Actualizar botones de información adicional
                has_artist_info = 'artist_details' in self.current_song and (
                    self.current_song['artist_details'].get('wikipedia_content', '-') != '-' or
                    self.current_song['artist_details'].get('bio', '-') != '-'
                )
                has_album_info = 'album_details' in self.current_song and (
                    self.current_song['album_details'].get('wikipedia_content', '-') != '-'
                )
                if has_artist_info:
                    self.artist_wiki_button.setEnabled(has_artist_info)
                
                if has_album_info:
                    self.album_wiki_button.setEnabled(has_album_info)

                separator3 = QFrame()
                separator3.setFrameShape(QFrame.Shape.HLine)
                separator3.setFrameShadow(QFrame.Shadow.Sunken)
                info_layout.addWidget(separator3)
                
                artist_widget = QWidget()
                artist_layout = QVBoxLayout(artist_widget)
                
                artist_title = QLabel(f"Información del Artista: {self.current_song['artist']}")
                artist_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
                artist_layout.addWidget(artist_title)
                
                artist_details = self.current_song['artist_details']
                
                if artist_details.get('bio', '-') != '-':
                    bio_label = QLabel("Biografía:")
                    bio_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
                    artist_layout.addWidget(bio_label)
                    
                    bio_text = QTextEdit()
                    bio_text.setReadOnly(True)
                    bio_text.setMaximumHeight(100)
                    bio_text.setText(artist_details['bio'][:500] + '...' if len(artist_details['bio']) > 500 else artist_details['bio'])
                    artist_layout.addWidget(bio_text)
                
                if artist_details.get('formed_year', '-') != '-' or artist_details.get('origin', '-') != '-':
                    details_layout = QHBoxLayout()
                    
                    if artist_details.get('formed_year', '-') != '-':
                        formed_label = QLabel(f"Formado en: {artist_details['formed_year']}")
                        details_layout.addWidget(formed_label)
                    
                    if artist_details.get('origin', '-') != '-':
                        origin_label = QLabel(f"Origen: {artist_details['origin']}")
                        details_layout.addWidget(origin_label)
                    
                    artist_layout.addLayout(details_layout)
                
                # Enlaces del artista
                if any(key in artist_details and artist_details[key] != '-' for key in ['spotify_url', 'youtube_url', 'musicbrainz_url', 'wikipedia_url', 'rateyourmusic_url', 'discogs_url']):
                    artist_links_label = QLabel("Enlaces del Artista:")
                    artist_links_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
                    artist_layout.addWidget(artist_links_label)
                    
                    artist_links_layout = QHBoxLayout()
                    
                    if artist_details.get('spotify_url', '-') != '-':
                        spotify_button = QPushButton("Spotify")
                        spotify_button.clicked.connect(lambda: self.open_url(artist_details.get('spotify_url')))
                        artist_links_layout.addWidget(spotify_button)
                    
                    if artist_details.get('youtube_url', '-') != '-':
                        youtube_button = QPushButton("YouTube")
                        youtube_button.clicked.connect(lambda: self.open_url(artist_details.get('youtube_url')))
                        artist_links_layout.addWidget(youtube_button)
                    
                    if artist_details.get('wikipedia_url', '-') != '-':
                        wiki_button = QPushButton("Wikipedia")
                        wiki_button.clicked.connect(lambda: self.open_url(artist_details.get('wikipedia_url')))
                        artist_links_layout.addWidget(wiki_button)
                    
                    if artist_details.get('musicbrainz_url', '-') != '-':
                        mb_button = QPushButton("MusicBrainz")
                        mb_button.clicked.connect(lambda: self.open_url(artist_details.get('musicbrainz_url')))
                        artist_links_layout.addWidget(mb_button)
                    
                    if artist_details.get('rateyourmusic_url', '-') != '-':
                        rym_button = QPushButton("RYM")
                        rym_button.clicked.connect(lambda: self.open_url(artist_details.get('rateyourmusic_url')))
                        artist_links_layout.addWidget(rym_button)
                    
                    if artist_details.get('discogs_url', '-') != '-':
                        discogs_button = QPushButton("Discogs")
                        discogs_button.clicked.connect(lambda: self.open_url(artist_details.get('discogs_url')))
                        artist_links_layout.addWidget(discogs_button)
                    
                    artist_layout.addLayout(artist_links_layout)
                
                # Botón para ver información completa del artista
                view_artist_button = QPushButton("Ver información completa del artista")
                view_artist_button.clicked.connect(lambda: self.display_artist_info(artist_details))
                artist_layout.addWidget(view_artist_button)
                
                info_layout.addWidget(artist_widget)
            
            # Información del Álbum
            if 'album_details' in self.current_song:
                separator4 = QFrame()
                separator4.setFrameShape(QFrame.Shape.HLine)
                separator4.setFrameShadow(QFrame.Shadow.Sunken)
                info_layout.addWidget(separator4)
                
                album_widget = QWidget()
                album_layout = QVBoxLayout(album_widget)
                
                album_title = QLabel(f"Información del Álbum: {self.current_song['album']}")
                album_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
                album_layout.addWidget(album_title)
                
                album_details = self.current_song['album_details']
                
                details_layout = QHBoxLayout()
                
                if album_details.get('year', '-') != '-':
                    year_label = QLabel(f"Año: {album_details['year']}")
                    details_layout.addWidget(year_label)
                
                if album_details.get('label', '-') != '-':
                    label_label = QLabel(f"Sello: {album_details['label']}")
                    details_layout.addWidget(label_label)
                
                album_layout.addLayout(details_layout)
                
                if album_details.get('genre', '-') != '-':
                    genre_label = QLabel(f"Género: {album_details['genre']}")
                    album_layout.addWidget(genre_label)
                
                if album_details.get('total_tracks', '-') != '-':
                    tracks_label = QLabel(f"Pistas: {album_details['total_tracks']}")
                    album_layout.addWidget(tracks_label)
                
                # Enlaces del álbum
                if any(key in album_details and album_details[key] != '-' for key in ['spotify_url', 'youtube_url', 'musicbrainz_url', 'wikipedia_url', 'rateyourmusic_url', 'discogs_url']):
                    album_links_label = QLabel("Enlaces del Álbum:")
                    album_links_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
                    album_layout.addWidget(album_links_label)
                    
                    album_links_layout = QHBoxLayout()
                    
                    if album_details.get('spotify_url', '-') != '-':
                        spotify_button = QPushButton("Spotify")
                        spotify_button.clicked.connect(lambda: self.open_url(album_details.get('spotify_url')))
                        album_links_layout.addWidget(spotify_button)
                    
                    if album_details.get('youtube_url', '-') != '-':
                        youtube_button = QPushButton("YouTube")
                        youtube_button.clicked.connect(lambda: self.open_url(album_details.get('youtube_url')))
                        album_links_layout.addWidget(youtube_button)
                    
                    if album_details.get('wikipedia_url', '-') != '-':
                        wiki_button = QPushButton("Wikipedia")
                        wiki_button.clicked.connect(lambda: self.open_url(album_details.get('wikipedia_url')))
                        album_links_layout.addWidget(wiki_button)
                    
                    if album_details.get('musicbrainz_url', '-') != '-':
                        mb_button = QPushButton("MusicBrainz")
                        mb_button.clicked.connect(lambda: self.open_url(album_details.get('musicbrainz_url')))
                        album_links_layout.addWidget(mb_button)
                    
                    if album_details.get('rateyourmusic_url', '-') != '-':
                        rym_button = QPushButton("RYM")
                        rym_button.clicked.connect(lambda: self.open_url(album_details.get('rateyourmusic_url')))
                        album_links_layout.addWidget(rym_button)
                    
                    if album_details.get('discogs_url', '-') != '-':
                        discogs_button = QPushButton("Discogs")
                        discogs_button.clicked.connect(lambda: self.open_url(album_details.get('discogs_url')))
                        album_links_layout.addWidget(discogs_button)
                    
                    album_layout.addLayout(album_links_layout)
                
                # Si hay contenido de Wikipedia
                if album_details.get('wikipedia_content', '-') != '-':
                    wiki_label = QLabel("Información de Wikipedia:")
                    wiki_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
                    album_layout.addWidget(wiki_label)
                    
                    wiki_text = QTextEdit()
                    wiki_text.setReadOnly(True)
                    wiki_text.setMaximumHeight(100)
                    wiki_text.setText(album_details['wikipedia_content'][:500] + '...' if len(album_details['wikipedia_content']) > 500 else album_details['wikipedia_content'])
                    album_layout.addWidget(wiki_text)
                
                info_layout.addWidget(album_widget)
        
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


    def display_artist_info(self, artist_data):
        """Muestra la información completa del artista en una ventana de diálogo."""
        from PyQt6.QtWidgets import QDialog, QTextBrowser, QVBoxLayout, QHBoxLayout, QPushButton
        
        # Crear un diálogo para mostrar la información
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Información del Artista: {artist_data.get('name', artist_data.get('artist', '-'))}")
        dialog.resize(800, 600)
        
        # Crear un explorador de texto para mostrar la información
        text_browser = QTextBrowser()
        text_browser.setOpenExternalLinks(True)
        
        # Formatear la información como HTML
        html_content = f"<h1>{artist_data.get('name', artist_data.get('artist', '-'))}</h1>"
        
        # Información básica
        if artist_data.get('formed_year', '-') != '-' or artist_data.get('origin', '-') != '-':
            html_content += "<h2>Información Básica</h2>"
            html_content += "<ul>"
            if artist_data.get('formed_year', '-') != '-':
                html_content += f"<li><b>Formado en:</b> {artist_data['formed_year']}</li>"
            if artist_data.get('origin', '-') != '-':
                html_content += f"<li><b>Origen:</b> {artist_data['origin']}</li>"
            if artist_data.get('tags', '-') != '-':
                html_content += f"<li><b>Etiquetas:</b> {artist_data['tags']}</li>"
            if artist_data.get('total_albums', '-') != '-':
                html_content += f"<li><b>Total de álbumes:</b> {artist_data['total_albums']}</li>"
            html_content += "</ul>"
        
        # Biografía
        if artist_data.get('bio', '-') != '-':
            html_content += "<h2>Biografía</h2>"
            html_content += f"<p>{artist_data['bio']}</p>"
        
        # Contenido de Wikipedia
        if artist_data.get('wikipedia_content', '-') != '-':
            html_content += "<h2>De Wikipedia</h2>"
            html_content += f"<p>{artist_data['wikipedia_content']}</p>"
        
        # Enlaces
        html_content += "<h2>Enlaces</h2><ul>"
        for link_type in ['spotify_url', 'youtube_url', 'musicbrainz_url', 'wikipedia_url', 'rateyourmusic_url', 'discogs_url']:
            if link_type in artist_data and artist_data[link_type] != '-':
                platform_name = link_type.split('_')[0].capitalize()
                html_content += f"<li><a href='{artist_data[link_type]}'>{platform_name}</a></li>"
        html_content += "</ul>"
        
        # Artistas similares
        if artist_data.get('similar_artists', '-') != '-':
            html_content += "<h2>Artistas Similares</h2>"
            html_content += f"<p>{artist_data['similar_artists']}</p>"
        
        # Establecer el contenido HTML
        text_browser.setHtml(html_content)
        
        # Botones de navegación
        button_layout = QHBoxLayout()
        close_button = QPushButton("Cerrar")
        close_button.clicked.connect(dialog.accept)
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        
        # Configurar el layout
        layout = QVBoxLayout()
        layout.addWidget(text_browser)
        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        
        # Mostrar el diálogo
        dialog.exec()

    def display_artist_info(self, artist_data):
        """Muestra la información del artista en una ventana o panel"""
        # Aquí implementarías cómo mostrar la información obtenida
        # Por ejemplo, podrías crear una nueva ventana o diálogo
        
        from PyQt6.QtWidgets import QDialog, QTextBrowser, QVBoxLayout
        
        # Crear un diálogo para mostrar la información
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Información del Artista")
        dialog.resize(800, 600)
        
        # Crear un explorador de texto para mostrar la información
        text_browser = QTextBrowser()
        
        # Formatear la información como HTML
        html_content = "<h1>Información del Artista</h1>"
        
        # Añadir enlaces
        if "links" in artist_data:
            html_content += "<h2>Enlaces</h2><ul>"
            for platform, url in artist_data["links"].items():
                html_content += f"<li><a href='{url}'>{platform.capitalize()}</a></li>"
            html_content += "</ul>"
        
        # Añadir información de Wikipedia si está disponible
        if "wikipedia_content" in artist_data and artist_data["wikipedia_content"]:
            html_content += "<h2>Biografía</h2>"
            html_content += f"<p>{artist_data['wikipedia_content'][:500]}...</p>"
        
        # Mostrar álbumes
        if "albums" in artist_data and artist_data["albums"]:
            html_content += "<h2>Álbumes</h2><ul>"
            for album in artist_data["albums"]:
                html_content += f"<li><b>{album['name']}</b> ({album['year']}) - {album['genre']}</li>"
            html_content += "</ul>"
        
        # Establecer el contenido HTML
        text_browser.setHtml(html_content)
        
        # Configurar el layout
        layout = QVBoxLayout()
        layout.addWidget(text_browser)
        dialog.setLayout(layout)
        
        # Mostrar el diálogo
        dialog.exec()

    def open_url(self, url):
        """Abre una URL en el navegador predeterminado."""
        if not url or url == '-':
            return
            
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception as e:
            print(f"Error al abrir URL {url}: {e}")




    
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

    def on_table_clicked(self, index):
        """Maneja clics en la tabla de scrobbles."""
        # Obtener la columna y la fila del índice
        column = index.column()
        proxy_row = index.row()
        
        # Convertir índice del modelo proxy al índice del modelo fuente
        source_index = self.proxy_model.mapToSource(index)
        source_row = source_index.row()
        
        # Si la columna es la última (Estado en DB), ejecutar la acción
        if column == 5:  # Columna "En Base de Datos"
            track_data = self.scrobbles_data[source_row]
            print(f"Click en columna DB para canción: {track_data['title']}")
            
            # Llamar al método para cambiar a la pestaña Music Browser
            self.switch_tab("Music Browser", "set_search_text", f"t:{track_data.get('title')}")





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