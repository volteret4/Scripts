#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import json
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                            QWidget, QLineEdit, QListWidget, QListWidgetItem,
                            QPushButton, QDialog, QLabel, QTextEdit, QMessageBox,
                            QSplitter, QFrame, QGridLayout, QScrollArea)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QClipboard, QKeySequence, QShortcut, QAction, QKeyEvent
import unicodedata
import subprocess
import platform

class EmojiData:
    """Clase para manejar los datos de emojis y sus tags"""

    def __init__(self):
        self.data_file = "emoji_tags.json"
        self.emojis_with_tags = self.load_emoji_data()

    def get_all_emojis(self):
        """Obtiene todos los emojis disponibles en Unicode"""
        emojis = []

        # Rangos principales de emojis en Unicode
        emoji_ranges = [
            (0x1F600, 0x1F64F),  # Emoticons
            (0x1F300, 0x1F5FF),  # Símbolos y pictogramas misceláneos
            (0x1F680, 0x1F6FF),  # Símbolos de transporte y mapas
            (0x1F700, 0x1F77F),  # Símbolos alquímicos
            (0x1F780, 0x1F7FF),  # Símbolos geométricos extendidos
            (0x1F800, 0x1F8FF),  # Flechas suplementarias-C
            (0x1F900, 0x1F9FF),  # Símbolos y pictogramas suplementarios
            (0x1FA00, 0x1FA6F),  # Símbolos de ajedrez extendidos
            (0x1FA70, 0x1FAFF),  # Símbolos y pictogramas extendidos-A
            (0x2600, 0x26FF),    # Símbolos misceláneos
            (0x2700, 0x27BF),    # Dingbats
            (0x1F1E6, 0x1F1FF),  # Símbolos de banderas regionales
        ]

        for start, end in emoji_ranges:
            for codepoint in range(start, end + 1):
                try:
                    char = chr(codepoint)
                    category = unicodedata.category(char)
                    if category.startswith('So') or category.startswith('Sm'):  # Symbol, other o Symbol, math
                        try:
                            name = unicodedata.name(char, "").lower()
                            if name:
                                emojis.append({
                                    'emoji': char,
                                    'name': name.replace('_', ' '),
                                    'codepoint': hex(codepoint)
                                })
                        except:
                            # Si no tiene nombre Unicode, usar el carácter como nombre
                            emojis.append({
                                'emoji': char,
                                'name': f"emoji_{hex(codepoint)}",
                                'codepoint': hex(codepoint)
                            })
                except (ValueError, OverflowError):
                    continue

        # Algunos emojis adicionales comunes
        additional_emojis = [
            '😀', '😃', '😄', '😁', '😆', '😅', '🤣', '😂', '🙂', '🙃',
            '😉', '😊', '😇', '🥰', '😍', '🤩', '😘', '😗', '😚', '😙',
            '😋', '😛', '😜', '🤪', '😝', '🤑', '🤗', '🤭', '🤫', '🤔',
            '🤐', '🤨', '😐', '😑', '😶', '😏', '😒', '🙄', '😬', '🤥',
            '😔', '😪', '🤤', '😴', '😷', '🤒', '🤕', '🤢', '🤮', '🤧',
            '🥵', '🥶', '🥴', '😵', '🤯', '🤠', '🥳', '😎', '🤓', '🧐',
            '🍎', '🍊', '🍋', '🍌', '🍉', '🍇', '🍓', '🍈', '🍒', '🍑',
            '🥭', '🍍', '🥥', '🥝', '🍅', '🍆', '🥑', '🥦', '🥬', '🥒',
            '🌶️', '🌽', '🥕', '🧄', '🧅', '🥔', '🍠', '🥐', '🥖', '🍞',
            '🥨', '🥯', '🧀', '🥚', '🍳', '🧈', '🥞', '🧇', '🥓', '🥩',
            '🍗', '🍖', '🦴', '🌭', '🍔', '🍟', '🍕', '🥪', '🥙', '🧆',
            '🌮', '🌯', '🥗', '🥘', '🥫', '🍝', '🍜', '🍲', '🍛', '🍣',
            '🍱', '🥟', '🦪', '🍤', '🍙', '🍚', '🍘', '🍥', '🥠', '🥮',
            '🍢', '🍡', '🍧', '🍨', '🍦', '🥧', '🧁', '🍰', '🎂', '🍮',
            '🍭', '🍬', '🍫', '🍿', '🍩', '🍪', '🌰', '🥜', '🍯', '🥛',
            '🍼', '☕', '🍵', '🧃', '🥤', '🍶', '🍺', '🍻', '🥂', '🍷',
            '🥃', '🍸', '🍹', '🧉', '⚽', '🏀', '🏈', '⚾', '🥎', '🎾',
            '🏐', '🏉', '🥏', '🎱', '🪀', '🏓', '🏸', '🏒', '🏑', '🥍',
            '🏏', '⛳', '🪁', '🏹', '🎣', '🤿', '🥊', '🥋', '🎽', '🛹',
            '🛷', '⛸️', '🥌', '🎿', '⛷️', '🏂', '🪂', '🏋️', '🤼', '🤸',
            '⛹️', '🤺', '🤾', '🏌️', '🏇', '🧘', '🏄', '🏊', '🤽', '🚣',
            '🧗', '🚵', '🚴', '🏆', '🥇', '🥈', '🥉', '🏅', '🎖️', '🏵️',
            '🎗️', '🎫', '🎟️', '🎪', '🤹', '🎭', '🩰', '🎨', '🎬', '🎤',
            '🎧', '🎼', '🎵', '🎶', '🥁', '🎷', '🎺', '🎸', '🪕', '🎻',
            '🎲', '♟️', '🎯', '🎳', '🎮', '🎰', '🧩', '🚗', '🚕', '🚙',
            '🚌', '🚎', '🏎️', '🚓', '🚑', '🚒', '🚐', '🚚', '🚛', '🚜',
            '🦯', '🦽', '🦼', '🛴', '🚲', '🛵', '🏍️', '🛺', '🚨', '🚔',
            '🚍', '🚘', '🚖', '🚡', '🚠', '🚟', '🚃', '🚋', '🚞', '🚝',
            '🚄', '🚅', '🚈', '🚂', '🚆', '🚇', '🚊', '🚉', '✈️', '🛫',
            '🛬', '🛩️', '💺', '🛰️', '🚀', '🛸', '🚁', '🛶', '⛵', '🚤',
            '🛥️', '🛳️', '⛴️', '🚢', '⚓', '⛽', '🚧', '🚦', '🚥', '🗺️',
            '🗿', '🗽', '🗼', '🏰', '🏯', '🏟️', '🎡', '🎢', '🎠', '⛲',
            '⛱️', '🏖️', '🏝️', '🏜️', '🌋', '⛰️', '🏔️', '🗻', '🏕️', '⛺',
            '🏠', '🏡', '🏘️', '🏚️', '🏗️', '🏭', '🏢', '🏬', '🏣', '🏤',
            '🏥', '🏦', '🏨', '🏪', '🏫', '🏩', '💒', '🏛️', '⛪', '🕌',
            '🕍', '🛕'
        ]

        for emoji in additional_emojis:
            if not any(e['emoji'] == emoji for e in emojis):
                try:
                    name = unicodedata.name(emoji[0] if len(emoji) > 1 else emoji, emoji).lower()
                    codepoint = hex(ord(emoji[0]) if len(emoji) > 1 else ord(emoji))
                    emojis.append({
                        'emoji': emoji,
                        'name': name.replace('_', ' '),
                        'codepoint': codepoint
                    })
                except:
                    # Manejar emojis multi-byte
                    try:
                        if len(emoji) == 1:
                            codepoint = hex(ord(emoji))
                        else:
                            # Para emojis compuestos, usar el primer carácter
                            codepoint = hex(ord(emoji[0]))

                        emojis.append({
                            'emoji': emoji,
                            'name': emoji,
                            'codepoint': codepoint
                        })
                    except:
                        continue

        return emojis

    def load_emoji_data(self):
        """Carga los datos de emojis con tags desde archivo"""
        emojis = self.get_all_emojis()

        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    saved_data = json.load(f)

                # Combinar datos guardados con lista completa
                for emoji_data in emojis:
                    emoji = emoji_data['emoji']
                    if emoji in saved_data:
                        emoji_data['tags'] = saved_data[emoji].get('tags', [])
                    else:
                        emoji_data['tags'] = []
            except:
                for emoji_data in emojis:
                    emoji_data['tags'] = []
        else:
            for emoji_data in emojis:
                emoji_data['tags'] = []

        return emojis

    def save_emoji_data(self):
        """Guarda los datos de emojis con tags en archivo"""
        data_to_save = {}
        for emoji_data in self.emojis_with_tags:
            if emoji_data['tags']:  # Solo guardar si tiene tags
                data_to_save[emoji_data['emoji']] = {
                    'tags': emoji_data['tags']
                }

        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error guardando datos: {e}")

    def update_emoji_tags(self, emoji, tags):
        """Actualiza los tags de un emoji"""
        for emoji_data in self.emojis_with_tags:
            if emoji_data['emoji'] == emoji:
                emoji_data['tags'] = tags
                break
        self.save_emoji_data()


