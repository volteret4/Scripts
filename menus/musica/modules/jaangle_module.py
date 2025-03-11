from PyQt6.QtWidgets import (QLabel, QVBoxLayout, QHBoxLayout, QPushButton, 
                          QGroupBox, QGridLayout, QSpinBox, QProgressBar,
                          QComboBox, QWidget, QMessageBox, QScrollArea, QDialog,
                          QLineEdit, QCheckBox)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap
import random
import sqlite3
from pathlib import Path
import time
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtCore import QUrl
import os

from base_module import BaseModule, PROJECT_ROOT

class MusicQuiz(BaseModule):
    """Módulo de quiz musical que permite a los usuarios adivinar canciones."""
    
    quiz_completed = pyqtSignal()
    
    def __init__(self, parent=None, theme='Tokyo Night', db_path=None, config=None):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        
        # Configuración por defecto
        self.quiz_duration_minutes = 5
        self.song_duration_seconds = 30
        self.pause_between_songs = 5
        self.min_song_duration = 60  # Duración mínima en segundos
        self.start_from_beginning_chance = 0.3  # 30% de posibilidad de comenzar desde el principio
        self.avoid_last_seconds = 15  # Evitar los últimos 15 segundos
        
        # Estado del juego
        self.current_correct_option = None
        self.remaining_time = 0
        self.score = 0
        self.total_played = 0
        self.game_active = False
        self.current_song_path = None
        
        # Filtros de sesión
        self.session_filters = None


        # Si hay configuración personalizada, aplicarla
        if config:
            if 'min_song_duration' in config:
                self.min_song_duration = config['min_song_duration']
            if 'start_from_beginning_chance' in config:
                self.start_from_beginning_chance = config['start_from_beginning_chance']
            if 'avoid_last_seconds' in config:
                self.avoid_last_seconds = config['avoid_last_seconds']
        
        # Estado del juego
        self.current_correct_option = None
        self.remaining_time = 0
        self.score = 0
        self.total_played = 0
        self.game_active = False
        self.current_song_path = None
        
        # Media player
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        
        # Inicializar la UI
        super().__init__(parent, theme)
        
        # Conectar a la base de datos
        self.connect_to_database()

    def init_ui(self):
        """Inicializa la interfaz de usuario del módulo."""
        main_layout = QVBoxLayout()
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Contenedor principal con scroll
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)  # Ocultar bordes
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)  # Ocultar scrollbar horizontal
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)  # Mostrar scrollbar vertical solo cuando sea necesario
        
        # Widget contenedor para el contenido
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(20)
        
        # Configuración del juego (inicialmente oculta)
        self.config_group = QGroupBox("Configuración")
        self.config_group.setVisible(False)  # Oculta por defecto
        config_layout = QGridLayout()
        
        # Duración total del quiz (ComboBox en lugar de SpinBox)
        self.quiz_duration_combo = QComboBox()
        self.quiz_duration_combo.addItems(["1 min", "3 min", "5 min", "10 min"])
        self.quiz_duration_combo.setCurrentIndex(2)  # Default: 5 min
        config_layout.addWidget(QLabel("Duración del quiz:"), 0, 0)
        config_layout.addWidget(self.quiz_duration_combo, 0, 1)
        
        # Duración de cada canción (ComboBox en lugar de SpinBox)
        self.song_duration_combo = QComboBox()
        self.song_duration_combo.addItems(["5 seg", "10 seg", "20 seg", "30 seg", "60 seg"])
        self.song_duration_combo.setCurrentIndex(3)  # Default: 30 seg
        config_layout.addWidget(QLabel("Tiempo por canción:"), 1, 0)
        config_layout.addWidget(self.song_duration_combo, 1, 1)
        
        # Pausa entre canciones (ComboBox en lugar de SpinBox)
        self.pause_duration_combo = QComboBox()
        self.pause_duration_combo.addItems(["0 seg", "1 seg", "2 seg", "3 seg", "5 seg", "10 seg"])
        self.pause_duration_combo.setCurrentIndex(4)  # Default: 5 seg
        config_layout.addWidget(QLabel("Pausa entre canciones:"), 2, 0)
        config_layout.addWidget(self.pause_duration_combo, 2, 1)
        
        # Botones para filtros en la configuración
        filter_layout = QGridLayout()
        self.filter_artists_btn = QPushButton("Filtrar Artistas")
        self.filter_artists_btn.clicked.connect(self.show_artist_filter_dialog)
        filter_layout.addWidget(self.filter_artists_btn, 0, 0)
        
        self.filter_albums_btn = QPushButton("Filtrar Álbumes")
        self.filter_albums_btn.clicked.connect(self.show_album_filter_dialog)
        filter_layout.addWidget(self.filter_albums_btn, 0, 1)
        
        self.filter_folders_btn = QPushButton("Filtrar Carpetas")
        self.filter_folders_btn.clicked.connect(self.show_folder_filter_dialog)
        filter_layout.addWidget(self.filter_folders_btn, 1, 0)
        
        self.filter_genres_btn = QPushButton("Filtrar Géneros")
        self.filter_genres_btn.clicked.connect(self.show_genre_filter_dialog)
        filter_layout.addWidget(self.filter_genres_btn, 1, 1)
        
        self.filter_sellos_btn = QPushButton("Filtrar Sellos")
        self.filter_sellos_btn.clicked.connect(self.show_sellos_filter_dialog)
        filter_layout.addWidget(self.filter_genres_btn, 1, 1)


        # Nuevo botón para filtros de sesión
        self.session_filters_btn = QPushButton("Filtros de Sesión ⭐")
        self.session_filters_btn.clicked.connect(self.show_session_filter_dialog)
        filter_layout.addWidget(self.session_filters_btn, 2, 0)
        
        # Botón para limpiar filtros de sesión
        self.clear_session_btn = QPushButton("Limpiar Filtros Sesión")
        self.clear_session_btn.clicked.connect(self.clear_session_filters)
        filter_layout.addWidget(self.clear_session_btn, 2, 1)
        
        config_layout.addLayout(filter_layout, 3, 0, 1, 2)  # Añadir layout de filtros a la configuración
        
        self.config_group.setLayout(config_layout)
        scroll_layout.addWidget(self.config_group)
        
        # Timer y progreso en un layout horizontal más compacto con botón de inicio/detención
        timer_layout = QHBoxLayout()
        
        self.countdown_label = QLabel("30")
        self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.countdown_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        timer_layout.addWidget(self.countdown_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_bar.setMaximumHeight(self.countdown_label.sizeHint().height())
        self.progress_bar.setStyleSheet("QProgressBar { border: none; background-color: transparent; }")
        timer_layout.addWidget(self.progress_bar)
        
        # Botón toggle para iniciar/detener
        self.toggle_button = QPushButton("Iniciar Quiz")
        self.toggle_button.clicked.connect(self.toggle_quiz)
        timer_layout.addWidget(self.toggle_button)
        
        # Botón de configuración
        self.config_button = QPushButton("⚙️")
        self.config_button.setFixedWidth(40)
        self.config_button.clicked.connect(self.toggle_config)
        timer_layout.addWidget(self.config_button)
        
        scroll_layout.addLayout(timer_layout)
        
        # Opciones de canciones con imágenes de álbumes
        options_layout = QGridLayout()
        self.option_buttons = []
        
        for i in range(4):
            row, col = divmod(i, 2)
            option_group = QGroupBox(f"Opción {i+1}")
            option_layout = QHBoxLayout()  # Cambiado a horizontal para imagen + info
            
            # Imagen del álbum
            album_image = QLabel()
            album_image.setFixedSize(120, 120)
            album_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
            album_image.setText("Portada")
            album_image.setStyleSheet("border: 1px solid gray; background-color: lightgray;")
            option_layout.addWidget(album_image)
            
            # Información de la canción
            song_info = QVBoxLayout()
            song_label = QLabel("Título:")
            artist_label = QLabel("Artista:")
            album_label = QLabel("Álbum:")
            
            song_info.addWidget(song_label)
            song_info.addWidget(artist_label)
            song_info.addWidget(album_label)
            
            # Contenedor para la información de la canción
            info_container = QWidget()
            info_container.setLayout(song_info)
            option_layout.addWidget(info_container, 1)  # Dar más espacio a la info
            
            # Botón de selección
            select_button = QPushButton("Seleccionar")
            select_button.setProperty("option_id", i)
            select_button.clicked.connect(self.on_option_selected)
            
            # Guardar referencias para actualizar después
            select_button.song_label = song_label
            select_button.artist_label = artist_label
            select_button.album_label = album_label
            select_button.album_image = album_image
            
            option_layout.addWidget(select_button)
            option_group.setLayout(option_layout)
            option_group.setStyleSheet("QGroupBox { border: none; }")  # Hacer cajas invisibles
            
            options_layout.addWidget(option_group, row, col)
            self.option_buttons.append(select_button)
        
        scroll_layout.addLayout(options_layout)
        
        # Estadísticas
        stats_layout = QHBoxLayout()
        self.score_label = QLabel("Aciertos: 0")
        self.score_label.setFixedHeight(20)
        self.total_label = QLabel("Total: 0")
        self.total_label.setFixedHeight(20)
        self.accuracy_label = QLabel("Precisión: 0%")
        self.accuracy_label.setFixedHeight(20)
        
        stats_layout.addWidget(self.score_label)
        stats_layout.addWidget(self.total_label)
        stats_layout.addWidget(self.accuracy_label)
        
        scroll_layout.addLayout(stats_layout)
        
        # Finalizar configuración del scroll area
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)
        
        # Timer para countdown
        self.timer = QTimer()
        self.timer.setInterval(1000)  # 1 segundo
        self.timer.timeout.connect(self.update_countdown)
        
        # Timer para el quiz completo
        self.quiz_timer = QTimer()
        self.quiz_timer.timeout.connect(self.end_quiz)
        
        self.setLayout(main_layout)
        
        # Deshabilitar opciones al inicio
        self.enable_options(False)

    def connect_to_database(self):
        """Establece la conexión con la base de datos."""
        try:
            if not self.db_path:
                project_root = PROJECT_ROOT
                self.db_path = project_root / "data" / "music.db"
            
            # Verificar que el archivo de base de datos existe
            if not os.path.exists(self.db_path):
                raise FileNotFoundError(f"Base de datos no encontrada: {self.db_path}")
            
            self.conn = sqlite3.connect(str(self.db_path))
            self.cursor = self.conn.cursor()
            print(f"Conectado a la base de datos: {self.db_path}")
            
            # Verificar la estructura de la base de datos
            self.cursor.execute("PRAGMA table_info(songs)")
            columns = self.cursor.fetchall()
            required_columns = ["id", "title", "artist", "album", "file_path", "duration"]
            
            column_names = [column[1] for column in columns]
            missing_columns = [col for col in required_columns if col not in column_names]
            
            if missing_columns:
                raise Exception(f"La tabla 'songs' no tiene las columnas necesarias: {', '.join(missing_columns)}")
                
        except Exception as e:
            print(f"Error al conectar a la base de datos: {e}")
            self.show_error_message("Error de base de datos", 
                              f"No se pudo conectar a la base de datos: {e}")

    def toggle_config(self):
        """Muestra u oculta la sección de configuración."""
        self.config_group.setVisible(not self.config_group.isVisible())

    def toggle_quiz(self):
        """Alterna entre iniciar y detener el quiz."""
        if not self.game_active:
            self.start_quiz()
            self.toggle_button.setText("Detener Quiz")  # Actualizar texto del botón
        else:
            self.stop_quiz()
            self.toggle_button.setText("Iniciar Quiz")  # Esto ya está en stop_quiz

    def start_quiz(self):
        """Inicia el juego de quiz musical."""
        # Actualizar configuraciones desde los combobox
        self.quiz_duration_minutes = int(self.quiz_duration_combo.currentText().split()[0])
        self.song_duration_seconds = int(self.song_duration_combo.currentText().split()[0])
        self.pause_between_songs = int(self.pause_duration_combo.currentText().split()[0])
        
        # Reiniciar estadísticas
        self.score = 0
        self.total_played = 0
        self.update_stats_display()
        
        # Activar el juego
        self.game_active = True
        
        # Actualizar estados de botones - elegir una de estas opciones dependiendo de tu diseño:
        # Opción 1: Si usas botones separados de inicio y parada
        if hasattr(self, 'start_button') and hasattr(self, 'stop_button'):
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
        
        # Iniciar el primer turno
        self.show_next_question()
        
        # Programar el final del quiz
        total_duration_ms = self.quiz_duration_minutes * 60 * 1000
        self.quiz_timer.start(total_duration_ms)

    def stop_quiz(self):
        """Detiene el juego en curso."""
        self.game_active = False
        
        # Actualizar estados de botones - elegir una opción:
        # Opción 1: Si usas botones separados
        if hasattr(self, 'start_button') and hasattr(self, 'stop_button'):
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
        
        # Detener los timers
        self.timer.stop()
        self.quiz_timer.stop()
        
        # Detener la reproducción
        self.player.stop()
        
        # Deshabilitar opciones
        self.enable_options(False)
        
        # Restablecer la visualización
        self.countdown_label.setText("---")
        self.progress_bar.setValue(0)

    def end_quiz(self):
        """Finaliza el quiz cuando se acaba el tiempo total."""
        self.stop_quiz()
        
        # Mostrar resultados finales
        score_percent = 0 if self.total_played == 0 else (self.score / self.total_played) * 100
        msg = QMessageBox()
        msg.setWindowTitle("Quiz completado")
        msg.setText(f"¡Quiz completado!\n\nPuntuación: {self.score}/{self.total_played}\nPrecisión: {score_percent:.1f}%")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.exec()
        
        # Emitir señal de quiz completado
        self.quiz_completed.emit()


    def get_random_songs(self, count=4, max_retries=3):
        """Versión modificada que incorpora los filtros de sesión con la estructura correcta de la base de datos."""
        retries = 0
        while retries < max_retries:
            try:
                # Construir la consulta base
                query = """
                    SELECT s.id, s.title, s.artist, s.album, s.file_path, s.duration, 
                        a.album_art_path, s.track_number, s.album_art_path_denorm
                    FROM songs s
                    LEFT JOIN albums a ON s.album = a.name AND s.artist = (
                        SELECT name FROM artists WHERE id = a.artist_id
                    )
                    WHERE s.duration >= ? AND s.file_path IS NOT NULL
                """
                params = [self.min_song_duration]
                
                # Verificar si hay artistas excluidos
                excluded_artists = self.get_excluded_items("excluded_artists")
                if excluded_artists:
                    placeholders = ", ".join(["?" for _ in excluded_artists])
                    query += f" AND s.artist NOT IN ({placeholders})"
                    params.extend(excluded_artists)
                
                # Verificar si hay álbumes excluidos
                excluded_albums = self.get_excluded_items("excluded_albums")
                if excluded_albums:
                    placeholders = ", ".join(["?" for _ in excluded_albums])
                    query += f" AND s.album NOT IN ({placeholders})"
                    params.extend(excluded_albums)
                
                # Verificar si hay géneros excluidos
                excluded_genres = self.get_excluded_items("excluded_genres")
                if excluded_genres:
                    placeholders = ", ".join(["?" for _ in excluded_genres])
                    query += f" AND s.genre NOT IN ({placeholders})"
                    params.extend(excluded_genres)
                
                # Verificar si hay carpetas excluidas
                excluded_folders = self.get_excluded_items("excluded_folders")
                if excluded_folders:
                    folder_conditions = []
                    for folder in excluded_folders:
                        folder_conditions.append("s.file_path NOT LIKE ?")
                        params.append(f"{folder}%")
                    if folder_conditions:
                        query += f" AND {' AND '.join(folder_conditions)}"
                
                # Aplicar filtros de sesión si están activos
                if hasattr(self, 'session_filters') and self.session_filters:
                    session_filters = self.session_filters.get('filters', {})
                    
                    # Filtrar por artistas incluidos
                    included_artists = session_filters.get('Artistas', [])
                    if included_artists:
                        placeholders = ", ".join(["?" for _ in included_artists])
                        query += f" AND s.artist IN ({placeholders})"
                        params.extend(included_artists)
                    
                    # Filtrar por álbumes incluidos
                    included_albums = session_filters.get('Álbumes', [])
                    if included_albums:
                        placeholders = ", ".join(["?" for _ in included_albums])
                        query += f" AND s.album IN ({placeholders})"
                        params.extend(included_albums)
                    
                    # Filtrar por géneros incluidos
                    included_genres = session_filters.get('Géneros', [])
                    if included_genres:
                        placeholders = ", ".join(["?" for _ in included_genres])
                        query += f" AND s.genre IN ({placeholders})"
                        params.extend(included_genres)
                    
                    # Filtrar por carpetas incluidas
                    included_folders = session_filters.get('Carpetas', [])
                    if included_folders:
                        folder_conditions = []
                        for folder in included_folders:
                            folder_conditions.append("s.file_path LIKE ?")
                            params.append(f"{folder}%")
                        if folder_conditions:
                            query += f" AND ({' OR '.join(folder_conditions)})"
                
                # Agregar orden aleatorio y límite
                query += " ORDER BY RANDOM() LIMIT ?"
                params.append(count * 2)  # Obtener el doble para tener margen si algunos archivos no existen
                
                self.cursor.execute(query, params)
                candidates = self.cursor.fetchall()
                
                # Verificar que los archivos existen
                valid_songs = []
                for song in candidates:
                    if song[4] and os.path.exists(song[4]):
                        valid_songs.append(song)
                        if len(valid_songs) >= count:
                            break
                
                if len(valid_songs) >= count:
                    return valid_songs[:count]
                
                # Si no hay suficientes canciones válidas, intentar de nuevo con menos filtros
                retries += 1
                print(f"No se encontraron suficientes canciones válidas. Reintento {retries}/{max_retries}")
            except Exception as e:
                print(f"Error al obtener canciones aleatorias: {e}")
                retries += 1
        
        # Si llegamos aquí, no pudimos obtener suficientes canciones
        print("Error: No se pudieron obtener suficientes canciones válidas después de varios intentos")
        return []

    def load_album_art(self, album_art_path):
        """Carga la imagen de la portada del álbum para mostrarla en la UI."""
        if not album_art_path or not os.path.exists(album_art_path):
            # Intentar usar el campo album_art_path_denorm si está disponible
            if hasattr(self, 'current_song') and self.current_song and self.current_song[28]:
                album_art_path = self.current_song[28]
                if not os.path.exists(album_art_path):
                    return None
            else:
                return None
        
        try:
            pixmap = QPixmap(album_art_path)
            if not pixmap.isNull():
                return pixmap.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio)
            else:
                print(f"Error: Pixmap nulo para {album_art_path}")
        except Exception as e:
            print(f"Error al cargar portada del álbum: {e}")
        
        return None

    def show_next_question(self):
        """Muestra la siguiente pregunta del quiz."""
        if not self.game_active:
            return
            
        # Detener la reproducción anterior si existe
        self.player.stop()
        
        # Obtener las canciones aleatorias
        songs = self.get_random_songs(4)
        
        if not songs or len(songs) < 4:
            self.show_error_message("Error", "No hay suficientes canciones en la base de datos.")
            self.stop_quiz()
            return
            
        # Elegir una canción aleatoria como correcta
        self.current_correct_option = random.randint(0, 3)
        self.current_song = songs[self.current_correct_option]
        
        # Configurar las opciones
        for i, button in enumerate(self.option_buttons):
            song = songs[i]
            button.song_label.setText(f"Canción: {song[1]}")
            button.artist_label.setText(f"Artista: {song[2]}")
            button.album_label.setText(f"Álbum: {song[3]}")
            
            # Intentar cargar la portada del álbum desde album_art_path primero
            album_art = None
            if song[6]:  # album_art_path de la tabla albums
                album_art = self.load_album_art(song[6])
            
            # Si no funciona, intentar con album_art_path_denorm de la tabla songs
            if not album_art and len(song) > 8 and song[8]:
                album_art = self.load_album_art(song[8])
            
            if album_art:
                button.album_image.setPixmap(album_art)
                button.album_image.setText("")
            else:
                button.album_image.setText("Portada")
                button.album_image.setPixmap(QPixmap())
            
            # Restablecer el estilo
            button.setStyleSheet("")
            
        # Habilitar los botones
        self.enable_options(True)
        
        # Iniciar la reproducción de la canción correcta
        correct_song = songs[self.current_correct_option]
        self.current_song_path = correct_song[4]
        
        try:
            # Verificar que la ruta del archivo exista
            if not os.path.exists(self.current_song_path):
                print(f"Error: El archivo de audio no existe: {self.current_song_path}")
                raise FileNotFoundError(f"Archivo de audio no encontrado: {self.current_song_path}")
                
            # Determinar desde dónde empezar a reproducir la canción
            song_duration = correct_song[5]  # Duración en segundos
            if not song_duration or song_duration <= 0:
                song_duration = 60  # Valor predeterminado si la duración no es válida
                
            # Calcular los límites de reproducción
            start_from_beginning = random.random() < 0.3  # 30% de probabilidad de comenzar desde el principio
            avoid_last_seconds = min(15, int(song_duration * 0.1))  # Evitar los últimos 15 segundos o 10% de la canción
            
            # Si la canción tiene suficiente duración, elegir un punto aleatorio para comenzar
            if start_from_beginning or song_duration <= (self.song_duration_seconds + avoid_last_seconds):
                start_position = 0
            else:
                max_start = max(0, song_duration - self.song_duration_seconds - avoid_last_seconds)
                if max_start > 0:
                    start_position = random.randint(10, max_start)
                else:
                    start_position = 0
            
            # Configurar el reproductor
            source = QUrl.fromLocalFile(self.current_song_path)
            self.player.setSource(source)
            
            # Verificar si la fuente es válida antes de reproducir
            QTimer.singleShot(100, lambda: self.play_song_at_position(start_position))
        except Exception as e:
            print(f"Error al reproducir la canción: {e}")
            # Intentar con la siguiente pregunta si hay error
            QTimer.singleShot(500, self.show_next_question)
            return
            
        # Configurar el temporizador
        self.remaining_time = self.song_duration_seconds
        self.countdown_label.setText(str(self.remaining_time))
        self.progress_bar.setValue(100)
        
        # Iniciar la cuenta regresiva
        self.timer.start()

    def play_song_at_position(self, position_seconds):
        """Reproduce la canción desde una posición específica."""
        try:
            if self.player.mediaStatus() in [QMediaPlayer.MediaStatus.InvalidMedia, 
                                            QMediaPlayer.MediaStatus.NoMedia]:
                print(f"Error: Fuente de media inválida: {self.current_song_path}")
                # Intentar reproducir la siguiente canción
                QTimer.singleShot(500, self.show_next_question)
                return
                
            # Establecer la posición y reproducir
            self.player.setPosition(int(position_seconds * 1000))  # Convertir a milisegundos enteros
            self.player.play()
            
            # Verificar después de un breve retraso si la reproducción comenzó
            QTimer.singleShot(500, self.check_playback_started)
        except Exception as e:
            print(f"Error al establecer la posición de reproducción: {e}")
            QTimer.singleShot(500, self.show_next_question)


    def check_playback_started(self):
        """Verifica si la reproducción ha comenzado correctamente."""
        if self.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            print("Error: No se pudo iniciar la reproducción")
            # Intentar reproducir de nuevo
            self.player.play()
            
            # Si sigue sin funcionar después de otro intento, pasar a la siguiente pregunta
            QTimer.singleShot(1000, lambda: self.check_if_still_not_playing())

    def check_if_still_not_playing(self):
        """Comprueba si la canción sigue sin reproducirse después de un segundo intento."""
        if self.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            print("Error persistente: La canción no se puede reproducir después de varios intentos")
            QTimer.singleShot(500, self.show_next_question)



    def update_countdown(self):
        """Actualiza la cuenta atrás y el progreso."""
        if self.remaining_time > 0:
            self.remaining_time -= 1
            self.countdown_label.setText(str(self.remaining_time))
            
            # Actualizar barra de progreso
            progress_value = (self.remaining_time / self.song_duration_seconds) * 100
            self.progress_bar.setValue(int(progress_value))
            
            # Si hay poco tiempo, cambiar el color
            if self.remaining_time <= 5:
                self.countdown_label.setStyleSheet("color: red;")
            else:
                self.countdown_label.setStyleSheet("")
        else:
            # Se acabó el tiempo
            self.timer.stop()
            
            # Marcar como incorrecto (sin respuesta)
            self.total_played += 1
            self.update_stats_display()
            
            # Resaltar la opción correcta
            self.option_buttons[self.current_correct_option].setStyleSheet("background-color: green;")
            
            # Deshabilitar opciones
            self.enable_options(False)
            
            # Pausa antes de la siguiente pregunta
            QTimer.singleShot(self.pause_between_songs * 1000, self.show_next_question)

    def on_option_selected(self):
        """Maneja la selección de una opción por parte del usuario."""
        if not self.game_active:
            return
            
        # Obtener el botón que se presionó
        button = self.sender()
        selected_option = button.property("option_id")
        
        # Detener el timer
        self.timer.stop()
        
        # Actualizar estadísticas
        self.total_played += 1
        if selected_option == self.current_correct_option:
            self.score += 1
            button.setStyleSheet("background-color: green;")
        else:
            button.setStyleSheet("background-color: red;")
            # Mostrar la opción correcta
            self.option_buttons[self.current_correct_option].setStyleSheet("background-color: green;")
        
        self.update_stats_display()
        
        # Deshabilitar opciones
        self.enable_options(False)
        
        # Pausa antes de la siguiente pregunta
        QTimer.singleShot(self.pause_between_songs * 1000, self.show_next_question)

    def update_stats_display(self):
        """Actualiza los labels de estadísticas."""
        self.score_label.setText(f"Aciertos: {self.score}")
        self.total_label.setText(f"Total: {self.total_played}")
        
        accuracy = 0 if self.total_played == 0 else (self.score / self.total_played) * 100
        self.accuracy_label.setText(f"Precisión: {accuracy:.1f}%")

    def enable_options(self, enabled):
        """Habilita o deshabilita las opciones de respuesta."""
        for button in self.option_buttons:
            button.setEnabled(enabled)

    def show_error_message(self, title, message):
        """Muestra un mensaje de error."""
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.exec()

    def closeEvent(self, event):
        """Limpia los recursos al cerrar el módulo."""
        self.stop_quiz()
        if self.conn:
            self.conn.close()
        super().closeEvent(event)


    def show_artist_filter_dialog(self):
        """Muestra un diálogo para filtrar artistas con información de álbumes y sellos."""
        try:
            dialog = QDialog(self)
            dialog.setWindowTitle("Filtrar Artistas")
            dialog.setMinimumWidth(600)  # Ampliado para acomodar más columnas
            dialog.setMinimumHeight(500)
            
            layout = QVBoxLayout()
            
            # Añadir un buscador
            search_layout = QHBoxLayout()
            search_label = QLabel("Buscar:")
            search_edit = QLineEdit()
            search_edit.setPlaceholderText("Escribe para filtrar...")
            search_layout.addWidget(search_label)
            search_layout.addWidget(search_edit)
            layout.addLayout(search_layout)
            
            # Crear un widget de tabla para mostrar artistas, álbumes y sellos
            table = QTableWidget()
            table.setColumnCount(3)
            table.setHorizontalHeaderLabels(["Artista", "Álbumes", "Sellos"])
            table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
            table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
            
            # Obtener la lista de artistas
            self.cursor.execute("SELECT id, name FROM artists ORDER BY name")
            artists = self.cursor.fetchall()
            
            # Obtener artistas excluidos
            excluded_artists = self.get_excluded_items("excluded_artists")
            
            # Configurar el número de filas de la tabla
            table.setRowCount(len(artists))
            
            # Diccionario para mantener referencia a los checkboxes
            checkboxes = {}
            
            # Llenar la tabla con datos
            for row, (artist_id, artist_name) in enumerate(artists):
                # Crear widget para checkbox del artista
                checkbox_widget = QWidget()
                checkbox_layout = QHBoxLayout(checkbox_widget)
                checkbox_layout.setContentsMargins(5, 0, 0, 0)
                checkbox = QCheckBox(artist_name)
                checkbox.setChecked(artist_name in excluded_artists)
                checkbox_layout.addWidget(checkbox)
                checkbox_layout.addStretch()
                
                # Guardar referencia al checkbox
                checkboxes[artist_name] = checkbox
                
                # Añadir el widget con checkbox a la tabla
                table.setCellWidget(row, 0, checkbox_widget)
                
                # Obtener álbumes del artista
                self.cursor.execute("""
                    SELECT name FROM albums 
                    WHERE artist_id = ? 
                    ORDER BY year DESC, name
                """, (artist_id,))
                albums = self.cursor.fetchall()
                albums_text = ", ".join([album[0] for album in albums])
                
                # Añadir álbumes a la segunda columna
                albums_item = QTableWidgetItem(albums_text)
                albums_item.setFlags(albums_item.flags() & ~Qt.ItemIsEditable)
                table.setItem(row, 1, albums_item)
                
                # Obtener sellos discográficos del artista
                self.cursor.execute("""
                    SELECT DISTINCT label FROM albums 
                    WHERE artist_id = ? AND label IS NOT NULL AND label != ''
                    ORDER BY label
                """, (artist_id,))
                labels = self.cursor.fetchall()
                labels_text = ", ".join([label[0] for label in labels])
                
                # Añadir sellos a la tercera columna
                labels_item = QTableWidgetItem(labels_text)
                labels_item.setFlags(labels_item.flags() & ~Qt.ItemIsEditable)
                table.setItem(row, 2, labels_item)
            
            layout.addWidget(table)
            
            # Función para filtrar la tabla según el texto de búsqueda
            def filter_table(text):
                text = text.lower()
                for row in range(table.rowCount()):
                    artist_widget = table.cellWidget(row, 0)
                    if artist_widget:
                        checkbox = artist_widget.layout().itemAt(0).widget()
                        artist_name = checkbox.text()
                        
                        # También buscar en álbumes y sellos
                        albums_text = table.item(row, 1).text().lower() if table.item(row, 1) else ""
                        labels_text = table.item(row, 2).text().lower() if table.item(row, 2) else ""
                        
                        visible = (text in artist_name.lower() or 
                                text in albums_text or 
                                text in labels_text)
                        
                        table.setRowHidden(row, not visible)
            
            search_edit.textChanged.connect(filter_table)
            
            # Botones
            buttons_layout = QHBoxLayout()
            select_all_btn = QPushButton("Seleccionar Todos")
            deselect_all_btn = QPushButton("Deseleccionar Todos")
            save_btn = QPushButton("Guardar")
            cancel_btn = QPushButton("Cancelar")
            
            buttons_layout.addWidget(select_all_btn)
            buttons_layout.addWidget(deselect_all_btn)
            buttons_layout.addWidget(save_btn)
            buttons_layout.addWidget(cancel_btn)
            
            layout.addLayout(buttons_layout)
            dialog.setLayout(layout)
            
            # Conectar señales
            def select_all():
                for row in range(table.rowCount()):
                    if not table.isRowHidden(row):
                        widget = table.cellWidget(row, 0)
                        if widget:
                            checkbox = widget.layout().itemAt(0).widget()
                            checkbox.setChecked(True)
            
            def deselect_all():
                for row in range(table.rowCount()):
                    if not table.isRowHidden(row):
                        widget = table.cellWidget(row, 0)
                        if widget:
                            checkbox = widget.layout().itemAt(0).widget()
                            checkbox.setChecked(False)
            
            def save_changes():
                excluded = []
                for artist_name, checkbox in checkboxes.items():
                    if checkbox.isChecked():
                        excluded.append(artist_name)
                self.save_excluded_items("excluded_artists", excluded)
                dialog.accept()
            
            select_all_btn.clicked.connect(select_all)
            deselect_all_btn.clicked.connect(deselect_all)
            save_btn.clicked.connect(save_changes)
            cancel_btn.clicked.connect(dialog.reject)
            
            dialog.exec()
        except Exception as e:
            print(f"Error al mostrar el diálogo de filtrar artistas: {e}")
            self.show_error_message("Error", f"Error al mostrar el diálogo: {e}")

    def show_album_filter_dialog(self):
        """Muestra un diálogo para filtrar álbumes con información de artista, sello y año."""
        try:
            dialog = QDialog(self)
            dialog.setWindowTitle("Filtrar Álbumes")
            dialog.setMinimumWidth(700)
            dialog.setMinimumHeight(500)
            
            layout = QVBoxLayout()
            
            # Añadir un buscador
            search_layout = QHBoxLayout()
            search_label = QLabel("Buscar:")
            search_edit = QLineEdit()
            search_edit.setPlaceholderText("Escribe para filtrar...")
            search_layout.addWidget(search_label)
            search_layout.addWidget(search_edit)
            layout.addLayout(search_layout)
            
            # Crear un widget de tabla para mostrar álbumes, artistas, sellos y años
            table = QTableWidget()
            table.setColumnCount(4)
            table.setHorizontalHeaderLabels(["Álbum", "Artista", "Sello", "Año"])
            table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
            table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
            
            # Obtener la lista de álbumes con información adicional
            self.cursor.execute("""
                SELECT a.id, a.name, ar.name, a.label, a.year
                FROM albums a
                JOIN artists ar ON a.artist_id = ar.id
                ORDER BY a.name
            """)
            albums = self.cursor.fetchall()
            
            # Obtener álbumes excluidos
            excluded_albums = self.get_excluded_items("excluded_albums")
            
            # Configurar el número de filas de la tabla
            table.setRowCount(len(albums))
            
            # Diccionario para mantener referencia a los checkboxes
            checkboxes = {}
            
            # Llenar la tabla con datos
            for row, (album_id, album_name, artist_name, label, year) in enumerate(albums):
                # Crear widget para checkbox del álbum
                checkbox_widget = QWidget()
                checkbox_layout = QHBoxLayout(checkbox_widget)
                checkbox_layout.setContentsMargins(5, 0, 0, 0)
                checkbox = QCheckBox(album_name)
                checkbox.setChecked(album_name in excluded_albums)
                checkbox_layout.addWidget(checkbox)
                checkbox_layout.addStretch()
                
                # Guardar referencia al checkbox
                checkboxes[album_name] = checkbox
                
                # Añadir el widget con checkbox a la tabla
                table.setCellWidget(row, 0, checkbox_widget)
                
                # Añadir información del artista
                artist_item = QTableWidgetItem(artist_name or "")
                artist_item.setFlags(artist_item.flags() & ~Qt.ItemIsEditable)
                table.setItem(row, 1, artist_item)
                
                # Añadir información del sello
                label_item = QTableWidgetItem(label or "")
                label_item.setFlags(label_item.flags() & ~Qt.ItemIsEditable)
                table.setItem(row, 2, label_item)
                
                # Añadir información del año
                year_item = QTableWidgetItem(year or "")
                year_item.setFlags(year_item.flags() & ~Qt.ItemIsEditable)
                table.setItem(row, 3, year_item)
            
            layout.addWidget(table)
            
            # Función para filtrar la tabla según el texto de búsqueda
            def filter_table(text):
                text = text.lower()
                for row in range(table.rowCount()):
                    album_widget = table.cellWidget(row, 0)
                    if album_widget:
                        checkbox = album_widget.layout().itemAt(0).widget()
                        album_name = checkbox.text().lower()
                        
                        artist_text = table.item(row, 1).text().lower() if table.item(row, 1) else ""
                        label_text = table.item(row, 2).text().lower() if table.item(row, 2) else ""
                        year_text = table.item(row, 3).text().lower() if table.item(row, 3) else ""
                        
                        visible = (text in album_name or 
                                text in artist_text or 
                                text in label_text or 
                                text in year_text)
                        
                        table.setRowHidden(row, not visible)
            
            search_edit.textChanged.connect(filter_table)
            
            # Botones
            buttons_layout = QHBoxLayout()
            select_all_btn = QPushButton("Seleccionar Todos")
            deselect_all_btn = QPushButton("Deseleccionar Todos")
            save_btn = QPushButton("Guardar")
            cancel_btn = QPushButton("Cancelar")
            
            buttons_layout.addWidget(select_all_btn)
            buttons_layout.addWidget(deselect_all_btn)
            buttons_layout.addWidget(save_btn)
            buttons_layout.addWidget(cancel_btn)
            
            layout.addLayout(buttons_layout)
            dialog.setLayout(layout)
            
            # Conectar señales
            def select_all():
                for row in range(table.rowCount()):
                    if not table.isRowHidden(row):
                        widget = table.cellWidget(row, 0)
                        if widget:
                            checkbox = widget.layout().itemAt(0).widget()
                            checkbox.setChecked(True)
            
            def deselect_all():
                for row in range(table.rowCount()):
                    if not table.isRowHidden(row):
                        widget = table.cellWidget(row, 0)
                        if widget:
                            checkbox = widget.layout().itemAt(0).widget()
                            checkbox.setChecked(False)
            
            def save_changes():
                excluded = []
                for album_name, checkbox in checkboxes.items():
                    if checkbox.isChecked():
                        excluded.append(album_name)
                self.save_excluded_items("excluded_albums", excluded)
                dialog.accept()
            
            select_all_btn.clicked.connect(select_all)
            deselect_all_btn.clicked.connect(deselect_all)
            save_btn.clicked.connect(save_changes)
            cancel_btn.clicked.connect(dialog.reject)
            
            dialog.exec()
        except Exception as e:
            print(f"Error al mostrar el diálogo de filtrar álbumes: {e}")
            self.show_error_message("Error", f"Error al mostrar el diálogo: {e}")





    def show_genre_filter_dialog(self):
        """Muestra un diálogo para filtrar géneros con información de artistas y sellos."""
        try:
            dialog = QDialog(self)
            dialog.setWindowTitle("Filtrar Géneros")
            dialog.setMinimumWidth(700)
            dialog.setMinimumHeight(500)
            
            layout = QVBoxLayout()
            
            # Añadir un buscador
            search_layout = QHBoxLayout()
            search_label = QLabel("Buscar:")
            search_edit = QLineEdit()
            search_edit.setPlaceholderText("Escribe para filtrar...")
            search_layout.addWidget(search_label)
            search_layout.addWidget(search_edit)
            layout.addLayout(search_layout)
            
            # Crear un widget de tabla para mostrar géneros, artistas y sellos
            table = QTableWidget()
            table.setColumnCount(3)
            table.setHorizontalHeaderLabels(["Género", "Artistas", "Sellos"])
            table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
            table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
            
            # Obtener la lista de géneros
            self.cursor.execute("SELECT DISTINCT genre FROM songs WHERE genre IS NOT NULL AND genre != '' ORDER BY genre")
            genres = self.cursor.fetchall()
            
            # Obtener géneros excluidos
            excluded_genres = self.get_excluded_items("excluded_genres")
            
            # Configurar el número de filas de la tabla
            table.setRowCount(len(genres))
            
            # Diccionario para mantener referencia a los checkboxes
            checkboxes = {}
            
            # Llenar la tabla con datos
            for row, (genre,) in enumerate(genres):
                # Crear widget para checkbox del género
                checkbox_widget = QWidget()
                checkbox_layout = QHBoxLayout(checkbox_widget)
                checkbox_layout.setContentsMargins(5, 0, 0, 0)
                checkbox = QCheckBox(genre)
                checkbox.setChecked(genre in excluded_genres)
                checkbox_layout.addWidget(checkbox)
                checkbox_layout.addStretch()
                
                # Guardar referencia al checkbox
                checkboxes[genre] = checkbox
                
                # Añadir el widget con checkbox a la tabla
                table.setCellWidget(row, 0, checkbox_widget)
                
                # Obtener artistas de este género
                self.cursor.execute("""
                    SELECT DISTINCT artist 
                    FROM songs 
                    WHERE genre = ? 
                    ORDER BY artist
                """, (genre,))
                artists = self.cursor.fetchall()
                artists_text = ", ".join([artist[0] for artist in artists[:10]])
                if len(artists) > 10:
                    artists_text += f"... (+{len(artists) - 10} más)"
                
                # Añadir artistas a la segunda columna
                artists_item = QTableWidgetItem(artists_text)
                artists_item.setFlags(artists_item.flags() & ~Qt.ItemIsEditable)
                table.setItem(row, 1, artists_item)
                
                # Obtener sellos de este género
                self.cursor.execute("""
                    SELECT DISTINCT label 
                    FROM songs 
                    WHERE genre = ? AND label IS NOT NULL AND label != '' 
                    ORDER BY label
                """, (genre,))
                labels = self.cursor.fetchall()
                labels_text = ", ".join([label[0] for label in labels[:10]])
                if len(labels) > 10:
                    labels_text += f"... (+{len(labels) - 10} más)"
                
                # Añadir sellos a la tercera columna
                labels_item = QTableWidgetItem(labels_text)
                labels_item.setFlags(labels_item.flags() & ~Qt.ItemIsEditable)
                table.setItem(row, 2, labels_item)
            
            layout.addWidget(table)
            
            # Función para filtrar la tabla según el texto de búsqueda
            def filter_table(text):
                text = text.lower()
                for row in range(table.rowCount()):
                    genre_widget = table.cellWidget(row, 0)
                    if genre_widget:
                        checkbox = genre_widget.layout().itemAt(0).widget()
                        genre_name = checkbox.text().lower()
                        
                        artists_text = table.item(row, 1).text().lower() if table.item(row, 1) else ""
                        labels_text = table.item(row, 2).text().lower() if table.item(row, 2) else ""
                        
                        visible = (text in genre_name or 
                                text in artists_text or 
                                text in labels_text)
                        
                        table.setRowHidden(row, not visible)
            
            search_edit.textChanged.connect(filter_table)
            
            # Botones
            buttons_layout = QHBoxLayout()
            select_all_btn = QPushButton("Seleccionar Todos")
            deselect_all_btn = QPushButton("Deseleccionar Todos")
            save_btn = QPushButton("Guardar")
            cancel_btn = QPushButton("Cancelar")
            
            buttons_layout.addWidget(select_all_btn)
            buttons_layout.addWidget(deselect_all_btn)
            buttons_layout.addWidget(save_btn)
            buttons_layout.addWidget(cancel_btn)
            
            layout.addLayout(buttons_layout)
            dialog.setLayout(layout)
            
            # Conectar señales
            def select_all():
                for row in range(table.rowCount()):
                    if not table.isRowHidden(row):
                        widget = table.cellWidget(row, 0)
                        if widget:
                            checkbox = widget.layout().itemAt(0).widget()
                            checkbox.setChecked(True)
            
            def deselect_all():
                for row in range(table.rowCount()):
                    if not table.isRowHidden(row):
                        widget = table.cellWidget(row, 0)
                        if widget:
                            checkbox = widget.layout().itemAt(0).widget()
                            checkbox.setChecked(False)
            
            def save_changes():
                excluded = []
                for genre_name, checkbox in checkboxes.items():
                    if checkbox.isChecked():
                        excluded.append(genre_name)
                self.save_excluded_items("excluded_genres", excluded)
                dialog.accept()
            
            select_all_btn.clicked.connect(select_all)
            deselect_all_btn.clicked.connect(deselect_all)
            save_btn.clicked.connect(save_changes)
            cancel_btn.clicked.connect(dialog.reject)
            
            dialog.exec()
        except Exception as e:
            print(f"Error al mostrar el diálogo de filtrar géneros: {e}")
            self.show_error_message("Error", f"Error al mostrar el diálogo: {e}")


    def show_sellos_filter_dialog(self):
        """Muestra un diálogo para filtrar por sellos discográficos con información de artistas y álbumes."""
        try:
            dialog = QDialog(self)
            dialog.setWindowTitle("Filtrar por Sellos Discográficos")
            dialog.setMinimumWidth(700)
            dialog.setMinimumHeight(500)
            
            layout = QVBoxLayout()
            
            # Añadir un buscador
            search_layout = QHBoxLayout()
            search_label = QLabel("Buscar:")
            search_edit = QLineEdit()
            search_edit.setPlaceholderText("Escribe para filtrar...")
            search_layout.addWidget(search_label)
            search_layout.addWidget(search_edit)
            layout.addLayout(search_layout)
            
            # Crear pestañas para filtros positivos y negativos
            tabs = QTabWidget()
            
            # Crear widgets para ambas pestañas
            include_tab = QWidget()
            exclude_tab = QWidget()
            
            include_layout = QVBoxLayout(include_tab)
            exclude_layout = QVBoxLayout(exclude_tab)
            
            # Crear tablas para ambas pestañas
            include_table = QTableWidget()
            exclude_table = QTableWidget()
            
            for table in [include_table, exclude_table]:
                table.setColumnCount(3)
                table.setHorizontalHeaderLabels(["Sello", "Artistas", "Álbumes"])
                table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
                table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
                table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
            
            # Obtener la lista de sellos
            self.cursor.execute("""
                SELECT DISTINCT label 
                FROM albums 
                WHERE label IS NOT NULL AND label != '' 
                ORDER BY label
            """)
            labels = self.cursor.fetchall()
            
            # Obtener sellos incluidos y excluidos
            included_labels = self.get_included_items("included_labels")
            excluded_labels = self.get_excluded_items("excluded_labels")
            
            # Configurar el número de filas de las tablas
            include_table.setRowCount(len(labels))
            exclude_table.setRowCount(len(labels))
            
            # Diccionarios para mantener referencia a los checkboxes
            include_checkboxes = {}
            exclude_checkboxes = {}
            
            # Llenar las tablas con datos
            for row, (label,) in enumerate(labels):
                # Tabla de inclusión
                include_checkbox_widget = QWidget()
                include_checkbox_layout = QHBoxLayout(include_checkbox_widget)
                include_checkbox_layout.setContentsMargins(5, 0, 0, 0)
                include_checkbox = QCheckBox(label)
                include_checkbox.setChecked(label in included_labels)
                include_checkbox_layout.addWidget(include_checkbox)
                include_checkbox_layout.addStretch()
                
                include_checkboxes[label] = include_checkbox
                include_table.setCellWidget(row, 0, include_checkbox_widget)
                
                # Tabla de exclusión
                exclude_checkbox_widget = QWidget()
                exclude_checkbox_layout = QHBoxLayout(exclude_checkbox_widget)
                exclude_checkbox_layout.setContentsMargins(5, 0, 0, 0)
                exclude_checkbox = QCheckBox(label)
                exclude_checkbox.setChecked(label in excluded_labels)
                exclude_checkbox_layout.addWidget(exclude_checkbox)
                exclude_checkbox_layout.addStretch()
                
                exclude_checkboxes[label] = exclude_checkbox
                exclude_table.setCellWidget(row, 0, exclude_checkbox_widget)
                
                # Obtener artistas de este sello
                self.cursor.execute("""
                    SELECT DISTINCT ar.name 
                    FROM albums a
                    JOIN artists ar ON a.artist_id = ar.id
                    WHERE a.label = ? 
                    ORDER BY ar.name
                """, (label,))
                artists = self.cursor.fetchall()
                artists_text = ", ".join([artist[0] for artist in artists[:10]])
                if len(artists) > 10:
                    artists_text += f"... (+{len(artists) - 10} más)"
                
                # Añadir artistas a ambas tablas
                artists_item_include = QTableWidgetItem(artists_text)
                artists_item_include.setFlags(artists_item_include.flags() & ~Qt.ItemIsEditable)
                include_table.setItem(row, 1, artists_item_include)
                
                artists_item_exclude = QTableWidgetItem(artists_text)
                artists_item_exclude.setFlags(artists_item_exclude.flags() & ~Qt.ItemIsEditable)
                exclude_table.setItem(row, 1, artists_item_exclude)
                
                # Obtener álbumes de este sello
                self.cursor.execute("""
                    SELECT name 
                    FROM albums 
                    WHERE label = ? 
                    ORDER BY year DESC, name
                """, (label,))
                albums = self.cursor.fetchall()
                albums_text = ", ".join([album[0] for album in albums[:10]])
                if len(albums) > 10:
                    albums_text += f"... (+{len(albums) - 10} más)"
                
                # Añadir álbumes a ambas tablas
                albums_item_include = QTableWidgetItem(albums_text)
                albums_item_include.setFlags(albums_item_include.flags() & ~Qt.ItemIsEditable)
                include_table.setItem(row, 2, albums_item_include)
                
                albums_item_exclude = QTableWidgetItem(albums_text)
                albums_item_exclude.setFlags(albums_item_exclude.flags() & ~Qt.ItemIsEditable)
                exclude_table.setItem(row, 2, albums_item_exclude)
            
            # Añadir tablas a los layouts
            include_layout.addWidget(include_table)
            exclude_layout.addWidget(exclude_table)
            
            # Añadir pestañas al widget
            tabs.addTab(include_tab, "Incluir Sellos")
            tabs.addTab(exclude_tab, "Excluir Sellos")
            layout.addWidget(tabs)
            
            # Funciones para filtrar las tablas
            def filter_include_table(text):
                text = text.lower()
                for row in range(include_table.rowCount()):
                    label_widget = include_table.cellWidget(row, 0)
                    if label_widget:
                        checkbox = label_widget.layout().itemAt(0).widget()
                        label_name = checkbox.text().lower()
                        
                        artists_text = include_table.item(row, 1).text().lower() if include_table.item(row, 1) else ""
                        albums_text = include_table.item(row, 2).text().lower() if include_table.item(row, 2) else ""
                        
                        visible = (text in label_name or 
                                text in artists_text or 
                                text in albums_text)
                        
                        include_table.setRowHidden(row, not visible)
            
            def filter_exclude_table(text):
                text = text.lower()
                for row in range(exclude_table.rowCount()):
                    label_widget = exclude_table.cellWidget(row, 0)
                    if label_widget:
                        checkbox = label_widget.layout().itemAt(0).widget()
                        label_name = checkbox.text().lower()
                        
                        artists_text = exclude_table.item(row, 1).text().lower() if exclude_table.item(row, 1) else ""
                        albums_text = exclude_table.item(row, 2).text().lower() if exclude_table.item(row, 2) else ""
                        
                        visible = (text in label_name or 
                                text in artists_text or 
                                text in albums_text)
                        
                        exclude_table.setRowHidden(row, not visible)
            
            def filter_tables(text):
                current_index = tabs.currentIndex()
                if current_index == 0:
                    filter_include_table(text)
                else:
                    filter_exclude_table(text)
            
            search_edit.textChanged.connect(filter_tables)
            tabs.currentChanged.connect(lambda: filter_tables(search_edit.text()))
            
            # Botones
            buttons_layout = QHBoxLayout()
            select_all_btn = QPushButton("Seleccionar Todos")
            deselect_all_btn = QPushButton("Deseleccionar Todos")
            save_btn = QPushButton("Guardar")
            cancel_btn = QPushButton("Cancelar")
            
            buttons_layout.addWidget(select_all_btn)
            buttons_layout.addWidget(deselect_all_btn)
            buttons_layout.addWidget(save_btn)
            buttons_layout.addWidget(cancel_btn)
            
            layout.addLayout(buttons_layout)
            dialog.setLayout(layout)
            
            # Conectar señales
            for row in range(table.rowCount()):
                    if not table.isRowHidden(row):
                        widget = table.cellWidget(row, 0)
                        if widget:
                            checkbox = widget.layout().itemAt(0).widget()
                            checkbox.setChecked(True)
            
            def deselect_all():
                for row in range(table.rowCount()):
                    if not table.isRowHidden(row):
                        widget = table.cellWidget(row, 0)
                        if widget:
                            checkbox = widget.layout().itemAt(0).widget()
                            checkbox.setChecked(False)
            
            def save_changes():
                excluded = []
                for genre_name, checkbox in checkboxes.items():
                    if checkbox.isChecked():
                        excluded.append(genre_name)
                self.save_excluded_items("excluded_genres", excluded)
                dialog.accept()
            
            select_all_btn.clicked.connect(select_all)
            deselect_all_btn.clicked.connect(deselect_all)
            save_btn.clicked.connect(save_changes)
            cancel_btn.clicked.connect(dialog.reject)
            
            dialog.exec()
        except Exception as e:
            print(f"Error al mostrar el diálogo de filtrar géneros: {e}")
            self.show_error_message("Error", f"Error al mostrar el diálogo: {e}")


    def show_year_filter_dialog(self):
        """Muestra un diálogo para filtrar años/décadas con información de artistas y álbumes."""
        try:
            dialog = QDialog(self)
            dialog.setWindowTitle("Filtrar por Año/Década")
            dialog.setMinimumWidth(800)
            dialog.setMinimumHeight(600)
            
            layout = QVBoxLayout()
            
            # Selector de modo: Año o Década
            mode_layout = QHBoxLayout()
            mode_label = QLabel("Filtrar por:")
            mode_combo = QComboBox()
            mode_combo.addItems(["Década", "Año"])
            mode_layout.addWidget(mode_label)
            mode_layout.addWidget(mode_combo)
            layout.addLayout(mode_layout)
            
            # Añadir un buscador
            search_layout = QHBoxLayout()
            search_label = QLabel("Buscar:")
            search_edit = QLineEdit()
            search_edit.setPlaceholderText("Escribe para filtrar...")
            search_layout.addWidget(search_label)
            search_layout.addWidget(search_edit)
            layout.addLayout(search_layout)
            
            # Selector de tipo de filtro
            filter_type_layout = QHBoxLayout()
            filter_type_label = QLabel("Tipo de filtro:")
            filter_type_combo = QComboBox()
            filter_type_combo.addItems(["Incluir (Positivo)", "Excluir (Negativo)"])
            filter_type_layout.addWidget(filter_type_label)
            filter_type_layout.addWidget(filter_type_combo)
            layout.addLayout(filter_type_layout)
            
            # Crear un widget de tabla para mostrar años/décadas, artistas y álbumes
            table = QTableWidget()
            table.setColumnCount(3)
            table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
            table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
            
            # Función para actualizar la tabla según el modo seleccionado
            def update_table_data():
                if mode_combo.currentText() == "Década":
                    table.setHorizontalHeaderLabels(["Década", "Artistas", "Álbumes"])
                    load_decades_data()
                else:
                    table.setHorizontalHeaderLabels(["Año", "Artistas", "Álbumes"])
                    load_years_data()
            
            # Cargar datos de décadas
            def load_decades_data():
                # Obtener décadas de las canciones
                self.cursor.execute("""
                    SELECT DISTINCT CAST(SUBSTR(album_year, 1, 3) || '0' AS TEXT) AS decade
                    FROM songs 
                    WHERE album_year IS NOT NULL AND album_year != '' AND LENGTH(album_year) >= 4
                    ORDER BY decade
                """)
                decades = self.cursor.fetchall()
                
                # Obtener décadas incluidas o excluidas según el tipo de filtro
                filter_type = "included_decades" if filter_type_combo.currentText() == "Incluir (Positivo)" else "excluded_decades"
                filtered_decades = self.get_excluded_items(filter_type)
                
                # Configurar el número de filas de la tabla
                table.setRowCount(len(decades))
                
                # Diccionario para mantener referencia a los checkboxes
                checkboxes = {}
                
                # Llenar la tabla con datos
                for row, (decade,) in enumerate(decades):
                    # Crear widget para checkbox de la década
                    checkbox_widget = QWidget()
                    checkbox_layout = QHBoxLayout(checkbox_widget)
                    checkbox_layout.setContentsMargins(5, 0, 0, 0)
                    checkbox = QCheckBox(f"{decade}s")
                    checkbox.setChecked(decade in filtered_decades)
                    checkbox_layout.addWidget(checkbox)
                    checkbox_layout.addStretch()
                    
                    # Guardar referencia al checkbox
                    checkboxes[decade] = checkbox
                    
                    # Añadir el widget con checkbox a la tabla
                    table.setCellWidget(row, 0, checkbox_widget)
                    
                    # Obtener artistas de esta década
                    self.cursor.execute("""
                        SELECT DISTINCT artist 
                        FROM songs 
                        WHERE SUBSTR(album_year, 1, 3) || '0' = ? 
                        ORDER BY artist
                    """, (decade,))
                    artists = self.cursor.fetchall()
                    artists_text = ", ".join([artist[0] for artist in artists[:10]])
                    if len(artists) > 10:
                        artists_text += f"... (+{len(artists) - 10} más)"
                    
                    # Añadir artistas a la segunda columna
                    artists_item = QTableWidgetItem(artists_text)
                    artists_item.setFlags(artists_item.flags() & ~Qt.ItemIsEditable)
                    table.setItem(row, 1, artists_item)
                    
                    # Obtener álbumes de esta década
                    self.cursor.execute("""
                        SELECT DISTINCT album 
                        FROM songs 
                        WHERE SUBSTR(album_year, 1, 3) || '0' = ? AND album IS NOT NULL AND album != '' 
                        ORDER BY album
                    """, (decade,))
                    albums = self.cursor.fetchall()
                    albums_text = ", ".join([album[0] for album in albums[:10]])
                    if len(albums) > 10:
                        albums_text += f"... (+{len(albums) - 10} más)"
                    
                    # Añadir álbumes a la tercera columna
                    albums_item = QTableWidgetItem(albums_text)
                    albums_item.setFlags(albums_item.flags() & ~Qt.ItemIsEditable)
                    table.setItem(row, 2, albums_item)
                
                return checkboxes
            
            # Cargar datos de años
            def load_years_data():
                # Obtener años de las canciones
                self.cursor.execute("""
                    SELECT DISTINCT album_year
                    FROM songs 
                    WHERE album_year IS NOT NULL AND album_year != '' AND LENGTH(album_year) >= 4
                    ORDER BY album_year
                """)
                years = self.cursor.fetchall()
                
                # Obtener años incluidos o excluidos según el tipo de filtro
                filter_type = "included_years" if filter_type_combo.currentText() == "Incluir (Positivo)" else "excluded_years"
                filtered_years = self.get_excluded_items(filter_type)
                
                # Configurar el número de filas de la tabla
                table.setRowCount(len(years))
                
                # Diccionario para mantener referencia a los checkboxes
                checkboxes = {}
                
                # Llenar la tabla con datos
                for row, (year,) in enumerate(years):
                    # Crear widget para checkbox del año
                    checkbox_widget = QWidget()
                    checkbox_layout = QHBoxLayout(checkbox_widget)
                    checkbox_layout.setContentsMargins(5, 0, 0, 0)
                    checkbox = QCheckBox(year)
                    checkbox.setChecked(year in filtered_years)
                    checkbox_layout.addWidget(checkbox)
                    checkbox_layout.addStretch()
                    
                    # Guardar referencia al checkbox
                    checkboxes[year] = checkbox
                    
                    # Añadir el widget con checkbox a la tabla
                    table.setCellWidget(row, 0, checkbox_widget)
                    
                    # Obtener artistas de este año
                    self.cursor.execute("""
                        SELECT DISTINCT artist 
                        FROM songs 
                        WHERE album_year = ? 
                        ORDER BY artist
                    """, (year,))
                    artists = self.cursor.fetchall()
                    artists_text = ", ".join([artist[0] for artist in artists[:10]])
                    if len(artists) > 10:
                        artists_text += f"... (+{len(artists) - 10} más)"
                    
                    # Añadir artistas a la segunda columna
                    artists_item = QTableWidgetItem(artists_text)
                    artists_item.setFlags(artists_item.flags() & ~Qt.ItemIsEditable)
                    table.setItem(row, 1, artists_item)
                    
                    # Obtener álbumes de este año
                    self.cursor.execute("""
                        SELECT DISTINCT album 
                        FROM songs 
                        WHERE album_year = ? AND album IS NOT NULL AND album != '' 
                        ORDER BY album
                    """, (year,))
                    albums = self.cursor.fetchall()
                    albums_text = ", ".join([album[0] for album in albums[:10]])
                    if len(albums) > 10:
                        albums_text += f"... (+{len(albums) - 10} más)"
                    
                    # Añadir álbumes a la tercera columna
                    albums_item = QTableWidgetItem(albums_text)
                    albums_item.setFlags(albums_item.flags() & ~Qt.ItemIsEditable)
                    table.setItem(row, 2, albums_item)
                
                return checkboxes
            
            layout.addWidget(table)
            
            # Variables para mantener los checkboxes
            decade_checkboxes = {}
            year_checkboxes = {}
            current_checkboxes = {}
            
            # Función para filtrar la tabla según el texto de búsqueda
            def filter_table(text):
                text = text.lower()
                for row in range(table.rowCount()):
                    period_widget = table.cellWidget(row, 0)
                    if period_widget:
                        checkbox = period_widget.layout().itemAt(0).widget()
                        period_name = checkbox.text().lower()
                        
                        artists_text = table.item(row, 1).text().lower() if table.item(row, 1) else ""
                        albums_text = table.item(row, 2).text().lower() if table.item(row, 2) else ""
                        
                        visible = (text in period_name or 
                                text in artists_text or 
                                text in albums_text)
                        
                        table.setRowHidden(row, not visible)
            
            search_edit.textChanged.connect(filter_table)
            
            # Función para actualizar el tipo de filtro
            def update_filter_type():
                nonlocal current_checkboxes
                update_table_data()
            
            filter_type_combo.currentIndexChanged.connect(update_filter_type)
            
            # Función para cargar los datos según el modo seleccionado
            def update_mode():
                nonlocal current_checkboxes
                
                # Guardar los datos actuales si hay alguno
                if current_checkboxes:
                    save_current_state()
                
                update_table_data()
            
            mode_combo.currentIndexChanged.connect(update_mode)
            
            # Botones
            buttons_layout = QHBoxLayout()
            select_all_btn = QPushButton("Seleccionar Todos")
            deselect_all_btn = QPushButton("Deseleccionar Todos")
            save_btn = QPushButton("Guardar")
            cancel_btn = QPushButton("Cancelar")
            
            buttons_layout.addWidget(select_all_btn)
            buttons_layout.addWidget(deselect_all_btn)
            buttons_layout.addWidget(save_btn)
            buttons_layout.addWidget(cancel_btn)
            
            layout.addLayout(buttons_layout)
            dialog.setLayout(layout)
            
            # Conectar señales
            def select_all():
                for row in range(table.rowCount()):
                    if not table.isRowHidden(row):
                        widget = table.cellWidget(row, 0)
                        if widget:
                            checkbox = widget.layout().itemAt(0).widget()
                            checkbox.setChecked(True)
            
            def deselect_all():
                for row in range(table.rowCount()):
                    if not table.isRowHidden(row):
                        widget = table.cellWidget(row, 0)
                        if widget:
                            checkbox = widget.layout().itemAt(0).widget()
                            checkbox.setChecked(False)
            
            def save_current_state():
                selected = []
                
                # Determinar qué tipo de filtro estamos guardando
                is_decade = mode_combo.currentText() == "Década"
                is_positive = filter_type_combo.currentText() == "Incluir (Positivo)"
                
                filter_key = ""
                if is_decade and is_positive:
                    filter_key = "included_decades"
                elif is_decade and not is_positive:
                    filter_key = "excluded_decades"
                elif not is_decade and is_positive:
                    filter_key = "included_years"
                else:
                    filter_key = "excluded_years"
                
                # Guardar los elementos seleccionados
                for period, checkbox in current_checkboxes.items():
                    if checkbox.isChecked():
                        selected.append(period)
                
                self.save_excluded_items(filter_key, selected)
            
            def save_changes():
                save_current_state()
                dialog.accept()
            
            select_all_btn.clicked.connect(select_all)
            deselect_all_btn.clicked.connect(deselect_all)
            save_btn.clicked.connect(save_changes)
            cancel_btn.clicked.connect(dialog.reject)
            
            # Cargar datos iniciales
            if mode_combo.currentText() == "Década":
                current_checkboxes = load_decades_data()
            else:
                current_checkboxes = load_years_data()
            
            dialog.exec()
        except Exception as e:
            print(f"Error al mostrar el diálogo de filtrar por año/década: {e}")
            self.show_error_message("Error", f"Error al mostrar el diálogo: {e}")



    def get_excluded_items(self, table_name):
        """Obtiene los elementos excluidos de la base de datos."""
        try:
            # Verificar si la tabla existe
            self.cursor.execute(f"""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='{table_name}'
            """)
            if not self.cursor.fetchone():
                return []
            
            # Obtener los elementos
            self.cursor.execute(f"SELECT name FROM {table_name}")
            items = self.cursor.fetchall()
            return [item[0] for item in items]
        except Exception as e:
            print(f"Error al obtener elementos excluidos de {table_name}: {e}")
            return []


    def show_session_filter_dialog(self):
        """Muestra un diálogo para configurar filtros de sesión temporales."""
        try:
            dialog = QDialog(self)
            dialog.setWindowTitle("Filtros de Sesión")
            dialog.setMinimumWidth(450)
            dialog.setMinimumHeight(550)
            
            layout = QVBoxLayout()
            
            # Selector de tipo de filtro
            filter_type_layout = QHBoxLayout()
            filter_type_label = QLabel("Tipo de filtro:")
            filter_type_combo = QComboBox()
            filter_type_combo.addItems(["Artistas", "Álbumes", "Géneros", "Carpetas"])
            filter_type_layout.addWidget(filter_type_label)
            filter_type_layout.addWidget(filter_type_combo)
            layout.addLayout(filter_type_layout)
            
            # Añadir un buscador
            search_layout = QHBoxLayout()
            search_label = QLabel("Buscar:")
            search_edit = QLineEdit()
            search_edit.setPlaceholderText("Escribe para filtrar...")
            search_layout.addWidget(search_label)
            search_layout.addWidget(search_edit)
            layout.addLayout(search_layout)
            
            # Crear una lista con checkboxes
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll_content = QWidget()
            checkbox_layout = QVBoxLayout(scroll_content)
            
            # Variables para almacenar los checkboxes por categoría
            all_checkboxes = {
                "Artistas": {},
                "Álbumes": {},
                "Géneros": {},
                "Carpetas": {}
            }
            
            # Obtener elementos para cada categoría
            # Artistas
            self.cursor.execute("SELECT name FROM artists ORDER BY name")
            artists = self.cursor.fetchall()
            for artist in artists:
                artist_name = artist[0]
                checkbox = QCheckBox(artist_name)
                checkbox.setVisible(False)  # Inicialmente oculto
                checkbox_layout.addWidget(checkbox)
                all_checkboxes["Artistas"][artist_name] = checkbox
                
            # Álbumes
            self.cursor.execute("SELECT name FROM albums ORDER BY name")
            albums = self.cursor.fetchall()
            for album in albums:
                album_name = album[0]
                checkbox = QCheckBox(album_name)
                checkbox.setVisible(False)  # Inicialmente oculto
                checkbox_layout.addWidget(checkbox)
                all_checkboxes["Álbumes"][album_name] = checkbox
                
            # Géneros
            self.cursor.execute("SELECT name FROM genres ORDER BY name")
            genres = self.cursor.fetchall()
            if not genres:
                self.cursor.execute("SELECT DISTINCT genre FROM songs WHERE genre IS NOT NULL ORDER BY genre")
                genres = self.cursor.fetchall()
            for genre in genres:
                genre_name = genre[0]
                if genre_name:
                    checkbox = QCheckBox(genre_name)
                    checkbox.setVisible(False)  # Inicialmente oculto
                    checkbox_layout.addWidget(checkbox)
                    all_checkboxes["Géneros"][genre_name] = checkbox
                    
            # Carpetas
            self.cursor.execute("""
                SELECT DISTINCT folder_path FROM albums 
                WHERE folder_path IS NOT NULL 
                ORDER BY folder_path
            """)
            folders = self.cursor.fetchall()
            for folder in folders:
                folder_path = folder[0]
                if folder_path:
                    checkbox = QCheckBox(folder_path)
                    checkbox.setVisible(False)  # Inicialmente oculto
                    checkbox_layout.addWidget(checkbox)
                    all_checkboxes["Carpetas"][folder_path] = checkbox
            
            scroll_content.setLayout(checkbox_layout)
            scroll.setWidget(scroll_content)
            layout.addWidget(scroll)
            
            # Función para mostrar los checkboxes correspondientes al tipo seleccionado
            def update_visible_checkboxes():
                selected_type = filter_type_combo.currentText()
                search_text = search_edit.text().lower()
                
                # Ocultar todos los checkboxes
                for category in all_checkboxes.values():
                    for checkbox in category.values():
                        checkbox.setVisible(False)
                
                # Mostrar solo los del tipo seleccionado que coincidan con la búsqueda
                for item_name, checkbox in all_checkboxes[selected_type].items():
                    checkbox.setVisible(search_text in item_name.lower())
            
            filter_type_combo.currentTextChanged.connect(update_visible_checkboxes)
            search_edit.textChanged.connect(update_visible_checkboxes)
            
            # Mostrar los checkboxes iniciales (artistas por defecto)
            update_visible_checkboxes()
            
            # Área para nombre de sesión
            session_layout = QHBoxLayout()
            session_label = QLabel("Nombre de la sesión:")
            session_edit = QLineEdit()
            session_edit.setPlaceholderText("Mi sesión personalizada")
            session_layout.addWidget(session_label)
            session_layout.addWidget(session_edit)
            layout.addLayout(session_layout)
            
            # Botones de operaciones de sesión
            session_ops_layout = QHBoxLayout()
            save_session_btn = QPushButton("Guardar Sesión")
            load_session_btn = QPushButton("Cargar Sesión")
            session_ops_layout.addWidget(save_session_btn)
            session_ops_layout.addWidget(load_session_btn)
            layout.addLayout(session_ops_layout)
            
            # Botones de acciones
            buttons_layout = QHBoxLayout()
            select_all_btn = QPushButton("Seleccionar Todos")
            deselect_all_btn = QPushButton("Deseleccionar Todos")
            apply_btn = QPushButton("Aplicar")
            cancel_btn = QPushButton("Cancelar")
            
            buttons_layout.addWidget(select_all_btn)
            buttons_layout.addWidget(deselect_all_btn)
            buttons_layout.addWidget(apply_btn)
            buttons_layout.addWidget(cancel_btn)
            
            layout.addLayout(buttons_layout)
            dialog.setLayout(layout)
            
            # Conectar señales
            def select_all():
                selected_type = filter_type_combo.currentText()
                for checkbox in all_checkboxes[selected_type].values():
                    if checkbox.isVisible():
                        checkbox.setChecked(True)
            
            def deselect_all():
                selected_type = filter_type_combo.currentText()
                for checkbox in all_checkboxes[selected_type].values():
                    if checkbox.isVisible():
                        checkbox.setChecked(False)
            
            def apply_filters():
                # Guardar los filtros de sesión
                session_filters = {
                    "name": session_edit.text() or "Sesión temporal",
                    "filters": {}
                }
                
                for filter_type, checkboxes in all_checkboxes.items():
                    session_filters["filters"][filter_type] = [
                        item for item, checkbox in checkboxes.items() 
                        if checkbox.isChecked()
                    ]
                
                # Almacenar en el objeto
                self.session_filters = session_filters
                # Aplicar los filtros inmediatamente
                self.apply_session_filters()
                dialog.accept()
            
            def save_session():
                # Primero recopilar los filtros seleccionados
                session_name = session_edit.text() or "Sesión temporal"
                session_data = {
                    "name": session_name,
                    "filters": {}
                }
                
                for filter_type, checkboxes in all_checkboxes.items():
                    session_data["filters"][filter_type] = [
                        item for item, checkbox in checkboxes.items() 
                        if checkbox.isChecked()
                    ]
                
                # Guardar en un archivo JSON
                self.save_session_to_file(session_data)
            
            def load_session():
                # Cargar desde un archivo JSON
                session_data = self.load_session_from_file()
                if not session_data:
                    return
                
                # Actualizar la UI con los filtros cargados
                session_edit.setText(session_data.get("name", "Sesión cargada"))
                
                # Limpiar todas las selecciones actuales
                for category in all_checkboxes.values():
                    for checkbox in category.values():
                        checkbox.setChecked(False)
                
                # Marcar las selecciones según los datos cargados
                loaded_filters = session_data.get("filters", {})
                for filter_type, items in loaded_filters.items():
                    if filter_type in all_checkboxes:
                        for item in items:
                            if item in all_checkboxes[filter_type]:
                                all_checkboxes[filter_type][item].setChecked(True)
            
            select_all_btn.clicked.connect(select_all)
            deselect_all_btn.clicked.connect(deselect_all)
            apply_btn.clicked.connect(apply_filters)
            save_session_btn.clicked.connect(save_session)
            load_session_btn.clicked.connect(load_session)
            cancel_btn.clicked.connect(dialog.reject)
            
            dialog.exec()
        except Exception as e:
            print(f"Error al mostrar el diálogo de filtros de sesión: {e}")
            self.show_error_message("Error", f"Error al mostrar el diálogo: {e}")

    def save_session_to_file(self, session_data):
        """Guarda los filtros de sesión en un archivo JSON."""
        try:
            from PyQt6.QtWidgets import QFileDialog
            import json
            
            # Obtener la ubicación donde guardar el archivo
            file_path, _ = QFileDialog.getSaveFileName(
                self, 
                "Guardar Sesión", 
                str(Path.home()), 
                "Archivos JSON (*.json)"
            )
            
            if not file_path:
                return
            
            # Añadir la extensión .json si no está
            if not file_path.endswith('.json'):
                file_path += '.json'
            
            # Guardar los datos en el archivo
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, ensure_ascii=False, indent=4)
            
            self.show_info_message("Sesión guardada", f"La sesión se ha guardado correctamente en: {file_path}")
        except Exception as e:
            print(f"Error al guardar la sesión: {e}")
            self.show_error_message("Error", f"Error al guardar la sesión: {e}")

    def load_session_from_file(self):
        """Carga los filtros de sesión desde un archivo JSON."""
        try:
            from PyQt6.QtWidgets import QFileDialog
            import json
            
            # Solicitar la ubicación del archivo a cargar
            file_path, _ = QFileDialog.getOpenFileName(
                self, 
                "Cargar Sesión", 
                str(Path.home()), 
                "Archivos JSON (*.json)"
            )
            
            if not file_path:
                return None
            
            # Cargar los datos del archivo
            with open(file_path, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            self.show_info_message("Sesión cargada", f"La sesión '{session_data.get('name', 'sin nombre')}' se ha cargado correctamente")
            return session_data
        except Exception as e:
            print(f"Error al cargar la sesión: {e}")
            self.show_error_message("Error", f"Error al cargar la sesión: {e}")
            return None

    def apply_session_filters(self):
        """Aplica los filtros de sesión actual al obtener canciones."""
        if hasattr(self, 'session_filters') and self.session_filters:
            # Mostrar un indicador visual de que hay filtros de sesión activos
            self.update_session_filter_indicator(True)
        else:
            self.update_session_filter_indicator(False)

    def update_session_filter_indicator(self, is_active):
        """Actualiza el indicador visual de filtros de sesión activos."""
        if not hasattr(self, 'session_filter_indicator'):
            # Crear el indicador si no existe
            self.session_filter_indicator = QLabel("⭐ Filtros de sesión activos")
            self.session_filter_indicator.setStyleSheet("color: #FFD700; font-weight: bold;")
            
            # Agregarlo a un layout existente (usar el mismo layout donde están los labels de estadísticas)
            # Asumiendo que hay un stats_layout donde están score_label, total_label, etc.
            stats_layout = self.score_label.parent().layout()
            if stats_layout:
                stats_layout.addWidget(self.session_filter_indicator)
        
        # Mostrar u ocultar el indicador
        self.session_filter_indicator.setVisible(is_active)

    def clear_session_filters(self):
        """Limpia los filtros de sesión actuales."""
        self.session_filters = None
        self.update_session_filter_indicator(False)
        self.show_info_message("Filtros eliminados", "Los filtros de sesión han sido eliminados")

    def show_info_message(self, title, message):
        """Muestra un mensaje informativo."""
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.exec()



    def show_folder_filter_dialog(self):
        """Muestra un diálogo para filtrar carpetas de álbumes."""
        try:
            dialog = QDialog(self)
            dialog.setWindowTitle("Filtrar Carpetas")
            dialog.setMinimumWidth(400)
            dialog.setMinimumHeight(500)
            
            layout = QVBoxLayout()
            
            # Añadir un buscador
            search_layout = QHBoxLayout()
            search_label = QLabel("Buscar:")
            search_edit = QLineEdit()
            search_edit.setPlaceholderText("Escribe para filtrar...")
            search_layout.addWidget(search_label)
            search_layout.addWidget(search_edit)
            layout.addLayout(search_layout)
            
            # Crear una lista con checkboxes
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll_content = QWidget()
            checkbox_layout = QVBoxLayout(scroll_content)
            
            # Obtener la lista de carpetas únicas
            self.cursor.execute("""
                SELECT DISTINCT folder_path FROM albums 
                WHERE folder_path IS NOT NULL 
                ORDER BY folder_path
            """)
            folders = self.cursor.fetchall()
            
            # Obtener carpetas excluidas
            excluded_folders = self.get_excluded_items("excluded_folders")
            
            checkboxes = {}
            for folder in folders:
                folder_path = folder[0]
                if folder_path:  # Asegurarse de que no es None
                    checkbox = QCheckBox(folder_path)
                    checkbox.setChecked(folder_path in excluded_folders)
                    checkbox_layout.addWidget(checkbox)
                    checkboxes[folder_path] = checkbox
            
            scroll_content.setLayout(checkbox_layout)
            scroll.setWidget(scroll_content)
            layout.addWidget(scroll)
            
            # Conectar el buscador para filtrar los checkboxes
            def filter_folders(text):
                text = text.lower()
                for folder_path, checkbox in checkboxes.items():
                    checkbox.setVisible(text in folder_path.lower())
            
            search_edit.textChanged.connect(filter_folders)
            
            # Botones
            buttons_layout = QHBoxLayout()
            select_all_btn = QPushButton("Seleccionar Todos")
            deselect_all_btn = QPushButton("Deseleccionar Todos")
            save_btn = QPushButton("Guardar")
            cancel_btn = QPushButton("Cancelar")
            
            buttons_layout.addWidget(select_all_btn)
            buttons_layout.addWidget(deselect_all_btn)
            buttons_layout.addWidget(save_btn)
            buttons_layout.addWidget(cancel_btn)
            
            layout.addLayout(buttons_layout)
            dialog.setLayout(layout)
            
            # Conectar señales
            def select_all():
                for checkbox in checkboxes.values():
                    if checkbox.isVisible():
                        checkbox.setChecked(True)
            
            def deselect_all():
                for checkbox in checkboxes.values():
                    if checkbox.isVisible():
                        checkbox.setChecked(False)
            
            def save_changes():
                excluded = [folder for folder, checkbox in checkboxes.items() if checkbox.isChecked()]
                self.save_excluded_items("excluded_folders", excluded)
                dialog.accept()
            
            select_all_btn.clicked.connect(select_all)
            deselect_all_btn.clicked.connect(deselect_all)
            save_btn.clicked.connect(save_changes)
            cancel_btn.clicked.connect(dialog.reject)
            
            dialog.exec()
        except Exception as e:
            print(f"Error al mostrar el diálogo de filtrar carpetas: {e}")
            self.show_error_message("Error", f"Error al mostrar el diálogo: {e}")