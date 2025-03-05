import sys
import os
import subprocess
import requests
import logging
from base_module import BaseModule, THEMES
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, 
                             QLabel, QLineEdit, QMessageBox, QApplication, QFileDialog, QTableWidget, 
                             QTableWidgetItem, QHeaderView)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor, QTextDocument



# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MuspyArtistModule(BaseModule):
    def __init__(self, 
                 muspy_username=None, 
                 muspy_api_key=None, 
                 artists_file=None,
                 query_db_script_path=None,
                 search_mbid_script_path=None,
                 lastfm_username=None,
                 parent=None, 
                 db_path='music_database.db',
                 theme='Tokyo Night', 
                 *args, **kwargs):
        """
        Initialize the Muspy Artist Management Module
        
        Args:
            muspy_username (str, optional): Muspy username
            muspy_api_key (str, optional): Muspy API key
            artists_file (str, optional): Path to artists file
            query_db_script_path (str, optional): Path to MBID query script
            search_mbid_script_path (str, optional): Path to MBID search script
            parent (QWidget, optional): Parent widget
            theme (str, optional): UI theme
        """
        self.muspy_username = muspy_username
        self.muspy_api_key = muspy_api_key
        self.artists_file = artists_file
        self.query_db_script_path = query_db_script_path
        self.search_mbid_script_path = search_mbid_script_path
        self.lastfm_username = lastfm_username
        self.db_path = db_path

        self.available_themes = kwargs.pop('temas', [])
        self.selected_theme = kwargs.pop('tema_seleccionado', theme)        
        
        super().__init__(parent, theme)

    def init_ui(self):
        """Initialize the user interface for Muspy artist management"""
        # Main vertical layout
        main_layout = QVBoxLayout(self)

        # Top section with search
        top_layout = QHBoxLayout()
        
        self.artist_input = QLineEdit()
        self.artist_input.setPlaceholderText("Enter artist name")
        self.artist_input.returnPressed.connect(self.search_and_add_artist)
        top_layout.addWidget(self.artist_input)

        self.search_add_button = QPushButton("Search & Add to Muspy")
        self.search_add_button.clicked.connect(self.search_and_add_artist)
        top_layout.addWidget(self.search_add_button)

        main_layout.addLayout(top_layout)

        # Results area (will be replaced by table when getting releases)
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        main_layout.addWidget(self.results_text)

        # Bottom buttons layout
        bottom_layout = QHBoxLayout()
        
        self.load_artists_button = QPushButton("Load Artists")
        self.load_artists_button.clicked.connect(self.load_artists_from_file)
        bottom_layout.addWidget(self.load_artists_button)

        self.sync_artists_button = QPushButton("Sync Artists")
        self.sync_artists_button.clicked.connect(self.sync_artists_with_muspy)
        bottom_layout.addWidget(self.sync_artists_button)

        self.sync_lastfm_button = QPushButton("Sync Lastfm")
        self.sync_lastfm_button.clicked.connect(self.sync_lastfm_muspy)
        bottom_layout.addWidget(self.sync_lastfm_button)
        
        self.get_releases_button = QPushButton("Get Releases")
        self.get_releases_button.clicked.connect(self.get_muspy_releases)
        bottom_layout.addWidget(self.get_releases_button)

        main_layout.addLayout(bottom_layout)


    def load_artists_from_file(self):
        """Load artists from a text file"""
        if not self.artists_file:
            self.artists_file = QFileDialog.getOpenFileName(self, "Select Artists File", "", "Text Files (*.txt)")[0]
        
        if not self.artists_file:
            return

        try:
            with open(self.artists_file, 'r', encoding='utf-8') as f:
                self.artists = [line.strip() for line in f if line.strip()]
            
            self.results_text.clear()
            self.results_text.append(f"Loaded {len(self.artists)} artists from {self.artists_file}\n")

        except Exception as e:
            self.results_text.append(f"Error loading file: {e}\n")


    def search_and_add_artist(self):
        """Search for artist MBID and add to Muspy"""
        artist_name = self.artist_input.text().strip()
        if not artist_name:
            QMessageBox.warning(self, "Error", "Please enter an artist name")
            return

        # Ensure results_text is visible
        self.results_text.show()

        # Get MBID for the artist
        mbid = self.get_mbid_artist_searched(artist_name)
        
        if not mbid:
            QMessageBox.warning(self, "Error", f"Could not find MBID for {artist_name}")
            return
        
        # Add to Muspy
        self.add_artist_to_muspy(mbid, artist_name)

    def sync_artists_with_muspy(self):
        """Synchronize artists from file with Muspy"""
        if not hasattr(self, 'artists') or not self.artists:
            QMessageBox.warning(self, "Error", "No artists loaded. First load a file.")
            return

        self.results_text.clear()
        successful_adds = 0

        for artist_name in self.artists:
            mbid = self.get_mbid_artist_searched(artist_name)
            if self.add_artist_to_muspy(mbid):
                successful_adds += 1

        self.results_text.append(f"Synchronized {successful_adds}/{len(self.artists)} artists with Muspy\n")

    def get_mbid_artist_searched(self, artist_name):
        """
        Retrieve the MusicBrainz ID for a given artist
        
        Args:
            artist_name (str): Name of the artist to search
        
        Returns:
            str or None: MusicBrainz ID of the artist
        """
        if artist_name is None:
            return None
        
        try:
            # First attempt: query existing database
            if self.query_db_script_path:
                # Add full absolute paths
                full_db_path = os.path.expanduser(self.db_path)
                full_script_path = os.path.expanduser(self.query_db_script_path)
                
                # Print out the actual paths being used
                self.results_text.append(f"Attempting to run script with:")
                self.results_text.append(f"Script Path: {full_script_path}")
                self.results_text.append(f"DB Path: {full_db_path}")
                self.results_text.append(f"Artist: {artist_name}")

                mbid_result = subprocess.run(
                    ['python', self.query_db_script_path, "--db", self.db_path, "--artist", artist_name, "--mbid"], 
                    capture_output=True, 
                    text=True
                )
                
                # More detailed logging
                self.results_text.append(f"Return Code: {mbid_result.returncode}")
                self.results_text.append(f"STDOUT: {mbid_result.stdout}")
                self.results_text.append(f"STDERR: {mbid_result.stderr}")
                
                if mbid_result.returncode == 0 and mbid_result.stdout.strip():
                    return mbid_result.stdout.strip()

                # # Log stdout and stderr for debugging
                # if mbid_result.stdout:
                #     self.results_text.append(f"Query DB Script STDOUT: {mbid_result.stdout.strip()}")
                # if mbid_result.stderr:
                #     self.results_text.append(f"Query DB Script STDERR: {mbid_result.stderr.strip()}")
                
                # if mbid_result.returncode == 0 and mbid_result.stdout.strip():
                #     return mbid_result.stdout.strip()
            
            # Second attempt: search for MBID if first method fails
            if self.search_mbid_script_path:
                mbid_search_result = subprocess.run(
                    ['python', self.search_mbid_script_path, "--db", self.db_path,"--artist", artist_name], 
                    capture_output=True, 
                    text=True
                )
                
                # Log stdout and stderr for debugging
                if mbid_search_result.stdout:
                    self.results_text.append(f"MBID Search Script STDOUT: {mbid_search_result.stdout.strip()}")
                if mbid_search_result.stderr:
                    self.results_text.append(f"MBID Search Script STDERR: {mbid_search_result.stderr.strip()}")
                
                if mbid_search_result.returncode == 0 and mbid_search_result.stdout.strip():
                    return mbid_search_result.stdout.strip()
            
            return None
        
        except subprocess.TimeoutExpired:
            self.results_text.append("Script execution timed out")
        except PermissionError:
            self.results_text.append(f"Permission denied running script: {full_script_path}")
        except FileNotFoundError:
            self.results_text.append(f"Script or database file not found: {full_script_path} or {full_db_path}")
        except Exception as e:
            logging.error(f"Unexpected error getting MBID for {artist_name}: {e}")
            self.results_text.append(f"Unexpected error: {e}")
            return None
 
    def add_artist_to_muspy(self, mbid=None, artist_name=None):
        """
        Add/Follow an artist to Muspy using their MBID or name
        
        Args:
            mbid (str, optional): MusicBrainz ID of the artist
            artist_name (str, optional): Name of the artist for logging
        
        Returns:
            bool: True if artist was successfully added, False otherwise
        """
        if not self.muspy_username or not self.muspy_api_key:
            QMessageBox.warning(self, "Error", "Muspy configuration not available")
            return False

        try:
            # Ensure results_text is visible and clear
            self.results_text.show()
            self.results_text.clear()

            # Determine the URL based on whether MBID is provided
            if mbid:
                # Follow a specific artist by MBID
                url = f"https://muspy.com/api/1/artists/{self.muspy_username}/{mbid}"
                method = 'PUT'
                data = {}

            headers = {
                'Authorization': f'Token {self.muspy_api_key}',
                'Content-Type': 'application/json'
            }
            
            # Use the appropriate request method
            if method == 'PUT':
                response = requests.put(url, headers=headers, json=data)
            else:
                response = requests.post(url, headers=headers, json=data)
            
            if response.status_code in [200, 201]:
                message = f"Artist {artist_name or 'Unknown'} added to Muspy"
                self.results_text.append(message)
                QMessageBox.information(self, "Success", message)
                return True
            else:
                message = f"Could not add {artist_name or 'Unknown'} to Muspy: {response.text}"
                self.results_text.append(message)
                QMessageBox.warning(self, "Error", message)
                return False
        except Exception as e:
            message = f"Error adding to Muspy: {e}"
            QMessageBox.warning(self, "Error", message)
            return False

    def sync_lastfm_muspy(self):
        """Synchronize Last.fm artists with Muspy"""
        if not self.lastfm_username:
            QMessageBox.warning(self, "Error", "Last.fm username not configured")
            return

        try:
            # Import artists via last.fm
            url = f"https://muspy.com/api/1/artists/{self.muspy_username}"
            method = 'PUT'
            data = {
                'import': 'last.fm',
                'username': self.lastfm_username,
                'count': 10,
                'period': 'overall'
            }

            headers = {
                'Authorization': f'Token {self.muspy_api_key}',
                'Content-Type': 'application/json'
            }
            
            # Use the appropriate request method
            if method == 'PUT':
                response = requests.put(url, headers=headers, json=data)
            else:
                response = requests.post(url, headers=headers, json=data)
            
            if response.status_code in [200, 201]:
                self.results_text.append(f"Synchronized artists from Last.fm account {self.lastfm_username}\n")
                return True
            else:
                self.results_text.append(f"Could not sync Last.fm artists: {response.text}\n")
                return False
        except Exception as e:
            self.results_text.append(f"Error syncing with Muspy: {e}\n")
            return False

    def get_muspy_releases(self):
        """
        Retrieve upcoming releases from Muspy for the current user
        
        Displays releases in a QTableWidget
        """
        if not self.muspy_username or not self.muspy_api_key:
            QMessageBox.warning(self, "Error", "Muspy configuration not available")
            return

        try:
            url = "https://muspy.com/api/1/releases/upcoming"
            headers = {
                'Authorization': f'Token {self.muspy_api_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                releases = response.json()
                
                if not releases:
                    QMessageBox.information(self, "No Releases", "No upcoming releases in Muspy")
                    return
                
                # Display releases in table
                self.display_releases_table(releases)
            else:
                QMessageBox.warning(self, "Error", f"Error retrieving releases: {response.text}")
        
        except Exception as e:
            QMessageBox.warning(self, "Connection Error", f"Connection error with Muspy: {e}")


    def display_releases_table(self, releases):
        """
        Display releases in a QTableWidget for better rendering
        """
        # First, clear any existing table
        for i in reversed(range(self.layout().count())): 
            item = self.layout().itemAt(i)
            if item is not None:
                widget = item.widget()
                if widget is not None and isinstance(widget, QTableWidget):
                    self.layout().removeItem(item)
                    widget.deleteLater()

        # Create the table
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(['Artist', 'Disambiguation', 'Title', 'Date', 'Type'])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        # Configure number of rows
        table.setRowCount(len(releases))
        
        # Fill the table
        for row, release in enumerate(releases):
            artist = release.get('artist', {})
            
            # Create items for each column
            table.setItem(row, 0, QTableWidgetItem(artist.get('name', 'Unknown')))
            table.setItem(row, 1, QTableWidgetItem(artist.get('disambiguation', '')))
            table.setItem(row, 2, QTableWidgetItem(release.get('title', 'Untitled')))
            table.setItem(row, 3, QTableWidgetItem(release.get('date', 'No date')))
            table.setItem(row, 4, QTableWidgetItem(release.get('type', 'Unknown')))
        
        # Hide the text edit and add the table to the layout
        self.results_text.hide()
        # Insert the table just above the bottom buttons
        self.layout().insertWidget(self.layout().count() - 1, table)
        return table



def main():
    """Main function to run the Muspy Artist Management Module"""
    app = QApplication(sys.argv)
    
    # Parse command-line arguments
    muspy_username = None
    muspy_api_key = None
    artists_file = None
    query_db_script_path = None
    search_mbid_script_path = None
    db_path = None
    for arg in sys.argv[1:]:
        if arg.startswith('--muspy-username='):
            muspy_username = arg.split('=')[1]
        elif arg.startswith('--muspy-api-key='):
            muspy_api_key = arg.split('=')[1]
        elif arg.startswith('--artists-file='):
            artists_file = arg.split('=')[1]
        elif arg.startswith('--query-db-script-path='):
            query_db_script_path = arg.split('=')[1]
        elif arg.startswith('--search-mbid-script-path='):
            search_mbid_script_path = arg.split('=')[1]
        elif arg.startswith('--lastfm-username='):
            lastfm_username = arg.split('=')[1]
        elif arg.startswith('--db-path='):
            db_path = arg.split('=')[1]

    # Create module instance
    module = MuspyArtistModule(
        muspy_username=muspy_username, 
        muspy_api_key=muspy_api_key,
        artists_file=artists_file,
        query_db_script_path=query_db_script_path,
        search_mbid_script_path=search_mbid_script_path,
        lastfm_username=lastfm_username,
        db_path=db_path
    )
    module.show()
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()






    