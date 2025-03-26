#!/usr/bin/env python3
"""
Script Name: crear_tarea_caldav.py
Description: Añadir tarea a calendario Tareas, a todotxt de obsidian y todofi.sh y a taskwarrior
Author: volteret4 (Bash version) / converted to Python
"""

import os
import sys
import subprocess
import json
import datetime
from pathlib import Path
import tempfile
import re
from PyQt6.QtWidgets import (QApplication, QMainWindow, QDialog, QVBoxLayout, QHBoxLayout, 
                           QLabel, QLineEdit, QPushButton, QCalendarWidget, QListWidget,
                           QListWidgetItem, QMessageBox, QFileDialog, QInputDialog,
                           QStyleFactory, QWidget)
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QColor, QPalette, QKeyEvent, QFont

# Configuración - mantiene las mismas rutas y valores que en el script original
HOME = os.environ.get('HOME')
DISCOS = "d1573ec1-e837-6918-1dfe-bc0b6c04681d"  # CHANGE!!!
TAREAS = "7c44de6e-69ac-8496-f46d-d6753c9eab1f"  # CHANGE!!!
MUSICA = "e2e4e951-3599-8f21-de6c-105ec980b1ec"  # CHANGE!!!

TODO_DIR = Path("/mnt/windows/FTP/Wiki/Obsidian/Important/todotxt/todo")  # CHANGE!!!
TODO_DIR_ROOT = Path("/mnt/windows/FTP/Wiki/Obsidian/Important/todotxt/")
TASKS_FILE = Path("/mnt/windows/FTP/wiki/Obsidian/Important/Tareas.md")  # NUEVA RUTA PARA TAREAS

# Lista de archivos markdown con títulos
MARKDOWN_FILES = [
    {
        "path": "/mnt/windows/FTP/wiki/Obsidian/Spaces/Proyectos Interesantes/Indice Proyectos.md",
        "title": "indice"
    },
    {
        "path": "/mnt/windows/FTP/wiki/Obsidian/Spaces/Blogs/snipets y scripts/music-fuzzy/Aplicación música pollo.md",
        "title": "m_fuzzy"
    },
    {
        "path": "/mnt/windows/FTP/wiki/Obsidian/Spaces/Blogs/snipets y scripts/music-fuzzy/creacion base de datos/Creación de la base de datos.md",
        "title": "create_db"
    },
    {
        "path": "/mnt/windows/FTP/wiki/Obsidian/Spaces/Blogs/Tumtumpa/Blog Tumtumpá.md",
        "title": "tumtumpa"
    }
]

# Definición de colores del tema Catppuccin Mocha
class CatppuccinMocha:
    # Colores base
    BASE = QColor(30, 30, 46)       # #1e1e2e
    MANTLE = QColor(24, 24, 37)     # #181825
    CRUST = QColor(17, 17, 27)      # #11111b
    
    # Textos
    TEXT = QColor(205, 214, 244)    # #cdd6f4
    SUBTEXT1 = QColor(186, 194, 222) # #bac2de
    SUBTEXT0 = QColor(166, 173, 200) # #a6adc8
    
    # Superficies
    SURFACE0 = QColor(49, 50, 68)   # #313244
    SURFACE1 = QColor(69, 71, 90)   # #45475a
    SURFACE2 = QColor(88, 91, 112)  # #585b70
    
    # Colores brillantes
    BLUE = QColor(137, 180, 250)    # #89b4fa
    LAVENDER = QColor(180, 190, 254) # #b4befe
    SAPPHIRE = QColor(116, 199, 236) # #74c7ec
    MAUVE = QColor(203, 166, 247)   # #cba6f7
    PINK = QColor(245, 194, 231)    # #f5c2e7
    RED = QColor(243, 139, 168)     # #f38ba8
    MAROON = QColor(235, 160, 172)  # #eba0ac
    PEACH = QColor(250, 179, 135)   # #fab387
    YELLOW = QColor(249, 226, 175)  # #f9e2af
    GREEN = QColor(166, 227, 161)   # #a6e3a1
    TEAL = QColor(148, 226, 213)    # #94e2d5
    SKY = QColor(137, 220, 235)     # #89dceb

