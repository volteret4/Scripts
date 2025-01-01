
#!/usr/bin/env python
#
# Script Name: fuzzy.py
# Description: 
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# TODO: - No muestra coincidencias por contenido
#       - No coinciden indices de archivo y contendio en grupos >2
#       - 
# Notes:
#   Dependencies:  - python3, 
#

import os
import tkinter as tk
import re
import glob

# Define el directorio donde están tus archivos Markdown
SEARCH_DIR = "/mnt/windows/FTP/wiki/Obsidian/"

# Lista de subcarpetas a ignorar
EXCLUDE_DIRS = [
    "/mnt/windows/FTP/wiki/Obsidian/Plantillas",
    "/mnt/windows/FTP/wiki/Obsidian/.trash",
    "/mnt/windows/FTP/wiki/Obsidian/Dibujos",
    "/mnt/windows/FTP/wiki/Obsidian/.obsidian",
    "/mnt/windows/FTP/wiki/Obsidian/.makemd",
    "/mnt/windows/FTP/wiki/Obsidian/.space",
    "/mnt/windows/FTP/wiki/Obsidian/logseq",
]

def search_files(query):
    """Realiza la búsqueda de archivos Markdown que coincidan con la consulta."""
    title_matches = []
    content_matches = []
    important_matches = []
    wallabag_matches = []
    journal_matches = []

    for filename in glob.iglob(os.path.join(SEARCH_DIR, '**', '*.md'), recursive=True):
        # Ignorar archivos en las carpetas excluidas
        if any(excluded in filename for excluded in EXCLUDE_DIRS):
            continue
        
        title = os.path.basename(filename).replace('.md', '')  # Eliminar la extensión .md
        found_content_lines = set()  # Usamos un set para evitar duplicados en el contenido

        # Buscar coincidencias en el título
        if re.search(query, title, re.IGNORECASE):
            title_matches.append((filename, title))
            with open(filename, 'r', encoding='utf-8') as file:
                content = file.read()
                # Eliminar secciones delimitadas por '---'
                ###content = re.sub(r'---.*?---', '', content, flags=re.DOTALL).strip()
                
                # Buscar líneas que coincidan con la consulta en el contenido
                for line_number, line in enumerate(content.splitlines(), start=1):
                    if re.search(query, line, re.IGNORECASE):
                        found_content_lines.add(f"Línea {line_number}: {line.strip()}")

        # Clasificación según ruta
        if '/Important/' in filename:
            if re.search(query, title, re.IGNORECASE):  # Filtrar según el título
                important_matches.append((filename, f"{title}"))
        elif '/Spaces/Wallabag/' in filename:
            if re.search(query, title, re.IGNORECASE):  # Filtrar según el título
                wallabag_matches.append((filename, f"{title}"))
        elif '/journals/' in filename:
            if re.search(query, title, re.IGNORECASE):  # Filtrar según el título
                journal_matches.append((filename, f"{title}"))

    return title_matches, list(found_content_lines), important_matches, wallabag_matches, journal_matches

def update_results(event):
    """Actualiza la lista de resultados según el texto de búsqueda."""
    query = search_entry.get()
    global title_results, content_results, important_results, wallabag_results, journal_results  # Asegúrate de que son variables globales
    title_results, content_results, important_results, wallabag_results, journal_results = search_files(query)

    # Limpiar la lista de resultados
    result_list.delete(0, tk.END)

    # Agregar coincidencias en títulos en negrita o mayúsculas
    if title_results:
        result_list.insert(tk.END, "RESULTADOS EN TÍTULO")
        result_list.itemconfig(tk.END, {'fg': '#cba6f7'})  # Cambiar color a #cba6f7
        for filename, title in title_results:
            result_list.insert(tk.END, title)  # Títulos en mayúsculas
        result_list.insert(tk.END, "")  # Línea en blanco

    # Agregar coincidencias en contenido
    if content_results:
        result_list.insert(tk.END, "RESULTADOS EN CONTENIDO".upper())  # Contenido en mayúsculas y en color #cba6f7
        result_list.itemconfig(tk.END, {'fg': '#cba6f7'})  # Cambiar color a #cba6f7
        for line in content_results:
            result_list.insert(tk.END, line)
        result_list.insert(tk.END, "")  # Línea en blanco

    # Agregar coincidencias en rutas
    if important_results:
        result_list.insert(tk.END, "RESULTADOS EN IMPORTANT:".upper())
        result_list.itemconfig(tk.END, {'fg': '#cba6f7'})  # Cambiar color a #cba6f7
        for filename, title in important_results:
            result_list.insert(tk.END, title)
        result_list.insert(tk.END, "")  # Línea en blanco

    if wallabag_results:
        result_list.insert(tk.END, "RESULTADOS EN WALLABAG:".upper())
        result_list.itemconfig(tk.END, {'fg': '#cba6f7'})  # Cambiar color a #cba6f7
        for filename, title in wallabag_results:
            result_list.insert(tk.END, title)
        result_list.insert(tk.END, "")  # Línea en blanco

    if journal_results:
        result_list.insert(tk.END, "RESULTADOS EN JOURNALS:".upper())
        result_list.itemconfig(tk.END, {'fg': '#cba6f7'})  # Cambiar color a #cba6f7
        for filename, title in journal_results:
            result_list.insert(tk.END, title)

    # Limpiar el contenido mostrado
    content_text.delete(1.0, tk.END)