class EditTagsDialog(QDialog):
    """Diálogo para editar tags de un emoji"""

    def __init__(self, parent, emoji, current_tags):
        super().__init__(parent)
        self.emoji = emoji
        self.current_tags = current_tags
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle(f"Editar tags para {self.emoji}")
        self.setModal(True)
        self.resize(400, 300)

        layout = QVBoxLayout(self)

        # Mostrar el emoji
        emoji_label = QLabel(self.emoji)
        emoji_label.setFont(QFont("", 48))
        emoji_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(emoji_label)

        # Instrucciones
        instructions = QLabel("Ingresa los tags separados por comas:")
        layout.addWidget(instructions)

        # Campo de texto para tags
        self.tags_edit = QTextEdit()
        self.tags_edit.setPlainText(', '.join(self.current_tags))
        self.tags_edit.setMaximumHeight(150)
        layout.addWidget(self.tags_edit)

        # Botones
        button_layout = QHBoxLayout()

        save_btn = QPushButton("Guardar")
        save_btn.clicked.connect(self.accept)
        button_layout.addWidget(save_btn)

        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        # Foco inicial en el campo de texto
        self.tags_edit.setFocus()

    def get_tags(self):
        """Obtiene los tags editados"""
        text = self.tags_edit.toPlainText().strip()
        if not text:
            return []

        tags = [tag.strip() for tag in text.split(',')]
        return [tag for tag in tags if tag]  # Filtrar tags vacíos


