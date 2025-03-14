from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, 
                           QPushButton, QScrollArea, QLabel, QComboBox,
                           QGroupBox, QFrame, QSizePolicy)
from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
import requests
from bs4 import BeautifulSoup
import json
import re
from pathlib import Path
import time
import random
from typing import List, Dict, Optional, Tuple
import logging

from base_module import BaseModule

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WebPlayer(QFrame):
    """Widget for displaying embedded music players"""
    
    def __init__(self, parent=None, source_type="bandcamp", source_url=None, title="", artist=""):
        super().__init__(parent)
        self.source_type = source_type
        self.source_url = source_url
        self.title = title
        self.artist = artist
        
        # Setup web profile with specific settings for embedded players
        self.profile = QWebEngineProfile(f"Player-{random.randint(1000, 9999)}", self)
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
        
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Info section
        info_layout = QHBoxLayout()
        self.source_label = QLabel(f"[{self.source_type.upper()}]")
        self.title_label = QLabel(f"<b>{self.title}</b>")
        self.artist_label = QLabel(f"by {self.artist}")
        
        info_layout.addWidget(self.source_label)
        info_layout.addWidget(self.title_label)
        info_layout.addWidget(self.artist_label)
        info_layout.addStretch()
        
        # Web view for embedded player
        self.web_view = QWebEngineView()
        self.web_view.setMinimumHeight(300)
        self.web_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        page = QWebEnginePage(self.profile, self.web_view)
        self.web_view.setPage(page)
        
        # Add widgets to layout
        layout.addLayout(info_layout)
        layout.addWidget(self.web_view)
        
        # Set frame properties
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        
        # Load content if URL is provided
        if self.source_url:
            self.load_player()
    
    def load_player(self):
        """Load the appropriate player based on source type"""
        if not self.source_url:
            return
            
        if self.source_type == "bandcamp":
            # Create Bandcamp embedded player HTML
            html = f"""
            <iframe style="border: 0; width: 100%; height: 100%;" 
                    src="{self.source_url}/embeddable_player/size=large/tracklist=false/artwork=small" 
                    seamless></iframe>
            """
            self.web_view.setHtml(html)
            
        elif self.source_type == "soundcloud":
            # Create SoundCloud embedded player HTML
            html = f"""
            <iframe width="100%" height="100%" scrolling="no" frameborder="no" allow="autoplay"
                    src="https://w.soundcloud.com/player/?url={self.source_url}&color=%23ff5500&auto_play=false&hide_related=false&show_comments=false&show_user=true&show_reposts=false&show_teaser=true&visual=true">
            </iframe>
            """
            self.web_view.setHtml(html)
    
    def set_source(self, source_type, source_url, title="", artist=""):
        """Update the player with new source information"""
        self.source_type = source_type
        self.source_url = source_url
        self.title = title
        self.artist = artist
        
        self.source_label.setText(f"[{self.source_type.upper()}]")
        self.title_label.setText(f"<b>{self.title}</b>")
        self.artist_label.setText(f"by {self.artist}")
        
        self.load_player()