def display_file_content(filename, query):
    """Muestra el contenido del archivo en el área de texto, resaltando la búsqueda."""
    with open(filename, 'r', encoding='utf-8') as file:
        content = file.read()
        # Eliminar secciones delimitadas por '---'
        content = re.sub(r'---.*?---', '', content, flags=re.DOTALL).strip()
        content_text.delete(1.0, tk.END)  # Limpiar el área de texto antes de mostrar nuevo contenido
        content_text.insert(tk.END, content)  # Mostrar el contenido del archivo

        # Resaltar el texto buscado
        if query:
            start_index = '1.0'
            while True:
                start_index = content_text.search(query, start_index, stopindex=tk.END, nocase=True)
                if not start_index:
                    break
                end_index = f"{start_index}+{len(query)}c"
                content_text.tag_add("highlight", start_index, end_index)
                start_index = end_index

def on_select(event):
    """Muestra el contenido del archivo seleccionado en la lista de resultados."""
    selection = result_list.curselection()
    if selection:
        index = selection[0]
        filename = None

        # Variable de compensación para ajustar los índices debido a los títulos y líneas vacías
        adjusted_index = index

        # Ajustar el índice para los títulos y las líneas vacías
        if title_results:
            adjusted_index -= 1  # Descontar el título de "RESULTADOS EN TÍTULO" y la línea en blanco
        if adjusted_index < len(title_results):  # Es un archivo del grupo de Títulos
            filename, _ = title_results[adjusted_index]
        else:
            adjusted_index -= len(title_results) + 1  # Descontar los resultados de título y salto de línea

            if content_results:
                adjusted_index -= 1  # Descontar el título de "RESULTADOS EN CONTENIDO" y la línea en blanco
            if adjusted_index < len(content_results):  # Es un archivo del grupo de Contenidos
                line = content_results[adjusted_index]  # Aquí solo tienes las líneas, no los archivos
                # Si quieres mostrar el archivo donde está la línea, deberías usar la lógica para asignar el archivo
            else:
                adjusted_index -= len(content_results) + 2  # Descontar los resultados de contenido y salto de línea

                if important_results:
                    adjusted_index -= 1  # Descontar el título de "RESULTADOS EN IMPORTANT" y la línea en blanco
                if adjusted_index < len(important_results):  # Es un archivo del grupo de Important
                    filename, _ = important_results[adjusted_index]
                else:
                    adjusted_index -= len(important_results) + 2  # Descontar los resultados de Important y salto de línea

                    if wallabag_results:
                        adjusted_index -= 1  # Descontar el título de "RESULTADOS EN WALLABAG" y la línea en blanco
                    if adjusted_index < len(wallabag_results):  # Es un archivo del grupo de Wallabag
                        filename, _ = wallabag_results[adjusted_index]
                    else:
                        adjusted_index -= len(wallabag_results) + 2  # Descontar los resultados de Wallabag y salto de línea

                        if journal_results:
                            adjusted_index -= 1  # Descontar el título de "RESULTADOS EN JOURNALS" y la línea en blanco
                        if adjusted_index < len(journal_results):  # Es un archivo del grupo de Journals
                            filename, _ = journal_results[adjusted_index]

        if filename:
            # Mostrar el contenido del archivo seleccionado
            display_file_content(filename, search_entry.get())



