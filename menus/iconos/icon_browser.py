#!/usr/bin/env python3
"""
Icon Browser - Navegador de iconos con búsqueda difusa y sistema de tags
"""

import sys
import os
import sqlite3
import shutil
import argparse
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QHBoxLayout, QLineEdit, QScrollArea, QLabel,
                            QPushButton, QDialog, QTextEdit, QDialogButtonBox,
                            QGridLayout, QFrame, QMessageBox, QProgressBar,
                            QStatusBar)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui import QPixmap, QIcon, QKeySequence, QShortcut, QFont
from fuzzywuzzy import fuzz
import yaml


class IconItem(QFrame):
    """Widget individual para mostrar un icono"""
    clicked = pyqtSignal(str)  # Emite la ruta del archivo

    def __init__(self, icon_data: Dict, tags: List[str] = None):
        super().__init__()
        self.icon_path = icon_data['path']
        self.icon_data = icon_data
        self.tags = tags or []
        self.is_selected = False
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Imagen del icono
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFixedSize(64, 64)
        self.icon_label.setScaledContents(True)

        # Cargar imagen
        pixmap = QPixmap(self.icon_path)
        if not pixmap.isNull():
            self.icon_label.setPixmap(pixmap)
        else:
            self.icon_label.setText("No img")

        # Nombre del archivo
        filename = self.icon_data['filename']
        self.name_label = QLabel(filename)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setWordWrap(True)

        layout.addWidget(self.icon_label)
        layout.addWidget(self.name_label)
        self.setLayout(layout)

        # Estilo base
        self.setFrameStyle(QFrame.Shape.Box)
        self.setFixedSize(80, 100)

        # Tooltip mejorado
        tooltip_parts = []
        if self.tags:
            tooltip_parts.append(f"Tags: {', '.join(self.tags)}")

        if self.icon_data.get('width') and self.icon_data.get('height'):
            tooltip_parts.append(f"Tamaño: {self.icon_data['width']}x{self.icon_data['height']}")

        if self.icon_data.get('format'):
            tooltip_parts.append(f"Formato: {self.icon_data['format']}")

        tooltip_parts.append(f"Archivo: {filename}")
        tooltip_parts.append(f"Ruta: {self.icon_path}")

        self.setToolTip('\n'.join(tooltip_parts))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.icon_path)
        super().mousePressEvent(event)

    def apply_theme(self, theme_config: Dict):
        """Aplica el tema al widget"""
        bg_color = theme_config.get('widget_bg', '#2e2e2e')
        text_color = theme_config.get('text_color', '#ffffff')
        border_color = theme_config.get('border_color', '#555555')
        accent_color = theme_config.get('accent_color', '#0078d4')

        if self.is_selected:
            border_style = f"2px solid {accent_color}"
            bg_color = theme_config.get('selected_bg', bg_color)
        else:
            border_style = f"1px solid {border_color}"

        self.setStyleSheet(f"""
            IconItem {{
                background-color: {bg_color};
                border: {border_style};
                border-radius: 4px;
            }}
            IconItem:hover {{
                border: 2px solid {accent_color};
            }}
            QLabel {{
                color: {text_color};
                background: transparent;
                border: none;
            }}
        """)

    def set_selected(self, selected: bool, theme_config: Dict):
        """Marca o desmarca el icono como seleccionado"""
        self.is_selected = selected
        self.apply_theme(theme_config)


class TagEditDialog(QDialog):
    """Dialog para editar tags de un icono"""

    def __init__(self, icon_path: str, current_tags: List[str], all_tags: List[str], parent=None):
        super().__init__(parent)
        self.icon_path = icon_path
        self.current_tags = current_tags.copy()
        self.all_tags = all_tags
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle(f"Editar Tags - {Path(self.icon_path).name}")
        self.setModal(True)
        self.resize(400, 300)

        layout = QVBoxLayout()

        # Información del archivo
        info_label = QLabel(f"Archivo: {Path(self.icon_path).name}")
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