class MusicSearchModule(BaseModule):
    """Module for searching and displaying music from Bandcamp and SoundCloud"""
    
    def __init__(self, parent=None, theme='Tokyo Night'):
        self.search_results = []
        self.current_players = []
        super().__init__(parent, theme)
    
    def init_ui(self):
        """Initialize the user interface"""
        main_layout = QVBoxLayout(self)
        
        # Search controls
        search_layout = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter artist or album name...")
        self.search_input.returnPressed.connect(self.perform_search)
        
        self.source_selector = QComboBox()
        self.source_selector.addItems(["All", "Bandcamp", "SoundCloud"])
        
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.perform_search)
        
        search_layout.addWidget(self.search_input, 3)
        search_layout.addWidget(self.source_selector, 1)
        search_layout.addWidget(self.search_button, 1)
        
        # Results area
        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.results_container)
        
        # Status label
        self.status_label = QLabel("Enter a search term to find music")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Add layouts to main layout
        main_layout.addLayout(search_layout)
        main_layout.addWidget(self.status_label)
        main_layout.addWidget(self.scroll_area)
    
    def perform_search(self):
        """Handle search button click"""
        query = self.search_input.text().strip()
        if not query:
            self.status_label.setText("Please enter a search term")
            return
            
        self.status_label.setText(f"Searching for '{query}'...")
        self.search_results = []
        
        # Clear previous results
        self.clear_results()
        
        # Determine which sources to search
        source = self.source_selector.currentText().lower()
        
        if source in ["all", "bandcamp"]:
            self.search_bandcamp(query)
            
        if source in ["all", "soundcloud"]:
            self.search_soundcloud(query)
            
        # Update status
        if not self.search_results:
            self.status_label.setText(f"No results found for '{query}'")
        else:
            self.status_label.setText(f"Found {len(self.search_results)} results for '{query}'")
            self.display_results()
    
    def search_bandcamp(self, query):
        """Search for music on Bandcamp"""
        try:
            # Format search URL
            search_url = f"https://bandcamp.com/search?q={query.replace(' ', '+')}"
            
            # Send request with fake user agent to avoid being blocked
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(search_url, headers=headers)
            
            if response.status_code != 200:
                print(f"Error searching Bandcamp: Status code {response.status_code}")
                return
                
            # Parse HTML response
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find results - Bandcamp specific structure
            results = soup.select('li.searchresult')
            
            for result in results[:5]:  # Limit to 5 results
                try:
                    title_elem = result.select_one('.heading')
                    artist_elem = result.select_one('.subhead')
                    link_elem = result.select_one('a.artcont')
                    
                    if title_elem and artist_elem and link_elem:
                        title = title_elem.text.strip()
                        artist = artist_elem.text.strip()
                        url = link_elem['href']
                        
                        self.search_results.append({
                            "source": "bandcamp",
                            "title": title,
                            "artist": artist,
                            "url": url
                        })
                except Exception as e:
                    print(f"Error parsing Bandcamp result: {e}")
                    
        except Exception as e:
            print(f"Error searching Bandcamp: {e}")
    
    def search_soundcloud(self, query):
        """Search for music on SoundCloud"""
        try:
            # Format search URL
            search_url = f"https://soundcloud.com/search/sounds?q={query.replace(' ', '%20')}"
            
            # Send request with fake user agent to avoid being blocked
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(search_url, headers=headers)
            
            if response.status_code != 200:
                print(f"Error searching SoundCloud: Status code {response.status_code}")
                return
                
            # Parse HTML response
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract JSON data from page script (SoundCloud stores page data in JS objects)
            scripts = soup.find_all('script')
            
            # Find the script that contains track data
            data = None
            for script in scripts:
                if script.string and 'window.__sc_hydration' in script.string:
                    match = re.search(r'window\.__sc_hydration\s*=\s*(\[.+?\]);', script.string, re.DOTALL)
                    if match:
                        data = json.loads(match.group(1))
                        break
            
            if not data:
                print("Could not find SoundCloud track data in page")
                return
                
            # Extract track information from the hydration data
            tracks = []
            for item in data:
                if item.get('hydratable') == 'sound':
                    tracks.append(item.get('data', {}))
            
            # Process track results
            for track in tracks[:5]:  # Limit to 5 results
                try:
                    title = track.get('title', '')
                    user = track.get('user', {}).get('username', '')
                    track_url = track.get('permalink_url', '')
                    
                    self.search_results.append({
                        "source": "soundcloud",
                        "title": title,
                        "artist": user,
                        "url": track_url
                    })
                except Exception as e:
                    print(f"Error parsing SoundCloud result: {e}")
                    
        except Exception as e:
            print(f"Error searching SoundCloud: {e}")
    
    def clear_results(self):
        """Clear current results"""
        # Clear all widgets from results layout
        for player in self.current_players:
            self.results_layout.removeWidget(player)
            player.deleteLater()
        
        self.current_players = []
        
        # Clear any spacers
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            if item.spacerItem():
                self.results_layout.removeItem(item)
    
    def display_results(self):
        """Display search results as playable widgets"""
        for result in self.search_results:
            try:
                player = WebPlayer(
                    source_type=result["source"],
                    source_url=result["url"],
                    title=result["title"],
                    artist=result["artist"]
                )
                
                self.results_layout.addWidget(player)
                self.current_players.append(player)
                
            except Exception as e:
                print(f"Error creating player: {e}")
        
        # Add spacer at the end
        self.results_layout.addStretch()