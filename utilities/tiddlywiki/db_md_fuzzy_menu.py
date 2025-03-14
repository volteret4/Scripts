#!/usr/bin/env python
import os
import tkinter as tk
import re
import sqlite3
import subprocess
import tkinter.messagebox as messagebox
from markdown import markdown
from tkinterweb import HtmlFrame

# Define la ruta a la base de datos SQLite
DB_PATH = "/home/huan/Scripts/wiki_obsidian.db"  # Actualiza esta ruta

# Define los paths que quieres mostrar al final con iconos (mantiene la lógica original)
SECONDARY_PATHS = [
    "/mnt/windows/FTP/wiki/Obsidian/Spaces/Scripts"
]

def conectar_db():
    """Establece conexión con la base de datos SQLite."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"Error al conectar a la base de datos: {e}")
        return None

def display_file_content(snippet_id, query=None):
    """Muestra el contenido del archivo con formato Markdown desde la base de datos."""
    global html_viewer
    
    try:
        conn = conectar_db()
        if not conn:
            return
        
        cursor = conn.cursor()
        # Obtener contenido de la base de datos
        cursor.execute("SELECT filename, content FROM snippets WHERE id = ?", (snippet_id,))
        result = cursor.fetchone()
        
        if result:
            content = result['content']
            
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
        else:
            html_viewer.load_html("<html><body><h1>Error</h1><p>No se encontró el archivo en la base de datos.</p></body></html>")
        
        conn.close()
            
    except Exception as e:
        print(f"Error al renderizar el contenido del snippet {snippet_id}: {e}")
        html_viewer.load_html(f"<html><body><h1>Error</h1><p>Error al renderizar contenido: {e}</p></body></html>")

def get_selected_snippet():
    """Obtiene el snippet seleccionado actualmente."""
    selection = result_list.curselection()
    if selection:
        index = selection[0]
        all_results = primary_results + secondary_results
        if index < len(all_results):
            return all_results[index]
    return None

def search_snippets(query):
    """Realiza la búsqueda de archivos Markdown en la base de datos que coincidan con la consulta."""
    primary_matches = []
    secondary_matches = []
    
    try:
        conn = conectar_db()
        if not conn:
            return [], []
        
        cursor = conn.cursor()
        
        # Usar FTS para búsqueda de texto completo si está disponible, de lo contrario usar LIKE
        sql_query = """
        SELECT s.id, s.filename, s.path, s.content, s.source
        FROM snippets s
        WHERE s.filename LIKE ? OR s.content LIKE ?
        """
        cursor.execute(sql_query, (f"%{query}%", f"%{query}%"))
        results = cursor.fetchall()
        
        for row in results:
            snippet_id = row['id']
            filename = row['filename']
            filepath = row['path']
            
            # Obtener los tags del snippet
            cursor.execute("""
                SELECT t.name 
                FROM tags t 
                JOIN snippet_tags st ON t.id = st.tag_id 
                WHERE st.snippet_id = ?
            """, (snippet_id,))
            tags = [tag[0] for tag in cursor.fetchall()]
            
            # Determinar si es un path primario o secundario
            is_secondary = any(path in filepath for path in SECONDARY_PATHS)
            
            # Crear el item con icono, identificador y título
            item = {
                'id': snippet_id,
                'filename': filename,
                'path': filepath,
                'tags': tags
            }
            
            if is_secondary:
                secondary_matches.append(('📁', item, filename))
            else:
                primary_matches.append(('📄', item, filename))
        
        conn.close()
        
    except Exception as e:
        print(f"Error al buscar snippets: {e}")
    
    return primary_matches, secondary_matches

def update_results(event=None):
    """Actualiza la lista de resultados según el texto de búsqueda."""
    query = search_entry.get()
    global primary_results, secondary_results
    
    primary_results, secondary_results = search_snippets(query)

    result_list.delete(0, tk.END)

    for icon, _, title in primary_results:
        result_list.insert(tk.END, f"{icon} {title}")

    for icon, _, title in secondary_results:
        result_list.insert(tk.END, f"{icon} {title}")

def on_select(event):
    """Muestra el contenido del archivo seleccionado."""
    selection = result_list.curselection()
    if selection:
        index = selection[0]
        all_results = primary_results + secondary_results
        if index < len(all_results):
            _, item, _ = all_results[index]
            display_file_content(item['id'], search_entry.get())

def edit_file(event=None):
    """Abre el archivo seleccionado con Obsidian."""
    selected = get_selected_snippet()
    if selected:
        _, item, _ = selected
        file_path = os.path.join(item['path'], item['filename'])
        if os.path.isfile(file_path):
            obsidian_uri = f"obsidian://open?path={file_path}"
            subprocess.run(["xdg-open", obsidian_uri])
        else:
            messagebox.showwarning("Archivo no encontrado", 
                                  f"El archivo {file_path} no existe en el sistema de archivos.")

def open_folder(event=None):
    """Abre la carpeta que contiene el archivo seleccionado."""
    selected = get_selected_snippet()
    if selected:
        _, item, _ = selected
        folder_path = item['path']
        if os.path.isdir(folder_path):
            subprocess.run(["thunar", folder_path])
        else:
            messagebox.showwarning("Carpeta no encontrada", 
                                  f"La carpeta {folder_path} no existe en el sistema de archivos.")

def delete_file(event=None):
    """Elimina el archivo seleccionado de la base de datos y del sistema de archivos."""
    selected = get_selected_snippet()
    if selected:
        _, item, _ = selected
        file_path = os.path.join(item['path'], item['filename'])
        snippet_id = item['id']
        
        confirm = messagebox.askyesno(
            "Confirmar eliminación", 
            f"¿Estás seguro de que deseas eliminar '{item['filename']}'?\n\nEsto eliminará el archivo del sistema y de la base de datos."
        )
        
        if confirm:
            try:
                # Eliminar de la base de datos
                conn = conectar_db()
                if conn:
                    cursor = conn.cursor()
                    # Eliminar los tags asociados
                    cursor.execute("DELETE FROM snippet_tags WHERE snippet_id = ?", (snippet_id,))
                    # Eliminar el snippet
                    cursor.execute("DELETE FROM snippets WHERE id = ?", (snippet_id,))
                    conn.commit()
                    conn.close()
                
                # Eliminar el archivo físico si existe
                if os.path.isfile(file_path):
                    os.remove(file_path)
                
                update_results()  # Actualizar la lista de resultados
                messagebox.showinfo("Éxito", f"El archivo '{item['filename']}' ha sido eliminado.")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo eliminar: {str(e)}")

def focus_search(event=None):
    """Focaliza el campo de búsqueda."""
    search_entry.focus_set()

def select_all(event=None):
    """Selecciona todo el texto en el campo de búsqueda."""
    search_entry.select_range(0, tk.END)
    return "break"

def show_tags(event=None):
    """Muestra los tags del snippet seleccionado."""
    selected = get_selected_snippet()
    if selected:
        _, item, _ = selected
        tags = item['tags']
        if tags:
            messagebox.showinfo("Tags", f"Tags para '{item['filename']}':\n\n{', '.join(tags)}")
        else:
            messagebox.showinfo("Tags", f"No hay tags para '{item['filename']}'.")

def create_gui():
    """Crea la interfaz gráfica."""
    global root, search_entry, result_list, html_viewer, primary_results, secondary_results
    root = tk.Tk()
    root.title("Buscador de archivos Markdown - Base de datos")
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
    
    tags_button = tk.Button(search_frame, text="Ver Tags", command=show_tags, bg='#cba6f7')
    tags_button.pack(side=tk.LEFT, padx=(0, 15))

    search_entry = tk.Entry(search_frame, bg='#cba6f7', fg='black', font=('Arial', 12), 
                          insertbackground='black', width=50)
    search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

    result_list = tk.Listbox(root, width=50, height=20, font=('Arial', 12), 
                            bg='#14141e', fg='white')
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
    <body>
        <h1 style="color: #cba6f7;">Buscador de Markdown en Base de Datos</h1>
        <p>Escribe en el campo de búsqueda para comenzar...</p>
        <ul>
            <li>Usa <code>Control+F</code> para enfocar la búsqueda</li>
            <li>Selecciona un archivo para ver su contenido</li>
            <li>Botón <b>Editar</b> abre el archivo en Obsidian</li>
            <li>Botón <b>Carpeta</b> abre el directorio en el explorador</li>
            <li>Botón <b>Ver Tags</b> muestra las etiquetas asociadas</li>
        </ul>
    </body>
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
    root.bind("<Control-t>", lambda e: show_tags())
    root.bind("<Delete>", lambda e: delete_file())
    root.bind("<Control-a>", select_all)

    primary_results = []
    secondary_results = []

    search_entry.focus_set()
    root.mainloop()

def check_db_connection():
    """Verifica que la conexión a la base de datos funcione correctamente."""
    conn = conectar_db()
    if not conn:
        messagebox.showerror("Error de Conexión", 
                            f"No se pudo conectar a la base de datos en:\n{DB_PATH}\n\nVerifica la ruta y que el archivo exista.")
        return False
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM snippets")
        count = cursor.fetchone()[0]
        conn.close()
        return True
    except sqlite3.Error as e:
        messagebox.showerror("Error de Base de Datos", 
                            f"La base de datos existe pero hay un error al acceder a las tablas:\n{str(e)}")
        return False

def buscar_avanzada():
    """Abre una ventana para realizar búsquedas avanzadas con filtros."""
    def ejecutar_busqueda():
        path = path_entry.get() if path_var.get() else None
        title = title_entry.get() if title_var.get() else None
        content = content_entry.get() if content_var.get() else None
        tags = tags_entry.get() if tags_var.get() else None
        date = date_entry.get() if date_var.get() else None
        
        try:
            conn = conectar_db()
            if not conn:
                return
            
            cursor = conn.cursor()
            
            # Construir la consulta SQL base
            query = """
            SELECT DISTINCT s.id, s.filename, s.path, s.content, s.source
            FROM snippets s
            """
            
            # Condiciones y parámetros
            conditions = []
            params = {}
            
            # Si hay tags, unimos con las tablas necesarias
            if tags:
                query += """
                JOIN snippet_tags st ON s.id = st.snippet_id
                JOIN tags t ON st.tag_id = t.id
                """
                # Convertir la cadena de tags en una lista
                tag_list = [tag.strip() for tag in tags.split(',')]
                # Aquí asumimos que queremos snippets que contengan TODOS los tags especificados
                for i, tag in enumerate(tag_list):
                    conditions.append(f"EXISTS (SELECT 1 FROM tags t JOIN snippet_tags st ON t.id = st.tag_id WHERE st.snippet_id = s.id AND t.name = :tag{i})")
                    params[f"tag{i}"] = tag
            
            # Agregar otras condiciones
            if path:
                conditions.append("s.path LIKE :path")
                params["path"] = f"%{path}%"
            
            if title:
                conditions.append("s.filename LIKE :title")
                params["title"] = f"%{title}%"
            
            if content:
                conditions.append("s.content LIKE :content")
                params["content"] = f"%{content}%"
            
            if date:
                try:
                    # Simplificado, en la realidad usaríamos la función parse_date del script de consultas
                    conditions.append("s.last_modified LIKE :date")
                    params["date"] = f"%{date}%"
                except Exception as e:
                    messagebox.showwarning("Error de fecha", f"Error al procesar la fecha: {e}")
            
            # Completar la consulta con las condiciones
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            # Ejecutar la consulta
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            # Procesar resultados para el formato que usa la interfaz principal
            global primary_results, secondary_results
            primary_results = []
            secondary_results = []
            
            for row in results:
                snippet_id = row['id']
                filename = row['filename']
                filepath = row['path']
                
                # Obtener los tags del snippet
                cursor.execute("""
                    SELECT t.name 
                    FROM tags t 
                    JOIN snippet_tags st ON t.id = st.tag_id 
                    WHERE st.snippet_id = ?
                """, (snippet_id,))
                snippet_tags = [tag[0] for tag in cursor.fetchall()]
                
                # Crear el item con toda la información necesaria
                item = {
                    'id': snippet_id,
                    'filename': filename,
                    'path': filepath,
                    'tags': snippet_tags
                }
                
                # Determinar si es un path primario o secundario
                is_secondary = any(sec_path in filepath for sec_path in SECONDARY_PATHS)
                
                if is_secondary:
                    secondary_results.append(('📁', item, filename))
                else:
                    primary_results.append(('📄', item, filename))
            
            # Actualizar la lista de resultados en la interfaz principal
            result_list.delete(0, tk.END)
            
            for icon, _, title in primary_results:
                result_list.insert(tk.END, f"{icon} {title}")
            
            for icon, _, title in secondary_results:
                result_list.insert(tk.END, f"{icon} {title}")
            
            search_window.destroy()
            
            # Mostrar mensaje con total de resultados
            messagebox.showinfo("Búsqueda completada", f"Se encontraron {len(results)} resultados.")
            
            conn.close()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al realizar la búsqueda: {e}")
    
    # Crear ventana de búsqueda avanzada
    search_window = tk.Toplevel(root)
    search_window.title("Búsqueda Avanzada")
    search_window.configure(bg='#14141e')
    search_window.geometry("500x400")
    
    # Variables para los checkboxes
    path_var = tk.BooleanVar(value=False)
    title_var = tk.BooleanVar(value=False)
    content_var = tk.BooleanVar(value=False)
    tags_var = tk.BooleanVar(value=False)
    date_var = tk.BooleanVar(value=False)
    
    # Frame principal
    main_frame = tk.Frame(search_window, bg='#14141e', padx=20, pady=20)
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # Path
    path_frame = tk.Frame(main_frame, bg='#14141e')
    path_frame.pack(fill=tk.X, pady=5)
    tk.Checkbutton(path_frame, text="Ruta:", variable=path_var, bg='#14141e', fg='white', selectcolor='black').pack(side=tk.LEFT)
    path_entry = tk.Entry(path_frame, bg='#cba6f7', fg='black')
    path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))
    
    # Título
    title_frame = tk.Frame(main_frame, bg='#14141e')
    title_frame.pack(fill=tk.X, pady=5)
    tk.Checkbutton(title_frame, text="Título:", variable=title_var, bg='#14141e', fg='white', selectcolor='black').pack(side=tk.LEFT)
    title_entry = tk.Entry(title_frame, bg='#cba6f7', fg='black')
    title_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))
    
    # Contenido
    content_frame = tk.Frame(main_frame, bg='#14141e')
    content_frame.pack(fill=tk.X, pady=5)
    tk.Checkbutton(content_frame, text="Contenido:", variable=content_var, bg='#14141e', fg='white', selectcolor='black').pack(side=tk.LEFT)
    content_entry = tk.Entry(content_frame, bg='#cba6f7', fg='black')
    content_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))
    
    # Tags
    tags_frame = tk.Frame(main_frame, bg='#14141e')
    tags_frame.pack(fill=tk.X, pady=5)
    tk.Checkbutton(tags_frame, text="Tags:", variable=tags_var, bg='#14141e', fg='white', selectcolor='black').pack(side=tk.LEFT)
    tags_entry = tk.Entry(tags_frame, bg='#cba6f7', fg='black')
    tags_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))
    
    # Fecha
    date_frame = tk.Frame(main_frame, bg='#14141e')
    date_frame.pack(fill=tk.X, pady=5)
    tk.Checkbutton(date_frame, text="Fecha:", variable=date_var, bg='#14141e', fg='white', selectcolor='black').pack(side=tk.LEFT)
    date_entry = tk.Entry(date_frame, bg='#cba6f7', fg='black')
    date_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))
    
    # Ayuda sobre formatos de fecha
    tk.Label(main_frame, text="Formatos de fecha: YYYY-MM-DD, mes YYYY, YYYY, hoy, esta semana...", 
            bg='#14141e', fg='#888888', font=('Arial', 9)).pack(pady=(0, 10))
    
    # Botones
    buttons_frame = tk.Frame(main_frame, bg='#14141e')
    buttons_frame.pack(fill=tk.X, pady=10)
    
    tk.Button(buttons_frame, text="Cancelar", command=search_window.destroy, 
             bg='#ff8b8b', fg='black').pack(side=tk.LEFT, padx=5)
    
    tk.Button(buttons_frame, text="Buscar", command=ejecutar_busqueda,
             bg='#1974D2', fg='white').pack(side=tk.RIGHT, padx=5)

def menu_principal():
    """Crea el menú principal de la aplicación."""
    menu_bar = tk.Menu(root)
    root.config(menu=menu_bar)
    
    # Menú Archivo
    file_menu = tk.Menu(menu_bar, tearoff=0)
    menu_bar.add_cascade(label="Archivo", menu=file_menu)
    file_menu.add_command(label="Búsqueda Avanzada", command=buscar_avanzada)
    file_menu.add_separator()
    file_menu.add_command(label="Salir", command=root.quit)
    
    # Menú Editar
    edit_menu = tk.Menu(menu_bar, tearoff=0)
    menu_bar.add_cascade(label="Editar", menu=edit_menu)
    edit_menu.add_command(label="Editar archivo seleccionado", command=edit_file)
    edit_menu.add_command(label="Abrir carpeta", command=open_folder)
    edit_menu.add_command(label="Ver tags", command=show_tags)
    edit_menu.add_command(label="Eliminar archivo", command=delete_file)
    
    # Menú Ver
    view_menu = tk.Menu(menu_bar, tearoff=0)
    menu_bar.add_cascade(label="Ver", menu=view_menu)
    view_menu.add_command(label="Estadísticas", command=mostrar_estadisticas)
    
    # Menú Ayuda
    help_menu = tk.Menu(menu_bar, tearoff=0)
    menu_bar.add_cascade(label="Ayuda", menu=help_menu)
    help_menu.add_command(label="Acerca de", command=acerca_de)
    help_menu.add_command(label="Ayuda", command=mostrar_ayuda)

def mostrar_estadisticas():
    """Muestra estadísticas sobre los archivos en la base de datos."""
    try:
        conn = conectar_db()
        if not conn:
            return
        
        cursor = conn.cursor()
        
        # Obtener estadísticas básicas
        cursor.execute("SELECT COUNT(*) FROM snippets")
        total_snippets = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM tags")
        total_tags = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT t.name, COUNT(st.snippet_id) as count
            FROM tags t
            JOIN snippet_tags st ON t.id = st.tag_id
            GROUP BY t.name
            ORDER BY count DESC
            LIMIT 10
        """)
        top_tags = cursor.fetchall()
        
        cursor.execute("""
            SELECT strftime('%Y-%m', last_modified) as month, COUNT(*) as count
            FROM snippets
            GROUP BY month
            ORDER BY month DESC
            LIMIT 12
        """)
        snippets_by_month = cursor.fetchall()
        
        conn.close()
        
        # Mostrar estadísticas en una ventana emergente
        stats_window = tk.Toplevel(root)
        stats_window.title("Estadísticas")
        stats_window.configure(bg='#14141e')
        stats_window.geometry("600x500")
        
        stats_frame = tk.Frame(stats_window, bg='#14141e', padx=20, pady=20)
        stats_frame.pack(fill=tk.BOTH, expand=True)
        
        # Estadísticas generales
        tk.Label(stats_frame, text="Estadísticas Generales", font=("Arial", 14, "bold"), 
                bg='#14141e', fg='#cba6f7').pack(anchor="w", pady=(0, 10))
        
        tk.Label(stats_frame, text=f"Total de archivos: {total_snippets}", 
                bg='#14141e', fg='white').pack(anchor="w")
        
        tk.Label(stats_frame, text=f"Total de tags: {total_tags}", 
                bg='#14141e', fg='white').pack(anchor="w", pady=(0, 20))
        
        # Tags más populares
        tk.Label(stats_frame, text="Tags más populares", font=("Arial", 14, "bold"), 
                bg='#14141e', fg='#cba6f7').pack(anchor="w", pady=(0, 10))
        
        tag_frame = tk.Frame(stats_frame, bg='#14141e')
        tag_frame.pack(fill=tk.X, pady=(0, 20))
        
        if top_tags:
            for tag in top_tags:
                tag_name = tag[0]
                tag_count = tag[1]
                tk.Label(tag_frame, text=f"{tag_name}: {tag_count}", 
                        bg='#14141e', fg='white').pack(anchor="w")
        else:
            tk.Label(tag_frame, text="No hay tags en la base de datos", 
                    bg='#14141e', fg='white').pack(anchor="w")
        
        # Archivos por mes
        tk.Label(stats_frame, text="Archivos por mes", font=("Arial", 14, "bold"), 
                bg='#14141e', fg='#cba6f7').pack(anchor="w", pady=(0, 10))
        
        month_frame = tk.Frame(stats_frame, bg='#14141e')
        month_frame.pack(fill=tk.X)
        
        if snippets_by_month:
            for month_data in snippets_by_month:
                month = month_data[0]
                count = month_data[1]
                tk.Label(month_frame, text=f"{month}: {count}", 
                        bg='#14141e', fg='white').pack(anchor="w")
        else:
            tk.Label(month_frame, text="No hay información de fecha disponible", 
                    bg='#14141e', fg='white').pack(anchor="w")
        
    except Exception as e:
        messagebox.showerror("Error", f"Error al obtener estadísticas: {e}")

