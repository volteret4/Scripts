#!/usr/bin/env python3
"""
Script Indexer - Indexa scripts en una base de datos SQLite
"""

import sqlite3
import hashlib
import argparse
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import yaml
import re
import sys
import os


class ScriptIndexer:
    """Indexador de scripts para base de datos SQLite"""

    def __init__(self, db_path: Optional[str] = None):
        self.script_dir = Path(__file__).parent
        self.db_path = db_path or (self.script_dir / 'scripts.db')
        self.config_file = self.script_dir / 'script_config.yaml'

        # Cargar configuración al inicio
        self.config = self.load_config()

        # Extensiones soportadas (desde config o por defecto)
        self.supported_extensions = set(self.config.get('extensions', ['.py', '.sh', '.ini', '.env', '.yml', '.yaml']))

        # Carpetas excluidas (por defecto + config)
        self.default_excluded_folders = {
            '.git', '__pycache__', '.vscode', 'node_modules',
            '.pytest_cache', 'python_venv', '.env', 'venv',
            '.mypy_cache', '.tox', 'dist', 'build', '.eggs'
        }

        # Agregar carpetas excluidas del config
        config_excluded = set(self.config.get('excluded_folders', []))
        self.excluded_folders = self.default_excluded_folders.union(config_excluded)

        self.setup_database()

    def load_config(self) -> Dict:
        """Carga la configuración desde el archivo YAML"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
                    print(f"Configuración cargada desde: {self.config_file}")
                    return config
            except (yaml.YAMLError, IOError) as e:
                print(f"Error leyendo configuración: {e}")

        print("Usando configuración por defecto")
        return {}

    def setup_database(self):
        """Crea las tablas de la base de datos"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute('PRAGMA foreign_keys = ON')

        # Optimizaciones de SQLite
        self.conn.execute('PRAGMA synchronous = OFF')
        self.conn.execute('PRAGMA journal_mode = MEMORY')
        self.conn.execute('PRAGMA temp_store = MEMORY')
        self.conn.execute('PRAGMA cache_size = 10000')

        # Tabla principal de scripts
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS scripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                filename TEXT NOT NULL,
                directory TEXT NOT NULL,
                extension TEXT NOT NULL,
                size_bytes INTEGER,
                hash TEXT,
                description TEXT,
                author TEXT,
                repository TEXT,
                license TEXT,
                notes TEXT,
                dependencies TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_modified TIMESTAMP,
                is_executable BOOLEAN DEFAULT 0,
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

        # Tabla de relación scripts-tags
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS script_tags (
                script_id INTEGER,
                tag_id INTEGER,
                PRIMARY KEY (script_id, tag_id),
                FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
            )
        ''')

        # Índices para mejorar rendimiento
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_scripts_path ON scripts(path)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_scripts_filename ON scripts(filename)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_scripts_directory ON scripts(directory)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_scripts_extension ON scripts(extension)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_scripts_hash ON scripts(hash)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(name)')

        # Vista para búsquedas fáciles
        self.conn.execute('DROP VIEW IF EXISTS scripts_with_tags')
        self.conn.execute('''
            CREATE VIEW scripts_with_tags AS
            SELECT
                s.*,
                COALESCE(GROUP_CONCAT(t.name, ','), '') as tags
            FROM scripts s
            LEFT JOIN script_tags st ON s.id = st.script_id
            LEFT JOIN tags t ON st.tag_id = t.id
            GROUP BY s.id, s.path, s.filename, s.directory, s.extension,
                     s.size_bytes, s.hash, s.description, s.author, s.repository,
                     s.license, s.notes, s.dependencies, s.created_at, s.updated_at,
                     s.last_modified, s.is_executable, s.is_valid
        ''')

        self.conn.commit()

    def get_script_folders(self) -> List[Path]:
        """Obtiene las carpetas de scripts del archivo de configuración"""
        # Carpetas por defecto
        default_folders = [
            Path.home() / 'Scripts',
            Path.home() / '.local/bin',
            Path.home() / 'bin',
        ]

        # Carpetas desde configuración
        config_folders = self.config.get('script_folders', [])

        all_folders = []

        # Agregar carpetas del config primero (tienen prioridad)
        for folder_str in config_folders:
            folder_path = Path(folder_str).expanduser()
            all_folders.append(folder_path)

        # Agregar carpetas por defecto que no estén ya incluidas
        for default_folder in default_folders:
            if default_folder not in all_folders:
                all_folders.append(default_folder)

        # Filtrar carpetas existentes
        existing_folders = []
        for folder in all_folders:
            if folder.exists() and folder.is_dir():
                existing_folders.append(folder)
            else:
                print(f"Carpeta no existe o no es accesible: {folder}")

        if existing_folders:
            print(f"Carpetas a indexar: {[str(f) for f in existing_folders]}")
        else:
            print("⚠️  No se encontraron carpetas válidas para indexar")

        return existing_folders

    def get_excluded_folders(self) -> set:
        """Obtiene las carpetas a excluir (ya cargadas en __init__)"""
        return self.excluded_folders

    def create_default_config(self):
        """Crea un archivo de configuración por defecto"""
        config = {
            'script_folders': [
                str(Path.home() / 'Scripts'),
                str(Path.home() / '.local/bin'),
                str(Path.home() / 'bin'),
            ],
            'excluded_folders': list(self.default_excluded_folders),
            'extensions': ['.py', '.sh', '.ini', '.env', '.yml', '.yaml']
        }

        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
            print(f"Archivo de configuración creado: {self.config_file}")
        except IOError as e:
            print(f"Error creando configuración: {e}")

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

    def extract_script_metadata(self, file_path: Path) -> Dict:
        """Extrae metadata del header del script"""
        metadata = {
            'description': '',
            'author': '',
            'repository': '',
            'license': '',
            'notes': '',
            'dependencies': ''
        }

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(2000)  # Leer solo el inicio del archivo

                # Patrones para extraer metadata
                patterns = {
                    'description': [
                        r'#\s*Description:\s*(.+)',
                        r'#\s*DESC:\s*(.+)',
                        r'"""[\s\S]*?Description:\s*(.+?)[\s\S]*?"""',
                        r'#\s*(.+?)(?:\n|$)'  # Primera línea de comentario
                    ],
                    'author': [
                        r'#\s*Author:\s*(.+)',
                        r'#\s*By:\s*(.+)',
                        r'#\s*Created by:\s*(.+)'
                    ],
                    'repository': [
                        r'#\s*Repository:\s*(.+)',
                        r'#\s*Repo:\s*(.+)',
                        r'#\s*URL:\s*(.+)',
                        r'#\s*GitHub:\s*(.+)'
                    ],
                    'license': [
                        r'#\s*License:\s*(.+)',
                        r'#\s*Licence:\s*(.+)'
                    ],
                    'notes': [
                        r'#\s*Notes:\s*(.+)',
                        r'#\s*Note:\s*(.+)'
                    ],
                    'dependencies': [
                        r'#\s*Dependencies:\s*(.+)',
                        r'#\s*Requires:\s*(.+)',
                        r'#\s*Deps:\s*(.+)'
                    ]
                }

                for field, field_patterns in patterns.items():
                    for pattern in field_patterns:
                        match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
                        if match:
                            metadata[field] = match.group(1).strip()
                            break

        except Exception as e:
            print(f"Error extrayendo metadata de {file_path}: {e}")

        return metadata

    def is_script_changed(self, file_path: Path) -> bool:
        """Verifica si un script ha cambiado desde la última indexación"""
        cursor = self.conn.execute(
            'SELECT last_modified, hash FROM scripts WHERE path = ?',
            (str(file_path),)
        )
        result = cursor.fetchone()

        if not result:
            return True  # Archivo nuevo

        db_modified, db_hash = result
        file_modified = datetime.fromtimestamp(file_path.stat().st_mtime)

        # Comparar por fecha de modificación primero
        if db_modified != file_modified.isoformat():
            return True

        # Si las fechas coinciden, comparar hash
        current_hash = self.get_file_hash(file_path)
        return current_hash != db_hash

    def index_file(self, file_path: Path, force_update: bool = False) -> bool:
        """Indexa un archivo de script individual"""
        try:
            # Verificar si el archivo ha cambiado
            if not force_update and not self.is_script_changed(file_path):
                return False

            # Obtener información del archivo
            stat = file_path.stat()
            hash_value = self.get_file_hash(file_path)
            metadata = self.extract_script_metadata(file_path)

            # Verificar si es ejecutable
            is_executable = os.access(file_path, os.X_OK)

            # Preparar datos
            data = {
                'path': str(file_path),
                'filename': file_path.name,
                'directory': str(file_path.parent),
                'extension': file_path.suffix.lower(),
                'size_bytes': stat.st_size,
                'hash': hash_value,
                'description': metadata['description'],
                'author': metadata['author'],
                'repository': metadata['repository'],
                'license': metadata['license'],
                'notes': metadata['notes'],
                'dependencies': metadata['dependencies'],
                'last_modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'updated_at': datetime.now().isoformat(),
                'is_executable': is_executable
            }

            # Insertar o actualizar en la base de datos
            self.conn.execute('''
                INSERT OR REPLACE INTO scripts
                (path, filename, directory, extension, size_bytes, hash, description,
                 author, repository, license, notes, dependencies, last_modified,
                 updated_at, is_executable)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['path'], data['filename'], data['directory'], data['extension'],
                data['size_bytes'], data['hash'], data['description'], data['author'],
                data['repository'], data['license'], data['notes'], data['dependencies'],
                data['last_modified'], data['updated_at'], data['is_executable']
            ))

            return True

        except Exception as e:
            print(f"Error indexando {file_path}: {e}")
            return False

    def index_directory(self, directory: Path, recursive: bool = True,
                       progress_callback=None) -> Dict[str, int]:
        """Indexa todos los scripts en un directorio"""
        stats = {'indexed': 0, 'updated': 0, 'errors': 0, 'skipped': 0}

        if not directory.exists() or not directory.is_dir():
            print(f"Directorio no existe: {directory}")
            return stats

        print(f"Indexando: {directory}")

        # Obtener todos los archivos de script
        files_to_process = []

        try:
            for file_path in directory.rglob("*" if recursive else "*"):
                if file_path.is_file():
                    # Verificar si está en carpeta excluida
                    if any(excluded in file_path.parts for excluded in self.excluded_folders):
                        continue

                    # Verificar extensión
                    if file_path.suffix.lower() in self.supported_extensions:
                        files_to_process.append(file_path)

        except (PermissionError, OSError) as e:
            print(f"Error accediendo a {directory}: {e}")
            return stats

        total_files = len(files_to_process)
        print(f"Encontrados {total_files} archivos de script")

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
                elif (i + 1) % 25 == 0:
                    print(f"Procesados {i + 1}/{total_files} archivos... ({((i + 1) / total_files) * 100:.1f}%)")

                # Commit cada 50 archivos
                if (i + 1) % 50 == 0:
                    self.conn.commit()

            except Exception as e:
                stats['errors'] += 1
                print(f"Error procesando {file_path}: {e}")

        # Commit final
        self.conn.commit()
        print(f"Completado {directory}: {stats['updated']} actualizados, {stats['skipped']} sin cambios")

        return stats

    def cleanup_database(self):
        """Limpia scripts que ya no existen en el sistema"""
        print("Limpiando base de datos...")

        cursor = self.conn.execute('SELECT id, path FROM scripts')
        scripts_to_remove = []

        for script_id, path in cursor.fetchall():
            if not Path(path).exists():
                scripts_to_remove.append(script_id)

        if scripts_to_remove:
            placeholders = ','.join('?' * len(scripts_to_remove))
            self.conn.execute(
                f'DELETE FROM scripts WHERE id IN ({placeholders})',
                scripts_to_remove
            )
            print(f"Eliminados {len(scripts_to_remove)} scripts obsoletos")

        # Limpiar tags huérfanos
        self.conn.execute('''
            DELETE FROM tags WHERE id NOT IN (
                SELECT DISTINCT tag_id FROM script_tags
            )
        ''')

        self.conn.commit()

    def get_stats(self) -> Dict[str, int]:
        """Obtiene estadísticas de la base de datos"""
        stats = {}

        cursor = self.conn.execute('SELECT COUNT(*) FROM scripts')
        stats['total_scripts'] = cursor.fetchone()[0]

        cursor = self.conn.execute('SELECT COUNT(*) FROM scripts WHERE is_executable = 1')
        stats['executable_scripts'] = cursor.fetchone()[0]

        cursor = self.conn.execute('SELECT COUNT(*) FROM tags')
        stats['total_tags'] = cursor.fetchone()[0]

        cursor = self.conn.execute('SELECT COUNT(DISTINCT script_id) FROM script_tags')
        stats['tagged_scripts'] = cursor.fetchone()[0]

        cursor = self.conn.execute('SELECT COUNT(DISTINCT directory) FROM scripts')
        stats['directories'] = cursor.fetchone()[0]

        # Estadísticas por extensión
        cursor = self.conn.execute('''
            SELECT extension, COUNT(*) FROM scripts
            GROUP BY extension ORDER BY COUNT(*) DESC
        ''')
        stats['by_extension'] = dict(cursor.fetchall())

        return stats

    def run_full_index(self, force: bool = False):
        """Ejecuta una indexación completa"""
        print("=== Iniciando indexación de scripts ===")

        # Crear configuración por defecto si no existe
        if not self.config_file.exists():
            print("Archivo de configuración no encontrado, creando uno por defecto...")
            self.create_default_config()

        # Mostrar configuración actual
        print(f"Extensiones soportadas: {sorted(self.supported_extensions)}")
        print(f"Carpetas excluidas: {sorted(self.excluded_folders)}")

        # Obtener carpetas a indexar
        folders = self.get_script_folders()

        if not folders:
            print("❌ No hay carpetas válidas para indexar.")
            print("Edita el archivo 'script_config.yaml' y agrega carpetas existentes.")
            return

        print(f"📁 Indexando {len(folders)} carpetas...")

        total_stats = {'indexed': 0, 'updated': 0, 'errors': 0, 'skipped': 0}

        # Indexar cada carpeta
        for folder in folders:
            stats = self.index_directory(folder, recursive=True)
            for key in total_stats:
                total_stats[key] += stats[key]

        # Limpiar base de datos
        if not force:
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
        print(f"Total de scripts: {db_stats['total_scripts']}")
        print(f"Scripts ejecutables: {db_stats['executable_scripts']}")
        print(f"Scripts con tags: {db_stats['tagged_scripts']}")
        print(f"Total de tags: {db_stats['total_tags']}")
        print(f"Directorios: {db_stats['directories']}")

        if db_stats['by_extension']:
            print("\nPor extensión:")
            for ext, count in db_stats['by_extension'].items():
                print(f"  {ext}: {count}")

        # Sugerencias si no se encontraron muchos scripts
        if db_stats['total_scripts'] < 5:
            print(f"\n💡 Sugerencias:")
            print(f"- Verifica que las carpetas en '{self.config_file}' contengan scripts")
            print(f"- Asegúrate de que los scripts tengan extensiones válidas: {sorted(self.supported_extensions)}")
            print(f"- Ejecuta con --force para re-indexar todo: python {sys.argv[0]} --force")
    def close(self):
        """Cierra la conexión a la base de datos"""
        if hasattr(self, 'conn'):
            self.conn.close()


def main():
    parser = argparse.ArgumentParser(description='Indexador de scripts para Script Manager')
    parser.add_argument('--force', '-f', action='store_true',
                       help='Forzar re-indexación completa')
    parser.add_argument('--db', type=str,
                       help='Ruta personalizada para la base de datos')
    parser.add_argument('--stats', '-s', action='store_true',
                       help='Mostrar solo estadísticas')
    parser.add_argument('--config', action='store_true',
                       help='Crear archivo de configuración por defecto')

    args = parser.parse_args()

    indexer = ScriptIndexer(args.db)

    try:
        if args.config:
            indexer.create_default_config()
        elif args.stats:
            stats = indexer.get_stats()
            print("=== Estadísticas de la base de datos ===")
            for key, value in stats.items():
                if key == 'by_extension':
                    print("Por extensión:")
                    for ext, count in value.items():
                        print(f"  {ext}: {count}")
                else:
                    print(f"{key.replace('_', ' ').title()}: {value}")
        else:
            indexer.run_full_index(args.force)
    finally:
        indexer.close()


if __name__ == '__main__':
    main()
