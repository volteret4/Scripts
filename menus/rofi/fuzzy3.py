import os
import tkinter as tk
from tkinter import messagebox
from tkhtmlview import HTMLLabel
import markdown
from markdown.extensions import fenced_code
import re
import glob
import subprocess

# Configuración de colores
BACKGROUND_COLOR = "#14141e"
TEXT_COLOR = "white"
HIGHLIGHT_BG_COLOR = "#cba6f7"
HIGHLIGHT_TEXT_COLOR = "black"
BUTTON_BG_COLOR = "#f8bd9a"

# Directorios
SEARCH_DIR = "/mnt/windows/FTP/wiki/Obsidian/"
IMAGES_DIR = "/mnt/windows/FTP/wiki/Obsidian/Dibujos"

# Funciones

def search_files(query):
    matches = []
    for filename in glob.iglob(os.path.join(SEARCH_DIR, '**', '*.md'), recursive=True):
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                content = file.read()
                if re.search(query, content, re.IGNORECASE):
                    matches.append(filename)
        except Exception as e:
            print(f"Error al leer el archivo {filename}: {e}")
    return matches

def convert_markdown_to_html(content):
    """Convierte contenido Markdown a HTML y ajusta rutas de imágenes."""
    content = re.sub(r'!\[(.*?)\]\((.*?)\)',
                     lambda m: f'![{m.group(1)}]({os.path.join(IMAGES_DIR, m.group(2))})',
                     content)
    html_content = markdown.markdown(content, extensions=['fenced_code'])
    return html_content

def display_file_content(filename, query):
    with open(filename, 'r', encoding='utf-8') as file:
        content = file.read()

    html_content = convert_markdown_to_html(content)

    if query:
        html_content = re.sub(
            f"({re.escape(query)})",
            r"<span style='background-color: yellow;'>\1</span>",
            html_content,
            flags=re.IGNORECASE
        )

    html_label.set_html(html_content)

def on_select(event):
    selected = result_list.curselection()
    if selected:
        filename = result_list.get(selected[0])
        display_file_content(filename, search_entry.get())

def update_results(event=None):
    query = search_entry.get()
    matches = search_files(query)
    result_list.delete(0, tk.END)
    for match in matches:
        result_list.insert(tk.END, match)
    html_label.set_html("<h1>Selecciona un archivo para ver el contenido</h1>")

def open_with_editor():
    selected = result_list.curselection()
    if selected:
        filename = result_list.get(selected[0])
        subprocess.run(["vscodium", filename])

def create_gui():
    global search_entry, result_list, html_label

    root = tk.Tk()
    root.title("Markdown Search")
    root.geometry("1200x800")
    root.configure(bg=BACKGROUND_COLOR)

    # Campo de búsqueda
    search_frame = tk.Frame(root, bg=BACKGROUND_COLOR)
    search_frame.pack(pady=10)

    search_entry = tk.Entry(search_frame, width=50, font=("Arial", 14), bg=HIGHLIGHT_BG_COLOR, fg=TEXT_COLOR, insertbackground=TEXT_COLOR)
    search_entry.pack(side=tk.LEFT, padx=5)
    search_entry.bind("<KeyRelease>", update_results)

    search_button = tk.Button(search_frame, text="Buscar", command=lambda: update_results(None), bg=BUTTON_BG_COLOR)
    search_button.pack(side=tk.LEFT, padx=5)

    # Lista de resultados
    result_list = tk.Listbox(root, width=50, height=20, font=("Arial", 12), bg=BACKGROUND_COLOR, fg=TEXT_COLOR)
    result_list.pack(side=tk.LEFT, fill=tk.BOTH, padx=10, pady=10)
    result_list.bind("<<ListboxSelect>>", on_select)

    # Área para mostrar el HTML del archivo
    html_label = HTMLLabel(root, html="<h1>Selecciona un archivo para ver el contenido</h1>", width=80, height=30, background=BACKGROUND_COLOR, foreground=TEXT_COLOR)
    html_label.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Atajos de teclado
    root.bind("<Control-f>", lambda e: search_entry.focus())
    root.bind("<Control-o>", lambda e: open_with_editor())

    root.mainloop()

