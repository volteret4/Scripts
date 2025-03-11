import sys
import json
import traceback
import sqlite3
import requests
from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                            QTableView, QHeaderView, QLabel, QSplitter, QFrame)
from PyQt6.QtCore import Qt, QAbstractTableModel, pyqtSignal, QSortFilterProxyModel,QTimer
from PyQt6.QtGui import QFont,QColor

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
        """Carga información de la canción actual desde la base de datos con información adicional."""
        try:
            # Verificar si el archivo de la base de datos existe
            if not Path(self.database_path).exists():
                print(f"Base de datos no encontrada: {self.database_path}")
                self.current_song = {
                    'title': 'No hay base de datos',
                    'artist': '-',
                    'album': '-',
                    'duration': '-',
                    'play_count': '-',
                    'in_database': False
                }
                return
                    
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            # Consulta para obtener la canción actual con datos extendidos
            query = """
            SELECT cs.title, cs.artist, cs.album, cs.duration, cs.play_count,
                s.id, s.genre, s.album_artist, s.date, s.bitrate,
                s.sample_rate, s.bit_depth, s.mbid, s.has_lyrics
            FROM current_song cs
            LEFT JOIN songs s ON cs.title LIKE '%' || s.title || '%' AND cs.artist LIKE '%' || s.artist || '%'
            ORDER BY cs.timestamp DESC
            LIMIT 1
            """
            
            cursor.execute(query)
            result = cursor.fetchone()
            
            if result:
                has_song_data = result[5] is not None  # Comprobamos si hay un ID de canción
                
                self.current_song = {
                    'title': result[0],
                    'artist': result[1],
                    'album': result[2],
                    'duration': result[3],
                    'play_count': result[4],
                    'in_database': has_song_data
                }
                
                # Si encontramos la canción en la base de datos, añadimos los datos adicionales
                if has_song_data:
                    self.current_song.update({
                        'song_id': result[5],
                        'genre': result[6] or '-',
                        'album_artist': result[7] or '-',
                        'date': result[8] or '-',
                        'bitrate': result[9] or '-',
                        'sample_rate': result[10] or '-',
                        'bit_depth': result[11] or '-',
                        'mbid': result[12] or '-',
                        'has_lyrics': bool(result[13])
                    })
                    
                    # Intentar obtener enlaces relacionados con la canción
                    song_id = result[5]
                    links_query = """
                    SELECT spotify_url, lastfm_url, youtube_url, musicbrainz_url 
                    FROM song_links 
                    WHERE song_id = ?
                    """
                    cursor.execute(links_query, (song_id,))
                    links_result = cursor.fetchone()
                    
                    if links_result:
                        self.current_song.update({
                            'spotify_url': links_result[0] or '-',
                            'lastfm_url': links_result[1] or '-',
                            'youtube_url': links_result[2] or '-',
                            'musicbrainz_url': links_result[3] or '-'
                        })
            else:
                # Si no hay datos en la base de datos, intentar usar datos de LastFM
                if hasattr(self, 'scrobbles_data') and self.scrobbles_data:
                    # Buscar una canción que esté reproduciendo actualmente
                    now_playing = next((track for track in self.scrobbles_data 
                                    if track.get('status') == 'Reproduciendo'), None)
                    
                    if now_playing:
                        self.current_song = {
                            'title': now_playing['title'],
                            'artist': now_playing['artist'],
                            'album': now_playing['album'],
                            'duration': '-',
                            'play_count': '-',
                            'in_database': False
                        }
                        print(f"Usando datos de LastFM para canción actual: {self.current_song['title']}")
                    else:
                        self.current_song = {
                            'title': 'No hay datos en reproducción',
                            'artist': '-',
                            'album': '-',
                            'duration': '-',
                            'play_count': '-',
                            'in_database': False
                        }
                else:
                    self.current_song = {
                        'title': 'No hay datos',
                        'artist': '-',
                        'album': '-',
                        'duration': '-',
                        'play_count': '-',
                        'in_database': False
                    }
            
            conn.close()
            
        except sqlite3.OperationalError as e:
            print(f"Error de SQLite al cargar la canción actual: {e}")
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
        """Actualiza los elementos de la interfaz con los datos cargados, incluyendo información extendida."""
        # Actualizar información de la canción actual (información básica)
        self.song_title.setText(f"Título: {self.current_song['title']}")
        self.song_artist.setText(f"Artista: {self.current_song['artist']}")
        self.song_album.setText(f"Álbum: {self.current_song['album']}")
        self.song_duration.setText(f"Duración: {self.current_song['duration']}")
        self.song_playcount.setText(f"Reproducciones: {self.current_song['play_count']}")
        
        # Añadir información extendida si está disponible
        if self.current_song.get('in_database', False):
            # Restablecer estilos normales
            self.song_title.setStyleSheet("")
            self.song_artist.setStyleSheet("")
            self.song_album.setStyleSheet("")
            
            # Ocultar label de advertencia si existe
            if hasattr(self, 'db_warning_label'):
                self.db_warning_label.setVisible(False)
                
            # Mostrar información extendida si está disponible
            if hasattr(self, 'extended_info_layout') and 'genre' in self.current_song:
                # Si ya tenemos un layout de información extendida, actualizarlo
                if not hasattr(self, 'genre_label'):
                    # Crear labels si no existen
                    self.genre_label = QLabel(f"Género: {self.current_song.get('genre', '-')}")
                    self.bitrate_label = QLabel(f"Bitrate: {self.current_song.get('bitrate', '-')} kbps")
                    self.sample_rate_label = QLabel(f"Sample Rate: {self.current_song.get('sample_rate', '-')} Hz")
                    
                    # Añadir al layout
                    self.extended_info_layout.addWidget(self.genre_label)
                    self.extended_info_layout.addWidget(self.bitrate_label)
                    self.extended_info_layout.addWidget(self.sample_rate_label)
                    
                    # Si hay enlaces, añadirlos como botones
                    if 'spotify_url' in self.current_song and self.current_song['spotify_url'] != '-':
                        self.spotify_button = QPushButton("Abrir en Spotify")
                        self.spotify_button.clicked.connect(
                            lambda: self.open_url(self.current_song.get('spotify_url'))
                        )
                        self.extended_info_layout.addWidget(self.spotify_button)
                    
                    if 'has_lyrics' in self.current_song and self.current_song['has_lyrics']:
                        self.lyrics_button = QPushButton("Ver Letras")
                        self.lyrics_button.clicked.connect(
                            lambda: self.show_lyrics(self.current_song.get('song_id'))
                        )
                        self.extended_info_layout.addWidget(self.lyrics_button)
                else:
                    # Actualizar los labels existentes
                    self.genre_label.setText(f"Género: {self.current_song.get('genre', '-')}")
                    self.bitrate_label.setText(f"Bitrate: {self.current_song.get('bitrate', '-')} kbps")
                    self.sample_rate_label.setText(f"Sample Rate: {self.current_song.get('sample_rate', '-')} Hz")
            else:
                # Crear un nuevo layout para información extendida
                if 'genre' in self.current_song:
                    self.extended_info_layout = QVBoxLayout()
                    self.song_info_layout.addLayout(self.extended_info_layout)
                    
                    # Crear y añadir labels
                    self.genre_label = QLabel(f"Género: {self.current_song.get('genre', '-')}")
                    self.bitrate_label = QLabel(f"Bitrate: {self.current_song.get('bitrate', '-')} kbps")
                    self.sample_rate_label = QLabel(f"Sample Rate: {self.current_song.get('sample_rate', '-')} Hz")
                    
                    self.extended_info_layout.addWidget(self.genre_label)
                    self.extended_info_layout.addWidget(self.bitrate_label)
                    self.extended_info_layout.addWidget(self.sample_rate_label)
                    
                    # Si hay enlaces, añadirlos como botones
                    if 'spotify_url' in self.current_song and self.current_song['spotify_url'] != '-':
                        self.spotify_button = QPushButton("Abrir en Spotify")
                        self.spotify_button.clicked.connect(
                            lambda: self.open_url(self.current_song.get('spotify_url'))
                        )
                        self.extended_info_layout.addWidget(self.spotify_button)
                    
                    if 'has_lyrics' in self.current_song and self.current_song['has_lyrics']:
                        self.lyrics_button = QPushButton("Ver Letras")
                        self.lyrics_button.clicked.connect(
                            lambda: self.show_lyrics(self.current_song.get('song_id'))
                        )
                        self.extended_info_layout.addWidget(self.lyrics_button)
        else:
            # Si la canción no está en la base de datos, mostrar en amarillo
            warning_style = "background-color: rgba(255, 255, 0, 0.3); padding: 5px; border-radius: 3px;"
            self.song_title.setStyleSheet(warning_style)
            self.song_artist.setStyleSheet(warning_style)
            self.song_album.setStyleSheet(warning_style)
            
            # Agregar un label extra que indique "No en base de datos"
            if not hasattr(self, 'db_warning_label'):
                self.db_warning_label = QLabel("⚠️ Datos no encontrados en la base de datos")
                self.db_warning_label.setStyleSheet("color: #B7950B; font-weight: bold;")
                self.song_info_layout.insertWidget(0, self.db_warning_label)
            self.db_warning_label.setVisible(True)
            
            # Ocultar información extendida si existe
            if hasattr(self, 'extended_info_layout'):
                for i in reversed(range(self.extended_info_layout.count())): 
                    widget = self.extended_info_layout.itemAt(i).widget()
                    if widget:
                        widget.setVisible(False)
        
        # Actualizar el título del historial
        self.history_title.setText(f"Historial de Scrobbles ({self.username}) - {len(self.scrobbles_data)} entradas")

    
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
        
    # def set_tab_manager(self, tab_manager):
    #     """Establece el gestor de pestañas."""
    #     self.tab_manager = tab_manager


    # def search_and_load_track_info(self, track_title=None, artist_name=None):
    #     """Busca información del artista usando el script consultar_items_db.py"""
    #     # Si tenemos canción actual o recibimos parámetros
    #     if track_title is None and artist_name is None and hasattr(self, 'current_song'):
    #         track_title = self.current_song.get('title')
    #         artist_name = self.current_song.get('artist')
        
    #     if not artist_name or artist_name == '-':
    #         print("No hay suficiente información del artista para buscar")
    #         return
        
    #     try:
    #         # Construir el comando para ejecutar el script
    #         import subprocess
    #         import json
            
    #         # Ejecutar el script consultar_items_db.py con los argumentos adecuados
    #         command = ["python", "consultar_items_db.py", "--artist", artist_name, "--artist-info"]
    #         print(f"Ejecutando comando: {' '.join(command)}")
            
    #         # Ejecutar el proceso y capturar la salida
    #         result = subprocess.run(command, capture_output=True, text=True, check=True)
            
    #         # Cargar los datos JSON de la respuesta
    #         if result.stdout:
    #             artist_data = json.loads(result.stdout)
    #             print(f"Información obtenida para el artista '{artist_name}'")
                
    #             # Aquí puedes procesar los datos recibidos
    #             self.display_artist_info(artist_data)
    #         else:
    #             print(f"No se encontraron resultados para el artista '{artist_name}'")
        
    #     except subprocess.CalledProcessError as e:
    #         print(f"Error al ejecutar consultar_items_db.py: {e}")
    #         print(f"Salida de error: {e.stderr}")
    #     except json.JSONDecodeError as e:
    #         print(f"Error al decodificar la respuesta JSON: {e}")
    #     except Exception as e:
    #         print(f"Error al buscar información del artista: {e}")
    #         traceback.print_exc()


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


# Para pruebas independientes del módulo
# if __name__ == "__main__":
#     from PyQt6.QtWidgets import QApplication
    
#     app = QApplication(sys.argv)
    
#     # Parámetros de ejemplo, pero ya se cargan desde el config.json
#     api_key = "YOUR_API_KEY"
#     username = "YOUR_USERNAME"
#     database_path = "./music.db"
#     track_limit = 50
    
#     # Si se proporcionan argumentos
#     if len(sys.argv) > 4:
#         api_key = sys.argv[1]
#         username = sys.argv[2]
#         database_path = sys.argv[3]
#         track_limit = int(sys.argv[4])
    
#     # Crear y mostrar el módulo
#     module = LastFMModule(api_key, username, database_path, track_limit)
#     module.show()
    
#     sys.exit(app.exec())


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