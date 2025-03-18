#!/usr/bin/env python3
import sys
import os
import sqlite3
import subprocess
import datetime
import re
from dateutil.relativedelta import relativedelta
from PyQt6.QtWidgets import (QApplication, QMainWindow, QSplitter, QTreeWidget, 
                           QTreeWidgetItem, QLineEdit, QVBoxLayout, QHBoxLayout, 
                           QWidget, QPushButton, QTextEdit, QCheckBox, QMessageBox,
                           QLabel, QFileDialog, QComboBox)
from PyQt6.QtCore import Qt, QSize, QSortFilterProxyModel
from PyQt6.QtGui import QKeySequence, QFont, QIcon, QShortcut
from PyQt6.QtWebEngineWidgets import QWebEngineView
import markdown

# Reutilizamos la función de parse_date del script original
def parse_date(date_str):
    """
    Convierte una cadena de fecha en un objeto datetime.
    Admite formatos:
    - Fechas ISO (YYYY-MM-DD)
    - Meses (enero 2024, ene 2024)
    - Años (2024)
    - Relativos (hoy, ayer, esta semana, este mes, este año)
    """
    today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Fechas relativas
    if date_str.lower() == "hoy":
        return today, today + datetime.timedelta(days=1) - datetime.timedelta(microseconds=1)
    
    if date_str.lower() == "ayer":
        yesterday = today - datetime.timedelta(days=1)
        return yesterday, yesterday + datetime.timedelta(days=1) - datetime.timedelta(microseconds=1)
    
    if date_str.lower() == "esta semana":
        start_of_week = today - datetime.timedelta(days=today.weekday())
        end_of_week = start_of_week + datetime.timedelta(days=7) - datetime.timedelta(microseconds=1)
        return start_of_week, end_of_week
    
    if date_str.lower() == "este mes":
        start_of_month = today.replace(day=1)
        if today.month == 12:
            end_of_month = today.replace(year=today.year + 1, month=1, day=1) - datetime.timedelta(microseconds=1)
        else:
            end_of_month = today.replace(month=today.month + 1, day=1) - datetime.timedelta(microseconds=1)
        return start_of_month, end_of_month
    
    if date_str.lower() == "este año":
        start_of_year = today.replace(month=1, day=1)
        end_of_year = today.replace(year=today.year + 1, month=1, day=1) - datetime.timedelta(microseconds=1)
        return start_of_year, end_of_year
    
    # Intentar formato ISO
    try:
        date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        return date, date + datetime.timedelta(days=1) - datetime.timedelta(microseconds=1)
    except ValueError:
        pass
    
    # Intentar año
    if re.match(r'^\d{4}$', date_str):
        year = int(date_str)
        start = datetime.datetime(year, 1, 1)
        end = datetime.datetime(year + 1, 1, 1) - datetime.timedelta(microseconds=1)
        return start, end
    
    # Intentar mes y año
    meses = {
        'enero': 1, 'ene': 1, 'jan': 1, 'january': 1,
        'febrero': 2, 'feb': 2, 'february': 2,
        'marzo': 3, 'mar': 3, 'march': 3,
        'abril': 4, 'abr': 4, 'apr': 4, 'april': 4,
        'mayo': 5, 'may': 5,
        'junio': 6, 'jun': 6, 'june': 6,
        'julio': 7, 'jul': 7, 'july': 7,
        'agosto': 8, 'ago': 8, 'aug': 8, 'august': 8,
        'septiembre': 9, 'sep': 9, 'sept': 9, 'september': 9,
        'octubre': 10, 'oct': 10, 'october': 10,
        'noviembre': 11, 'nov': 11, 'november': 11,
        'diciembre': 12, 'dic': 12, 'dec': 12, 'december': 12
    }
    
    for nombre_mes, num_mes in meses.items():
        # Patrones como "enero 2024" o "ene 2024"
        pattern = f'^{nombre_mes}\s+(\d{{4}})$'
        match = re.match(pattern, date_str.lower())
        if match:
            year = int(match.group(1))
            start = datetime.datetime(year, num_mes, 1)
            if num_mes == 12:
                end = datetime.datetime(year + 1, 1, 1) - datetime.timedelta(microseconds=1)
            else:
                end = datetime.datetime(year, num_mes + 1, 1) - datetime.timedelta(microseconds=1)
            return start, end
    
    raise ValueError(f"Formato de fecha no reconocido: {date_str}")

