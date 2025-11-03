#!/usr/bin/env python3
"""
Selector de imágenes con PyQt6 - Versión con imágenes de ejemplo
Uso: python image_selector.py <directorio_destino>
"""

import sys
import os
import requests
import json
from urllib.parse import quote_plus, urlparse
from pathlib import Path
import argparse
import random

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QHBoxLayout, QLineEdit, QPushButton, QListWidget,
                            QLabel, QProgressBar, QMessageBox, QListWidgetItem,
                            QScrollArea, QGridLayout, QFrame)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QFont, QKeySequence, QShortcut


class ImageSearchThread(QThread):
    """Thread para generar imágenes de ejemplo"""
    images_found = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def __init__(self, query, offset=0):
        super().__init__()
        self.query = query
        self.offset = offset

    def run(self):
        try:
            images = self.generate_example_images(self.query, self.offset)
            self.images_found.emit(images)
        except Exception as e:
            self.error_occurred.emit(str(e))

    def generate_example_images(self, query, offset=0):
        """Generar imágenes de ejemplo usando servicios gratuitos"""
        images = []

        # Lista de servicios de imágenes de ejemplo
        image_services = [
            {
                'name': 'Picsum',
                'url_template': 'https://picsum.photos/{width}/{height}?random={seed}',
                'thumb_template': 'https://picsum.photos/200/150?random={seed}',
                'sizes': [(800, 600), (1024, 768), (640, 480)]
            },
            {
                'name': 'PlaceImg',
                'url_template': 'https://placeimg.com/{width}/{height}/any/{seed}',
                'thumb_template': 'https://placeimg.com/200/150/any/{seed}',
                'sizes': [(800, 600), (640, 480), (1024, 768)]
            },
            {
                'name': 'Lorem Picsum ID',
                'url_template': 'https://picsum.photos/id/{id}/{width}/{height}',
                'thumb_template': 'https://picsum.photos/id/{id}/200/150',
                'sizes': [(800, 600), (1024, 768)],
                'id_range': (1, 1000)  # IDs disponibles
            }
        ]

        # Generar 10 imágenes de ejemplo
        for i in range(10):
            service = random.choice(image_services)
            width, height = random.choice(service['sizes'])

            if 'id_range' in service:
                # Servicio con IDs específicos
                img_id = random.randint(*service['id_range']) + offset + i
                image_url = service['url_template'].format(
                    id=img_id, width=width, height=height
                )
                thumbnail_url = service['thumb_template'].format(id=img_id)
            else:
                # Servicio con seeds aleatorios
                seed = hash(query + str(i + offset)) % 10000
                image_url = service['url_template'].format(
                    width=width, height=height, seed=seed
                )
                thumbnail_url = service['thumb_template'].format(seed=seed)

            # Crear entrada de imagen
            image_data = {
                'url': image_url,
                'title': f'{query} - {service["name"]} {width}x{height} #{i+1+offset}',
                'thumbnail': thumbnail_url,
                'service': service['name'],
                'dimensions': f'{width}x{height}'
            }

            images.append(image_data)

        return images


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
            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }

            response = requests.get(self.url, stream=True, headers=headers, timeout=30)
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
                        else:
                            # Progreso indeterminado
                            self.progress_updated.emit(50)

            self.download_finished.emit(True, "Descarga completada")
        except requests.exceptions.Timeout:
            self.download_finished.emit(False, "Timeout - La descarga tardó demasiado")
        except requests.exceptions.RequestException as e:
            self.download_finished.emit(False, f"Error de conexión: {str(e)}")
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
        self.setFixedSize(200, 200)
        self.setStyleSheet("""
            QFrame {
                border: 1px solid #ccc;
                border-radius: 5px;
                margin: 2px;
                background-color: white;
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
        self.image_label.setStyleSheet("border: none; background-color: #f5f5f5; border-radius: 3px;")
        self.image_label.setText("Cargando...")

        # Título
        title_label = QLabel(self.image_data['title'])
        title_label.setWordWrap(True)
        title_label.setMaximumHeight(35)
        title_label.setStyleSheet("border: none; font-size: 9px; padding: 2px; color: #333;")

        # Información adicional
        info_label = QLabel(f"📐 {self.image_data['dimensions']} • {self.image_data['service']}")
        info_label.setStyleSheet("border: none; font-size: 8px; color: #666; padding: 2px;")
        info_label.setMaximumHeight(20)

        layout.addWidget(self.image_label)
        layout.addWidget(title_label)
        layout.addWidget(info_label)
        layout.setContentsMargins(5, 5, 5, 5)

        self.setLayout(layout)

        # Cargar thumbnail de forma asíncrona
        self.load_thumbnail()

    def load_thumbnail(self):
        """Cargar imagen thumbnail"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
            }
            response = requests.get(self.image_data['thumbnail'], timeout=10, headers=headers)
            if response.status_code == 200:
                pixmap = QPixmap()
                if pixmap.loadFromData(response.content):
                    scaled_pixmap = pixmap.scaled(180, 135, Qt.AspectRatioMode.KeepAspectRatio,
                                                Qt.TransformationMode.SmoothTransformation)
                    self.image_label.setPixmap(scaled_pixmap)
                else:
                    self.image_label.setText("❌ Error\ncargando")
            else:
                self.image_label.setText(f"❌ Error {response.status_code}")
        except Exception as e:
            self.image_label.setText("❌ Sin\npreview")
            print(f"Error cargando thumbnail: {e}")

    def mousePressEvent(self, event):
        """Manejar clic en imagen"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.image_selected.emit(self.image_data)
            # Efecto visual de selección
            self.setStyleSheet("""
                QFrame {
                    border: 3px solid #0078d4;
                    border-radius: 5px;
                    margin: 2px;
                    background-color: #e6f3ff;
                }
            """)


class ImageSelector(QMainWindow):
    def __init__(self, output_dir):
        super().__init__()
        self.output_dir = Path(output_dir)
        self.current_images = []
        self.current_offset = 0
        self.current_query = ""
        self.selected_image = None
        self.selected_widget = None

        self.setup_ui()
        self.setup_shortcuts()

    def setup_ui(self):
        self.setWindowTitle("Selector de Imágenes - Ejemplos")
        self.setGeometry(100, 100, 1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()

        # Header con información
        header_layout = QVBoxLayout()

        title_label = QLabel("🖼️ Selector de Imágenes de Ejemplo")
        title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #0078d4; padding: 10px;")
        header_layout.addWidget(title_label)

        info_label = QLabel("💡 Introduce un término de búsqueda para generar imágenes de ejemplo")
        info_label.setStyleSheet("color: #666; padding: 5px; font-style: italic;")
        header_layout.addWidget(info_label)

        # Búsqueda
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Término de búsqueda (ej: naturaleza, tecnología, arte)...")
        self.search_input.returnPressed.connect(self.search_images)
        self.search_input.setStyleSheet("""
            QLineEdit {
                font-size: 12px;
                padding: 8px;
                border: 2px solid #ccc;
                border-radius: 5px;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
        """)

        self.search_button = QPushButton("🔍 Generar Imágenes")
        self.search_button.clicked.connect(self.search_images)
        self.search_button.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                font-weight: bold;
                padding: 8px 15px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
        """)

        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_button)

        # Estado
        self.info_label = QLabel("👆 Introduce un término de búsqueda para comenzar")
        self.info_label.setStyleSheet("font-weight: bold; color: #666; padding: 10px; background-color: #f8f9fa; border-radius: 5px;")

        # Área de resultados con scroll
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setMinimumHeight(400)

        self.results_widget = QWidget()
        self.results_layout = QGridLayout()
        self.results_widget.setLayout(self.results_layout)
        self.scroll_area.setWidget(self.results_widget)

        # Navegación
        nav_layout = QHBoxLayout()
        self.prev_button = QPushButton("⬅️ Anterior")
        self.prev_button.clicked.connect(self.previous_page)
        self.prev_button.setEnabled(False)

        self.next_button = QPushButton("Siguiente ➡️")
        self.next_button.clicked.connect(self.next_page)
        self.next_button.setEnabled(False)

        self.page_label = QLabel("Página 1")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_label.setStyleSheet("font-weight: bold; color: #0078d4;")

        nav_layout.addWidget(self.prev_button)
        nav_layout.addWidget(self.page_label)
        nav_layout.addWidget(self.next_button)

        # Progreso y botones
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #0078d4;
                border-radius: 4px;
            }
        """)

        button_layout = QHBoxLayout()
        self.download_button = QPushButton("⬇️ Descargar Seleccionada")
        self.download_button.clicked.connect(self.download_selected)
        self.download_button.setEnabled(False)
        self.download_button.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)

        self.cancel_button = QPushButton("❌ Cancelar")
        self.cancel_button.clicked.connect(self.close)
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)

        button_layout.addWidget(self.download_button)
        button_layout.addWidget(self.cancel_button)

        # Agregar todo al layout principal
        layout.addLayout(header_layout)
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

        # Atajos numéricos para seleccionar imágenes
        for i in range(1, 10):
            shortcut = QShortcut(QKeySequence(f"{i}"), self)
            shortcut.activated.connect(lambda checked, idx=i-1: self.select_image_by_index(idx))

    def select_image_by_index(self, index):
        """Seleccionar imagen por índice numérico"""
        if 0 <= index < len(self.current_images):
            image_data = self.current_images[index]
            self.select_image(image_data)
            # Actualizar visual de la imagen seleccionada
            self.update_visual_selection(index)

    def update_visual_selection(self, selected_index):
        """Actualizar selección visual"""
        # Resetear todas las imágenes
        for i in range(self.results_layout.count()):
            widget = self.results_layout.itemAt(i).widget()
            if isinstance(widget, ImageWidget):
                widget.setStyleSheet("""
                    QFrame {
                        border: 1px solid #ccc;
                        border-radius: 5px;
                        margin: 2px;
                        background-color: white;
                    }
                    QFrame:hover {
                        border: 2px solid #0078d4;
                        background-color: #f0f8ff;
                    }
                """)

        # Marcar la seleccionada
        if selected_index < self.results_layout.count():
            widget = self.results_layout.itemAt(selected_index).widget()
            if isinstance(widget, ImageWidget):
                widget.setStyleSheet("""
                    QFrame {
                        border: 3px solid #0078d4;
                        border-radius: 5px;
                        margin: 2px;
                        background-color: #e6f3ff;
                    }
                """)

    def search_images(self):
        """Buscar/generar imágenes"""
        query = self.search_input.text().strip()
        if not query:
            QMessageBox.warning(self, "Advertencia", "Por favor introduce un término de búsqueda")
            return

        self.current_query = query
        self.current_offset = 0
        self.info_label.setText(f"🔄 Generando imágenes para '{query}'...")
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
            self.info_label.setText("❌ No se pudieron generar imágenes")
            return

        self.info_label.setText(f"✅ Mostrando {len(images)} imágenes para '{self.current_query}' - Usa números 1-9 para selección rápida")

        row, col = 0, 0
        for i, image_data in enumerate(images):
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
        self.info_label.setText(f"✅ Seleccionada: {image_data['title']}")

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
        self.info_label.setText(f"🔄 Cargando página...")

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
        self.info_label.setText("⬇️ Descargando imagen...")

        self.download_thread = ImageDownloadThread(self.selected_image['url'], destination)
        self.download_thread.download_finished.connect(self.handle_download_finished)
        self.download_thread.progress_updated.connect(self.progress_bar.setValue)
        self.download_thread.start()

    def handle_download_finished(self, success, message):
        """Manejar finalización de descarga"""
        self.progress_bar.setVisible(False)

        if success:
            QMessageBox.information(self, "✅ Éxito",
                f"Imagen descargada como 'image.png'\n\nDetalles:\n"
                f"• Servicio: {self.selected_image['service']}\n"
                f"• Dimensiones: {self.selected_image['dimensions']}\n"
                f"• Ubicación: {self.output_dir}/image.png")
            self.close()
        else:
            QMessageBox.critical(self, "❌ Error", f"Error al descargar imagen:\n{message}")
            self.download_button.setEnabled(True)
            self.info_label.setText("❌ Error en la descarga - Intenta con otra imagen")

    def handle_search_error(self, error):
        """Manejar errores de búsqueda"""
        self.info_label.setText(f"❌ Error: {error}")
        QMessageBox.critical(self, "Error", f"Error al generar imágenes: {error}")


def main():
    parser = argparse.ArgumentParser(description='Selector de imágenes de ejemplo')
    parser.add_argument('output_dir', help='Directorio de destino para la imagen')
    args = parser.parse_args()

    if not os.path.exists(args.output_dir):
        print(f"Error: El directorio {args.output_dir} no existe")
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Estilo moderno

    # Aplicar tema
    app.setStyleSheet("""
        QMainWindow {
            background-color: #f8f9fa;
        }
        QScrollArea {
            background-color: white;
            border: 1px solid #ddd;
            border-radius: 5px;
        }
        QPushButton {
            font-size: 11px;
        }
    """)

    window = ImageSelector(args.output_dir)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
