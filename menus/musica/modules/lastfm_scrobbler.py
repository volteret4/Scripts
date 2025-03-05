import sys
import json
from typing import Dict, Any, Optional
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QScrollArea, QFrame)
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices, QFont

from base_module import BaseModule, THEMES

class LastFMScrobbleModule(BaseModule):
    def __init__(self, username: str = "", api_key: str = "", 
                 services: Dict[str, Dict[str, str]] = None):
        """
        Initialize LastFM Scrobble Module
        
        :param username: LastFM username to track
        :param api_key: LastFM API key
        :param services: Dictionary of services with their URLs and icons
        """
        super().__init__()
        
        self.username = username
        self.api_key = api_key
        
        # Default services if not provided
        self.services = services or {
            'YouTube': {
                'url_template': 'https://www.youtube.com/results?search_query={}+{}',
                'function': self.open_youtube
            },
            'LastFM': {
                'url_template': 'https://www.last.fm/music/{}/_/{}',
                'function': self.open_lastfm
            },
            'RateYourMusic': {
                'url_template': 'https://rateyourmusic.com/search?searchterm={}+{}',
                'function': self.open_rateyourmusic
            },
            'Spotify': {
                'url_template': 'https://open.spotify.com/search/{}%20{}',
                'function': self.open_spotify
            },
            'Discogs': {
                'url_template': 'https://www.discogs.com/search/?q={}+{}',
                'function': self.open_discogs
            },
            'AllMusic': {
                'url_template': 'https://www.allmusic.com/search/all/{}+{}',
                'function': self.open_allmusic
            }
        }
        
        # Current track information
        self.current_track: Optional[Dict[str, str]] = None
        
        self.init_ui()
        
        # Timer for updating track (you'll replace this with actual LastFM API call)
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_current_track)
        self.update_timer.start(5000)  # Update every 5 seconds

    def init_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout()
        
        # Scroll area for track history
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_area.setWidget(scroll_content)
        
        # Current track section
        self.current_track_label = QLabel("No track playing")
        self.current_track_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.current_track_label.setFont(QFont('Inter', 16))
        layout.addWidget(self.current_track_label)
        
        layout.addWidget(scroll_area)
        
        self.setLayout(layout)

    def update_current_track(self):
        """
        Simulated track update. 
        Replace with actual LastFM API call in production.
        """
        # This is a mock implementation. You'll want to replace this 
        # with actual LastFM API tracking
        mock_track = {
            'artist': 'Arctic Monkeys',
            'track': 'Do I Wanna Know?',
            'album': 'AM',
            'timestamp': '2024-03-04 15:30:00'
        }
        
        self.display_track(mock_track)

    def display_track(self, track: Dict[str, str]):
        """Display the current track with service buttons"""
        # Update current track label with clickable artist and track
        artist_track = f"<a href='#' style='color: {self.theme['accent']};'>{track['artist']}</a> - " \
                       f"<a href='#' style='color: {self.theme['accent']};'>{track['track']}</a>"
        self.current_track_label.setText(artist_track)
        self.current_track_label.setOpenExternalLinks(False)
        self.current_track_label.linkActivated.connect(self.on_artist_track_clicked)
        
        # Create a frame for service buttons
        service_frame = QFrame()
        service_layout = QHBoxLayout(service_frame)
        service_layout.setContentsMargins(0, 10, 0, 10)
        
        # Create buttons for each service
        for service_name, service_info in self.services.items():
            btn = QPushButton(service_name)
            btn.setFixedSize(60, 30)
            btn.clicked.connect(lambda checked, 
                                s=service_name, 
                                t=track['track'], 
                                a=track['artist']: 
                                self.open_service(s, a, t))
            service_layout.addWidget(btn)
        
        service_layout.addStretch()
        
        # Update track information
        self.current_track = track

    def on_artist_track_clicked(self, link):
        """
        Handle clicks on artist or track name
        Customize this method as needed
        """
        if self.current_track:
            print(f"Clicked on {self.current_track['artist']} or {self.current_track['track']}")
            # Add your custom logic here, like opening artist page, etc.

    def open_service(self, service_name: str, artist: str, track: str):
        """Open the specified service's search results"""
        service = self.services.get(service_name)
        if service and 'url_template' in service:
            # Replace spaces with '+' for URL
            formatted_url = service['url_template'].format(
                artist.replace(' ', '+'), 
                track.replace(' ', '+')
            )
            QDesktopServices.openUrl(QUrl(formatted_url))

    def open_youtube(self, artist: str, track: str):
        """Custom implementation for YouTube"""
        self.open_service('YouTube', artist, track)

    def open_lastfm(self, artist: str, track: str):
        """Custom implementation for LastFM"""
        self.open_service('LastFM', artist, track)

    def open_rateyourmusic(self, artist: str, track: str):
        """Custom implementation for RateYourMusic"""
        self.open_service('RateYourMusic', artist, track)

    def open_spotify(self, artist: str, track: str):
        """Custom implementation for Spotify"""
        self.open_service('Spotify', artist, track)

    def open_discogs(self, artist: str, track: str):
        """Custom implementation for Discogs"""
        self.open_service('Discogs', artist, track)

    def open_allmusic(self, artist: str, track: str):
        """Custom implementation for AllMusic"""
        self.open_service('AllMusic', artist, track)

    def apply_theme(self, theme_name: str = 'Tokyo Night'):
        """Apply theme to the module"""
        theme = THEMES.get(theme_name, THEMES['Tokyo Night'])
        self.theme = theme
        
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {theme['bg']};
                color: {theme['fg']};
            }}
            QLabel {{
                color: {theme['fg']};
            }}
            QPushButton {{
                background-color: {theme['secondary_bg']};
                color: {theme['fg']};
                border: 1px solid {theme['border']};
                border-radius: 3px;
            }}
            QPushButton:hover {{
                background-color: {theme['button_hover']};
            }}
        """)

# This allows the module to be dynamically loaded
def get_module_class():
    return LastFMScrobbleModule