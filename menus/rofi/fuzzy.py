#!/usr/bin/env python
import os
import tkinter as tk
import re
import glob
import subprocess
import tkinter.messagebox as messagebox
from markdown import markdown
from tkinterweb import HtmlFrame

# Define el directorio donde están tus archivos Markdown
SEARCH_DIR = "/mnt/windows/FTP/wiki/Obsidian/"

# Define los paths que quieres mostrar al final con iconos
SECONDARY_PATHS = [
    "/mnt/windows/FTP/wiki/Obsidian/.space/",
    "/mnt/windows/FTP/wiki/Obsidian/Templates/",
    "/mnt/windows/FTP/wiki/Obsidian/Adjuntos/",
    "/mnt/windows/FTP/wiki/Obsidian/calendars/",
    "/mnt/windows/FTP/wiki/Obsidian/Dibujos/",
    "/mnt/windows/FTP/wiki/Obsidian/journals/",
    "/mnt/windows/FTP/wiki/Obsidian/Tags/",
    "/mnt/windows/FTP/wiki/Obsidian/Spaces/Infinity"
    # Añade más paths aquí
]

def display_file_content(filename, query):
    """Muestra el contenido del archivo con formato Markdown."""
    global html_viewer
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            content = file.read()
            # Eliminar secciones delimitadas por '---'
            content = re.sub(r'---.*?---', '', content, flags=re.DOTALL).strip()
            
            # Convertir Markdown a HTML con extensiones
            html_content = markdown(content, extensions=[
                'markdown.extensions.extra',
                'markdown.extensions.codehilite',
                'markdown.extensions.tables',
                'markdown.extensions.toc'
            ])
            
            # Añadir estilos CSS para el tema oscuro y formato Markdown
            html_content = f"""
            <html>
            <head>
                <style>
                    body {{
                        background-color: #14141e !important;
                        color: white !important;
                        font-family: Arial, sans-serif;
                        padding: 20px;
                        line-height: 1.6;
                    }}
                    h1, h2, h3, h4, h5, h6 {{
                        color: #cba6f7;
                        margin-top: 24px;
                        margin-bottom: 16px;
                        font-weight: 600;
                        line-height: 1.25;
                    }}
                    h1 {{ font-size: 2em; border-bottom: 1px solid #444; padding-bottom: .3em; }}
                    h2 {{ font-size: 1.5em; border-bottom: 1px solid #444; padding-bottom: .3em; }}
                    h3 {{ font-size: 1.25em; }}
                    h4 {{ font-size: 1em; }}
                    p {{
                        margin-bottom: 16px;
                    }}
                    a {{
                        color: #1974D2;
                        text-decoration: none;
                    }}
                    a:hover {{
                        text-decoration: underline;
                    }}
                    code {{
                        background-color: #282a36;
                        padding: 0.2em 0.4em;
                        border-radius: 3px;
                        font-family: monospace;
                        font-size: 85%;
                    }}
                    pre {{
                        background-color: #282a36;
                        padding: 16px;
                        border-radius: 6px;
                        overflow: auto;
                        line-height: 1.45;
                    }}
                    pre code {{
                        background-color: transparent;
                        padding: 0;
                    }}
                    blockquote {{
                        padding: 0 1em;
                        color: #8b949e;
                        border-left: .25em solid #444;
                        margin: 0 0 16px 0;
                    }}
                    ul, ol {{
                        padding-left: 2em;
                        margin-bottom: 16px;
                    }}
                    li {{
                        margin: 0.25em 0;
                    }}
                    table {{
                        border-collapse: collapse;
                        margin-bottom: 16px;
                        width: 100%;
                    }}
                    table th, table td {{
                        padding: 6px 13px;
                        border: 1px solid #444;
                    }}
                    table th {{
                        background-color: #282a36;
                    }}
                    img {{
                        max-width: 100%;
                        height: auto;
                    }}
                    hr {{
                        height: .25em;
                        padding: 0;
                        margin: 24px 0;
                        background-color: #444;
                        border: 0;
                    }}
                </style>
            </head>
            <body>
                {html_content}
            </body>
            </html>
            """
            
            # Actualizar el contenido HTML
            html_viewer.load_html(html_content)
            
    except Exception as e:
        print(f"Error al renderizar el archivo {filename}: {e}")

