import sys
import sqlite3
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLineEdit, QListWidget, QTextEdit, QPushButton, QLabel, QListWidgetItem,
                             QDialog, QCheckBox, QScrollArea, QSplitter, QFrame, QMessageBox,  QDialogButtonBox)
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QColor, QPalette, QFont, QIcon
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
            QLineEdit, QTextEdit, QListWidget {{
                background-color: {cls.surface0};
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
            
            QScrollBar:vertical {{
                background-color: {cls.surface0};
                width: 12px;
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
            "/mnt/windows/FTP/Obsidian/Spaces/Wiki",
            "/mnt/windows/FTP/Obsidian/Spaces/Blogs",
            "/mnt/windows/FTP/Obsidian/Spaces/Proyectos Interesantes",
            "/mnt/windows/FTP/Obsidian/Spaces/Scripts",
            "/mnt/windows/FTP/Obsidian/Recortes"
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
        
        # Panel izquierdo: Lista de resultados
        self.results_list = QListWidget()
        self.results_list.currentItemChanged.connect(self.show_snippet)
        # Añadir espacio vertical entre los elementos
        self.results_list.setStyleSheet("""
            QListWidget::item { 
                padding-top: 5px; 
                padding-bottom: 5px; 
            }
        """)      


        # Panel derecho: Visualizador de markdown
        self.markdown_view = QTextEdit()
        self.markdown_view.setReadOnly(True)
        
        # Añade ambos widgets al splitter horizontal
        horizontal_splitter.addWidget(self.results_list)
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
        
        status_layout.addWidget(self.status_label)
        main_splitter.addWidget(status_widget)
        
        # Configurar tamaños del splitter vertical (90% contenido, 10% status)
        main_splitter.setSizes([int(self.height() * 0.9), int(self.height() * 0.1)])
        
        main_layout.addWidget(main_splitter)
        
        # Cargar todos los snippets al inicio
        self.search_snippets()
    
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

    # Modificar el método open_folder_filter para guardar los filtros
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
        # Procesar los resultados devueltos por el worker
        for snippet_id, filename, path, content, tags in results:
            # Mostrar solo el nombre del archivo y las etiquetas
            display_text = filename
            
            if tags:
                display_text += f" ({', '.join(tags)})"
            
            item = self.results_list.addItem(display_text)
            # Guardar el ID, contenido y ruta completa como datos del item
            self.results_list.item(self.results_list.count() - 1).setData(Qt.ItemDataRole.UserRole, 
                                                                        (snippet_id, content, path))
        
        # Actualizar etiqueta de estado con el conteo de resultados
        self.status_label.setText(f"Resultados: {self.results_list.count()}")
        
        # Seleccionar el primer resultado si existe
        if self.results_list.count() > 0:
            self.results_list.setCurrentRow(0)

    
    def show_snippet(self, current, previous):
        if current is None:
            return
        
        snippet_id, content, path = current.data(Qt.ItemDataRole.UserRole)
        
        # Añadir la ruta en la parte superior del contenido
        content_with_path = f"**Ruta:** {path}\n\n{content}"
        
        # Renderizar el markdown a HTML
        html_content = MarkdownRenderer.render_markdown(content_with_path)
        
        # Mostrar el contenido HTML
        self.markdown_view.setHtml(html_content)
    
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
    db_path = 'wiki_obsidian.db'  # Cambiar por la ruta real de tu base de datos
    
    # Lista de carpetas raíz para el filtro
    root_folders = [
        "/mnt/windows/FTP/Obsidian/Spaces/Wiki",
        "/mnt/windows/FTP/Obsidian/Spaces/Blogs",
        "/mnt/windows/FTP/Obsidian/Spaces/Proyectos Interesantes",
        "/mnt/windows/FTP/Obsidian/Spaces/Scripts",
        "/mnt/windows/FTP/Obsidian/Recortes"
    ]
    
    viewer = MarkdownSearchViewer(db_path, root_folders)
    viewer.show()
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()