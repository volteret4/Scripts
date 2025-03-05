import os
import sqlite3
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, 
                           QLineEdit, QPushButton, QComboBox, QTableWidget, 
                           QTableWidgetItem, QLabel, QFormLayout, QMessageBox,
                           QTextEdit, QDateTimeEdit, QSpinBox, QDoubleSpinBox,
                           QCheckBox, QDialog, QFileDialog, QScrollArea)
from PyQt6.QtCore import Qt, pyqtSignal, QDateTime

from base_module import BaseModule, THEMES

class DatabaseEditor(BaseModule):
    """Módulo para buscar y editar elementos en la base de datos de música."""
    
    def __init__(self, db_path: str = "music_database.db", parent=None, theme='Tokyo Night', **kwargs):
        # Definir atributos antes de llamar a super().__init__()
        self.db_path = db_path
        self.current_table = "songs"
        self.current_item_id = None
        self.edit_widgets = {}
        self.search_results = []

        self.available_themes = kwargs.pop('temas', [])
        self.selected_theme = kwargs.pop('tema_seleccionado', theme)
        
        # Ahora llamamos a super().__init__() que internamente llamará a self.init_ui()
        super().__init__(parent, theme)
        
    def init_ui(self):
        """Inicializa la interfaz del módulo."""
        layout = QVBoxLayout(self)
        
        # Panel superior para búsqueda
        search_panel = QWidget()
        search_layout = QHBoxLayout(search_panel)
        
        self.table_selector = QComboBox()
        self.table_selector.addItems(["songs", "artists", "albums", "genres", "lyrics"])
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


    def change_table(self, table_name: str):
        """Cambiar la tabla actual y actualizar los campos de búsqueda."""
        self.current_table = table_name
        self.search_field.clear()
        
        # Obtener la estructura de la tabla
        fields = self.get_table_structure(table_name)
        
        # Añadir los campos a la lista desplegable
        for field in fields:
            self.search_field.addItem(field[1])  # field[1] es el nombre del campo
        
        # Añadir opción para buscar en todos los campos de texto
        self.search_field.addItem("Todos los campos de texto")
    
    def get_table_structure(self, table_name: str) -> List[Tuple]:
        """Obtener la estructura de una tabla."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name})")
            structure = cursor.fetchall()
            conn.close()
            return structure
        except sqlite3.Error as e:
            print(f"Error al obtener estructura de tabla: {e}")
            return []
    
    def search_database(self):
        """Realizar búsqueda en la base de datos y mostrar resultados."""
        search_term = self.search_input.text()
        field = self.search_field.currentText()
        table = self.current_table
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Construir la consulta SQL
            if field == "Todos los campos de texto":
                # Obtener todos los campos de texto de la tabla
                cursor.execute(f"PRAGMA table_info({table})")
                fields = [f[1] for f in cursor.fetchall() if f[2].upper() == 'TEXT']
                
                # Construir WHERE con todos los campos
                where_clauses = [f"{f} LIKE ?" for f in fields]
                query = f"SELECT * FROM {table} WHERE {' OR '.join(where_clauses)}"
                params = [f"%{search_term}%" for _ in fields]
            else:
                query = f"SELECT * FROM {table} WHERE {field} LIKE ?"
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
            
            self.results_table.resizeColumnsToContents()
            conn.close()
            
            # Cambiar a la pestaña de resultados
            self.tab_widget.setCurrentIndex(0)
            
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Error de Base de Datos", f"Error al realizar la búsqueda: {e}")
    
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
                
                if "TIMESTAMP" in col_type:
                    widget = QDateTimeEdit()
                    widget.setCalendarPopup(True)
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
                
                elif col_name == "lyrics" or col_name == "bio" or "wikipedia_content" in col_name:
                    widget = QTextEdit()
                    if col_value:
                        widget.setText(str(col_value))
                
                elif col_name.endswith("_path") or "_url" in col_name:
                    layout = QHBoxLayout()
                    widget = QLineEdit()
                    if col_value:
                        widget.setText(str(col_value))
                    
                    browse_button = QPushButton("...")
                    browse_button.clicked.connect(lambda checked, field=col_name: self.browse_path(field))
                    
                    layout.addWidget(widget)
                    layout.addWidget(browse_button)
                    
                    container = QWidget()
                    container.setLayout(layout)
                    
                    self.edit_layout.addRow(f"{col_name}:", container)
                    self.edit_widgets[col_name] = widget
                    continue
                
                else:
                    widget = QLineEdit()
                    if col_value:
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
            import traceback
            traceback.print_exc()
    
    def browse_path(self, field_name):
        """Abrir diálogo para seleccionar archivo o directorio."""
        current_path = self.edit_widgets[field_name].text()
        
        if "file_path" in field_name or "album_art_path" in field_name:
            file_path, _ = QFileDialog.getOpenFileName(
                self, f"Seleccionar {field_name}", 
                os.path.dirname(current_path) if current_path else "",
            )
            if file_path:
                self.edit_widgets[field_name].setText(file_path)
        else:
            # Para URLs, no se hace nada ya que no hay diálogo para URLs
            pass
    
    def save_item(self):
        """Guardar los cambios del ítem."""
        if not self.current_item_id:
            QMessageBox.warning(self, "Error", "No hay ítem para guardar.")
            return
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Obtener la estructura de la tabla
            cursor.execute(f"PRAGMA table_info({self.current_table})")
            columns = cursor.fetchall()
            
            # Construir la consulta UPDATE
            update_fields = []
            params = []
            
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
                    else:
                        value = str(widget.text()) if hasattr(widget, 'text') else None
                    
                    update_fields.append(f"{col_name} = ?")
                    params.append(value)
            
            query = f"UPDATE {self.current_table} SET {', '.join(update_fields)} WHERE id = ?"
            params.append(self.current_item_id)
            
            cursor.execute(query, params)
            conn.commit()
            conn.close()
            
            QMessageBox.information(self, "Éxito", "Ítem actualizado con éxito.")
            
            # Actualizar la búsqueda para reflejar los cambios
            self.search_database()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al guardar ítem: {e}")
            import traceback
            traceback.print_exc()
    
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
            import traceback
            traceback.print_exc()
    
    def delete_selected_item(self):
        """Eliminar el ítem seleccionado."""
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
            f"¿Está seguro que desea eliminar el ítem con ID {item_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute(f"DELETE FROM {self.current_table} WHERE id = ?", (item_id,))
                conn.commit()
                conn.close()
                
                QMessageBox.information(self, "Éxito", "Ítem eliminado con éxito.")
                
                # Actualizar la búsqueda para reflejar los cambios
                self.search_database()
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al eliminar ítem: {e}")
                import traceback
                traceback.print_exc()
    
    def cleanup(self):
        """Método llamado cuando se cierra el módulo."""
        # Aquí se puede realizar cualquier limpieza necesaria
        pass