def get_selected_file():
    """Obtiene el archivo seleccionado actualmente."""
    selection = result_list.curselection()
    if selection:
        index = selection[0]
        # Obtener el texto del ítem para verificar si es un encabezado
        item_text = result_list.get(index)
        if item_text.startswith("==="):
            return None  # Es un encabezado, no un archivo
        
        # Calcular el índice real en la lista de resultados
        real_index = index
        for i in range(index):
            if result_list.get(i).startswith("==="):
                real_index -= 1
                
        if real_index < len(all_results):
            _, filename, _ = all_results[real_index]
            return filename
    return None

def extract_tags(content):
    """Extrae los tags del contenido Markdown."""
    # Busca tags al estilo #tag o tags en metadatos YAML: tags: [tag1, tag2]
    yaml_tags = re.search(r'---.*?tags:\s*\[(.*?)\].*?---', content, re.DOTALL)
    inline_tags = re.findall(r'(?<!\S)#([a-zA-Z0-9_-]+)', content)
    
    tags = []
    if yaml_tags:
        tags.extend([tag.strip().strip('"\'') for tag in yaml_tags.group(1).split(',')])
    if inline_tags:
        tags.extend(inline_tags)
    
    return tags

def search_files(query):
    """Realiza la búsqueda de archivos Markdown que coincidan con la consulta."""
    # Crear listas para cada categoría
    title_matches = []
    tag_matches = []
    content_matches = []
    wallabag_matches = []
    
    for filename in glob.iglob(os.path.join(SEARCH_DIR, '**', '*.md'), recursive=True):
        title = os.path.basename(filename).replace('.md', '')
        
        is_secondary = any(path in filename for path in SECONDARY_PATHS)
        is_wallabag = "wallabag" in filename.lower()
        
        icon = '📁' if is_secondary else '📄'
        
        # Buscar coincidencias en el título
        if re.search(query, title, re.IGNORECASE):
            title_matches.append((icon, filename, title))
            continue  # Si coincide en el título, no buscamos en otras categorías
                
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                content = file.read()
                
                # Extraer y comprobar tags
                tags = extract_tags(content)
                if any(re.search(query, tag, re.IGNORECASE) for tag in tags):
                    tag_matches.append((icon, filename, title))
                    continue  # Si coincide en tags, no buscamos en contenido
                
                # Eliminar metadatos para buscar en contenido
                content = re.sub(r'---.*?---', '', content, flags=re.DOTALL).strip()
                
                # Buscar en contenido
                if re.search(query, content, re.IGNORECASE):
                    if is_wallabag:
                        wallabag_matches.append((icon, filename, title))
                    else:
                        content_matches.append((icon, filename, title))
                        
        except Exception as e:
            print(f"Error al leer el archivo {filename}: {e}")
    
    return title_matches, tag_matches, content_matches, wallabag_matches

def update_results(event):
    """Actualiza la lista de resultados según el texto de búsqueda."""
    query = search_entry.get()
    global all_results
    title_matches, tag_matches, content_matches, wallabag_matches = search_files(query)

    # Combinar todos los resultados para facilitar la referencia
    all_results = title_matches + tag_matches + content_matches + wallabag_matches

    # Limpiar la lista de resultados
    result_list.delete(0, tk.END)
    
    # Insertar resultados por categoría
    if title_matches:
        result_list.insert(tk.END, "=== Coincidencias en Título ===")
        for icon, _, title in title_matches:
            result_list.insert(tk.END, f"{icon} {title}")
    
    if tag_matches:
        result_list.insert(tk.END, "=== Coincidencias en Tags ===")
        for icon, _, title in tag_matches:
            result_list.insert(tk.END, f"{icon} {title}")
    
    if content_matches:
        result_list.insert(tk.END, "=== Coincidencias en Contenido ===")
        for icon, _, title in content_matches:
            result_list.insert(tk.END, f"{icon} {title}")
    
    if wallabag_matches:
        result_list.insert(tk.END, "=== Wallabag ===")
        for icon, _, title in wallabag_matches:
            result_list.insert(tk.END, f"{icon} {title}")
    
    # Si no hay resultados, mostrar un mensaje
    if not all_results:
        result_list.insert(tk.END, "No se encontraron resultados")