def apply_catppuccin_mocha_theme(app):
    """Aplica el tema Catppuccin Mocha a la aplicación"""
    app.setStyle(QStyleFactory.create("Fusion"))
    
    palette = QPalette()
    # General
    palette.setColor(QPalette.ColorRole.Window, CatppuccinMocha.BASE)
    palette.setColor(QPalette.ColorRole.WindowText, CatppuccinMocha.TEXT)
    palette.setColor(QPalette.ColorRole.Base, CatppuccinMocha.MANTLE)
    palette.setColor(QPalette.ColorRole.AlternateBase, CatppuccinMocha.CRUST)
    palette.setColor(QPalette.ColorRole.ToolTipBase, CatppuccinMocha.MANTLE)
    palette.setColor(QPalette.ColorRole.ToolTipText, CatppuccinMocha.TEXT)
    palette.setColor(QPalette.ColorRole.Text, CatppuccinMocha.TEXT)
    palette.setColor(QPalette.ColorRole.Button, CatppuccinMocha.SURFACE0)
    palette.setColor(QPalette.ColorRole.ButtonText, CatppuccinMocha.TEXT)
    palette.setColor(QPalette.ColorRole.BrightText, CatppuccinMocha.RED)
    
    # Disabled
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, CatppuccinMocha.SUBTEXT0)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, CatppuccinMocha.SUBTEXT0)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, CatppuccinMocha.SUBTEXT0)
    
    # Highlight
    palette.setColor(QPalette.ColorRole.Highlight, CatppuccinMocha.MAUVE)
    palette.setColor(QPalette.ColorRole.HighlightedText, CatppuccinMocha.CRUST)
    
    # Links
    palette.setColor(QPalette.ColorRole.Link, CatppuccinMocha.BLUE)
    palette.setColor(QPalette.ColorRole.LinkVisited, CatppuccinMocha.LAVENDER)
    
    app.setPalette(palette)
    
    # Establecer fuente global
    font = QFont("JetBrains Mono", 10)
    app.setFont(font)

def run_command(cmd, shell=False):
    """Ejecuta un comando y devuelve su salida."""
    if shell:
        result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    else:
        result = subprocess.run(cmd, text=True, capture_output=True)
    
    return result.stdout.strip(), result.returncode

def get_clipboard_content():
    """Recupera el contenido del portapapeles usando copyq."""
    content, _ = run_command("copyq clipboard", shell=True)
    return content

def extract_categories(text):
    """Extrae categorías (@palabras) del texto."""
    pattern = r'@(\w+)'
    matches = re.findall(pattern, text)
    return set(matches)

def check_task_query_exists(file_path, project_name):
    """Verifica si la consulta de tareas ya existe en el archivo."""
    try:
        with open(file_path, "r", encoding='utf-8') as f:
            content = f.read()
            query_pattern = r'```tasks\s+not done\s+tags include #' + re.escape(project_name)
            return bool(re.search(query_pattern, content))
    except FileNotFoundError:
        return False

def add_task_query(file_path, project_name):
    """Añade un bloque de consulta de tareas al archivo si no existe."""
    if not check_task_query_exists(file_path, project_name):
        with open(file_path, "a", encoding='utf-8') as f:
            f.write("\n\n")
            f.write(f"```tasks\nnot done\ntags include #{project_name}\nhide tags\nshort mode\nsort by due\nsort by priority\nsort by scheduled\n```\n")