def focus_search(event=None):
    """Focaliza el campo de búsqueda."""
    search_entry.focus_set()

# Función para abrir el archivo con el programa predeterminado
def open_current_file(event=None):
    """Abre el archivo que se está mostrando actualmente."""
    selection = result_list.curselection()
    if selection:
        index = selection[0]
        filename = None

        # Verificar si el índice está dentro de los títulos
        if 1 <= index <= len(title_results):  # Es un título
            filename, _ = title_results[index - 1]
        elif len(title_results) + 2 <= index <= len(title_results) + 1 + len(content_results):
            adjusted_index = index - len(title_results) - 2
            filename = content_results[adjusted_index]
        elif len(title_results) + len(content_results) + 3 <= index <= len(title_results) + len(content_results) + 2 + len(important_results):
            adjusted_index = index - len(title_results) - len(content_results) - 3
            filename, _ = important_results[adjusted_index]
        elif len(title_results) + len(content_results) + len(important_results) + 4 <= index <= len(title_results) + len(content_results) + len(important_results) + 3 + len(wallabag_results):
            adjusted_index = index - len(title_results) - len(content_results) - len(important_results) - 4
            filename, _ = wallabag_results[adjusted_index]
        elif len(title_results) + len(content_results) + len(important_results) + len(wallabag_results) + 5 <= index <= len(title_results) + len(content_results) + len(important_results) + len(wallabag_results) + 4 + len(journal_results):
            adjusted_index = index - len(title_results) - len(content_results) - len(important_results) - len(wallabag_results) - 5
            filename, _ = journal_results[adjusted_index]

        if filename:
            # Abrir el archivo con el programa predeterminado
            os.system(f"geany '{filename}'")

def create_gui():
    """Crea la interfaz gráfica."""
    global root, search_entry, result_list, content_text, title_results, content_results, important_results, wallabag_results, journal_results
    root = tk.Tk()
    root.title("Buscador de archivos Markdown")
    
    # Cambiar colores y tamaño de la ventana
    root.configure(bg='#14141e')  # Color de fondo oscuro para el menú principal
    root.geometry("1600x900")  # Aumentar tamaño de la ventana principal

    # Campo de búsqueda
    search_entry = tk.Entry(root, bg='#cba6f7', fg='black', font=('FiraCode', 14))  # Cambiar a color #cba6f7 y aumentar fuente
    search_entry.pack(pady=(5, 5), padx=3)  # Márgenes reducidos a 3px
    search_entry.bind('<KeyRelease>', update_results)  # Actualiza resultados al escribir

    # Frame para la lista de resultados y el contenido
    frame = tk.Frame(root, bg='#14141e')  # Establecer fondo del frame
    frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

    # Lista de resultados
    result_list = tk.Listbox(
        frame, 
        selectmode=tk.SINGLE, 
        bg='#14141e', 
        fg='white', 
        bd=0, 
        font=('FiraCode', 11),
        selectbackground='#cba6f7',  # Color de fondo al seleccionar
        selectforeground='black'      # Color de texto al seleccionar
    )
    result_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 10), pady=(5, 5))  # Márgenes añadidos


    # Área de texto para mostrar el contenido del archivo
    content_text = tk.Text(frame, wrap=tk.WORD, bg='#14141e', fg='white', bd=0, font=('Nerdfont', 11))  # Cambiar a color #14141e
    content_text.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=3)  # Añadir márgenes
    content_text.tag_config("highlight", foreground="#cba6f7")  # Resaltar texto


    # Atajo de teclado para enfocar el campo de búsqueda
    root.bind("<Control-f>", lambda event: focus_search())  # Ctrl+F para enfocar el campo de búsqueda
    # Atajo de teclado para abrir el archivo mostrado al presionar Ctrl + O
    root.bind("<Control-o>", open_current_file)

    # Focalizar automáticamente el campo de búsqueda al iniciar
    focus_search()

    # Conectar el evento de selección
    result_list.bind("<<ListboxSelect>>", on_select)

    # Iniciar la interfaz gráfica
    root.mainloop()

if __name__ == "__main__":
    title_results = []
    content_results = []
    important_results = []
    wallabag_results = []
    journal_results = []
    create_gui()
