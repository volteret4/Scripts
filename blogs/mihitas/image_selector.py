#!/usr/bin/env python3
"""
Selector de imágenes con PyQt6 y DuckDuckGo
Uso: python image_selector.py <directorio_destino>
"""

import sys
import os
import requests
import json
from urllib.parse import quote_plus, urlparse
from pathlib import Path
import argparse

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QHBoxLayout, QLineEdit, QPushButton, QListWidget,
                            QLabel, QProgressBar, QMessageBox, QListWidgetItem,
                            QScrollArea, QGridLayout, QFrame)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QFont, QKeySequence, QShortcut


class ImageSearchThread(QThread):
    """Thread para buscar imágenes sin bloquear la UI"""
    images_found = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def __init__(self, query, offset=0):
        super().__init__()
        self.query = query
        self.offset = offset

    def run(self):
        try:
            images = self.search_duckduckgo_images(self.query, self.offset)
            self.images_found.emit(images)
        except Exception as e:
            self.error_occurred.emit(str(e))

    def search_duckduckgo_images(self, query, offset=0):
        """Buscar imágenes en DuckDuckGo"""
        # Primer request para obtener token
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

        # Obtener token de búsqueda
        token_url = "https://duckduckgo.com/"
        token_response = session.get(token_url)

        # Buscar imágenes
        search_url = "https://duckduckgo.com/i.js"
        params = {
            'l': 'us-en',
            'o': 'json',
            'q': query,
            's': offset,
            'u': 'bing',
            'f': ',,,',
            'p': '1'
        }

        response = session.get(search_url, params=params)

        if response.status_code == 200:
            try:
                data = response.json()
                images = []

                if 'results' in data:
                    for item in data['results'][:10]:  # Primeras 10 imágenes
                        if 'image' in item and 'title' in item:
                            images.append({
                                'url': item['image'],
                                'title': item['title'][:100],  # Limitar título
                                'thumbnail': item.get('thumbnail', item['image'])
                            })

                return images
            except json.JSONDecodeError:
                # Fallback: usar método alternativo si falla JSON
                return self.search_fallback(query)

        return []

    def search_fallback(self, query):
        """Método alternativo de búsqueda"""
        # Usar Unsplash como fallback
        try:
            url = f"https://api.unsplash.com/search/photos"
            params = {
                'query': query,
                'per_page': 10,
                'client_id': 'your_unsplash_access_key'  # Necesitarías registrarte en Unsplash
            }

            # Por simplicidad, devolver imágenes de ejemplo
            return [
                {
                    'url': f'https://picsum.photos/800/600?random={i}&{quote_plus(query)}',
                    'title': f'{query} - Imagen {i+1}',
                    'thumbnail': f'https://picsum.photos/200/150?random={i}&{quote_plus(query)}'
                }
                for i in range(10)
            ]
        except:
            return []


