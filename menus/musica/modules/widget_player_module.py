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
        
        # Setup web view with minimal configuration
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Info section
        info_layout = QHBoxLayout()
        self.source_label = QLabel(f"[{self.source_type.upper()}]")
        self.title_label = QLabel(f"<b>{self.title}</b>")
        self.artist_label = QLabel(f"by {self.artist}")
        
        info_layout.addWidget(self.source_label)
        info_layout.addWidget(self.title_label)
        info_layout.addWidget(self.artist_label)
        info_layout.addStretch()
        
        # Web view for embedded player - using standard configuration
        self.web_view = QWebEngineView()
        self.web_view.setMinimumHeight(300)
        self.web_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
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
            
        try:
            if self.source_type == "bandcamp":
                # Create Bandcamp embedded player HTML
                album_url = self.source_url
                
                # Verificar si la URL ya tiene el formato de reproductor embebido
                if "/embeddable_player/" not in album_url:
                    # Si es una URL de álbum o track, usamos esa URL directamente
                    iframe_src = album_url
                    
                    # Agregar parámetro para reproductor embebido si no está presente
                    if "/album/" in album_url or "/track/" in album_url:
                        iframe_src = f"{album_url}/embeddable_player/size=large/tracklist=false/artwork=small"
                else:
                    iframe_src = album_url
                
                if album_url:
                    html = f"""
                    <html>
                    <head>
                    <style>
                        body {{ margin: 0; padding: 0; overflow: hidden; }}
                        iframe {{ border: 0; width: 100%; height: 100%; }}
                    </style>
                    </head>
                    <body>
                    <iframe src="{iframe_src}" 
                            seamless allowfullscreen></iframe>
                    </body>
                    </html>
                    """
                    self.web_view.setHtml(html)
                    logger.info(f"Widget de Bandcamp cargado: {album_url}")
                
            # El resto del código para SoundCloud se mantiene igual
            elif self.source_type == "soundcloud":
                # Create SoundCloud embedded player HTML
                track_url = self.source_url
                
                if track_url:
                    html = f"""
                    <html>
                    <head>
                    <style>
                        body {{ margin: 0; padding: 0; overflow: hidden; }}
                        iframe {{ border: 0; width: 100%; height: 100%; }}
                    </style>
                    </head>
                    <body>
                    <iframe width="100%" height="100%" scrolling="no" frameborder="no" allow="autoplay"
                            src="https://w.soundcloud.com/player/?url={track_url}&color=%23ff5500&auto_play=false&hide_related=false&show_comments=false&show_user=true&show_reposts=false&show_teaser=true&visual=true">
                    </iframe>
                    </body>
                    </html>
                    """
                    self.web_view.setHtml(html)
                    logger.info(f"Widget de SoundCloud cargado: {track_url}")
        except Exception as e:
            logger.error(f"Error al cargar el reproductor: {e}")
            # Mostrar un mensaje de error en el widget
            self.web_view.setHtml(f"<html><body><p>Error al cargar el reproductor: {str(e)}</p></body></html>")
    
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
            self.status_label.setText("Por favor ingresa un término de búsqueda")
            return
            
        self.status_label.setText(f"Buscando '{query}'...")
        self.search_results = []
        
        # Clear previous results
        self.clear_results()
        
        # Determine which sources to search
        source = self.source_selector.currentText().lower()
        
        # Check if the input is a direct URL first
        if query.startswith("http"):
            if "bandcamp.com" in query and source in ["all", "bandcamp"]:
                self.add_direct_player("bandcamp", query)
            elif "soundcloud.com" in query and source in ["all", "soundcloud"]:
                self.add_direct_player("soundcloud", query)
            else:
                self.status_label.setText("URL proporcionada no compatible con las fuentes seleccionadas")
        else:
            # Perform search in selected sources
            if source in ["all", "bandcamp"]:
                self.search_bandcamp(query)
                
            if source in ["all", "soundcloud"]:
                self.search_soundcloud(query)
                
            # Display results
            if self.search_results:
                self.status_label.setText(f"Se encontraron {len(self.search_results)} resultados para '{query}'")
                self.display_results()
            else:
                self.status_label.setText(f"No se encontraron resultados para '{query}'")


    def add_direct_widget(self, source_type, url):
        """Add a widget directly from URL"""
        try:
            # Extract basic info from URL
            title = url.split("/")[-1].replace("-", " ").title() if source_type == "bandcamp" else "Track"
            artist = url.split("/")[-2].replace("-", " ").title() if source_type == "bandcamp" else "Artist"
            
            # Create player widget
            player = WebPlayer(
                source_type=source_type,
                source_url=url,
                title=title,
                artist=artist
            )
            
            self.results_layout.addWidget(player)
            self.current_players.append(player)
            
            self.status_label.setText(f"Widget de {source_type} cargado correctamente")
            
        except Exception as e:
            logger.error(f"Error creating player: {e}")
            self.status_label.setText(f"Error al crear el widget: {str(e)}")
    
    def search_bandcamp(self, query):
        """Search for music on Bandcamp"""
        try:
            # Format search URL
            search_url = f"https://bandcamp.com/search?q={query.replace(' ', '+')}"
            
            # Send request with fake user agent to avoid being blocked
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Referer": "https://bandcamp.com/",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Cache-Control": "max-age=0"
            }
            
            logger.info(f"Realizando búsqueda en Bandcamp: {search_url}")
            response = requests.get(search_url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"Error buscando en Bandcamp: Status code {response.status_code}")
                return
                
            # Parse HTML response
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find results - Bandcamp specific structure
            results = soup.select('li.searchresult')
            
            for result in results[:5]:  # Limit to 5 results
                try:
                    title_elem = result.select_one('.heading')
                    artist_elem = result.select_one('.subhead')
                    
                    # Buscar enlaces específicos a álbumes/tracks dentro del resultado
                    album_link = result.select_one('a[href*="/album/"], a[href*="/track/"]')
                    if not album_link:
                        link_elem = result.select_one('a.artcont')
                        url = link_elem['href'] if link_elem else None
                    else:
                        url = album_link['href']
                    
                    if title_elem and artist_elem and url:
                        title = title_elem.text.strip()
                        artist = artist_elem.text.strip()
                        
                        # Si la URL no tiene protocolo, añadirlo
                        if url.startswith('//'):
                            url = 'https:' + url
                        
                        self.search_results.append({
                            "source": "bandcamp",
                            "title": title,
                            "artist": artist,
                            "url": url
                        })
                        logger.info(f"Encontrado en Bandcamp: {title} - {artist} - URL: {url}")
                except Exception as e:
                    logger.error(f"Error analizando resultado de Bandcamp: {e}")
                    
        except Exception as e:
            logger.error(f"Error buscando en Bandcamp: {e}")
    

    def search_soundcloud(self, query):
        """Search for music on SoundCloud"""
        try:
            # Format search URL
            search_url = f"https://soundcloud.com/search/sounds?q={query.replace(' ', '%20')}"
            
            # Send request with fake user agent to avoid being blocked
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Referer": "https://soundcloud.com/",
                "Connection": "keep-alive"
            }
            
            logger.info(f"Realizando búsqueda en SoundCloud: {search_url}")
            response = requests.get(search_url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"Error buscando en SoundCloud: Status code {response.status_code}")
                return
                
            # Extract track URLs directly from the HTML using regex
            # This is more reliable than trying to parse complex JavaScript objects
            track_urls = re.findall(r'https://soundcloud\.com/[^"\'&]+', response.text)
            
            # Filter out duplicate URLs and navigation links
            seen_urls = set()
            filtered_urls = []
            
            for url in track_urls:
                # Skip navigation links and ensure it's a track/user URL
                if '/discover' in url or '/stream' in url or '/you' in url or '/upload' in url:
                    continue
                    
                # Normalize URL by removing query parameters
                base_url = url.split('?')[0]
                
                # Only add unique URLs
                if base_url not in seen_urls:
                    seen_urls.add(base_url)
                    filtered_urls.append(base_url)
            
            # Process the first 5 unique track URLs
            for url in filtered_urls[:5]:
                try:
                    # Extract artist and title from URL path
                    path_parts = url.replace('https://soundcloud.com/', '').split('/')
                    
                    if len(path_parts) >= 2:
                        artist = path_parts[0].replace('-', ' ').title()
                        title = path_parts[1].replace('-', ' ').title()
                    else:
                        artist = path_parts[0].replace('-', ' ').title()
                        title = "Track"
                        
                    self.search_results.append({
                        "source": "soundcloud",
                        "title": title,
                        "artist": artist,
                        "url": url
                    })
                    logger.info(f"Encontrado en SoundCloud: {title} - {artist}")
                except Exception as e:
                    logger.error(f"Error analizando resultado de SoundCloud: {e}")
                    
        except Exception as e:
            logger.error(f"Error buscando en SoundCloud: {e}")
    
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
                # Create a player for each result
                player = WebPlayer(
                    source_type=result["source"],
                    source_url=result["url"],
                    title=result["title"],
                    artist=result["artist"]
                )
                
                self.results_layout.addWidget(player)
                self.current_players.append(player)
                
            except Exception as e:
                logger.error(f"Error al crear reproductor: {e}")
        
        # Add spacer at the end
        self.results_layout.addStretch()


        
    def add_direct_player(self, source_type, url):
        """Add a player widget directly from a URL"""
        try:
            # Extract basic info from URL
            if source_type == "bandcamp":
                # Extraer información del artista y título del álbum/track
                if "/album/" in url:
                    album_name = url.split("/album/")[-1].replace("-", " ").title()
                    artist_name = url.split(".bandcamp.com")[0].split("//")[-1].replace("-", " ").title()
                    title = f"Album: {album_name}"
                elif "/track/" in url:
                    track_name = url.split("/track/")[-1].replace("-", " ").title()
                    artist_name = url.split(".bandcamp.com")[0].split("//")[-1].replace("-", " ").title()
                    title = f"Track: {track_name}"
                else:
                    parts = url.split("/")
                    artist_name = url.split(".bandcamp.com")[0].split("//")[-1].replace("-", " ").title()
                    title = "Artist Page"
            else:  # soundcloud
                parts = url.split("/")
                if len(parts) > 4:
                    artist_name = parts[3].replace("-", " ").title()
                    title = parts[4].replace("-", " ").title() if len(parts) > 4 else "Track"
                else:
                    artist_name = parts[3].replace("-", " ").title() if len(parts) > 3 else "Artist"
                    title = "Track"
            
            # Create player with direct URL
            player = WebPlayer(
                source_type=source_type,
                source_url=url,
                title=title,
                artist=artist_name
            )
            
            self.results_layout.addWidget(player)
            self.current_players.append(player)
            self.status_label.setText(f"Widget cargado desde URL directa: {source_type}")
            
        except Exception as e:
            logger.error(f"Error al crear reproductor desde URL: {e}")
            self.status_label.setText(f"Error al crear reproductor: {str(e)}")