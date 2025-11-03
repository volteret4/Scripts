#!/usr/bin/env python3
"""
Conversor de notas de Obsidian a posts de Hugo (PyQt6 + UI file + Themes)
Uso: python crear_post_ui.py [archivo.md] [--all] [--theme THEME_NAME]
"""

import sys
import os
import json
import yaml
import shutil
import subprocess
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QLineEdit, QCheckBox, QScrollArea,
    QMessageBox, QDialog, QDialogButtonBox, QGridLayout, QFrame,
    QProgressBar, QTabWidget, QGroupBox, QSplitter, QFileDialog, QComboBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSettings
from PyQt6.QtGui import QFont, QKeySequence, QShortcut, QPalette, QAction
from PyQt6 import uic


class ThemeManager:
    """Gestor de temas dinámicos"""

    def __init__(self, themes_file: str = "themes.yml"):
        self.themes_file = Path(themes_file)
        self.themes = self.load_themes()
        self.current_theme = "tokyo-night"  # Tema por defecto

    def load_themes(self) -> Dict:
        """Cargar temas desde archivo YAML"""
        if not self.themes_file.exists():
            self.create_default_themes()

        try:
            with open(self.themes_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Error cargando temas: {e}")
            return self.get_default_themes()

    def create_default_themes(self):
        """Crear archivo de temas por defecto"""
        default_themes = self.get_default_themes()
        try:
            with open(self.themes_file, 'w', encoding='utf-8') as f:
                yaml.dump(default_themes, f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            print(f"Error creando archivo de temas: {e}")

    def get_default_themes(self) -> Dict:
        """Obtener temas por defecto como fallback"""
        return {
            'tokyo-night': {
                'accent_color': '#7aa2f7',
                'bg_color': '#1a1b26',
                'border_color': '#414868',
                'search_bg': '#24283b',
                'search_border': '#414868',
                'text_color': '#c0caf5',
                'widget_bg': '#24283b'
            },
            'catppuccin': {
                'accent_color': '#89b4fa',
                'bg_color': '#1e1e2e',
                'border_color': '#45475a',
                'search_bg': '#313244',
                'search_border': '#45475a',
                'text_color': '#cdd6f4',
                'widget_bg': '#313244'
            }
        }

    def get_theme_names(self) -> List[str]:
        """Obtener lista de nombres de temas"""
        return list(self.themes.keys())

    def get_theme(self, theme_name: str) -> Dict:
        """Obtener configuración de tema específico"""
        return self.themes.get(theme_name, self.themes.get('tokyo-night', {}))

    def set_current_theme(self, theme_name: str):
        """Establecer tema actual"""
        if theme_name in self.themes:
            self.current_theme = theme_name

    def get_current_theme(self) -> Dict:
        """Obtener tema actual"""
        return self.get_theme(self.current_theme)

    def generate_stylesheet(self, theme_name: str = None) -> str:
        """Generar stylesheet CSS para el tema"""
        if theme_name is None:
            theme_name = self.current_theme

        theme = self.get_theme(theme_name)

        return f"""
        QMainWindow {{
            background-color: {theme['bg_color']};
            color: {theme['text_color']};
        }}

        QWidget {{
            background-color: {theme['bg_color']};
            color: {theme['text_color']};
        }}

        QGroupBox {{
            font-weight: bold;
            border: 2px solid {theme['border_color']};
            border-radius: 5px;
            margin-top: 1ex;
            padding-top: 10px;
            background-color: {theme['widget_bg']};
            color: {theme['text_color']};
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
            color: {theme['accent_color']};
        }}

        QLineEdit, QTextEdit {{
            border: 1px solid {theme['border_color']};
            border-radius: 4px;
            padding: 5px;
            font-size: 11px;
            background-color: {theme['search_bg']};
            color: {theme['text_color']};
        }}

        QLineEdit:focus, QTextEdit:focus {{
            border-color: {theme['accent_color']};
            border-width: 2px;
        }}

        QPushButton {{
            border: 1px solid {theme['border_color']};
            border-radius: 4px;
            padding: 6px 12px;
            background-color: {theme['widget_bg']};
            color: {theme['text_color']};
        }}

        QPushButton:hover {{
            background-color: {theme['accent_color']};
            color: {theme['bg_color']};
            border-color: {theme['accent_color']};
        }}

        QPushButton:pressed {{
            background-color: {theme['border_color']};
        }}

        QPushButton:disabled {{
            background-color: {theme['border_color']};
            color: {theme['border_color']};
        }}

        QCheckBox {{
            spacing: 5px;
            color: {theme['text_color']};
        }}

        QCheckBox::indicator {{
            width: 15px;
            height: 15px;
        }}

        QCheckBox::indicator:unchecked {{
            border: 1px solid {theme['border_color']};
            background-color: {theme['widget_bg']};
            border-radius: 3px;
        }}

        QCheckBox::indicator:checked {{
            border: 1px solid {theme['accent_color']};
            background-color: {theme['accent_color']};
            border-radius: 3px;
        }}

        QScrollArea {{
            background-color: {theme['bg_color']};
            border: 1px solid {theme['border_color']};
            border-radius: 5px;
        }}

        QScrollBar:vertical {{
            background-color: {theme['widget_bg']};
            width: 12px;
            border-radius: 6px;
        }}

        QScrollBar::handle:vertical {{
            background-color: {theme['accent_color']};
            border-radius: 6px;
            min-height: 20px;
        }}

        QScrollBar::handle:vertical:hover {{
            background-color: {theme['text_color']};
        }}

        QLabel {{
            color: {theme['text_color']};
        }}

        QMenuBar {{
            background-color: {theme['widget_bg']};
            color: {theme['text_color']};
            border-bottom: 1px solid {theme['border_color']};
        }}

        QMenuBar::item {{
            background-color: transparent;
            padding: 4px 8px;
        }}

        QMenuBar::item:selected {{
            background-color: {theme['accent_color']};
            color: {theme['bg_color']};
        }}

        QMenu {{
            background-color: {theme['widget_bg']};
            color: {theme['text_color']};
            border: 1px solid {theme['border_color']};
        }}

        QMenu::item {{
            padding: 4px 16px;
        }}

        QMenu::item:selected {{
            background-color: {theme['accent_color']};
            color: {theme['bg_color']};
        }}

        QStatusBar {{
            background-color: {theme['widget_bg']};
            color: {theme['text_color']};
            border-top: 1px solid {theme['border_color']};
        }}

        QProgressBar {{
            border: 1px solid {theme['border_color']};
            border-radius: 5px;
            text-align: center;
            background-color: {theme['widget_bg']};
            color: {theme['text_color']};
        }}

        QProgressBar::chunk {{
            background-color: {theme['accent_color']};
            border-radius: 4px;
        }}

        QComboBox {{
            border: 1px solid {theme['border_color']};
            border-radius: 4px;
            padding: 4px 8px;
            background-color: {theme['widget_bg']};
            color: {theme['text_color']};
        }}

        QComboBox:hover {{
            border-color: {theme['accent_color']};
        }}

        QComboBox::drop-down {{
            border: none;
        }}

        QComboBox::down-arrow {{
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 5px solid {theme['text_color']};
        }}

        QComboBox QAbstractItemView {{
            background-color: {theme['widget_bg']};
            color: {theme['text_color']};
            border: 1px solid {theme['border_color']};
            selection-background-color: {theme['accent_color']};
        }}

        QSplitter::handle {{
            background-color: {theme['border_color']};
        }}

        QSplitter::handle:hover {{
            background-color: {theme['accent_color']};
        }}
        """


class BlogConfig:
    """Configuración de los blogs"""
    NOTAS = {
        'name': 'notas',
        'dir': '/mnt/NFS/blogs/notas',
        'content_dir': '/mnt/NFS/blogs/notas/content/post/',
        'static_dir': '/mnt/NFS/blogs/notas/static/',
        'needs_category': True
    }

    MIHITAS = {
        'name': 'mihitas',
        'dir': '/mnt/NFS/blogs/mihitas',
        'content_dir': '/mnt/NFS/blogs/mihitas/content/posts/',
        'static_dir': '/mnt/NFS/blogs/mihitas/static/',
        'needs_category': False
    }

    OBSIDIAN_IMG_DIR = "/mnt/windows/FTP/wiki/Obsidian/Dibujos/img/"


class CategoryManager:
    """Gestor de categorías con archivo JSON"""

    def __init__(self, categories_file: str = "categorias.json"):
        self.categories_file = Path(categories_file)
        self.categories = self.load_categories()

    def load_categories(self) -> List[str]:
        """Cargar categorías desde archivo JSON"""
        if self.categories_file.exists():
            try:
                with open(self.categories_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('categorias', [])
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        return []

    def save_categories(self):
        """Guardar categorías al archivo JSON"""
        try:
            with open(self.categories_file, 'w', encoding='utf-8') as f:
                json.dump({'categorias': sorted(self.categories)}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error guardando categorías: {e}")

    def add_category(self, category: str):
        """Añadir nueva categoría"""
        category = category.strip()
        if category and category not in self.categories:
            self.categories.append(category)
            self.save_categories()
            return True
        return False

    def get_categories(self) -> List[str]:
        """Obtener lista de categorías ordenada"""
        return sorted(self.categories)


class TagManager:
    """Gestor de tags con archivo JSON"""

    def __init__(self, tags_file: str = "tags.json"):
        self.tags_file = Path(tags_file)
        self.tags = self.load_tags()

    def load_tags(self) -> List[str]:
        """Cargar tags desde archivo JSON"""
        if self.tags_file.exists():
            try:
                with open(self.tags_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('tags', [])
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        return []

    def save_tags(self):
        """Guardar tags al archivo JSON"""
        try:
            with open(self.tags_file, 'w', encoding='utf-8') as f:
                json.dump({'tags': sorted(self.tags)}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error guardando tags: {e}")

    def add_tag(self, tag: str):
        """Añadir nuevo tag"""
        tag = tag.strip()
        if tag and tag not in self.tags:
            self.tags.append(tag)
            self.save_tags()
            return True
        return False

    def get_tags(self) -> List[str]:
        """Obtener lista de tags ordenada"""
        return sorted(self.tags)


class AddCategoryDialog(QDialog):
    """Diálogo para añadir nuevas categorías"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Añadir Nueva Categoría")
        self.setModal(True)
        self.resize(400, 150)

        layout = QVBoxLayout()

        # Instrucciones
        label = QLabel("Introduce la nueva categoría:")
        layout.addWidget(label)

        # Input
        self.category_input = QLineEdit()
        self.category_input.setPlaceholderText("Nombre de la categoría...")
        layout.addWidget(self.category_input)

        # Botones
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

        # Focus en input
        self.category_input.setFocus()
        self.category_input.returnPressed.connect(self.accept)

    def get_category(self) -> str:
        """Obtener la categoría introducida"""
        return self.category_input.text().strip()


class AddTagDialog(QDialog):
    """Diálogo para añadir nuevos tags"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Añadir Nuevo Tag")
        self.setModal(True)
        self.resize(400, 150)

        layout = QVBoxLayout()

        # Instrucciones
        label = QLabel("Introduce el nuevo tag:")
        layout.addWidget(label)

        # Input
        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("Nombre del tag...")
        layout.addWidget(self.tag_input)

        # Botones
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

        # Focus en input
        self.tag_input.setFocus()
        self.tag_input.returnPressed.connect(self.accept)

    def get_tag(self) -> str:
        """Obtener el tag introducido"""
        return self.tag_input.text().strip()


class ProcessThread(QThread):
    """Thread para procesar el post sin bloquear UI"""

    progress_updated = pyqtSignal(str)
    finished_successfully = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, file_path: str, blogs: List[str], title: str,
                 tags: List[str], description: str, category: str = ""):
        super().__init__()
        self.file_path = Path(file_path)
        self.blogs = blogs
        self.title = title
        self.tags = tags
        self.description = description
        self.category = category

    def run(self):
        try:
            for blog_name in self.blogs:
                self.progress_updated.emit(f"Procesando blog: {blog_name}")
                self.process_blog(blog_name)

            self.finished_successfully.emit("Posts procesados exitosamente")

        except Exception as e:
            self.error_occurred.emit(str(e))

    def process_blog(self, blog_name: str):
        """Procesar un blog específico"""
        # Configuración del blog
        config = BlogConfig.NOTAS if blog_name == 'notas' else BlogConfig.MIHITAS

        # Crear directorios
        content_dir = Path(config['content_dir'])
        static_dir = Path(config['static_dir'])
        content_dir.mkdir(parents=True, exist_ok=True)
        static_dir.mkdir(parents=True, exist_ok=True)
        (static_dir / "images").mkdir(exist_ok=True)

        # Crear directorio del post
        post_name = self.file_path.stem
        output_dir = content_dir / post_name
        output_dir.mkdir(exist_ok=True)

        # Generar archivo
        output_file = output_dir / "index.md"

        with open(output_file, 'w', encoding='utf-8') as f:
            # Escribir frontmatter
            if blog_name == 'notas':
                f.write(self.generate_frontmatter_notas())
            else:
                f.write(self.generate_frontmatter_mihitas())

            # Procesar contenido
            f.write(self.process_content())

        self.progress_updated.emit(f"Blog {blog_name} procesado: {output_file}")

        # Git commit
        try:
            self.git_commit(config['dir'])
            self.progress_updated.emit(f"Git commit realizado para {blog_name}")
        except Exception as e:
            self.progress_updated.emit(f"Error en git commit para {blog_name}: {e}")

    def generate_frontmatter_notas(self) -> str:
        """Generar frontmatter para blog notas"""
        date = datetime.now().strftime("%Y-%m-%d")
        tags_str = ", ".join(f'"{tag}"' for tag in self.tags)

        return f"""---
title : "{self.title}"
date : "{date}"
image : ""
tags : [{tags_str}]
categories : ["{self.category}"]
description : "{self.description}"
---

"""

    def generate_frontmatter_mihitas(self) -> str:
        """Generar frontmatter para blog mihitas"""
        date = datetime.now().strftime("%Y-%m-%d")
        tags_str = ", ".join(f'"{tag}"' for tag in self.tags)

        return f"""+++
title = "{self.title}"
date = "{date}"
author = "volteret4"
cover = ""
tags = [{tags_str}]
keywords = [{tags_str}]
description = "{self.description}"
showFullContent = false
readingTime = true
hideComments = false
+++

"""

    def process_content(self) -> str:
        """Procesar contenido del archivo"""
        content = []
        in_frontmatter = False
        content_started = False

        with open(self.file_path, 'r', encoding='utf-8') as f:
            for line in f:
                # Detectar frontmatter YAML
                if line.strip() == "---":
                    if not content_started:
                        in_frontmatter = True
                        content_started = True
                        continue
                    elif in_frontmatter:
                        in_frontmatter = False
                        continue

                # Saltar frontmatter
                if in_frontmatter:
                    continue

                content_started = True

                # Procesar imágenes de Obsidian
                line = self.process_images(line)
                content.append(line)

        return "".join(content)

    def process_images(self, line: str) -> str:
        """Procesar imágenes de Obsidian"""
        # Patrón para imágenes: ![[image.png]]
        pattern = r'!\[\[([^]]+\.(png|jpg|jpeg|gif|webp))\]\]'

        def replace_image(match):
            img_name = match.group(1)
            img_path = Path(BlogConfig.OBSIDIAN_IMG_DIR) / img_name

            if img_path.exists():
                try:
                    return f"![{img_name}](/images/{img_name})"
                except Exception:
                    return f"<!-- Imagen no copiada: {img_name} -->"
            else:
                return f"<!-- Imagen no encontrada: {img_name} -->"

        return re.sub(pattern, replace_image, line)

    def git_commit(self, blog_dir: str):
        """Realizar commit a git"""
        try:
            os.chdir(blog_dir)
            subprocess.run(["git", "add", "."], check=True)

            # Obtener mensaje random de commit
            try:
                result = subprocess.run(
                    ["curl", "-s", "https://whatthecommit.com/index.txt"],
                    capture_output=True, text=True, timeout=10
                )
                commit_msg = result.stdout.strip() if result.returncode == 0 else "Update post"
            except:
                commit_msg = "Update post"

            subprocess.run(["git", "commit", "-m", commit_msg], check=True)
            subprocess.run(["git", "push"], check=True)

        except subprocess.CalledProcessError as e:
            raise Exception(f"Error en git: {e}")


class PostCreator(QMainWindow):
    """Ventana principal del creador de posts usando archivo .ui"""

    def __init__(self, theme_name: str = "tokyo-night"):
        super().__init__()
        self.tag_manager = TagManager()
        self.category_manager = CategoryManager()
        self.theme_manager = ThemeManager()
        self.settings = QSettings("PostCreator", "Settings")

        self.selected_file = None
        self.tag_checkboxes = {}
        self.tag_shortcuts = {}
        self.category_checkboxes = {}
        self.category_shortcuts = {}

        # Configurar tema inicial
        saved_theme = self.settings.value("theme", theme_name)
        self.theme_manager.set_current_theme(saved_theme)

        # Cargar UI desde archivo
        self.load_ui()
        self.setup_theme_selector()
        self.setup_connections()
        self.setup_shortcuts()
        self.setup_tags_and_categories()

        # Aplicar tema
        self.apply_theme()

    def load_ui(self):
        """Cargar interfaz desde archivo .ui"""
        try:
            # Buscar archivo .ui en el mismo directorio
            ui_file = Path(__file__).parent / "crear_post.ui"
            if not ui_file.exists():
                raise FileNotFoundError(f"Archivo UI no encontrado: {ui_file}")

            uic.loadUi(str(ui_file), self)

        except Exception as e:
            QMessageBox.critical(None, "Error",
                f"No se pudo cargar la interfaz UI:\n{str(e)}\n\n"
                f"Asegúrate de que crear_post.ui esté en el mismo directorio.")
            sys.exit(1)

    def setup_theme_selector(self):
        """Configurar selector de temas en el menú"""
        # Crear selector de tema como combobox en la barra de estado
        self.theme_selector = QComboBox()
        self.theme_selector.addItems(self.theme_manager.get_theme_names())
        self.theme_selector.setCurrentText(self.theme_manager.current_theme)
        self.theme_selector.currentTextChanged.connect(self.change_theme)

        # Añadir a la barra de estado
        self.statusbar.addPermanentWidget(QLabel("Tema:"))
        self.statusbar.addPermanentWidget(self.theme_selector)

        # Crear acciones para cada tema en el menú
        for theme_name in self.theme_manager.get_theme_names():
            action = QAction(theme_name.replace('-', ' ').title(), self)
            action.triggered.connect(lambda checked, name=theme_name: self.change_theme(name))
            self.menuTemas.addAction(action)

    def change_theme(self, theme_name: str):
        """Cambiar tema de la aplicación"""
        self.theme_manager.set_current_theme(theme_name)
        self.theme_selector.setCurrentText(theme_name)
        self.apply_theme()

        # Guardar tema seleccionado
        self.settings.setValue("theme", theme_name)

        self.statusbar.showMessage(f"Tema cambiado a: {theme_name.replace('-', ' ').title()}", 3000)

    def apply_theme(self):
        """Aplicar tema actual a la aplicación"""
        stylesheet = self.theme_manager.generate_stylesheet()
        self.setStyleSheet(stylesheet)
        self.update()

    def setup_connections(self):
        """Configurar conexiones de señales"""
        # Botones principales
        self.processButton.clicked.connect(self.process_post)
        self.addTagButton.clicked.connect(self.add_new_tag)
        self.addCategoryButton.clicked.connect(self.add_new_category)

        # Checkbox de todos los blogs
        self.allBlogsCheckBox.toggled.connect(self.toggle_all_blogs)

        # Acciones de menú
        self.actionAbrir.triggered.connect(self.open_file_dialog)
        self.actionAtajos.triggered.connect(self.show_shortcuts_help)
        self.actionAcerca_de.triggered.connect(self.show_about)

        # Drag & Drop para archivos
        self.setAcceptDrops(True)

    def setup_shortcuts(self):
        """Configurar atajos de teclado"""
        # Enter para procesar
        process_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Return), self)
        process_shortcut.activated.connect(self.process_post)

        # Escape para cancelar
        cancel_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        cancel_shortcut.activated.connect(self.close)

    def setup_tags_and_categories(self):
        """Configurar sistema de tags y categorías"""
        self.refresh_tags()
        self.refresh_categories()

    def refresh_categories(self):
        """Actualizar lista de categorías en la interfaz"""
        # Limpiar checkboxes existentes
        for checkbox in self.category_checkboxes.values():
            checkbox.deleteLater()
        for shortcut in self.category_shortcuts.values():
            shortcut.deleteLater()

        self.category_checkboxes.clear()
        self.category_shortcuts.clear()

        # Crear nuevos checkboxes para categorías
        categories = self.category_manager.get_categories()
        row, col = 0, 0

        for i, category in enumerate(categories):
            checkbox = QCheckBox(f"&{i+1}. {category}" if i < 9 else category)
            checkbox.setObjectName(category)
            checkbox.toggled.connect(self.update_selected_category_display)

            self.category_checkboxes[category] = checkbox
            self.categoriesGridLayout.addWidget(checkbox, row, col)

            # Hotkey numérico solo para las primeras 9
            if i < 9:
                shortcut = QShortcut(QKeySequence(f"{i+1}"), self)
                shortcut.activated.connect(lambda checked, cb=checkbox: self.toggle_category_exclusive(cb))
                self.category_shortcuts[category] = shortcut

            col += 1
            if col >= 3:  # 3 columnas
                col = 0
                row += 1

    def toggle_category_exclusive(self, checkbox):
        """Alternar categoría de forma exclusiva (solo una seleccionada)"""
        # Desmarcar todas las demás categorías
        for cat_checkbox in self.category_checkboxes.values():
            if cat_checkbox != checkbox:
                cat_checkbox.setChecked(False)

        # Alternar la seleccionada
        checkbox.toggle()
        self.update_selected_category_display()

    def update_selected_category_display(self):
        """Actualizar display de categoría seleccionada"""
        selected_category = self.get_selected_category()
        if selected_category:
            self.selectedCategoryLabel.setText(f"📂 {selected_category}")
            self.selectedCategoryLabel.setStyleSheet("""
                padding: 5px;
                border: 2px solid #28a745;
                border-radius: 3px;
                background-color: #d4edda;
                color: #155724;
                font-weight: bold;
            """)
        else:
            self.selectedCategoryLabel.setText("Ninguna categoría seleccionada")
            self.selectedCategoryLabel.setStyleSheet("""
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 3px;
                background-color: #f9f9f9;
            """)

    def update_selected_tags_display(self):
        """Actualizar display de tags seleccionados"""
        selected_tags = self.get_selected_tags()
        if selected_tags:
            tags_text = ", ".join(selected_tags)
            self.selectedTagsLabel.setText(f"🏷️ {tags_text}")
            self.selectedTagsLabel.setStyleSheet("""
                padding: 5px;
                border: 2px solid #007bff;
                border-radius: 3px;
                background-color: #d1ecf1;
                color: #0c5460;
                font-weight: bold;
            """)
        else:
            self.selectedTagsLabel.setText("Ningún tag seleccionado")
            self.selectedTagsLabel.setStyleSheet("""
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 3px;
                background-color: #f9f9f9;
            """)

    def get_selected_category(self) -> str:
        """Obtener categoría seleccionada"""
        for category, checkbox in self.category_checkboxes.items():
            if checkbox.isChecked():
                return category
        return ""

    def add_new_category(self):
        """Añadir nueva categoría"""
        dialog = AddCategoryDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_category = dialog.get_category()
            if new_category:
                if self.category_manager.add_category(new_category):
                    self.refresh_categories()
                    QMessageBox.information(self, "Éxito", f"Categoría '{new_category}' añadida correctamente")
                else:
                    QMessageBox.warning(self, "Advertencia", "Categoría ya existe o está vacía")

    def refresh_tags(self):
        """Actualizar lista de tags en la interfaz"""
        # Limpiar checkboxes existentes
        for checkbox in self.tag_checkboxes.values():
            checkbox.deleteLater()
        for shortcut in self.tag_shortcuts.values():
            shortcut.deleteLater()

        self.tag_checkboxes.clear()
        self.tag_shortcuts.clear()

        # Crear nuevos checkboxes
        tags = self.tag_manager.get_tags()
        row, col = 0, 0

        for i, tag in enumerate(tags):
            checkbox = QCheckBox(f"&{i+1}. {tag}" if i < 9 else tag)
            checkbox.setObjectName(tag)
            checkbox.toggled.connect(self.update_selected_tags_display)

            self.tag_checkboxes[tag] = checkbox
            self.tagsGridLayout.addWidget(checkbox, row, col)

            # Hotkey numérico solo para los primeros 9
            if i < 9:
                shortcut = QShortcut(QKeySequence(f"Alt+{i+1}"), self)
                shortcut.activated.connect(lambda checked, cb=checkbox: cb.toggle())
                self.tag_shortcuts[tag] = shortcut

            col += 1
            if col >= 3:  # 3 columnas
                col = 0
                row += 1

    def add_new_tag(self):
        """Añadir nuevo tag"""
        dialog = AddTagDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_tag = dialog.get_tag()
            if new_tag:
                if self.tag_manager.add_tag(new_tag):
                    self.refresh_tags()
                    QMessageBox.information(self, "Éxito", f"Tag '{new_tag}' añadido correctamente")
                else:
                    QMessageBox.warning(self, "Advertencia", "Tag ya existe o está vacío")

    def get_selected_tags(self) -> List[str]:
        """Obtener tags seleccionados"""
        selected = []
        for tag, checkbox in self.tag_checkboxes.items():
            if checkbox.isChecked():
                selected.append(tag)
        return selected

    def set_selected_tags(self, tags: List[str]):
        """Establecer tags seleccionados"""
        for tag, checkbox in self.tag_checkboxes.items():
            checkbox.setChecked(tag in tags)
        self.update_selected_tags_display()

    def set_selected_category(self, category: str):
        """Establecer categoría seleccionada"""
        for cat, checkbox in self.category_checkboxes.items():
            checkbox.setChecked(cat == category)
        self.update_selected_category_display()

    def dragEnterEvent(self, event):
        """Manejar entrada de drag & drop"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1 and urls[0].toLocalFile().endswith('.md'):
                event.accept()
            else:
                event.ignore()
        else:
            event.ignore()

    def dropEvent(self, event):
        """Manejar drop de archivos"""
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path.endswith('.md'):
                self.file_selected(file_path)
                event.accept()
            else:
                QMessageBox.warning(self, "Error", "Solo se aceptan archivos .md")
                event.ignore()

    def file_selected(self, file_path: str):
        """Archivo seleccionado"""
        self.selected_file = file_path
        file_path_obj = Path(file_path)
        file_name = file_path_obj.name

        # Mostrar información del archivo
        self.fileInfoLabel.setText(f"📄 Archivo cargado: {file_name}")
        self.fileInfoLabel.setStyleSheet("""
            font-weight: bold;
            color: #28a745;
            padding: 10px;
            border: 2px solid #28a745;
            border-radius: 5px;
            text-align: center;
        """)
        self.fileInfoLabel.setToolTip(f"Ruta completa: {file_path}")

        # Auto-completar título
        title = self.convert_title(file_name)
        self.titleLineEdit.setText(title)

        # Extraer y seleccionar tags
        extracted_tags = self.extract_tags_from_file(file_path)
        self.set_selected_tags(extracted_tags)

        # Habilitar botón de procesamiento
        self.processButton.setEnabled(True)

        # Actualizar barra de estado
        self.statusbar.showMessage(f"Archivo cargado: {file_name}")

    def load_file_directly(self, file_path: str):
        """Cargar archivo directamente (usado desde argumentos de línea de comandos)"""
        try:
            self.file_selected(file_path)
            # Dar foco al campo de descripción para facilitar la edición
            self.descriptionTextEdit.setFocus()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error cargando archivo:\n{str(e)}")

    def convert_title(self, filename: str) -> str:
        """Convertir nombre de archivo a título"""
        # Remover extensión y reemplazar guiones/underscores por espacios
        title = Path(filename).stem
        title = re.sub(r'[-_]', ' ', title)
        # Capitalizar cada palabra
        return title.title()

    def extract_tags_from_file(self, file_path: str) -> List[str]:
        """Extraer tags del archivo de Obsidian"""
        tags = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

                # Buscar tags en frontmatter YAML
                yaml_match = re.search(r'^---\s*\n(.*?)\n---', content, re.MULTILINE | re.DOTALL)
                if yaml_match:
                    yaml_content = yaml_match.group(1)

                    # Formato: tags: [tag1, tag2, tag3]
                    list_match = re.search(r'tags:\s*\[(.*?)\]', yaml_content)
                    if list_match:
                        tag_content = list_match.group(1)
                        tags.extend([tag.strip(' "\'') for tag in tag_content.split(',') if tag.strip()])

                    # Formato lista YAML
                    else:
                        in_tags = False
                        for line in yaml_content.split('\n'):
                            if line.strip() == 'tags:':
                                in_tags = True
                            elif in_tags and line.strip().startswith('- '):
                                tag = line.strip()[2:].strip(' "\'')
                                if tag:
                                    tags.append(tag)
                            elif in_tags and not line.startswith(' ') and line.strip():
                                break

                # Buscar tags inline (#tag)
                inline_tags = re.findall(r'#([a-zA-Z0-9_-]+)', content)
                tags.extend(inline_tags)

        except Exception as e:
            print(f"Error extrayendo tags: {e}")

        return list(set(tags))  # Remover duplicados

    def open_file_dialog(self):
        """Abrir diálogo para seleccionar archivo"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar archivo Markdown",
            "/mnt/windows/FTP/wiki/Obsidian/",
            "Archivos Markdown (*.md);;Todos los archivos (*)"
        )

        if file_path:
            self.file_selected(file_path)

    def toggle_all_blogs(self, checked: bool):
        """Toggle para todos los blogs"""
        if checked:
            self.blogNotasCheckBox.setChecked(True)
            self.blogMihitasCheckBox.setChecked(True)
            self.blogNotasCheckBox.setEnabled(False)
            self.blogMihitasCheckBox.setEnabled(False)
        else:
            self.blogNotasCheckBox.setEnabled(True)
            self.blogMihitasCheckBox.setEnabled(True)

    def show_shortcuts_help(self):
        """Mostrar ayuda de atajos de teclado"""
        help_text = """
<h3>⌨️ Atajos de Teclado</h3>

<h4>📂 Categorías:</h4>
<ul>
<li><b>1-9:</b> Seleccionar categoría por número (exclusivo)</li>
</ul>

<h4>🏷️ Tags:</h4>
<ul>
<li><b>Alt+1 a Alt+9:</b> Toggle tags por número</li>
</ul>

<h4>📄 Archivos:</h4>
<ul>
<li><b>Ctrl+O:</b> Abrir archivo desde diálogo</li>
<li><b>Drag & Drop:</b> Arrastra archivos .md a la zona indicada</li>
</ul>

<h4>⚡ Procesamiento:</h4>
<ul>
<li><b>Enter:</b> Procesar post</li>
<li><b>Escape:</b> Cancelar/cerrar</li>
</ul>

<h4>🎨 Temas:</h4>
<ul>
<li><b>Selector en barra de estado:</b> Cambiar tema</li>
<li><b>Menú Temas:</b> Acceso rápido a todos los temas</li>
</ul>
        """

        QMessageBox.information(self, "Atajos de Teclado", help_text)

    def show_about(self):
        """Mostrar información sobre la aplicación"""
        current_theme = self.theme_manager.current_theme.replace('-', ' ').title()

        about_text = f"""
<h3>🚀 Creador de Posts v2.2</h3>
<p><b>Conversor de notas Obsidian a posts Hugo</b></p>

<p>📝 <b>Características:</b></p>
<ul>
<li>Interfaz gráfica moderna con PyQt6</li>
<li>🎨 <b>Sistema de temas dinámicos</b></li>
<li>📂 <b>Gestor de categorías con JSON</b></li>
<li>🏷️ <b>Gestor de tags inteligente</b></li>
<li>📄 <b>Drag & Drop para archivos</b></li>
<li>Soporte para múltiples blogs</li>
<li>Selector de imágenes integrado</li>
<li>Git integration automática</li>
</ul>

<p>🎨 <b>Tema actual:</b> {current_theme}</p>
<p>📁 <b>Temas disponibles:</b> {len(self.theme_manager.themes)}</p>
<p>📂 <b>Categorías:</b> {len(self.category_manager.categories)}</p>
<p>🏷️ <b>Tags:</b> {len(self.tag_manager.tags)}</p>

<p>⚡ <b>Hotkeys numerados para máxima rapidez</b></p>

<p>🔧 Desarrollado con PyQt6 + Qt Designer + YAML Themes + JSON Data</p>
        """

        QMessageBox.about(self, "Acerca de Creador de Posts", about_text)

    def process_post(self):
        """Procesar el post"""
        if not self.selected_file:
            QMessageBox.warning(self, "Error", "Por favor selecciona un archivo primero usando Ctrl+O o arrastrándolo")
            return

        # Validar entrada
        title = self.titleLineEdit.text().strip()
        if not title:
            QMessageBox.warning(self, "Error", "El título es obligatorio")
            return

        description = self.descriptionTextEdit.toPlainText().strip()
        category = self.get_selected_category()

        # Obtener blogs seleccionados
        blogs = []
        if self.allBlogsCheckBox.isChecked():
            blogs = ['notas', 'mihitas']
        else:
            if self.blogNotasCheckBox.isChecked():
                blogs.append('notas')
            if self.blogMihitasCheckBox.isChecked():
                blogs.append('mihitas')

        if not blogs:
            QMessageBox.warning(self, "Error", "Selecciona al menos un blog")
            return

        # Validar categoría si es necesario
        if 'notas' in blogs and not category:
            QMessageBox.warning(self, "Error", "La categoría es obligatoria para el blog notas")
            return

        # Obtener tags seleccionados
        tags = self.get_selected_tags()

        # Mostrar interfaz de progreso
        self.progressBar.setVisible(True)
        self.progressLogTextEdit.setVisible(True)
        self.progressBar.setRange(0, 0)  # Progreso indeterminado
        self.processButton.setEnabled(False)

        # Actualizar barra de estado
        self.statusbar.showMessage("Procesando post...")

        # Iniciar procesamiento en thread separado
        self.process_thread = ProcessThread(
            self.selected_file, blogs, title, tags, description, category
        )
        self.process_thread.progress_updated.connect(self.update_progress)
        self.process_thread.finished_successfully.connect(self.process_finished)
        self.process_thread.error_occurred.connect(self.process_error)
        self.process_thread.start()

    def update_progress(self, message: str):
        """Actualizar progreso"""
        self.progressLogTextEdit.append(message)
        # Auto-scroll al final
        scrollbar = self.progressLogTextEdit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

        # Actualizar barra de estado también
        self.statusbar.showMessage(message)

    def process_finished(self, message: str):
        """Procesamiento finalizado exitosamente"""
        self.progressBar.setVisible(False)
        self.progressBar.setRange(0, 100)
        self.processButton.setEnabled(True)

        self.statusbar.showMessage("✅ Post procesado exitosamente", 5000)

        QMessageBox.information(self, "✅ Éxito", message)

        # Limpiar formulario
        self.reset_form()

    def process_error(self, error: str):
        """Error en el procesamiento"""
        self.progressBar.setVisible(False)
        self.progressBar.setRange(0, 100)
        self.processButton.setEnabled(True)

        self.statusbar.showMessage("❌ Error en procesamiento", 5000)

        QMessageBox.critical(self, "❌ Error", f"Error procesando post:\n{error}")

    def reset_form(self):
        """Resetear formulario"""
        self.selected_file = None
        self.fileInfoLabel.setText("📄 Arrastra aquí un archivo .md o usa Ctrl+O para abrir")
        self.fileInfoLabel.setStyleSheet("""
            font-weight: bold;
            color: #0078d4;
            padding: 10px;
            border: 2px dashed #0078d4;
            border-radius: 5px;
            text-align: center;
        """)

        self.titleLineEdit.clear()
        self.descriptionTextEdit.clear()

        # Desmarcar todos los checkboxes
        for checkbox in self.tag_checkboxes.values():
            checkbox.setChecked(False)
        for checkbox in self.category_checkboxes.values():
            checkbox.setChecked(False)

        self.blogNotasCheckBox.setChecked(False)
        self.blogMihitasCheckBox.setChecked(False)
        self.allBlogsCheckBox.setChecked(False)

        self.progressLogTextEdit.clear()
        self.progressLogTextEdit.setVisible(False)
        self.processButton.setEnabled(False)

        # Actualizar displays
        self.update_selected_tags_display()
        self.update_selected_category_display()

        self.statusbar.showMessage("Formulario reiniciado", 3000)


def main():
    """Función principal"""
    import argparse

    # Procesar argumentos
    parser = argparse.ArgumentParser(description='Conversor de notas Obsidian a Hugo (PyQt6 + UI + Themes)')
    parser.add_argument('markdown_file', nargs='?', help='Archivo markdown de Obsidian a procesar')
    parser.add_argument('--all', action='store_true', help='Preseleccionar todos los blogs')
    parser.add_argument('--theme', default='tokyo-night', help='Tema a usar (ver themes.yml)')
    parser.add_argument('--list-themes', action='store_true', help='Listar temas disponibles')
    args = parser.parse_args()

    # Crear aplicación
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Estilo moderno

    # Si solo se pide listar temas
    if args.list_themes:
        theme_manager = ThemeManager()
        print("🎨 Temas disponibles:")
        for theme_name in theme_manager.get_theme_names():
            print(f"  • {theme_name}")
        sys.exit(0)

    # Validar archivo si se proporciona
    if args.markdown_file:
        markdown_path = Path(args.markdown_file)
        if not markdown_path.exists():
            print(f"Error: El archivo '{args.markdown_file}' no existe")
            sys.exit(1)

        if not markdown_path.suffix.lower() == '.md':
            print(f"Error: El archivo debe tener extensión .md")
            sys.exit(1)

    # Validar tema
    theme_manager = ThemeManager()
    if args.theme not in theme_manager.get_theme_names():
        print(f"Error: Tema '{args.theme}' no encontrado")
        print("Temas disponibles:")
        for theme_name in theme_manager.get_theme_names():
            print(f"  • {theme_name}")
        sys.exit(1)

    # Crear ventana principal
    try:
        window = PostCreator(args.theme)
    except Exception as e:
        QMessageBox.critical(None, "Error Fatal",
            f"No se pudo inicializar la aplicación:\n{str(e)}")
        sys.exit(1)

    # Si se especificó un archivo, cargarlo automáticamente
    if args.markdown_file:
        # Pre-cargar el archivo especificado
        QTimer.singleShot(100, lambda: window.load_file_directly(str(markdown_path.absolute())))

    # Si se especificó --all, preseleccionar todos los blogs
    if args.all:
        QTimer.singleShot(200, lambda: window.allBlogsCheckBox.setChecked(True))

    window.show()

    # Mensaje de bienvenida con tema
    theme_name = args.theme.replace('-', ' ').title()
    window.statusbar.showMessage(f"🎨 Tema {theme_name} cargado | 📝 Listo para crear posts", 5000)

    # Ejecutar aplicación
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
