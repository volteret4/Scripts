#!/usr/bin/env python3
"""
Selector de imágenes mejorado con múltiples fuentes
Uso: python image_selector.py <directorio_destino>
"""

import sys
import os
import requests
import json
from urllib.parse import quote_plus, urlparse
from pathlib import Path
import argparse
import time
import re
import random

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QHBoxLayout, QLineEdit, QPushButton, QListWidget,
                            QLabel, QProgressBar, QMessageBox, QListWidgetItem,
                            QScrollArea, QGridLayout, QFrame)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer
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
            images = self.search_images_multiple_sources(self.query, self.offset)
            self.images_found.emit(images)
        except Exception as e:
            self.error_occurred.emit(str(e))

    def search_images_multiple_sources(self, query, offset=0):
        """Buscar imágenes usando múltiples fuentes"""
        images = []

        print(f"Buscando imágenes para: {query}")

        # Método 1: Unsplash Source (garantizado)
        try:
            unsplash_images = self.search_unsplash_source(query)
            images.extend(unsplash_images)
            print(f"Unsplash Source: {len(unsplash_images)} imágenes")
        except Exception as e:
            print(f"Error Unsplash Source: {e}")

        # Método 2: Lorem Picsum con categorías
        try:
            lorem_images = self.search_lorem_picsum_enhanced(query)
            images.extend(lorem_images)
            print(f"Lorem Picsum: {len(lorem_images)} imágenes")
        except Exception as e:
            print(f"Error Lorem Picsum: {e}")

        # Método 3: Placeholder.com con variaciones
        try:
            placeholder_images = self.search_placeholder_com(query)
            images.extend(placeholder_images)
            print(f"Placeholder.com: {len(placeholder_images)} imágenes")
        except Exception as e:
            print(f"Error Placeholder.com: {e}")

        print(f"Total de imágenes encontradas: {len(images)}")

        # Asegurar que tenemos exactamente 15 imágenes
        if len(images) < 15:
            # Agregar más imágenes Lorem Picsum con diferentes semillas
            additional_needed = 15 - len(images)
            for i in range(additional_needed):
                seed = abs(hash(query + str(i + 100))) % 10000
                images.append({
                    'url': f"https://picsum.photos/seed/{seed}/800/600",
                    'title': f'{query} - Imagen adicional {i+1}',
                    'thumbnail': f"https://picsum.photos/seed/{seed}/200/150",
                    'source': 'Lorem Picsum Extra'
                })

        # Limitar a exactamente 15 y eliminar duplicados
        unique_images = []
        seen_urls = set()

        for img in images:
            if img['url'] not in seen_urls and len(unique_images) < 15:
                seen_urls.add(img['url'])
                unique_images.append(img)

        print(f"Imágenes únicas devueltas: {len(unique_images)}")
        return unique_images

    def search_unsplash_source(self, query):
        """Buscar en Unsplash Source (más confiable)"""
        images = []
        try:
            # Unsplash Source permite diferentes parámetros
            categories = [query, "nature", "technology", "abstract", "business"]

            for i in range(6):  # 6 imágenes de Unsplash
                # Usar diferentes categorías y semillas
                category = categories[i % len(categories)]
                seed = abs(hash(query + str(i))) % 1000

                img_url = f"https://source.unsplash.com/800x600/?{quote_plus(category)}&sig={seed}"
                thumbnail_url = f"https://source.unsplash.com/200x150/?{quote_plus(category)}&sig={seed}"

                images.append({
                    'url': img_url,
                    'title': f'{query} - Unsplash {i+1}',
                    'thumbnail': thumbnail_url,
                    'source': 'Unsplash'
                })

        except Exception as e:
            print(f"Error en Unsplash Source: {e}")

        return images

    def search_lorem_picsum_enhanced(self, query):
        """Lorem Picsum con más variaciones"""
        images = []
        try:
            # Generar diferentes semillas basadas en la consulta
            base_seed = abs(hash(query)) % 1000

            for i in range(6):  # 6 imágenes de Lorem Picsum
                seed = base_seed + (i * 123) % 1000  # Diferentes semillas

                # Añadir filtros de Lorem Picsum para variedad
                filters = ["", "?grayscale", "?blur=1", ""]
                filter_str = filters[i % len(filters)]

                img_url = f"https://picsum.photos/seed/{seed}/800/600{filter_str}"
                thumbnail_url = f"https://picsum.photos/seed/{seed}/200/150{filter_str}"

                filter_name = "Normal" if not filter_str else filter_str.replace("?", "").capitalize()

                images.append({
                    'url': img_url,
                    'title': f'{query} - Lorem {filter_name} {i+1}',
                    'thumbnail': thumbnail_url,
                    'source': 'Lorem Picsum'
                })

        except Exception as e:
            print(f"Error en Lorem Picsum Enhanced: {e}")

        return images

    def search_placeholder_com(self, query):
        """Placeholder.com con colores y texto"""
        images = []
        try:
            colors = ["FF5733", "33C1FF", "28A745", "FFC107", "6C757D"]

            for i, color in enumerate(colors[:3]):  # 3 imágenes de Placeholder
                # Crear URLs con texto personalizado
                text = quote_plus(query[:20])  # Limitar texto

                img_url = f"https://via.placeholder.com/800x600/{color}/FFFFFF?text={text}+{i+1}"
                thumbnail_url = f"https://via.placeholder.com/200x150/{color}/FFFFFF?text={text}+{i+1}"

                images.append({
                    'url': img_url,
                    'title': f'{query} - Placeholder {i+1}',
                    'thumbnail': thumbnail_url,
                    'source': 'Placeholder.com'
                })

        except Exception as e:
            print(f"Error en Placeholder.com: {e}")

        return images


