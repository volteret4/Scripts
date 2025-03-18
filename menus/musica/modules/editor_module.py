import os
import sqlite3
import json
from typing import List, Dict, Any, Optional, Tuple
import traceback
from datetime import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, 
                           QLineEdit, QPushButton, QComboBox, QTableWidget, 
                           QTableWidgetItem, QLabel, QFormLayout, QMessageBox,
                           QTextEdit, QDateTimeEdit, QSpinBox, QDoubleSpinBox,
                           QCheckBox, QDialog, QFileDialog, QScrollArea, QHeaderView)
from PyQt6.QtCore import Qt, pyqtSignal, QDateTime, QSettings

from base_module import BaseModule, THEMES
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseEditor(BaseModule):
    """Módulo para buscar y editar elementos en la base de datos de música."""
    
    def __init__(self, db_path: str = "music_database.db", parent=None, theme='Tokyo Night', **kwargs):
        # Definir atributos antes de llamar a super().__init__()
        self.db_path = db_path
        self.current_table = "songs"
        self.current_item_id = None
        self.edit_widgets = {}
        self.search_results = []
        self.column_order = {}  # Diccionario para almacenar el orden de columnas por tabla
        
        self.available_themes = kwargs.pop('temas', [])
        self.selected_theme = kwargs.pop('tema_seleccionado', theme)
        
        # Cargar el orden de columnas si está en los argumentos
        self.column_order = kwargs.pop('column_order', {})
        
        # Ahora llamamos a super().__init__() que internamente llamará a self.init_ui()
        super().__init__(parent, theme)
        
    def init_ui(self):
        """Inicializa la interfaz del módulo."""
        layout = QVBoxLayout(self)
        
        # Panel superior para búsqueda
        search_panel = QWidget()
        search_layout = QHBoxLayout(search_panel)
        
        self.table_selector = QComboBox()
        # Añadir solo las tablas principales, no las tablas FTS internas
        main_tables = ["songs", "artists", "albums", "genres", "lyrics", "scrobbles", "listens", "song_links"]
        self.table_selector.addItems(main_tables)
        self.table_selector.currentTextChanged.connect(self.change_table)
        search_layout.addWidget(QLabel("Tabla:"))
        search_layout.addWidget(self.table_selector)
        
        self.search_field = QComboBox()
        search_layout.addWidget(QLabel("Campo:"))
        search_layout.addWidget(self.search_field)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Término de búsqueda...")
        self.search_input.returnPressed.connect(self.search_database)
        search_layout.addWidget(self.search_input)
        
        search_button = QPushButton("Buscar")
        search_button.clicked.connect(self.search_database)
        search_layout.addWidget(search_button)
        
        layout.addWidget(search_panel)
        
        # El resto de la función sigue igual...
        # Pestañas para resultados y edición
        self.tab_widget = QTabWidget()
        
        # Pestaña de resultados
        self.results_tab = QWidget()
        results_layout = QVBoxLayout(self.results_tab)
        
        self.results_table = QTableWidget()
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.itemDoubleClicked.connect(self.load_item_for_edit)
        
        # Permitir mover y ordenar columnas
        self.results_table.horizontalHeader().setSectionsMovable(True)
        self.results_table.horizontalHeader().setSortIndicatorShown(True)
        self.results_table.horizontalHeader().sortIndicatorChanged.connect(self.sort_table)
        self.results_table.horizontalHeader().sectionMoved.connect(self.column_moved)
        
        results_layout.addWidget(self.results_table)
        
        # Botones debajo de la tabla de resultados
        buttons_layout = QHBoxLayout()
        
        edit_button = QPushButton("Editar Seleccionado")
        edit_button.clicked.connect(self.edit_selected_item)
        buttons_layout.addWidget(edit_button)
        
        new_button = QPushButton("Nuevo Item")
        new_button.clicked.connect(self.create_new_item)
        buttons_layout.addWidget(new_button)
        
        delete_button = QPushButton("Eliminar Seleccionado")
        delete_button.clicked.connect(self.delete_selected_item)
        buttons_layout.addWidget(delete_button)
        
        save_layout_button = QPushButton("Guardar Orden de Columnas")
        save_layout_button.clicked.connect(self.save_column_order_to_config)
        buttons_layout.addWidget(save_layout_button)
        
        results_layout.addLayout(buttons_layout)
        
        # Pestaña de edición
        self.edit_tab = QScrollArea()
        self.edit_tab.setWidgetResizable(True)
        self.edit_container = QWidget()
        self.edit_layout = QFormLayout(self.edit_container)
        self.edit_tab.setWidget(self.edit_container)
        
        # Botones de guardar y cancelar en pestaña de edición
        edit_buttons = QWidget()
        edit_buttons_layout = QHBoxLayout(edit_buttons)
        
        save_button = QPushButton("Guardar Cambios")
        save_button.clicked.connect(self.save_item)
        edit_buttons_layout.addWidget(save_button)
        
        cancel_button = QPushButton("Cancelar")
        cancel_button.clicked.connect(lambda: self.tab_widget.setCurrentIndex(0))
        edit_buttons_layout.addWidget(cancel_button)
        
        self.edit_layout.addRow(edit_buttons)
        
        # Añadir pestañas al widget principal
        self.tab_widget.addTab(self.results_tab, "Resultados de Búsqueda")
        self.tab_widget.addTab(self.edit_tab, "Editar Item")
        
        layout.addWidget(self.tab_widget)
        
        # Inicializar campos de búsqueda para la tabla seleccionada
        self.change_table(self.current_table)
    
    def apply_theme(self, theme_name=None):
        # Optional: Override if you need custom theming beyond base theme
        super().apply_theme(theme_name)
    
    def sort_table(self, column_index, order):
        """Ordena la tabla por la columna indicada."""
        self.results_table.sortItems(column_index, Qt.SortOrder(order))
    
    def column_moved(self, logical_index, old_visual_index, new_visual_index):
        """Guarda el nuevo orden de columnas cuando una columna es movida."""
        table_name = self.current_table
        if table_name not in self.column_order:
            self.column_order[table_name] = {}
        
        # Obtener todas las columnas y su posición visual actual
        visual_to_logical = {}
        logical_to_visual = {}
        header = self.results_table.horizontalHeader()
        
        for i in range(header.count()):
            logical = i
            visual = header.visualIndex(logical)
            visual_to_logical[visual] = logical
            logical_to_visual[logical] = visual
        
        # Guardar el mapeo visual a lógico
        self.column_order[table_name] = visual_to_logical
    
    def save_column_order_to_config(self):
        """Guarda el orden actual de columnas en la configuración."""
        if not hasattr(self, 'tab_manager') or not self.tab_manager:
            QMessageBox.warning(self, "Error", "No se puede guardar la configuración porque no hay acceso al gestor de pestañas.")
            return
        
        try:
            # Verificar si existe el módulo "Config Editor"
            if "Config Editor" in self.tab_manager.tabs:
                config_editor = self.tab_manager.tabs["Config Editor"]
                
                # Obtener la configuración actual
                current_config = config_editor.load_config()
                
                # Buscar la configuración de este módulo
                for module_config in current_config.get('modules', []):
                    if module_config.get('name') == 'DatabaseEditor':
                        # Actualizar o agregar el orden de columnas
                        if 'args' not in module_config:
                            module_config['args'] = {}
                        module_config['args']['column_order'] = self.column_order
                        break
                else:
                    # Si no se encontró la configuración del módulo, crear una nueva
                    if 'modules' not in current_config:
                        current_config['modules'] = []
                    
                    current_config['modules'].append({
                        'name': 'DatabaseEditor',
                        'path': 'modules/database_editor.py',
                        'args': {'column_order': self.column_order}
                    })
                
                # Guardar la configuración actualizada
                config_editor.update_config(current_config)
                config_editor.save_config()
                
                QMessageBox.information(self, "Éxito", "Orden de columnas guardado en la configuración.")
            else:
                # Si no existe el módulo Config Editor, usar el método de guardar configuración directamente
                self.save_column_order_directly()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al guardar orden de columnas: {e}")
            traceback.print_exc()
    
    def save_column_order_directly(self):
        """Guarda el orden de columnas directamente en el archivo de configuración."""
        try:
            config_path = getattr(self.tab_manager, 'config_path', 'config.json')
            
            # Cargar configuración existente
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
            else:
                config = {'modules': []}
            
            # Encontrar el módulo DatabaseEditor o crear uno nuevo
            found = False
            for module_config in config.get('modules', []):
                if module_config.get('name') == 'DatabaseEditor':
                    if 'args' not in module_config:
                        module_config['args'] = {}
                    module_config['args']['column_order'] = self.column_order
                    found = True
                    break
            
            if not found:
                config['modules'].append({
                    'name': 'DatabaseEditor',
                    'path': 'modules/database_editor.py',
                    'args': {'column_order': self.column_order}
                })
            
            # Guardar configuración
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=4)
            
            QMessageBox.information(self, "Éxito", "Orden de columnas guardado en la configuración.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al guardar orden de columnas directamente: {e}")
            traceback.print_exc()

    def get_table_structure(self, table_name: str) -> List[Tuple]:
        """Obtener la estructura de una tabla."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Verificar si la tabla existe antes de consultar su estructura
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            if not cursor.fetchone():
                print(f"La tabla {table_name} no existe en la base de datos")
                conn.close()
                return []
            
            # Escapar el nombre de la tabla para prevenir inyección SQL
            cursor.execute(f"PRAGMA table_info([{table_name}])")
            structure = cursor.fetchall()
            conn.close()
            
            # Filtrar tablas del sistema o tablas FTS internas
            if not structure:
                print(f"No se encontró estructura para la tabla {table_name}")
                return []
                
            # Filtrar columnas del sistema para tablas FTS
            if (table_name.endswith("_fts") or table_name.endswith("_config") or 
                table_name.endswith("_data") or table_name.endswith("_idx") or 
                table_name.endswith("_docsize")):
                return [col for col in structure if col[1] not in ('segid', 'term', 'pgno', 'k', 'v', 'block', 'sz')]
            
            return structure
        except sqlite3.Error as e:
            print(f"Error SQLite al obtener estructura de tabla {table_name}: {e}")
            traceback.print_exc()
            return []
        except Exception as e:
            print(f"Error general al obtener estructura de tabla {table_name}: {e}")
            traceback.print_exc()
            return []

    def get_table_structure(self, table_name: str) -> List[Tuple]:
        """Obtener la estructura de una tabla."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Verificar si la tabla existe antes de consultar su estructura
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            if not cursor.fetchone():
                print(f"La tabla {table_name} no existe en la base de datos")
                conn.close()
                return []
            
            # Obtener la estructura de la tabla
            cursor.execute(f"PRAGMA table_info(`{table_name}`)")
            structure = cursor.fetchall()
            conn.close()
            
            # Si no se encontró estructura, devolver lista vacía
            if not structure:
                print(f"No se encontró estructura para la tabla {table_name}")
                return []
                
            # Filtrar columnas del sistema para tablas FTS si es necesario
            if (table_name.endswith("_fts") or table_name.endswith("_config") or 
                table_name.endswith("_data") or table_name.endswith("_idx") or 
                table_name.endswith("_docsize")):
                return [col for col in structure if col[1] not in ('segid', 'term', 'pgno', 'k', 'v', 'block', 'sz')]
            
            return structure
        except sqlite3.Error as e:
            print(f"Error SQLite al obtener estructura de tabla {table_name}: {e}")
            traceback.print_exc()
            return []
        except Exception as e:
            print(f"Error general al obtener estructura de tabla {table_name}: {e}")
            traceback.print_exc()
            return []

    def change_table(self, table_name: str):
        """Cambiar la tabla actual y actualizar los campos de búsqueda."""
        if not table_name:
            return
            
        self.current_table = table_name
        self.search_field.clear()
        
        try:
            # Obtener la estructura de la tabla
            fields = self.get_table_structure(table_name)
            
            if not fields:
                QMessageBox.warning(self, "Error", f"No se pudo obtener la estructura de la tabla {table_name}")
                return
            
            # Añadir los campos a la lista desplegable
            for field in fields:
                if len(field) > 1:  # Asegurar que hay un nombre de campo disponible
                    self.search_field.addItem(field[1])  # field[1] es el nombre del campo
            
            # Añadir opción para buscar en todos los campos de texto si la tabla tiene al menos un campo
            if fields:
                self.search_field.addItem("Todos los campos de texto")
            
            # Comprobar si existe la tabla FTS correspondiente
            fts_table = f"{table_name}_fts"
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (fts_table,))
            has_fts = cursor.fetchone() is not None
            conn.close()
            
            # Añadir opción para búsqueda de texto completo solo si existe la tabla FTS
            if has_fts:
                self.search_field.addItem("Búsqueda de texto completo")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cambiar tabla: {str(e)}")
            traceback.print_exc()

    def search_related_item(self, field_name):
        """Abrir diálogo para buscar ítem relacionado."""
        # Determinar la tabla relacionada basada en el nombre del campo
        related_table = None
        if field_name == "artist_id":
            related_table = "artists"
        elif field_name == "album_id":
            related_table = "albums"
        elif field_name == "song_id" or field_name == "track_id":
            related_table = "songs"
        elif field_name == "lyrics_id":
            related_table = "lyrics"
        elif field_name == "genre_id":
            related_table = "genres"
        else:
            return
        
        # Determinar el campo a mostrar en la búsqueda
        display_field = "name"  # Por defecto, buscamos por nombre
        if related_table == "songs":
            display_field = "title"
        elif related_table == "lyrics":
            display_field = "track_id"  # Mostrar el ID de la canción asociada
        
        # Crear un diálogo para mostrar los resultados de búsqueda
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Buscar en {related_table}")
        dialog.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(dialog)
        
        # Campo de búsqueda
        search_layout = QHBoxLayout()
        search_input = QLineEdit()
        search_input.setPlaceholderText(f"Buscar por {display_field}...")
        search_button = QPushButton("Buscar")
        
        search_layout.addWidget(search_input)
        search_layout.addWidget(search_button)
        
        layout.addLayout(search_layout)
        
        # Tabla de resultados
        results_table = QTableWidget()
        results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        results_table.setAlternatingRowColors(True)
        layout.addWidget(results_table)
        
        # Botones de acción
        button_layout = QHBoxLayout()
        select_button = QPushButton("Seleccionar")
        cancel_button = QPushButton("Cancelar")
        
        button_layout.addWidget(select_button)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
        
        # Conectar señales
        cancel_button.clicked.connect(dialog.reject)
        
        # Función para realizar la búsqueda
        def perform_search():
            search_term = search_input.text()
            
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Obtener estructura de tabla
                cursor.execute(f"PRAGMA table_info({related_table})")
                columns = [info[1] for info in cursor.fetchall()]
                
                # Determinar columna para la búsqueda
                if display_field in columns:
                    search_column = display_field
                elif 'name' in columns:
                    search_column = 'name'
                elif 'title' in columns:
                    search_column = 'title'
                else:
                    search_column = columns[1]  # Primera columna después de id
                
                # Construir consulta
                query = f"SELECT * FROM {related_table} WHERE {search_column} LIKE ?"
                cursor.execute(query, [f"%{search_term}%"])
                results = cursor.fetchall()
                
                # Configurar tabla
                results_table.setRowCount(len(results))
                results_table.setColumnCount(len(columns))
                results_table.setHorizontalHeaderLabels(columns)
                
                # Rellenar datos
                for row, result in enumerate(results):
                    for col, value in enumerate(result):
                        item = QTableWidgetItem(str(value) if value is not None else "")
                        results_table.setItem(row, col, item)
                
                results_table.resizeColumnsToContents()
                
                # Mostrar columnas relevantes primero
                header = results_table.horizontalHeader()
                if 'id' in columns:
                    header.moveSection(header.visualIndex(columns.index('id')), 0)
                
                if search_column in columns and search_column != 'id':
                    header.moveSection(header.visualIndex(columns.index(search_column)), 1)
                
                conn.close()
                
            except Exception as e:
                QMessageBox.critical(dialog, "Error", f"Error al buscar: {e}")
        
        # Función para seleccionar un ítem
        def select_item():
            selected_rows = results_table.selectedItems()
            if not selected_rows:
                return
            
            row = selected_rows[0].row()
            item_id = results_table.item(row, 0).text()
            
            # Actualizar el campo con el ID seleccionado
            self.edit_widgets[field_name].setText(item_id)
            
            # Si el campo es lyrics_id, actualizar has_lyrics en songs
            if field_name == "lyrics_id" and self.current_table == "songs":
                if "has_lyrics" in self.edit_widgets:
                    self.edit_widgets["has_lyrics"].setChecked(True)
            
            dialog.accept()
        
        # Conectar señales restantes
        search_button.clicked.connect(perform_search)
        search_input.returnPressed.connect(perform_search)
        select_button.clicked.connect(select_item)
        results_table.itemDoubleClicked.connect(lambda: select_item())
        
        # Realizar búsqueda inicial con término vacío
        search_input.setText("")
        perform_search()
        
        # Mostrar diálogo
        dialog.exec()
        
        # Función para seleccionar un ítem
        def select_item():
            selected_rows = results_table.selectedItems()
            if not selected_rows:
                return
            
            row = selected_rows[0].row()
            item_id = results_table.item(row, 0).text()
            
            # Actualizar el campo con el ID seleccionado
            self.edit_widgets[field_name].setText(item_id)
            dialog.accept()
        
        # Conectar señales restantes
        search_button.clicked.connect(perform_search)
        search_input.returnPressed.connect(perform_search)
        select_button.clicked.connect(select_item)
        results_table.itemDoubleClicked.connect(lambda: select_item())
        
        # Realizar búsqueda inicial con término vacío
        search_input.setText("")
        perform_search()
        
        # Mostrar diálogo
        dialog.exec()


    def search_database(self):
        """Realizar búsqueda en la base de datos y mostrar resultados."""
        search_term = self.search_input.text()
        field = self.search_field.currentText()
        table = self.current_table
        
        if not search_term or not field or not table:
            QMessageBox.warning(self, "Campos incompletos", 
                                "Por favor complete todos los campos de búsqueda.")
            return
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Construir la consulta SQL
            if field == "Búsqueda de texto completo":
                # Usar la tabla FTS correspondiente
                fts_table = f"{table}_fts"
                
                # Verificar si existe la tabla FTS
                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{fts_table}'")
                if cursor.fetchone():
                    # Construir consulta FTS
                    query = f"SELECT {table}.* FROM {table} JOIN {fts_table} ON {table}.id = {fts_table}.id WHERE {fts_table} MATCH ?"
                    params = [search_term]
                else:
                    QMessageBox.warning(self, "Búsqueda FTS no disponible", 
                                        f"La búsqueda de texto completo no está disponible para la tabla {table}.")
                    return
            elif field == "Todos los campos de texto":
                # Obtener todos los campos de texto de la tabla
                cursor.execute(f"PRAGMA table_info({table})")
                all_fields = cursor.fetchall()
                text_fields = [f[1] for f in all_fields if f[2].upper() in ('TEXT', 'VARCHAR', 'CHAR', 'CLOB', 'STRING')]
                
                if not text_fields:
                    QMessageBox.warning(self, "No hay campos de texto", 
                                    f"La tabla {table} no tiene campos de texto para buscar.")
                    return
                    
                # Construir WHERE con todos los campos
                where_clauses = [f"{f} LIKE ?" for f in text_fields]
                query = f"SELECT * FROM {table} WHERE {' OR '.join(where_clauses)}"
                params = [f"%{search_term}%" for _ in text_fields]
            else:
                # Escapar el nombre del campo para prevenir inyección SQL
                query = f"SELECT * FROM {table} WHERE [{field}] LIKE ?"
                params = [f"%{search_term}%"]
            
            cursor.execute(query, params)
            self.search_results = cursor.fetchall()
            
            # Obtener los nombres de columnas
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [info[1] for info in cursor.fetchall()]
            
            # Configurar la tabla de resultados
            self.results_table.setRowCount(len(self.search_results))
            self.results_table.setColumnCount(len(columns))
            self.results_table.setHorizontalHeaderLabels(columns)
            
            # Rellenar los datos en la tabla
            for row, result in enumerate(self.search_results):
                for col, value in enumerate(result):
                    item = QTableWidgetItem(str(value) if value is not None else "")
                    self.results_table.setItem(row, col, item)
            
            # Aplicar orden de columnas guardado si existe para esta tabla
            if table in self.column_order and self.column_order[table]:
                header = self.results_table.horizontalHeader()
                visual_to_logical = self.column_order[table]
                
                # Establecer el orden visual de las columnas
                for visual, logical in visual_to_logical.items():
                    if isinstance(visual, str):
                        visual = int(visual)
                    if isinstance(logical, str):
                        logical = int(logical)
                    header.moveSection(header.visualIndex(logical), visual)
            
            self.results_table.resizeColumnsToContents()
            conn.close()
            
            # Cambiar a la pestaña de resultados
            self.tab_widget.setCurrentIndex(0)
            
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Error de Base de Datos", f"Error al realizar la búsqueda: {e}")
            traceback.print_exc()
    
    def edit_selected_item(self):
        """Cargar el ítem seleccionado para edición."""
        selected_rows = self.results_table.selectedItems()
        if not selected_rows:
            QMessageBox.warning(self, "Selección Requerida", "Por favor seleccione un ítem para editar.")
            return
        
        # Obtener el ID del ítem seleccionado (asumiendo que la primera columna es el ID)
        row = selected_rows[0].row()
        item_id = self.results_table.item(row, 0).text()
        self.load_item_for_edit(item_id=item_id)
    
    def load_item_for_edit(self, item=None, item_id=None):
        """Cargar un ítem para edición."""
        if item and not item_id:
            row = item.row()
            item_id = self.results_table.item(row, 0).text()
        
        self.current_item_id = item_id
        
        try:
            # Limpiar los widgets de edición actuales
            while self.edit_layout.rowCount() > 0:
                self.edit_layout.removeRow(0)
            
            self.edit_widgets = {}
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Obtener la estructura de la tabla
            cursor.execute(f"PRAGMA table_info({self.current_table})")
            columns = cursor.fetchall()
            
            # Obtener los datos del ítem
            cursor.execute(f"SELECT * FROM {self.current_table} WHERE id = ?", (item_id,))
            item_data = cursor.fetchone()
            
            if not item_data:
                raise ValueError(f"No se encontró ítem con ID {item_id}")
            
            # Crear widgets para cada campo
            for i, col in enumerate(columns):
                col_name = col[1]
                col_type = col[2].upper()
                col_value = item_data[i]
                
                # Crear el widget apropiado según el tipo de datos
                if col_name == "id":
                    # El ID no se edita, mostrar como texto
                    id_label = QLabel(str(col_value))
                    self.edit_layout.addRow(f"{col_name}:", id_label)
                    continue
                
                # Crear el widget apropiado según el tipo de campo
                if col_name in ["has_lyrics", "is_compilation"] or col_name.startswith("is_"):
                    # Campos booleanos
                    widget = QCheckBox()
                    if col_value is not None:
                        widget.setChecked(bool(int(col_value)))
                
                elif "TIMESTAMP" in col_type or col_name.endswith("_date") or col_name.endswith("_updated"):
                    widget = QDateTimeEdit()
                    widget.setCalendarPopup(True)
                    widget.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
                    if col_value:
                        try:
                            dt = QDateTime.fromString(str(col_value), "yyyy-MM-dd HH:mm:ss")
                            widget.setDateTime(dt)
                        except:
                            widget.setDateTime(QDateTime.currentDateTime())
                    else:
                        widget.setDateTime(QDateTime.currentDateTime())
                    
                elif "INTEGER" in col_type:
                    widget = QSpinBox()
                    widget.setRange(-9999999, 9999999)
                    if col_value is not None:
                        widget.setValue(int(col_value))
                
                elif "REAL" in col_type:
                    widget = QDoubleSpinBox()
                    widget.setRange(-9999999, 9999999)
                    widget.setDecimals(3)
                    if col_value is not None:
                        widget.setValue(float(col_value))
                
                # Manejo especial para las columnas de texto largo
                elif col_name in ["lyrics", "bio", "description"] or "wikipedia_content" in col_name:
                    widget = QTextEdit()
                    if col_value:
                        widget.setText(str(col_value))
                    
                    # Establecer una altura mínima para campos de texto largo
                    widget.setMinimumHeight(200)
                
                # Manejo especial para campos de fecha
                elif col_name == "date" or col_name == "year" or col_name == "album_year":
                    widget = QLineEdit()
                    if col_value:
                        widget.setText(str(col_value))
                    # Establecer placeholder para indicar formato esperado
                    widget.setPlaceholderText("YYYY o YYYY-MM-DD")
                
                # Manejo de los campos con paths y URLs
                elif col_name.endswith("_path") or col_name == "file_path" or col_name == "folder_path":
                    layout = QHBoxLayout()
                    widget = QLineEdit()
                    if col_value:
                        widget.setText(str(col_value))
                    
                    browse_button = QPushButton("...")
                    # Capturar el nombre del campo para el botón de búsqueda
                    browse_button.clicked.connect(lambda checked, field=col_name: self.browse_path(field))
                    
                    layout.addWidget(widget)
                    layout.addWidget(browse_button)
                    
                    container = QWidget()
                    container.setLayout(layout)
                    
                    self.edit_layout.addRow(f"{col_name}:", container)
                    self.edit_widgets[col_name] = widget
                    continue
                
                # Manejo especial para campos URLs
                elif "_url" in col_name:
                    widget = QLineEdit()
                    if col_value:
                        widget.setText(str(col_value))
                    # Establecer placeholder para indicar formato esperado
                    widget.setPlaceholderText("https://...")
                
                # Campo para IDs relacionados con opciones de búsqueda
                elif col_name.endswith("_id") and col_name != "id":
                    layout = QHBoxLayout()
                    widget = QLineEdit()
                    if col_value is not None:
                        widget.setText(str(col_value))
                    
                    # Botón para buscar elemento relacionado
                    search_button = QPushButton("Buscar")
                    search_button.clicked.connect(lambda checked, field=col_name: self.search_related_item(field))
                    
                    layout.addWidget(widget)
                    layout.addWidget(search_button)
                    
                    container = QWidget()
                    container.setLayout(layout)
                    
                    self.edit_layout.addRow(f"{col_name}:", container)
                    self.edit_widgets[col_name] = widget
                    continue
                
                else:
                    widget = QLineEdit()
                    if col_value is not None:
                        widget.setText(str(col_value))
                
                self.edit_layout.addRow(f"{col_name}:", widget)
                self.edit_widgets[col_name] = widget
            
            # Botones de guardar y cancelar
            button_layout = QHBoxLayout()
            save_button = QPushButton("Guardar Cambios")
            save_button.clicked.connect(self.save_item)
            
            cancel_button = QPushButton("Cancelar")
            cancel_button.clicked.connect(lambda: self.tab_widget.setCurrentIndex(0))
            
            button_layout.addWidget(save_button)
            button_layout.addWidget(cancel_button)
            
            button_container = QWidget()
            button_container.setLayout(button_layout)
            
            self.edit_layout.addRow(button_container)
            
            conn.close()
            
            # Cambiar a la pestaña de edición
            self.tab_widget.setCurrentIndex(1)
            
           
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar ítem para edición: {e}")
            traceback.print_exc()
    
    def browse_path(self, field_name):
        """Abrir diálogo para seleccionar archivo o directorio."""
        current_path = self.edit_widgets[field_name].text()
        
        if field_name == "file_path":
            # Para archivos de música
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Seleccionar archivo de música", 
                os.path.dirname(current_path) if current_path else "",
                "Archivos de música (*.mp3 *.flac *.wav *.ogg *.m4a *.aac);;Todos los archivos (*)"
            )
            if file_path:
                self.edit_widgets[field_name].setText(file_path)
        elif field_name == "album_art_path" or field_name == "album_art_path_denorm":
            # Para archivos de imagen
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Seleccionar portada de álbum", 
                os.path.dirname(current_path) if current_path else "",
                "Archivos de imagen (*.jpg *.jpeg *.png *.gif *.bmp);;Todos los archivos (*)"
            )
            if file_path:
                self.edit_widgets[field_name].setText(file_path)
        elif field_name == "folder_path":
            # Para directorios
            dir_path = QFileDialog.getExistingDirectory(
                self, "Seleccionar directorio", 
                current_path if current_path else ""
            )
            if dir_path:
                self.edit_widgets[field_name].setText(dir_path)
        else:
            # Para otros tipos de archivos
            file_path, _ = QFileDialog.getOpenFileName(
                self, f"Seleccionar {field_name}", 
                os.path.dirname(current_path) if current_path else ""
            )
            if file_path:
                self.edit_widgets[field_name].setText(file_path)
    
    def save_item(self):
        """Guardar los cambios del ítem y actualizar tablas relacionadas."""
        if not self.current_item_id:
            QMessageBox.warning(self, "Error", "No hay ítem para guardar.")
            return
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Obtener la estructura de la tabla
            cursor.execute(f"PRAGMA table_info({self.current_table})")
            columns = cursor.fetchall()
            
            # Guardar los valores antiguos para comparar después
            cursor.execute(f"SELECT * FROM {self.current_table} WHERE id = ?", (self.current_item_id,))
            old_values = {col[1]: val for col, val in zip(columns, cursor.fetchone())}
            
            # Construir la consulta UPDATE
            update_fields = []
            params = []
            new_values = {}
            
            for col in columns:
                col_name = col[1]
                col_type = col[2].upper()
                
                if col_name == "id":
                    continue  # No se actualiza el ID
                
                if col_name in self.edit_widgets:
                    widget = self.edit_widgets[col_name]
                    
                    if isinstance(widget, QLineEdit):
                        value = widget.text()
                    elif isinstance(widget, QTextEdit):
                        value = widget.toPlainText()
                    elif isinstance(widget, QDateTimeEdit):
                        value = widget.dateTime().toString("yyyy-MM-dd HH:mm:ss")
                    elif isinstance(widget, QSpinBox):
                        value = widget.value()
                    elif isinstance(widget, QDoubleSpinBox):
                        value = widget.value()
                    elif isinstance(widget, QCheckBox):
                        value = 1 if widget.isChecked() else 0
                    else:
                        value = str(widget.text()) if hasattr(widget, 'text') else None
                    
                    update_fields.append(f"{col_name} = ?")
                    params.append(value)
                    new_values[col_name] = value
            
            # Ejecutar la actualización principal
            query = f"UPDATE {self.current_table} SET {', '.join(update_fields)} WHERE id = ?"
            params.append(self.current_item_id)
            
            cursor.execute(query, params)
            
            # Actualizar tablas relacionadas
            self.update_related_tables(cursor, old_values, new_values)
            
            conn.commit()
            conn.close()
            
            QMessageBox.information(self, "Éxito", "Ítem actualizado con éxito y relaciones propagadas.")
            
            # Actualizar la búsqueda para reflejar los cambios
            self.search_database()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al guardar ítem: {e}")
            traceback.print_exc()

    


    def update_related_tables(self, cursor, old_values, new_values):
        """Actualizar tablas relacionadas basado en cambios en la tabla actual."""
        try:
            table = self.current_table
            item_id = self.current_item_id
            
            # Caso 1: Actualizar canciones cuando un artista cambia
            if table == "artists" and "name" in new_values and old_values["name"] != new_values["name"]:
                # Actualizar campos desnormalizados en songs
                cursor.execute(
                    "UPDATE songs SET artist = ? WHERE artist_id = ?", 
                    (new_values["name"], item_id)
                )
                logger.info(f"Actualizado artist en {cursor.rowcount} canciones")
                
                # Actualizar campos relacionados en albums si corresponde
                cursor.execute(
                    "UPDATE albums SET artist = ? WHERE artist_id = ?",
                    (new_values["name"], item_id)
                )
                logger.info(f"Actualizado artist en {cursor.rowcount} álbumes")
                
                # Actualizar en listens y scrobbles si existe
                try:
                    cursor.execute(
                        "UPDATE scrobbles SET artist_name = ? WHERE artist_id = ?",
                        (new_values["name"], item_id)
                    )
                    logger.info(f"Actualizado artist_name en {cursor.rowcount} scrobbles")
                except sqlite3.OperationalError:
                    # La columna podría no existir
                    pass
                
                try:
                    cursor.execute(
                        "UPDATE listens SET artist_name = ? WHERE artist_id = ?",
                        (new_values["name"], item_id)
                    )
                    logger.info(f"Actualizado artist_name en {cursor.rowcount} listens")
                except sqlite3.OperationalError:
                    pass
            
            # Caso 2: Actualizar canciones cuando un álbum cambia
            elif table == "albums" and "name" in new_values and old_values["name"] != new_values["name"]:
                cursor.execute(
                    "UPDATE songs SET album = ? WHERE album_id = ?",
                    (new_values["name"], item_id)
                )
                logger.info(f"Actualizado album en {cursor.rowcount} canciones")
                
                # Actualizar en listens y scrobbles si existe
                try:
                    cursor.execute(
                        "UPDATE scrobbles SET album_name = ? WHERE album_id = ?",
                        (new_values["name"], item_id)
                    )
                    logger.info(f"Actualizado album_name en {cursor.rowcount} scrobbles")
                except sqlite3.OperationalError:
                    pass
                
                try:
                    cursor.execute(
                        "UPDATE listens SET album_name = ? WHERE album_id = ?",
                        (new_values["name"], item_id)
                    )
                    logger.info(f"Actualizado album_name en {cursor.rowcount} listens")
                except sqlite3.OperationalError:
                    pass
            
            # Caso 3: Actualizar relaciones cuando una canción cambia
            elif table == "songs":
                changes = []
                
                # Actualizar título
                if "title" in new_values and old_values["title"] != new_values["title"]:
                    # Actualizar en lyrics
                    cursor.execute(
                        "UPDATE lyrics SET title = ? WHERE track_id = ?",
                        (new_values["title"], item_id)
                    )
                    logger.info(f"Actualizado title en {cursor.rowcount} registros de lyrics")
                    
                    # Actualizar en listens y scrobbles
                    try:
                        cursor.execute(
                            "UPDATE scrobbles SET track_name = ? WHERE track_id = ?",
                            (new_values["title"], item_id)
                        )
                    except sqlite3.OperationalError:
                        pass
                    
                    try:
                        cursor.execute(
                            "UPDATE listens SET track_name = ? WHERE track_id = ?",
                            (new_values["title"], item_id)
                        )
                    except sqlite3.OperationalError:
                        pass
                    
                    try:
                        cursor.execute(
                            "UPDATE song_links SET track_name_denorm = ? WHERE song_id = ?",
                            (new_values["title"], item_id)
                        )
                    except sqlite3.OperationalError:
                        pass
                
                # Verificar cambio de artista
                if "artist_id" in new_values and old_values["artist_id"] != new_values["artist_id"]:
                    # Obtener el nombre del nuevo artista
                    cursor.execute("SELECT name FROM artists WHERE id = ?", (new_values["artist_id"],))
                    artist_result = cursor.fetchone()
                    if artist_result:
                        artist_name = artist_result[0]
                        cursor.execute(
                            "UPDATE songs SET artist = ? WHERE id = ?",
                            (artist_name, item_id)
                        )
                        
                        # Actualizar en listens y scrobbles
                        try:
                            cursor.execute(
                                "UPDATE scrobbles SET artist_name = ?, artist_id = ? WHERE track_id = ?",
                                (artist_name, new_values["artist_id"], item_id)
                            )
                        except sqlite3.OperationalError:
                            pass
                        
                        try:
                            cursor.execute(
                                "UPDATE listens SET artist_name = ?, artist_id = ? WHERE track_id = ?",
                                (artist_name, new_values["artist_id"], item_id)
                            )
                        except sqlite3.OperationalError:
                            pass
                
                # Verificar cambio de álbum
                if "album_id" in new_values and old_values["album_id"] != new_values["album_id"]:
                    # Obtener el nombre del nuevo álbum
                    cursor.execute("SELECT name FROM albums WHERE id = ?", (new_values["album_id"],))
                    album_result = cursor.fetchone()
                    if album_result:
                        album_name = album_result[0]
                        cursor.execute(
                            "UPDATE songs SET album = ? WHERE id = ?",
                            (album_name, item_id)
                        )
                        
                        # Actualizar en listens y scrobbles
                        try:
                            cursor.execute(
                                "UPDATE scrobbles SET album_name = ?, album_id = ? WHERE track_id = ?",
                                (album_name, new_values["album_id"], item_id)
                            )
                        except sqlite3.OperationalError:
                            pass
                        
                        try:
                            cursor.execute(
                                "UPDATE listens SET album_name = ?, album_id = ? WHERE track_id = ?",
                                (album_name, new_values["album_id"], item_id)
                            )
                        except sqlite3.OperationalError:
                            pass
            
            # Caso 4: Actualizar relaciones cuando un género cambia
            elif table == "genres" and "name" in new_values and old_values["name"] != new_values["name"]:
                try:
                    cursor.execute(
                        "UPDATE songs SET genre = ? WHERE genre_id = ?",
                        (new_values["name"], item_id)
                    )
                    logger.info(f"Actualizado genre en {cursor.rowcount} canciones")
                except sqlite3.OperationalError:
                    # Es posible que la columna no exista
                    pass
                
                try:
                    cursor.execute(
                        "UPDATE albums SET genre = ? WHERE genre_id = ?",
                        (new_values["name"], item_id)
                    )
                    logger.info(f"Actualizado genre en {cursor.rowcount} álbumes")
                except sqlite3.OperationalError:
                    pass
        
        except Exception as e:
            logger.error(f"Error actualizando tablas relacionadas: {e}")
            traceback.print_exc()
            # No lanzamos la excepción para permitir que la actualización principal continúe



    def create_new_item(self):
        """Crear un nuevo ítem en la tabla actual."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Obtener la estructura de la tabla
            cursor.execute(f"PRAGMA table_info({self.current_table})")
            columns = cursor.fetchall()
            
            # Crear un nuevo registro vacío
            fields = [col[1] for col in columns if col[1] != 'id']
            placeholders = ['?' for _ in fields]
            
            # Valores por defecto
            default_values = []
            for col in columns:
                if col[1] == 'id':
                    continue
                
                col_type = col[2].upper()
                if 'TIMESTAMP' in col_type:
                    default_values.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                elif 'INTEGER' in col_type:
                    default_values.append(0)
                elif 'REAL' in col_type:
                    default_values.append(0.0)
                else:
                    default_values.append('')
            
            # Añadir valores por defecto específicos según la tabla
            if self.current_table == "songs":
                # Encontrar índices de campos relevantes
                title_idx = fields.index("title") if "title" in fields else -1
                if title_idx >= 0:
                    default_values[title_idx] = "Nueva Canción"
                    
                artist_name_idx = fields.index("artist") if "artist" in fields else -1
                if artist_name_idx >= 0:
                    default_values[artist_name_idx] = "Desconocido"
                    
                album_name_idx = fields.index("album") if "album" in fields else -1
                if album_name_idx >= 0:
                    default_values[album_name_idx] = "Desconocido"
            
            elif self.current_table == "artists":
                name_idx = fields.index("name") if "name" in fields else -1
                if name_idx >= 0:
                    default_values[name_idx] = "Nuevo Artista"
            
            elif self.current_table == "albums":
                name_idx = fields.index("name") if "name" in fields else -1
                if name_idx >= 0:
                    default_values[name_idx] = "Nuevo Álbum"
                    
                artist_name_idx = fields.index("artist") if "artist" in fields else -1
                if artist_name_idx >= 0:
                    default_values[artist_name_idx] = "Desconocido"
            
            query = f"INSERT INTO {self.current_table} ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
            cursor.execute(query, default_values)
            conn.commit()
            
            # Obtener el ID del nuevo ítem
            new_id = cursor.lastrowid
            conn.close()
            
            # Cargar el nuevo ítem para edición
            self.load_item_for_edit(item_id=new_id)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al crear nuevo ítem: {e}")
            traceback.print_exc()

    def delete_selected_item(self):
        """Eliminar el ítem seleccionado y manejar referencias."""
        selected_rows = self.results_table.selectedItems()
        if not selected_rows:
            QMessageBox.warning(self, "Selección Requerida", "Por favor seleccione un ítem para eliminar.")
            return
        
        # Obtener el ID del ítem seleccionado
        row = selected_rows[0].row()
        item_id = self.results_table.item(row, 0).text()
        
        # Confirmar eliminación
        reply = QMessageBox.question(
            self, 
            "Confirmar Eliminación",
            f"¿Está seguro que desea eliminar el ítem con ID {item_id}?\nEsto podría afectar a registros relacionados.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Verificar dependencias antes de eliminar
                can_delete, dependent_items = self.check_delete_dependencies(cursor, item_id)
                
                if not can_delete:
                    # Mostrar mensaje con elementos dependientes
                    deps_str = "\n".join([f"- {count} registros en {table}" for table, count in dependent_items.items()])
                    confirm_cascade = QMessageBox.question(
                        self,
                        "Referencias Encontradas",
                        f"Existen {sum(dependent_items.values())} registros que hacen referencia a este ítem:\n{deps_str}\n\n¿Desea eliminar de todas formas y establecer estas referencias en NULL?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )
                    
                    if confirm_cascade != QMessageBox.StandardButton.Yes:
                        conn.close()
                        return
                    
                    # Actualizar referencias a NULL
                    self.update_dependencies_before_delete(cursor, item_id)
                
                # Ejecutar la eliminación
                cursor.execute(f"DELETE FROM {self.current_table} WHERE id = ?", (item_id,))
                conn.commit()
                conn.close()
                
                QMessageBox.information(self, "Éxito", "Ítem eliminado con éxito.")
                
                # Actualizar la búsqueda para reflejar los cambios
                self.search_database()
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al eliminar ítem: {e}")
                traceback.print_exc()

    def check_delete_dependencies(self, cursor, item_id):
        """Verificar si hay elementos dependientes antes de eliminar."""
        table = self.current_table
        dependent_items = {}
        can_delete = True
        
        # Verificar dependencias según el tipo de tabla
        if table == "artists":
            # Verificar canciones con este artista
            cursor.execute("SELECT COUNT(*) FROM songs WHERE artist_id = ?", (item_id,))
            song_count = cursor.fetchone()[0]
            if song_count > 0:
                dependent_items["songs"] = song_count
                can_delete = False
            
            # Verificar álbumes con este artista
            cursor.execute("SELECT COUNT(*) FROM albums WHERE artist_id = ?", (item_id,))
            album_count = cursor.fetchone()[0]
            if album_count > 0:
                dependent_items["albums"] = album_count
                can_delete = False
        
        elif table == "albums":
            # Verificar canciones en este álbum
            cursor.execute("SELECT COUNT(*) FROM songs WHERE album_id = ?", (item_id,))
            song_count = cursor.fetchone()[0]
            if song_count > 0:
                dependent_items["songs"] = song_count
                can_delete = False
        
        elif table == "songs":
            # Verificar lyrics para esta canción
            cursor.execute("SELECT COUNT(*) FROM lyrics WHERE track_id = ?", (item_id,))
            lyrics_count = cursor.fetchone()[0]
            if lyrics_count > 0:
                dependent_items["lyrics"] = lyrics_count
                can_delete = False
            
            # Verificar referencias en listens o scrobbles
            try:
                cursor.execute("SELECT COUNT(*) FROM listens WHERE track_id = ?", (item_id,))
                listens_count = cursor.fetchone()[0]
                if listens_count > 0:
                    dependent_items["listens"] = listens_count
                    can_delete = False
            except sqlite3.OperationalError:
                pass
            
            try:
                cursor.execute("SELECT COUNT(*) FROM scrobbles WHERE track_id = ?", (item_id,))
                scrobbles_count = cursor.fetchone()[0]
                if scrobbles_count > 0:
                    dependent_items["scrobbles"] = scrobbles_count
                    can_delete = False
            except sqlite3.OperationalError:
                pass
            
            try:
                cursor.execute("SELECT COUNT(*) FROM song_links WHERE song_id = ?", (item_id,))
                links_count = cursor.fetchone()[0]
                if links_count > 0:
                    dependent_items["song_links"] = links_count
                    can_delete = False
            except sqlite3.OperationalError:
                pass
        
        elif table == "genres":
            # Verificar canciones con este género
            cursor.execute("SELECT COUNT(*) FROM songs WHERE genre_id = ?", (item_id,))
            song_count = cursor.fetchone()[0]
            if song_count > 0:
                dependent_items["songs"] = song_count
                can_delete = False
            
            # Verificar álbumes con este género
            try:
                cursor.execute("SELECT COUNT(*) FROM albums WHERE genre_id = ?", (item_id,))
                album_count = cursor.fetchone()[0]
                if album_count > 0:
                    dependent_items["albums"] = album_count
                    can_delete = False
            except sqlite3.OperationalError:
                pass
        
        return can_delete, dependent_items

    def update_dependencies_before_delete(self, cursor, item_id):
        """Actualizar referencias antes de eliminar un ítem."""
        table = self.current_table
        
        try:
            # Actualizar referencias según el tipo de tabla
            if table == "artists":
                # Establecer artist_id como NULL en songs
                cursor.execute("UPDATE songs SET artist_id = NULL, artist = 'Desconocido' WHERE artist_id = ?", (item_id,))
                logger.info(f"Actualizadas {cursor.rowcount} canciones con artista NULL")
                
                # Actualizar álbumes
                cursor.execute("UPDATE albums SET artist_id = NULL, artist = 'Desconocido' WHERE artist_id = ?", (item_id,))
                logger.info(f"Actualizados {cursor.rowcount} álbumes con artista NULL")
                
                # Actualizar scrobbles y listens si existen
                try:
                    cursor.execute("UPDATE scrobbles SET artist_id = NULL, artist_name = 'Desconocido' WHERE artist_id = ?", (item_id,))
                except sqlite3.OperationalError:
                    pass
                
                try:
                    cursor.execute("UPDATE listens SET artist_id = NULL, artist_name = 'Desconocido' WHERE artist_id = ?", (item_id,))
                except sqlite3.OperationalError:
                    pass
            
            elif table == "albums":
                # Establecer album_id como NULL en songs
                cursor.execute("UPDATE songs SET album_id = NULL, album = 'Desconocido' WHERE album_id = ?", (item_id,))
                logger.info(f"Actualizadas {cursor.rowcount} canciones con álbum NULL")
                
                # Actualizar referencias en scrobbles y listens
                try:
                    cursor.execute("UPDATE scrobbles SET album_id = NULL, album_name = 'Desconocido' WHERE album_id = ?", (item_id,))
                except sqlite3.OperationalError:
                    pass
                
                try:
                    cursor.execute("UPDATE listens SET album_id = NULL, album_name = 'Desconocido' WHERE album_id = ?", (item_id,))
                except sqlite3.OperationalError:
                    pass
            
            elif table == "songs":
                # Eliminar lyrics relacionadas
                cursor.execute("DELETE FROM lyrics WHERE track_id = ?", (item_id,))
                logger.info(f"Eliminados {cursor.rowcount} registros de lyrics relacionados")
                
                # Eliminar referencias en listens y scrobbles
                try:
                    cursor.execute("DELETE FROM listens WHERE track_id = ?", (item_id,))
                    logger.info(f"Eliminados {cursor.rowcount} registros de listens relacionados")
                except sqlite3.OperationalError:
                    pass
                
                try:
                    cursor.execute("DELETE FROM scrobbles WHERE track_id = ?", (item_id,))
                    logger.info(f"Eliminados {cursor.rowcount} registros de scrobbles relacionados")
                except sqlite3.OperationalError:
                    pass
                
                try:
                    cursor.execute("DELETE FROM song_links WHERE song_id = ?", (item_id,))
                    logger.info(f"Eliminados {cursor.rowcount} registros de song_links relacionados")
                except sqlite3.OperationalError:
                    pass
            
            elif table == "genres":
                # Actualizar canciones con este género
                cursor.execute("UPDATE songs SET genre_id = NULL, genre = 'Sin categoría' WHERE genre_id = ?", (item_id,))
                logger.info(f"Actualizadas {cursor.rowcount} canciones con género NULL")
                
                # Actualizar álbumes si existe la relación
                try:
                    cursor.execute("UPDATE albums SET genre_id = NULL, genre = 'Sin categoría' WHERE genre_id = ?", (item_id,))
                    logger.info(f"Actualizados {cursor.rowcount} álbumes con género NULL")
                except sqlite3.OperationalError:
                    pass
            
            elif table == "lyrics":
                # Actualizar canciones relacionadas
                cursor.execute("UPDATE songs SET has_lyrics = 0, lyrics_id = NULL WHERE lyrics_id = ?", (item_id,))
                logger.info(f"Actualizadas {cursor.rowcount} canciones sin lyrics")
        
        except Exception as e:
            logger.error(f"Error actualizando dependencias: {e}")
            traceback.print_exc()
            # No lanzamos la excepción para permitir que la eliminación continúe
        
    def cleanup(self):
        """Método llamado cuando se cierra el módulo."""
        # Guardar el orden de columnas antes de cerrar
        self.save_column_order_to_config()