def acerca_de():
    """Muestra información sobre la aplicación."""
    about_window = tk.Toplevel(root)
    about_window.title("Acerca de")
    about_window.configure(bg='#14141e')
    about_window.geometry("400x300")
    
    about_frame = tk.Frame(about_window, bg='#14141e', padx=20, pady=20)
    about_frame.pack(fill=tk.BOTH, expand=True)
    
    tk.Label(about_frame, text="Buscador de Markdown en Base de Datos", 
            font=("Arial", 16, "bold"), bg='#14141e', fg='#cba6f7').pack(pady=(0, 20))
    
    tk.Label(about_frame, text="Una aplicación para buscar y visualizar archivos Markdown\nalmacenados en una base de datos SQLite.", 
            bg='#14141e', fg='white', justify="left").pack(anchor="w", pady=(0, 10))
    
    tk.Label(about_frame, text="Desarrollado con Python, Tkinter y SQLite.", 
            bg='#14141e', fg='white').pack(anchor="w", pady=(0, 20))
    
    tk.Label(about_frame, text="Versión 1.0", 
            bg='#14141e', fg='white').pack(anchor="w")
    
    tk.Button(about_frame, text="Cerrar", command=about_window.destroy, 
             bg='#cba6f7', fg='black').pack(pady=20)