def on_select(event):
    """Muestra el contenido del archivo seleccionado."""
    filename = get_selected_file()
    if filename:
        display_file_content(filename, search_entry.get())

def edit_file(event=None):
    """Abre el archivo seleccionado con Obsidian."""
    filename = get_selected_file()
    if filename and os.path.isfile(filename):
        file_path = os.path.abspath(filename)
        obsidian_uri = f"obsidian://open?path={file_path}"
        subprocess.run(["xdg-open", obsidian_uri])

def open_folder(event=None):
    """Abre la carpeta que contiene el archivo seleccionado."""
    filename = get_selected_file()
    if filename and os.path.isfile(filename):
        folder_path = os.path.dirname(filename)
        subprocess.run(["thunar", folder_path])

def delete_file(event=None):
    """Elimina el archivo seleccionado."""
    filename = get_selected_file()
    if filename and os.path.isfile(filename):
        confirm = messagebox.askyesno(
            "Confirmar eliminación", 
            f"¿Estás seguro de que deseas eliminar '{os.path.basename(filename)}'?"
        )
        if confirm:
            try:
                os.remove(filename)
                update_results(None)
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo eliminar el archivo: {str(e)}")

def focus_search(event=None):
    """Focaliza el campo de búsqueda."""
    search_entry.focus_set()

def select_all(event=None):
    """Selecciona todo el texto en el campo de búsqueda."""
    search_entry.select_range(0, tk.END)
    return "break"

def create_gui():
    """Crea la interfaz gráfica."""
    global root, search_entry, result_list, html_viewer, all_results
    root = tk.Tk()
    root.title("Buscador de archivos Markdown")
    root.configure(bg='#14141e')
    root.geometry("1600x800")

    search_frame = tk.Frame(root, bg='#14141e')
    search_frame.pack(pady=(10, 10), padx=5)

    open_button = tk.Button(search_frame, text="Carpeta", command=open_folder, bg='#f8bd9a')
    open_button.pack(side=tk.LEFT, padx=(0, 15))

    edit_button = tk.Button(search_frame, text="Editar", command=edit_file, bg='#1974D2')
    edit_button.pack(side=tk.LEFT, padx=(0, 15))

    delete_button = tk.Button(search_frame, text="Eliminar", command=delete_file, bg='#ff8b8b')
    delete_button.pack(side=tk.LEFT, padx=(0, 15))

    search_entry = tk.Entry(search_frame, bg='#cba6f7', fg='black', font=('Arial', 12), 
                          insertbackground='black', width=50)
    search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

    result_list = tk.Listbox(root, width=50, height=20, font=('Arial', 12), 
                            bg='#14141e', fg='white', selectbackground='#cba6f7')
    result_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    html_viewer = HtmlFrame(root, horizontal_scrollbar="auto")
    html_viewer.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

    html_viewer.load_html("""
    <html>
    <head>
        <style>
            body {
                background-color: #14141e;
                color: white;
                font-family: Firacode, sans-serif;
                font-size: 19px;
            }
        </style>
    </head>
    <body></body>
    </html>
    """)

    # Bindings
    search_entry.bind("<KeyRelease>", update_results)
    search_entry.bind("<Return>", update_results)
    search_entry.bind("<FocusIn>", focus_search)
    result_list.bind("<<ListboxSelect>>", on_select)
    root.bind("<Control-f>", lambda e: focus_search())
    root.bind("<Control-o>", lambda e: open_folder())
    root.bind("<Control-e>", lambda e: edit_file())
    root.bind("<Delete>", lambda e: delete_file())
    root.bind("<Control-a>", select_all)

    all_results = []

    search_entry.focus_set()
    root.mainloop()

if __name__ == "__main__":
    create_gui()