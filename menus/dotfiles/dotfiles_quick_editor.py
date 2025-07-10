#!/usr/bin/env python3
"""
PyQt6 Dotfiles Editor - Versión con base de datos SQLite
Usa la base de datos creada por dotfiles_indexer.py para búsquedas rápidas
Author: volteret4
Dependencies: PyQt6, sqlite3, pyyaml
"""

import sys
import os
import subprocess
import argparse
import sqlite3
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                            QWidget, QTextEdit, QPushButton, QLabel,
                            QMessageBox, QSplitter, QLineEdit, QRadioButton,
                            QButtonGroup, QTableWidget, QTableWidgetItem, QHeaderView,
                            QCheckBox, QComboBox)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QKeySequence, QShortcut, QFont
import yaml


class DatabaseSearchThread(QThread):
    """Hilo para realizar búsquedas en la base de datos sin bloquear la UI"""
    results_ready = pyqtSignal(list)

    def __init__(self, db_path, query, filters):
        super().__init__()
        self.db_path = db_path
        self.query = query
        self.filters = filters

    def run(self):
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row

            # Construir query SQL con filtros
            base_query = '''
                SELECT * FROM dotfiles_with_categories
                WHERE 1=1
            '''
            params = []

            # Filtro de búsqueda por texto
            if self.query.strip():
                query_lower = f"%{self.query.lower()}%"
                base_query += '''
                    AND (
                        LOWER(filename) LIKE ? OR
                        LOWER(relative_path) LIKE ? OR
                        LOWER(path) LIKE ? OR
                        LOWER(categories) LIKE ?
                    )
                '''
                params.extend([query_lower, query_lower, query_lower, query_lower])

            # Filtro por tipo de archivo
            if self.filters.get('config_only'):
                base_query += ' AND is_config = 1'
            if self.filters.get('executable_only'):
                base_query += ' AND is_executable = 1'

            # Filtro por fuente
            if self.filters.get('source_root'):
                base_query += ' AND source_root = ?'
                params.append(self.filters['source_root'])

            # Filtro por extensión
            if self.filters.get('extension'):
                base_query += ' AND extension = ?'
                params.append(self.filters['extension'])

            # Ordenamiento por relevancia
            base_query += '''
                ORDER BY
                    CASE
                        WHEN LOWER(filename) = LOWER(?) THEN 1
                        WHEN LOWER(filename) LIKE ? THEN 2
                        WHEN LOWER(relative_path) LIKE ? THEN 3
                        ELSE 4
                    END,
                    is_config DESC,
                    filename
                LIMIT 500
            '''

            if self.query.strip():
                params.extend([self.query.lower(), f"{self.query.lower()}%", f"%{self.query.lower()}%"])
            else:
                params.extend(['', '', ''])

            cursor = conn.execute(base_query, params)
            results = [dict(row) for row in cursor.fetchall()]

            conn.close()
            self.results_ready.emit(results)

        except Exception as e:
            print(f"Error en búsqueda: {e}")
            self.results_ready.emit([])


