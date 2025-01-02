import os
import sys
import json
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk  # Necesitamos añadir esta importación
import subprocess
import platform
import re
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen import File 


# Path to your music library JSON file
MUSIC_LIBRARY_PATH = "/home/huan/.music_library_index.json"
RUTA_LIBRERIA="/mnt/NFS/moode/moode"

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

# def create_music_index(self):
#     """Crear un índice de la biblioteca musical usando mutagen para extraer metadatos de los archivos FLAC"""
#     print("Generando índice de música... (esto puede tardar unos minutos)")
#     music_index = []
    
#     for base_path in self.base_paths:
#         # Buscar archivos FLAC en la estructura
#         for root, dirs, files in os.walk(base_path):
#             for file in files:
#                 if file.lower().endswith('.flac'):
#                     flac_file_path = os.path.join(root, file)
#                     try:
#                         # Usar mutagen para leer los metadatos del archivo FLAC
#                         audio_file = FLAC(flac_file_path)
                        
#                         # Extraer los metadatos: artista, álbum, fecha, sello discográfico
#                         artist = audio_file.get('artist', ['Desconocido'])[0]
#                         album = audio_file.get('album', ['Desconocido'])[0]
#                         date = audio_file.get('date', ['Desconocida'])[0]
#                         label = audio_file.get('label', ['Desconocido'])[0]
                        
#                         # Verificar si ya existe en el índice
#                         if not any(item['path'] == flac_file_path for item in music_index):
#                             music_index.append({
#                                 'artist': artist,
#                                 'album': album,
#                                 'date': date,
#                                 'label': label,
#                                 'path': flac_file_path
#                             })
#                     except Exception as e:
#                         print(f"Error al procesar {flac_file_path}: {e}")
    