class ThemedDialog(QDialog):
    """Clase base para diálogos con el tema Catppuccin aplicado"""
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setup_style()
        
    def setup_style(self):
        """Aplica estilos específicos al diálogo"""
        self.setStyleSheet(f"""
            QDialog {{ 
                background-color: {CatppuccinMocha.BASE.name()}; 
                color: {CatppuccinMocha.TEXT.name()};
                border-radius: 8px;
            }}
            QLabel {{ 
                color: {CatppuccinMocha.TEXT.name()}; 
                font-size: 11pt; 
            }}
            QLineEdit {{ 
                background-color: {CatppuccinMocha.SURFACE0.name()}; 
                color: {CatppuccinMocha.TEXT.name()}; 
                border: 1px solid {CatppuccinMocha.SURFACE2.name()};
                border-radius: 4px;
                padding: 5px;
            }}
            QPushButton {{ 
                background-color: {CatppuccinMocha.SURFACE1.name()}; 
                color: {CatppuccinMocha.TEXT.name()}; 
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{ 
                background-color: {CatppuccinMocha.MAUVE.name()}; 
                color: {CatppuccinMocha.CRUST.name()}; 
            }}
            QPushButton:pressed {{ 
                background-color: {CatppuccinMocha.PINK.name()}; 
            }}
            QCalendarWidget {{ 
                background-color: {CatppuccinMocha.MANTLE.name()}; 
                color: {CatppuccinMocha.TEXT.name()}; 
            }}
            QListWidget {{ 
                background-color: {CatppuccinMocha.MANTLE.name()}; 
                color: {CatppuccinMocha.TEXT.name()}; 
                border: 1px solid {CatppuccinMocha.SURFACE2.name()};
                border-radius: 4px;
                padding: 5px;
            }}
            QListWidget::item {{ 
                padding: 5px; 
                border-radius: 2px;
            }}
            QListWidget::item:selected {{ 
                background-color: {CatppuccinMocha.MAUVE.name()}; 
                color: {CatppuccinMocha.CRUST.name()}; 
            }}
        """)

class CalendarDialog(ThemedDialog):
    def __init__(self, title, default_date=None, parent=None):
        super().__init__(title, parent)
        self.resize(300, 300)
        
        layout = QVBoxLayout()
        
        if default_date is None:
            default_date = datetime.date.today()
            
        self.calendar = QCalendarWidget()
        self.calendar.setSelectedDate(QDate(default_date.year, default_date.month, default_date.day))
        self.calendar.setStyleSheet(f"""
            QCalendarWidget QWidget {{
                alternate-background-color: {CatppuccinMocha.SURFACE0.name()};
            }}
            QCalendarWidget QAbstractItemView:enabled {{
                color: {CatppuccinMocha.TEXT.name()};
                selection-background-color: {CatppuccinMocha.MAUVE.name()};
                selection-color: {CatppuccinMocha.CRUST.name()};
            }}
            QCalendarWidget QWidget#qt_calendar_navigationbar {{
                background-color: {CatppuccinMocha.SURFACE1.name()};
            }}
            QCalendarWidget QToolButton {{
                color: {CatppuccinMocha.TEXT.name()};
                background-color: {CatppuccinMocha.SURFACE1.name()};
                border: none;
                border-radius: 4px;
                padding: 6px;
            }}
            QCalendarWidget QToolButton:hover {{
                background-color: {CatppuccinMocha.MAUVE.name()};
                color: {CatppuccinMocha.CRUST.name()};
            }}
            QCalendarWidget QMenu {{
                background-color: {CatppuccinMocha.MANTLE.name()};
                color: {CatppuccinMocha.TEXT.name()};
            }}
            QCalendarWidget QSpinBox {{
                background-color: {CatppuccinMocha.SURFACE0.name()};
                color: {CatppuccinMocha.TEXT.name()};
                border: 1px solid {CatppuccinMocha.SURFACE2.name()};
                border-radius: 4px;
            }}
        """)
        
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("Aceptar")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addWidget(self.calendar)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
    def get_selected_date(self):
        date = self.calendar.selectedDate()
        return f"{date.year()}-{date.month():02d}-{date.day():02d}"

class EntryDialog(ThemedDialog):
    def __init__(self, default_text, prompt, parent=None):
        super().__init__("Entrada", parent)
        self.resize(400, 100)
        
        layout = QVBoxLayout()
        
        self.label = QLabel(prompt)
        self.entry = QLineEdit(default_text)
        
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("Aceptar")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addWidget(self.label)
        layout.addWidget(self.entry)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
    def get_text(self):
        return self.entry.text()