class DotfilesEditor(QMainWindow):
    """Editor de dotfiles con base de datos SQLite"""

    def __init__(self, theme_name: str = 'solarized-dark'):
        super().__init__()

        # Configuración de rutas
        self.script_dir = Path(__file__).parent
        self.db_path = self.script_dir / 'dotfiles.db'
        self.themes_file = self.script_dir / 'themes.yml'

        # Sistema de temas
        self.theme_name = theme_name
        self.theme_config = self.load_theme()

        # Verificar que existe la base de datos
        if not self.db_path.exists():
            QMessageBox.warning(
                None,
                "Base de datos no encontrada",
                f"No se encontró la base de datos de dotfiles en {self.db_path}.\n"
                "Ejecuta primero: python dotfiles_indexer.py"
            )
            sys.exit(1)

        # Conexión a la base de datos
        self.setup_database()

        # Variables de estado
        self.current_file = None
        self.current_content = ""
        self.search_thread = None
        self.source_roots = []
        self.extensions = []

        # Inicializar UI
        self.init_ui()
        self.apply_theme()
        self.load_filter_options()
        self.setup_shortcuts()

        # Cargar archivos iniciales
        self.perform_search()

    def setup_database(self):
        """Configura la conexión a la base de datos"""
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row

        # Optimizaciones para lectura
        self.conn.execute('PRAGMA synchronous = OFF')
        self.conn.execute('PRAGMA journal_mode = MEMORY')
        self.conn.execute('PRAGMA temp_store = MEMORY')
        self.conn.execute('PRAGMA cache_size = 10000')

    def load_theme(self) -> dict:
        """Carga la configuración del tema"""
        if not self.themes_file.exists():
            self.create_default_themes()

        try:
            with open(self.themes_file, 'r', encoding='utf-8') as f:
                themes = yaml.safe_load(f)
                return themes.get(self.theme_name, themes.get('solarized-dark', {}))
        except (yaml.YAMLError, IOError):
            return self.get_default_theme()

    def get_default_theme(self) -> dict:
        """Retorna el tema por defecto"""
        return {
            'bg_color': '#002b36',
            'text_color': '#839496',
            'accent_color': '#268bd2',
            'widget_bg': '#073642',
            'border_color': '#586e75',
            'search_bg': '#073642',
            'search_border': '#586e75'
        }

    def create_default_themes(self):
        """Crea el archivo de temas con configuraciones por defecto"""
        themes = {
            'solarized-dark': {
                'bg_color': '#002b36',
                'text_color': '#839496',
                'accent_color': '#268bd2',
                'widget_bg': '#073642',
                'border_color': '#586e75',
                'search_bg': '#073642',
                'search_border': '#586e75'
            },
            'tokyo-night': {
                'bg_color': '#1a1b26',
                'text_color': '#c0caf5',
                'accent_color': '#7aa2f7',
                'widget_bg': '#24283b',
                'border_color': '#414868',
                'search_bg': '#24283b',
                'search_border': '#414868'
            },
            'catppucin': {
                'bg_color': '#1e1e2e',
                'text_color': '#cdd6f4',
                'accent_color': '#89b4fa',
                'widget_bg': '#313244',
                'border_color': '#45475a',
                'search_bg': '#313244',
                'search_border': '#45475a'
            },
            'gruvbox': {
                'bg_color': '#282828',
                'text_color': '#ebdbb2',
                'accent_color': '#83a598',
                'widget_bg': '#3c3836',
                'border_color': '#504945',
                'search_bg': '#3c3836',
                'search_border': '#504945'
            },
            'kanagawa': {
                'bg_color': '#1f1f28',
                'text_color': '#dcd7ba',
                'accent_color': '#7e9cd8',
                'widget_bg': '#2a2a37',
                'border_color': '#54546d',
                'search_bg': '#2a2a37',
                'search_border': '#54546d'
            },
            'forest-dark': {
                'bg_color': '#2d3142',
                'text_color': '#bfc7d5',
                'accent_color': '#56c596',
                'widget_bg': '#3d405b',
                'border_color': '#4f5b66',
                'search_bg': '#3d405b',
                'search_border': '#4f5b66'
            },
            'neon': {
                'bg_color': '#0d1117',
                'text_color': '#00ff88',
                'accent_color': '#ff0080',
                'widget_bg': '#161b22',
                'border_color': '#00ff88',
                'search_bg': '#161b22',
                'search_border': '#00ff88'
            }
        }

        try:
            with open(self.themes_file, 'w', encoding='utf-8') as f:
                yaml.dump(themes, f, default_flow_style=False, allow_unicode=True)
        except IOError:
            pass

    def apply_theme(self):
        """Aplica el tema a toda la interfaz"""
        bg_color = self.theme_config.get('bg_color', '#002b36')
        text_color = self.theme_config.get('text_color', '#839496')
        accent_color = self.theme_config.get('accent_color', '#268bd2')
        widget_bg = self.theme_config.get('widget_bg', '#073642')
        border_color = self.theme_config.get('border_color', '#586e75')
        search_bg = self.theme_config.get('search_bg', '#073642')
        search_border = self.theme_config.get('search_border', '#586e75')

        style = f"""
            QMainWindow {{
                background-color: {bg_color};
                color: {text_color};
            }}

            QWidget {{
                background-color: {bg_color};
                color: {text_color};
                font-family: 'Consolas', 'Monaco', monospace;
            }}

            QTableWidget {{
                background-color: {widget_bg};
                color: {text_color};
                border: 2px solid {border_color};
                border-radius: 5px;
                selection-background-color: {accent_color};
                selection-color: {bg_color};
                gridline-color: {border_color};
                alternate-background-color: {bg_color};
            }}

            QTableWidget::item {{
                padding: 5px;
                border: none;
            }}

            QTableWidget::item:selected {{
                background-color: {accent_color};
                color: {bg_color};
            }}

            QHeaderView::section {{
                background-color: {widget_bg};
                color: {text_color};
                border: 1px solid {border_color};
                padding: 5px;
                font-weight: bold;
            }}

            QHeaderView::section:hover {{
                background-color: {accent_color};
                color: {bg_color};
            }}

            QTextEdit {{
                background-color: {widget_bg};
                color: {text_color};
                border: 2px solid {border_color};
                border-radius: 5px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11pt;
                selection-background-color: {accent_color};
                selection-color: {bg_color};
            }}

            QLineEdit {{
                background-color: {search_bg};
                color: {text_color};
                border: 2px solid {search_border};
                border-radius: 5px;
                padding: 8px;
                font-size: 12pt;
            }}

            QLineEdit:focus {{
                border-color: {accent_color};
            }}

            QPushButton {{
                background-color: {widget_bg};
                color: {text_color};
                border: 2px solid {border_color};
                border-radius: 5px;
                padding: 8px;
                font-weight: bold;
                min-width: 60px;
            }}

            QPushButton:hover {{
                background-color: {accent_color};
                color: {bg_color};
                border-color: {accent_color};
            }}

            QPushButton:pressed {{
                background-color: {border_color};
            }}

            QPushButton:disabled {{
                background-color: {bg_color};
                color: {border_color};
                border-color: {border_color};
            }}

            QLabel {{
                color: {text_color};
                font-weight: bold;
                padding: 5px;
            }}

            QCheckBox {{
                color: {text_color};
                spacing: 5px;
            }}

            QCheckBox::indicator {{
                width: 15px;
                height: 15px;
            }}

            QCheckBox::indicator:unchecked {{
                border: 2px solid {border_color};
                background-color: {widget_bg};
            }}

            QCheckBox::indicator:checked {{
                border: 2px solid {accent_color};
                background-color: {accent_color};
            }}

            QComboBox {{
                background-color: {widget_bg};
                color: {text_color};
                border: 2px solid {border_color};
                border-radius: 5px;
                padding: 5px;
                min-width: 100px;
            }}

            QComboBox:hover {{
                border-color: {accent_color};
            }}

            QComboBox::drop-down {{
                border: none;
            }}

            QComboBox::down-arrow {{
                border: none;
                background: {accent_color};
            }}

            QComboBox QAbstractItemView {{
                background-color: {widget_bg};
                color: {text_color};
                border: 2px solid {border_color};
                selection-background-color: {accent_color};
            }}

            QSplitter::handle {{
                background-color: {border_color};
                width: 3px;
                height: 3px;
            }}

            QSplitter::handle:hover {{
                background-color: {accent_color};
            }}
        """
        self.setStyleSheet(style)

    def init_ui(self):
        self.setWindowTitle("Dotfiles Editor (Database)")
        self.setGeometry(100, 100, 1400, 900)

        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Layout principal vertical
        main_layout = QVBoxLayout(central_widget)

        # Barra superior con búsqueda
        search_bar = QWidget()
        search_layout = QHBoxLayout(search_bar)
        search_bar.setFixedHeight(50)

        # Campo de búsqueda
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar dotfiles por nombre, ruta o categoría...")
        self.search_input.textChanged.connect(self.on_search_changed)
        search_layout.addWidget(self.search_input)

        # Botón de reindexar
        self.reindex_btn = QPushButton("Reindexar")
        self.reindex_btn.clicked.connect(self.reindex_database)
        self.reindex_btn.setMaximumWidth(100)
        search_layout.addWidget(self.reindex_btn)

        main_layout.addWidget(search_bar)

        # Barra de filtros
        filter_bar = QWidget()
        filter_layout = QHBoxLayout(filter_bar)
        filter_bar.setFixedHeight(40)

        # Filtros
        self.config_only_cb = QCheckBox("Solo configuración")
        self.config_only_cb.toggled.connect(self.on_filter_changed)
        filter_layout.addWidget(self.config_only_cb)

        self.executable_only_cb = QCheckBox("Solo ejecutables")
        self.executable_only_cb.toggled.connect(self.on_filter_changed)
        filter_layout.addWidget(self.executable_only_cb)

        # Filtro por fuente
        filter_layout.addWidget(QLabel("Fuente:"))
        self.source_combo = QComboBox()
        self.source_combo.currentTextChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(self.source_combo)

        # Filtro por extensión
        filter_layout.addWidget(QLabel("Extensión:"))
        self.extension_combo = QComboBox()
        self.extension_combo.currentTextChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(self.extension_combo)

        filter_layout.addStretch()
        main_layout.addWidget(filter_bar)

        # Splitter para dividir los paneles
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # Panel izquierdo - Tabla de archivos
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # Información de resultados
        self.results_label = QLabel("Cargando...")
        left_layout.addWidget(self.results_label)

        # Tabla de archivos
        self.file_table = QTableWidget()
        self.file_table.setColumnCount(4)
        self.file_table.setHorizontalHeaderLabels(["Archivo", "Ruta", "Tipo", "Tamaño"])

        # Configurar tabla
        self.file_table.setAlternatingRowColors(True)
        self.file_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.file_table.setSortingEnabled(True)

        # Ajustar columnas
        header = self.file_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        # Conectar selección
        self.file_table.itemSelectionChanged.connect(self.load_selected_file)

        left_layout.addWidget(self.file_table)

        # Panel derecho - Editor
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Información del archivo actual
        self.current_file_label = QLabel("Ningún archivo seleccionado")
        right_layout.addWidget(self.current_file_label)

        # Editor de texto
        self.text_editor = QTextEdit()
        self.text_editor.setFont(QFont("Consolas", 11))
        right_layout.addWidget(self.text_editor)

        # Barra de botones inferior
        button_bar = QWidget()
        button_layout = QHBoxLayout(button_bar)

        self.save_btn = QPushButton("Guardar (Ctrl+S)")
        self.save_btn.clicked.connect(self.save_file)
        self.save_btn.setEnabled(False)
        button_layout.addWidget(self.save_btn)

        self.open_folder_btn = QPushButton("Carpeta (Ctrl+O)")
        self.open_folder_btn.clicked.connect(self.open_containing_folder)
        self.open_folder_btn.setEnabled(False)
        button_layout.addWidget(self.open_folder_btn)

        self.edit_vscode_btn = QPushButton("Zed (Ctrl+E)")
        self.edit_vscode_btn.clicked.connect(self.edit_with_vscodium)
        self.edit_vscode_btn.setEnabled(False)
        button_layout.addWidget(self.edit_vscode_btn)

        button_layout.addStretch()

        # Status label
        self.status_label = QLabel("Listo")
        button_layout.addWidget(self.status_label)

        right_layout.addWidget(button_bar)

        # Añadir paneles al splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([500, 900])

        # Timer para búsqueda con delay
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.perform_search)

    def load_filter_options(self):
        """Carga las opciones para los filtros"""
        try:
            # Cargar fuentes (source_roots)
            cursor = self.conn.execute('SELECT DISTINCT source_root FROM dotfiles ORDER BY source_root')
            self.source_roots = [row[0] for row in cursor.fetchall()]

            self.source_combo.clear()
            self.source_combo.addItem("Todas las fuentes", "")
            for source in self.source_roots:
                display_name = str(Path(source).name) if source else "Sin fuente"
                self.source_combo.addItem(display_name, source)

            # Cargar extensiones
            cursor = self.conn.execute('''
                SELECT DISTINCT extension FROM dotfiles
                WHERE extension IS NOT NULL AND extension != ""
                ORDER BY extension
            ''')
            self.extensions = [row[0] for row in cursor.fetchall()]

            self.extension_combo.clear()
            self.extension_combo.addItem("Todas las extensiones", "")
            for ext in self.extensions:
                self.extension_combo.addItem(ext, ext)

        except Exception as e:
            print(f"Error cargando opciones de filtro: {e}")

    def setup_shortcuts(self):
        """Configurar atajos de teclado"""
        # Ctrl+S para guardar
        save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        save_shortcut.activated.connect(self.save_file)

        # Ctrl+O para abrir carpeta
        open_folder_shortcut = QShortcut(QKeySequence("Ctrl+O"), self)
        open_folder_shortcut.activated.connect(self.open_containing_folder)

        # Ctrl+E para editar con VSCodium
        vscode_shortcut = QShortcut(QKeySequence("Ctrl+E"), self)
        vscode_shortcut.activated.connect(self.edit_with_vscodium)

        # Ctrl+F para enfocar búsqueda
        search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        search_shortcut.activated.connect(lambda: self.search_input.setFocus())

        # Ctrl+R para reindexar
        reindex_shortcut = QShortcut(QKeySequence("Ctrl+R"), self)
        reindex_shortcut.activated.connect(self.reindex_database)

        # Escape para limpiar búsqueda
        clear_shortcut = QShortcut(QKeySequence("Escape"), self)
        clear_shortcut.activated.connect(lambda: self.search_input.clear())

    def on_search_changed(self):
        """Maneja el cambio en el texto de búsqueda"""
        self.search_timer.stop()
        self.search_timer.start(300)  # 300ms delay

    def on_filter_changed(self):
        """Maneja el cambio en los filtros"""
        self.perform_search()

    def get_current_filters(self) -> dict:
        """Obtiene los filtros actuales"""
        return {
            'config_only': self.config_only_cb.isChecked(),
            'executable_only': self.executable_only_cb.isChecked(),
            'source_root': self.source_combo.currentData() or None,
            'extension': self.extension_combo.currentData() or None,
        }

    def perform_search(self):
        """Realiza la búsqueda en la base de datos"""
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.terminate()
            self.search_thread.wait()

        query = self.search_input.text().strip()
        filters = self.get_current_filters()

        self.search_thread = DatabaseSearchThread(self.db_path, query, filters)
        self.search_thread.results_ready.connect(self.update_results)
        self.search_thread.start()

        self.results_label.setText("Buscando...")

    def update_results(self, results):
        """Actualiza la tabla con los resultados de búsqueda"""
        self.file_table.setRowCount(len(results))

        for row, file_data in enumerate(results):
            # Columna 0: Nombre del archivo con indicadores
            filename = file_data['filename']
            if file_data['is_config']:
                filename += " [CONFIG]"
            if file_data['is_executable']:
                filename += " [EXEC]"

            filename_item = QTableWidgetItem(filename)
            filename_item.setData(Qt.ItemDataRole.UserRole, file_data)
            self.file_table.setItem(row, 0, filename_item)

            # Columna 1: Ruta relativa
            path_item = QTableWidgetItem(file_data['relative_path'])
            self.file_table.setItem(row, 1, path_item)

            # Columna 2: Tipo de archivo
            file_type = []
            if file_data['categories']:
                file_type.append(file_data['categories'].split(',')[0])  # Primera categoría
            if file_data['extension']:
                file_type.append(file_data['extension'])

            type_text = ' | '.join(file_type) if file_type else 'Archivo'
            type_item = QTableWidgetItem(type_text)
            self.file_table.setItem(row, 2, type_item)

            # Columna 3: Tamaño
            size_kb = file_data['size_bytes'] / 1024
            if size_kb < 1:
                size_text = f"{file_data['size_bytes']} B"
            elif size_kb < 1024:
                size_text = f"{size_kb:.1f} KB"
            else:
                size_mb = size_kb / 1024
                size_text = f"{size_mb:.1f} MB"

            size_item = QTableWidgetItem(size_text)
            size_item.setData(Qt.ItemDataRole.UserRole, file_data['size_bytes'])
            self.file_table.setItem(row, 3, size_item)

        # Actualizar información de resultados
        query_text = self.search_input.text().strip()
        if query_text:
            self.results_label.setText(f"Encontrados {len(results)} archivos para '{query_text}'")
        else:
            self.results_label.setText(f"Mostrando {len(results)} archivos")

        # Ordenar por relevancia inicialmente
        if query_text:
            self.file_table.sortItems(0, Qt.SortOrder.AscendingOrder)

    def load_selected_file(self):
        """Cargar el archivo seleccionado en el editor"""
        current_row = self.file_table.currentRow()
        if current_row < 0:
            return

        filename_item = self.file_table.item(current_row, 0)
        if not filename_item:
            return

        file_data = filename_item.data(Qt.ItemDataRole.UserRole)
        if not file_data:
            return

        try:
            self.current_file = Path(file_data['path'])

            if not self.current_file.exists():
                QMessageBox.warning(self, "Archivo no encontrado",
                                  f"El archivo {self.current_file} no existe.\n"
                                  "Considera reindexar la base de datos.")
                return

            # Leer el contenido del archivo
            try:
                with open(self.current_file, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                try:
                    with open(self.current_file, 'r', encoding='latin-1') as f:
                        content = f.read()
                except Exception as e:
                    QMessageBox.warning(self, "Error de codificación",
                                      f"No se pudo leer el archivo: {e}")
                    return

            self.text_editor.setPlainText(content)
            self.current_content = content

            # Actualizar UI
            display_info = f"Editando: {file_data['relative_path']}"
            if file_data['categories']:
                display_info += f" | Categorías: {file_data['categories']}"

            self.current_file_label.setText(display_info)
            self.save_btn.setEnabled(True)
            self.open_folder_btn.setEnabled(True)
            self.edit_vscode_btn.setEnabled(True)
            self.status_label.setText(f"Archivo cargado: {file_data['filename']}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar archivo: {e}")

    def save_file(self):
        """Guardar el archivo actual"""
        if not self.current_file:
            QMessageBox.information(self, "Info", "No hay archivo seleccionado para guardar")
            return

        try:
            content = self.text_editor.toPlainText()
            with open(self.current_file, 'w', encoding='utf-8') as f:
                f.write(content)

            self.current_content = content
            self.status_label.setText(f"Archivo guardado: {self.current_file.name}")

            # Limpiar el mensaje después de 3 segundos
            QTimer.singleShot(3000, lambda: self.status_label.setText("Listo"))

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al guardar archivo: {e}")

    def open_containing_folder(self):
        """Abrir la carpeta que contiene el archivo actual"""
        if not self.current_file:
            QMessageBox.information(self, "Info", "No hay archivo seleccionado")
            return

        folder_to_open = self.current_file.parent

        try:
            subprocess.run(['xdg-open', str(folder_to_open)], check=True)
            self.status_label.setText(f"Carpeta abierta: {folder_to_open}")
        except subprocess.CalledProcessError:
            QMessageBox.warning(self, "Error", "Error al abrir la carpeta")
        except FileNotFoundError:
            QMessageBox.warning(self, "Error", "xdg-open no encontrado")

    def edit_with_vscodium(self):
        """Abrir el archivo actual con Zed o VSCodium"""
        if not self.current_file:
            QMessageBox.information(self, "Info", "No hay archivo seleccionado para editar")
            return

        try:
            subprocess.Popen(['zeditor', str(self.current_file)])
            self.status_label.setText(f"Abriendo con Zed: {self.current_file.name}")
        except FileNotFoundError:
            # Intentar con 'code' si 'codium' no existe
            try:
                subprocess.Popen(['codium', str(self.current_file)])
                self.status_label.setText(f"Abriendo con VS Code: {self.current_file.name}")
            except FileNotFoundError:
                QMessageBox.warning(self, "Error", "VSCodium/VS Code no encontrado")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al abrir con VSCodium: {e}")

    def reindex_database(self):
        """Ejecuta el reindexado de la base de datos"""
        reply = QMessageBox.question(
            self, 'Reindexar base de datos',
            '¿Deseas reindexar la base de datos de dotfiles?\n'
            'Esto puede tomar varios minutos.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Cerrar conexión temporalmente
                self.conn.close()

                # Ejecutar el indexador
                indexer_script = self.script_dir / 'dotfiles_indexer.py'
                if indexer_script.exists():
                    self.status_label.setText("Reindexando...")
                    self.reindex_btn.setEnabled(False)

                    # Ejecutar en segundo plano
                    process = subprocess.Popen([
                        sys.executable, str(indexer_script)
                    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

                    stdout, stderr = process.communicate()

                    if process.returncode == 0:
                        QMessageBox.information(self, "Éxito",
                                              "Base de datos reindexada correctamente")
                        # Reconectar y recargar
                        self.setup_database()
                        self.load_filter_options()
                        self.perform_search()
                    else:
                        QMessageBox.warning(self, "Error",
                                          f"Error durante el reindexado:\n{stderr}")
                else:
                    QMessageBox.warning(self, "Error",
                                      "No se encontró dotfiles_indexer.py")

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error ejecutando reindexado: {e}")
            finally:
                self.reindex_btn.setEnabled(True)
                if not hasattr(self, 'conn') or not self.conn:
                    self.setup_database()

    def get_database_stats(self):
        """Obtiene estadísticas de la base de datos"""
        try:
            cursor = self.conn.execute('SELECT COUNT(*) FROM dotfiles')
            total_files = cursor.fetchone()[0]

            cursor = self.conn.execute('SELECT COUNT(*) FROM dotfiles WHERE is_config = 1')
            config_files = cursor.fetchone()[0]

            cursor = self.conn.execute('SELECT COUNT(DISTINCT source_root) FROM dotfiles')
            source_roots = cursor.fetchone()[0]

            return {
                'total_files': total_files,
                'config_files': config_files,
                'source_roots': source_roots
            }
        except Exception:
            return {'total_files': 0, 'config_files': 0, 'source_roots': 0}

    def show_database_info(self):
        """Muestra información sobre la base de datos"""
        stats = self.get_database_stats()
        info_text = f"""
Base de datos: {self.db_path}

Estadísticas:
• Total de archivos: {stats['total_files']}
• Archivos de configuración: {stats['config_files']}
• Fuentes indexadas: {stats['source_roots']}

Última actualización: {self.db_path.stat().st_mtime if self.db_path.exists() else 'Desconocida'}
        """
        QMessageBox.information(self, "Información de la base de datos", info_text)

    def closeEvent(self, event):
        """Manejar el cierre de la aplicación"""
        # Terminar hilo de búsqueda si está ejecutándose
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.terminate()
            self.search_thread.wait()

        # Verificar cambios sin guardar
        if self.current_file and self.text_editor.toPlainText() != self.current_content:
            reply = QMessageBox.question(
                self, 'Guardar cambios',
                'Hay cambios sin guardar. ¿Deseas guardar antes de salir?',
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel
            )

            if reply == QMessageBox.StandardButton.Save:
                self.save_file()
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
                return

        # Cerrar conexión a la base de datos
        if hasattr(self, 'conn'):
            self.conn.close()

        event.accept()


def main():
    parser = argparse.ArgumentParser(description='Dotfiles Editor con base de datos SQLite')
    parser.add_argument('--theme', default='solarized-dark',
                       choices=['solarized-dark', 'tokyo-night', 'catppucin',
                               'gruvbox', 'kanagawa', 'forest-dark', 'neon'],
                       help='Tema de color a usar')
    parser.add_argument('--db-info', action='store_true',
                       help='Mostrar información de la base de datos y salir')

    args = parser.parse_args()

    app = QApplication(sys.argv)

    # Si solo se quiere información de la DB
    if args.db_info:
        script_dir = Path(__file__).parent
        db_path = script_dir / 'dotfiles.db'

        if not db_path.exists():
            print(f"Base de datos no encontrada: {db_path}")
            print("Ejecuta primero: python dotfiles_indexer.py")
            sys.exit(1)

        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute('SELECT COUNT(*) FROM dotfiles')
        total = cursor.fetchone()[0]
        cursor = conn.execute('SELECT COUNT(*) FROM dotfiles WHERE is_config = 1')
        config = cursor.fetchone()[0]
        conn.close()

        print(f"Base de datos: {db_path}")
        print(f"Total de archivos: {total}")
        print(f"Archivos de configuración: {config}")
        sys.exit(0)

    editor = DotfilesEditor(args.theme)
    editor.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