#     # Guardar índice en el atributo de la clase
#     self.music_index = music_index  # Guardamos el índice en self.music_index
#     with open(self.index_file, 'w') as f:
#         json.dump(music_index, f, indent=2)
    
    return music_index
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

    def create_music_index(self, force_update=False):
        """
        Crear o actualizar el índice de la biblioteca musical por disco.
        
        Args:
            force_update (bool): Si es True, fuerza la actualización completa del índice
        """
        from datetime import datetime
        import os.path
        
        # Verificar si necesitamos actualizar
        need_update = force_update
        if not need_update and os.path.exists(MUSIC_LIBRARY_PATH):
            # Verificar la fecha de última modificación del archivo
            last_modified = datetime.fromtimestamp(os.path.getmtime(MUSIC_LIBRARY_PATH))
            today = datetime.now()
            if last_modified.date() < today.date():
                need_update = True
        
        # Cargar índice existente si existe
        existing_index = {}
        if os.path.exists(MUSIC_LIBRARY_PATH) and not force_update:
            try:
                with open(MUSIC_LIBRARY_PATH, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                    # Convertir la lista a diccionario usando la ruta como clave
                    existing_index = {item['path']: item for item in existing_data}
            except Exception as e:
                print(f"Error loading existing index: {e}")
                existing_index = {}
        
        if not need_update and existing_index:
            print("El índice está actualizado")
            self.library = list(existing_index.values())
            return
        
        print("Actualizando índice de música...")
        music_index = {}
        
        for root, dirs, files in os.walk(RUTA_LIBRERIA):
            # Verificar si estamos en un directorio "Disc X"
            if os.path.basename(root).startswith("Disc "):
                try:
                    # Tomar el primer archivo FLAC para obtener los metadatos
                    flac_files = [f for f in files if f.lower().endswith('.flac')]
                    if not flac_files:
                        continue
                    
                    sample_file = os.path.join(root, flac_files[0])
                    audio_file = FLAC(sample_file)
                    
                    # Extraer los metadatos
                    artist = audio_file.get('artist', ['Desconocido'])[0]
                    album = audio_file.get('album', ['Desconocido'])[0]
                    date = audio_file.get('date', ['Desconocida'])[0]
                    label = audio_file.get('label', ['Desconocido'])[0]
                    
                    # Usar el directorio padre como clave (contiene todos los discos del álbum)
                    album_dir = os.path.dirname(root)
                    
                    if album_dir not in music_index:
                        # Verificar si ya existe en el índice anterior
                        if album_dir in existing_index and not force_update:
                            music_index[album_dir] = existing_index[album_dir]
                        else:
                            music_index[album_dir] = {
                                'artist': artist,
                                'album': album,
                                'date': date,
                                'label': label,
                                'path': album_dir,
                                'discs': []
                            }
                    
                    # Añadir información del disco
                    disc_number = os.path.basename(root).split()[1]
                    if disc_number not in music_index[album_dir]['discs']:
                        music_index[album_dir]['discs'].append(disc_number)
                    
                except Exception as e:
                    print(f"Error al procesar {root}: {e}")
        
        # Convertir el diccionario a lista para mantener el formato original
        final_index = list(music_index.values())
        
        # Guardar el índice actualizado
        with open(MUSIC_LIBRARY_PATH, 'w', encoding='utf-8') as f:
            json.dump(final_index, f, indent=2)
        
        # Actualizar la biblioteca en memoria
        self.library = final_index

    def load_library(self):
        """Load the music library from JSON file and sort it."""
        try:
            if not os.path.exists(MUSIC_LIBRARY_PATH):
                self.create_music_index()
            else:
                with open(MUSIC_LIBRARY_PATH, 'r', encoding='utf-8') as file:
                    self.library = json.load(file)
                    
                    # Ordenar la biblioteca al cargarla
                    self.library.sort(key=lambda x: f"{x['artist'].lower()} - {x['album'].lower()}")
                    
                # Verificar si necesita actualización por fecha
                from datetime import datetime
                last_modified = datetime.fromtimestamp(os.path.getmtime(MUSIC_LIBRARY_PATH))
                if last_modified.date() < datetime.now().date():
                    print("Índice desactualizado, actualizando...")
                    self.create_music_index()
                    
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
            # Primero buscar en el directorio del álbum
            cover_names = ['cover', 'folder', 'front', 'artwork', 'albumart']
            image_extensions = ['.jpg', '.jpeg', '.png']

            # Buscar en el directorio del álbum y en sus subdirectorios inmediatos
            search_paths = [album_path]
            # Añadir subdirectorios que empiecen con "Disc"
            for item in os.listdir(album_path):
                if item.startswith("Disc ") and os.path.isdir(os.path.join(album_path, item)):
                    search_paths.append(os.path.join(album_path, item))

            # Buscar en todas las rutas
            for search_path in search_paths:
                # Primero buscar nombres específicos
                for name in cover_names:
                    for ext in image_extensions:
                        file_path = os.path.join(search_path, name + ext)
                        if os.path.exists(file_path):
                            print(f"Found cover image: {file_path}")  # Debug
                            return file_path

                # Si no se encuentra, buscar cualquier imagen
                for file in os.listdir(search_path):
                    if any(file.lower().endswith(ext) for ext in image_extensions):
                        file_path = os.path.join(search_path, file)
                        print(f"Found generic image: {file_path}")  # Debug
                        return file_path

            print("No cover image found")  # Debug
            return None
        except Exception as e:
            print(f"Error finding cover image: {e}")
            return None

    def display_cover_image(self, image_path):
        """Display cover image in the cover frame."""
        try:
            if image_path and os.path.exists(image_path):
                print(f"Loading image from: {image_path}")  # Debug
                # Cargar y redimensionar la imagen
                image = Image.open(image_path)
                
                # Obtener dimensiones originales
                width, height = image.size
                print(f"Original dimensions: {width}x{height}")  # Debug
                
                # Calcular nueva dimensión manteniendo proporción
                max_size = (500, 500)
                ratio = min(max_size[0]/width, max_size[1]/height)
                new_size = (int(width * ratio), int(height * ratio))
                print(f"New dimensions: {new_size}")  # Debug
                
                # Redimensionar
                image = image.resize(new_size, Image.Resampling.LANCZOS)
                
                # Convertir a PhotoImage
                photo = ImageTk.PhotoImage(image)
                
                # Mantener referencia a la imagen
                self.current_photo = photo
                
                # Mostrar la imagen
                self.cover_frame.configure(image=photo)
                print("Image displayed successfully")  # Debug
            else:
                print(f"Invalid image path: {image_path}")  # Debug
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
        """Update search results based on query and sort alphabetically."""
        query = self.search_entry.get().lower()
        
        # Clear previous results
        self.result_list.delete(0, tk.END)
        
        # Create a list to store matching albums with their display strings
        matching_albums = []
        
        # Search through library and create display strings
        for album in self.library:
            # Check if query matches any field
            if (query in album['artist'].lower() or 
                query in album['album'].lower() or 
                query in album.get('label', '').lower() or 
                query in album.get('date', '').lower()):
                
                # Create a tuple with the sort key and display string
                # Using artist and album for sorting
                sort_key = f"{album['artist'].lower()} - {album['album'].lower()}"
                display = f"{album['artist']} - {album['album']} ({album.get('date', 'No date')})"
                matching_albums.append((sort_key, display))
        
        # Sort the results alphabetically
        matching_albums.sort(key=lambda x: x[0])
        
        # Insert sorted results into listbox
        for _, display in matching_albums:
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
                album_path = album['path']  # Esta es la ruta completa del álbum
                print(f"Searching for cover in: {album_path}")  # Debug
                cover_path = self.find_cover_image(album_path)
                if cover_path:
                    print(f"Cover found: {cover_path}")  # Debug
                else:
                    print("No cover found")  # Debug
                self.display_cover_image(cover_path)

    def add_keyboard_shortcuts(self):
        """Add keyboard shortcuts."""
        # Atajo ESC para cerrar la aplicación
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        
        # Control + F para focus en búsqueda
        self.root.bind("<Control-f>", lambda e: self.search_entry.focus_set())
        # Control + O para abrir carpeta
        self.root.bind("<Control-o>", lambda e: self.open_selected_folder())
        self.root.bind("<Control-a>", self.select_all)
        
        # Asegurarse de que estos atajos funcionen también cuando el foco está en el listbox
        self.result_list.bind("<Control-f>", lambda e: self.search_entry.focus_set())
        self.result_list.bind("<Return>", lambda e: self.play_selected_album())
        self.result_list.bind("<Escape>", lambda e: self.root.destroy())
        
        # Atajos específicos para la caja de búsqueda
        self.search_entry.bind("<Return>", self.move_focus_to_list)
        self.search_entry.bind("<Escape>", lambda e: self.root.destroy())

    def move_focus_to_list(self, event=None):
        """Move focus to the results list and select first item if available."""
        if self.result_list.size() > 0:  # Si hay elementos en la lista
            self.result_list.focus_set()  # Mover el foco a la lista
            self.result_list.selection_clear(0, tk.END)  # Limpiar selección actual
            self.result_list.selection_set(0)  # Seleccionar primer elemento
            self.result_list.see(0)  # Asegurar que el elemento sea visible
            # Disparar el evento de selección para actualizar los detalles
            self.on_select(None)

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