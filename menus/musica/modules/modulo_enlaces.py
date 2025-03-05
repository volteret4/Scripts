import sys
import os
import subprocess
import json
from base_module import BaseModule, THEMES
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, 
                             QLabel, QLineEdit, QMessageBox, QApplication, QTableWidget, 
                             QTableWidgetItem, QHeaderView)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor, QIcon
import musicbrainzngs
from datetime import datetime, date

class MusicBrainzReleasesModule(BaseModule):
    def __init__(self, parent=None, theme='Tokyo Night', *args, **kwargs):
        """
        Initialize the MusicBrainz Releases Module
        
        Args:
            parent (QWidget, optional): Parent widget. Defaults to None.
            theme (str, optional): UI theme. Defaults to 'Tokyo Night'.
        """
        # Configure MusicBrainz
        musicbrainzngs.set_useragent("MusicReleasesTracker", "1.0", "your_email@example.com")

        self.available_themes = kwargs.pop('temas', [])
        self.selected_theme = kwargs.pop('tema_seleccionado', theme)        
        
        super().__init__(parent, theme)

    def init_ui(self):
        """Initialize the user interface for MusicBrainz releases search"""
        layout = QVBoxLayout(self)

        # Search input and button layout
        search_layout = QHBoxLayout()
        
        self.artist_input = QLineEdit()
        self.artist_input.setPlaceholderText("Enter artist name")
        self.artist_input.returnPressed.connect(self.search_artist_releases)
        search_layout.addWidget(self.artist_input)

        self.search_button = QPushButton("Search Releases")
        self.search_button.clicked.connect(self.search_artist_releases)
        search_layout.addWidget(self.search_button)

        layout.addLayout(search_layout)

        # Results table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(7)  # In DB, Checked, Title, Date, Type, Label, Links
        self.results_table.setHorizontalHeaderLabels(["In DB", "Checked", "Title", "Date", "Type", "Label", "Links"])
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        # Make first two columns narrower
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.results_table)

    def run_external_script(self, script_path, args):
        """
        Run an external Python script with given arguments
        
        Args:
            script_path (str): Full path to the script
            args (list): List of arguments to pass to the script
        
        Returns:
            str: Output of the script
        """
        try:
            # Construct full command
            full_command = [sys.executable, script_path] + args
            
            # Run the script and capture output
            result = subprocess.run(full_command, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            QMessageBox.warning(self, "Script Error", f"Error running script: {e}")
            return ""

    def search_artist_releases(self):
        """Search for artist releases in MusicBrainz"""
        artist_name = self.artist_input.text().strip()
        if not artist_name:
            QMessageBox.warning(self, "Error", "Please enter an artist name")
            return

        # First, check albums in local database
        db_albums_output = self.run_external_script(
            os.path.expanduser("~/Scripts/menus/musica/base_datos/tools/consultar_items_db.py"),
            ["--db", os.path.expanduser("~/Scripts/MOODE.sqlite"), "--artist", artist_name, "--artist-albums"]
        )

        # Parse database albums
        try:
            db_albums = json.loads(db_albums_output) if db_albums_output else []
        except json.JSONDecodeError:
            db_albums = []

        # Search MusicBrainz for releases
        releases = self.search_musicbrainz_releases(artist_name)
        
        # Display results
        self.display_releases(artist_name, releases, db_albums)

    def search_musicbrainz_releases(self, artist_name):
        """
        Search for upcoming releases for a given artist in MusicBrainz
        
        Args:
            artist_name (str): Name of the artist to search
        
        Returns:
            list: Formatted list of releases
        """
        try:
            # Search for artist ID
            result = musicbrainzngs.search_artists(artist=artist_name)
            
            if not result['artist-list']:
                QMessageBox.warning(self, "Error", f"Artist {artist_name} not found in MusicBrainz")
                return []

            artist_id = result['artist-list'][0]['id']

            # Search releases
            releases = musicbrainzngs.search_releases(artist=artist_name)
            
            formatted_releases = []
            for release in releases.get('release-list', []):
                # Get record label
                labels = [label.get('name', 'Unknown') for label in release.get('label-info-list', [])]
                
                formatted_releases.append({
                    'title': release.get('title', 'Unknown Title'),
                    'date': release.get('date', 'Date Not Confirmed'),
                    'type': release.get('release-group', {}).get('type', 'Unknown Type'),
                    'label': ', '.join(labels) if labels else 'Label Not Specified',
                    'url': release.get('url-rels', [{}])[0].get('target', '') if release.get('url-rels') else ''
                })
            
            return formatted_releases

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error searching MusicBrainz: {e}")
            return []

    def get_album_links(self, artist_name, album_name):
        """
        Get album links from local database
        
        Args:
            artist_name (str): Name of the artist
            album_name (str): Name of the album
        
        Returns:
            dict: Links to various music platforms
        """
        links_output = self.run_external_script(
            os.path.expanduser("~/Scripts/menus/musica/base_datos/tools/consultar_items_db.py"),
            ["--db", os.path.expanduser("~/Scripts/MOODE.sqlite"), 
             "--artist", artist_name, "--album", album_name, "--links"]
        )

        try:
            return json.loads(links_output)
        except json.JSONDecodeError:
            return {}

    def display_releases(self, artist_name, releases, db_albums):
        """
        Display releases in the table
        
        Args:
            artist_name (str): Name of the artist
            releases (list): List of release dictionaries
            db_albums (list): List of albums from local database
        """
        # Clear existing table
        self.results_table.setRowCount(0)

        if not releases:
            QMessageBox.information(self, "No Results", f"No releases found for {artist_name}")
            return

        # Set number of rows
        self.results_table.setRowCount(len(releases))

        # Current date for comparison
        today = date.today()

        for row, release in enumerate(releases):
            # Check if album is in local database
            in_db = False
            for db_album in db_albums:
                if release['title'] == db_album[0]:
                    in_db = True
                    break

            # Create "In DB" icon
            in_db_item = QTableWidgetItem()
            in_db_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            if in_db:
                in_db_item.setBackground(QColor(200, 255, 200))
                in_db_item.setIcon(QIcon.fromTheme("dialog-ok"))  # Requires system icon theme

            # Get album links
            album_links = self.get_album_links(artist_name, release['title']) if in_db else {}

            # Create links item
            links_item = QTableWidgetItem()
            links_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            if album_links:
                # Combine all links
                link_text = " | ".join(f"{platform}: {url}" for platform, url in album_links.items())
                links_item.setText(link_text)

            # Checked column (empty for now, could be used for manual tracking)
            checked_item = QTableWidgetItem()
            checked_item.setFlags(Qt.ItemFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled))

            # Title
            title_item = QTableWidgetItem(release.get('title', 'No Title'))
            
            # Date
            date_str = release.get('date', 'No Date')
            date_item = QTableWidgetItem(date_str)
            
            # Type
            type_item = QTableWidgetItem(release.get('type', 'Unknown'))
            
            # Label
            label_item = QTableWidgetItem(release.get('label', 'Label Not Specified'))

            # Highlight future releases in green
            try:
                if date_str != 'No Date':
                    release_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    if release_date > today:
                        for item in [title_item, date_item, type_item, label_item]:
                            item.setBackground(QColor(200, 255, 200))
            except ValueError:
                # Handle unexpected date formats
                pass

            # Add items to table
            self.results_table.setItem(row, 0, in_db_item)
            self.results_table.setItem(row, 1, checked_item)
            self.results_table.setItem(row, 2, title_item)
            self.results_table.setItem(row, 3, date_item)
            self.results_table.setItem(row, 4, type_item)
            self.results_table.setItem(row, 5, label_item)
            self.results_table.setItem(row, 6, links_item)

def main():
    """Main function to run the application"""
    app = QApplication(sys.argv)
    
    # Create module instance
    module = MusicBrainzReleasesModule()
    module.show()
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()