import os
import sys
import json
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk  # Necesitamos añadir esta importación
import subprocess
import platform
import re

# Path to your music library JSON file
MUSIC_LIBRARY_PATH = "/home/huan/.music_library_index.json"

# Define preferred applications (can be customized)
MUSIC_PLAYERS = {
    'Linux': ['deadbeef', 'rhythmbox', 'audacious', 'vlc'],
    'Windows': ['wmplayer', 'musicbee', 'foobar2000'],
    'Darwin': ['iTunes', 'Music']
}

FILE_MANAGERS = {
    'Linux': ['thunar', 'nautilus', 'dolphin', 'pcmanfm'],
    'Windows': ['explorer'],
    'Darwin': ['Finder']
}

def find_available_app(app_list):
    """Find the first available application from the list."""
    for app in app_list:
        try:
            # Check if the application is available in the system path
            subprocess.call([app, '--help'], 
                            stdout=subprocess.DEVNULL, 
                            stderr=subprocess.DEVNULL)
            return app
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    return None

def open_with_default_app(path, is_folder=False):
    """
    Open file or folder using the most appropriate method for the current platform.
    
    :param path: Path to the file or folder to open
    :param is_folder: True if path is a folder, False if it's a file
    """
    system = platform.system()
    
    # Ensure path exists
    if not os.path.exists(path):
        print(f"Path does not exist: {path}")
        return False
    
    try:
        # Platform-specific opening methods
        if system == 'Darwin':  # macOS
            if is_folder:
                subprocess.call(['open', path])
            else:
                subprocess.call(['open', '-a', 'Music', path])
            return True
        
        elif system == 'Windows':
            if is_folder:
                os.startfile(path)
            else:
                # Try to find a default music player
                music_player = find_available_app(MUSIC_PLAYERS['Windows'])
                if music_player:
                    subprocess.Popen([music_player, path])
                else:
                    os.startfile(path)
            return True
        
        elif system == 'Linux':
            # Find appropriate applications
            if is_folder:
                file_manager = find_available_app(FILE_MANAGERS['Linux'])
                if file_manager:
                    subprocess.Popen([file_manager, path])
                else:
                    subprocess.Popen(['xdg-open', path])
            else:
                music_player = find_available_app(MUSIC_PLAYERS['Linux'])
                if music_player:
                    subprocess.Popen([music_player, path])
                else:
                    subprocess.Popen(['xdg-open', path])
            return True
        
        else:
            print(f"Unsupported operating system: {system}")
            return False
    
    except Exception as e:
        print(f"Error opening {path}: {e}")
        return False

class MusicLibrarySearchApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Music Library Search")
        self.root.geometry("1600x800")
        self.root.configure(bg='#14141e')

        # Load music library
        self.load_library()

        # Create search frame
        self.create_search_frame()

        # Create results listbox
        self.create_results_list()

        # Create details text frame
        self.create_details_frame()

        # Keyboard shortcuts
        self.add_keyboard_shortcuts()

        # Focus on search entry when opening
        self.search_entry.focus_set()

        # Variable para mantener referencia a la imagen
        self.current_photo = None

    def load_library(self):
        """Load the music library from JSON file."""
        try:
            with open(MUSIC_LIBRARY_PATH, 'r', encoding='utf-8') as file:
                self.library = json.load(file)
        except Exception as e:
            print(f"Error loading library: {e}")
            self.library = []

    def create_search_frame(self):
        """Create search input frame."""
        search_frame = tk.Frame(self.root, bg='#14141e')
        search_frame.pack(pady=(10, 10), padx=5, fill=tk.X)

        # Play button
        play_button = tk.Button(search_frame, 
                                text="▶ Reproducir", 
                                command=self.play_selected_album, 
                                bg='#1974D2', 
                                fg='white')
        play_button.pack(side=tk.LEFT, padx=(0, 10))

        # Open Folder button
        open_folder_button = tk.Button(search_frame, 
                                       text="📁 Abrir Carpeta", 
                                       command=self.open_selected_folder, 
                                       bg='#f8bd9a', 
                                       fg='black')
        open_folder_button.pack(side=tk.LEFT, padx=(0, 10))

        # Search entry
        self.search_entry = tk.Entry(search_frame, 
                                     bg='#cba6f7', 
                                     fg='black', 
                                     font=('Arial', 12), 
                                     insertbackground='black', 
                                     width=50)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        # Bind events
        self.search_entry.bind("<KeyRelease>", self.update_results)
        self.search_entry.bind("<Return>", self.update_results)

    def create_results_list(self):
        """Create results listbox."""
        self.result_list = tk.Listbox(self.root, 
                                      width=50, 
                                      height=20, 
                                      font=('Arial', 12), 
                                      bg='#14141e', 
                                      fg='white')
        self.result_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.result_list.bind("<<ListboxSelect>>", self.on_select)

    def create_details_frame(self):
        """Create frame for details and cover art."""
        # Frame principal para detalles
        self.details_frame = tk.Frame(self.root, bg='#14141e')
        self.details_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Frame para la imagen
        self.cover_frame = tk.Label(self.details_frame, bg='#14141e')
        self.cover_frame.pack(side=tk.TOP, pady=10)

        # Text area para los detalles
        self.details_text = tk.Text(self.details_frame,
                                  width=80,
                                  height=10,
                                  wrap=tk.WORD,
                                  bg='#14141e',
                                  fg='white',
                                  font=('Arial', 12))
        self.details_text.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    def find_cover_image(self, album_path):
        """Find cover image in album directory."""
        try:
            disc1_path = os.path.join(album_path, "Disc 1")
            if not os.path.exists(disc1_path):
                return None

            # Lista de posibles nombres de archivo
            cover_names = ['cover', 'folder', 'front', 'artwork', 'albumart']
            image_extensions = ['.jpg', '.jpeg', '.png']

            # Primero buscar nombres específicos
            for name in cover_names:
                for ext in image_extensions:
                    file_path = os.path.join(disc1_path, name + ext)
                    if os.path.exists(file_path):
                        return file_path

            # Si no se encuentra, buscar cualquier imagen
            for file in os.listdir(disc1_path):
                if any(file.lower().endswith(ext) for ext in image_extensions):
                    return os.path.join(disc1_path, file)

            return None
        except Exception as e:
            print(f"Error finding cover image: {e}")
            return None
  
    def display_cover_image(self, image_path):
        """Display cover image in the cover frame."""
        try:
            if image_path and os.path.exists(image_path):
                # Cargar y redimensionar la imagen
                image = Image.open(image_path)
                # Mantener la proporción de aspecto
                max_size = (300, 300)
                image.thumbnail(max_size, Image.Resampling.LANCZOS)
                
                # Convertir a PhotoImage
                photo = ImageTk.PhotoImage(image)
                
                # Mantener referencia a la imagen
                self.current_photo = photo
                
                # Mostrar la imagen
                self.cover_frame.configure(image=photo)
            else:
                # Si no hay imagen, limpiar el frame
                self.cover_frame.configure(image='')
                self.current_photo = None
        except Exception as e:
            print(f"Error displaying cover image: {e}")
            self.cover_frame.configure(image='')
            self.current_photo = None

    def get_selected_album(self):
        """Get the selected album from the results list."""
        selection = self.result_list.curselection()
        if not selection:
            return None

        # Get the selected item's text
        selected_text = self.result_list.get(selection[0])
        
        # Find the corresponding album
        for album in self.library:
            display_text = f"{album['artist']} - {album['album']} ({album.get('date', 'No date')})"
            if display_text == selected_text:
                return album
        
        return None

    def play_selected_album(self):
        """Play the selected album using the system's default music player."""
        album = self.get_selected_album()
        if album and 'path' in album:
            # Try to open the album's path
            open_with_default_app(album['path'], is_folder=False)

    def open_selected_folder(self):
        """Open the folder of the selected album in the file manager."""
        album = self.get_selected_album()
        if album and 'path' in album:
            # Open the directory containing the album
            folder_path = os.path.dirname(album['path'])
            open_with_default_app(folder_path, is_folder=True)

    def update_results(self, event=None):
        """Update search results based on query."""
        query = self.search_entry.get().lower()
        
        # Clear previous results
        self.result_list.delete(0, tk.END)
        
        # Search through library
        for album in self.library:
            # Check if query matches any field
            if (query in album['artist'].lower() or 
                query in album['album'].lower() or 
                query in album.get('label', '').lower() or 
                query in album.get('date', '').lower()):
                
                # Format display string
                display = f"{album['artist']} - {album['album']} ({album.get('date', 'No date')})"
                self.result_list.insert(tk.END, display)

    def on_select(self, event):
        """Display details of selected album."""
        album = self.get_selected_album()
        if album:
            # Clear previous details
            self.details_text.delete(1.0, tk.END)
            
            # Display album details
            details = (f"Artist: {album['artist']}\n"
                      f"Album: {album['album']}\n"
                      f"Date: {album.get('date', 'Unknown')}\n"
                      f"Label: {album.get('label', 'Unknown')}\n"
                      f"Path: {album.get('path', 'Unknown')}")
            
            self.details_text.insert(tk.END, details)

            # Buscar y mostrar la imagen de portada
            if 'path' in album:
                cover_path = self.find_cover_image(os.path.dirname(album['path']))
                self.display_cover_image(cover_path)

    # def add_keyboard_shortcuts(self):
    #     """Add keyboard shortcuts."""
    #     self.root.bind("<Control-f>", lambda e: self.search_entry.focus_set())
    #     self.root.bind("<Control-p>", lambda e: self.play_selected_album())
    #     self.root.bind("<Control-o>", lambda e: self.open_selected_folder())
    #     self.root.bind("<Control-a>", self.select_all)

    def add_keyboard_shortcuts(self):
        """Add keyboard shortcuts."""
        # Control + F para focus en búsqueda
        self.root.bind("<Control-f>", lambda e: self.search_entry.focus_set())
        # Control + O para abrir carpeta
        self.root.bind("<Control-o>", lambda e: self.open_selected_folder())
        self.root.bind("<Control-a>", self.select_all)
        
        # Asegurarse de que estos atajos funcionen también cuando el foco está en el listbox
        self.result_list.bind("<Control-f>", lambda e: self.search_entry.focus_set())
        #self.result_list.bind("<Control-o>", lambda e: self.open_selected_folder())
        self.result_list.bind("<Return>", lambda e: self.play_selected_album())

    def select_all(self, event=None):
        """Select all text in the search entry."""
        self.search_entry.select_range(0, tk.END)
        return "break"

def main():
    root = tk.Tk()
    app = MusicLibrarySearchApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()