def search_snippets(db_path, search_text="", exact_match=False, path=None, title=None, 
                   tags=None, content=None, source=None, date=None):
    print(f"Buscando en: {db_path}")
    print(f"Parámetros de búsqueda: texto='{search_text}', exacta={exact_match}, path={path}, title={title}, tags={tags}")
    
    # Resto del código existente...
    
    # Antes de retornar los resultados

    """
    Busca snippets en la base de datos según los criterios especificados.
    Los criterios se combinan con AND lógico.
    Añade soporte para búsqueda difusa/exacta.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Construir la consulta SQL base
    query = """
    SELECT DISTINCT s.id, s.filename, s.path, s.content, s.source, s.last_modified
    FROM snippets s
    """
    
    # Condiciones y parámetros
    conditions = []
    params = {}
    
    # Procesar la búsqueda general
    if search_text:
        if exact_match:
            # Si es exacta, busca coincidencia exacta en todos los campos
            text_conditions = []
            text_conditions.append("s.filename LIKE :search_text")
            text_conditions.append("s.path LIKE :search_text")
            text_conditions.append("s.content LIKE :search_text")
            text_conditions.append("s.source LIKE :search_text")
            # También buscar en tags
            query += " LEFT JOIN snippet_tags st ON s.id = st.snippet_id LEFT JOIN tags t ON st.tag_id = t.id "
            text_conditions.append("t.name LIKE :search_text")
            
            conditions.append("(" + " OR ".join(text_conditions) + ")")
            params["search_text"] = f"%{search_text}%"
        else:
            # Si es difusa, usar la tabla FTS si está disponible
            try:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='snippet_fts'")
                if cursor.fetchone():
                    # Usar FTS para búsqueda difusa
                    query = """
                    SELECT DISTINCT s.id, s.filename, s.path, s.content, s.source, s.last_modified
                    FROM snippet_fts fts
                    JOIN snippets s ON s.filename = fts.filename AND s.path = fts.path
                    """
                    conditions.append("snippet_fts MATCH :search_text")
                    params["search_text"] = search_text
                else:
                    # Fallback si no hay FTS
                    text_conditions = []
                    text_conditions.append("s.filename LIKE :search_text")
                    text_conditions.append("s.path LIKE :search_text")
                    text_conditions.append("s.content LIKE :search_text")
                    text_conditions.append("s.source LIKE :search_text")
                    
                    query += " LEFT JOIN snippet_tags st ON s.id = st.snippet_id LEFT JOIN tags t ON st.tag_id = t.id "
                    text_conditions.append("t.name LIKE :search_text")
                    
                    conditions.append("(" + " OR ".join(text_conditions) + ")")
                    params["search_text"] = f"%{search_text}%"
            except Exception as e:
                print(f"Error con FTS: {e}")
                # Fallback si hay algún error
                text_conditions = []
                text_conditions.append("s.filename LIKE :search_text")
                text_conditions.append("s.path LIKE :search_text")
                text_conditions.append("s.content LIKE :search_text")
                text_conditions.append("s.source LIKE :search_text")
                
                conditions.append("(" + " OR ".join(text_conditions) + ")")
                params["search_text"] = f"%{search_text}%"
    
    # Si hay tags, unimos con las tablas necesarias si no lo hemos hecho ya
    if tags and "JOIN tags t ON" not in query:
        query += """
        JOIN snippet_tags st ON s.id = st.snippet_id
        JOIN tags t ON st.tag_id = t.id
        """
    
    if tags:
        # Convertir la cadena de tags en una lista
        tag_list = [tag.strip() for tag in tags.split(',')]
        # Para cada tag, agregamos una condición
        for i, tag in enumerate(tag_list):
            conditions.append(f"EXISTS (SELECT 1 FROM tags t JOIN snippet_tags st ON t.id = st.tag_id WHERE st.snippet_id = s.id AND t.name = :tag{i})")
            params[f"tag{i}"] = tag
    
    # Agregar otras condiciones
    if path:
        conditions.append("s.path LIKE :path")
        params["path"] = f"%{path}%"
    
    if title:  # En realidad busca en filename
        conditions.append("s.filename LIKE :title")
        params["title"] = f"%{title}%"
    
    if content:
        conditions.append("s.content LIKE :content")
        params["content"] = f"%{content}%"
    
    if source:
        conditions.append("s.source LIKE :source")
        params["source"] = f"%{source}%"
    
    if date:
        try:
            date_start, date_end = parse_date(date)
            conditions.append("s.last_modified BETWEEN :date_start AND :date_end")
            params["date_start"] = date_start.strftime("%Y-%m-%d %H:%M:%S")
            params["date_end"] = date_end.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError as e:
            print(f"Error al procesar la fecha: {e}")
            conn.close()
            return []
    
    # Completar la consulta con las condiciones
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    # Ejecutar la consulta
    try:
        cursor.execute(query, params)
        results = cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Error en consulta SQL: {e}")
        print(f"Query: {query}")
        print(f"Params: {params}")
        conn.close()
        return []
    
    # Obtener tags para cada snippet encontrado
    snippets_with_tags = []
    for row in results:
        snippet_dict = dict(row)
        
        # Obtener tags para este snippet
        cursor.execute("""
            SELECT t.name 
            FROM tags t 
            JOIN snippet_tags st ON t.id = st.tag_id 
            WHERE st.snippet_id = ?
        """, (row['id'],))
        
        tags = [tag[0] for tag in cursor.fetchall()]
        snippet_dict['tags'] = tags
        snippets_with_tags.append(snippet_dict)
    
    conn.close()
    print(f"Resultados encontrados: {len(snippets_with_tags)}")
    return snippets_with_tags

    
def update_snippet_content(db_path, snippet_id, new_content):
    """Actualiza el contenido de un snippet en la base de datos"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Actualizar el contenido y la fecha de modificación
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "UPDATE snippets SET content = ?, last_modified = ? WHERE id = ?",
            (new_content, current_time, snippet_id)
        )
        
        # Comprobar si también hay que actualizar la tabla FTS si existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='snippet_fts'")
        if cursor.fetchone():
            # Obtener la información del snippet
            cursor.execute("SELECT filename, path, source FROM snippets WHERE id = ?", (snippet_id,))
            row = cursor.fetchone()
            if row:
                filename, path, source = row
                # Actualizar FTS
                cursor.execute(
                    "UPDATE snippet_fts SET content = ? WHERE filename = ? AND path = ?",
                    (new_content, filename, path)
                )
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error al actualizar snippet: {e}")
        return False

