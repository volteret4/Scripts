
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

import os
import shutil
import subprocess
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox
import sys

class PlaylistManager(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Gestor de Playlists")
        self.geometry("800x400")
        self.configure(bg='#14141e')

        style = ttk.Style()
        style.configure("TFrame", background="#14141e", borderwidth=0, relief="flat")
        style.configure("TLabel", background="#14141e", foreground="white")
        style.configure("TButton", background="#1f1f2e", foreground="white")

        main_frame = ttk.Frame(self, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")

        self.columnconfigure(0, weight=2)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        main_frame.columnconfigure(0, weight=2, minsize=250)
        main_frame.columnconfigure(1, weight=1)

        ttk.Label(main_frame, text="Blogs Disponibles:", font=("Helvetica", 14, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(main_frame, text="Playlists:", font=("Helvetica", 14, "bold")).grid(row=0, column=1, sticky="w", padx=(10,0))

        self.blog_listbox = tk.Listbox(
            main_frame, height=15, bg='#14141e', fg='white',
            selectbackground="#A084CA", selectforeground="black",
            highlightthickness=0, borderwidth=0
        )
        self.blog_listbox.grid(row=1, column=0, sticky="nsew")

        self.playlist_listbox = tk.Listbox(
            main_frame, height=15, bg='#14141e', fg='white',
            selectbackground="#A084CA", selectforeground="black",
            highlightthickness=0, borderwidth=0
        )
        self.playlist_listbox.grid(row=1, column=1, sticky="nsew", padx=(10,0))

        self.play_button = ttk.Button(main_frame, text="Reproducir Seleccionado", command=self.play_selected)
        self.play_button.grid(row=2, column=0, columnspan=2, pady=10)

        self.blog_listbox.bind('<<ListboxSelect>>', self.on_blog_select)
        self.after(100, lambda: self.blog_listbox.focus_set())
        self.blog_listbox.bind("<Tab>", lambda e: self.playlist_listbox.focus_set())
        self.playlist_listbox.bind("<Shift-Tab>", lambda e: self.blog_listbox.focus_set())
        self.playlist_listbox.bind("<Return>", lambda e: self.play_selected())

        self.selected_blog = None
        self.refresh_blogs()

    def show_move_dialog(self, blog_name, playlist_name):
        """Muestra un diálogo preguntando si mover la playlist"""
        dialog = tk.Tk()
        dialog.title("Mover Playlist")
        
        # Centrar el diálogo
        dialog.geometry("300x150")
        dialog.eval('tk::PlaceWindow . center')
        
        # Configurar estilo oscuro
        dialog.configure(bg='#14141e')
        
        # Mensaje
        label = tk.Label(
            dialog,
            text="¿Has terminado la lista?",
            bg='#14141e',
            fg='white',
            font=("Helvetica", 12),
            pady=20
        )
        label.pack()

        # Frame para los botones
        button_frame = tk.Frame(dialog, bg='#14141e')
        button_frame.pack(pady=10)

        def on_yes():
            self.move_to_listened(blog_name, playlist_name)
            dialog.destroy()
            sys.exit()

        def on_no():
            dialog.destroy()
            sys.exit()

        # Botones
        yes_btn = tk.Button(
            button_frame,
            text="Sí",
            command=on_yes,
            bg='#1f1f2e',
            fg='white',
            width=10
        )
        no_btn = tk.Button(
            button_frame,
            text="No",
            command=on_no,
            bg='#1f1f2e',
            fg='white',
            width=10
        )
        
        yes_btn.pack(side=tk.LEFT, padx=5)
        no_btn.pack(side=tk.LEFT, padx=5)

        # Hacer que el diálogo sea modal
        dialog.transient()
        dialog.grab_set()
        
        # Bind teclas
        dialog.bind('<Return>', lambda e: on_yes())
        dialog.bind('<Escape>', lambda e: on_no())
        
        # Focus en el botón Sí
        yes_btn.focus_set()
        
        dialog.mainloop()

    def count_tracks_in_playlist(self, playlist_path):
        try:
            with open(playlist_path, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                return len(lines)
        except Exception:
            return 0

    def get_blogs_with_counts(self):
        pending_dir = "PENDIENTE"
        blogs = {}
        
        if os.path.exists(pending_dir):
            for blog in os.listdir(pending_dir):
                blog_path = os.path.join(pending_dir, blog)
                if os.path.isdir(blog_path):
                    playlists = [f for f in os.listdir(blog_path) if f.endswith('.m3u')]
                    blogs[blog] = len(playlists)
        
        return blogs

    def get_monthly_playlists_with_counts(self, blog_name):
        blog_path = os.path.join("PENDIENTE", blog_name)
        playlists = {}
        
        if os.path.exists(blog_path):
            for playlist in os.listdir(blog_path):
                if playlist.endswith('.m3u'):
                    full_path = os.path.join(blog_path, playlist)
                    track_count = self.count_tracks_in_playlist(full_path)
                    playlists[playlist] = track_count
        
        return playlists

    def move_to_listened(self, blog_name, playlist_name):
        source = os.path.join("PENDIENTE", blog_name, playlist_name)
        listened_blog_dir = os.path.join("ESCUCHADO", blog_name)
        
        os.makedirs(listened_blog_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_")
        new_name = timestamp + playlist_name
        destination = os.path.join(listened_blog_dir, new_name)
        
        shutil.move(source, destination)
        return destination

    def refresh_blogs(self):
        self.blog_listbox.delete(0, tk.END)
        blogs = self.get_blogs_with_counts()
        
        for blog, count in blogs.items():
            self.blog_listbox.insert(tk.END, f"{blog} ({count} playlists)")

    def on_blog_select(self, event):
        if not self.blog_listbox.curselection():
            return
        
        selection = self.blog_listbox.get(self.blog_listbox.curselection())
        self.selected_blog = selection.split(" (")[0]

        self.playlist_listbox.delete(0, tk.END)
        playlists = self.get_monthly_playlists_with_counts(self.selected_blog)
        
        for playlist, count in playlists.items():
            self.playlist_listbox.insert(tk.END, f"{playlist} ({count} canciones)")

    def play_selected(self):
        if not self.selected_blog or not self.playlist_listbox.curselection():
            messagebox.showwarning("Selección requerida", "Por favor, selecciona un blog y una playlist")
            return

        playlist_selection = self.playlist_listbox.get(self.playlist_listbox.curselection())
        playlist_name = playlist_selection.split(" (")[0]
        
        playlist_path = os.path.join("PENDIENTE", self.selected_blog, playlist_name)
        
        if not os.path.exists(playlist_path):
            messagebox.showerror("Error", "No se encuentra el archivo de la playlist")
            return

        # Guardar variables antes de destruir la ventana principal
        selected_blog = self.selected_blog
        
        # Destruir la ventana de tkinter
        self.destroy()
        
        try:
            # Ejecutar mpv con opciones para forzar la interfaz de video
            process = subprocess.run(["mpv", "--player-operation-mode=pseudo-gui", "--force-window=yes", playlist_path])
            
            # Si mpv se cerró normalmente, mostrar el diálogo
            if process.returncode == 0:
                # Crear nueva instancia de tkinter para el diálogo
                self.show_move_dialog(selected_blog, playlist_name)
            else:
                sys.exit()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al reproducir: {str(e)}")
            sys.exit()

if __name__ == "__main__":
    app = PlaylistManager()
    app.mainloop()