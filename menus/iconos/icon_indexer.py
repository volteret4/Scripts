#!/usr/bin/env python3
"""
Icon Indexer - Indexa todos los iconos del sistema en una base de datos SQLite
"""

import sqlite3
import json
import hashlib
import argparse
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import yaml
from PIL import Image
import mimetypes


class IconIndexer:
    """Indexador de iconos para base de datos SQLite"""

    def __init__(self, db_path: Optional[str] = None):
        self.script_dir = Path(__file__).parent
        self.db_path = db_path or (self.script_dir / 'icons.db')
        self.config_file = self.script_dir / 'config.yaml'
        self.tags_file = self.script_dir / 'tags.json'  # Para migrar tags existentes

        # Extensiones de imagen soportadas
        self.supported_extensions = {
            '.png', '.jpg', '.jpeg', '.svg', '.ico', '.bmp',
            '.gif', '.xpm', '.webp', '.tiff', '.tga'
        }

        self.setup_database()

    def setup_database(self):
        """Crea las tablas de la base de datos"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute('PRAGMA foreign_keys = ON')

        # Tabla principal de iconos
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS icons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                filename TEXT NOT NULL,
                directory TEXT NOT NULL,
                size_bytes INTEGER,
                width INTEGER,
                height INTEGER,
                format TEXT,
                hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_modified TIMESTAMP,
                is_valid BOOLEAN DEFAULT 1
            )
        ''')

        # Tabla de tags
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Tabla de relación iconos-tags
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS icon_tags (
                icon_id INTEGER,
                tag_id INTEGER,
                PRIMARY KEY (icon_id, tag_id),
                FOREIGN KEY (icon_id) REFERENCES icons(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
            )
        ''')

        # Índices para mejorar rendimiento
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_icons_path ON icons(path)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_icons_filename ON icons(filename)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_icons_directory ON icons(directory)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_icons_hash ON icons(hash)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(name)')

        # Vista para búsquedas fáciles
        self.conn.execute('DROP VIEW IF EXISTS icons_with_tags')
        self.conn.execute('''
            CREATE VIEW icons_with_tags AS
            SELECT
                i.*,
                COALESCE(GROUP_CONCAT(t.name, ','), '') as tags
            FROM icons i
            LEFT JOIN icon_tags it ON i.id = it.icon_id
            LEFT JOIN tags t ON it.tag_id = t.id
            GROUP BY i.id, i.path, i.filename, i.directory, i.size_bytes,
                     i.width, i.height, i.format, i.hash, i.created_at,
                     i.updated_at, i.last_modified, i.is_valid
        ''')

        self.conn.commit()

    def get_icon_folders(self) -> List[Path]:
        """Obtiene las carpetas de iconos del sistema y configuración"""
        potential_folders = [
            # Carpetas del usuario
            Path.home() / '.local/share/icons',
            Path.home() / '.icons',
            Path.home() / '.local/share/pixmaps',

            # Carpetas del sistema
            Path('/usr/share/pixmaps'),

            # Carpetas específicas de escritorios
            Path('/usr/share/icons/Papirus/48x48'),
            Path('/usr/share/icons/Papirus-Dark/48x48'),
            Path('/usr/share/icons/hicolor/48x48'),
            Path('/usr/share/icons/Adwaita/scalable '),

            Path('/usr/share/icons/Moka/48x48'),
            Path('/usr/share/icons/Sardi/48'),
            Path('/usr/share/icons/Surfn/48'),
            Path('/usr/share/icons/ubuntu-mono-dark/status/48'),
            Path('/usr/share/icons/Tango/48x48'),

            # Carpetas adicionales
            Path.home() / 'Imágenes/Iconos',
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
                        potential_folders.append(folder_path)
            except (yaml.YAMLError, IOError):
                pass

        # Filtrar carpetas existentes
        existing_folders = []
        for folder in potential_folders:
            if folder.exists() and folder.is_dir():
                existing_folders.append(folder)

        # Agregar carpetas de /opt
        opt_path = Path('/opt')
        if opt_path.exists():
            for app_dir in opt_path.iterdir():
                if app_dir.is_dir():
                    icons_dir = app_dir / 'share/icons'
                    if icons_dir.exists():
                        existing_folders.append(icons_dir)

        return existing_folders

    def get_file_hash(self, file_path: Path) -> str:
        """Calcula el hash MD5 de un archivo"""
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except (IOError, OSError):
            return ""

    def get_image_info(self, file_path: Path) -> Dict:
        """Obtiene información de la imagen"""
        info = {
            'width': None,
            'height': None,
            'format': None
        }

        try:
            # Para SVG, intentar parsear básicamente
            if file_path.suffix.lower() == '.svg':
                info['format'] = 'SVG'
                # Podríamos parsear el SVG para obtener dimensiones, pero es complejo
                # Por ahora dejamos las dimensiones como None
                return info

            # Para otros formatos, usar PIL
            try:
                with Image.open(file_path) as img:
                    info['width'] = img.width
                    info['height'] = img.height
                    info['format'] = img.format
                    return info
            except Exception as pil_error:
                # Si PIL falla, intentar con información básica del archivo
                pass

        except Exception as e:
            # Error general al acceder al archivo
            pass

        # Fallback: usar mimetypes para al menos determinar el formato
        try:
            mime_type, _ = mimetypes.guess_type(str(file_path))
            if mime_type and mime_type.startswith('image/'):
                info['format'] = mime_type.split('/')[-1].upper()
        except Exception:
            # Si todo falla, usar la extensión del archivo
            info['format'] = file_path.suffix[1:].upper() if file_path.suffix else 'UNKNOWN'

        return info

    def is_icon_changed(self, file_path: Path) -> bool:
        """Verifica si un icono ha cambiado desde la última indexación"""
        cursor = self.conn.execute(
            'SELECT last_modified, hash FROM icons WHERE path = ?',
            (str(file_path),)
        )
        result = cursor.fetchone()

        if not result:
            return True  # Archivo nuevo

        db_modified, db_hash = result
        file_modified = datetime.fromtimestamp(file_path.stat().st_mtime)

        # Comparar por fecha de modificación primero (más rápido)
        if db_modified != file_modified.isoformat():
            return True

        # Si las fechas coinciden, comparar hash para estar seguros
        current_hash = self.get_file_hash(file_path)
        return current_hash != db_hash

    def index_file(self, file_path: Path, force_update: bool = False) -> bool:
        """Indexa un archivo de icono individual"""
        try:
            # Verificar si el archivo ha cambiado
            if not force_update and not self.is_icon_changed(file_path):
                return False  # No necesita actualización

            # Obtener información del archivo
            stat = file_path.stat()
            hash_value = self.get_file_hash(file_path)
            image_info = self.get_image_info(file_path)

            # Preparar datos
            data = {
                'path': str(file_path),
                'filename': file_path.name,
                'directory': str(file_path.parent),
                'size_bytes': stat.st_size,
                'width': image_info['width'],
                'height': image_info['height'],
                'format': image_info['format'],
                'hash': hash_value,
                'last_modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'updated_at': datetime.now().isoformat()
            }

            # Insertar o actualizar en la base de datos
            self.conn.execute('''
                INSERT OR REPLACE INTO icons
                (path, filename, directory, size_bytes, width, height, format, hash, last_modified, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['path'], data['filename'], data['directory'],
                data['size_bytes'], data['width'], data['height'],
                data['format'], data['hash'], data['last_modified'], data['updated_at']
            ))

            return True

        except Exception as e:
            print(f"Error indexando {file_path}: {e}")
            return False

    def index_directory(self, directory: Path, recursive: bool = True,
                       progress_callback=None) -> Dict[str, int]:
        """Indexa todos los iconos en un directorio"""
        stats = {'indexed': 0, 'updated': 0, 'errors': 0, 'skipped': 0}

        if not directory.exists() or not directory.is_dir():
            print(f"Directorio no existe o no es accesible: {directory}")
            return stats

        print(f"Indexando: {directory}")

        # Obtener todos los archivos de imagen
        files_to_process = []
        pattern = "**/*" if recursive else "*"

        print("Buscando archivos de imagen...")
        try:
            for file_path in directory.glob(pattern):
                if (file_path.is_file() and
                    file_path.suffix.lower() in self.supported_extensions):
                    files_to_process.append(file_path)
        except (PermissionError, OSError) as e:
            print(f"Error accediendo a {directory}: {e}")
            return stats

        total_files = len(files_to_process)
        print(f"Encontrados {total_files} archivos de imagen")

        if total_files == 0:
            return stats

        # Procesar archivos
        for i, file_path in enumerate(files_to_process):
            try:
                if self.index_file(file_path):
                    stats['updated'] += 1
                else:
                    stats['skipped'] += 1

                stats['indexed'] += 1

                # Callback de progreso
                if progress_callback:
                    progress_callback(i + 1, total_files, file_path)
                elif (i + 1) % 50 == 0:  # Mostrar progreso cada 50 archivos
                    print(f"Procesados {i + 1}/{total_files} archivos... ({((i + 1) / total_files) * 100:.1f}%)")

                # Commit cada 100 archivos para mejorar rendimiento
                if (i + 1) % 100 == 0:
                    self.conn.commit()

            except Exception as e:
                stats['errors'] += 1
                print(f"Error procesando {file_path}: {e}")

        # Commit final para este directorio
        self.conn.commit()
        print(f"Completado {directory}: {stats['updated']} actualizados, {stats['skipped']} sin cambios, {stats['errors']} errores")

        return stats

    def migrate_tags_from_json(self):
        """Migra tags existentes desde el archivo JSON"""
        if not self.tags_file.exists():
            return

        try:
            with open(self.tags_file, 'r', encoding='utf-8') as f:
                tags_data = json.load(f)

            print("Migrando tags desde JSON...")

            for file_path, tags in tags_data.items():
                if not tags:
                    continue

                # Buscar el icono en la base de datos
                cursor = self.conn.execute(
                    'SELECT id FROM icons WHERE path = ?',
                    (file_path,)
                )
                result = cursor.fetchone()

                if not result:
                    continue  # Icono no encontrado

                icon_id = result[0]

                # Agregar tags
                for tag_name in tags:
                    self.add_tag_to_icon(icon_id, tag_name.strip())

            self.conn.commit()
            print("Migración de tags completada")

        except (json.JSONDecodeError, IOError) as e:
            print(f"Error migrando tags: {e}")

    def add_tag_to_icon(self, icon_id: int, tag_name: str):
        """Agrega un tag a un icono"""
        if not tag_name:
            return

        # Crear tag si no existe
        self.conn.execute(
            'INSERT OR IGNORE INTO tags (name) VALUES (?)',
            (tag_name,)
        )

        # Obtener ID del tag
        cursor = self.conn.execute(
            'SELECT id FROM tags WHERE name = ?',
            (tag_name,)
        )
        tag_id = cursor.fetchone()[0]

        # Crear relación icono-tag
        self.conn.execute(
            'INSERT OR IGNORE INTO icon_tags (icon_id, tag_id) VALUES (?, ?)',
            (icon_id, tag_id)
        )

    def cleanup_database(self):
        """Limpia iconos que ya no existen en el sistema"""
        print("Limpiando base de datos...")

        cursor = self.conn.execute('SELECT id, path FROM icons')
        icons_to_remove = []

        for icon_id, path in cursor.fetchall():
            if not Path(path).exists():
                icons_to_remove.append(icon_id)

        if icons_to_remove:
            placeholders = ','.join('?' * len(icons_to_remove))
            self.conn.execute(
                f'DELETE FROM icons WHERE id IN ({placeholders})',
                icons_to_remove
            )
            print(f"Eliminados {len(icons_to_remove)} iconos obsoletos")

        # Limpiar tags huérfanos
        self.conn.execute('''
            DELETE FROM tags WHERE id NOT IN (
                SELECT DISTINCT tag_id FROM icon_tags
            )
        ''')

        self.conn.commit()

    def get_stats(self) -> Dict[str, int]:
        """Obtiene estadísticas de la base de datos"""
        stats = {}

        cursor = self.conn.execute('SELECT COUNT(*) FROM icons')
        stats['total_icons'] = cursor.fetchone()[0]

        cursor = self.conn.execute('SELECT COUNT(*) FROM tags')
        stats['total_tags'] = cursor.fetchone()[0]

        cursor = self.conn.execute('''
            SELECT COUNT(DISTINCT icon_id) FROM icon_tags
        ''')
        stats['tagged_icons'] = cursor.fetchone()[0]

        cursor = self.conn.execute('SELECT COUNT(DISTINCT directory) FROM icons')
        stats['directories'] = cursor.fetchone()[0]

        # Estadísticas adicionales
        cursor = self.conn.execute('SELECT COUNT(*) FROM icon_tags')
        stats['total_tag_assignments'] = cursor.fetchone()[0]

        cursor = self.conn.execute('''
            SELECT COUNT(*) FROM icons WHERE is_valid = 1
        ''')
        stats['valid_icons'] = cursor.fetchone()[0]

        return stats

    def run_full_index(self, force: bool = False):
        """Ejecuta una indexación completa"""
        print("=== Iniciando indexación de iconos ===")

        # Migrar tags existentes
        self.migrate_tags_from_json()

        # Obtener carpetas a indexar
        folders = self.get_icon_folders()
        print(f"Carpetas a indexar: {len(folders)}")

        total_stats = {'indexed': 0, 'updated': 0, 'errors': 0, 'skipped': 0}

        # Indexar cada carpeta
        for folder in folders:
            stats = self.index_directory(folder, recursive=True)
            for key in total_stats:
                total_stats[key] += stats[key]

        # Limpiar base de datos
        if not force:  # Solo limpiar en indexación incremental
            self.cleanup_database()

        # Commit final
        self.conn.commit()

        # Mostrar estadísticas
        print("\n=== Indexación completada ===")
        print(f"Archivos procesados: {total_stats['indexed']}")
        print(f"Archivos actualizados: {total_stats['updated']}")
        print(f"Archivos sin cambios: {total_stats['skipped']}")
        print(f"Errores: {total_stats['errors']}")

        db_stats = self.get_stats()
        print(f"\n=== Estadísticas de la base de datos ===")
        print(f"Total de iconos: {db_stats['total_icons']}")
        print(f"Iconos con tags: {db_stats['tagged_icons']}")
        print(f"Total de tags: {db_stats['total_tags']}")
        print(f"Directorios: {db_stats['directories']}")

    def close(self):
        """Cierra la conexión a la base de datos"""
        if hasattr(self, 'conn'):
            self.conn.close()


def main():
    parser = argparse.ArgumentParser(description='Indexador de iconos para Icon Browser')
    parser.add_argument('--force', '-f', action='store_true',
                       help='Forzar re-indexación completa')
    parser.add_argument('--db', type=str,
                       help='Ruta personalizada para la base de datos')
    parser.add_argument('--stats', '-s', action='store_true',
                       help='Mostrar solo estadísticas')

    args = parser.parse_args()

    indexer = IconIndexer(args.db)

    try:
        if args.stats:
            stats = indexer.get_stats()
            print("=== Estadísticas de la base de datos ===")
            for key, value in stats.items():
                print(f"{key.replace('_', ' ').title()}: {value}")
        else:
            indexer.run_full_index(args.force)
    finally:
        indexer.close()


if __name__ == '__main__':
    main()
