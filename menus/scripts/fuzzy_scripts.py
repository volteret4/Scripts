#!/usr/bin/env python3
"""
Script Name: fuzzy_scripts.py
Description: Script manager with fuzzy search, database backend and theme support
Author: volteret4
Repository: https://github.com/volteret4/
License:
Notes:
    Dependencies: PyQt6, python3, fuzzywuzzy, pyyaml
"""

import os
import sys
import os
import sqlite3
import subprocess
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLineEdit, QPushButton, QListWidget,
                             QTextEdit, QLabel, QSplitter, QListWidgetItem,
                             QMessageBox, QTreeWidget, QTreeWidgetItem, QHeaderView,
                             QDialog, QDialogButtonBox, QStatusBar, QFrame)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, pyqtSlot
from PyQt6.QtGui import QKeySequence, QShortcut, QFont, QIcon
from datetime import datetime
from fuzzywuzzy import fuzz
import yaml


class TagEditDialog(QDialog):
    """Dialog para editar tags de un script"""

    def __init__(self, script_path: str, current_tags: List[str], all_tags: List[str], parent=None):
        super().__init__(parent)
        self.script_path = script_path
        self.current_tags = current_tags.copy()
        self.all_tags = all_tags
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle(f"Editar Tags - {Path(self.script_path).name}")
        self.setModal(True)
        self.resize(400, 300)

        layout = QVBoxLayout()

        # Información del archivo
        info_label = QLabel(f"Script: {Path(self.script_path).name}")
        layout.addWidget(info_label)

        # Editor de tags
        self.tags_edit = QTextEdit()
        self.tags_edit.setPlainText('\n'.join(self.current_tags))
        self.tags_edit.setPlaceholderText("Ingresa un tag por línea...")
        layout.addWidget(self.tags_edit)

        # Botones
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)

    def get_tags(self) -> List[str]:
        """Retorna la lista de tags editados"""
        text = self.tags_edit.toPlainText().strip()
        if not text:
            return []
        return [tag.strip() for tag in text.split('\n') if tag.strip()]


class CustomTreeWidgetItem(QTreeWidgetItem):
    """TreeWidgetItem personalizado para ordenación correcta"""

    def __lt__(self, other):
        column = self.treeWidget().sortColumn()

        # Ordenar por tipo y luego alfabéticamente
        self_data = self.data(0, Qt.ItemDataRole.UserRole)
        other_data = other.data(0, Qt.ItemDataRole.UserRole)

        if self_data and other_data:
            self_type = self_data.get('type', '')
            other_type = other_data.get('type', '')

            # Primero carpetas, luego scripts
            if self_type != other_type:
                if self_type == 'directory':
                    return True  # Carpetas primero
                elif other_type == 'directory':
                    return False

            # Dentro del mismo tipo, ordenar alfabéticamente
            self_text = self.text(0).lower()
            other_text = other.text(0).lower()

            # Quitar emojis para comparación
            import re
            self_clean = re.sub(r'[📁🐍📜⚙️🔧📄]\s*', '', self_text)
            other_clean = re.sub(r'[📁🐍📜⚙️🔧📄]\s*', '', other_text)

            return self_clean < other_clean

        return super().__lt__(other)


