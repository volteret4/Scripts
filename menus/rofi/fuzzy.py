#!/usr/bin/env python
# Script Name: fuzzy.py
# Description:
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# TODO: 
# - No muestra coincidencias por contenido
# - No coinciden indices de archivo y contenido en grupos >2
# 
# Notes:
# Dependencies: - python3,

import os
import tkinter as tk
import re
import glob
import subprocess
import tkinter.messagebox as messagebox

# Define el directorio donde están tus archivos Markdown
SEARCH_DIR = "/mnt/windows/FTP/wiki/Obsidian/"

def search_files(query):
    """Realiza la búsqueda de archivos Markdown que coincidan con la consulta."""
    title_matches = []
    content_matches = {}
    important_matches = []
    wallabag_matches = []
    journal_matches = []

    for filename in glob.iglob(os.path.join(SEARCH_DIR, '**', '*.md'), recursive=True):
        title = os.path.basename(filename).replace('.md', '')  # Eliminar la extensión .md

        # Buscar coincidencias en el título
        if re.search(query, title, re.IGNORECASE):
            title_matches.append((filename, title))  # Agregar a coincidencias de título

            # Verificar si "wallabag" está en el nombre del archivo
            if "wallabag" in filename.lower():  
                wallabag_matches.append((filename, title))  # Solo si "wallabag" está en el título

        # Leer el contenido del archivo
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                content = file.read()
                # Eliminar secciones delimitadas por '---'
                content = re.sub(r'---.*?---', '', content, flags=re.DOTALL).strip()

                # Verificar si hay coincidencias en el contenido
                if re.search(query, content, re.IGNORECASE):
                    content_matches[filename] = title  # Almacenar el título solo una vez

                    # Verificar si "wallabag" está en el contenido
                    if "wallabag" in content.lower():  
                        wallabag_matches.append((filename, title))  # Agregar si hay coincidencia

        except Exception as e:
            print(f"Error al leer el archivo {filename}: {e}")

    return title_matches, list(content_matches.items()), important_matches, wallabag_matches, journal_matches
def update_results(event):
    """Actualiza la lista de resultados según el texto de búsqueda."""
    query = search_entry.get()
    global title_results, content_results, important_results, wallabag_results, journal_results  # Asegúrate de que son variables globales
    title_results, content_results, important_results, wallabag_results, journal_results = search_files(query)

    # Limpiar la lista de resultados
    result_list.delete(0, tk.END)

    # Agregar coincidencias en títulos
    for filename, title in title_results:
        result_list.insert(tk.END, title)  # Títulos en mayúsculas

    # Agregar coincidencias en contenido
    for filename, title in content_results:
        if "wallabag" in filename.lower():
            result_list.insert(tk.END, f"W {title}")
        elif "journal" in filename.lower():
            result_list.insert(tk.END, f"D {title}")
        elif "important" in filename.lower():
            result_list.insert(tk.END, f"T {title}")
        else:
            result_list.insert(tk.END, title)  # Mostrar contenido como un solo título

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
            first_match = None  # Variable para almacenar la primera coincidencia
            while True:
                start_index = content_text.search(query, start_index, stopindex=tk.END, nocase=True)
                if not start_index:
                    break
                end_index = f"{start_index}+{len(query)}c"
                content_text.tag_add("highlight", start_index, end_index)
                if first_match is None:  # Guardar la primera coincidencia
                    first_match = start_index
                start_index = end_index

            # Desplazarse a la primera coincidencia si existe
            if first_match:
                content_text.see(first_match)  # Desplaza el texto para que la coincidencia sea visible
                content_text.mark_set("insert", first_match)  # Coloca el cursor en la primera coincidencia

def on_select(event):
    """Muestra el contenido del archivo seleccionado en la lista de resultados."""
    selection = result_list.curselection()
    if selection:
        index = selection[0]  # Inicializa el nombre de archivo a None
        filename = None  # Verificar si el índice está dentro de los títulos
        if index < len(title_results):
            # Es un título
            filename, title = title_results[index]
        else:
            adjusted_index = index - len(title_results)  # Ajustar índice por los títulos
            # Determinar el grupo correcto
            if adjusted_index < len(content_results):
                # Es un resultado en CONTENT
                filename, title = content_results[adjusted_index]
            else:
                adjusted_index -= len(content_results)
                if adjusted_index < len(important_results):
                    # Es un resultado en Important
                    filename, title = important_results[adjusted_index]
                adjusted_index -= len(important_results)
                if adjusted_index < len(wallabag_results):
                    # Es un resultado en Wallabag
                    filename, title = wallabag_results[adjusted_index]
                else:
                    # Es un resultado en Journals
                    adjusted_index -= len(wallabag_results)
                    filename, title = journal_results[adjusted_index]

        if filename:  # Asegurarse de que se tiene un nombre de archivo válido
            display_file_content(filename, search_entry.get())