def mostrar_ayuda():
    """Muestra ayuda sobre cómo usar la aplicación."""
    html_content = """
    <html>
    <head>
        <style>
            body {
                background-color: #14141e;
                color: white;
                font-family: Arial, sans-serif;
                padding: 20px;
                line-height: 1.6;
            }
            h1, h2, h3 {
                color: #cba6f7;
            }
            code {
                background-color: #282a36;
                padding: 0.2em 0.4em;
                border-radius: 3px;
                font-family: monospace;
            }
            .shortcut {
                display: inline-block;
                background-color: #282a36;
                padding: 2px 8px;
                border-radius: 4px;
                margin: 2px;
            }
        </style>
    </head>
    <body>
        <h1>Ayuda - Buscador de Markdown</h1>
        
        <h2>Búsqueda</h2>
        <p>Para buscar, simplemente escribe en el campo de búsqueda. La aplicación buscará en títulos y contenido de los archivos.</p>
        <p>Para una búsqueda más específica, usa el menú <b>Archivo > Búsqueda Avanzada</b>.</p>
        
        <h2>Visualización</h2>
        <p>Al seleccionar un archivo en la lista de resultados, su contenido se mostrará en el panel derecho con formato.</p>
        
        <h2>Atajos de teclado</h2>
        <ul>
            <li><span class="shortcut">Ctrl+F</span> - Enfoca el campo de búsqueda</li>
            <li><span class="shortcut">Ctrl+E</span> - Edita el archivo seleccionado</li>
            <li><span class="shortcut">Ctrl+O</span> - Abre la carpeta del archivo</li>
            <li><span class="shortcut">Ctrl+T</span> - Muestra los tags del archivo</li>
            <li><span class="shortcut">Delete</span> - Elimina el archivo seleccionado</li>
        </ul>
        
        <h2>Gestión de Tags</h2>
        <p>Puedes ver los tags asociados a un archivo usando el botón <b>Ver Tags</b> o presionando <span class="shortcut">Ctrl+T</span>.</p>
        <p>Para buscar por tags específicos, utiliza la función de búsqueda avanzada.</p>
    </body>
    </html>
    """
    
    help_window = tk.Toplevel(root)
    help_window.title("Ayuda")
    help_window.configure(bg='#14141e')
    help_window.geometry("700x600")
    
    help_frame = HtmlFrame(help_window, horizontal_scrollbar="auto")
    help_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    help_frame.load_html(html_content)