class ScriptManager(QMainWindow):
    """Ventana principal del gestor de scripts"""

    def __init__(self, theme_name: str = 'solarized-dark'):
        super().__init__()

        # Configuración
        self.script_dir = Path(__file__).parent
        self.db_path = self.script_dir / 'scripts.db'
        self.themes_file = self.script_dir / 'script_themes.yaml'
        self.theme_name = theme_name

        # Verificar que la base de datos existe
        if not self.db_path.exists():
            QMessageBox.warning(
                None,
                "Base de datos no encontrada",
                f"No se encontró la base de datos de scripts en {self.db_path}.\n"
                "Ejecuta primero: python script_indexer.py"
            )
            sys.exit(1)

        # Conexión a la base de datos
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row

        # Optimización SQLite
        self.conn.execute('PRAGMA synchronous = OFF')
        self.conn.execute('PRAGMA journal_mode = MEMORY')
        self.conn.execute('PRAGMA temp_store = MEMORY')
        self.conn.execute('PRAGMA cache_size = 10000')

        # Datos
        self.filtered_scripts = []
        self.theme_config = self.load_theme()
        self.current_script = None
        self.focus_cycle = []
        self.focus_index = 0
        self.focus_mode = 'search'  # 'search' o 'tree'

        # UI
        self.init_ui()
        self.setup_shortcuts()
        self.apply_theme()

        # Cargar scripts iniciales
        self.filter_scripts()

        # Establecer foco inicial en búsqueda
        self.search_bar.setFocus()

    def init_ui(self):
        """Inicializar la interfaz de usuario"""
        self.setWindowTitle("Script Manager")
        self.setGeometry(100, 100, 1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)

        # Barra de búsqueda y botones
        search_layout = QHBoxLayout()

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Buscar scripts... (nombre, descripción, tags)")
        self.search_bar.textChanged.connect(self.on_search_changed)
        self.search_bar.installEventFilter(self)

        self.launch_btn = QPushButton("Lanzar (Enter)")
        self.launch_btn.setObjectName("launch_btn")
        self.launch_btn.clicked.connect(self.launch_script)

        self.edit_btn = QPushButton("Editar (Ctrl+E)")
        self.edit_btn.setObjectName("edit_btn")
        self.edit_btn.clicked.connect(self.edit_script)

        self.tags_btn = QPushButton("Tags (Ctrl+T)")
        self.tags_btn.setObjectName("tags_btn")
        self.tags_btn.clicked.connect(self.edit_selected_tags)

        self.open_btn = QPushButton("Abrir (Ctrl+O)")
        self.open_btn.setObjectName("open_btn")
        self.open_btn.clicked.connect(self.open_folder)

        search_layout.addWidget(self.search_bar)
        search_layout.addWidget(self.launch_btn)
        search_layout.addWidget(self.edit_btn)
        search_layout.addWidget(self.tags_btn)
        search_layout.addWidget(self.open_btn)

        main_layout.addLayout(search_layout)

        # Barra de estado
        self.update_status()

        # Splitter principal (horizontal)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Panel izquierdo - Árbol de scripts
        self.script_tree = QTreeWidget()
        self.script_tree.setHeaderLabels(['Scripts'])
        self.script_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

        # Habilitar ordenación
        self.script_tree.setSortingEnabled(True)
        self.script_tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)

        self.script_tree.itemSelectionChanged.connect(self.on_script_selected)
        self.script_tree.installEventFilter(self)
        main_splitter.addWidget(self.script_tree)

        # Panel derecho
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Info del script
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)

        self.path_label = QLabel("Path: ")
        self.path_label.setObjectName("path_label")
        self.path_label.setWordWrap(True)

        self.desc_label = QLabel("Descripción: ")
        self.desc_label.setObjectName("desc_label")
        self.desc_label.setWordWrap(True)

        self.author_label = QLabel("Autor: ")
        self.author_label.setObjectName("author_label")

        self.tags_label = QLabel("Tags: ")
        self.tags_label.setObjectName("tags_label")
        self.tags_label.setWordWrap(True)

        info_layout.addWidget(self.path_label)
        info_layout.addWidget(self.desc_label)
        info_layout.addWidget(self.author_label)
        info_layout.addWidget(self.tags_label)
        info_widget.setMaximumHeight(120)

        # Contenido del script
        self.content_text = QTextEdit()
        self.content_text.setFont(QFont("Consolas", 10))
        self.content_text.installEventFilter(self)

        right_layout.addWidget(info_widget)
        right_layout.addWidget(self.content_text)

        main_splitter.addWidget(right_panel)
        main_splitter.setSizes([400, 800])

        main_layout.addWidget(main_splitter)

        # Configurar el ciclo de focus
        self.focus_cycle = [self.search_bar, self.script_tree, self.content_text]

        # Timer para búsqueda con delay
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.filter_scripts)

    def update_status(self):
        """Actualiza la barra de estado"""
        try:
            cursor = self.conn.execute('SELECT COUNT(*) FROM scripts')
            total_scripts = cursor.fetchone()[0]

            cursor = self.conn.execute('SELECT COUNT(DISTINCT script_id) FROM script_tags')
            tagged_scripts = cursor.fetchone()[0]

            search_text = self.search_bar.text().strip() if hasattr(self, 'search_bar') else ""
            if search_text:
                status_text = f"Mostrando {len(self.filtered_scripts)} scripts (de {total_scripts} total, {tagged_scripts} con tags)"
            else:
                status_text = f"Total: {total_scripts} scripts, {tagged_scripts} con tags"

            self.statusBar().showMessage(status_text)

        except Exception as e:
            self.statusBar().showMessage(f"Error: {e}")

    def get_script_tags(self, script_id: int) -> List[str]:
        """Obtiene los tags de un script"""
        cursor = self.conn.execute('''
            SELECT t.name FROM tags t
            JOIN script_tags st ON t.id = st.tag_id
            WHERE st.script_id = ?
            ORDER BY t.name
        ''', (script_id,))
        return [row[0] for row in cursor.fetchall()]

    def get_all_tags(self) -> List[str]:
        """Obtiene todos los tags disponibles"""
        cursor = self.conn.execute('SELECT name FROM tags ORDER BY name')
        return [row[0] for row in cursor.fetchall()]

    def filter_scripts(self):
        """Filtra los scripts según el texto de búsqueda"""
        search_text = self.search_bar.text().strip().lower() if hasattr(self, 'search_bar') else ""

        if not search_text:
            # Sin búsqueda: mostrar todos los scripts organizados por directorio
            cursor = self.conn.execute('''
                SELECT * FROM scripts
                ORDER BY directory, filename
                LIMIT 500
            ''')
        else:
            # Con búsqueda: buscar en todos los campos relevantes
            cursor = self.conn.execute('''
                SELECT s.*, GROUP_CONCAT(t.name, ',') as tags FROM scripts s
                LEFT JOIN script_tags st ON s.id = st.script_id
                LEFT JOIN tags t ON st.tag_id = t.id
                WHERE
                    LOWER(s.filename) LIKE ? OR
                    LOWER(s.description) LIKE ? OR
                    LOWER(s.author) LIKE ? OR
                    LOWER(s.notes) LIKE ? OR
                    EXISTS (
                        SELECT 1 FROM tags t2
                        JOIN script_tags st2 ON t2.id = st2.tag_id
                        WHERE st2.script_id = s.id AND LOWER(t2.name) LIKE ?
                    )
                GROUP BY s.id
                ORDER BY s.filename
                LIMIT 500
            ''', (f'%{search_text}%', f'%{search_text}%', f'%{search_text}%',
                  f'%{search_text}%', f'%{search_text}%'))

        # Convertir resultados
        self.filtered_scripts = []
        for row in cursor.fetchall():
            script_data = dict(row)
            self.filtered_scripts.append(script_data)

        self.update_tree_display()
        self.update_status()

    def update_tree_display(self):
        """Actualiza la visualización del árbol respetando la estructura real de carpetas"""
        self.script_tree.clear()

        # Deshabilitar ordenación temporalmente
        self.script_tree.setSortingEnabled(False)

        # Obtener el directorio home para hacer paths relativos
        home_path = Path.home()

        # Crear estructura de árbol jerárquica
        root_paths = {}  # path_relativo -> item

        # Primero, crear todos los scripts organizados por path completo
        scripts_by_path = {}
        for script_data in self.filtered_scripts:
            full_path = Path(script_data['directory'])

            # Hacer path relativo al HOME si está dentro de HOME
            try:
                if full_path.is_relative_to(home_path):
                    relative_path = full_path.relative_to(home_path)
                    # Si es directamente HOME, usar "~"
                    if str(relative_path) == '.':
                        display_path = Path('~')
                    else:
                        display_path = Path('~') / relative_path
                else:
                    # Si no está en HOME, usar path absoluto
                    display_path = full_path
            except (ValueError, AttributeError):
                # Fallback para versiones de Python < 3.9
                if str(full_path).startswith(str(home_path)):
                    relative_part = str(full_path)[len(str(home_path)):].lstrip('/')
                    if not relative_part:
                        display_path = Path('~')
                    else:
                        display_path = Path('~') / relative_part
                else:
                    display_path = full_path

            if display_path not in scripts_by_path:
                scripts_by_path[display_path] = []
            scripts_by_path[display_path].append(script_data)

        # Crear estructura jerárquica
        for display_path, scripts in scripts_by_path.items():
            # Crear todos los directorios padre si no existen
            current_path = display_path
            path_parts = []

            # Obtener todas las partes del path
            while current_path != current_path.parent:
                path_parts.append(current_path)
                current_path = current_path.parent
                # Parar en ~ para no seguir hacia arriba
                if current_path.name == '~' or str(current_path) == '~':
                    path_parts.append(current_path)
                    break
            path_parts.reverse()  # Del raíz hacia abajo

            # Crear jerarquía de carpetas
            parent_item = None
            for i, path_part in enumerate(path_parts):
                path_key = str(path_part)

                if path_key not in root_paths:
                    # Crear nuevo item de directorio
                    if parent_item is None:
                        dir_item = CustomTreeWidgetItem(self.script_tree)
                    else:
                        dir_item = CustomTreeWidgetItem(parent_item)

                    # Mostrar nombre apropiado
                    if str(path_part) == '~':
                        dir_name = "~"
                        tooltip_path = str(home_path)
                    else:
                        dir_name = path_part.name
                        # Construir tooltip con path real
                        if str(display_path).startswith('~'):
                            real_path = home_path / str(path_part)[2:] if len(str(path_part)) > 1 else home_path
                            tooltip_path = str(real_path)
                        else:
                            tooltip_path = str(path_part)

                    dir_item.setText(0, f"📁 {dir_name}")
                    dir_item.setToolTip(0, tooltip_path)
                    dir_item.setData(0, Qt.ItemDataRole.UserRole, {
                        'type': 'directory',
                        'path': tooltip_path,
                        'display_path': str(path_part)
                    })

                    root_paths[path_key] = dir_item
                    parent_item = dir_item
                else:
                    parent_item = root_paths[path_key]

            # Ahora agregar scripts a la carpeta final
            final_dir_item = root_paths[str(display_path)]
            for script_data in scripts:
                script_item = CustomTreeWidgetItem(final_dir_item)

                # Icono según extensión
                ext = script_data.get('extension', '').lower()
                if ext == '.py':
                    icon = "🐍"
                elif ext == '.sh':
                    icon = "📜"
                elif ext in ['.yml', '.yaml']:
                    icon = "⚙️"
                elif ext in ['.ini', '.env']:
                    icon = "🔧"
                else:
                    icon = "📄"

                script_item.setText(0, f"{icon} {script_data['filename']}")
                script_item.setToolTip(0, script_data['path'])  # Tooltip con path completo

                # Guardar datos del script
                script_data['type'] = 'script'
                script_item.setData(0, Qt.ItemDataRole.UserRole, script_data)

        # Expandir todo y reactivar ordenación
        self.script_tree.expandAll()
        self.script_tree.setSortingEnabled(True)

    def on_search_changed(self):
        """Maneja el cambio en el texto de búsqueda"""
        self.search_timer.stop()
        self.search_timer.start(300)  # 300ms delay

    def on_script_selected(self):
        """Maneja selección en el árbol"""
        current_item = self.script_tree.currentItem()
        if current_item:
            data = current_item.data(0, Qt.ItemDataRole.UserRole)
            if data and data.get('type') == 'script':
                self.current_script = data
                self.show_script_details(data)
            else:
                self.current_script = None
                self.clear_script_details()

    def clear_script_details(self):
        """Limpiar detalles cuando se selecciona una carpeta"""
        self.path_label.setText("Path: ")
        self.desc_label.setText("Descripción: ")
        self.author_label.setText("Autor: ")
        self.tags_label.setText("Tags: ")
        self.content_text.setPlainText("")

    def show_script_details(self, script):
        """Mostrar detalles del script seleccionado"""
        self.path_label.setText(f"Path: {script['path']}")
        self.desc_label.setText(f"Descripción: {script.get('description', 'Sin descripción')}")
        self.author_label.setText(f"Autor: {script.get('author', 'Sin autor')}")

        # Obtener y mostrar tags
        tags = self.get_script_tags(script['id'])
        self.tags_label.setText(f"Tags: {', '.join(tags) if tags else 'Sin tags'}")

        # Cargar contenido del script
        try:
            with open(script['path'], 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                self.content_text.setPlainText(content)
        except Exception as e:
            self.content_text.setPlainText(f"Error al cargar el archivo: {str(e)}")

    def launch_script(self):
        """Lanzar el script seleccionado usando tdrop + kitty"""
        if not self.current_script:
            QMessageBox.warning(self, "Advertencia", "No hay script seleccionado")
            return

        try:
            script_path = self.current_script['path']
            script_dir = str(Path(script_path).parent)

            # Determinar cómo ejecutar según la extensión
            ext = self.current_script.get('extension', '').lower()

            if ext == '.py':
                cmd = f"cd '{script_dir}' && python3 '{script_path}'"
            elif ext == '.sh':
                cmd = f"cd '{script_dir}' && bash '{script_path}'"
            elif ext in ['.yml', '.yaml']:
                # Para archivos YAML, abrirlos con editor por defecto
                cmd = f"cd '{script_dir}' && $EDITOR '{script_path}' || nano '{script_path}'"
            elif ext in ['.ini', '.env']:
                # Para archivos de configuración, abrirlos con editor
                cmd = f"cd '{script_dir}' && $EDITOR '{script_path}' || nano '{script_path}'"
            else:
                # Para otros tipos, intentar ejecutar directamente si es ejecutable
                if self.current_script.get('is_executable'):
                    cmd = f"cd '{script_dir}' && '{script_path}'"
                else:
                    # Si no es ejecutable, abrirlo con editor
                    cmd = f"cd '{script_dir}' && $EDITOR '{script_path}' || nano '{script_path}'"

            # Comando completo con pausa al final
            full_cmd = f"{cmd}; echo '\\nPresiona Enter para cerrar...'; read"

            # Obtener PANEL_HEIGHT del entorno, por defecto 0 si no está definido


            # Usar tdrop con kitty
            tdrop_cmd = [
                'tdrop', '-ma', '-w', '80%', '-h', '500', '-x', '200',  '-y', '250', '-s', 'dropdown',
                'kitty', '--', 'bash', '-c', full_cmd
            ]

            subprocess.Popen(tdrop_cmd)

        except FileNotFoundError:
            # Si tdrop no está disponible, usar fallback
            QMessageBox.warning(self, "Error",
                "tdrop no está instalado. Instálalo con:\n"
                "git clone https://github.com/noctuid/tdrop\n"
                "cd tdrop && sudo make install\n\n"
                "O usa un terminal normal.")

            # Fallback a kitty normal
            try:
                full_cmd = f"cd '{script_dir}' && {cmd}; echo '\\nPresiona Enter para cerrar...'; read"
                subprocess.Popen(['kitty', '--', 'bash', '-c', full_cmd])
            except FileNotFoundError:
                # Fallback final a gnome-terminal
                subprocess.Popen([
                    'gnome-terminal', '--', 'bash', '-c',
                    f"{cmd}; echo 'Presiona Enter para cerrar...'; read"
                ])

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al lanzar script: {str(e)}")

    def edit_script(self):
        """Editar el script seleccionado"""
        if not self.current_script:
            QMessageBox.warning(self, "Advertencia", "No hay script seleccionado")
            return

        try:
            # Intentar varios editores
            editors = ['codium', 'code', 'gedit', 'nano']
            script_path = self.current_script['path']

            for editor in editors:
                try:
                    subprocess.Popen([editor, script_path])
                    break
                except FileNotFoundError:
                    continue
            else:
                QMessageBox.warning(self, "Error",
                    "No se encontró ningún editor disponible (codium, code, gedit, nano)")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al abrir editor: {str(e)}")

    def edit_selected_tags(self):
        """Abre el editor de tags para el script seleccionado"""
        if not self.current_script:
            QMessageBox.information(self, "Info", "Selecciona un script primero")
            return

        script_id = self.current_script['id']
        current_tags = self.get_script_tags(script_id)
        all_tags = self.get_all_tags()

        dialog = TagEditDialog(self.current_script['path'], current_tags, all_tags, self)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_tags = dialog.get_tags()
            self.update_script_tags(script_id, new_tags)
            self.filter_scripts()  # Actualizar vista
            self.show_script_details(self.current_script)  # Actualizar detalles

    def update_script_tags(self, script_id: int, new_tags: List[str]):
        """Actualiza los tags de un script en la base de datos"""
        try:
            # Eliminar tags existentes
            self.conn.execute('DELETE FROM script_tags WHERE script_id = ?', (script_id,))

            # Agregar nuevos tags
            for tag_name in new_tags:
                if not tag_name.strip():
                    continue

                # Crear tag si no existe
                self.conn.execute(
                    'INSERT OR IGNORE INTO tags (name) VALUES (?)',
                    (tag_name.strip(),)
                )

                # Obtener ID del tag
                cursor = self.conn.execute(
                    'SELECT id FROM tags WHERE name = ?',
                    (tag_name.strip(),)
                )
                tag_id = cursor.fetchone()[0]

                # Crear relación script-tag
                self.conn.execute(
                    'INSERT INTO script_tags (script_id, tag_id) VALUES (?, ?)',
                    (script_id, tag_id)
                )

            self.conn.commit()
            QMessageBox.information(self, "Éxito", "Tags actualizados correctamente")

        except Exception as e:
            self.conn.rollback()
            QMessageBox.warning(self, "Error", f"No se pudieron actualizar los tags: {e}")

    def open_folder(self):
        """Abrir la carpeta que contiene el script con Thunar"""
        if not self.current_script:
            QMessageBox.warning(self, "Advertencia", "No hay script seleccionado")
            return

        try:
            folder_path = Path(self.current_script['path']).parent

            # Intentar Thunar primero, luego otros gestores de archivos
            file_managers = ['thunar', 'nautilus', 'dolphin', 'pcmanfm', 'xdg-open']

            for manager in file_managers:
                try:
                    subprocess.Popen([manager, str(folder_path)])
                    return
                except FileNotFoundError:
                    continue

            # Si no se encuentra ningún gestor, mostrar error
            QMessageBox.warning(self, "Error",
                "No se encontró ningún gestor de archivos disponible\n"
                "(thunar, nautilus, dolphin, pcmanfm)")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al abrir carpeta: {str(e)}")

    def load_theme(self) -> Dict:
        """Carga la configuración del tema"""
        if not self.themes_file.exists():
            self.create_default_themes()

        try:
            with open(self.themes_file, 'r', encoding='utf-8') as f:
                themes = yaml.safe_load(f)
                return themes.get(self.theme_name, themes.get('solarized-dark', {}))
        except (yaml.YAMLError, IOError):
            return self.get_default_theme()

    def get_default_theme(self) -> Dict:
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
        # Usar los mismos temas que icon_browser
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
            },
            'rose-pine': {
                'bg_color': '#191724',
                'text_color': '#e0def4',
                'accent_color': '#c4a7e7',
                'widget_bg': '#1f1d2e',
                'border_color': '#26233a',
                'search_bg': '#1f1d2e',
                'search_border': '#26233a'
            }
        }

        try:
            with open(self.themes_file, 'w', encoding='utf-8') as f:
                yaml.dump(themes, f, default_flow_style=False, allow_unicode=True)
        except IOError:
            pass

    def apply_theme(self):
        """Aplica el tema a la interfaz"""
        style = f"""
            QMainWindow {{
                background-color: {self.theme_config['bg_color']};
                color: {self.theme_config['text_color']};
            }}
            QWidget {{
                background-color: {self.theme_config['bg_color']};
                color: {self.theme_config['text_color']};
            }}
            QLineEdit {{
                background-color: {self.theme_config['search_bg']};
                color: {self.theme_config['text_color']};
                border: 2px solid {self.theme_config['search_border']};
                border-radius: 4px;
                padding: 8px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border-color: {self.theme_config['accent_color']};
            }}
            QPushButton {{
                background-color: {self.theme_config['widget_bg']};
                border: 2px solid {self.theme_config['border_color']};
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
                color: {self.theme_config['text_color']};
                min-width: 100px;
            }}
            QPushButton:hover {{
                background-color: {self.theme_config['accent_color']};
                border-color: {self.theme_config['accent_color']};
                color: {self.theme_config['bg_color']};
            }}
            QPushButton#launch_btn {{
                background-color: {self.theme_config['accent_color']};
                color: {self.theme_config['bg_color']};
            }}
            QPushButton#launch_btn:hover {{
                background-color: {self.theme_config['text_color']};
                color: {self.theme_config['bg_color']};
            }}
            QPushButton#tags_btn {{
                background-color: {self.theme_config['widget_bg']};
                border-color: {self.theme_config['accent_color']};
                color: {self.theme_config['accent_color']};
            }}
            QPushButton#tags_btn:hover {{
                background-color: {self.theme_config['accent_color']};
                color: {self.theme_config['bg_color']};
            }}
            QPushButton#open_btn {{
                background-color: {self.theme_config['widget_bg']};
                border-color: {self.theme_config['border_color']};
            }}
            QPushButton#open_btn:hover {{
                background-color: {self.theme_config['border_color']};
                color: {self.theme_config['bg_color']};
            }}
            QTreeWidget {{
                background-color: {self.theme_config['widget_bg']};
                border: 2px solid {self.theme_config['border_color']};
                border-radius: 4px;
                padding: 4px;
                font-size: 13px;
                color: {self.theme_config['text_color']};
                outline: none;
            }}
            QTreeWidget::item {{
                padding: 6px 8px;
                border-radius: 4px;
                margin: 1px 0px;
            }}
            QTreeWidget::item:selected {{
                background-color: {self.theme_config['accent_color']};
                color: {self.theme_config['bg_color']};
                font-weight: bold;
            }}
            QTreeWidget::item:hover {{
                background-color: {self.theme_config['border_color']};
            }}
            QTreeWidget:focus {{
                border-color: {self.theme_config['accent_color']};
            }}
            QTextEdit {{
                background-color: {self.theme_config['widget_bg']};
                border: 2px solid {self.theme_config['border_color']};
                border-radius: 4px;
                padding: 8px;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                font-size: 11px;
                color: {self.theme_config['text_color']};
            }}
            QTextEdit:focus {{
                border-color: {self.theme_config['accent_color']};
            }}
            QLabel {{
                color: {self.theme_config['text_color']};
                font-size: 13px;
                padding: 4px;
                background-color: transparent;
            }}
            QLabel#path_label {{
                color: {self.theme_config['accent_color']};
                font-weight: bold;
            }}
            QLabel#desc_label {{
                font-style: italic;
            }}
            QSplitter::handle {{
                background-color: {self.theme_config['border_color']};
                width: 3px;
                margin: 2px;
                border-radius: 1px;
            }}
            QSplitter::handle:hover {{
                background-color: {self.theme_config['accent_color']};
            }}
            QHeaderView::section {{
                background-color: {self.theme_config['widget_bg']};
                color: {self.theme_config['text_color']};
                padding: 8px;
                border: 1px solid {self.theme_config['border_color']};
                font-weight: bold;
            }}
            QHeaderView::section:hover {{
                background-color: {self.theme_config['accent_color']};
                color: {self.theme_config['bg_color']};
            }}
            /* Scrollbars */
            QScrollBar:vertical {{
                background-color: {self.theme_config['widget_bg']};
                width: 12px;
                border-radius: 6px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {self.theme_config['border_color']};
                border-radius: 6px;
                min-height: 20px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {self.theme_config['accent_color']};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar:horizontal {{
                background-color: {self.theme_config['widget_bg']};
                height: 12px;
                border-radius: 6px;
                margin: 0px;
            }}
            QScrollBar::handle:horizontal {{
                background-color: {self.theme_config['border_color']};
                border-radius: 6px;
                min-width: 20px;
                margin: 2px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background-color: {self.theme_config['accent_color']};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
        """
        self.setStyleSheet(style)

    def setup_shortcuts(self):
        """Configurar atajos de teclado"""
        # Enter para lanzar script
        enter_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Return), self)
        enter_shortcut.activated.connect(self.launch_script)

        # Ctrl+E para editar
        edit_shortcut = QShortcut(QKeySequence("Ctrl+E"), self)
        edit_shortcut.activated.connect(self.edit_script)

        # Ctrl+T para editar tags
        tags_shortcut = QShortcut(QKeySequence("Ctrl+T"), self)
        tags_shortcut.activated.connect(self.edit_selected_tags)

        # Ctrl+O para abrir carpeta
        folder_shortcut = QShortcut(QKeySequence("Ctrl+O"), self)
        folder_shortcut.activated.connect(self.open_folder)

        # Ctrl+F para focus en búsqueda
        search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        search_shortcut.activated.connect(lambda: self.search_bar.setFocus())

        # Tab para ciclo de focus
        tab_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Tab), self)
        tab_shortcut.activated.connect(self.cycle_focus)

        # Escape para cerrar
        esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        esc_shortcut.activated.connect(self.close)

    def cycle_focus(self):
        """Ciclar el focus entre elementos"""
        self.focus_index = (self.focus_index + 1) % len(self.focus_cycle)
        self.focus_cycle[self.focus_index].setFocus()

    def eventFilter(self, obj, event):
        """Filtro de eventos para manejar navegación con teclado"""
        from PyQt6.QtCore import QEvent
        from PyQt6.QtGui import QKeyEvent

        if event.type() == QEvent.Type.KeyPress:
            key = event.key()

            # TAB: cambiar entre búsqueda y árbol
            if key == Qt.Key.Key_Tab:
                if obj == self.search_bar:
                    self.script_tree.setFocus()
                    return True
                elif obj == self.script_tree:
                    self.content_text.setFocus()
                    return True
                elif obj == self.content_text:
                    self.search_bar.setFocus()
                    return True

            # Si estamos en búsqueda y presionamos Enter
            if obj == self.search_bar and (key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter):
                if self.script_tree.topLevelItemCount() > 0:
                    self.script_tree.setFocus()
                    # Seleccionar primer script encontrado
                    for i in range(self.script_tree.topLevelItemCount()):
                        top_item = self.script_tree.topLevelItem(i)
                        if top_item.childCount() > 0:
                            first_script = top_item.child(0)
                            self.script_tree.setCurrentItem(first_script)
                            break
                return True

        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        """Maneja el cierre de la aplicación"""
        if hasattr(self, 'conn'):
            self.conn.close()
        event.accept()


def find_app_icon() -> Optional[QIcon]:
    """Busca el icono de la aplicación"""
    icon_names = ['script-manager', 'text-x-script', 'application-x-executable']

    for name in icon_names:
        icon = QIcon.fromTheme(name)
        if not icon.isNull():
            return icon

    return QIcon.fromTheme("text-x-generic")


def main():
    parser = argparse.ArgumentParser(description='Script Manager - Gestor de scripts con búsqueda difusa')
    parser.add_argument('--theme', default='solarized-dark',
                       choices=['solarized-dark', 'tokyo-night', 'catppucin',
                               'gruvbox', 'kanagawa', 'forest-dark', 'neon', 'rose-pine'],
                       help='Tema de color a usar')

    args = parser.parse_args()

    app = QApplication(sys.argv)

    # Configurar icono de la aplicación
    app_icon = find_app_icon()
    if app_icon:
        app.setWindowIcon(app_icon)

    script_manager = ScriptManager(args.theme)
    script_manager.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