class FileListDialog(ThemedDialog):
    def __init__(self, parent=None):
        super().__init__("Selecciona un archivo de Obsidian", parent)
        self.resize(600, 400)
        
        self.selected_path = None
        self.selected_title = None
        
        layout = QVBoxLayout()
        
        self.label = QLabel("Elige dónde añadir la tarea:")
        self.file_list = QListWidget()
        self.file_list.installEventFilter(self)
        
        # Agregar archivos a la lista
        for file in MARKDOWN_FILES:
            item = QListWidgetItem(file['title'])
            # Destacar la primera letra para la selección rápida
            item.setData(Qt.ItemDataRole.UserRole, file['title'][0].lower())
            self.file_list.addItem(item)
            
        # Agregar opción para seleccionar un archivo nuevo
        item = QListWidgetItem("+ Añadir nuevo archivo")
        item.setData(Qt.ItemDataRole.UserRole, "+")
        self.file_list.addItem(item)
        
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("Seleccionar")
        self.ok_button.clicked.connect(self.select_file)
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addWidget(self.label)
        layout.addWidget(self.file_list)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
    def eventFilter(self, obj, event):
        """Filtra eventos para detectar pulsaciones de teclas y seleccionar por inicial"""
        if obj == self.file_list and event.type() == QKeyEvent.Type.KeyPress:
            key = event.text().lower()
            if key and key.isalpha():
                # Buscar el primer elemento que comience con esa letra
                for i in range(self.file_list.count()):
                    item = self.file_list.item(i)
                    first_letter = item.data(Qt.ItemDataRole.UserRole)
                    if first_letter == key:
                        self.file_list.setCurrentItem(item)
                        return True
        return super().eventFilter(obj, event)
    
    def select_file(self):
        selected_row = self.file_list.currentRow()
        
        # Si seleccionó "Añadir nuevo archivo"
        if selected_row == len(MARKDOWN_FILES):
            file_dialog = QFileDialog()
            file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
            file_dialog.setNameFilter("Markdown (*.md)")
            file_dialog.setDirectory("/mnt/windows/FTP/Wiki/Obsidian/")
            
            # Aplicar estilo al diálogo de archivos
            file_dialog.setStyleSheet(f"""
                QFileDialog {{
                    background-color: {CatppuccinMocha.BASE.name()};
                    color: {CatppuccinMocha.TEXT.name()};
                }}
                QFileDialog QListView, QFileDialog QTreeView {{
                    background-color: {CatppuccinMocha.MANTLE.name()};
                    color: {CatppuccinMocha.TEXT.name()};
                }}
                QFileDialog QComboBox, QFileDialog QLineEdit {{
                    background-color: {CatppuccinMocha.SURFACE0.name()};
                    color: {CatppuccinMocha.TEXT.name()};
                    border: 1px solid {CatppuccinMocha.SURFACE2.name()};
                    border-radius: 4px;
                    padding: 5px;
                }}
            """)
            
            if file_dialog.exec():
                file_paths = file_dialog.selectedFiles()
                if file_paths:
                    new_file = file_paths[0]
                    title_dialog = QInputDialog()
                    title_dialog.setStyleSheet(f"""
                        QInputDialog {{
                            background-color: {CatppuccinMocha.BASE.name()};
                            color: {CatppuccinMocha.TEXT.name()};
                        }}
                        QInputDialog QLineEdit {{
                            background-color: {CatppuccinMocha.SURFACE0.name()};
                            color: {CatppuccinMocha.TEXT.name()};
                            border: 1px solid {CatppuccinMocha.SURFACE2.name()};
                            border-radius: 4px;
                            padding: 5px;
                        }}
                    """)
                    title, ok = title_dialog.getText(self, "Título para el archivo", 
                                                    "Introduce un título para este archivo:", 
                                                    QLineEdit.EchoMode.Normal, 
                                                    Path(new_file).stem)
                    
                    if ok and title:
                        # Agregar el nuevo archivo a la lista global
                        new_file_data = {"path": new_file, "title": title}
                        MARKDOWN_FILES.append(new_file_data)
                        self.selected_path = new_file
                        self.selected_title = title
                        self.accept()
        else:
            self.selected_path = MARKDOWN_FILES[selected_row]["path"]
            self.selected_title = MARKDOWN_FILES[selected_row]["title"]
            self.accept()

