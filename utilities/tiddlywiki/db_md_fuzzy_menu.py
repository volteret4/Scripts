import sys
import sqlite3
import re
import subprocess
import platform
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLineEdit, QListWidget, QTextEdit, QPushButton, QLabel, QListWidgetItem,
                             QDialog, QCheckBox, QScrollArea, QSplitter, QFrame, QMessageBox,  QDialogButtonBox)
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QColor, QPalette, QFont, QIcon, QShortcut, QKeySequence
import markdown
from markdown.extensions import codehilite, fenced_code
import os
from functools import partial
from db_md_async_search import SearchWorker
import json


class CatppuccinDarkTheme:
    # Colores del tema Catppuccin Mocha (variante oscura)
    base = "#1e1e2e"
    mantle = "#181825"
    crust = "#11111b"
    text = "#cdd6f4"
    subtext0 = "#a6adc8"
    subtext1 = "#bac2de"
    surface0 = "#313244"
    surface1 = "#45475a"
    surface2 = "#585b70"
    overlay0 = "#6c7086"
    blue = "#89b4fa"
    lavender = "#b4befe"
    sapphire = "#74c7ec"
    sky = "#89dceb"
    teal = "#94e2d5"
    green = "#a6e3a1"
    yellow = "#f9e2af"
    peach = "#fab387"
    maroon = "#eba0ac"
    red = "#f38ba8"
    mauve = "#cba6f7"
    pink = "#f5c2e7"
    flamingo = "#f2cdcd"
    rosewater = "#f5e0dc"

    @classmethod
    def apply_to_app(cls, app):
        # Aplicar el tema Catppuccin a toda la aplicación
        palette = QPalette()
        
        # Colores generales
        palette.setColor(QPalette.ColorRole.Window, QColor(cls.base))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(cls.text))
        palette.setColor(QPalette.ColorRole.Base, QColor(cls.mantle))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(cls.crust))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(cls.mantle))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(cls.text))
        palette.setColor(QPalette.ColorRole.Text, QColor(cls.text))
        palette.setColor(QPalette.ColorRole.Button, QColor(cls.surface0))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(cls.text))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(cls.rosewater))
        
        # Colores para elementos deshabilitados - corregido para PyQt6
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(cls.overlay0))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(cls.overlay0))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(cls.overlay0))
        
        # Colores para selección
        palette.setColor(QPalette.ColorRole.Highlight, QColor(cls.mauve))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(cls.crust))
        
        # Aplica la paleta a la aplicación
        app.setPalette(palette)
        
        # Estilo adicional para widgets específicos
        app.setStyleSheet(f"""
            QLineEdit {{
                background-color: {cls.surface0};
                color: {cls.text};
                border: 1px solid {cls.surface2};
                border-radius: 4px;
                padding: 4px;
            }}

            QTextEdit, QListWidget {{
                background-color: {cls.base};
                color: {cls.text};
                border: 1px solid {cls.surface2};
                border-radius: 4px;
                padding: 4px;
            }}
            
            QPushButton {{
                background-color: {cls.surface1};
                color: {cls.text};
                border: 1px solid {cls.surface2};
                border-radius: 4px;
                padding: 6px 12px;
            }}
            
            QPushButton:hover {{
                background-color: {cls.surface2};
            }}
            
            QPushButton:pressed {{
                background-color: {cls.blue};
                color: {cls.crust};
            }}
            
            QSplitter::handle {{
                background-color: {cls.surface1};
            }}


            QScrollBar:horizontal {{
                background-color: {cls.surface0};
                width: 10px;
                margin: 0px;
            }}
            
            QScrollBar::handle:horizontal {{
                background-color: {cls.surface2};
                min-height: 20px;
                border-radius: 4px;
            }}
            
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                height: 0px;
            }}


            QScrollBar:vertical {{
                background-color: {cls.surface0};
                width: 10px;
                margin: 0px;
            }}
            
            QScrollBar::handle:vertical {{
                background-color: {cls.surface2};
                min-height: 20px;
                border-radius: 4px;
            }}
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            
            QCheckBox {{
                color: {cls.text};
            }}
            
            QCheckBox::indicator:checked {{
                background-color: {cls.blue};
            }}
            
            QLabel {{
                color: {cls.text};
            }}
        """)