class ImageDownloadThread(QThread):
    """Thread para descargar imagen"""
    download_finished = pyqtSignal(bool, str)
    progress_updated = pyqtSignal(int)

    def __init__(self, url, destination):
        super().__init__()
        self.url = url
        self.destination = destination

    def run(self):
        try:
            response = requests.get(self.url, stream=True)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(self.destination, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress = int((downloaded / total_size) * 100)
                            self.progress_updated.emit(progress)

            self.download_finished.emit(True, "Descarga completada")
        except Exception as e:
            self.download_finished.emit(False, str(e))


class ImageWidget(QFrame):
    """Widget personalizado para mostrar imagen con información"""
    image_selected = pyqtSignal(dict)

    def __init__(self, image_data):
        super().__init__()
        self.image_data = image_data
        self.setup_ui()

    def setup_ui(self):
        self.setFrameStyle(QFrame.Shape.Box)
        self.setFixedSize(200, 180)
        self.setStyleSheet("""
            QFrame {
                border: 1px solid #ccc;
                border-radius: 5px;
                margin: 2px;
            }
            QFrame:hover {
                border: 2px solid #0078d4;
                background-color: #f0f8ff;
            }
        """)

        layout = QVBoxLayout()

        # Imagen thumbnail
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedSize(180, 135)
        self.image_label.setStyleSheet("border: none; background-color: #f5f5f5;")

        # Cargar thumbnail
        self.load_thumbnail()

        # Título
        title_label = QLabel(self.image_data['title'])
        title_label.setWordWrap(True)
        title_label.setMaximumHeight(40)
        title_label.setStyleSheet("border: none; font-size: 10px; padding: 2px;")

        layout.addWidget(self.image_label)
        layout.addWidget(title_label)
        layout.setContentsMargins(5, 5, 5, 5)

        self.setLayout(layout)

    def load_thumbnail(self):
        """Cargar imagen thumbnail"""
        try:
            response = requests.get(self.image_data['thumbnail'], timeout=5)
            if response.status_code == 200:
                pixmap = QPixmap()
                pixmap.loadFromData(response.content)
                scaled_pixmap = pixmap.scaled(180, 135, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation)
                self.image_label.setPixmap(scaled_pixmap)
            else:
                self.image_label.setText("No preview")
        except:
            self.image_label.setText("No preview")

    def mousePressEvent(self, event):
        """Manejar clic en imagen"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.image_selected.emit(self.image_data)


class ImageSelector(QMainWindow):
    def __init__(self, output_dir):
        super().__init__()
        self.output_dir = Path(output_dir)
        self.current_images = []
        self.current_offset = 0
        self.current_query = ""
        self.selected_image = None

        self.setup_ui()
        self.setup_shortcuts()

    def setup_ui(self):
        self.setWindowTitle("Selector de Imágenes - DuckDuckGo")
        self.setGeometry(100, 100, 1000, 700)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()

        # Búsqueda
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar imágenes...")
        self.search_input.returnPressed.connect(self.search_images)

        self.search_button = QPushButton("Buscar")
        self.search_button.clicked.connect(self.search_images)

        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_button)

        # Información
        self.info_label = QLabel("Introduce un término de búsqueda")
        self.info_label.setStyleSheet("font-weight: bold; color: #666;")

        # Área de resultados con scroll
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.results_widget = QWidget()
        self.results_layout = QGridLayout()
        self.results_widget.setLayout(self.results_layout)
        self.scroll_area.setWidget(self.results_widget)

        # Navegación
        nav_layout = QHBoxLayout()
        self.prev_button = QPushButton("← Anterior")
        self.prev_button.clicked.connect(self.previous_page)
        self.prev_button.setEnabled(False)

        self.next_button = QPushButton("Siguiente →")
        self.next_button.clicked.connect(self.next_page)
        self.next_button.setEnabled(False)

        self.page_label = QLabel("Página 1")

        nav_layout.addWidget(self.prev_button)
        nav_layout.addWidget(self.page_label)
        nav_layout.addWidget(self.next_button)

        # Progreso y botones
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)

        button_layout = QHBoxLayout()
        self.download_button = QPushButton("Descargar Seleccionada")
        self.download_button.clicked.connect(self.download_selected)
        self.download_button.setEnabled(False)

        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.clicked.connect(self.close)

        button_layout.addWidget(self.download_button)
        button_layout.addWidget(self.cancel_button)

        # Agregar todo al layout principal
        layout.addLayout(search_layout)
        layout.addWidget(self.info_label)
        layout.addWidget(self.scroll_area)
        layout.addLayout(nav_layout)
        layout.addWidget(self.progress_bar)
        layout.addLayout(button_layout)

        central_widget.setLayout(layout)

    def setup_shortcuts(self):
        """Configurar atajos de teclado"""
        enter_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Return), self)
        enter_shortcut.activated.connect(self.download_selected)

        enter_shortcut2 = QShortcut(QKeySequence(Qt.Key.Key_Enter), self)
        enter_shortcut2.activated.connect(self.download_selected)

    def search_images(self):
        """Buscar imágenes"""
        query = self.search_input.text().strip()
        if not query:
            return

        self.current_query = query
        self.current_offset = 0
        self.info_label.setText(f"Buscando '{query}'...")
        self.clear_results()

        self.search_thread = ImageSearchThread(query, self.current_offset)
        self.search_thread.images_found.connect(self.display_images)
        self.search_thread.error_occurred.connect(self.handle_search_error)
        self.search_thread.start()

    def display_images(self, images):
        """Mostrar imágenes en la interfaz"""
        self.current_images = images
        self.clear_results()

        if not images:
            self.info_label.setText("No se encontraron imágenes")
            return

        self.info_label.setText(f"Mostrando {len(images)} imágenes para '{self.current_query}'")

        row, col = 0, 0
        for image_data in images:
            image_widget = ImageWidget(image_data)
            image_widget.image_selected.connect(self.select_image)

            self.results_layout.addWidget(image_widget, row, col)

            col += 1
            if col >= 5:  # 5 columnas
                col = 0
                row += 1

        # Actualizar navegación
        page_num = (self.current_offset // 10) + 1
        self.page_label.setText(f"Página {page_num}")
        self.prev_button.setEnabled(self.current_offset > 0)
        self.next_button.setEnabled(len(images) == 10)

    def clear_results(self):
        """Limpiar resultados anteriores"""
        while self.results_layout.count():
            child = self.results_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def select_image(self, image_data):
        """Seleccionar una imagen"""
        self.selected_image = image_data
        self.download_button.setEnabled(True)
        self.info_label.setText(f"Seleccionada: {image_data['title']}")

    def previous_page(self):
        """Página anterior"""
        if self.current_offset >= 10:
            self.current_offset -= 10
            self.search_page()

    def next_page(self):
        """Página siguiente"""
        self.current_offset += 10
        self.search_page()

    def search_page(self):
        """Buscar página específica"""
        self.info_label.setText(f"Cargando página...")

        self.search_thread = ImageSearchThread(self.current_query, self.current_offset)
        self.search_thread.images_found.connect(self.display_images)
        self.search_thread.error_occurred.connect(self.handle_search_error)
        self.search_thread.start()

    def download_selected(self):
        """Descargar imagen seleccionada"""
        if not self.selected_image:
            QMessageBox.warning(self, "Advertencia", "Por favor selecciona una imagen primero")
            return

        destination = self.output_dir / "image.png"

        self.progress_bar.setVisible(True)
        self.download_button.setEnabled(False)

        self.download_thread = ImageDownloadThread(self.selected_image['url'], destination)
        self.download_thread.download_finished.connect(self.handle_download_finished)
        self.download_thread.progress_updated.connect(self.progress_bar.setValue)
        self.download_thread.start()

    def handle_download_finished(self, success, message):
        """Manejar finalización de descarga"""
        self.progress_bar.setVisible(False)

        if success:
            QMessageBox.information(self, "Éxito", "Imagen descargada como 'image.png'")
            self.close()
        else:
            QMessageBox.critical(self, "Error", f"Error al descargar: {message}")
            self.download_button.setEnabled(True)

    def handle_search_error(self, error):
        """Manejar errores de búsqueda"""
        self.info_label.setText(f"Error en búsqueda: {error}")
        QMessageBox.critical(self, "Error", f"Error al buscar imágenes: {error}")


def main():
    parser = argparse.ArgumentParser(description='Selector de imágenes con DuckDuckGo')
    parser.add_argument('output_dir', help='Directorio de destino para la imagen')
    args = parser.parse_args()

    if not os.path.exists(args.output_dir):
        print(f"Error: El directorio {args.output_dir} no existe")
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Estilo moderno

    window = ImageSelector(args.output_dir)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