def delete_snippet(db_path, snippet_id):
    """Elimina un snippet de la base de datos"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Obtener información del snippet antes de eliminarlo
        cursor.execute("SELECT filename, path FROM snippets WHERE id = ?", (snippet_id,))
        snippet_info = cursor.fetchone()
        
        # Eliminar registros de tablas relacionadas primero
        cursor.execute("DELETE FROM snippet_tags WHERE snippet_id = ?", (snippet_id,))
        
        # Eliminar el snippet principal
        cursor.execute("DELETE FROM snippets WHERE id = ?", (snippet_id,))
        
        # Si existe la tabla FTS, actualizar también
        if snippet_info:
            filename, path = snippet_info
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='snippet_fts'")
            if cursor.fetchone():
                cursor.execute(
                    "DELETE FROM snippet_fts WHERE filename = ? AND path = ?",
                    (filename, path)
                )
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error al eliminar snippet: {e}")
        return False

class SnippetViewer(QMainWindow):
    def __init__(self, db_path):
        super().__init__()
        self.db_path = db_path
        self.current_snippet_id = None
        self.current_snippet_path = None
        # Theme system
        self.themes = {
            "Default": {
                'bg': '#ffffff', 
                'fg': '#000000',
                'accent': '#2979ff',
                'secondary_bg': '#f0f0f0',
                'border': '#cccccc',
                'selection': '#e0e0e0',
                'button_hover': '#d0d0d0'
            },
            "Dark": {
                'bg': '#2d2d2d',
                'fg': '#ffffff',
                'accent': '#03a9f4',
                'secondary_bg': '#3d3d3d',
                'border': '#555555',
                'selection': '#505050',
                'button_hover': '#606060'
            },
            "Synthwave": {
                'bg': '#262335',
                'fg': '#f8f8f2',
                'accent': '#ff8adc',
                'secondary_bg': '#3b315e',
                'border': '#7d77a9',
                'selection': '#4b3c83',
                'button_hover': '#fe5f86'
            },
            "Catppuccin": {
                'bg': '#1e1e2e',
                'fg': '#cdd6f4',
                'accent': '#89b4fa',
                'secondary_bg': '#313244',
                'border': '#6c7086',
                'selection': '#45475a',
                'button_hover': '#585b70'
            }
        }
        self.current_theme = "Catppuccin"  # Default theme
        
        self.initUI()
    


    def initUI(self):
        self.setWindowTitle("Visor de Snippets")
        self.setGeometry(100, 100, 1200, 800)
        
        # Widget principal
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        
         # Panel superior: búsqueda y botones
        search_panel = QWidget()
        search_layout = QHBoxLayout(search_panel)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_panel.setMaximumHeight(50)  # Ajustar según necesidad

        # Selector de temas
        self.theme_selector = QComboBox()
        self.theme_selector.addItems(list(self.themes.keys()))
        self.theme_selector.setCurrentText(self.current_theme)
        self.theme_selector.currentTextChanged.connect(self.apply_theme)
        search_layout.addWidget(QLabel("Tema:"))
        search_layout.addWidget(self.theme_selector)

        # Caja de búsqueda unificada
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar snippets... (t:título p:ruta tag:etiquetas d:fecha s:fuente)")
        self.search_input.returnPressed.connect(self.perform_search)
        search_layout.addWidget(self.search_input)
        
        # Checkbox para búsqueda exacta
        self.exact_match_checkbox = QCheckBox("Búsqueda exacta")
        search_layout.addWidget(self.exact_match_checkbox)
        
        # Checkbox para editable
        self.editable_checkbox = QCheckBox("Editable")
        search_layout.addWidget(self.editable_checkbox)
        self.editable_checkbox.stateChanged.connect(self.toggle_editable)
        
        # Botones para acciones
        self.btn_open_folder = QPushButton("Abrir carpeta")
        self.btn_open_folder.setToolTip("Abrir carpeta del snippet (Ctrl+O)")
        self.btn_open_folder.clicked.connect(self.open_folder)
        search_layout.addWidget(self.btn_open_folder)
        
        self.btn_open_obsidian = QPushButton("Abrir en Obsidian")
        self.btn_open_obsidian.setToolTip("Abrir en Obsidian (Ctrl+E)")
        self.btn_open_obsidian.clicked.connect(self.open_in_obsidian)
        search_layout.addWidget(self.btn_open_obsidian)
        
        self.btn_delete = QPushButton("Eliminar")
        self.btn_delete.setToolTip("Eliminar snippet (Ctrl+Delete)")
        self.btn_delete.clicked.connect(self.delete_current_snippet)
        search_layout.addWidget(self.btn_delete)
        
        # Botón de ayuda para mostrar la sintaxis de búsqueda
        self.btn_help = QPushButton("?")
        self.btn_help.setToolTip("Mostrar ayuda de búsqueda")
        self.btn_help.setMaximumWidth(30)
        self.btn_help.clicked.connect(self.show_search_help)
        search_layout.addWidget(self.btn_help)
        
        main_layout.addWidget(search_panel)
        
        # # Panel de filtros avanzados
        # filter_panel = QWidget()
        # filter_layout = QHBoxLayout(filter_panel)
        # filter_layout.setContentsMargins(0, 0, 0, 0)
        # filter_panel.setMaximumHeight(50)  # Ajustar según necesidad


        # # Labels y campos de filtro
        # filter_layout.addWidget(QLabel("Título:"))
        # self.title_filter = QLineEdit()
        # filter_layout.addWidget(self.title_filter)
        
        # filter_layout.addWidget(QLabel("Ruta:"))
        # self.path_filter = QLineEdit()
        # filter_layout.addWidget(self.path_filter)
        
        # filter_layout.addWidget(QLabel("Tags:"))
        # self.tags_filter = QLineEdit()
        # filter_layout.addWidget(self.tags_filter)
        
        # filter_layout.addWidget(QLabel("Fecha:"))
        # self.date_filter = QLineEdit()
        # self.date_filter.setPlaceholderText("ej: hoy, ayer, 2023-01-01")
        # filter_layout.addWidget(self.date_filter)
        
        # filter_layout.addWidget(QLabel("Fuente:"))
        # self.source_filter = QLineEdit()
        # filter_layout.addWidget(self.source_filter)
        
        # main_layout.addWidget(filter_panel)
        
        # Splitter para paneles izquierdo y derecho
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Panel izquierdo: resultados de búsqueda
        self.results_tree = QTreeWidget()
        self.results_tree.setHeaderLabels(["Nombre", "Tags", "Ruta", "Fecha"])
        self.results_tree.setColumnWidth(0, 150)  # Ancho para la columna de tags
        self.results_tree.setColumnWidth(1, 200)
        self.results_tree.setColumnWidth(2, 300)
        self.results_tree.itemClicked.connect(self.snippet_selected)
        splitter.addWidget(self.results_tree)
        
        # Hacer que las columnas sean ordenables
        self.results_tree.setSortingEnabled(True)
        self.results_tree.header().setSectionsClickable(True)

        # Panel derecho: contenido del snippet y vista renderizada
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Vista renderizada del markdown
        self.markdown_view = QWebEngineView()
        self.markdown_view.setMinimumWidth(500)
        
        # Editor de texto para contenido
        self.content_editor = QTextEdit()
        self.content_editor.setVisible(False)  # Inicialmente oculto
        self.content_editor.textChanged.connect(self.content_changed)
        
        right_layout.addWidget(self.markdown_view)
        right_layout.addWidget(self.content_editor)
        
        splitter.addWidget(right_panel)
        
        # Configurar proporción inicial del splitter
        splitter.setSizes([300, 900])  # Proporciones iniciales
        
        main_layout.addWidget(splitter)
        
        # Configurar atajos de teclado
        self.shortcut_open_folder = QShortcut(QKeySequence("Ctrl+O"), self)
        self.shortcut_open_folder.activated.connect(self.open_folder)
        
        self.shortcut_open_obsidian = QShortcut(QKeySequence("Ctrl+E"), self)
        self.shortcut_open_obsidian.activated.connect(self.open_in_obsidian)
        
        self.shortcut_delete = QShortcut(QKeySequence("Ctrl+Delete"), self)
        self.shortcut_delete.activated.connect(self.delete_current_snippet)

        self.apply_theme(self.current_theme)

        # Desactivar botones inicialmente
        self.update_button_states()
        
        # Realizar búsqueda inicial vacía para mostrar todos los resultados
    
        self.perform_search()
    


    def apply_theme(self, theme_name):
        """Aplica el tema seleccionado a la interfaz"""
        if theme_name not in self.themes:
            return
            
        self.current_theme = theme_name
        theme = self.themes[theme_name]
        
        # Set application style sheet
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background-color: {theme['bg']};
                color: {theme['fg']};
            }}
            
            QTreeWidget {{
                background-color: {theme['secondary_bg']};
                color: {theme['fg']};
                border: 1px solid {theme['border']};
            }}
            
            QTreeWidget::item:selected {{
                background-color: {theme['selection']};
            }}
            
            QLineEdit, QTextEdit {{
                background-color: {theme['secondary_bg']};
                color: {theme['fg']};
                border: 1px solid {theme['border']};
                border-radius: 3px;
                padding: 2px 4px;
            }}
            
            QPushButton {{
                background-color: {theme['secondary_bg']};
                color: {theme['fg']};
                border: 1px solid {theme['border']};
                border-radius: 3px;
                padding: 4px 8px;
            }}
            
            QPushButton:hover {{
                background-color: {theme['button_hover']};
            }}
            
            QPushButton:pressed {{
                background-color: {theme['accent']};
            }}
            
            QCheckBox {{
                color: {theme['fg']};
            }}
            
            QSplitter::handle {{
                background-color: {theme['border']};
            }}
            
            QLabel {{
                color: {theme['fg']};
            }}
        """)
        
        # Custom WebView background
        if theme_name != "Default":  # Only for dark themes
            script = f"""
            (function() {{
                document.body.style.backgroundColor = "{theme['bg']}";
                document.body.style.color = "{theme['fg']}";
            }})()
            """
            self.markdown_view.page().runJavaScript(script)


    def show_search_help(self):
        """Muestra un diálogo con ayuda sobre la sintaxis de búsqueda"""
        help_text = """
        <h3>Sintaxis de búsqueda</h3>
        <p>Puedes usar los siguientes atajos para filtrar tu búsqueda:</p>
        <ul>
            <li><b>t:</b> o <b>title:</b> - Buscar en el título del archivo</li>
            <li><b>p:</b> o <b>path:</b> - Buscar en la ruta del archivo</li>
            <li><b>tag:</b> o <b>tags:</b> - Buscar por etiquetas (separadas por comas)</li>
            <li><b>d:</b> o <b>date:</b> - Buscar por fecha (hoy, ayer, este mes, etc.)</li>
            <li><b>s:</b> o <b>source:</b> - Buscar por fuente del snippet</li>
        </ul>
        <p>Ejemplos:</p>
        <ul>
            <li><code>python t:tutorial</code> - Busca "python" en contenido y "tutorial" en el título</li>
            <li><code>p:proyectos tag:importante,urgente</code> - Snippets en la ruta "proyectos" con etiquetas "importante" y "urgente"</li>
            <li><code>d:este mes s:web</code> - Snippets de este mes con fuente "web"</li>
        </ul>
        <p>Puedes usar comillas para términos con espacios: <code>t:"mi proyecto"</code></p>
        """
        
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Ayuda de búsqueda")
        msg_box.setTextFormat(Qt.TextFormat.RichText)
        msg_box.setText(help_text)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.exec()


    def content_changed(self):
        """Maneja los cambios en el editor de contenido"""
        if self.current_snippet_id and self.content_editor.isVisible():
            new_content = self.content_editor.toPlainText()
            
            # Obtener colores del tema actual
            theme = self.themes[self.current_theme]
            bg_color = theme['bg']
            text_color = theme['fg']
            
            # Actualizar la vista renderizada del markdown
            html_content = markdown.markdown(new_content)
            styled_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        line-height: 1.6;
                        margin: 20px;
                        background-color: {bg_color};
                        color: {text_color};
                    }}
                    h1, h2, h3, h4, h5, h6 {{
                        color: {text_color};
                        margin-top: 20px;
                    }}
                    code {{
                        background-color: {theme['secondary_bg']};
                        padding: 2px 4px;
                        border-radius: 3px;
                    }}
                    pre {{
                        background-color: {theme['secondary_bg']};
                        padding: 10px;
                        border-radius: 5px;
                        overflow-x: auto;
                    }}
                    blockquote {{
                        border-left: 4px solid {theme['border']};
                        padding-left: 16px;
                        margin-left: 0;
                        color: {theme['accent']};
                    }}
                </style>
            </head>
            <body>
                {html_content}
            </body>
            </html>
            """
            self.markdown_view.setHtml(styled_html)
            
    def perform_search(self):
        """Realiza la búsqueda según los criterios especificados en la caja de búsqueda unificada"""
        query = self.search_input.text()
        exact_match = self.exact_match_checkbox.isChecked()
        
        # Analizar la consulta para extraer filtros
        filters = self.parse_search_query(query)
        
        # Realizar la búsqueda
        results = search_snippets(
            self.db_path, 
            search_text=filters['search_text'], 
            exact_match=exact_match,
            title=filters['title'],
            path=filters['path'],
            tags=filters['tags'],
            date=filters['date'],
            source=filters['source']
        )
        
        # Actualizar el árbol de resultados
        self.update_results_tree(results)

    
    def update_results_tree(self, results):
        """Actualiza el árbol de resultados con los snippets encontrados"""
        self.results_tree.clear()
        
        for snippet in results:
            item = QTreeWidgetItem(self.results_tree)
            item.setText(0, snippet['filename'])
            item.setText(1, snippet['path'])
            
            # Mostrar tags en la columna 2 en lugar de como hijos
            if snippet.get('tags'):
                item.setText(2, ', '.join(snippet['tags']))
            
            # Formatear fecha
            date_str = snippet['last_modified']
            try:
                date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                formatted_date = date_obj.strftime("%d/%m/%Y %H:%M")
                item.setText(3, formatted_date)
            except:
                item.setText(3, date_str)
            
            # Guardar el ID del snippet como datos del item
            item.setData(0, Qt.ItemDataRole.UserRole, snippet['id'])

        self.results_tree.sortItems(1, Qt.SortOrder.AscendingOrder)

        # No expandir todos los elementos ya que no hay hijos
        # self.results_tree.expandAll()
        
        # Actualizar estado de los botones
        self.update_button_states()

    def snippet_selected(self, item):
        """Maneja la selección de un snippet en el árbol de resultados"""
        # Ignorar si es un item hijo (tags)
        if item.parent() is not None:
            return
        
        # Recuperar ID del snippet
        snippet_id = item.data(0, Qt.ItemDataRole.UserRole)
        if snippet_id:
            self.current_snippet_id = snippet_id
            self.load_snippet_content(snippet_id)
            self.apply_theme(self.current_theme)
            self.update_button_states()
    
    def load_snippet_content(self, snippet_id):
        """Carga el contenido del snippet seleccionado"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT content, path, filename FROM snippets WHERE id = ?", 
            (snippet_id,)
        )
        result = cursor.fetchone()
        conn.close()
        
        if result:
            content, path, filename = result
            self.current_snippet_path = os.path.join(path, filename)
            
            # Actualizar el editor de texto si está visible
            if self.content_editor.isVisible():
                self.content_editor.setPlainText(content)
            
            # Renderizar el markdown
            html_content = markdown.markdown(content)
            
            # Aplicar estilos CSS básicos para mejorar la visualización
            styled_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        line-height: 1.6;
                        margin: 20px;
                    }}
                    h1, h2, h3, h4, h5, h6 {{
                        color: #333;
                        margin-top: 20px;
                    }}
                    code {{
                        background-color: #f4f4f4;
                        padding: 2px 4px;
                        border-radius: 3px;
                    }}
                    pre {{
                        background-color: #f4f4f4;
                        padding: 10px;
                        border-radius: 5px;
                        overflow-x: auto;
                    }}
                    blockquote {{
                        border-left: 4px solid #ddd;
                        padding-left: 16px;
                        margin-left: 0;
                        color: #666;
                    }}
                </style>
            </head>
            <body>
                {html_content}
            </body>
            </html>
            """
            
            self.markdown_view.setHtml(styled_html)
    
    def load_snippet_content(self, snippet_id):
        """Carga el contenido del snippet seleccionado"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT content, path, filename FROM snippets WHERE id = ?", 
            (snippet_id,)
        )
        result = cursor.fetchone()
        conn.close()
        
        if result:
            content, path, filename = result
            self.current_snippet_path = os.path.join(path, filename)
            
            # Actualizar el editor de texto si está visible
            if self.content_editor.isVisible():
                self.content_editor.setPlainText(content)
            
            # Renderizar el markdown
            html_content = markdown.markdown(content)
            
            # Obtener colores del tema actual
            theme = self.themes[self.current_theme]
            bg_color = theme['bg']
            text_color = theme['fg']
            
            # Aplicar estilos CSS básicos para mejorar la visualización
            styled_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        line-height: 1.6;
                        margin: 20px;
                        background-color: {bg_color};
                        color: {text_color};
                    }}
                    h1, h2, h3, h4, h5, h6 {{
                        color: {text_color};
                        margin-top: 20px;
                    }}
                    code {{
                        background-color: {theme['secondary_bg']};
                        padding: 2px 4px;
                        border-radius: 3px;
                    }}
                    pre {{
                        background-color: {theme['secondary_bg']};
                        padding: 10px;
                        border-radius: 5px;
                        overflow-x: auto;
                    }}
                    blockquote {{
                        border-left: 4px solid {theme['border']};
                        padding-left: 16px;
                        margin-left: 0;
                        color: {theme['accent']};
                    }}
                </style>
            </head>
            <body>
                {html_content}
            </body>
            </html>
            """
            
            self.markdown_view.setHtml(styled_html)
    
    def save_content(self):
        """Guarda el contenido editado en la base de datos"""
        if self.current_snippet_id and self.content_editor.isVisible():
            new_content = self.content_editor.toPlainText()
            success = update_snippet_content(self.db_path, self.current_snippet_id, new_content)
            
            if success:
                QMessageBox.information(self, "Guardado", "Contenido guardado correctamente")
            else:
                QMessageBox.warning(self, "Error", "Error al guardar el contenido")
    
    def toggle_editable(self, state):
        """Alterna entre vista de solo lectura y editable"""
        if state == Qt.CheckState.Checked:
            # Si hay un snippet seleccionado, cargar su contenido en el editor
            if self.current_snippet_id:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT content FROM snippets WHERE id = ?", (self.current_snippet_id,))
                result = cursor.fetchone()
                conn.close()
                
                if result:
                    content = result[0]
                    self.content_editor.setPlainText(content)
            
            # Mostrar editor y ocultar vista renderizada
            self.content_editor.setVisible(True)
            self.markdown_view.setVisible(False)
            
            # Añadir botón guardar si no existe
            if not hasattr(self, 'btn_save'):
                self.btn_save = QPushButton("Guardar cambios")
                self.btn_save.clicked.connect(self.save_content)
                # Añadir al layout donde están los otros botones
                self.btn_save.setParent(self.search_input.parent())
                self.search_input.parent().layout().addWidget(self.btn_save)
            else:
                self.btn_save.setVisible(True)
        else:
            # Ocultar editor y mostrar vista renderizada
            self.content_editor.setVisible(False)
            self.markdown_view.setVisible(True)
            
            # Ocultar botón guardar si existe
            if hasattr(self, 'btn_save'):
                self.btn_save.setVisible(False)
    
    def open_folder(self):
        """Abre la carpeta que contiene el snippet actual"""
        if not self.current_snippet_id:
            QMessageBox.information(self, "Información", "Selecciona un snippet primero")
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT path FROM snippets WHERE id = ?", (self.current_snippet_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            folder_path = result[0]
            try:
                # Abrir explorador de archivos según el sistema operativo
                if os.name == 'nt':  # Windows
                    os.startfile(folder_path)
                elif os.name == 'posix':  # Linux, Mac
                    if sys.platform == 'darwin':  # Mac
                        subprocess.Popen(['open', folder_path])
                    else:  # Linux
                        subprocess.Popen(['xdg-open', folder_path])
            except Exception as e:
                QMessageBox.warning(self, "Error", f"No se pudo abrir la carpeta: {e}")
        else:
            QMessageBox.warning(self, "Error", "No se encontró la ruta del snippet")
    
    def open_in_obsidian(self):
        """Abre el snippet actual en Obsidian"""
        if not self.current_snippet_id:
            QMessageBox.information(self, "Información", "Selecciona un snippet primero")
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT path, filename FROM snippets WHERE id = ?", (self.current_snippet_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0] and result[1]:
            path, filename = result
            file_path = os.path.join(path, filename)
            
            try:
                # Intentar abrir con Obsidian usando el protocolo obsidian://
                obsidian_uri = f"obsidian://open?path={os.path.abspath(file_path)}"
                
                if os.name == 'nt':  # Windows
                    os.startfile(obsidian_uri)
                elif os.name == 'posix':  # Linux, Mac
                    if sys.platform == 'darwin':  # Mac
                        subprocess.Popen(['open', obsidian_uri])
                    else:  # Linux
                        subprocess.Popen(['xdg-open', obsidian_uri])
            except Exception as e:
                QMessageBox.warning(self, "Error", f"No se pudo abrir Obsidian: {e}")
                
                # Intento alternativo: abrir el archivo con la aplicación predeterminada
                try:
                    if os.name == 'nt':  # Windows
                        os.startfile(file_path)
                    elif os.name == 'posix':  # Linux, Mac
                        if sys.platform == 'darwin':  # Mac
                            subprocess.Popen(['open', file_path])
                        else:  # Linux
                            subprocess.Popen(['xdg-open', file_path])
                except Exception as e2:
                    QMessageBox.warning(self, "Error", f"No se pudo abrir el archivo: {e2}")
        else:
            QMessageBox.warning(self, "Error", "No se encontró la ruta del snippet")
    
    def delete_current_snippet(self):
        """Elimina el snippet actual con confirmación previa"""
        if not self.current_snippet_id:
            QMessageBox.information(self, "Información", "Selecciona un snippet primero")
            return
        
        # Obtener nombre del snippet para mostrar en el mensaje de confirmación
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT filename FROM snippets WHERE id = ?", (self.current_snippet_id,))
        result = cursor.fetchone()
        conn.close()
        
        filename = result[0] if result else "este snippet"
        
        # Pedir confirmación
        reply = QMessageBox.question(
            self, 
            "Confirmar eliminación",
            f"¿Estás seguro de que quieres eliminar '{filename}'?\n\nEsta acción no se puede deshacer.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Eliminar el snippet
            success = delete_snippet(self.db_path, self.current_snippet_id)
            
            if success:
                QMessageBox.information(self, "Eliminado", f"'{filename}' eliminado correctamente")
                # Actualizar la búsqueda para reflejar los cambios
                self.perform_search()
                # Limpiar la vista actual
                self.markdown_view.setHtml("")
                if self.content_editor.isVisible():
                    self.content_editor.clear()
                # Resetear el snippet actual
                self.current_snippet_id = None
                self.current_snippet_path = None
                # Actualizar estado de botones
                self.update_button_states()
            else:
                QMessageBox.warning(self, "Error", "Error al eliminar el snippet")
    
    def update_button_states(self):
        """Actualiza el estado de los botones según si hay un snippet seleccionado"""
        snippet_selected = self.current_snippet_id is not None
        self.btn_open_folder.setEnabled(snippet_selected)
        self.btn_open_obsidian.setEnabled(snippet_selected)
        self.btn_delete.setEnabled(snippet_selected)
        
        # Si hay botón de guardar y hay un snippet seleccionado y el editor es visible
        if hasattr(self, 'btn_save'):
            self.btn_save.setEnabled(snippet_selected and self.content_editor.isVisible())


    def parse_search_query(self, query):
        """
        Analiza una consulta de búsqueda con atajos y devuelve un diccionario con los filtros.
        
        Atajos soportados:
        - t: o title: - título/filename
        - p: o path: - ruta
        - tag: o tags: - etiquetas
        - d: o date: - fecha
        - s: o source: - fuente
        
        Ejemplo: "python t:tutorial p:programming/python tag:beginner,advanced d:este mes"
        """
        filters = {
            'search_text': '',
            'title': None,
            'path': None,
            'tags': None,
            'date': None,
            'source': None
        }
        
        # Patrones para los diferentes atajos
        patterns = {
            'title': [r't:', r'title:'],
            'path': [r'p:', r'path:'],
            'tags': [r'tag:', r'tags:'],
            'date': [r'd:', r'date:'],
            'source': [r's:', r'source:']
        }
        
        # Divide la consulta por espacios pero mantiene unidos los valores con comillas
        tokens = []
        in_quotes = False
        current_token = ''
        
        for char in query + ' ':  # Añadimos un espacio al final para procesar el último token
            if char == '"':
                in_quotes = not in_quotes
                current_token += char
            elif char == ' ' and not in_quotes:
                if current_token:
                    tokens.append(current_token)
                    current_token = ''
            else:
                current_token += char
        
        remaining_tokens = []
        
        # Procesar cada token
        for token in tokens:
            matched = False
            
            # Comprobar si el token tiene alguno de los atajos
            for filter_name, prefixes in patterns.items():
                for prefix in prefixes:
                    if token.lower().startswith(prefix):
                        # Extraer el valor eliminando el prefijo
                        value = token[len(prefix):].strip()
                        
                        # Si el valor está entre comillas, quitar las comillas
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        
                        filters[filter_name] = value
                        matched = True
                        break
                if matched:
                    break
            
            # Si no coincide con ningún patrón, agregarlo al texto de búsqueda general
            if not matched:
                remaining_tokens.append(token)
        
        # El texto restante se considera texto de búsqueda general
        filters['search_text'] = ' '.join(remaining_tokens)
        
        return filters

def main():
    app = QApplication(sys.argv)
    
    # Si se especifica la ruta a la base de datos como argumento
    if len(sys.argv) > 1:
        db_path = os.path.normpath(os.path.abspath(sys.argv[1]))

        print(f"Usando base de datos: {db_path}")  # Mensaje para depuración
    else:
        db_path, _ = QFileDialog.getOpenFileName(
            None, 
            "Seleccionar base de datos SQLite", 
            "", 
            "Archivos SQLite (*.sqlite *.db);;Todos los archivos (*)"
        )
        
        if not db_path:
            sys.exit(0)
    
    # Verificar que la base de datos existe y tiene la estructura correcta
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Verificar que existe la tabla snippets
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='snippets'")
        if not cursor.fetchone():
            QMessageBox.critical(None, "Error", "La base de datos seleccionada no contiene la tabla 'snippets'")
            conn.close()
            sys.exit(1)
        
        # Verificar que hay datos en la tabla
        cursor.execute("SELECT COUNT(*) FROM snippets")
        count = cursor.fetchone()[0]
        print(f"Encontrados {count} snippets en la base de datos")
        
        conn.close()
    except sqlite3.Error as e:
        QMessageBox.critical(None, "Error", f"Error al acceder a la base de datos: {e}")
        sys.exit(1)
    
    viewer = SnippetViewer(db_path)
    viewer.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()