class PathFilterDialog(QDialog):
    def __init__(self, parent, db_path, root_folders):
        super().__init__(parent)
        self.db_path = db_path
        self.root_folders = root_folders
        self.selected_folders = []
        
        # Cargar filtros guardados previamente
        self.load_saved_filters()
        
        self.setup_ui()
    
    def load_saved_filters(self):
        try:
            if os.path.exists('filter_settings.json'):
                with open('filter_settings.json', 'r') as f:
                    data = json.load(f)
                    if 'selected_folders' in data and isinstance(data['selected_folders'], list):
                        self.selected_folders = data['selected_folders']
                        print(f"Dialog: Filtros cargados: {self.selected_folders}")
        except Exception as e:
            print(f"Dialog: Error cargando filtros: {e}")
    
    def setup_ui(self):
        self.setWindowTitle("Filtrar por carpetas")
        layout = QVBoxLayout(self)
        
        # Lista de carpetas con checkboxes
        self.folder_list = QListWidget()
        
        # Añadir las carpetas a la lista
        for folder in self.root_folders:
            item = QListWidgetItem(folder)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            
            # Marcar las carpetas que estaban seleccionadas previamente
            if folder in self.selected_folders:
                item.setCheckState(Qt.CheckState.Checked)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)
            
            self.folder_list.addItem(item)
        
        layout.addWidget(self.folder_list)
        
        # Botones
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | 
                                      QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.resize(400, 300)
    
    def get_selected_folders(self):
        selected = []
        for i in range(self.folder_list.count()):
            item = self.folder_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item.text())
        return selected

class MarkdownRenderer:
    @staticmethod
    def render_markdown(text):
        # Configurar extensiones de markdown para resaltado de sintaxis
        md = markdown.Markdown(extensions=[
            'fenced_code',
            'codehilite',
            'tables',
            'nl2br'
        ])
        
        # Convertir markdown a HTML
        html = md.convert(text)
        
        # Añadir estilos CSS personalizados para el tema Catppuccin
        styled_html = f"""
        <style>
            body {{
                background-color: #1e1e2e;
                color: #cdd6f4;
                font-family: 'Roboto', 'Segoe UI', 'Arial', sans-serif;
                line-height: 1.6;
                padding: 10px;
            }}
            h1, h2, h3, h4, h5, h6 {{
                color: #f5c2e7;
                margin-top: 20px;
                margin-bottom: 10px;
            }}
            a {{
                color: #89b4fa;
                text-decoration: none;
            }}
            a:hover {{
                text-decoration: underline;
            }}
            code {{
                font-family: 'Fira Code', 'Consolas', monospace;
                background-color: #313244;
                color: #a6e3a1;
                padding: 2px 4px;
                border-radius: 3px;
            }}
            pre {{
                background-color: #313244;
                padding: 10px;
                border-radius: 5px;
                overflow-x: auto;
            }}
            pre code {{
                background-color: transparent;
                padding: 0;
            }}
            blockquote {{
                border-left: 4px solid #74c7ec;
                margin-left: 0;
                padding-left: 10px;
                color: #a6adc8;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
                margin: 15px 0;
            }}
            th, td {{
                border: 1px solid #585b70;
                padding: 8px;
                text-align: left;
            }}
            th {{
                background-color: #45475a;
            }}
            img {{
                max-width: 100%;
                height: auto;
            }}
            ul, ol {{
                padding-left: 20px;
            }}
            hr {{
                border: none;
                border-top: 1px solid #45475a;
                margin: 20px 0;
            }}
            /* Colores de resaltado de código para Catppuccin */
            .codehilite .hll {{ background-color: #45475a }}
            .codehilite .c {{ color: #6c7086 }} /* Comentario */
            .codehilite .k {{ color: #cba6f7 }} /* Keyword */
            .codehilite .n {{ color: #cdd6f4 }} /* Name */
            .codehilite .o {{ color: #89dceb }} /* Operator */
            .codehilite .p {{ color: #cdd6f4 }} /* Punctuation */
            .codehilite .cm {{ color: #6c7086 }} /* Comment.Multiline */
            .codehilite .cp {{ color: #6c7086 }} /* Comment.Preproc */
            .codehilite .c1 {{ color: #6c7086 }} /* Comment.Single */
            .codehilite .cs {{ color: #6c7086 }} /* Comment.Special */
            .codehilite .kc {{ color: #cba6f7 }} /* Keyword.Constant */
            .codehilite .kd {{ color: #cba6f7 }} /* Keyword.Declaration */
            .codehilite .kn {{ color: #cba6f7 }} /* Keyword.Namespace */
            .codehilite .kp {{ color: #cba6f7 }} /* Keyword.Pseudo */
            .codehilite .kr {{ color: #cba6f7 }} /* Keyword.Reserved */
            .codehilite .kt {{ color: #cba6f7 }} /* Keyword.Type */
            .codehilite .m {{ color: #fab387 }} /* Literal.Number */
            .codehilite .s {{ color: #a6e3a1 }} /* Literal.String */
            .codehilite .na {{ color: #f5c2e7 }} /* Name.Attribute */
            .codehilite .nb {{ color: #89b4fa }} /* Name.Builtin */
            .codehilite .nc {{ color: #f9e2af }} /* Name.Class */
            .codehilite .no {{ color: #f38ba8 }} /* Name.Constant */
            .codehilite .nd {{ color: #f9e2af }} /* Name.Decorator */
            .codehilite .ni {{ color: #cdd6f4 }} /* Name.Entity */
            .codehilite .ne {{ color: #f38ba8 }} /* Name.Exception */
            .codehilite .nf {{ color: #89b4fa }} /* Name.Function */
            .codehilite .nl {{ color: #cdd6f4 }} /* Name.Label */
            .codehilite .nn {{ color: #f9e2af }} /* Name.Namespace */
            .codehilite .nt {{ color: #f38ba8 }} /* Name.Tag */
            .codehilite .nv {{ color: #cdd6f4 }} /* Name.Variable */
            .codehilite .ow {{ color: #89dceb }} /* Operator.Word */
            .codehilite .mb {{ color: #fab387 }} /* Literal.Number.Bin */
            .codehilite .mf {{ color: #fab387 }} /* Literal.Number.Float */
            .codehilite .mh {{ color: #fab387 }} /* Literal.Number.Hex */
            .codehilite .mi {{ color: #fab387 }} /* Literal.Number.Integer */
            .codehilite .mo {{ color: #fab387 }} /* Literal.Number.Oct */
            .codehilite .sb {{ color: #a6e3a1 }} /* Literal.String.Backtick */
            .codehilite .sc {{ color: #a6e3a1 }} /* Literal.String.Char */
            .codehilite .sd {{ color: #a6e3a1 }} /* Literal.String.Doc */
            .codehilite .s2 {{ color: #a6e3a1 }} /* Literal.String.Double */
            .codehilite .se {{ color: #fab387 }} /* Literal.String.Escape */
            .codehilite .sh {{ color: #a6e3a1 }} /* Literal.String.Heredoc */
            .codehilite .si {{ color: #fab387 }} /* Literal.String.Interpol */
            .codehilite .sx {{ color: #a6e3a1 }} /* Literal.String.Other */
            .codehilite .sr {{ color: #a6e3a1 }} /* Literal.String.Regex */
            .codehilite .s1 {{ color: #a6e3a1 }} /* Literal.String.Single */
            .codehilite .ss {{ color: #a6e3a1 }} /* Literal.String.Symbol */
        </style>
        {html}
        """
        
        return styled_html