class IconBrowser(QMainWindow):
    """Ventana principal del navegador de iconos"""

    def __init__(self, theme_name: str = 'solarized-dark', clipboard_method: str = 'auto'):
        super().__init__()

        # Configuración
        self.script_dir = Path(__file__).parent
        self.db_path = self.script_dir / 'icons.db'
        self.themes_file = self.script_dir / 'themes.yaml'
        self.config_file = self.script_dir / 'config.yaml'
        self.theme_name = theme_name
        self.clipboard_method = clipboard_method

        # Verificar que la base de datos existe
        if not self.db_path.exists():
            QMessageBox.warning(
                None,
                "Base de datos no encontrada",
                f"No se encontró la base de datos de iconos en {self.db_path}.\n"
                "Ejecuta primero: python index_icons.py"
            )
            sys.exit(1)

        # Conexión a la base de datos
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row  # Para acceso por nombre de columna

        # OPTIMIZACIÓN: Configurar SQLite para mayor velocidad
        self.conn.execute('PRAGMA synchronous = OFF')
        self.conn.execute('PRAGMA journal_mode = MEMORY')
        self.conn.execute('PRAGMA temp_store = MEMORY')
        self.conn.execute('PRAGMA cache_size = 10000')

        # Datos
        self.filtered_icons = []
        self.theme_config = self.load_theme()
        self.icon_widgets = []  # Lista de widgets de iconos
        self.current_icon_index = -1  # Índice del icono seleccionado
        self.focus_mode = 'search'  # 'search' o 'icons'

        # UI
        self.setup_ui()
        self.setup_shortcuts()
        self.apply_theme()

        # Cargar iconos iniciales (solo con tags)
        self.filter_icons()

        # Establecer foco inicial en búsqueda
        self.search_edit.setFocus()

    def setup_ui(self):
        """Configura la interfaz de usuario"""
        self.setWindowTitle("Icon Browser")
        self.setGeometry(100, 100, 1000, 700)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)

        # Barra de búsqueda
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Buscar iconos... (nombre o tags)")
        self.search_edit.textChanged.connect(self.on_search_changed)
        self.search_edit.installEventFilter(self)  # Para capturar eventos de teclado
        main_layout.addWidget(self.search_edit)

        # Barra de estado - CORREGIDO: usar statusBar() de QMainWindow
        self.update_status()

        # Área de scroll para los iconos
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.installEventFilter(self)  # Para capturar eventos de teclado

        # Widget contenedor para el grid de iconos
        self.icons_widget = QWidget()
        self.icons_layout = QGridLayout(self.icons_widget)
        self.icons_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.scroll_area.setWidget(self.icons_widget)
        main_layout.addWidget(self.scroll_area)

        # Timer para búsqueda con delay
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.filter_icons)

    def update_status(self):
        """Actualiza la barra de estado"""
        try:
            cursor = self.conn.execute('SELECT COUNT(*) FROM icons')
            total_icons = cursor.fetchone()[0]

            cursor = self.conn.execute('''
                SELECT COUNT(DISTINCT icon_id) FROM icon_tags
            ''')
            tagged_icons = cursor.fetchone()[0]

            search_text = self.search_edit.text().strip() if hasattr(self, 'search_edit') else ""
            if search_text:
                status_text = f"Mostrando {len(self.filtered_icons)} iconos (de {total_icons} total, {tagged_icons} con tags)"
            else:
                status_text = f"Mostrando {len(self.filtered_icons)} iconos con tags (de {total_icons} total)"

            # CORREGIDO: usar statusBar() en lugar de status_bar
            self.statusBar().showMessage(status_text)

        except Exception as e:
            # CORREGIDO: usar statusBar() en lugar de status_bar
            self.statusBar().showMessage(f"Error: {e}")

    def get_icon_tags(self, icon_id: int) -> List[str]:
        """Obtiene los tags de un icono"""
        cursor = self.conn.execute('''
            SELECT t.name FROM tags t
            JOIN icon_tags it ON t.id = it.tag_id
            WHERE it.icon_id = ?
            ORDER BY t.name
        ''', (icon_id,))
        return [row[0] for row in cursor.fetchall()]

    def get_all_tags(self) -> List[str]:
        """Obtiene todos los tags disponibles"""
        cursor = self.conn.execute('SELECT name FROM tags ORDER BY name')
        return [row[0] for row in cursor.fetchall()]

    def filter_icons(self):
        """Filtra los iconos según el texto de búsqueda"""
        search_text = self.search_edit.text().strip().lower() if hasattr(self, 'search_edit') else ""

        if not search_text:
            # Sin búsqueda: mostrar solo iconos con tags
            cursor = self.conn.execute('''
                SELECT DISTINCT i.* FROM icons i
                JOIN icon_tags it ON i.id = it.icon_id
                ORDER BY i.filename
                LIMIT 200
            ''')
        else:
            # Con búsqueda: buscar en todos los iconos
            cursor = self.conn.execute('''
                SELECT i.*, GROUP_CONCAT(t.name, ',') as tags FROM icons i
                LEFT JOIN icon_tags it ON i.id = it.icon_id
                LEFT JOIN tags t ON it.tag_id = t.id
                WHERE
                    LOWER(i.filename) LIKE ? OR
                    LOWER(i.path) LIKE ? OR
                    EXISTS (
                        SELECT 1 FROM tags t2
                        JOIN icon_tags it2 ON t2.id = it2.tag_id
                        WHERE it2.icon_id = i.id AND LOWER(t2.name) LIKE ?
                    )
                GROUP BY i.id
                ORDER BY i.filename
                LIMIT 200
            ''', (f'%{search_text}%', f'%{search_text}%', f'%{search_text}%'))

        # Convertir resultados a lista de diccionarios
        self.filtered_icons = []
        for row in cursor.fetchall():
            icon_data = dict(row)
            self.filtered_icons.append(icon_data)

        self.update_icons_display()
        self.update_status()

    def update_icons_display(self):
        """Actualiza la visualización de los iconos"""
        # Limpiar layout existente
        while self.icons_layout.count():
            child = self.icons_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Limpiar lista de widgets
        self.icon_widgets = []
        self.current_icon_index = -1

        # Agregar iconos filtrados
        row, col = 0, 0
        max_cols = 10

        for icon_data in self.filtered_icons:
            # Obtener tags del icono
            tags = self.get_icon_tags(icon_data['id'])

            # Crear widget del icono
            icon_item = IconItem(icon_data, tags)
            icon_item.clicked.connect(self.on_icon_clicked)
            icon_item.apply_theme(self.theme_config)

            self.icons_layout.addWidget(icon_item, row, col)
            self.icon_widgets.append(icon_item)

            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        # Seleccionar el primer icono si hay iconos
        if self.icon_widgets and self.focus_mode == 'icons':
            self.select_icon(0)

        # Actualizar la UI
        self.icons_widget.update()

    def on_icon_clicked(self, icon_path: str):
        """Maneja el clic en un icono"""
        self.selected_icon = icon_path
        # Encontrar el índice del icono clickeado
        for i, widget in enumerate(self.icon_widgets):
            if widget.icon_path == icon_path:
                self.select_icon(i)
                break

    def copy_to_clipboard(self, text: str) -> bool:
        """Copia texto al clipboard usando diferentes métodos según la plataforma"""

        def try_qt_clipboard():
            """Intenta usar el clipboard de Qt"""
            try:
                clipboard = QApplication.clipboard()
                clipboard.setText(text)
                return True
            except Exception:
                return False

        def try_copyq():
            """Intenta usar CopyQ"""
            try:
                # OPTIMIZACIÓN: Reducir timeout y usar check=False para mayor velocidad
                result = subprocess.run(['copyq', 'add', text],
                                      capture_output=True, timeout=1, check=False)
                return result.returncode == 0
            except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
                return False

        def try_xclip():
            """Intenta usar xclip"""
            try:
                # OPTIMIZACIÓN: Usar timeout más corto
                process = subprocess.run(['xclip', '-selection', 'clipboard'],
                                       input=text.encode(), timeout=1, check=False)
                return process.returncode == 0
            except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
                return False

        def try_xsel():
            """Intenta usar xsel"""
            try:
                # OPTIMIZACIÓN: Usar timeout más corto
                process = subprocess.run(['xsel', '--clipboard', '--input'],
                                       input=text.encode(), timeout=1, check=False)
                return process.returncode == 0
            except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
                return False

        def try_pbcopy():
            """Intenta usar pbcopy (macOS)"""
            try:
                # OPTIMIZACIÓN: Usar timeout más corto
                process = subprocess.run(['pbcopy'], input=text.encode(), timeout=1, check=False)
                return process.returncode == 0
            except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
                return False

        # Usar ÚNICAMENTE el método especificado
        if self.clipboard_method == 'qt':
            return try_qt_clipboard()
        elif self.clipboard_method == 'copyq':
            return try_copyq()
        elif self.clipboard_method == 'xclip':
            return try_xclip()
        elif self.clipboard_method == 'xsel':
            return try_xsel()
        elif self.clipboard_method == 'pbcopy':
            return try_pbcopy()
        elif self.clipboard_method == 'auto':
            # Solo en modo automático intentar múltiples métodos
            if sys.platform == 'linux':
                # Linux: CopyQ > xclip > xsel > Qt
                methods = [try_copyq, try_xclip, try_xsel, try_qt_clipboard]
            elif sys.platform == 'darwin':
                # macOS: pbcopy > Qt
                methods = [try_pbcopy, try_qt_clipboard]
            elif sys.platform == 'win32':
                # Windows: Qt
                methods = [try_qt_clipboard]
            else:
                # Otros: Qt
                methods = [try_qt_clipboard]

            for method in methods:
                if method():
                    return True
            return False
        else:
            # Método no reconocido, usar Qt como fallback
            return try_qt_clipboard()

    def copy_selected_path(self):
        """Copia el path del icono seleccionado y cierra la ventana"""
        if hasattr(self, 'selected_icon') and self.selected_icon:
            # OPTIMIZACIÓN: No hacer consultas a BD, ya tenemos el path
            success = self.copy_to_clipboard(self.selected_icon)
            if success:
                # OPTIMIZACIÓN: Cerrar inmediatamente sin delays innecesarios
                self.close()
            else:
                method_msg = f"método '{self.clipboard_method}'" if self.clipboard_method != 'auto' else "ningún método disponible"
                QMessageBox.warning(self, "Error",
                    f"No se pudo copiar al clipboard usando {method_msg}.\n"
                    f"Verifica que la herramienta esté instalada o usa --clipboard auto")
        else:
            QMessageBox.information(self, "Info", "Selecciona un icono primero")

    def edit_selected_tags(self):
        """Abre el editor de tags para el icono seleccionado"""
        if not hasattr(self, 'selected_icon'):
            QMessageBox.information(self, "Info", "Selecciona un icono primero")
            return

        # Obtener ID del icono
        cursor = self.conn.execute('SELECT id FROM icons WHERE path = ?', (self.selected_icon,))
        result = cursor.fetchone()
        if not result:
            QMessageBox.warning(self, "Error", "Icono no encontrado en la base de datos")
            return

        icon_id = result[0]
        current_tags = self.get_icon_tags(icon_id)
        all_tags = self.get_all_tags()

        dialog = TagEditDialog(self.selected_icon, current_tags, all_tags, self)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_tags = dialog.get_tags()
            self.update_icon_tags(icon_id, new_tags)
            self.filter_icons()  # Actualizar vista

    def update_icon_tags(self, icon_id: int, new_tags: List[str]):
        """Actualiza los tags de un icono en la base de datos"""
        try:
            # Eliminar tags existentes
            self.conn.execute('DELETE FROM icon_tags WHERE icon_id = ?', (icon_id,))

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

                # Crear relación icono-tag
                self.conn.execute(
                    'INSERT INTO icon_tags (icon_id, tag_id) VALUES (?, ?)',
                    (icon_id, tag_id)
                )

            self.conn.commit()
            QMessageBox.information(self, "Éxito", "Tags actualizados correctamente")

        except Exception as e:
            self.conn.rollback()
            QMessageBox.warning(self, "Error", f"No se pudieron actualizar los tags: {e}")

    def open_selected_folder(self):
        """Abre la carpeta del icono seleccionado"""
        if not hasattr(self, 'selected_icon'):
            QMessageBox.information(self, "Info", "Selecciona un icono primero")
            return

        folder_path = Path(self.selected_icon).parent
        try:
            if sys.platform == 'linux':
                subprocess.run(['xdg-open', str(folder_path)])
            elif sys.platform == 'darwin':
                subprocess.run(['open', str(folder_path)])
            elif sys.platform == 'win32':
                subprocess.run(['explorer', str(folder_path)])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo abrir la carpeta: {e}")

    def copy_selected_file(self):
        """Copia el archivo seleccionado a ~/.local/share/icons/pollo"""
        if not hasattr(self, 'selected_icon'):
            QMessageBox.information(self, "Info", "Selecciona un icono primero")
            return

        dest_dir = Path.home() / '.local/share/icons/pollo'
        dest_dir.mkdir(parents=True, exist_ok=True)

        source_path = Path(self.selected_icon)
        dest_path = dest_dir / source_path.name

        try:
            shutil.copy2(source_path, dest_path)
            QMessageBox.information(self, "Éxito", f"Archivo copiado a: {dest_path}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo copiar el archivo: {e}")

    def closeEvent(self, event):
        """Maneja el cierre de la aplicación"""
        if hasattr(self, 'conn'):
            self.conn.close()
        event.accept()

    def get_icon_folders(self) -> List[Path]:
        """Obtiene las carpetas de iconos disponibles en el sistema"""
        # Carpetas base del sistema
        potential_folders = [
            # Carpetas del usuario
            Path.home() / '.local/share/icons',
            Path.home() / '.icons',
            Path.home() / '.local/share/pixmaps',

            # Carpetas del sistema
            Path('/usr/share/icons'),
            Path('/usr/share/pixmaps'),
            Path('/usr/local/share/icons'),
            Path('/usr/local/share/pixmaps'),

            # Carpetas específicas de escritorios
            Path('/usr/share/icons/hicolor'),
            Path('/usr/share/icons/Adwaita'),
            Path('/usr/share/icons/breeze'),
            Path('/usr/share/icons/oxygen'),

            # Carpetas adicionales comunes
            Path.home() / 'Pictures/Icons',  # Carpeta personal
            Path.home() / 'Imágenes/Iconos',  # Carpeta personal en español

            # Carpeta de iconos copiados por la aplicación
            Path.home() / '.local/share/icons/pollo',
        ]

        # Leer carpetas adicionales del archivo de configuración
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    custom_folders = config.get('icon_folders', [])
                    for folder_str in custom_folders:
                        folder_path = Path(folder_str).expanduser()
                        if folder_path.exists() and folder_path.is_dir():
                            potential_folders.append(folder_path)
            except (yaml.YAMLError, IOError):
                pass

        # Filtrar solo las carpetas que existen
        existing_folders = []
        for folder in potential_folders:
            if folder.exists() and folder.is_dir():
                existing_folders.append(folder)

        # Agregar carpetas de /opt que contengan iconos
        opt_path = Path('/opt')
        if opt_path.exists():
            for app_dir in opt_path.iterdir():
                if app_dir.is_dir():
                    icons_dir = app_dir / 'share/icons'
                    if icons_dir.exists():
                        existing_folders.append(icons_dir)

        return existing_folders

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

    def setup_shortcuts(self):
        """Configura los atajos de teclado"""
        # Enter: copiar path y cerrar
        enter_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Return), self)
        enter_shortcut.activated.connect(self.copy_selected_path)

        # Ctrl+E: editar tags
        edit_shortcut = QShortcut(QKeySequence("Ctrl+E"), self)
        edit_shortcut.activated.connect(self.edit_selected_tags)

        # Ctrl+O: abrir carpeta
        open_shortcut = QShortcut(QKeySequence("Ctrl+O"), self)
        open_shortcut.activated.connect(self.open_selected_folder)

        # Ctrl+C: copiar archivo
        copy_shortcut = QShortcut(QKeySequence("Ctrl+C"), self)
        copy_shortcut.activated.connect(self.copy_selected_file)

        # Esc: cerrar aplicación
        esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        esc_shortcut.activated.connect(self.close)

    def eventFilter(self, obj, event):
        """Filtro de eventos para manejar navegación con teclado"""
        from PyQt6.QtCore import QEvent
        from PyQt6.QtGui import QKeyEvent

        if event.type() == QEvent.Type.KeyPress:
            key = event.key()

            # TAB: cambiar entre búsqueda e iconos
            if key == Qt.Key.Key_Tab:
                self.toggle_focus_mode()
                return True

            # Si estamos en modo iconos, manejar navegación
            if self.focus_mode == 'icons' and self.icon_widgets:
                if key == Qt.Key.Key_Up:
                    self.navigate_icons(-10)  # Fila anterior
                    return True
                elif key == Qt.Key.Key_Down:
                    self.navigate_icons(10)  # Fila siguiente
                    return True
                elif key == Qt.Key.Key_Left:
                    self.navigate_icons(-1)  # Icono anterior
                    return True
                elif key == Qt.Key.Key_Right:
                    self.navigate_icons(1)  # Icono siguiente
                    return True
                elif key == Qt.Key.Key_Home:
                    self.select_icon(0)  # Primer icono
                    return True
                elif key == Qt.Key.Key_End:
                    self.select_icon(len(self.icon_widgets) - 1)  # Último icono
                    return True
                elif key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
                    self.copy_selected_path()
                    return True

            # Si estamos en búsqueda y presionamos Enter
            elif self.focus_mode == 'search' and (key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter):
                if self.icon_widgets:
                    self.focus_mode = 'icons'
                    self.select_icon(0)
                    self.update_focus_style()
                return True

        return super().eventFilter(obj, event)

    def toggle_focus_mode(self):
        """Cambia entre modo búsqueda e iconos"""
        if self.focus_mode == 'search':
            if self.icon_widgets:
                self.focus_mode = 'icons'
                if self.current_icon_index == -1:
                    self.select_icon(0)
                self.scroll_area.setFocus()
        else:
            self.focus_mode = 'search'
            self.search_edit.setFocus()

        self.update_focus_style()

    def update_focus_style(self):
        """Actualiza el estilo visual según el modo de foco"""
        if self.focus_mode == 'search':
            self.search_edit.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {self.theme_config['search_bg']};
                    color: {self.theme_config['text_color']};
                    border: 3px solid {self.theme_config['accent_color']};
                    border-radius: 4px;
                    padding: 8px;
                    font-size: 14px;
                }}
            """)
        else:
            self.search_edit.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {self.theme_config['search_bg']};
                    color: {self.theme_config['text_color']};
                    border: 2px solid {self.theme_config['search_border']};
                    border-radius: 4px;
                    padding: 8px;
                    font-size: 14px;
                }}
            """)

    def navigate_icons(self, delta: int):
        """Navega entre iconos usando un delta"""
        if not self.icon_widgets:
            return

        new_index = self.current_icon_index + delta

        # Asegurar que el índice esté en rango
        new_index = max(0, min(new_index, len(self.icon_widgets) - 1))

        self.select_icon(new_index)

    def select_icon(self, index: int):
        """Selecciona un icono por índice"""
        if not self.icon_widgets or index < 0 or index >= len(self.icon_widgets):
            return

        # Deseleccionar icono anterior
        if 0 <= self.current_icon_index < len(self.icon_widgets):
            self.icon_widgets[self.current_icon_index].set_selected(False, self.theme_config)

        # Seleccionar nuevo icono
        self.current_icon_index = index
        selected_widget = self.icon_widgets[index]
        selected_widget.set_selected(True, self.theme_config)
        self.selected_icon = selected_widget.icon_path

        # Asegurar que el icono esté visible
        self.scroll_area.ensureWidgetVisible(selected_widget)

    def apply_theme(self):
        """Aplica el tema a la interfaz"""
        style = f"""
            QMainWindow {{
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
            QScrollArea {{
                background-color: {self.theme_config['bg_color']};
                border: none;
            }}
            QWidget {{
                background-color: {self.theme_config['bg_color']};
                color: {self.theme_config['text_color']};
            }}
        """
        self.setStyleSheet(style)
        self.update_focus_style()

    def on_search_changed(self):
        """Maneja el cambio en el texto de búsqueda"""
        self.search_timer.stop()
        self.search_timer.start(300)  # 300ms delay


