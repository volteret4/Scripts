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
from PyQt6.QtGui import QFont

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
                        
                    track_data = {
                        'timestamp': timestamp,
                        'title': track['name'],
                        'artist': track['artist']['#text'],
                        'album': track['album']['#text'] if 'album' in track and '#text' in track['album'] else "-",
                        'status': status
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
        """Carga información de la canción actual desde la base de datos."""
        try:
            # Verificar si el archivo de la base de datos existe
            if not Path(self.database_path).exists():
                print(f"Base de datos no encontrada: {self.database_path}")
                self.current_song = {
                    'title': 'No hay base de datos',
                    'artist': '-',
                    'album': '-',
                    'duration': '-',
                    'play_count': '-'
                }
                return
                
        #     conn = sqlite3.connect(self.database_path)
        #     cursor = conn.cursor()
            
        #     # Consulta para obtener la canción actual
        #     query = """
        #     SELECT title, artist, album, duration, play_count
        #     FROM current_song
        #     ORDER BY timestamp DESC
        #     LIMIT 1
        #     """
            
        #     cursor.execute(query)
        #     result = cursor.fetchone()
            
        #     if result:
        #         self.current_song = {
        #             'title': result[0],
        #             'artist': result[1],
        #             'album': result[2],
        #             'duration': result[3],
        #             'play_count': result[4]
        #         }
        #     else:
        #         self.current_song = {
        #             'title': 'No hay datos',
        #             'artist': '-',
        #             'album': '-',
        #             'duration': '-',
        #             'play_count': '-'
        #         }
            
        #     conn.close()
            
        # except sqlite3.OperationalError as e:
        #     print(f"Error de SQLite al cargar la canción actual: {e}")
        #     self.current_song = {
        #         'title': 'Error en la base de datos',
        #         'artist': str(e),
        #         'album': '-',
        #         'duration': '-',
        #         'play_count': '-'
        #     }
        except Exception as e:
            print(f"Error al cargar la canción actual: {e}")
            traceback.print_exc()
            self.current_song = {
                'title': 'Error',
                'artist': str(e),
                'album': '-',
                'duration': '-',
                'play_count': '-'
            }
    
    # ACTUALIZACIÓN DE LA INTERFAZ
    def update_ui(self):
        """Actualiza los elementos de la interfaz con los datos cargados."""
        # Actualizar información de la canción actual
        self.song_title.setText(f"Título: {self.current_song['title']}")
        self.song_artist.setText(f"Artista: {self.current_song['artist']}")
        self.song_album.setText(f"Álbum: {self.current_song['album']}")
        self.song_duration.setText(f"Duración: {self.current_song['duration']}")
        self.song_playcount.setText(f"Reproducciones: {self.current_song['play_count']}")
        
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


    def search_and_load_track_info(self, track_title=None, artist_name=None):
        """Busca información de la pista en la base de datos de música a través del módulo MUSIC_FUZZY."""
        if not hasattr(self, 'tab_manager') or self.tab_manager is None:
            print("No se puede buscar información de pista: TabManager no configurado")
            return
        
        # Si tenemos canción actual o recibimos parámetros
        if track_title is None and artist_name is None and hasattr(self, 'current_song'):
            track_title = self.current_song.get('title')
            artist_name = self.current_song.get('artist')
        
        if not track_title or not artist_name or track_title == '-' or artist_name == '-':
            print("No hay suficiente información para buscar")
            return
        
        # Construir query para el módulo de búsqueda
        query = f"title:\"{track_title}\" artist:\"{artist_name}\""
        
        # Llamar al método de búsqueda en el módulo MUSIC_FUZZY
        try:
            results = self.call_module_method('MUSIC_FUZZY', 'search_parser_query', query)
            
            if results and len(results) > 0:
                print(f"Encontrado {len(results)} resultados para '{track_title}' por '{artist_name}'")
                # Aquí podrías mostrar la información encontrada o actualizar la UI
                # Por ejemplo, añadir un botón para mostrar detalles completos
            else:
                print(f"No se encontraron resultados para '{track_title}' por '{artist_name}'")
        
        except Exception as e:
            print(f"Error al buscar pista: {e}")
            traceback.print_exc()


class ScrobblesTableModel(QAbstractTableModel):
    """Modelo de datos para la tabla de scrobbles."""
    
    def __init__(self, data):
        super().__init__()
        self._data = data if data else []
        self._headers = ["Fecha/Hora", "Canción", "Álbum", "Artista", "Estado"]
    
    def rowCount(self, parent=None):
        return len(self._data)
    
    def columnCount(self, parent=None):
        return len(self._headers)
    
    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._data)):
            return None
        
        if role == Qt.ItemDataRole.DisplayRole:
            row = index.row()
            col = index.column()
            
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
if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Parámetros de ejemplo, pero ya se cargan desde el config.json
    api_key = "YOUR_API_KEY"
    username = "YOUR_USERNAME"
    database_path = "./music.db"
    track_limit = 50
    
    # Si se proporcionan argumentos
    if len(sys.argv) > 4:
        api_key = sys.argv[1]
        username = sys.argv[2]
        database_path = sys.argv[3]
        track_limit = int(sys.argv[4])
    
    # Crear y mostrar el módulo
    module = LastFMModule(api_key, username, database_path, track_limit)
    module.show()
    
    sys.exit(app.exec())