def crear_indexador():
    """Crea una ventana para indexar archivos en la base de datos."""
    def ejecutar_indexacion():
        ruta = ruta_entry.get()
        
        if not os.path.isdir(ruta):
            messagebox.showerror("Error", "La ruta especificada no es un directorio válido")
            return
        
        try:
            # Función que realiza la indexación
            total_archivos = indexar_directorio(ruta, recursivo.get())
            messagebox.showinfo("Indexación Completada", f"Se han indexado {total_archivos} archivos.")
            indexar_window.destroy()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error durante la indexación: {e}")
    
    indexar_window = tk.Toplevel(root)
    indexar_window.title("Indexar Archivos")
    indexar_window.configure(bg='#14141e')
    indexar_window.geometry("500x250")
    
    indexar_frame = tk.Frame(indexar_window, bg='#14141e', padx=20, pady=20)
    indexar_frame.pack(fill=tk.BOTH, expand=True)
    
    tk.Label(indexar_frame, text="Indexar archivos Markdown a la base de datos", 
            font=("Arial", 14, "bold"), bg='#14141e', fg='#cba6f7').pack(pady=(0, 20))
    
    ruta_frame = tk.Frame(indexar_frame, bg='#14141e')
    ruta_frame.pack(fill=tk.X, pady=5)
    
    tk.Label(ruta_frame, text="Directorio:", bg='#14141e', fg='white').pack(side=tk.LEFT)
    
    ruta_entry = tk.Entry(ruta_frame, bg='#cba6f7', fg='black', width=40)
    ruta_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 5))
    ruta_entry.insert(0, "/mnt/windows/FTP/wiki/Obsidian/")
    
    def seleccionar_directorio():
        directorio = tk.filedialog.askdirectory(initialdir=ruta_entry.get())
        if directorio:
            ruta_entry.delete(0, tk.END)
            ruta_entry.insert(0, directorio)
    
    tk.Button(ruta_frame, text="...", command=seleccionar_directorio, 
             bg='#f8bd9a', fg='black', width=3).pack(side=tk.LEFT)
    
    # Opciones de indexación
    opciones_frame = tk.Frame(indexar_frame, bg='#14141e')
    opciones_frame.pack(fill=tk.X, pady=10)
    
    recursivo = tk.BooleanVar(value=True)
    tk.Checkbutton(opciones_frame, text="Buscar recursivamente en subdirectorios", 
                  variable=recursivo, bg='#14141e', fg='white', 
                  selectcolor='black').pack(anchor="w")
    
    # Botones
    botones_frame = tk.Frame(indexar_frame, bg='#14141e')
    botones_frame.pack(fill=tk.X, pady=20)
    
    tk.Button(botones_frame, text="Cancelar", command=indexar_window.destroy, 
             bg='#ff8b8b', fg='black', width=10).pack(side=tk.LEFT)
    
    tk.Button(botones_frame, text="Indexar", command=ejecutar_indexacion, 
             bg='#1974D2', fg='white', width=10).pack(side=tk.RIGHT)