class EmojiGridWidget(QWidget):
    """Widget personalizado para mostrar emojis en cuadrícula"""

    emojiSelected = pyqtSignal(dict)  # Señal cuando se selecciona un emoji

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_index = 0
        self.emoji_buttons = []
        self.emoji_data_list = []
        self.setup_ui()

    def setup_ui(self):
        # Área de scroll
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Widget contenedor para la cuadrícula
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(5)

        self.scroll_area.setWidget(self.grid_widget)

        # Layout principal
        layout = QVBoxLayout(self)
        layout.addWidget(self.scroll_area)
        layout.setContentsMargins(0, 0, 0, 0)

    def load_emojis(self, emoji_data_list):
        """Carga emojis en la cuadrícula"""
        # Limpiar cuadrícula anterior
        self.clear_grid()

        self.emoji_data_list = emoji_data_list
        self.emoji_buttons = []

        cols = 8  # Número de columnas
        row, col = 0, 0

        for i, emoji_data in enumerate(emoji_data_list):
            btn = QPushButton(emoji_data['emoji'])
            btn.setFont(QFont("", 24))
            btn.setFixedSize(60, 60)
            btn.setToolTip(f"{emoji_data['name']}\nTags: {', '.join(emoji_data['tags']) if emoji_data['tags'] else 'ninguno'}")
            btn.clicked.connect(lambda checked, data=emoji_data: self.emojiSelected.emit(data))

            # Estilo especial para el botón
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2a2a35;
                    border: 2px solid transparent;
                    border-radius: 8px;
                }
                QPushButton:hover {
                    border-color: #9a7ecc;
                    background-color: #32323f;
                }
                QPushButton:focus {
                    border-color: #b59bd6;
                    background-color: #9a7ecc;
                }
            """)

            self.grid_layout.addWidget(btn, row, col)
            self.emoji_buttons.append(btn)

            col += 1
            if col >= cols:
                col = 0
                row += 1

        # Seleccionar el primer emoji por defecto
        if self.emoji_buttons:
            self.selected_index = 0
            self.update_selection()

    def clear_grid(self):
        """Limpia la cuadrícula"""
        while self.grid_layout.count():
            child = self.grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def keyPressEvent(self, event):
        """Maneja navegación con teclado"""
        if not self.emoji_buttons:
            return

        cols = 8
        total = len(self.emoji_buttons)

        if event.key() == Qt.Key.Key_Up:
            if self.selected_index >= cols:
                self.selected_index -= cols
                self.update_selection()
                event.accept()
                return
        elif event.key() == Qt.Key.Key_Down:
            if self.selected_index + cols < total:
                self.selected_index += cols
                self.update_selection()
                event.accept()
                return
        elif event.key() == Qt.Key.Key_Left:
            if self.selected_index > 0:
                self.selected_index -= 1
                self.update_selection()
                event.accept()
                return
        elif event.key() == Qt.Key.Key_Right:
            if self.selected_index < total - 1:
                self.selected_index += 1
                self.update_selection()
                event.accept()
                return
        elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            if 0 <= self.selected_index < len(self.emoji_data_list):
                self.emojiSelected.emit(self.emoji_data_list[self.selected_index])
                event.accept()
                return

        super().keyPressEvent(event)

    def update_selection(self):
        """Actualiza la selección visual"""
        for i, btn in enumerate(self.emoji_buttons):
            if i == self.selected_index:
                btn.setFocus()
                # Hacer scroll para que el botón sea visible
                self.scroll_area.ensureWidgetVisible(btn)
                # Emitir señal de selección
                if i < len(self.emoji_data_list):
                    self.emojiSelected.emit(self.emoji_data_list[i])
            else:
                btn.clearFocus()

    def get_selected_emoji_data(self):
        """Obtiene los datos del emoji seleccionado"""
        if 0 <= self.selected_index < len(self.emoji_data_list):
            return self.emoji_data_list[self.selected_index]
        return None


class EmojiManager(QMainWindow):
    """Ventana principal del gestor de emojis"""

    def __init__(self):
        super().__init__()
        self.emoji_data = EmojiData()
        self.clipboard = QApplication.clipboard()
        self.is_grid_view = False  # False = lista, True = cuadrícula
        self.setup_ui()
        self.setup_shortcuts()
        self.load_emojis()

    def setup_ui(self):
        self.setWindowTitle("Gestor de Emojis")
        self.setGeometry(100, 100, 1000, 700)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        # Campo de búsqueda y controles
        search_layout = QHBoxLayout()

        search_label = QLabel("Buscar:")
        search_layout.addWidget(search_label)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Busca por nombre o tags...")
        self.search_edit.textChanged.connect(self.filter_emojis)
        search_layout.addWidget(self.search_edit)

        clear_btn = QPushButton("Limpiar")
        clear_btn.clicked.connect(self.clear_search)
        search_layout.addWidget(clear_btn)

        # Botón para cambiar vista
        self.view_btn = QPushButton("Vista Cuadrícula")
        self.view_btn.clicked.connect(self.toggle_view)
        search_layout.addWidget(self.view_btn)

        layout.addLayout(search_layout)

        # Splitter para dividir la vista
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # Container para las vistas (lista o cuadrícula)
        self.view_container = QWidget()
        self.view_layout = QVBoxLayout(self.view_container)
        self.view_layout.setContentsMargins(0, 0, 0, 0)

        # Vista de lista
        self.emoji_list = QListWidget()
        self.emoji_list.setFont(QFont("", 16))
        self.emoji_list.itemDoubleClicked.connect(self.copy_emoji_and_close)
        self.emoji_list.currentItemChanged.connect(self.on_emoji_selected_list)

        # Vista de cuadrícula
        self.emoji_grid = EmojiGridWidget(self)
        self.emoji_grid.emojiSelected.connect(self.on_emoji_selected_grid)
        self.emoji_grid.hide()

        self.view_layout.addWidget(self.emoji_list)
        self.view_layout.addWidget(self.emoji_grid)

        splitter.addWidget(self.view_container)

        # Panel de información
        info_panel = QFrame()
        info_panel.setFrameStyle(QFrame.Shape.StyledPanel)
        info_layout = QVBoxLayout(info_panel)

        self.selected_emoji_label = QLabel("")
        self.selected_emoji_label.setFont(QFont("", 72))  # Mucho más grande
        self.selected_emoji_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.selected_emoji_label.setMinimumHeight(120)
        info_layout.addWidget(self.selected_emoji_label)

        self.emoji_info_label = QLabel("")
        self.emoji_info_label.setWordWrap(True)
        info_layout.addWidget(self.emoji_info_label)

        self.tags_label = QLabel("")
        self.tags_label.setWordWrap(True)
        info_layout.addWidget(self.tags_label)

        # Botones de acción
        action_layout = QHBoxLayout()

        copy_btn = QPushButton("Copiar y Cerrar (Enter)")
        copy_btn.clicked.connect(self.copy_selected_emoji_and_close)
        action_layout.addWidget(copy_btn)

        edit_tags_btn = QPushButton("Editar Tags (Ctrl+E)")
        edit_tags_btn.clicked.connect(self.edit_tags)
        action_layout.addWidget(edit_tags_btn)

        info_layout.addLayout(action_layout)
        info_layout.addStretch()

        splitter.addWidget(info_panel)
        splitter.setSizes([600, 400])

        # Barra de estado
        self.status_label = QLabel(f"Total: {len(self.emoji_data.emojis_with_tags)} emojis")
        self.statusBar().addWidget(self.status_label)

    def setup_shortcuts(self):
        """Configura atajos de teclado"""
        # Enter para copiar y cerrar
        copy_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Return), self)
        copy_shortcut.activated.connect(self.copy_selected_emoji_and_close)

        copy_shortcut2 = QShortcut(QKeySequence(Qt.Key.Key_Enter), self)
        copy_shortcut2.activated.connect(self.copy_selected_emoji_and_close)

        # Ctrl+E para editar tags
        edit_shortcut = QShortcut(QKeySequence("Ctrl+E"), self)
        edit_shortcut.activated.connect(self.edit_tags)

        # Ctrl+F para buscar
        search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        search_shortcut.activated.connect(self.focus_search)

        # Escape para limpiar búsqueda
        clear_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        clear_shortcut.activated.connect(self.clear_search)

        # Flechas arriba/abajo para navegar emojis desde cualquier lugar
        up_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Up), self)
        up_shortcut.activated.connect(self.navigate_up)

        down_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Down), self)
        down_shortcut.activated.connect(self.navigate_down)

        left_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Left), self)
        left_shortcut.activated.connect(self.navigate_left)

        right_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Right), self)
        right_shortcut.activated.connect(self.navigate_right)

    def navigate_up(self):
        """Navega hacia arriba en la lista/cuadrícula"""
        if self.is_grid_view:
            # Dar foco a la cuadrícula y enviar evento
            self.emoji_grid.setFocus()
            event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Up, Qt.KeyboardModifier.NoModifier)
            self.emoji_grid.keyPressEvent(event)
        else:
            self.emoji_list.setFocus()
            current_row = self.emoji_list.currentRow()
            if current_row > 0:
                self.emoji_list.setCurrentRow(current_row - 1)

    def navigate_down(self):
        """Navega hacia abajo en la lista/cuadrícula"""
        if self.is_grid_view:
            self.emoji_grid.setFocus()
            event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier)
            self.emoji_grid.keyPressEvent(event)
        else:
            self.emoji_list.setFocus()
            current_row = self.emoji_list.currentRow()
            if current_row < self.emoji_list.count() - 1:
                self.emoji_list.setCurrentRow(current_row + 1)

    def navigate_left(self):
        """Navega hacia la izquierda (solo en cuadrícula)"""
        if self.is_grid_view:
            self.emoji_grid.setFocus()
            event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Left, Qt.KeyboardModifier.NoModifier)
            self.emoji_grid.keyPressEvent(event)

    def navigate_right(self):
        """Navega hacia la derecha (solo en cuadrícula)"""
        if self.is_grid_view:
            self.emoji_grid.setFocus()
            event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier)
            self.emoji_grid.keyPressEvent(event)

    def toggle_view(self):
        """Cambia entre vista de lista y cuadrícula"""
        self.is_grid_view = not self.is_grid_view

        if self.is_grid_view:
            self.emoji_list.hide()
            self.emoji_grid.show()
            self.emoji_grid.setFocus()
            self.view_btn.setText("Vista Lista")
            # Cargar emojis en cuadrícula
            self.load_emojis_grid()
        else:
            self.emoji_grid.hide()
            self.emoji_list.show()
            self.emoji_list.setFocus()
            self.view_btn.setText("Vista Cuadrícula")

    def load_emojis(self):
        """Carga todos los emojis en la vista actual"""
        if self.is_grid_view:
            self.load_emojis_grid()
        else:
            self.load_emojis_list()

    def load_emojis_list(self):
        """Carga emojis en vista de lista"""
        self.emoji_list.clear()

        for emoji_data in self.emoji_data.emojis_with_tags:
            item = QListWidgetItem()
            item_text = f"{emoji_data['emoji']} - {emoji_data['name']}"
            if emoji_data['tags']:
                item_text += f" ({', '.join(emoji_data['tags'])})"

            item.setText(item_text)
            item.setData(Qt.ItemDataRole.UserRole, emoji_data)
            self.emoji_list.addItem(item)

        self.update_status()

    def load_emojis_grid(self):
        """Carga emojis en vista de cuadrícula"""
        search_text = self.search_edit.text().lower()

        if search_text:
            # Filtrar emojis
            filtered_emojis = []
            for emoji_data in self.emoji_data.emojis_with_tags:
                matches = (search_text in emoji_data['name'].lower() or
                          any(search_text in tag.lower() for tag in emoji_data['tags']))
                if matches:
                    filtered_emojis.append(emoji_data)
            self.emoji_grid.load_emojis(filtered_emojis)
        else:
            self.emoji_grid.load_emojis(self.emoji_data.emojis_with_tags)

        self.update_status()

    def filter_emojis(self):
        """Filtra emojis según el texto de búsqueda"""
        if self.is_grid_view:
            self.load_emojis_grid()
        else:
            search_text = self.search_edit.text().lower()

            if not search_text:
                self.load_emojis_list()
                return

            self.emoji_list.clear()
            filtered_count = 0

            for emoji_data in self.emoji_data.emojis_with_tags:
                matches = (search_text in emoji_data['name'].lower() or
                          any(search_text in tag.lower() for tag in emoji_data['tags']))

                if matches:
                    item = QListWidgetItem()
                    item_text = f"{emoji_data['emoji']} - {emoji_data['name']}"
                    if emoji_data['tags']:
                        item_text += f" ({', '.join(emoji_data['tags'])})"

                    item.setText(item_text)
                    item.setData(Qt.ItemDataRole.UserRole, emoji_data)
                    self.emoji_list.addItem(item)
                    filtered_count += 1

            self.status_label.setText(f"Mostrando: {filtered_count} / {len(self.emoji_data.emojis_with_tags)} emojis")

    def clear_search(self):
        """Limpia el campo de búsqueda"""
        self.search_edit.clear()
        self.search_edit.setFocus()

    def focus_search(self):
        """Pone el foco en el campo de búsqueda"""
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    def on_emoji_selected_list(self, current, previous):
        """Maneja la selección de un emoji en vista de lista"""
        if current is None:
            return

        emoji_data = current.data(Qt.ItemDataRole.UserRole)
        if emoji_data:
            self.update_emoji_info(emoji_data)

    def on_emoji_selected_grid(self, emoji_data):
        """Maneja la selección de un emoji en vista de cuadrícula"""
        self.update_emoji_info(emoji_data)

    def update_emoji_info(self, emoji_data):
        """Actualiza la información del emoji seleccionado"""
        self.selected_emoji_label.setText(emoji_data['emoji'])

        info_text = f"Nombre: {emoji_data['name']}\n"
        info_text += f"Código: {emoji_data['codepoint']}"
        self.emoji_info_label.setText(info_text)

        if emoji_data['tags']:
            tags_text = f"Tags: {', '.join(emoji_data['tags'])}"
        else:
            tags_text = "Tags: (ninguno)"
        self.tags_label.setText(tags_text)

    def copy_emoji_and_close(self, item):
        """Copia emoji y cierra ventana (doble clic)"""
        emoji_data = item.data(Qt.ItemDataRole.UserRole)
        if emoji_data:
            self.copy_and_paste_emoji(emoji_data['emoji'])
            self.close()

    def copy_selected_emoji_and_close(self):
        """Copia el emoji seleccionado y cierra la ventana"""
        emoji_data = None

        if self.is_grid_view:
            emoji_data = self.emoji_grid.get_selected_emoji_data()
        else:
            current_item = self.emoji_list.currentItem()
            if current_item:
                emoji_data = current_item.data(Qt.ItemDataRole.UserRole)

        if emoji_data:
            self.copy_and_paste_emoji(emoji_data['emoji'])
            self.close()

    def copy_and_paste_emoji(self, emoji):
        """Copia emoji al portapapeles y lo pega"""
        self.clipboard.setText(emoji)
        self.statusBar().showMessage(f"Copiado: {emoji}", 2000)

        # Intentar pegar automáticamente
        try:
            if platform.system() == "Linux":
                # En Linux, usar xdotool para pegar
                subprocess.run(["copyq", "add", emoji])

            elif platform.system() == "Windows":
                # En Windows, usar pyautogui si está disponible
                try:
                    import pyautogui
                    pyautogui.hotkey('ctrl', 'v')
                except ImportError:
                    pass
        except:
            # Si falla el pegado automático, solo copiar
            pass

    def edit_tags(self):
        """Abre diálogo para editar tags"""
        emoji_data = None

        if self.is_grid_view:
            emoji_data = self.emoji_grid.get_selected_emoji_data()
        else:
            current_item = self.emoji_list.currentItem()
            if current_item:
                emoji_data = current_item.data(Qt.ItemDataRole.UserRole)

        if not emoji_data:
            QMessageBox.information(self, "Info", "Selecciona un emoji primero")
            return

        # Guardar el emoji actual para re-seleccionarlo después
        current_emoji = emoji_data['emoji']

        dialog = EditTagsDialog(self, emoji_data['emoji'], emoji_data['tags'])
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_tags = dialog.get_tags()
            self.emoji_data.update_emoji_tags(emoji_data['emoji'], new_tags)

            # Actualizar la vista
            emoji_data['tags'] = new_tags
            self.filter_emojis() if self.search_edit.text() else self.load_emojis()

            # Re-seleccionar el emoji editado
            self.select_emoji_by_character(current_emoji)

            self.statusBar().showMessage("Tags actualizados", 2000)

    def select_emoji_by_character(self, emoji_char):
        """Selecciona un emoji específico en la lista"""
        if not self.is_grid_view:
            for i in range(self.emoji_list.count()):
                item = self.emoji_list.item(i)
                emoji_data = item.data(Qt.ItemDataRole.UserRole)
                if emoji_data and emoji_data['emoji'] == emoji_char:
                    self.emoji_list.setCurrentItem(item)
                    self.on_emoji_selected_list(item, None)
                    break

    def update_status(self):
        """Actualiza la barra de estado"""
        if self.is_grid_view:
            total_shown = len(self.emoji_grid.emoji_data_list)
            total = len(self.emoji_data.emojis_with_tags)
            if self.search_edit.text():
                self.status_label.setText(f"Mostrando: {total_shown} / {total} emojis")
            else:
                self.status_label.setText(f"Total: {total} emojis")
        else:
            total = len(self.emoji_data.emojis_with_tags)
            self.status_label.setText(f"Total: {total} emojis")


def main():
    app = QApplication(sys.argv)

    # Configurar la aplicación
    app.setApplicationName("Gestor de Emojis")
    app.setOrganizationName("EmojiManager")

    # Suprimir advertencia de estilos en Linux
    app.setStyle('Fusion')  # Usar estilo Fusion que está disponible

    # Aplicar tema oscuro personalizado
    app.setStyleSheet("""
        /* Tema oscuro personalizado */
        QMainWindow {
            background-color: #14141e;
            color: white;
        }

        QWidget {
            background-color: #14141e;
            color: white;
        }

        QLineEdit {
            background-color: #2a2a35;
            border: 2px solid #9a7ecc;
            border-radius: 5px;
            padding: 5px;
            color: white;
            font-size: 14px;
        }

        QLineEdit:focus {
            border-color: #b59bd6;
            background-color: #32323f;
        }

        QListWidget {
            background-color: #1e1e2a;
            border: 1px solid #9a7ecc;
            border-radius: 5px;
            color: white;
            selection-background-color: #9a7ecc;
            selection-color: white;
            outline: none;
        }

        QListWidget::item {
            padding: 8px;
            border-bottom: 1px solid #2a2a35;
        }

        QListWidget::item:hover {
            background-color: #2a2a35;
        }

        QListWidget::item:selected {
            background-color: #9a7ecc;
            color: white;
        }

        QPushButton {
            background-color: #9a7ecc;
            color: white;
            border: none;
            border-radius: 5px;
            padding: 8px 16px;
            font-weight: bold;
            font-size: 13px;
        }

        QPushButton:hover {
            background-color: #b59bd6;
        }

        QPushButton:pressed {
            background-color: #8a6ebc;
        }

        QLabel {
            color: white;
            font-size: 13px;
        }

        QFrame {
            background-color: #1e1e2a;
            border: 1px solid #9a7ecc;
            border-radius: 5px;
        }

        QStatusBar {
            background-color: #14141e;
            color: white;
            border-top: 1px solid #9a7ecc;
        }

        QSplitter::handle {
            background-color: #9a7ecc;
            width: 3px;
        }

        QTextEdit {
            background-color: #2a2a35;
            border: 2px solid #9a7ecc;
            border-radius: 5px;
            color: white;
            padding: 5px;
            font-size: 13px;
        }

        QTextEdit:focus {
            border-color: #b59bd6;
            background-color: #32323f;
        }

        QDialog {
            background-color: #14141e;
            color: white;
        }

        QMessageBox {
            background-color: #14141e;
            color: white;
        }

        QMessageBox QPushButton {
            min-width: 80px;
            padding: 6px 12px;
        }
    """)

    # Crear y mostrar la ventana principal
    window = EmojiManager()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
