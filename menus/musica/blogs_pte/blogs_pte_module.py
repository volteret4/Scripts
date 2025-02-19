
#!/usr/bin/env python
#
# Script Name: menu_blogs.py
# Description: Crean un menu, con un listado de blogs, y unas playlists mensuales de cada unno de ellos, para reproducir en mpv.
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# TODO:     QUIERO AÑADIR MAS WIDGETS, 
#           Y LA POSIBILIDAD DE CREAR UNA LISTA DE POSTS/PAGINAS DE LAS QUE CREAR UNA PLAYLIST A GUARDAR EN LA CARPETA LOCAL
#
# Notes:
#   Dependencies:  - python3, tkinter
#                  - mpv
#                  - servidor freshrss y categoria blog creada en el.
#
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QLabel,
    QProgressBar, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QScrollArea
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from base_module import BaseModule, THEME
import logging
import os
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import re
import requests
from typing import List, Dict
from urllib.parse import quote
from dotenv import load_dotenv
import asyncio

load_dotenv()

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def clean_youtube_url(url):
    """Limpia y normaliza URLs de YouTube"""
    # Eliminar parámetros innecesarios
    if 'youtube.com/watch' in url:
        video_id = re.search(r'v=([^&]+)', url)
        if video_id:
            return f'https://youtube.com/watch?v={video_id.group(1)}'
    elif 'youtu.be/' in url:
        video_id = url.split('/')[-1].split('?')[0]
        return f'https://youtube.com/watch?v={video_id}'
    elif 'youtube.com/embed/' in url:
        video_id = url.split('/')[-1].split('?')[0]
        return f'https://youtube.com/watch?v={video_id}'
    return url

def extract_bandcamp_id(url):
    """Extrae y normaliza URLs de Bandcamp"""
    # Asegurarse de que la URL es completa
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url.lstrip('/')
    return url

def extract_music_urls(url):
    """
    Extrae las URLs de música (Bandcamp, SoundCloud, YouTube) del contenido HTML de la URL dada.
    """
    try:
        response = requests.get(url)
        content = response.text
        music_patterns = [
            r'"\b(https?://[a-zA-Z0-9-]+\.bandcamp\.com)\b"'
            r'(https?://(?:www\.)?soundcloud\.com/[^\s"\'<>]+)',
            r'(https?://(?:www\.)?youtube\.com/embed/[^\s"\'<>]+)',
            r'(https?://(?:www\.)?youtube\.com/watch\?[^\s"\'<>]+)',
            r'(https?://(?:www\.)?youtu\.be/[^\s"\'<>]+)'
        ]
        music_urls = set()
        
        for pattern in music_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                extracted_url = match[0] if isinstance(match, tuple) else match
                if 'bandcamp.com' in extracted_url:
                    if extracted_url.startswith('//'):
                        extracted_url = 'https:' + extracted_url
                    extracted_url = extract_bandcamp_id(extracted_url)
                else:
                    extracted_url = clean_youtube_url(extracted_url)
                music_urls.add(extracted_url)
                
        return list(music_urls)
    except Exception as e:
        print(f"Error al extraer URLs: {e}")
        return []

class TitleExtractorWorker(QThread):
    """Worker thread for extracting titles from media URLs"""
    progress_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, playlist_path):
        super().__init__()
        self.playlist_path = playlist_path

    def run(self):
        try:
            # Read URLs from playlist
            with open(self.playlist_path, 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]

            titles = []
            for url in urls:
                self.progress_signal.emit(f"Extracting title from: {url}")
                try:
                    # Use yt-dlp to get video title
                    result = subprocess.run(
                        ['yt-dlp', '--get-title', url],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    title = result.stdout.strip()
                    if title:
                        titles.append(title)
                except subprocess.CalledProcessError as e:
                    self.error_signal.emit(f"Error extracting title from {url}: {str(e)}")
                    continue

            # Write titles to .titles file
            titles_path = self.playlist_path.with_suffix('.titles')
            with open(titles_path, 'w', encoding='utf-8') as f:
                for title in titles:
                    f.write(f"{title}\n")

            self.progress_signal.emit(f"Created titles file: {titles_path}")
            self.finished_signal.emit()

        except Exception as e:
            self.error_signal.emit(f"Error: {str(e)}")
            self.finished_signal.emit()


class ScrollableModuleContainer(QWidget):
    """Container for multiple module widgets"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                width: 0px;
            }
        """)

        # Container widget for modules
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setSpacing(10)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        scroll_area.setWidget(self.container)

        main_layout.addWidget(scroll_area)

    def add_module(self, module: QWidget):
        """Add a new module widget to the container"""
        self.container_layout.addWidget(module)