def indexar_directorio(ruta_base, recursivo=True):
    """Indexa los archivos Markdown en el directorio especificado a la base de datos."""
    conn = conectar_db()
    if not conn:
        return 0
    
    cursor = conn.cursor()
    
    # Verificar si las tablas existen, si no, crearlas
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS snippets (
        id INTEGER PRIMARY KEY,
        filename TEXT NOT NULL,
        path TEXT NOT NULL,
        content TEXT,
        source TEXT DEFAULT 'obsidian',
        last_modified TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tags (
        id INTEGER PRIMARY KEY,
        name TEXT UNIQUE NOT NULL
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS snippet_tags (
        snippet_id INTEGER,
        tag_id INTEGER,
        PRIMARY KEY (snippet_id, tag_id),
        FOREIGN KEY (snippet_id) REFERENCES snippets(id) ON DELETE CASCADE,
        FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
    )
    """)
    
    # Crear índices para mejorar el rendimiento
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_snippets_filename ON snippets (filename)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_snippets_path ON snippets (path)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tags_name ON tags (name)")
    
    # Si es posible, crear una tabla de búsqueda de texto completo (FTS)
    try:
        cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS snippets_fts USING fts5(
            content,
            content='snippets',
            content_rowid='id'
        )
        """)
        
        # Trigger para mantener actualizada la tabla FTS
        cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS snippets_ai AFTER INSERT ON snippets
        BEGIN
            INSERT INTO snippets_fts(rowid, content) VALUES (new.id, new.content);
        END
        """)
        
        cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS snippets_au AFTER UPDATE ON snippets
        BEGIN
            INSERT INTO snippets_fts(snippets_fts, rowid, content) VALUES('delete', old.id, old.content);
            INSERT INTO snippets_fts(rowid, content) VALUES (new.id, new.content);
        END
        """)
        
        cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS snippets_ad AFTER DELETE ON snippets
        BEGIN
            INSERT INTO snippets_fts(snippets_fts, rowid, content) VALUES('delete', old.id, old.content);
        END
        """)
    except sqlite3.Error as e:
        print(f"No se pudo crear la tabla FTS: {e}")
    
    conn.commit()
    
    # Función para extraer tags de contenido markdown
    def extraer_tags(contenido):
        # Buscar tags con formato #tag en el contenido
        tags = re.findall(r'#(\w+)', contenido)
        # También buscar tags en el frontmatter YAML
        frontmatter_tags = []
        yaml_match = re.search(r'---\s*\n(.*?)\n\s*---', contenido, re.DOTALL)
        if yaml_match:
            yaml_content = yaml_match.group(1)
            # Buscar líneas como "tags: [tag1, tag2]" o "tags:\n- tag1\n- tag2"
            tag_line = re.search(r'tags:\s*\[(.*?)\]', yaml_content)
            if tag_line:
                frontmatter_tags.extend([t.strip() for t in tag_line.group(1).split(',') if t.strip()])
            else:
                tag_lines = re.search(r'tags:\s*\n((?:- .*\n)+)', yaml_content)
                if tag_lines:
                    frontmatter_tags.extend([t.strip()[2:] for t in tag_lines.group(1).split('\n') if t.strip()])
        
        # Combinar y eliminar duplicados
        all_tags = list(set(tags + frontmatter_tags))
        return all_tags
    
    # Contador de archivos indexados
    contador = 0
    
    # Patrón para archivos markdown
    patron = "**/*.md" if recursivo else "*.md"
    
    # Recorrer los archivos
    for archivo in glob.glob(os.path.join(ruta_base, patron), recursive=recursivo):
        try:
            # Obtener ruta y nombre del archivo
            ruta_completa = os.path.abspath(archivo)
            nombre_archivo = os.path.basename(archivo)
            ruta_carpeta = os.path.dirname(ruta_completa)
            
            # Comprobar si el archivo ya existe en la base de datos
            cursor.execute(
                "SELECT id FROM snippets WHERE path = ? AND filename = ?", 
                (ruta_carpeta, nombre_archivo)
            )
            existe = cursor.fetchone()
            
            # Obtener fecha de modificación
            fecha_mod = datetime.datetime.fromtimestamp(os.path.getmtime(ruta_completa)).strftime('%Y-%m-%d %H:%M:%S')
            
            # Leer contenido del archivo
            with open(ruta_completa, 'r', encoding='utf-8') as f:
                contenido = f.read()
            
            # Extraer tags
            tags = extraer_tags(contenido)
            
            if existe:
                # Actualizar el archivo existente
                snippet_id = existe[0]
                cursor.execute(
                    "UPDATE snippets SET content = ?, last_modified = ? WHERE id = ?",
                    (contenido, fecha_mod, snippet_id)
                )
            else:
                # Insertar nuevo archivo
                cursor.execute(
                    "INSERT INTO snippets (filename, path, content, last_modified) VALUES (?, ?, ?, ?)",
                    (nombre_archivo, ruta_carpeta, contenido, fecha_mod)
                )
                snippet_id = cursor.lastrowid
            
            # Eliminar tags antiguos si es una actualización
            if existe:
                cursor.execute("DELETE FROM snippet_tags WHERE snippet_id = ?", (snippet_id,))
            
            # Insertar tags
            for tag in tags:
                # Insertar tag si no existe
                cursor.execute(
                    "INSERT OR IGNORE INTO tags (name) VALUES (?)",
                    (tag,)
                )
                
                # Obtener ID del tag
                cursor.execute("SELECT id FROM tags WHERE name = ?", (tag,))
                tag_id = cursor.fetchone()[0]
                
                # Relacionar snippet con tag
                cursor.execute(
                    "INSERT INTO snippet_tags (snippet_id, tag_id) VALUES (?, ?)",
                    (snippet_id, tag_id)
                )
            
            contador += 1
            
            # Commit cada 100 archivos para no perder progreso
            if contador % 100 == 0:
                conn.commit()
                
        except Exception as e:
            print(f"Error al procesar archivo {archivo}: {e}")
    
    # Commit final
    conn.commit()
    conn.close()
    
    return contador

def inicializar_db():
    """Inicializa la base de datos si no existe."""
    # Verificar si el directorio existe
    db_dir = os.path.dirname(DB_PATH)
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)
    
    conn = conectar_db()
    if not conn:
        return False
    
    cursor = conn.cursor()
    
    # Crear tablas necesarias
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS snippets (
        id INTEGER PRIMARY KEY,
        filename TEXT NOT NULL,
        path TEXT NOT NULL,
        content TEXT,
        source TEXT DEFAULT 'obsidian',
        last_modified TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tags (
        id INTEGER PRIMARY KEY,
        name TEXT UNIQUE NOT NULL
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS snippet_tags (
        snippet_id INTEGER,
        tag_id INTEGER,
        PRIMARY KEY (snippet_id, tag_id),
        FOREIGN KEY (snippet_id) REFERENCES snippets(id) ON DELETE CASCADE,
        FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
    )
    """)
    
    conn.commit()
    conn.close()
    
    return True

