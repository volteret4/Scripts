
#!/usr/bin/env python
#
# Script Name: menu_blogs.py
# Description:  Crea un menu, con un listado de blogs obtenido de Freshrss, y unas playlists mensuales de cada unno de ellos, para reproducir en mpv. 
#               También crea una entrada para urls para crear playlists de esa url.
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# TODO: 
# Notes:
#   Dependencies:  - python3, 
#

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QLabel,
    QProgressBar, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QScrollArea, QInputDialog, QMenu
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from base_module import BaseModule, THEME
import yt_dlp
import logging
import os
import re
import requests
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from urllib.parse import urlparse, parse_qs, quote
from typing import List, Dict


logging.basicConfig(level=logging.DEBUG)



class MusicManagerModule(BaseModule):
    def __init__(self, **kwargs):
        self.pending_dir = Path(kwargs.get('pending_dir', 'playlists/PENDIENTE'))
        self.listened_dir = Path(kwargs.get('listened_dir', 'playlists/ESCUCHADO'))
        self.local_dir = Path(kwargs.get('local_dir', 'playlists/LISTAS_LOCALES'))
        self.output_dir = kwargs.get('output_dir', str(self.pending_dir))
        self.selected_blog = None
        self.worker = None
        super().__init__()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Main content area with three panels
        main_panel = QHBoxLayout()
        
        # Left panel (Blogs and Local Playlists)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Blogs section
        blog_label = QLabel("Blogs:")
        blog_label.setStyleSheet(f"color: {THEME['fg']}; font-weight: bold; font-size: 14px;")
        
        self.blog_list = QListWidget()
        self.blog_list.setStyleSheet(self._get_list_style())
        
        # Local playlists section
        local_label = QLabel("Listas Locales:")
        local_label.setStyleSheet(f"color: {THEME['fg']}; font-weight: bold; font-size: 14px;")
        
        self.local_list = QListWidget()
        self.local_list.setStyleSheet(self._get_list_style())
        
        left_layout.addWidget(blog_label)
        left_layout.addWidget(self.blog_list)
        left_layout.addWidget(local_label)
        left_layout.addWidget(self.local_list)
        
        # Middle panel (Playlists)
        middle_panel = QWidget()
        middle_layout = QVBoxLayout(middle_panel)
        
        playlist_label = QLabel("Playlists:")
        playlist_label.setStyleSheet(f"color: {THEME['fg']}; font-weight: bold; font-size: 14px;")
        
        self.playlist_list = QListWidget()
        self.playlist_list.setStyleSheet(self._get_list_style())
        self.playlist_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.playlist_list.customContextMenuRequested.connect(self.show_playlist_context_menu)
        
        self.play_button = QPushButton("Reproducir Seleccionado")
        self.play_button.setStyleSheet(self._get_button_style())
        
        middle_layout.addWidget(playlist_label)
        middle_layout.addWidget(self.playlist_list)
        middle_layout.addWidget(self.play_button)
        
        # Right panel (Playlist Content)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        content_label = QLabel("Contenido:")
        content_label.setStyleSheet(f"color: {THEME['fg']}; font-weight: bold; font-size: 14px;")
        
        self.content_list = QListWidget()
        self.content_list.setStyleSheet(self._get_list_style())
        self.content_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.content_list.customContextMenuRequested.connect(self.show_track_context_menu)
        
        right_layout.addWidget(content_label)
        right_layout.addWidget(self.content_list)
        
        # Add panels to main layout
        main_panel.addWidget(left_panel, stretch=2)
        main_panel.addWidget(middle_panel, stretch=2)
        main_panel.addWidget(right_panel, stretch=3)
        layout.addLayout(main_panel)
        
        # URL Processor at the bottom
        url_layout = QHBoxLayout()
        self.url_process_input = QLineEdit()
        self.url_process_input.setPlaceholderText("Ingrese URL del blog para procesar")
        url_layout.addWidget(self.url_process_input)
        
        self.process_url_button = QPushButton("Procesar URL")
        self.process_url_button.setStyleSheet(self._get_button_style())
        self.process_url_button.clicked.connect(self.process_url)
        url_layout.addWidget(self.process_url_button)
        layout.addLayout(url_layout)
        
        # Connect signals
        self.blog_list.itemSelectionChanged.connect(self.on_blog_select)
        self.local_list.itemSelectionChanged.connect(self.on_local_select)
        self.playlist_list.itemSelectionChanged.connect(self.on_playlist_select)
        self.play_button.clicked.connect(self.play_selected)
        self.playlist_list.itemDoubleClicked.connect(self.play_selected)
        
        # Initial refresh
        self.refresh_lists()

    def _get_list_style(self):
        return f"""
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
        """

    def _get_button_style(self):
        return f"""
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
        """

    def count_tracks_in_playlist(self, playlist_path):
        """Count the number of tracks in a playlist file."""
        try:
            with open(playlist_path, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                return len(lines)
        except Exception:
            return 0

    def get_blogs_with_counts(self):
        """Get all blogs and their playlist counts."""
        blogs = {}
        if self.pending_dir.exists():
            for blog in self.pending_dir.iterdir():
                if blog.is_dir():
                    playlists = list(blog.glob('*.m3u'))
                    blogs[blog.name] = len(playlists)
        return blogs

    def get_monthly_playlists_with_counts(self, blog_name):
        """Get all playlists for a blog with their track counts."""
        blog_path = self.pending_dir / blog_name
        playlists = {}
        
        if blog_path.exists():
            for playlist in blog_path.glob('*.m3u'):
                track_count = self.count_tracks_in_playlist(playlist)
                playlists[playlist.name] = track_count
        
        return playlists

    def move_to_listened(self, blog_name, playlist_name):
        """Move a playlist to the listened directory."""
        source = self.pending_dir / blog_name / playlist_name
        listened_blog_dir = self.listened_dir / blog_name
        
        listened_blog_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_")
        new_name = timestamp + playlist_name
        destination = listened_blog_dir / new_name
        
        shutil.move(str(source), str(destination))
        return destination

    def refresh_lists(self):
        """Refresh both blog and local lists."""
        self.refresh_blogs()
        self.refresh_local_playlists()

    def refresh_blogs(self):
        """Refresh the list of available blogs."""
        self.blog_list.clear()
        blogs = self.get_blogs_with_counts()
        
        for blog, count in blogs.items():
            item = QListWidgetItem(f"{blog} ({count} playlists)")
            item.setData(Qt.ItemDataRole.UserRole, {'type': 'blog', 'name': blog})
            self.blog_list.addItem(item)

    def refresh_local_playlists(self):
        """Refresh the list of local playlists."""
        self.local_list.clear()
        if self.local_dir.exists():
            for playlist in self.local_dir.glob('*.m3u'):
                item = QListWidgetItem(playlist.stem)
                item.setData(Qt.ItemDataRole.UserRole, {'type': 'local', 'name': playlist.name})
                self.local_list.addItem(item)


    def get_track_info(self, url):
        """Get track information using yt-dlp."""
        try:
            ydl_opts = {
                'quiet': True,
                'extract_flat': True,
                'force_generic_extractor': False
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return info.get('title', url)
        except:
            return url

    def on_playlist_select(self):
            """Handle playlist selection event."""
            self.content_list.clear()
            
            selected_items = self.playlist_list.selectedItems()
            if not selected_items:
                return
                
            playlist_item = selected_items[0]
            playlist_data = playlist_item.data(Qt.ItemDataRole.UserRole)
            
            if not playlist_data:
                return
                
            if playlist_data['type'] == 'blog':
                playlist_path = self.pending_dir / playlist_data['blog'] / playlist_data['name']
                titles_path = self.pending_dir / playlist_data['blog'] / f"{playlist_path.stem}.titles"
            else:
                playlist_path = self.local_dir / playlist_data['name']
                titles_path = self.local_dir / f"{playlist_path.stem}.titles"
            
            if playlist_path.exists():
                # Cargar los títulos si existe el archivo
                titles = {}
                if titles_path.exists():
                    with open(titles_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            try:
                                url, title = line.strip().split(' | ', 1)
                                titles[url] = title
                            except ValueError:
                                continue

                # Leer la playlist y mostrar los títulos
                with open(playlist_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            # Usar el título del archivo .titles si existe, si no usar la URL
                            title = titles.get(line, line)
                            item = QListWidgetItem(title)
                            item.setData(Qt.ItemDataRole.UserRole, {'url': line})
                            self.content_list.addItem(item)

    
    def on_local_select(self):
        """Handle local playlist selection event."""
        items = self.local_list.selectedItems()
        if not items:
            return
        
        # Deselect any selected blog
        self.blog_list.clearSelection()
        self.selected_blog = None
        
        self.playlist_list.clear()
        item_data = items[0].data(Qt.ItemDataRole.UserRole)
        item = QListWidgetItem(item_data['name'])
        item.setData(Qt.ItemDataRole.UserRole, {
            'type': 'local',
            'name': item_data['name']
        })
        self.playlist_list.addItem(item)


    def show_playlist_context_menu(self, position):
        """Show context menu for playlists."""
        menu = QMenu()
        delete_action = menu.addAction("Eliminar Playlist")
        action = menu.exec(self.playlist_list.mapToGlobal(position))
        
        if action == delete_action:
            self.delete_selected_playlist()

    def show_track_context_menu(self, position):
        """Show context menu for tracks."""
        menu = QMenu()
        delete_action = menu.addAction("Eliminar Track")
        action = menu.exec(self.content_list.mapToGlobal(position))
        
        if action == delete_action:
            self.delete_selected_track()


    def delete_selected_playlist(self):
        """Delete the selected playlist."""
        selected_items = self.playlist_list.selectedItems()
        if not selected_items:
            return
            
        reply = QMessageBox.question(
            self,
            "Confirmar Eliminación",
            "¿Estás seguro de que quieres eliminar esta playlist?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            playlist_item = selected_items[0]
            playlist_data = playlist_item.data(Qt.ItemDataRole.UserRole)
            
            if playlist_data['type'] == 'blog':
                playlist_path = self.pending_dir / self.selected_blog / playlist_data['name']
            else:
                playlist_path = self.local_dir / playlist_data['name']
            
            try:
                playlist_path.unlink()
                self.refresh_lists()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al eliminar playlist: {str(e)}")


    def delete_selected_track(self):
        """Delete the selected track from the playlist."""
        playlist_items = self.playlist_list.selectedItems()
        track_items = self.content_list.selectedItems()
        
        if not playlist_items or not track_items:
            return
            
        reply = QMessageBox.question(
            self,
            "Confirmar Eliminación",
            "¿Estás seguro de que quieres eliminar esta canción?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            playlist_item = playlist_items[0]
            playlist_data = playlist_item.data(Qt.ItemDataRole.UserRole)
            
            if playlist_data['type'] == 'blog':
                playlist_path = self.pending_dir / playlist_data['blog'] / playlist_data['name']
                titles_path = self.pending_dir / playlist_data['blog'] / f"{playlist_path.stem}.titles"
            else:
                playlist_path = self.local_dir / playlist_data['name']
                titles_path = self.local_dir / f"{playlist_path.stem}.titles"
            
            try:
                # Read all lines from playlist
                with open(playlist_path, 'r', encoding='utf-8') as f:
                    playlist_lines = f.readlines()
                
                # Read all lines from titles if it exists
                titles_lines = []
                if titles_path.exists():
                    with open(titles_path, 'r', encoding='utf-8') as f:
                        titles_lines = f.readlines()
                
                # Remove the selected track
                track_url = track_items[0].data(Qt.ItemDataRole.UserRole)['url']
                
                # Filter out the track from playlist
                playlist_lines = [line for line in playlist_lines if track_url not in line]
                
                # Filter out the track from titles
                titles_lines = [line for line in titles_lines if not line.startswith(track_url + ' | ')]
                
                # Write back the files
                with open(playlist_path, 'w', encoding='utf-8') as f:
                    f.writelines(playlist_lines)
                    
                if titles_path.exists():
                    with open(titles_path, 'w', encoding='utf-8') as f:
                        f.writelines(titles_lines)
                
                # Refresh the content list
                self.on_playlist_select()
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al eliminar track: {str(e)}")




    def on_blog_select(self):
            """Handle blog selection event."""
            items = self.blog_list.selectedItems()
            if not items:
                return
            
            # Deselect any selected local playlist
            self.local_list.clearSelection()
            
            item_data = items[0].data(Qt.ItemDataRole.UserRole)
            self.selected_blog = item_data['name']
            
            self.playlist_list.clear()
            playlists = self.get_monthly_playlists_with_counts(self.selected_blog)
            
            for playlist, count in playlists.items():
                item = QListWidgetItem(f"{playlist} ({count} canciones)")
                # Añadir datos extra al item
                item.setData(Qt.ItemDataRole.UserRole, {
                    'type': 'blog',
                    'name': playlist,
                    'blog': self.selected_blog
                })
                self.playlist_list.addItem(item)

    def show_move_dialog(self, blog_name, playlist_name):
        """Show dialog asking whether to move the playlist to listened."""
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
        """Play the selected playlist."""
        if not self.playlist_list.selectedItems():
            QMessageBox.warning(
                self,
                "Selección requerida",
                "Por favor, selecciona una playlist"
            )
            return

        playlist_selection = self.playlist_list.selectedItems()[0]
        playlist_data = playlist_selection.data(Qt.ItemDataRole.UserRole)
        
        if playlist_data['type'] == 'blog':
            playlist_path = self.pending_dir / playlist_data['blog'] / playlist_data['name']
        else:
            playlist_path = self.local_dir / playlist_data['name']
        
        if not playlist_path.exists():
            QMessageBox.critical(self, "Error", "No se encuentra el archivo de la playlist")
            return

        try:
            process = subprocess.run(
                ["/home/huan/Scripts/menus/musica/menu_blogs/mpv/mpv_lastfm_starter.sh", 
                 "--player-operation-mode=pseudo-gui", 
                 "--force-window=yes", 
                 str(playlist_path)]
            )
            
            if process.returncode == 0 and playlist_data['type'] == 'blog':
                self.show_move_dialog(playlist_data['blog'], playlist_data['name'])
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al reproducir: {str(e)}")


    def process_url(self):
        """Process a blog URL to extract music links."""
        url = self.url_process_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Error", "Por favor ingrese una URL")
            return

        try:
            music_urls = extract_music_urls(url)
            if not music_urls:
                QMessageBox.warning(self, "No URLs", "No se encontraron URLs de música en la página")
                return

            # Ask for playlist name
            name, ok = QInputDialog.getText(
                self, 
                "Guardar Playlist",
                "Nombre de la playlist:",
                QLineEdit.EchoMode.Normal
            )
            
            if ok and name:
                # Create playlist file
                playlist_path = self.local_dir / f"{name}.m3u"
                
                with open(playlist_path, 'w', encoding='utf-8') as f:
                    f.write("#EXTM3U\n")
                    for music_url in music_urls:
                        f.write(f"{music_url}\n")
                
                self.refresh_local_playlists()
                QMessageBox.information(self, "Éxito", "Playlist creada correctamente")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al procesar URL: {str(e)}")


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
        feed_dir.mkdir(parents=True, exist_ok=True)
        playlist_path = feed_dir / f"{filename}.m3u"
        
        with open(playlist_path, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            for url in urls:
                f.write(f"{url}\n")
                
        logger.info(f"Playlist creada: {playlist_path}")
        
    def process_posts(self, posts: List[Dict[str, str]]):
        """Procesa los posts y crea playlists organizadas por feed y mes"""
        posts_by_feed_and_month = defaultdict(lambda: defaultdict(list))
        
        for post in posts:
            feed_title = post['feed_title']
            month_key = post['month_key']
            posts_by_feed_and_month[feed_title][month_key].append(post)
        
        for feed_title, months in posts_by_feed_and_month.items():
            safe_feed_name = re.sub(r'[^\w\-_]', '_', feed_title)
            feed_dir = self.output_dir / safe_feed_name
            
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

# def extract_music_urls(url):
#     """
#     Extrae las URLs de música (Bandcamp, SoundCloud, YouTube) del contenido HTML de la URL dada.
#     """
#     try:
#         response = requests.get(url)
#         content = response.text

#         music_patterns = [
#             r'"(bandcamp\.com/[^"]+)"',
#             r'(https?://(?:www\.)?soundcloud\.com/[^\s"\'<>]+)',
#             r'(https?://(?:www\.)?youtube\.com/embed/[^\s"\'<>]+)',
#             r'(https?://(?:www\.)?youtube\.com/watch\?[^\s"\'<>]+)',
#             r'(https?://(?:www\.)?youtu\.be/[^\s"\'<>]+)'
#         ]

#         music_urls = set()
#         for pattern in music_patterns:
#             matches = re.findall(pattern, content)
#             for match in matches:
#                 extracted_url = match[0] if isinstance(match, tuple) else match
#                 if 'bandcamp.com' in extracted_url:
#                     if extracted_url.startswith('//'):
#                         extracted_url = 'https:' + extracted_url
#                     extracted_url = extract_bandcamp_id(extracted_url)
#                 else:
#                     extracted_url = clean_youtube_url(extracted_url)
#                 music_urls.add(extracted_url)

#         return list(music_urls)

#     except Exception as e:
#         print(f"Error al extraer URLs: {e}")
#         return [] 

# def extract_bandcamp_id(url):
#     """Extrae el ID de álbum/track de Bandcamp desde un iframe."""
#     album_match = re.search(r'album=(\d+)', url)
#     track_match = re.search(r'track=(\d+)', url)
    
#     if album_match:
#         return f"https://bandcamp.com/album/{album_match.group(1)}"
#     elif track_match:
#         return f"https://bandcamp.com/track/{track_match.group(1)}"
#     return url

# def clean_youtube_url(url):
#     """Normaliza la URL de YouTube para obtener el formato watch?v=."""
#     parsed_url = urlparse(url)
#     if 'youtube.com/embed/' in url:
#         video_id = parsed_url.path.split('/')[-1]
#         return f'https://youtube.com/watch?v={video_id}'
#     if 'youtu.be' in url:
#         video_id = parsed_url.path.lstrip('/')
#         return f'https://youtube.com/watch?v={video_id}'
#     if 'youtube.com/watch' in url:
#         parsed_query = parse_qs(parsed_url.query)
#         video_id = parsed_query.get('v', [''])[0]
#         return f'https://youtube.com/watch?v={video_id}'
#     return url

