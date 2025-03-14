from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableView,
                           QHeaderView, QPushButton, QSplitter, QWidget, QAbstractItemView,
                           QTableWidgetItem, QMenu)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor
from typing import Dict, Optional
from pathlib import Path
from datetime import datetime
import json
import sqlite3
import os
import subprocess
from base_module import BaseModule, THEMES, PROJECT_ROOT
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LastFMScrobblerModule(BaseModule):
    """Module for scrobbling tracks to LastFM and viewing recent scrobbles."""
    
    def __init__(self, parent=None, theme='Tokyo Night', database_path=None, lastfm_user=None, 
                 lastfm_api_key=None, lastfm_api_secret=None, track_limit=20):
        # Store configuration first so they're available in init_ui
        self.database_path = database_path
        self.lastfm_api_key = lastfm_api_key
        self.lastfm_api_secret = lastfm_api_secret
        self.lastfm_user = lastfm_user
        self.max_scrobbles = track_limit
        self.conn = None
        self.cursor = None

        # Initialize the BaseModule last
        super().__init__(parent, theme)
        
        # Connect to database and load scrobbles after UI is initialized
        self.connect_to_db()
        self.load_recent_scrobbles()
    
    def init_ui(self):
        """Initialize the user interface as required by BaseModule."""
        # Create main layout
        self.main_layout = QVBoxLayout()
        
        # Create splitter for left and right panels
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel - Track queue
        self.left_panel = QWidget()
        self.left_layout = QVBoxLayout(self.left_panel)
        
        queue_label = QLabel("Cola de canciones para scrobblear")
        queue_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.left_layout.addWidget(queue_label)
        
        # Queue table
        self.queue_table = QTableWidget()
        self.queue_table.setColumnCount(3)
        self.queue_table.setHorizontalHeaderLabels(["Título", "Álbum", "Artista"])
        self.queue_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.queue_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.queue_table.setDragEnabled(True)
        self.queue_table.setAcceptDrops(True)
        self.queue_table.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.left_layout.addWidget(self.queue_table)
        
        # Scrobble button
        self.scrobble_button = QPushButton("Scrobblear Canciones")
        self.scrobble_button.clicked.connect(self.scrobble_songs)
        self.left_layout.addWidget(self.scrobble_button)
        
        # Right panel - Recent scrobbles
        self.right_panel = QWidget()
        self.right_layout = QVBoxLayout(self.right_panel)
        
        scrobbles_label = QLabel(f"Últimos {self.max_scrobbles} scrobbles")
        scrobbles_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.right_layout.addWidget(scrobbles_label)
        
        # Scrobbles table
        self.scrobbles_table = QTableWidget()
        self.scrobbles_table.setColumnCount(7)
        self.scrobbles_table.setHorizontalHeaderLabels([
            "Timestamp", "Artista", "Álbum", "Canción", "Sello", 
            "Enlaces", "En DB"
        ])
        self.scrobbles_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.scrobbles_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.scrobbles_table.cellClicked.connect(self.handle_cell_click)
        self.right_layout.addWidget(self.scrobbles_table)
        
        # Refresh button
        self.refresh_button = QPushButton("Actualizar Scrobbles")
        self.refresh_button.clicked.connect(self.load_recent_scrobbles)
        self.right_layout.addWidget(self.refresh_button)
        
        # Add panels to splitter with 1:3 ratio
        self.splitter.addWidget(self.left_panel)
        self.splitter.addWidget(self.right_panel)
        self.splitter.setSizes([100, 300])  # 1:3 ratio
        
        # Add splitter to main layout directly
        self.main_layout.addWidget(self.splitter)
        
        # Set the layout for this widget - use self.setLayout as this is a QWidget
        self.setLayout(self.main_layout)
    
    def connect_to_db(self):
        """Connect to the local database for storing scrobble data."""
        try:
            if self.database_path:
                print(f"Connecting to database at {self.database_path}")
                
                # Connect to the database
                self.conn = sqlite3.connect(self.database_path)
                
                # Create a cursor object
                self.cursor = self.conn.cursor()
                
                # Check if the connection is successful by querying the tables
                self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = self.cursor.fetchall()
                
                # Verify that the required tables exist
                required_tables = ['songs', 'artists', 'albums', 'scrobbles']
                existing_tables = [table[0] for table in tables]
                
                missing_tables = [table for table in required_tables if table not in existing_tables]
                if missing_tables:
                    print(f"Warning: Missing tables: {', '.join(missing_tables)}")
                else:
                    print("Successfully connected to the database")
                    
                return True
            else:
                print("No database path provided")
                return False
        except Exception as e:
            print(f"Error connecting to database: {e}")
            self.conn = None
            self.cursor = None
            return False
    
    def load_recent_scrobbles(self):
        """Load recent scrobbles from the database."""
        try:
            if not hasattr(self, 'conn') or not self.conn:
                print("No database connection available")
                return
            script = os.path.join(PROJECT_ROOT, 'base_datos', 'scrobbles_lastfm.py')
            subprocess.run(['python', script, '--db-path', self.database_path, '--user', self.lastfm_user,  '--lastfm-api-key', self.lastfm_api_key ])
            
            # Clear existing data
            self.scrobbles_table.setRowCount(0)
            
            # Query recent scrobbles
            query = f"""
            SELECT s.timestamp, s.scrobble_date, s.artist_name, s.album_name, s.track_name,
                   a.label, s.song_id, s.album_id, s.artist_id,
                   sl.spotify_url, sl.lastfm_url, sl.youtube_url, sl.musicbrainz_url, sl.bandcamp_url,
                   ar.spotify_url, ar.youtube_url, ar.musicbrainz_url, ar.discogs_url, ar.rateyourmusic_url, ar.wikipedia_url
            FROM scrobbles s
            LEFT JOIN albums a ON s.album_id = a.id
            LEFT JOIN song_links sl ON s.song_id = sl.song_id
            LEFT JOIN artists ar ON s.artist_id = ar.id
            ORDER BY s.timestamp DESC
            LIMIT {self.max_scrobbles}
            """
            
            self.cursor.execute(query)
            scrobbles = self.cursor.fetchall()
            
            # Fill table with scrobbles
            for row_idx, scrobble in enumerate(scrobbles):
                timestamp, scrobble_date, artist, album, track, label, song_id, album_id, artist_id = scrobble[:9]
                song_links = scrobble[9:14]
                artist_links = scrobble[14:20]
                
                # Add row
                self.scrobbles_table.insertRow(row_idx)
                
                # Format timestamp
                formatted_date = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                date_item = QTableWidgetItem(formatted_date)
                date_item.setData(8, timestamp)  # Usando 8 como valor entero para UserRole
                self.scrobbles_table.setItem(row_idx, 0, date_item)
                
                # Add artist, album, track
                self.scrobbles_table.setItem(row_idx, 1, QTableWidgetItem(artist))
                self.scrobbles_table.setItem(row_idx, 2, QTableWidgetItem(album))
                self.scrobbles_table.setItem(row_idx, 3, QTableWidgetItem(track))
                
                # Add label
                self.scrobbles_table.setItem(row_idx, 4, QTableWidgetItem(label if label else ""))
                
                # Add links
                links_item = QTableWidgetItem("Enlaces")
                links_item.setData(8, {  # Usando 8 como valor entero para UserRole
                    "song": {
                        "spotify": song_links[0],
                        "lastfm": song_links[1],
                        "youtube": song_links[2],
                        "musicbrainz": song_links[3],
                        "bandcamp": song_links[4]
                    },
                    "artist": {
                        "spotify": artist_links[0],
                        "youtube": artist_links[1],
                        "musicbrainz": artist_links[2],
                        "discogs": artist_links[3],
                        "rateyourmusic": artist_links[4],
                        "wikipedia": artist_links[5]
                    }
                })
                self.scrobbles_table.setItem(row_idx, 5, links_item)
                
                # In database indicator
                in_db = "Sí" if song_id is not None else "No"
                self.scrobbles_table.setItem(row_idx, 6, QTableWidgetItem(in_db))
            
            print(f"Loaded {len(scrobbles)} recent scrobbles")
        except Exception as e:
            print(f"Error loading scrobbles: {e}")
    
    def add_song_to_queue(self, song_data):
        """Add a song to the scrobble queue."""
        row = self.queue_table.rowCount()
        self.queue_table.insertRow(row)
        
        # Add song info to queue
        self.queue_table.setItem(row, 0, QTableWidgetItem(song_data["track"]))
        self.queue_table.setItem(row, 1, QTableWidgetItem(song_data["album"]))
        self.queue_table.setItem(row, 2, QTableWidgetItem(song_data["artist"]))
        
        # Store additional data
        for col in range(3):
            item = self.queue_table.item(row, col)
            if item:
                item.setData(8, song_data)  # Usando 8 como valor entero para UserRole
    
    def scrobble_songs(self):
        """Scrobble songs in the queue to LastFM."""
        try:
            song_count = self.queue_table.rowCount()
            if song_count == 0:
                print("No songs in queue to scrobble")
                return
            
            # Here you would implement the actual scrobbling logic
            # For now, we'll just print what would be scrobbled
            print(f"Scrobbling {song_count} songs:")
            
            for row in range(song_count):
                title = self.queue_table.item(row, 0).text()
                album = self.queue_table.item(row, 1).text()
                artist = self.queue_table.item(row, 2).text()
                print(f"  {row+1}. {artist} - {title} ({album})")
            
            # Clear queue after scrobbling
            self.queue_table.setRowCount(0)
            
            # Refresh scrobbles list
            self.load_recent_scrobbles()
        except Exception as e:
            print(f"Error scrobbling songs: {e}")
    
    def handle_cell_click(self, row, column):
        """Handle click on a cell in the scrobbles table."""
        try:
            # If timestamp column was clicked, execute popollo function with all cell contents
            if column == 0:
                # Collect all cell contents in this row
                row_data = {}
                headers = ["timestamp", "artist", "album", "track", "label", "links", "in_db"]
                
                for col_idx, header in enumerate(headers):
                    item = self.scrobbles_table.item(row, col_idx)
                    if item:
                        # Get the displayed text for most fields
                        row_data[header] = item.text()
                        
                        # For timestamp, also get the raw value
                        if col_idx == 0:
                            row_data["raw_timestamp"] = item.data(8)  # Usando 8 como valor entero para UserRole
                            
                        # For links, get the links data
                        if col_idx == 5:
                            row_data["links_data"] = item.data(8)  # Usando 8 como valor entero para UserRole
                
                # Execute popollo with all data from this row
                self.popollo(row_data)
            
            # If links column was clicked, show links menu
            elif column == 5:
                item = self.scrobbles_table.item(row, column)
                if item:
                    links_data = item.data(8)  # Usando 8 como valor entero para UserRole
                    if links_data:
                        self.show_links_menu(links_data, QCursor.pos())
        except Exception as e:
            print(f"Error handling cell click: {e}")
    
    def popollo(self, row_data):
        """Execute popollo function with content of all cells in the row."""
        print("Ejecutando popollo con datos de la fila:")
        print(json.dumps(row_data, indent=2, default=str))
        # Here you would implement the actual popollo functionality
    
    def show_links_menu(self, links_data, position):
        """Show a menu with links for the selected song/artist."""
        try:
            menu = QMenu()
            
            # Add song links
            if links_data.get("song"):
                song_menu = menu.addMenu("Canción")
                for service, url in links_data["song"].items():
                    if url:
                        action = song_menu.addAction(service.capitalize())
                        action.setData(url)
                        # Make links appear in a non-blue color
                        action.setStyleSheet("color: inherit;")
            
            # Add artist links
            if links_data.get("artist"):
                artist_menu = menu.addMenu("Artista")
                for service, url in links_data["artist"].items():
                    if url:
                        action = artist_menu.addAction(service.capitalize())
                        action.setData(url)
                        # Make links appear in a non-blue color
                        action.setStyleSheet("color: inherit;")
            
            # Connect actions
            menu.triggered.connect(self.open_link)
            
            # Show menu
            menu.exec_(position)
        except Exception as e:
            print(f"Error showing links menu: {e}")
    
    def open_link(self, action):
        """Open the selected link."""
        import webbrowser
        url = action.data()
        if url:
            webbrowser.open(url)
    
    def apply_theme(self, theme_name=None):
        """Apply theme to the module."""
        # Call the parent apply_theme method
        super().apply_theme(theme_name)