class FetchWorker(QThread):
    """Worker thread para operaciones en segundo plano"""
    progress_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)
    error_signal = pyqtSignal(str)

    def __init__(self, reader, playlist_manager):
        super().__init__()
        self.reader = reader
        self.playlist_manager = playlist_manager

    def run(self):
        try:
            # Login
            if not self.reader.login():
                self.error_signal.emit("Error en la autenticación")
                return

            # Obtener feeds
            self.progress_signal.emit("Obteniendo feeds de blogs...")
            blog_feeds = self.reader.get_blog_feeds()
            self.progress_signal.emit(f"Encontrados {len(blog_feeds)} feeds en la categoría Blogs")

            # Procesar posts
            all_posts = []
            for feed in blog_feeds:
                self.progress_signal.emit(f"Procesando feed: {feed['title']}")
                try:
                    posts = self.reader.get_unread_posts(feed['id'])
                    all_posts.extend(posts)
                    self.progress_signal.emit(f"  Obtenidos {len(posts)} posts nuevos")
                except Exception as e:
                    self.error_signal.emit(f"Error procesando feed {feed['title']}: {str(e)}")
                    continue

            # Crear playlists
            self.progress_signal.emit("Creando playlists...")
            self.playlist_manager.process_posts(all_posts)
            self.progress_signal.emit(f"Proceso completado. Posts totales procesados: {len(all_posts)}")
            self.finished_signal.emit(True)

        except Exception as e:
            self.error_signal.emit(f"Error: {str(e)}")
            self.finished_signal.emit(False)

class BlogPlaylistModule(BaseModule):
    def __init__(self, output_dir: str, freshrss_url: str, username: str, auth_token: str, parent=None):
        self.output_dir = output_dir
        self.freshrss_url = freshrss_url
        self.username = username
        self.auth_token = auth_token
        super().__init__(parent)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # Configuración
        config_layout = QHBoxLayout()
        
        self.url_input = QLineEdit(self.freshrss_url)
        self.url_input.setPlaceholderText("FreshRSS URL")
        config_layout.addWidget(QLabel("URL:"))
        config_layout.addWidget(self.url_input)

        self.output_dir_input = QLineEdit(self.output_dir)
        self.output_dir_input.setPlaceholderText("Output Directory")
        config_layout.addWidget(QLabel("Output:"))
        config_layout.addWidget(self.output_dir_input)

        layout.addLayout(config_layout)

        # Botones
        button_layout = QHBoxLayout()
        self.fetch_button = QPushButton("Fetch Playlists")
        self.fetch_button.clicked.connect(self.start_fetch)
        button_layout.addWidget(self.fetch_button)

        self.open_output_button = QPushButton("Open Output Directory")
        self.open_output_button.clicked.connect(self.open_output_dir)
        button_layout.addWidget(self.open_output_button)

        layout.addLayout(button_layout)

        # Progress and Log
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

        # Inicializar objetos
        self.reader = FreshRSSReader(self.freshrss_url, self.username, self.auth_token)
        self.playlist_manager = PlaylistManager(self.output_dir)
        
        # Worker
        self.worker = None

    def start_fetch(self):
        self.fetch_button.setEnabled(False)
        self.progress_bar.setRange(0, 0)  # Modo indeterminado
        self.log_text.clear()

        # Actualizar configuración con valores actuales
        self.reader.base_url = self.url_input.text().rstrip('/')
        self.playlist_manager.output_dir = Path(self.output_dir_input.text())

        # Crear y configurar worker
        self.worker = FetchWorker(self.reader, self.playlist_manager)
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.error_signal.connect(self.handle_error)
        self.worker.finished_signal.connect(self.handle_finished)
        self.worker.start()

    def update_progress(self, message):
        self.log_text.append(message)

    def handle_error(self, error_message):
        self.log_text.append(f"ERROR: {error_message}")

    def handle_finished(self, success):
        self.fetch_button.setEnabled(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100 if success else 0)
        self.worker = None

    def open_output_dir(self):
        os.system(f'xdg-open "{self.output_dir_input.text()}"')

