#!/usr/bin/env python3
#
# Script Name: sp_menu_playlists.py
# Description: Menú GUI para seleccionar playlists de Spotify
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:

import tkinter as tk
import os
import sys
from pathlib import Path

# Determinar la ruta del archivo de playlists
script_dir = Path(__file__).parent.absolute()
project_root = script_dir.parent  # Subir un nivel desde modules/

# Buscar el archivo de playlists en el cache del proyecto
playlist_file = project_root / ".content" / "cache" / "playlists.txt"

# Fallback a la ubicación original si no existe en cache
if not playlist_file.exists():
    playlist_file = Path("/home/huan/Scripts/Musica/playlists/spotify/playlists.txt")

# Verificar que el archivo existe
if not playlist_file.exists():
    print(f"Error: No se encontró el archivo de playlists en {playlist_file}", file=sys.stderr)
    sys.exit(1)

# Variable global para almacenar la ventana
root = None

def handle_click(playlist_id):
    """Manejar el clic en un botón de playlist"""
    print(playlist_id)
    root.quit()  # Cerrar la ventana Tkinter

def nueva_lista_click():
    """Manejar el clic en el botón 'NUEVA LISTA'"""
    print("nuevalista")
    root.quit()  # Cerrar la ventana Tkinter

def create_playlist_menu():
    """Crear y mostrar el menú de playlists"""
    global root
    
    try:
        # Leer el archivo de playlists
        with open(playlist_file, "r", encoding='utf-8') as file:
            lines = file.readlines()
    except Exception as e:
        print(f"Error al leer archivo de playlists: {e}", file=sys.stderr)
        sys.exit(1)

    # Verificar que el número de líneas es múltiplo de 3
    if len(lines) % 3 != 0:
        print("Error: El archivo no tiene un formato válido. Debe contener un nombre de lista, un ID y una línea vacía entre cada conjunto.", file=sys.stderr)
        sys.exit(1)

    # Crear una ventana de Tkinter
    root = tk.Tk()
    root.title("Selecciona una playlist - VVMM Post Creator")

    # Configuración del color de fondo
    root.config(bg="#0a0a0a")

    # Configuración de la fuente
    button_font = ("Helvetica", 10, "bold")

    # Configurar el cierre de ventana
    root.protocol("WM_DELETE_WINDOW", lambda: (print(""), root.quit()))

    def create_buttons():
        """Crear los botones de las playlists"""
        max_buttons_per_column = 7
        total_playlists = len(lines) // 3
        num_columns = (total_playlists + max_buttons_per_column - 1) // max_buttons_per_column
        
        buttons_created = 0
        
        for column in range(num_columns):
            for row in range(max_buttons_per_column):
                index = column * max_buttons_per_column * 3 + row * 3
                if index >= len(lines):
                    break
                    
                try:
                    playlist_name = lines[index].strip().replace("Nombre: ", "")
                    playlist_id = lines[index + 1].strip().replace("ID: ", "")
                    
                    # Truncar nombres muy largos
                    display_name = playlist_name if len(playlist_name) <= 25 else playlist_name[:22] + "..."
                    
                    button = tk.Button(
                        root, 
                        text=display_name, 
                        command=lambda id=playlist_id: handle_click(id), 
                        font=button_font, 
                        bg="#1DB954", 
                        fg="black",
                        width=20,
                        pady=2
                    )
                    button.grid(row=row, column=column, padx=5, pady=2, sticky="ew")
                    buttons_created += 1
                    
                    if buttons_created >= total_playlists:
                        break
                except IndexError:
                    break

        # Botón "NUEVA LISTA"
        nueva_lista_button = tk.Button(
            root, 
            text="🎵 NUEVA LISTA", 
            command=nueva_lista_click, 
            font=button_font, 
            bg="#FF6B35", 
            fg="white",
            pady=5
        )
        nueva_lista_button.grid(
            row=max_buttons_per_column, 
            columnspan=max(num_columns, 1), 
            padx=5, 
            pady=10, 
            sticky="ew"
        )

        # Configurar el peso de las columnas para que se expandan
        for col in range(max(num_columns, 1)):
            root.grid_columnconfigure(col, weight=1)

    # Crear los botones
    create_buttons()

    # Centrar la ventana en la pantalla
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f"{width}x{height}+{x}+{y}")

    # Configurar teclas de escape
    root.bind('<Escape>', lambda e: (print(""), root.quit()))
    root.bind('<Control-c>', lambda e: (print(""), root.quit()))

    # Hacer que la ventana sea modal
    root.grab_set()
    root.focus_force()

    return root

def main():
    """Función principal"""
    try:
        app = create_playlist_menu()
        app.mainloop()
    except KeyboardInterrupt:
        print("")  # Salida limpia
        sys.exit(0)
    except Exception as e:
        print(f"Error inesperado: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()