def edit_file():
    """Abre el archivo seleccionado con VSCodium."""
    selection = result_list.curselection()
    if selection:
        index = selection[0]
        if index < len(title_results):
            filename = title_results[index][0]
        else:
            adjusted_index = index - len(title_results)
            if adjusted_index < len(content_results):
                filename = content_results[adjusted_index][0]
            else:
                adjusted_index -= len(content_results)
                if adjusted_index < len(important_results):
                    filename = important_results[adjusted_index][0]
                adjusted_index -= len(important_results)
                if adjusted_index < len(wallabag_results):
                    filename = wallabag_results[adjusted_index][0]
                else:
                    adjusted_index -= len(wallabag_results)
                    filename = journal_results[adjusted_index][0]

        if filename and os.path.isfile(filename):
            subprocess.run(["vscodium", filename])  # Abre el archivo con VSCodium

def open_folder():
    """Abre el archivo seleccionado con VSCodium."""
    selection = result_list.curselection()
    if selection:
        index = selection[0]
        if index < len(title_results):
            filename = title_results[index][0]
        else:
            adjusted_index = index - len(title_results)
            if adjusted_index < len(content_results):
                filename = content_results[adjusted_index][0]
            else:
                adjusted_index -= len(content_results)
                if adjusted_index < len(important_results):
                    filename = important_results[adjusted_index][0]
                adjusted_index -= len(important_results)
                if adjusted_index < len(wallabag_results):
                    filename = wallabag_results[adjusted_index][0]
                else:
                    adjusted_index -= len(wallabag_results)
                    filename = journal_results[adjusted_index][0]

        if filename and os.path.isfile(filename):
            subprocess.run(["thunar", filename]) 

def delete_file():
    """Elimina el archivo seleccionado."""
    selection = result_list.curselection()
    if selection:
        index = selection[0]
        if index < len(title_results):
            filename = title_results[index][0]
        else:
            adjusted_index = index - len(title_results)
            if adjusted_index < len(content_results):
                filename = content_results[adjusted_index][0]
            else:
                adjusted_index -= len(content_results)
                if adjusted_index < len(important_results):
                    filename = important_results[adjusted_index][0]
                adjusted_index -= len(important_results)
                if adjusted_index < len(wallabag_results):
                    filename = wallabag_results[adjusted_index][0]
                else:
                    adjusted_index -= len(wallabag_results)
                    filename = journal_results[adjusted_index][0]

        if filename and os.path.isfile(filename):
            # Confirmación antes de eliminar
            confirm = messagebox.askyesno("Confirmar eliminación", f"¿Estás seguro de que deseas eliminar '{os.path.basename(filename)}'?")
            if confirm:
                os.remove(filename)  # Eliminar el archivo
                update_results(None)  # Actualiza la lista de resultados

def focus_search(event=None):
    """Focaliza el campo de búsqueda."""
    search_entry.focus_set()

def ctrl_f(event):
    """Focaliza el campo de búsqueda al pulsar Ctrl+F."""
    if event.state & 0x0004:  # Verifica si Ctrl está presionado
        focus_search()
def select_all(event=None):
    """Selecciona todo el texto en el Text widget."""
    search_entry.tag_add("sel", 1.0, "end")  # Selecciona desde el inicio hasta el final
    return "break"  # Evita el manejo predeterminado del evento



def edit_file_with_shortcut(event=None):
    """Abre el archivo seleccionado con VSCodium al presionar Ctrl+O."""
    edit_file()  # Llama a la función que ya tienes para abrir el archivo

def open_folder_with_shortcut(event=None):
    """Abre el archivo seleccionado con VSCodium al presionar Ctrl+O."""
    open_folder()  # Llama a la función que ya tienes para abrir el archivo

