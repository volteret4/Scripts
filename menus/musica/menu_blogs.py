
#!/usr/bin/env python
#
# Script Name: menu_blogs.py
# Description: Crean un menu, con un listado de blogs, y unas playlists mensuales de cada unno de ellos, para reproducir en mpv.
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# TODO: 
# Notes:
#   Dependencies:  - python3, tkinter
#                  - mpv
#                  - servidor freshrss y categoria blog creada en el.
#
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, 
                            QPushButton, QLabel, QMessageBox, QListWidgetItem)
from PyQt6.QtCore import Qt
from datetime import datetime
import os
import shutil
import subprocess
from pathlib import Path
from base_module import BaseModule, THEME  # Make sure to import the base module

class PlaylistManagerModule(BaseModule):
    """A module for managing music playlists with pending and listened states."""
    
    def __init__(self, pending_dir="PENDIENTE", listened_dir="ESCUCHADO", **kwargs):
        self.pending_dir = Path(pending_dir)
        self.listened_dir = Path(listened_dir)
        self.selected_blog = None
        super().__init__()
       # self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
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

    def refresh_blogs(self):
        """Refresh the list of available blogs."""
        self.blog_list.clear()
        blogs = self.get_blogs_with_counts()
        
        for blog, count in blogs.items():
            item = QListWidgetItem(f"{blog} ({count} playlists)")
            self.blog_list.addItem(item)

    def on_blog_select(self):
        """Handle blog selection event."""
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

        try:
            process = subprocess.run(
                ["/home/huan/Scripts/menus/musica/menu_blogs/mpv_lastfm_starter.sh", 
                 "--player-operation-mode=pseudo-gui", 
                 "--force-window=yes", 
                 str(playlist_path)]
            )
            
            if process.returncode == 0:
                self.show_move_dialog(self.selected_blog, playlist_name)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al reproducir: {str(e)}")