if __name__ == "__main__":
    create_gui()
import os
import tkinter as tk
from tkinter import messagebox
from tkhtmlview import HTMLLabel
import markdown
from markdown.extensions import fenced_code
import re
import glob
import subprocess

# Configuración de colores
BACKGROUND_COLOR = "#14141e"
TEXT_COLOR = "white"
HIGHLIGHT_BG_COLOR = "#cba6f7"
HIGHLIGHT_TEXT_COLOR = "black"
BUTTON_BG_COLOR = "#f8bd9a"

# Directorios
SEARCH_DIR = "/mnt/windows/FTP/wiki/Obsidian/"
IMAGES_DIR = "/mnt/windows/FTP/wiki/Obsidian/Dibujos"

# Funciones

def search_files(query):
    matches = []
    for filename in glob.iglob(os.path.join(SEARCH_DIR, '**', '*.md'), recursive=True):
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                content = file.read()
                if re.search(query, content, re.IGNORECASE):
                    matches.append(filename)
        except Exception as e:
            print(f"Error al leer el archivo {filename}: {e}")
    return matches

def convert_markdown_to_html(content):
    """Convierte contenido Markdown a HTML y ajusta rutas de imágenes."""
    content = re.sub(r'!\[(.*?)\]\((.*?)\)',
                     lambda m: f'![{m.group(1)}]({os.path.join(IMAGES_DIR, m.group(2))})',
                     content)
    html_content = markdown.markdown(content, extensions=['fenced_code'])
    return html_content

def display_file_content(filename, query):
    with open(filename, 'r', encoding='utf-8') as file:
        content = file.read()

    html_content = convert_markdown_to_html(content)

    if query:
        html_content = re.sub(
            f"({re.escape(query)})",
            r"<span style='background-color: yellow;'>\1</span>",
            html_content,
            flags=re.IGNORECASE
        )

    html_label.set_html(html_content)

def on_select(event):
    selected = result_list.curselection()
    if selected:
        filename = result_list.get(selected[0])
        display_file_content(filename, search_entry.get())

def update_results(event=None):
    query = search_entry.get()
    matches = search_files(query)
    result_list.delete(0, tk.END)
    for match in matches:
        result_list.insert(tk.END, match)
    html_label.set_html("<h1>Selecciona un archivo para ver el contenido</h1>")

def open_with_editor():
    selected = result_list.curselection()
    if selected:
        filename = result_list.get(selected[0])
        subprocess.run(["vscodium", filename])

def create_gui():
    global search_entry, result_list, html_label

    root = tk.Tk()
    root.title("Markdown Search")
    root.geometry("1200x800")
    root.configure(bg=BACKGROUND_COLOR)

    # Campo de búsqueda
    search_frame = tk.Frame(root, bg=BACKGROUND_COLOR)
    search_frame.pack(pady=10)

    search_entry = tk.Entry(search_frame, width=50, font=("Arial", 14), bg=HIGHLIGHT_BG_COLOR, fg=TEXT_COLOR, insertbackground=TEXT_COLOR)
    search_entry.pack(side=tk.LEFT, padx=5)
    search_entry.bind("<KeyRelease>", update_results)

    search_button = tk.Button(search_frame, text="Buscar", command=lambda: update_results(None), bg=BUTTON_BG_COLOR)
    search_button.pack(side=tk.LEFT, padx=5)

    # Lista de resultados
    result_list = tk.Listbox(root, width=50, height=20, font=("Arial", 12), bg=BACKGROUND_COLOR, fg=TEXT_COLOR)
    result_list.pack(side=tk.LEFT, fill=tk.BOTH, padx=10, pady=10)
    result_list.bind("<<ListboxSelect>>", on_select)

    # Área para mostrar el HTML del archivo
    html_label = HTMLLabel(root, html="<h1>Selecciona un archivo para ver el contenido</h1>", width=80, height=30, background=BACKGROUND_COLOR, foreground=TEXT_COLOR)
    html_label.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Atajos de teclado
    root.bind("<Control-f>", lambda e: search_entry.focus())
    root.bind("<Control-o>", lambda e: open_with_editor())

    root.mainloop()

if __name__ == "__main__":
    create_gui()