def delete_file_with_shortcut(event=None):
    """Elimina el archivo seleccionado al presionar Suprimir."""
    delete_file()  # Llama a la función que ya tienes para eliminar el archivo

def save_file():
    """Guarda el contenido del archivo editado."""
    selection = result_list.curselection()
    if selection:
        index = selection[0]
        if index < len(title_results):
            filename = title_results[index][0]
        else:
            adjusted_index = index - len(title_results)
            if adjusted_index < len(content_results):
                filename = content_results[adjusted_index][0]
            else:
                adjusted_index -= len(content_results)
                if adjusted_index < len(important_results):
                    filename = important_results[adjusted_index][0]
                adjusted_index -= len(important_results)
                if adjusted_index < len(wallabag_results):
                    filename = wallabag_results[adjusted_index][0]
                else:
                    adjusted_index -= len(wallabag_results)
                    filename = journal_results[adjusted_index][0]

        if filename and os.path.isfile(filename):
            # Guardar el contenido del área de texto en el archivo
            with open(filename, 'w', encoding='utf-8') as file:
                file.write(content_text.get(1.0, tk.END))  # Guarda el contenido
            messagebox.showinfo("Guardar archivo", f"Archivo '{os.path.basename(filename)}' guardado con éxito.")

def create_gui():
    """Crea la interfaz gráfica."""
    global root, search_entry, result_list, content_text, title_results, content_results, important_results, wallabag_results, journal_results
    root = tk.Tk()
    root.title("Buscador de archivos Markdown")
    
    # Cambiar colores y tamaño de la ventana
    root.configure(bg='#14141e')  # Color de fondo oscuro para el menú principal
    root.geometry("1800x800")  # Aumentar tamaño de la ventana

    # Campo de búsqueda
    search_frame = tk.Frame(root, bg='#14141e')  # Color de fondo oscuro para el marco
    search_frame.pack(pady=(10, 10), padx=5)

    # Botones de abrir y borrar
    open_button = tk.Button(search_frame, text="Carpeta", command=edit_file, bg='#f8bd9a')
    open_button.pack(side=tk.LEFT, padx=(0, 15))  # Mover a la izquierda

    edit_button = tk.Button(search_frame, text="Editar", command=open_folder, bg='#1974D2')
    edit_button.pack(side=tk.LEFT, padx=(0, 15))  # Mover a la izquierda

    delete_button = tk.Button(search_frame, text="Eliminar", command=delete_file, bg='#ff8b8b')
    delete_button.pack(side=tk.LEFT, padx=(0, 15))  # Mover a la izquierda

    # Campo de búsqueda
    search_entry = tk.Entry(search_frame, bg='#cba6f7', fg='black', font=('Arial', 12), insertbackground='black', width=50)
    search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
    search_entry.bind("<KeyRelease>", update_results)
    search_entry.bind("<Return>", update_results)  # Actualiza al presionar Enter
    search_entry.bind("<FocusIn>", focus_search)  # Focaliza al hacer clic en el campo

    # Lista de resultados
    result_list = tk.Listbox(root, width=50, height=20, font=('Arial', 12), bg='#14141e', fg='white')
    result_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    result_list.bind("<<ListboxSelect>>", on_select)

    # Área de texto para mostrar el contenido
    content_text = tk.Text(root, width=80, height=20, wrap=tk.WORD, bg='#14141e', fg='white', font=('Arial', 12))
    content_text.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

    # Resaltar el texto buscado
    content_text.tag_configure("highlight", background="#cba6f7", foreground="black")

    # Focalizar el campo de búsqueda al inicio
    focus_search()

    # Atajos de teclado
    root.bind("<Control-f>", ctrl_f)        # Para focalizar búsqueda
    root.bind("<Control-e>", edit_file_with_shortcut)  # Para abrir archivo con Ctrl+E
    root.bind("<Delete>", delete_file_with_shortcut)    # Para eliminar archivo con Suprimir
    root.bind("<Control-o>", open_folder_with_shortcut)  # Para abrir archivo con Ctrl+O
    root.bind("<Control-a>", select_all)
    root.bind("<Control-s>", lambda event: save_file())  # Para guardar archivo con Ctrl+S

    
    # Focalizar el campo de búsqueda al abrir la ventana
    focus_search()

    root.mainloop()

if __name__ == "__main__":
    create_gui()#!/usr/bin/env python