def show_message(title, message):
    """Muestra un mensaje en una ventana de diálogo."""
    msg_box = QMessageBox()
    msg_box.setWindowTitle(title)
    msg_box.setText(message)
    
    # Aplicar estilo al mensaje
    msg_box.setStyleSheet(f"""
        QMessageBox {{
            background-color: {CatppuccinMocha.BASE.name()};
            color: {CatppuccinMocha.TEXT.name()};
        }}
        QMessageBox QPushButton {{
            background-color: {CatppuccinMocha.SURFACE1.name()};
            color: {CatppuccinMocha.TEXT.name()};
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
        }}
        QMessageBox QPushButton:hover {{
            background-color: {CatppuccinMocha.MAUVE.name()};
            color: {CatppuccinMocha.CRUST.name()};
        }}
    """)
    
    msg_box.exec()

def main():
    app = QApplication(sys.argv)
    apply_catppuccin_mocha_theme(app)
    
    # Obtener argumentos de la línea de comandos
    args = " ".join(sys.argv[1:])
    
    # Seleccionar archivo de Obsidian
    file_dialog = FileListDialog()
    if file_dialog.exec():
        file_path = file_dialog.selected_path
        project_name = file_dialog.selected_title
    else:
        show_message("Operación cancelada", "No se seleccionó un archivo.")
        return 1
    
    if file_path is None:
        show_message("Operación cancelada", "No se seleccionó un archivo.")
        return 1
    
    # Obtener contenido del portapapeles
    contenido = get_clipboard_content()
    
    # Establecer fechas predeterminadas
    fecha_hoy = datetime.date.today().strftime("%Y-%m-%d")
    fecha_inicio = fecha_hoy
    fecha_fin = (datetime.date.today() + datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    
    # Solicitar título y etiquetas - CAMBIADO: + por #
    default_text = f"#{project_name} fecha_estandar "
    entry_dialog = EntryDialog(default_text, "Tags @ | Categorias #")
    if entry_dialog.exec():
        titulo = entry_dialog.get_text()
    else:
        show_message("Operación cancelada", "No se introdujo título.")
        return 1
    
    # Mostrar diálogo para elegir la fecha de inicio
    if "fecha_estandar" not in titulo:
        cal_dialog_inicio = CalendarDialog("Seleccione fecha de inicio (schedule)")
        if cal_dialog_inicio.exec():
            fecha_inicio = cal_dialog_inicio.get_selected_date()
    
        # Mostrar diálogo para elegir la fecha de fin
        cal_dialog_fin = CalendarDialog(
            "Seleccione fecha de fin (due)", 
            default_date=datetime.date.today() + datetime.timedelta(days=365)
        )
        if cal_dialog_fin.exec():
            fecha_fin = cal_dialog_fin.get_selected_date()
    
    # Si se ha borrado el placeholder fecha_estandar, mostrar diálogos para elegir fechas
    if "fecha_estandar" in titulo:
        titulo = titulo.replace("fecha_estandar", "")
    
    # Determinar el calendario y todofile basado en el contenido
    calendario = "tareas"  # Valor predeterminado
    todofile = TODO_DIR_ROOT / "todo" / "t_todo.todotxt"
    album = ""
    
    # Comprobar si el contenido es un enlace a un sitio de música
    music_sites = ["youtu.be", "youtube.com", "bandcamp.com", "soundcloud.com"]
    if any(site in titulo for site in music_sites):
        calendario = "discos"
        todofile = TODO_DIR_ROOT / "albums" / "a_todo.txt"
        # Obtener título del álbum usando yt-dlp
        album, _ = run_command(f'yt-dlp --get-title "{contenido}"', shell=True)
    elif args:
        calendario = "tareas"
        todofile = TODO_DIR_ROOT / "todo" / "t_todo.todotxt"
        titulo = args
    
    # Extraer categorías del título
    categorias = extract_categories(titulo)

    # Extraer categorias del titulo par el json
    pattern = r'@(' + '|'.join(re.escape(cat) for cat in categorias) + r')'
    
    # Reemplazar las categorías en el título por una cadena vacía
    titulo_todo = re.sub(pattern, "", titulo)

    # Reemplazar "@" por "#" en las categorías dentro del título
    pattern = r'@(\w+)'
    titulo_obsidian = re.sub(pattern, lambda m: '#' + m.group(1), titulo)

    # NUEVO: Añadir bloque de consulta de tareas al archivo seleccionado si no existe
    add_task_query(file_path, project_name)
    
    # MODIFICADO: Añadir la tarea al archivo Tareas en lugar de al archivo seleccionado
    with open(TASKS_FILE, "a", encoding='utf-8') as f:
        f.write("\n\n")
        f.write(f"- [ ] TODO {titulo_obsidian} 📅 {fecha_fin} ⏳ {fecha_inicio}")
    
    # Sincronizar con vdirsyncer
    _, sync_result = run_command("vdirsyncer sync", shell=True)
    
    if sync_result == 0:
        if calendario == "tareas":
            # Preparar comando para todotxt
            txt_cmd = f"{fecha_hoy} {titulo_todo}"
            
            # Añadir categorías
            for categoria in categorias:
                txt_cmd += f' "@{categoria}"'
            
            # Añadir fechas
            txt_cmd += f" due:{fecha_fin}"
            if fecha_inicio != fecha_hoy:
                txt_cmd += f" t:{fecha_inicio}"
            
            # Añadir al archivo todo.txt
            with open(todofile, "a", encoding='utf-8') as f:
                f.write(txt_cmd + "\n")
            
            # Exportar a json para taskwarrior
            export_cmd = f'python "{HOME}/Scripts/tareas/json_todotxt.pl" "{TODO_DIR}/t_todo.todotxt" > "{TODO_DIR_ROOT}/tw_from_t_todo.json"'
            run_command(export_cmd, shell=True)
            
            # Importar a taskwarrior
            import_cmd = f'cat "{TODO_DIR}/tw_from_t_todo.json" | task import'
            run_command(import_cmd, shell=True)
            
            # Crear comando para todo
            todo_cmd = f'todo --config "{HOME}/.config/todoman/config_tareas.py" new -l "{TAREAS}" -s "{fecha_inicio}" -d "{fecha_fin}" -r "{titulo_todo}"'
            
            # Añadir categorías
            for categoria in categorias:
                todo_cmd += f' -c "{categoria}"'
            
            # Ejecutar comando
            subprocess.Popen(todo_cmd, shell=True)
            run_command(f'notify-send "enviada tarea: {titulo_todo} ({fecha_inicio} → {fecha_fin})"', shell=True)
            
        elif calendario == "discos":
            todo_cmd = f'todo new -l "discos" -s "{fecha_inicio}" -d "{fecha_fin}" -r "{titulo_todo}"'
            subprocess.Popen(todo_cmd, shell=True)
            
            with open(todofile, "a", encoding='utf-8') as f:
                f.write(f"{fecha_hoy} {album} {contenido} {titulo_todo}\n")
        else:
            show_message("Error", "Error al añadir tarea a radicale")
            run_command('notify-send -u critical "Error en la operación"', shell=True)
    
    # Mostrar barra de progreso (podríamos implementar esto con QProgressDialog pero
    # mantengamos el script bash por ahora para mantener la compatibilidad)
    run_command(f'bash "{HOME}/Scripts/utilities/aliases/barra_progreso.sh" 10', shell=True)
    
    # Sincronizar con vdirsyncer de nuevo
    run_command("vdirsyncer sync", shell=True)
    
    # Mostrar mensaje de éxito con tema aplicado
    success_msg = f"Tarea añadida correctamente a:\n- Tareas: {TASKS_FILE}\n- Consulta añadida a: {project_name}\n- Calendario: {calendario}\n- Todo.txt\n- Taskwarrior"
    print(f"Tarea creada {success_msg}")
    run_command(f'notify-send "enviado disco: {album} {contenido} {titulo_todo}"', shell=True)

    return 0

if __name__ == "__main__":
    sys.exit(main())