class MarkdownSearchViewer(QMainWindow):
    def __init__(self, db_path, root_folders=None,*args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self.root_folders = root_folders or [
            "/mnt/windows/FTP/wiki/Obsidian/Spaces/Wiki",
            "/mnt/windows/FTP/wiki/Obsidian/Spaces/Blogs",
            "/mnt/windows/FTP/wiki/Obsidian/Spaces/Proyectos Interesantes",
            "/mnt/windows/FTP/wiki/Obsidian/Spaces/Scripts",
            "/mnt/windows/FTP/wiki/Obsidian/Recortes"
        ]
        self.selected_folders = []
        # Primero cargar las carpetas seleccionadas antes de iniciar búsquedas
        self.load_selected_folders()
        
        # Añadir variable para controlar el thread de búsqueda
        self.search_thread = None
        
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("Buscador de Snippets Markdown")
        self.setMinimumSize(900, 600)
        
        # Widget principal
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout principal
        main_layout = QVBoxLayout(central_widget)
        
        # Barra de búsqueda y botón de filtro
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar en título, contenido o tags...")
        self.search_timer = None
        self.search_input.textChanged.connect(self.delayed_search)
        self.search_input.textChanged.connect(self.search_snippets)
        
        self.filter_btn = QPushButton("Filtrar por Carpetas")
        self.filter_btn.clicked.connect(self.open_folder_filter)
        
        search_layout.addWidget(self.search_input, 5)
        search_layout.addWidget(self.filter_btn, 1)
        
        main_layout.addLayout(search_layout)
        
        # Splitter vertical para dividir la pantalla entre paneles y status
        main_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Panel superior: contiene el splitter horizontal con los dos paneles
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        
        # Splitter horizontal para los paneles de listado y contenido
        horizontal_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.horizontal_splitter = horizontal_splitter

        # Panel izquierdo: Lista de resultados con scroll fijo
        results_container = QWidget()
        results_layout = QVBoxLayout(results_container)
        results_layout.setContentsMargins(0, 0, 0, 0)
        
        self.results_list = QListWidget()
        self.results_list.currentItemChanged.connect(self.show_snippet)
        # Configurar scroll vertical fijo y estilos
        self.results_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.results_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.results_list.setStyleSheet("""
            QListWidget::item { 
                padding-top: 8px; 
                padding-bottom: 8px;
                border-bottom: 1px solid #45475a;
            }
            QListWidget::item:selected {
                background-color: #cba6f7;
                color: #11111b;
            }
            QListWidget::item:hover {
                background-color: #585b70;
            }
        """)
        
        results_layout.addWidget(self.results_list)

        # Panel derecho: Visualizador de markdown
        self.markdown_view = QTextEdit()
        self.markdown_view.setReadOnly(True)
        
        # Añade ambos widgets al splitter horizontal
        horizontal_splitter.addWidget(results_container)
        horizontal_splitter.addWidget(self.markdown_view)
        
        # Configurar tamaños iniciales para el splitter horizontal (50% cada uno)
        horizontal_splitter.setSizes([int(self.width() * 0.5), int(self.width() * 0.5)])
        
        top_layout.addWidget(horizontal_splitter)
        main_splitter.addWidget(top_widget)
        
        # Panel inferior: Etiqueta de estado
        status_widget = QWidget()
        status_layout = QVBoxLayout(status_widget)
        status_layout.setContentsMargins(0, 0, 0, 0)
        
        self.status_label = QLabel("Resultados: 0")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(f"""
            background-color: {CatppuccinDarkTheme.surface0};
            padding: 8px;
            border-radius: 4px;
            font-weight: bold;
        """)
        status_widget.setFixedHeight(0)
        status_layout.addWidget(self.status_label)
        main_splitter.addWidget(status_widget)
        
        # Configurar tamaños del splitter vertical (90% contenido, 10% status)
        main_splitter.setSizes([int(self.height() * 1), int(self.height() * 0)])
        
        main_layout.addWidget(main_splitter)
        
        # Cargar todos los snippets al inicio
        self.search_snippets()
        
        # Configurar atajos de teclado
        self.setup_shortcuts()
    
    def setup_shortcuts(self):
        """Configura los atajos de teclado"""
        # CTRL+F: Focus en el cajón de búsqueda
        self.shortcut_search = QShortcut(QKeySequence("Ctrl+F"), self)
        self.shortcut_search.activated.connect(self.focus_search)
        
        # Flecha arriba: Mover hacia arriba en la lista
        self.shortcut_up = QShortcut(QKeySequence("Up"), self)
        self.shortcut_up.activated.connect(self.move_selection_up)
        
        # Flecha abajo: Mover hacia abajo en la lista
        self.shortcut_down = QShortcut(QKeySequence("Down"), self)
        self.shortcut_down.activated.connect(self.move_selection_down)
        
        # CTRL+O: Abrir carpeta del archivo
        self.shortcut_open_folder = QShortcut(QKeySequence("Ctrl+O"), self)
        self.shortcut_open_folder.activated.connect(self.open_file_folder)
        
        # CTRL+E: Editar archivo
        self.shortcut_edit = QShortcut(QKeySequence("Ctrl+E"), self)
        self.shortcut_edit.activated.connect(self.edit_file)
        
        # NUEVOS HOTKEYS PARA EL SEPARADOR
        # Flecha derecha: Expandir panel derecho (mover separador a la izquierda)
        self.shortcut_right = QShortcut(QKeySequence("Right"), self)
        self.shortcut_right.activated.connect(self.expand_right_panel)
        
        # Flecha izquierda: Expandir panel izquierdo (mover separador a la derecha)
        self.shortcut_left = QShortcut(QKeySequence("Left"), self)
        self.shortcut_left.activated.connect(self.expand_left_panel)
    
    def focus_search(self):
        """Pone el foco en el cajón de búsqueda"""
        self.search_input.setFocus()
        self.search_input.selectAll()
    
    def move_selection_up(self):
        """Mueve la selección hacia arriba en la lista"""
        if self.results_list.count() == 0:
            return
            
        current_row = self.results_list.currentRow()
        if current_row <= 0:
            return
            
        # Buscar el elemento anterior que sea seleccionable (no header)
        for i in range(current_row - 1, -1, -1):
            item = self.results_list.item(i)
            if item and item.flags() & Qt.ItemFlag.ItemIsSelectable:
                self.results_list.setCurrentRow(i)
                break
    
    def move_selection_down(self):
        """Mueve la selección hacia abajo en la lista"""
        if self.results_list.count() == 0:
            return
            
        current_row = self.results_list.currentRow()
        if current_row >= self.results_list.count() - 1:
            return
            
        # Buscar el elemento siguiente que sea seleccionable (no header)
        for i in range(current_row + 1, self.results_list.count()):
            item = self.results_list.item(i)
            if item and item.flags() & Qt.ItemFlag.ItemIsSelectable:
                self.results_list.setCurrentRow(i)
                break
    


    def expand_right_panel(self):
        """Expande el panel derecho moviendo el separador hacia la izquierda"""
        if not hasattr(self, 'horizontal_splitter'):
            return
        
        current_sizes = self.horizontal_splitter.sizes()
        if len(current_sizes) != 2:
            return
        
        total_width = sum(current_sizes)
        step = total_width // 8  # Mover 12.5% del ancho total
        
        # Reducir panel izquierdo, expandir panel derecho
        new_left = max(current_sizes[0] - step, total_width // 8)  # Mínimo 12.5%
        new_right = total_width - new_left
        
        self.horizontal_splitter.setSizes([new_left, new_right])
        print(f"Expandiendo panel derecho: {new_left}, {new_right}")

    def expand_left_panel(self):
        """Expande el panel izquierdo moviendo el separador hacia la derecha"""
        if not hasattr(self, 'horizontal_splitter'):
            return
        
        current_sizes = self.horizontal_splitter.sizes()
        if len(current_sizes) != 2:
            return
        
        total_width = sum(current_sizes)
        step = total_width // 8  # Mover 12.5% del ancho total
        
        # Expandir panel izquierdo, reducir panel derecho
        new_left = min(current_sizes[0] + step, total_width * 7 // 8)  # Máximo 87.5%
        new_right = total_width - new_left
        
        self.horizontal_splitter.setSizes([new_left, new_right])
        print(f"Expandiendo panel izquierdo: {new_left}, {new_right}")



    def get_current_file_path(self):
        """Obtiene la ruta del archivo actualmente seleccionado"""
        current_item = self.results_list.currentItem()
        if not current_item:
            return None
            
        data = current_item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return None
            
        _, _, path = data
        return path
    
    def open_file_folder(self):
        """Abre la carpeta que contiene el archivo actual"""
        file_path = self.get_current_file_path()
        if not file_path:
            QMessageBox.information(self, "Información", "No hay archivo seleccionado")
            return
            
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "Advertencia", f"El archivo no existe:\n{file_path}")
            return
            
        try:
            folder_path = os.path.dirname(file_path)
            
            # Detectar el sistema operativo y abrir el explorador correspondiente
            system = platform.system()
            
            if system == "Linux":
                # Intentar varios exploradores de archivos de Linux
                file_managers = ['xdg-open', 'nautilus', 'dolphin', 'thunar', 'nemo', 'pcmanfm']
                
                for fm in file_managers:
                    try:
                        subprocess.run([fm, folder_path], check=True)
                        break
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        continue
                else:
                    # Si ningún explorador funciona, mostrar error
                    QMessageBox.warning(self, "Error", 
                                      f"No se pudo abrir el explorador de archivos.\n"
                                      f"Carpeta: {folder_path}")
                    
            elif system == "Windows":
                subprocess.run(['explorer', folder_path])
                
            elif system == "Darwin":  # macOS
                subprocess.run(['open', folder_path])
            else:
                QMessageBox.information(self, "No soportado", 
                                      f"Sistema operativo no soportado: {system}")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al abrir la carpeta:\n{str(e)}")
    
    def edit_file(self):
        """Abre el archivo actual en el editor por defecto"""
        file_path = self.get_current_file_path()
        if not file_path:
            QMessageBox.information(self, "Información", "No hay archivo seleccionado")
            return
            
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "Advertencia", f"El archivo no existe:\n{file_path}")
            return
            
        try:
            system = platform.system()
            
            if system == "Linux":
                # Intentar varios editores de texto de Linux
                editors = ['code', 'gedit', 'kate', 'mousepad', 'nano', 'vim', 'xdg-open']
                
                for editor in editors:
                    try:
                        # Para editores GUI, usar Popen para no bloquear la aplicación
                        if editor in ['code', 'gedit', 'kate', 'mousepad', 'xdg-open']:
                            subprocess.Popen([editor, file_path])
                        else:
                            # Para editores de terminal, abrir en una nueva terminal
                            subprocess.Popen(['x-terminal-emulator', '-e', editor, file_path])
                        break
                    except FileNotFoundError:
                        continue
                else:
                    QMessageBox.warning(self, "Error", 
                                      f"No se encontró un editor disponible.\n"
                                      f"Archivo: {file_path}")
                    
            elif system == "Windows":
                os.startfile(file_path)
                
            elif system == "Darwin":  # macOS
                subprocess.Popen(['open', file_path])
            else:
                QMessageBox.information(self, "No soportado", 
                                      f"Sistema operativo no soportado: {system}")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al abrir el archivo:\n{str(e)}")
    
    def keyPressEvent(self, event):
        """Maneja eventos de teclado adicionales"""
        # Si estamos en el campo de búsqueda, permitir navegación con flechas
        if self.search_input.hasFocus():
            if event.key() == Qt.Key.Key_Down:
                # Ir al primer elemento seleccionable de la lista
                if self.results_list.count() > 0:
                    for i in range(self.results_list.count()):
                        item = self.results_list.item(i)
                        if item and item.flags() & Qt.ItemFlag.ItemIsSelectable:
                            self.results_list.setCurrentRow(i)
                            self.results_list.setFocus()
                            break
                return
            elif event.key() == Qt.Key.Key_Up:
                # Ir al último elemento seleccionable de la lista
                if self.results_list.count() > 0:
                    for i in range(self.results_list.count() - 1, -1, -1):
                        item = self.results_list.item(i)
                        if item and item.flags() & Qt.ItemFlag.ItemIsSelectable:
                            self.results_list.setCurrentRow(i)
                            self.results_list.setFocus()
                            break
                return
        
        # Llamar al manejador padre para otros eventos
        super().keyPressEvent(event)
    
    def load_selected_folders(self):
        """Carga las carpetas seleccionadas desde un archivo JSON"""
        try:
            # Intentar cargar la configuración guardada
            if os.path.exists('filter_settings.json'):
                with open('filter_settings.json', 'r') as f:
                    data = json.load(f)
                    if 'selected_folders' in data and isinstance(data['selected_folders'], list):
                        # Filtrar para asegurarnos que solo se incluyen carpetas válidas
                        self.selected_folders = [folder for folder in data['selected_folders'] 
                                                if folder in self.root_folders]
                        print(f"Filtros cargados: {self.selected_folders}")
                    else:
                        # Si la estructura no es correcta, usar todas las carpetas
                        self.selected_folders = self.root_folders.copy()
                        print("Formato de filtros incorrecto, usando todas las carpetas")
            else:
                # Si el archivo no existe, usar todas las carpetas
                self.selected_folders = self.root_folders.copy()
                print("No hay filtros guardados, usando todas las carpetas")
        except Exception as e:
            print(f"Error cargando filtros: {e}")
            # Si hay algún error, usar todas las carpetas
            self.selected_folders = self.root_folders.copy()

    def save_selected_folders(self):
        """Guarda las carpetas seleccionadas en un archivo JSON"""
        try:
            # Crear diccionario de configuración
            config = {
                'selected_folders': self.selected_folders if self.selected_folders else []
            }
            
            # Guardar en formato JSON
            with open('filter_settings.json', 'w') as f:
                json.dump(config, f, indent=4)
            
            print(f"Filtros guardados: {self.selected_folders}")
        except Exception as e:
            print(f"Error guardando filtros: {e}")

    def open_folder_filter(self):
        dialog = PathFilterDialog(self, self.db_path, self.root_folders)
        if dialog.exec():
            self.selected_folders = dialog.get_selected_folders()
            print(f"Nuevos filtros seleccionados: {self.selected_folders}")
            # Guardar los filtros seleccionados
            self.save_selected_folders()
            # Actualizar la búsqueda con los filtros seleccionados
            self.search_snippets()

    def delayed_search(self):
        # "Debounce" technique to avoid many consecutive searches
        if hasattr(self, 'search_timer') and self.search_timer is not None:
            self.search_timer.stop()
            self.search_timer = None
        
        # Start search after a small delay
        QTimer.singleShot(300, self.search_snippets)
        
    def search_snippets(self):
        # Limpiar los resultados anteriores
        self.results_list.clear()
        
        # Verificar si hay carpetas seleccionadas, si no, cargarlas
        if not hasattr(self, 'selected_folders') or self.selected_folders is None:
            self.load_selected_folders()
        
        # Actualizar la etiqueta de estado a "Buscando..."
        self.status_label.setText("Buscando...")
        
        # Cancelar cualquier búsqueda anterior en progreso
        if self.search_thread is not None and self.search_thread.isRunning():
            self.search_thread.terminate()
            self.search_thread.wait()
        
        # Crear y configurar el worker thread
        search_term = self.search_input.text()
        self.search_thread = SearchWorker(self.db_path, search_term, self.selected_folders)
        
        # Conectar señales
        self.search_thread.search_finished.connect(self.process_search_results)
        self.search_thread.error_occurred.connect(self.handle_search_error)
        
        # Iniciar la búsqueda en un hilo separado
        self.search_thread.start()
    
    def process_search_results(self, results):
        # Limpiar resultados anteriores
        self.results_list.clear()
        
        if not results:
            self.status_label.setText("Resultados: 0")
            return
        
        # Categorizar resultados
        categorized_results = self.categorize_results(results)
        
        # Mostrar resultados por categorías
        self.display_categorized_results(categorized_results)
        
        # Actualizar etiqueta de estado con el conteo de resultados
        total_count = sum(len(cat_results) for cat_results in categorized_results.values())
        self.status_label.setText(f"Resultados: {total_count}")
        
        # Seleccionar el primer resultado si existe
        if self.results_list.count() > 0:
            # Buscar el primer elemento seleccionable (no header)
            for i in range(self.results_list.count()):
                item = self.results_list.item(i)
                if item and item.flags() & Qt.ItemFlag.ItemIsSelectable:
                    self.results_list.setCurrentRow(i)
                    break
    
    def categorize_results(self, results):
        """Categoriza los resultados según el tipo de coincidencia"""
        search_term = self.search_input.text().lower().strip()
        
        # Rutas prioritarias para contenido
        priority_paths = [
            "/mnt/windows/FTP/wiki/Obsidian/Spaces/Wiki/Linux/Comandos/",
            "/mnt/windows/FTP/wiki/Obsidian/Spaces/Wiki/Linux/Tutoriales/",
            "/mnt/windows/FTP/wiki/Obsidian/Spaces/Wiki/Linux/Apps/",
            "/mnt/windows/FTP/wiki/Obsidian/Spaces/Wiki/Python/",
            "/mnt/windows/FTP/wiki/Obsidian/Recortes/"
        ]
        
        categorized = {
            'titulo': [],
            'tag': [],
            'contenido_priority': [],
            'contenido_other': []
        }
        
        if not search_term:
            # Si no hay término de búsqueda, poner todo en contenido_other
            categorized['contenido_other'] = results
            return categorized
        
        for snippet_id, filename, path, content, tags in results:
            filename_lower = filename.lower()
            content_lower = content.lower()
            tags_lower = [tag.lower() for tag in tags] if tags else []
            
            # Verificar coincidencia por título
            if search_term in filename_lower:
                categorized['titulo'].append((snippet_id, filename, path, content, tags))
            # Verificar coincidencia por tag
            elif any(search_term in tag for tag in tags_lower):
                categorized['tag'].append((snippet_id, filename, path, content, tags))
            # Verificar coincidencia por contenido
            elif search_term in content_lower:
                # Verificar si está en ruta prioritaria
                is_priority = any(path.startswith(priority_path) for priority_path in priority_paths)
                if is_priority:
                    categorized['contenido_priority'].append((snippet_id, filename, path, content, tags))
                else:
                    categorized['contenido_other'].append((snippet_id, filename, path, content, tags))
            else:
                # Fallback para resultados de FTS que no coinciden exactamente
                categorized['contenido_other'].append((snippet_id, filename, path, content, tags))
        
        return categorized
    
    def display_categorized_results(self, categorized_results):
        """Muestra los resultados categorizados con headers"""
        
        # Definir categorías y sus títulos
        categories = [
            ('titulo', 'TÍTULO', categorized_results['titulo']),
            ('tag', 'TAG', categorized_results['tag']),
            ('contenido_priority', 'CONTENIDO (Prioritario)', categorized_results['contenido_priority']),
            ('contenido_other', 'CONTENIDO', categorized_results['contenido_other'])
        ]
        
        for category_key, category_title, results in categories:
            if not results:
                continue
                
            # Añadir header de categoría
            self.add_category_header(category_title, len(results))
            
            # Añadir resultados de la categoría
            for snippet_id, filename, path, content, tags in results:
                self.add_result_item(snippet_id, filename, path, content, tags, category_key)
    
    def add_category_header(self, title, count):
        """Añade un header de categoría a la lista"""
        header_item = QListWidgetItem(f"── {title} ({count}) ──")
        header_item.setFlags(Qt.ItemFlag.NoItemFlags)  # No seleccionable
        header_item.setBackground(QColor(CatppuccinDarkTheme.surface1))
        header_item.setForeground(QColor(CatppuccinDarkTheme.mauve))
        
        # Configurar fuente en negrita
        font = QFont()
        font.setBold(True)
        font.setPointSize(10)
        header_item.setFont(font)
        
        self.results_list.addItem(header_item)
    
    def add_result_item(self, snippet_id, filename, path, content, tags, category):
        """Añade un elemento de resultado a la lista"""
        # Mostrar nombre del archivo y tags
        display_text = filename
        
        if tags:
            display_text += f" ({', '.join(tags)})"
        
        item = QListWidgetItem(display_text)
        
        # Guardar datos del snippet
        item.setData(Qt.ItemDataRole.UserRole, (snippet_id, content, path))
        
        # Hacer el elemento seleccionable
        item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
        
        # Configurar colores según categoría
        if category == 'titulo':
            item.setForeground(QColor(CatppuccinDarkTheme.green))
        elif category == 'tag':
            item.setForeground(QColor(CatppuccinDarkTheme.blue))
        elif category == 'contenido_priority':
            item.setForeground(QColor(CatppuccinDarkTheme.yellow))
        else:
            item.setForeground(QColor(CatppuccinDarkTheme.text))
        
        # Añadir indentación visual
        item.setText("    " + display_text)
        
        self.results_list.addItem(item)
    
    def show_snippet(self, current, previous):
        if current is None:
            return
        
        # Verificar si es un header (no tiene datos de usuario)
        data = current.data(Qt.ItemDataRole.UserRole)
        if data is None:
            return
        
        snippet_id, content, path = data
        
        # Extraer el nombre del archivo sin extensión
        filename = os.path.basename(path)
        filename_without_ext = os.path.splitext(filename)[0]
        
        # Limpiar el frontmatter del contenido
        cleaned_content = self.remove_frontmatter(content)
        
        # Añadir el nombre del archivo como título principal
        content_with_header = f"# {filename_without_ext}\n\n**Ruta:** {path}\n\n{cleaned_content}"
        
        # Renderizar el markdown a HTML
        html_content = MarkdownRenderer.render_markdown(content_with_header)
        
        # Mostrar el contenido HTML
        self.markdown_view.setHtml(html_content)
    
    def remove_frontmatter(self, content):
        """Elimina el frontmatter YAML del contenido"""
        # Buscar frontmatter que empiece y termine con ---
        frontmatter_pattern = re.compile(r'^---\s*\n.*?\n---\s*\n', re.DOTALL | re.MULTILINE)
        
        # Eliminar el frontmatter si existe
        cleaned_content = frontmatter_pattern.sub('', content)
        
        # Eliminar líneas vacías iniciales que pudieran quedar
        cleaned_content = cleaned_content.lstrip('\n')
        
        return cleaned_content
    
    def handle_search_error(self, error_message):
        # Manejar errores de búsqueda
        QMessageBox.critical(self, "Error de búsqueda", error_message)
        self.status_label.setText("Error en la búsqueda")
    
    def closeEvent(self, event):
        # Asegurarse de que el hilo de búsqueda termine antes de cerrar
        if self.search_thread is not None and self.search_thread.isRunning():
            self.search_thread.terminate()
            self.search_thread.wait()
        
        # Cerrar la conexión a la base de datos al salir
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
        
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    
    # Aplicar el tema Catppuccin
    CatppuccinDarkTheme.apply_to_app(app)
    
    # Ruta de la base de datos
    db_path = '/home/huan/Scripts/utilities/tiddlywiki/wiki_obsidian.db'  # Cambiar por la ruta real de tu base de datos
    
    # Lista de carpetas raíz para el filtro
    root_folders = [
        "/mnt/windows/FTP/wiki/Obsidian/Spaces/Wiki",
        "/mnt/windows/FTP/wiki/Obsidian/Spaces/Blogs",
        "/mnt/windows/FTP/wiki/Obsidian/Spaces/Proyectos Interesantes",
        "/mnt/windows/FTP/wiki/Obsidian/Spaces/Scripts",
        "/mnt/windows/FTP/wiki/Obsidian/Recortes"
    ]
    
    viewer = MarkdownSearchViewer(db_path, root_folders)
    viewer.show()
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()