class FreshRSSReader:
    def __init__(self, base_url: str, username: str, api_password: str):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.api_password = api_password
        self.api_endpoint = f"{self.base_url}/api/greader.php"
        self.auth_token = None
        
    def login(self) -> bool:
        endpoint = f"{self.api_endpoint}/accounts/ClientLogin"
        params = {
            'Email': self.username,
            'Passwd': self.api_password
        }
        
        try:
            response = requests.get(endpoint, params=params)
            response.raise_for_status()
            
            for line in response.text.splitlines():
                if line.startswith('Auth='):
                    self.auth_token = line.replace('Auth=', '').strip()
                    logger.debug(f"Token obtenido correctamente")
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Error en login: {str(e)}")
            return False
            
    def get_headers(self) -> Dict[str, str]:
        if not self.auth_token:
            raise ValueError("No se ha realizado el login")
            
        return {
            'Authorization': f'GoogleLogin auth={self.auth_token}',
            'User-Agent': 'FreshRSS-Script/1.0'
        }

    def get_feed_subscriptions(self) -> List[Dict]:
        endpoint = f"{self.api_endpoint}/reader/api/0/subscription/list"
        params = {'output': 'json'}
        
        response = requests.get(endpoint, headers=self.get_headers(), params=params)
        response.raise_for_status()
        
        return response.json().get('subscriptions', [])

    def get_blog_feeds(self) -> List[Dict]:
        subscriptions = self.get_feed_subscriptions()
        blog_feeds = []
        
        for feed in subscriptions:
            for category in feed.get('categories', []):
                if category['label'] == 'Blogs':
                    blog_feeds.append(feed)
                    break
                    
        return blog_feeds

    def get_unread_posts(self, feed_id: str) -> List[Dict[str, str]]:
        endpoint = f"{self.api_endpoint}/reader/api/0/stream/contents/{quote(feed_id)}"
        params = {
            'output': 'json',
            'n': 1000,
            'xt': 'user/-/state/com.google/read'
        }
        
        response = requests.get(endpoint, headers=self.get_headers(), params=params)
        response.raise_for_status()
        data = response.json()
        
        posts = []
        for item in data.get('items', []):
            url = None
            if 'canonical' in item and item['canonical']:
                url = item['canonical'][0]['href']
            elif 'alternate' in item and item['alternate']:
                url = item['alternate'][0]['href']
            
            if url:
                published_date = datetime.fromtimestamp(item.get('published', 0))
                posts.append({
                    'url': url,
                    'date': published_date,
                    'title': item.get('title', 'Sin título'),
                    'month_key': published_date.strftime('%Y-%m'),
                    'feed_title': item.get('origin', {}).get('title', 'Unknown Feed')
                })
                
        return posts        