class ThumbnailLoader(QThread):
    """Thread separado para cargar thumbnails"""
    thumbnail_loaded = pyqtSignal(object, QPixmap)  # widget, pixmap

    def __init__(self, widget, url):
        super().__init__()
        self.widget = widget
        self.url = url

    def run(self):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept-Language': 'en-US,en;q=0.9',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            }

            print(f"Cargando thumbnail: {self.url}")

            response = requests.get(self.url, timeout=15, headers=headers, stream=True)
            response.raise_for_status()

            # Leer contenido
            content = response.content

            if len(content) > 0:
                pixmap = QPixmap()
                if pixmap.loadFromData(content):
                    print(f"Thumbnail cargado exitosamente: {len(content)} bytes")
                    self.thumbnail_loaded.emit(self.widget, pixmap)
                else:
                    print(f"Error al crear pixmap del contenido")
            else:
                print(f"Contenido vacío recibido")

        except requests.exceptions.RequestException as e:
            print(f"Error de requests cargando thumbnail {self.url}: {e}")
        except Exception as e:
            print(f"Error general cargando thumbnail {self.url}: {e}")


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
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Referer': 'https://unsplash.com/',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept-Language': 'en-US,en;q=0.9'
            }

            print(f"Descargando imagen desde: {self.url}")

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
                            # Si no conocemos el tamaño total, mostrar progreso básico
                            progress = min((downloaded // 1024) % 100, 95)
                            self.progress_updated.emit(progress)

            # Verificar que el archivo se creó correctamente
            if os.path.exists(self.destination) and os.path.getsize(self.destination) > 0:
                print(f"Imagen descargada exitosamente: {os.path.getsize(self.destination)} bytes")
                self.download_finished.emit(True, "Descarga completada")
            else:
                self.download_finished.emit(False, "El archivo descargado está vacío")

        except Exception as e:
            print(f"Error descargando imagen: {e}")
            self.download_finished.emit(False, str(e))


class ImageWidget(QFrame):
    """Widget personalizado para mostrar imagen con información"""
    image_selected = pyqtSignal(dict)

    def __init__(self, image_data):
        super().__init__()
        self.image_data = image_data
        self.thumbnail_loader = None
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
        self.image_label = QLabel("Cargando...")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedSize(180, 135)
        self.image_label.setStyleSheet("""
            border: 1px solid #ddd;
            background-color: #f8f9fa;
            color: #666;
            font-size: 12px;
        """)

        # Título
        title_label = QLabel(self.image_data['title'])
        title_label.setWordWrap(True)
        title_label.setMaximumHeight(35)
        title_label.setStyleSheet("border: none; font-size: 10px; padding: 2px; font-weight: bold;")

        # Fuente
        source_label = QLabel(f"📸 {self.image_data.get('source', 'Desconocida')}")
        source_label.setStyleSheet("border: none; font-size: 8px; color: #666; padding: 1px;")

        layout.addWidget(self.image_label)
        layout.addWidget(title_label)
        layout.addWidget(source_label)
        layout.setContentsMargins(5, 5, 5, 5)

        self.setLayout(layout)

        # Cargar thumbnail en un thread separado después de un pequeño delay
        QTimer.singleShot(100, self.load_thumbnail_async)

    def load_thumbnail_async(self):
        """Cargar imagen thumbnail de forma asíncrona"""
        print(f"Iniciando carga de thumbnail para: {self.image_data['title']}")
        self.thumbnail_loader = ThumbnailLoader(self, self.image_data['thumbnail'])
        self.thumbnail_loader.thumbnail_loaded.connect(self.on_thumbnail_loaded)
        self.thumbnail_loader.start()

    def on_thumbnail_loaded(self, widget, pixmap):
        """Callback cuando se carga el thumbnail"""
        if widget == self:
            scaled_pixmap = pixmap.scaled(180, 135, Qt.AspectRatioMode.KeepAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation)
            self.image_label.setPixmap(scaled_pixmap)
            self.image_label.setText("")  # Limpiar texto "Cargando..."
            print(f"Thumbnail mostrado para: {self.image_data['title']}")

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
        self.setWindowTitle("Selector de Imágenes - Múltiples Fuentes")
        self.setGeometry(100, 100, 1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()

        # Búsqueda
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar imágenes... (Ej: naturaleza, tecnología, abstract)")
        self.search_input.returnPressed.connect(self.search_images)

        self.search_button = QPushButton("🔍 Buscar")
        self.search_button.clicked.connect(self.search_images)

        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_button)

        # Información
        self.info_label = QLabel("Introduce un término de búsqueda. Se mostrarán 15 imágenes de diferentes fuentes.")
        self.info_label.setStyleSheet("font-weight: bold; color: #666; padding: 10px;")

        # Área de resultados con scroll
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.results_widget = QWidget()
        self.results_layout = QGridLayout()
        self.results_layout.setSpacing(10)  # Más espacio entre elementos
        self.results_widget.setLayout(self.results_layout)
        self.scroll_area.setWidget(self.results_widget)

        # Progreso y botones
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)

        button_layout = QHBoxLayout()
        self.download_button = QPushButton("⬇️ Descargar Seleccionada")
        self.download_button.clicked.connect(self.download_selected)
        self.download_button.setEnabled(False)
        self.download_button.setStyleSheet("font-weight: bold; padding: 10px;")

        self.cancel_button = QPushButton("❌ Cancelar")
        self.cancel_button.clicked.connect(self.close)
        self.cancel_button.setStyleSheet("padding: 10px;")

        button_layout.addWidget(self.download_button)
        button_layout.addWidget(self.cancel_button)

        # Agregar todo al layout principal
        layout.addLayout(search_layout)
        layout.addWidget(self.info_label)
        layout.addWidget(self.scroll_area)
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
            QMessageBox.warning(self, "Advertencia", "Por favor introduce un término de búsqueda")
            return

        self.current_query = query
        self.current_offset = 0
        self.info_label.setText(f"🔍 Buscando '{query}' - Se cargarán 15 imágenes...")
        self.clear_results()

        # Deshabilitar botón de búsqueda mientras se busca
        self.search_button.setEnabled(False)
        self.search_button.setText("Buscando...")

        self.search_thread = ImageSearchThread(query, self.current_offset)
        self.search_thread.images_found.connect(self.display_images)
        self.search_thread.error_occurred.connect(self.handle_search_error)
        self.search_thread.finished.connect(self.on_search_finished)
        self.search_thread.start()

    def on_search_finished(self):
        """Callback cuando termina la búsqueda"""
        self.search_button.setEnabled(True)
        self.search_button.setText("🔍 Buscar")

    def display_images(self, images):
        """Mostrar imágenes en la interfaz"""
        self.current_images = images
        self.clear_results()

        if not images:
            self.info_label.setText("❌ No se encontraron imágenes. Intenta con otro término de búsqueda.")
            return

        self.info_label.setText(f"✅ Mostrando {len(images)} imágenes para '{self.current_query}'. Las vistas previas se cargarán automáticamente.")

        row, col = 0, 0
        for i, image_data in enumerate(images):
            print(f"Creando widget {i+1}/{len(images)}: {image_data['title']}")

            image_widget = ImageWidget(image_data)
            image_widget.image_selected.connect(self.select_image)

            self.results_layout.addWidget(image_widget, row, col)

            col += 1
            if col >= 5:  # 5 columnas
                col = 0
                row += 1

        print(f"Todos los widgets creados. Total: {len(images)}")

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
        self.info_label.setText(f"✅ Seleccionada: {image_data['title']} (Fuente: {image_data.get('source', 'Desconocida')})")

        # Resaltar visualmente la imagen seleccionada
        for i in range(self.results_layout.count()):
            widget = self.results_layout.itemAt(i).widget()
            if hasattr(widget, 'image_data'):
                if widget.image_data == image_data:
                    widget.setStyleSheet("""
                        QFrame {
                            border: 3px solid #0078d4 !important;
                            background-color: #e3f2fd !important;
                        }
                    """)
                else:
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

    def download_selected(self):
        """Descargar imagen seleccionada"""
        if not self.selected_image:
            QMessageBox.warning(self, "Advertencia", "Por favor selecciona una imagen primero")
            return

        destination = self.output_dir / "image.png"

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.download_button.setEnabled(False)
        self.info_label.setText(f"⬇️ Descargando imagen de {self.selected_image.get('source', 'fuente desconocida')}...")

        self.download_thread = ImageDownloadThread(self.selected_image['url'], destination)
        self.download_thread.download_finished.connect(self.handle_download_finished)
        self.download_thread.progress_updated.connect(self.progress_bar.setValue)
        self.download_thread.start()

    def handle_download_finished(self, success, message):
        """Manejar finalización de descarga"""
        self.progress_bar.setVisible(False)

        if success:
            QMessageBox.information(self, "✅ Éxito", "Imagen descargada correctamente como 'image.png'")
            self.close()
        else:
            QMessageBox.critical(self, "❌ Error", f"Error al descargar la imagen:\n{message}")
            self.download_button.setEnabled(True)
            self.info_label.setText(f"❌ Error en descarga. Selecciona otra imagen.")

    def handle_search_error(self, error):
        """Manejar errores de búsqueda"""
        self.info_label.setText(f"❌ Error en búsqueda: {error}")
        QMessageBox.critical(self, "Error", f"Error al buscar imágenes:\n{error}")


def main():
    parser = argparse.ArgumentParser(description='Selector de imágenes con múltiples fuentes')
    parser.add_argument('output_dir', help='Directorio de destino para la imagen')
    args = parser.parse_args()

    if not os.path.exists(args.output_dir):
        print(f"Error: El directorio {args.output_dir} no existe")
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Estilo moderno

    # Configurar tema mejorado
    app.setStyleSheet("""
        QMainWindow {
            background-color: #f5f5f5;
        }
        QLineEdit {
            padding: 8px;
            border: 2px solid #ccc;
            border-radius: 4px;
            font-size: 14px;
        }
        QLineEdit:focus {
            border-color: #0078d4;
        }
        QPushButton {
            background-color: #0078d4;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-size: 14px;
        }
        QPushButton:hover {
            background-color: #106ebe;
        }
        QPushButton:disabled {
            background-color: #ccc;
        }
        QScrollArea {
            border: 1px solid #ddd;
            border-radius: 5px;
        }
    """)

    print("Iniciando aplicación de selector de imágenes...")
    window = ImageSelector(args.output_dir)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
