#!/usr/bin/env python3
"""
Generador de Páginas Web de Álbumes
Crea páginas web personalizadas para cada álbum con información completa.

Características:
- Extrae información de archivos de música
- Busca imágenes de álbum y artista
- Obtiene letras de canciones
- Busca enlaces relevantes en bases de datos y APIs
- Genera HTML, CSS y JavaScript personalizados
- Soporte para base de datos SQLite opcional
"""

import os
import sys
import argparse
import sqlite3
import tkinter as tk
from tkinter import simpledialog, messagebox
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import logging
import json
import urllib.parse
from datetime import datetime

# Importar módulos del proyecto
from modules.database_manager import DatabaseManager
from modules.image_finder import ImageFinder
from modules.lyrics_finder import LyricsFinder
from modules.link_finder import LinkFinder
from modules.html_generator import HTMLGenerator
from modules.album_processor import AlbumProcessor

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class AlbumWebGenerator:
    """Clase principal para generar páginas web de álbumes"""

    def __init__(self, db_path: Optional[str] = None):
        """
        Inicializar el generador

        Args:
            db_path: Ruta a la base de datos SQLite (opcional)
        """
        self.db_manager = DatabaseManager(db_path) if db_path else None
        self.image_finder = ImageFinder()
        self.lyrics_finder = LyricsFinder()
        self.link_finder = LinkFinder(self.db_manager)
        self.html_generator = HTMLGenerator()
        self.album_processor = AlbumProcessor()

    def get_user_comment(self, album_title: str, artist: str) -> str:
        """
        Mostrar popup para obtener comentario del usuario

        Args:
            album_title: Título del álbum
            artist: Nombre del artista

        Returns:
            Comentario del usuario
        """
        try:
            # Crear ventana principal oculta
            root = tk.Tk()
            root.withdraw()

            # Obtener comentario mediante diálogo
            comment = simpledialog.askstring(
                "Comentario del Álbum",
                f"Escribe un comentario para:\n{artist} - {album_title}",
                parent=root
            )

            root.destroy()
            return comment or ""

        except Exception as e:
            logger.warning(f"Error obteniendo comentario: {e}")
            return ""

    def process_album(self, folder_path: str, output_dir: str) -> Dict[str, Any]:
        """
        Procesar un álbum completo y generar su página web

        Args:
            folder_path: Ruta a la carpeta con archivos del álbum
            output_dir: Directorio de salida

        Returns:
            Información completa del álbum procesado
        """
        logger.info(f"Procesando álbum en: {folder_path}")

        # 1. Extraer información básica del álbum
        album_info = self.album_processor.extract_album_info(folder_path)
        logger.info(f"Álbum encontrado: {album_info['artist']} - {album_info['title']}")

        # 2. Obtener comentario del usuario
        album_info['user_comment'] = self.get_user_comment(
            album_info['title'],
            album_info['artist']
        )

        # 3. Buscar imágenes
        logger.info("Buscando imágenes...")
        album_info['album_image'] = self.image_finder.find_album_image(
            album_info['artist'],
            album_info['title']
        )
        album_info['artist_image'] = self.image_finder.find_artist_image(
            album_info['artist']
        )

        # 4. Buscar letras de canciones
        logger.info("Buscando letras de canciones...")
        album_info['lyrics'] = self.lyrics_finder.find_lyrics(
            album_info['artist'],
            album_info['tracks']
        )

        # 5. Buscar enlaces relevantes
        logger.info("Buscando enlaces...")
        album_info['links'] = self.link_finder.find_links(
            album_info['artist'],
            album_info['title'],
            album_info.get('mbid')
        )

        # 6. Generar archivos web
        logger.info("Generando archivos web...")
        self._generate_web_files(album_info, output_dir)

        return album_info

    def _generate_web_files(self, album_info: Dict[str, Any], output_dir: str):
        """
        Generar archivos HTML en la estructura docs/albums

        Args:
            album_info: Información completa del álbum
            output_dir: Directorio base de salida
        """
        # Crear estructura docs/albums
        docs_dir = Path(output_dir) / "docs"
        albums_dir = docs_dir / "albums"
        albums_dir.mkdir(parents=True, exist_ok=True)

        # Generar nombre seguro para archivos
        safe_name = self._get_safe_filename(
            f"{album_info['artist']} - {album_info['title']}"
        )

        # Solo generar HTML (CSS y JS son globales)
        html_content = self.html_generator.generate_html(album_info)
        html_path = albums_dir / f"{safe_name}.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        # Guardar información completa como JSON
        json_path = albums_dir / f"{safe_name}_data.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(album_info, f, indent=2, ensure_ascii=False)

        # Actualizar índice de álbumes
        self._update_albums_index(album_info, safe_name, docs_dir)

        logger.info(f"Archivo generado en: {albums_dir}")
        logger.info(f"  - HTML: {html_path.name}")
        logger.info(f"  - Data: {json_path.name}")

    def _update_albums_index(self, album_info: Dict[str, Any], filename: str, docs_dir: Path):
        """
        Actualizar el índice de álbumes con el nuevo álbum

        Args:
            album_info: Información del álbum
            filename: Nombre del archivo HTML generado
            docs_dir: Directorio docs
        """
        albums_data_file = docs_dir / "albums-data.json"

        # Cargar datos existentes o crear nueva lista
        if albums_data_file.exists():
            with open(albums_data_file, 'r', encoding='utf-8') as f:
                albums_data = json.load(f)
        else:
            albums_data = []

        # Crear entrada para el álbum
        album_entry = {
            'filename': f"{filename}.html",
            'title': album_info.get('title', 'Álbum Desconocido'),
            'artist': album_info.get('artist', 'Artista Desconocido'),
            'year': album_info.get('year'),
            'genre': album_info.get('genre', []),
            'cover_image': self._get_cover_image_path(album_info),
            'tracks_count': len(album_info.get('tracks', [])),
            'has_lyrics': bool(album_info.get('lyrics')),
            'date_added': str(datetime.now().isoformat())
        }

        # Verificar si el álbum ya existe (evitar duplicados)
        existing_index = None
        for i, existing in enumerate(albums_data):
            if (existing.get('artist') == album_entry['artist'] and
                existing.get('title') == album_entry['title']):
                existing_index = i
                break

        if existing_index is not None:
            # Actualizar álbum existente
            albums_data[existing_index] = album_entry
            logger.info(f"Álbum actualizado en el índice: {album_entry['title']}")
        else:
            # Agregar nuevo álbum
            albums_data.append(album_entry)
            logger.info(f"Álbum agregado al índice: {album_entry['title']}")

        # Guardar datos actualizados
        with open(albums_data_file, 'w', encoding='utf-8') as f:
            json.dump(albums_data, f, indent=2, ensure_ascii=False)

    def _get_cover_image_path(self, album_info: Dict[str, Any]) -> Optional[str]:
        """
        Obtener ruta de la imagen de portada

        Args:
            album_info: Información del álbum

        Returns:
            Ruta a la imagen de portada o None
        """
        album_image = album_info.get('album_image')
        if album_image and 'url' in album_image:
            return album_image['url']
        return None

    def _get_safe_filename(self, name: str) -> str:
        """
        Generar nombre de archivo seguro

        Args:
            name: Nombre original

        Returns:
            Nombre seguro para usar como filename
        """
        # Reemplazar caracteres problemáticos
        safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_. "
        safe_name = "".join(c if c in safe_chars else "_" for c in name)

        # Limpiar espacios múltiples y guiones
        while "  " in safe_name:
            safe_name = safe_name.replace("  ", " ")
        while "__" in safe_name:
            safe_name = safe_name.replace("__", "_")

        return safe_name.strip(" -_")


def main():
    """Función principal"""
    parser = argparse.ArgumentParser(description="Generador de Páginas Web de Álbumes")
    parser.add_argument("folder", help="Carpeta que contiene los archivos del álbum")
    parser.add_argument("-o", "--output",
                       help="Carpeta de salida (por defecto: ./web_output)")
    parser.add_argument("--db", help="Ruta a la base de datos SQLite")
    parser.add_argument("-v", "--verbose", action="store_true",
                       help="Modo verboso")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Verificar carpeta de entrada
    folder_path = Path(args.folder)
    if not folder_path.exists():
        logger.error(f"La carpeta {folder_path} no existe")
        sys.exit(1)

    # Establecer carpeta de salida
    output_dir = args.output or "."

    try:
        # Crear generador
        generator = AlbumWebGenerator(args.db)

        # Procesar álbum
        album_info = generator.process_album(str(folder_path), output_dir)

        logger.info("¡Página web generada exitosamente!")

    except Exception as e:
        logger.error(f"Error procesando álbum: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