class PlaylistManager:
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def create_m3u_playlist(self, urls: List[str], feed_dir: Path, filename: str):
        """Crea un archivo .m3u con las URLs proporcionadas"""
        # Asegurarse de que existe el directorio del feed
        feed_dir.mkdir(parents=True, exist_ok=True)
        
        playlist_path = feed_dir / f"{filename}.m3u"
        
        with open(playlist_path, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            for url in urls:
                f.write(f"{url}\n")
                
        logger.info(f"Playlist creada: {playlist_path}")
        
    def process_posts(self, posts: List[Dict[str, str]]):
        """Procesa los posts y crea playlists organizadas por feed y mes"""
        # Organizar posts por feed y luego por mes
        posts_by_feed_and_month = defaultdict(lambda: defaultdict(list))
        
        for post in posts:
            feed_title = post['feed_title']
            month_key = post['month_key']
            posts_by_feed_and_month[feed_title][month_key].append(post)
        
        # Procesar cada feed
        for feed_title, months in posts_by_feed_and_month.items():
            # Crear un nombre seguro para el directorio del feed
            safe_feed_name = re.sub(r'[^\w\-_]', '_', feed_title)
            feed_dir = self.output_dir / safe_feed_name
            
            # Procesar cada mes del feed
            for month_key, month_posts in months.items():
                all_music_urls = set()
                for post in month_posts:
                    music_urls = extract_music_urls(post['url'])
                    all_music_urls.update(music_urls)
                
                if all_music_urls:
                    self.create_m3u_playlist(
                        list(all_music_urls),
                        feed_dir,
                        month_key
                    )


class PlaylistManagerModule(QWidget):
    def __init__(self, pending_dir="PENDIENTE", listened_dir="ESCUCHADO", **kwargs):
        super().__init__()
        self.pending_dir = Path(pending_dir)
        self.listened_dir = Path(listened_dir)
        self.selected_blog = None
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        
        # Left side (Blogs)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        blog_label = QLabel("Blogs Disponibles:")
        blog_label.setStyleSheet(f"color: {THEME['fg']}; font-weight: bold; font-size: 14px;")
        
        self.blog_list = QListWidget()
        self.blog_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {THEME['secondary_bg']};
                border: 1px solid {THEME['border']};
                border-radius: 4px;
            }}
            QListWidget::item {{
                color: {THEME['fg']};
                padding: 5px;
            }}
            QListWidget::item:selected {{
                background-color: {THEME['selection']};
            }}
        """)
        
        left_layout.addWidget(blog_label)
        left_layout.addWidget(self.blog_list)
        
        # Right side (Playlists)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        playlist_label = QLabel("Playlists:")
        playlist_label.setStyleSheet(f"color: {THEME['fg']}; font-weight: bold; font-size: 14px;")
        
        self.playlist_list = QListWidget()
        self.playlist_list.setStyleSheet(self.blog_list.styleSheet())
        
        self.play_button = QPushButton("Reproducir Seleccionado")
        self.play_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['accent']};
                color: {THEME['bg']};
                border: none;
                padding: 8px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {THEME['button_hover']};
            }}
        """)
        
        right_layout.addWidget(playlist_label)
        right_layout.addWidget(self.playlist_list)
        right_layout.addWidget(self.play_button)
        
        # Add panels to main layout
        layout.addWidget(left_panel, stretch=2)
        layout.addWidget(right_panel, stretch=1)
        
        # Connect signals
        self.blog_list.itemSelectionChanged.connect(self.on_blog_select)
        self.play_button.clicked.connect(self.play_selected)
        self.playlist_list.itemDoubleClicked.connect(self.play_selected)
        
        # Initial refresh
        self.refresh_blogs()

    def show_move_dialog(self, blog_name, playlist_name):
        """Muestra un diálogo preguntando si mover la playlist"""
        dialog = tk.Tk()
        dialog.title("Mover Playlist")
        
        # Centrar el diálogo
        dialog.geometry("300x150")
        dialog.eval('tk::PlaceWindow . center')
        
        # Configurar estilo oscuro
        dialog.configure(bg='#14141e')
        
        # Mensaje
        label = tk.Label(
            dialog,
            text="¿Has terminado la lista?",
            bg='#14141e',
            fg='white',
            font=("Helvetica", 12),
            pady=20
        )
        label.pack()

        # Frame para los botones
        button_frame = tk.Frame(dialog, bg='#14141e')
        button_frame.pack(pady=10)

        def on_yes():
            self.move_to_listened(blog_name, playlist_name)
            dialog.destroy()
            sys.exit()

        def on_no():
            dialog.destroy()
            sys.exit()

        # Botones
        yes_btn = tk.Button(
            button_frame,
            text="Sí",
            command=on_yes,
            bg='#1f1f2e',
            fg='white',
            width=10
        )
        no_btn = tk.Button(
            button_frame,
            text="No",
            command=on_no,
            bg='#1f1f2e',
            fg='white',
            width=10
        )
        
        yes_btn.pack(side=tk.LEFT, padx=5)
        no_btn.pack(side=tk.LEFT, padx=5)

        # Hacer que el diálogo sea modal
        dialog.transient()
        dialog.grab_set()
        
        # Bind teclas
        dialog.bind('<Return>', lambda e: on_yes())
        dialog.bind('<Escape>', lambda e: on_no())
        
        # Focus en el botón Sí
        yes_btn.focus_set()
        
        dialog.mainloop()


    def count_tracks_in_playlist(self, playlist_path):
        try:
            with open(playlist_path, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                return len(lines)
        except Exception:
            return 0

    def get_blogs_with_counts(self):
        blogs = {}
        if self.pending_dir.exists():
            for blog in self.pending_dir.iterdir():
                if blog.is_dir():
                    playlists = list(blog.glob('*.m3u'))
                    blogs[blog.name] = len(playlists)
        return blogs
  
    def get_monthly_playlists_with_counts(self, blog_name):
        blog_path = self.pending_dir / blog_name
        playlists = {}
        
        if blog_path.exists():
            for playlist in blog_path.glob('*.m3u'):
                track_count = self.count_tracks_in_playlist(playlist)
                playlists[playlist.name] = track_count
        
        return playlists


    def move_to_listened(self, blog_name, playlist_name):
        source = self.pending_dir / blog_name / playlist_name
        listened_blog_dir = self.listened_dir / blog_name
        
        listened_blog_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_")
        new_name = timestamp + playlist_name
        destination = listened_blog_dir / new_name
        
        shutil.move(str(source), str(destination))
        return destination


    def refresh_blogs(self):
        self.blog_list.clear()
        blogs = self.get_blogs_with_counts()
        
        for blog, count in blogs.items():
            item = QListWidgetItem(f"{blog} ({count} playlists)")
            self.blog_list.addItem(item)

    def on_blog_select(self):
        items = self.blog_list.selectedItems()
        if not items:
            return
        
        selection = items[0].text()
        self.selected_blog = selection.split(" (")[0]

        self.playlist_list.clear()
        playlists = self.get_monthly_playlists_with_counts(self.selected_blog)
        
        for playlist, count in playlists.items():
            item = QListWidgetItem(f"{playlist} ({count} canciones)")
            self.playlist_list.addItem(item)


    def show_move_dialog(self, blog_name, playlist_name):
        reply = QMessageBox.question(
            self,
            "Mover Playlist",
            "¿Has terminado la lista?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.move_to_listened(blog_name, playlist_name)
            self.refresh_blogs()


    def play_selected(self):
        if not self.selected_blog or not self.playlist_list.selectedItems():
            QMessageBox.warning(
                self,
                "Selección requerida",
                "Por favor, selecciona un blog y una playlist"
            )
            return

        playlist_selection = self.playlist_list.selectedItems()[0].text()
        playlist_name = playlist_selection.split(" (")[0]
        playlist_path = self.pending_dir / self.selected_blog / playlist_name
        
        if not playlist_path.exists():
            QMessageBox.critical(self, "Error", "No se encuentra el archivo de la playlist")
            return

        # Create titles file before playing
        self.extract_titles(playlist_path)

        try:
            process = subprocess.run(
                ["/home/huan/Scripts/utilities/aliases/mpv_lastfm_starter.sh", 
                 "--player-operation-mode=pseudo-gui", 
                 "--force-window=yes", 
                 str(playlist_path)]
            )
            
            if process.returncode == 0:
                self.show_move_dialog(self.selected_blog, playlist_name)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al reproducir: {str(e)}")

    def extract_titles(self, playlist_path):
            """Extract titles from playlist URLs using yt-dlp"""
            self.title_worker = TitleExtractorWorker(playlist_path)
            self.title_worker.progress_signal.connect(lambda msg: print(f"Title extraction: {msg}"))
            self.title_worker.error_signal.connect(lambda err: print(f"Title extraction error: {err}"))
            self.title_worker.start()

if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    
    # Create the main container
    container = ScrollableModuleContainer()
    
    # Add multiple playlist manager modules
    module1 = PlaylistManagerModule(pending_dir="PENDIENTE1", listened_dir="ESCUCHADO1")
    module2 = PlaylistManagerModule(pending_dir="PENDIENTE2", listened_dir="ESCUCHADO2")
    
    container.add_module(module1)
    container.add_module(module2)
    
    container.show()
    sys.exit(app.exec())