def exportar_a_archivo():
    """Exporta un snippet seleccionado a un archivo."""
    selected = get_selected_snippet()
    if not selected:
        messagebox.showinfo("Selección", "Por favor, selecciona un archivo primero.")
        return
    
    _, item, _ = selected
    snippet_id = item['id']
    
    # Obtener el contenido del snippet
    conn = conectar_db()
    if not conn:
        return
    
    cursor = conn.cursor()
    cursor.execute("SELECT content FROM snippets WHERE id = ?", (snippet_id,))
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        messagebox.showerror("Error", "No se pudo obtener el contenido del archivo.")
        return
    
    contenido = result[0]
    
    # Solicitar ubicación para guardar
    file_path = tk.filedialog.asksaveasfilename(
        defaultextension=".md",
        filetypes=[("Markdown files", "*.md"), ("Text files", "*.txt"), ("All files", "*.*")],
        initialfile=item['filename']
    )
    
    if not file_path:
        return  # Usuario canceló
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(contenido)
        messagebox.showinfo("Éxito", f"Archivo guardado como {file_path}")
    except Exception as e:
        messagebox.showerror("Error", f"Error al guardar el archivo: {e}")

def administrar_tags():
    """Abre una ventana para administrar todos los tags."""
    tags_window = tk.Toplevel(root)
    tags_window.title("Administrar Tags")
    tags_window.configure(bg='#14141e')
    tags_window.geometry("600x500")
    
    # Frame principal
    main_frame = tk.Frame(tags_window, bg='#14141e', padx=20, pady=20)
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # Frame para la lista y botones
    list_frame = tk.Frame(main_frame, bg='#14141e')
    list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
    # Título
    tk.Label(list_frame, text="Tags disponibles", font=("Arial", 14, "bold"), 
            bg='#14141e', fg='#cba6f7').pack(anchor="w", pady=(0, 10))
    
    # Lista de tags
    tag_listbox = tk.Listbox(list_frame, bg='#14141e', fg='white', font=('Arial', 12), 
                            selectbackground='#cba6f7', selectforeground='black',
                            width=30, height=15)
    tag_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
    # Scrollbar para la lista
    scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=tag_listbox.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    tag_listbox.config(yscrollcommand=scrollbar.set)
    
    # Frame para información
    info_frame = tk.Frame(main_frame, bg='#14141e')
    info_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(20, 0))
    
    # Etiqueta info
    info_label = tk.Label(info_frame, text="Selecciona un tag para ver detalles", 
                         font=("Arial", 12), bg='#14141e', fg='white', 
                         wraplength=200, justify="left")
    info_label.pack(anchor="w", pady=(30, 10))
    
    # Etiqueta contador
    count_label = tk.Label(info_frame, text="", font=("Arial", 10), 
                          bg='#14141e', fg='white')
    count_label.pack(anchor="w")
    
    # Botones
    buttons_frame = tk.Frame(info_frame, bg='#14141e')
    buttons_frame.pack(anchor="w", pady=20)
    
    # Función para actualizar la lista de tags
    def cargar_tags():
        tag_listbox.delete(0, tk.END)
        
        conn = conectar_db()
        if not conn:
            return
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.name, COUNT(st.snippet_id) as count
            FROM tags t
            LEFT JOIN snippet_tags st ON t.id = st.tag_id
            GROUP BY t.name
            ORDER BY t.name
        """)
        
        tags = cursor.fetchall()
        conn.close()
        
        for tag in tags:
            tag_listbox.insert(tk.END, f"{tag[0]} ({tag[1]})")
    
    # Cargar tags iniciales
    cargar_tags()
    
    # Función para mostrar detalles de un tag
    def mostrar_detalles_tag(event):
        if not tag_listbox.curselection():
            return
        
        # Obtener el tag seleccionado (sin el contador)
        selected_tag = tag_listbox.get(tag_listbox.curselection()[0]).split(' (')[0]
        
        conn = conectar_db()
        if not conn:
            return
        
        cursor = conn.cursor()
        
        # Contar documentos con este tag
        cursor.execute("""
            SELECT COUNT(st.snippet_id)
            FROM snippet_tags st
            JOIN tags t ON st.tag_id = t.id
            WHERE t.name = ?
        """, (selected_tag,))
        
        count = cursor.fetchone()[0]
        
        # Mostrar información
        info_label.config(text=f"Tag: {selected_tag}")
        count_label.config(text=f"Usado en {count} archivos")
        
        conn.close()
    
    # Función para eliminar un tag
def eliminar_tag():
    if not tag_listbox.curselection():
        messagebox.showinfo("Selección", "Por favor, selecciona un tag primero.")
        return
    
    # Obtener el tag seleccionado (sin el contador)
    selected_tag = tag_listbox.get(tag_listbox.curselection()[0]).split(' (')[0]
    
    # Confirmar eliminación
    confirm = messagebox.askyesno(
        "Confirmar Eliminación", 
        f"¿Estás seguro de eliminar el tag '{selected_tag}'? Esta acción eliminará el tag de todos los archivos."
    )
    
    if confirm:
        try:
            conn = conectar_db()
            if not conn:
                return
            
            cursor = conn.cursor()
            
            # Obtener ID del tag
            cursor.execute("SELECT id FROM tags WHERE name = ?", (selected_tag,))
            result = cursor.fetchone()
            
            if result:
                tag_id = result[0]
                
                # Eliminar relaciones
                cursor.execute("DELETE FROM snippet_tags WHERE tag_id = ?", (tag_id,))
                
                # Eliminar tag
                cursor.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
                
                conn.commit()
                conn.close()
                
                messagebox.showinfo("Éxito", f"El tag '{selected_tag}' ha sido eliminado.")
                
                # Recargar lista de tags
                cargar_tags()
                
                # Limpiar etiquetas de información
                info_label.config(text="Selecciona un tag para ver detalles")
                count_label.config(text="")
            else:
                messagebox.showerror("Error", f"No se encontró el tag '{selected_tag}'.")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error al eliminar el tag: {e}")
    
    # Función para renombrar un tag
    def renombrar_tag():
        if not tag_listbox.curselection():
            messagebox.showinfo("Selección", "Por favor, selecciona un tag primero.")
            return
        
        # Obtener el tag seleccionado (sin el contador)
        selected_tag = tag_listbox.get(tag_listbox.curselection()[0]).split(' (')[0]
        
        # Pedir nuevo nombre
        nuevo_nombre = tk.simpledialog.askstring("Renombrar Tag", 
                                              f"Nuevo nombre para el tag '{selected_tag}':", 
                                              parent=tags_window)
        
        if not nuevo_nombre:
            return  # Usuario canceló o dejó en blanco
        
        try:
            conn = conectar_db()
            if not conn:
                return
            
            cursor = conn.cursor()
            
            # Verificar si ya existe un tag con ese nombre
            cursor.execute("SELECT id FROM tags WHERE name = ?", (nuevo_nombre,))
            exists = cursor.fetchone()
            
            if exists:
                messagebox.showerror("Error", f"Ya existe un tag con el nombre '{nuevo_nombre}'.")
                conn.close()
                return
            
            # Actualizar nombre del tag
            cursor.execute("UPDATE tags SET name = ? WHERE name = ?", (nuevo_nombre, selected_tag))
            
            conn.commit()
            conn.close()
            
            messagebox.showinfo("Éxito", f"Tag renombrado de '{selected_tag}' a '{nuevo_nombre}'.")
            
            # Recargar lista de tags
            cargar_tags()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al renombrar el tag: {e}")
    
    # Función para mostrar archivos con un tag específico
    def ver_archivos_con_tag():
        if not tag_listbox.curselection():
            messagebox.showinfo("Selección", "Por favor, selecciona un tag primero.")
            return
        
        # Obtener el tag seleccionado (sin el contador)
        selected_tag = tag_listbox.get(tag_listbox.curselection()[0]).split(' (')[0]
        
        # Cerrar ventana actual
        tags_window.destroy()
        
        # Configurar búsqueda con este tag
        search_entry.delete(0, tk.END)
        search_entry.insert(0, "#" + selected_tag)
        update_results()
    
    # Añadir botones para las acciones
    ver_button = tk.Button(buttons_frame, text="Ver Archivos", command=ver_archivos_con_tag,
                         bg='#1974D2', fg='white', width=15)
    ver_button.pack(anchor="w", pady=5)
    
    rename_button = tk.Button(buttons_frame, text="Renombrar", command=renombrar_tag,
                            bg='#cba6f7', fg='black', width=15)
    rename_button.pack(anchor="w", pady=5)
    
    delete_button = tk.Button(buttons_frame, text="Eliminar", command=eliminar_tag,
                            bg='#ff8b8b', fg='black', width=15)
    delete_button.pack(anchor="w", pady=5)
    
    # Asociar evento de selección
    tag_listbox.bind('<<ListboxSelect>>', mostrar_detalles_tag)
    
    # Botón cerrar
    tk.Button(main_frame, text="Cerrar", command=tags_window.destroy,
             bg='#282a36', fg='white', width=10).pack(side=tk.BOTTOM, pady=10)

def main():
    """Función principal que inicia la aplicación."""
    # Inicializar la base de datos si no existe
    if not inicializar_db():
        messagebox.showerror("Error", "No se pudo inicializar la base de datos.")
        return
    
    # Verificar conexión a la base de datos
    if not check_db_connection():
        return
    
    # Crear la interfaz gráfica
    create_gui()
    
    # Añadir menú principal
    menu_principal()

if __name__ == "__main__":
    main()