def find_app_icon() -> Optional[QIcon]:
    """Busca el icono de la aplicación en múltiples ubicaciones"""
    icon_names = ['icon-browser', 'folder', 'application-default-icon', 'image-x-generic']
    icon_extensions = ['.png', '.svg', '.xpm', '.ico']

    # Rutas específicas donde buscar
    search_paths = [
        Path(__file__).parent,
        Path(__file__).parent / 'icons',
        Path.home() / '.local/share/icon-browser',
        Path.home() / '.local/share/icons/hicolor/48x48/apps',
        Path.home() / '.local/share/icons/hicolor/32x32/apps',
        Path.home() / '.local/share/icons',
        Path('/usr/share/pixmaps'),
        Path('/usr/share/icons/hicolor/48x48/apps'),
        Path('/usr/share/icons/hicolor/32x32/apps'),
        Path.home() / '.icons'
    ]

    # Buscar por nombre específico del archivo
    for path in search_paths:
        if not path.exists():
            continue

        for name in icon_names:
            for ext in icon_extensions:
                icon_file = path / f"{name}{ext}"
                if icon_file.exists():
                    return QIcon(str(icon_file))

    # Si no encuentra nada, usar el icono por defecto del sistema
    return QIcon.fromTheme("folder") or QIcon.fromTheme("application-default-icon")


def main():
    parser = argparse.ArgumentParser(description='Icon Browser - Navegador de iconos con tags')
    parser.add_argument('--theme', default='solarized-dark',
                       choices=['solarized-dark', 'tokyo-night', 'catppucin',
                               'gruvbox', 'kanagawa', 'forest-dark', 'neon'],
                       help='Tema de color a usar')
    parser.add_argument('--clipboard', default='auto',
                       choices=['auto', 'qt', 'copyq', 'xclip', 'xsel', 'pbcopy'],
                       help='Método de clipboard a usar. auto detecta automáticamente, '
                            'copyq usa CopyQ, xclip usa xclip, xsel usa xsel, '
                            'pbcopy para macOS, qt usa Qt (fallback)')

    args = parser.parse_args()

    app = QApplication(sys.argv)

    # Configurar icono de la aplicación
    app_icon = find_app_icon()
    if app_icon:
        app.setWindowIcon(app_icon)

    window = IconBrowser(args.theme, args.clipboard)
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
