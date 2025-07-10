#!/usr/bin/env python3
"""
Dotfiles Indexer - Indexa archivos de configuración en una base de datos SQLite
para búsquedas rápidas por nombre y ruta.
Author: volteret4
Dependencies: sqlite3, pathlib, hashlib, argparse
"""

import sqlite3
import hashlib
import argparse
import mimetypes
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

# ==================== CONFIGURACIÓN ====================
# Edita estas variables según tus necesidades

# Rutas base a indexar (expandir ~ automáticamente)
SEARCH_PATHS = [
    "~/.local/share/chezmoi",
]

# Rutas específicas a excluir (expandir ~ automáticamente)
EXCLUDE_PATHS = [
    "~/.local/share/chezmoi/Scripts",
    "~/.local/share/chezmoi/.git",
    "~/.local/share/chezmoi/.ropeproject",
    "~/.config/google-chrome",
    "~/.config/chromium",
    "~/.config/mozilla/firefox",
    "~/.config/libreoffice",
    "~/.config/obs-studio",
    "~/.config/discord",
    "~/.config/Slack",
    "~/.config/QtProject/qtcreator/pylsp",
    "~/.config/VSCodium/Cache",
    "~/.config/VSCodium/User/History",
    "~/.config/VSCodium/User/workspaceStorage",
    "~/.config/VSCodium/WebStorage",
    "~/.config/VSCodium/logs",
    "~/.config/spotify",
    "~/.config/Steam",
    "~/.config/Ferdium/Partitions"
    "~/.config/pulse",  # PulseAudio genera muchos archivos temporales
    "~/.config/systemd/user",  # Archivos de systemd del usuario
    "/etc/ssl",  # Certificados SSL
    "/etc/alternatives",  # Enlaces simbólicos de alternatives
    "/etc/X11",  # Configuración de X11 (muchos archivos)
]

# Patrones de archivos a excluir (case-insensitive)
EXCLUDE_PATTERNS = [
    "*.log",
    "*.tmp",
    "*.cache",
    "*.pid",
    "*.lock",
    "*.swp",
    "*.swo",
    "*~",
    ".DS_Store",
    "Thumbs.db",
    "*.pyc",
    "*.pyo",
    "__pycache__",
    ".git",
    ".svn",
    ".hg",
    "node_modules",
    ".npm",
    ".yarn",
    "*.o",
    "*.so",
    "*.dll",
    "*.exe",
    "*.bin",
    "*.iso",
    "*.img",
    "*.deb",
    "*.rpm",
    "*.tar.*",
    "*.zip",
    "*.gz",
    "*.bz2",
    "*.xz",
]

# Extensiones de archivos de configuración comunes
CONFIG_EXTENSIONS = {
    ".conf", ".config", ".cfg", ".ini", ".yaml", ".yml", ".json", ".toml",
    ".xml", ".desktop", ".service", ".timer", ".mount", ".automount",
    ".sh", ".bash", ".zsh", ".fish", ".profile", ".bashrc", ".zshrc",
    ".vimrc", ".nvimrc", ".tmux.conf", ".gitconfig", ".gitignore",
    ".editorconfig", ".eslintrc", ".prettierrc", ".clang-format",
    ".py", ".lua", ".vim", ".el", ".emacs", ".xdefaults", ".Xresources",
    ".xinitrc", ".xprofile", ".inputrc", ".dircolors", ".aliases",
}

# Tamaño máximo de archivo a indexar (en bytes)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# Archivos sin extensión que son configuración
CONFIG_FILENAMES = {
    "Makefile", "Dockerfile", "Vagrantfile", "Pipfile", "Gemfile",
    "requirements.txt", "package.json", "composer.json", "CMakeLists.txt",
    "configure", "config", "rc", "profile", "bashrc", "zshrc", "vimrc",
    "tmux.conf", "gitconfig", "gitignore", "editorconfig", "aliases",
    "exports", "functions", "path", "screenrc",
}

# ==================== FIN CONFIGURACIÓN ====================


class DotfilesIndexer:
    """Indexador de archivos de configuración para base de datos SQLite"""

    def __init__(self, db_path: Optional[str] = None):
        self.script_dir = Path(__file__).parent
        self.db_path = db_path or (self.script_dir / 'dotfiles.db')

        # Expandir rutas de configuración
        self.search_paths = [Path(p).expanduser() for p in SEARCH_PATHS]
        self.exclude_paths = set(Path(p).expanduser() for p in EXCLUDE_PATHS)
        self.exclude_patterns = set(pattern.lower() for pattern in EXCLUDE_PATTERNS)
        self.config_extensions = CONFIG_EXTENSIONS
        self.config_filenames = CONFIG_FILENAMES
        self.max_file_size = MAX_FILE_SIZE

        self.setup_database()

    def setup_database(self):
        """Crea las tablas de la base de datos con índices optimizados"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute('PRAGMA foreign_keys = ON')
        self.conn.execute('PRAGMA journal_mode = WAL')  # Mejor rendimiento
        self.conn.execute('PRAGMA synchronous = NORMAL')
        self.conn.execute('PRAGMA cache_size = 10000')
        self.conn.execute('PRAGMA temp_store = MEMORY')

        # Tabla principal de archivos
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS dotfiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                filename TEXT NOT NULL,
                directory TEXT NOT NULL,
                extension TEXT,
                size_bytes INTEGER,
                hash TEXT,
                mime_type TEXT,
                is_config BOOLEAN DEFAULT 0,
                is_executable BOOLEAN DEFAULT 0,
                source_root TEXT NOT NULL,  -- Ruta base de donde viene el archivo
                relative_path TEXT NOT NULL,  -- Ruta relativa desde source_root
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_modified TIMESTAMP,
                last_indexed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Tabla de categorías para clasificar archivos
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                pattern TEXT  -- Patrón regex opcional para auto-clasificación
            )
        ''')

        # Tabla de relación archivo-categoría
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS file_categories (
                file_id INTEGER,
                category_id INTEGER,
                PRIMARY KEY (file_id, category_id),
                FOREIGN KEY (file_id) REFERENCES dotfiles(id) ON DELETE CASCADE,
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
            )
        ''')

        # Índices para búsquedas rápidas
        indices = [
            'CREATE INDEX IF NOT EXISTS idx_dotfiles_path ON dotfiles(path)',
            'CREATE INDEX IF NOT EXISTS idx_dotfiles_filename ON dotfiles(filename)',
            'CREATE INDEX IF NOT EXISTS idx_dotfiles_directory ON dotfiles(directory)',
            'CREATE INDEX IF NOT EXISTS idx_dotfiles_extension ON dotfiles(extension)',
            'CREATE INDEX IF NOT EXISTS idx_dotfiles_source_root ON dotfiles(source_root)',
            'CREATE INDEX IF NOT EXISTS idx_dotfiles_relative_path ON dotfiles(relative_path)',
            'CREATE INDEX IF NOT EXISTS idx_dotfiles_is_config ON dotfiles(is_config)',
            'CREATE INDEX IF NOT EXISTS idx_dotfiles_last_modified ON dotfiles(last_modified)',
            'CREATE INDEX IF NOT EXISTS idx_dotfiles_hash ON dotfiles(hash)',

            # Índices compuestos para búsquedas complejas
            'CREATE INDEX IF NOT EXISTS idx_dotfiles_filename_ext ON dotfiles(filename, extension)',
            'CREATE INDEX IF NOT EXISTS idx_dotfiles_config_source ON dotfiles(is_config, source_root)',

            # Índices para FTS (Full Text Search) - búsqueda en texto
            'CREATE INDEX IF NOT EXISTS idx_dotfiles_filename_fts ON dotfiles(filename COLLATE NOCASE)',
            'CREATE INDEX IF NOT EXISTS idx_dotfiles_relative_path_fts ON dotfiles(relative_path COLLATE NOCASE)',
        ]

        for index in indices:
            self.conn.execute(index)

        # Vista para búsquedas fáciles con categorías
        self.conn.execute('DROP VIEW IF EXISTS dotfiles_with_categories')
        self.conn.execute('''
            CREATE VIEW dotfiles_with_categories AS
            SELECT
                d.*,
                COALESCE(GROUP_CONCAT(c.name, ','), '') as categories
            FROM dotfiles d
            LEFT JOIN file_categories fc ON d.id = fc.file_id
            LEFT JOIN categories c ON fc.category_id = c.id
            GROUP BY d.id, d.path, d.filename, d.directory, d.extension,
                     d.size_bytes, d.hash, d.mime_type, d.is_config,
                     d.is_executable, d.source_root, d.relative_path,
                     d.created_at, d.updated_at, d.last_modified, d.last_indexed
        ''')

        # Insertar categorías básicas
        self.insert_default_categories()

        self.conn.commit()

    def insert_default_categories(self):
        """Inserta categorías por defecto"""
        default_categories = [
            ('Shell', 'Archivos de configuración de shell', r'\.(bashrc|zshrc|fishrc|profile)$|^\.profile$'),
            ('Editor', 'Configuración de editores', r'\.(vimrc|nvimrc|emacsrc)$|\.vim/|\.nvim/'),
            ('Git', 'Configuración de Git', r'\.git(config|ignore|attributes)|\.git/'),
            ('Desktop', 'Archivos .desktop y temas', r'\.desktop$|/themes/|/icons/'),
            ('Package Manager', 'Configuración de gestores de paquetes', r'requirements\.txt|package\.json|Pipfile|Gemfile'),
            ('System Service', 'Servicios del sistema', r'\.(service|timer|mount)$'),
            ('Build System', 'Sistemas de construcción', r'(Makefile|CMakeLists\.txt|configure)$'),
            ('SSH', 'Configuración SSH', r'\.ssh/|ssh_config'),
            ('Fonts', 'Archivos de fuentes', r'\.(ttf|otf|woff|woff2)$'),
            ('Container', 'Containerización', r'(Dockerfile|docker-compose\.yml|Vagrantfile)$'),
        ]

        for name, description, pattern in default_categories:
            self.conn.execute(
                'INSERT OR IGNORE INTO categories (name, description, pattern) VALUES (?, ?, ?)',
                (name, description, pattern)
            )

    def should_exclude_path(self, file_path: Path) -> bool:
        """Verifica si una ruta debe ser excluida"""
        # Verificar rutas excluidas
        for exclude_path in self.exclude_paths:
            try:
                file_path.relative_to(exclude_path)
                return True
            except ValueError:
                continue

        # Verificar patrones excluidos
        filename_lower = file_path.name.lower()
        for pattern in self.exclude_patterns:
            if pattern.startswith('*') and pattern.endswith('*'):
                # Patrón *texto*
                if pattern[1:-1] in filename_lower:
                    return True
            elif pattern.startswith('*'):
                # Patrón *.ext
                if filename_lower.endswith(pattern[1:]):
                    return True
            elif pattern.endswith('*'):
                # Patrón texto*
                if filename_lower.startswith(pattern[:-1]):
                    return True
            else:
                # Coincidencia exacta
                if filename_lower == pattern:
                    return True

        return False

    def is_config_file(self, file_path: Path) -> bool:
        """Determina si un archivo es de configuración"""
        filename = file_path.name
        extension = file_path.suffix.lower()

        # Verificar extensiones de configuración
        if extension in self.config_extensions:
            return True

        # Verificar nombres de archivo sin extensión
        if filename in self.config_filenames:
            return True

        # Verificar archivos de configuración comunes por patrón
        filename_lower = filename.lower()
        config_patterns = [
            'config', 'conf', 'rc', 'profile', 'ignore', 'env',
            'settings', 'preferences', 'options', 'rules'
        ]

        for pattern in config_patterns:
            if pattern in filename_lower:
                return True

        # Archivos dot (que empiecen con .)
        if filename.startswith('.') and len(filename) > 1:
            return True

        return False

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

    def get_mime_type(self, file_path: Path) -> str:
        """Obtiene el tipo MIME de un archivo"""
        try:
            mime_type, _ = mimetypes.guess_type(str(file_path))
            return mime_type or 'application/octet-stream'
        except Exception:
            return 'application/octet-stream'

    def is_file_changed(self, file_path: Path) -> bool:
        """Verifica si un archivo ha cambiado desde la última indexación"""
        cursor = self.conn.execute(
            'SELECT last_modified, hash FROM dotfiles WHERE path = ?',
            (str(file_path),)
        )
        result = cursor.fetchone()

        if not result:
            return True  # Archivo nuevo

        db_modified, db_hash = result
        try:
            file_modified = datetime.fromtimestamp(file_path.stat().st_mtime)

            # Comparar por fecha de modificación primero (más rápido)
            if db_modified != file_modified.isoformat():
                return True

            # Si las fechas coinciden, comparar hash para estar seguros
            current_hash = self.get_file_hash(file_path)
            return current_hash != db_hash
        except (OSError, IOError):
            return True  # Error al acceder al archivo, marcarlo como cambiado

    def find_source_root(self, file_path: Path) -> Path:
        """Encuentra la ruta raíz de búsqueda para un archivo"""
        for search_path in self.search_paths:
            try:
                file_path.relative_to(search_path)
                return search_path
            except ValueError:
                continue
        # Si no se encuentra, usar el directorio padre
        return file_path.parent

    def index_file(self, file_path: Path, force_update: bool = False) -> bool:
        """Indexa un archivo individual"""
        try:
            # Verificar si debe ser excluido
            if self.should_exclude_path(file_path):
                return False

            # Verificar tamaño de archivo
            stat = file_path.stat()
            if stat.st_size > self.max_file_size:
                return False

            # Verificar si el archivo ha cambiado
            if not force_update and not self.is_file_changed(file_path):
                return False  # No necesita actualización

            # Obtener información del archivo
            source_root = self.find_source_root(file_path)
            relative_path = file_path.relative_to(source_root)

            hash_value = self.get_file_hash(file_path)
            mime_type = self.get_mime_type(file_path)
            is_config = self.is_config_file(file_path)
            is_executable = file_path.is_file() and stat.st_mode & 0o111

            # Preparar datos
            data = {
                'path': str(file_path),
                'filename': file_path.name,
                'directory': str(file_path.parent),
                'extension': file_path.suffix.lower() if file_path.suffix else None,
                'size_bytes': stat.st_size,
                'hash': hash_value,
                'mime_type': mime_type,
                'is_config': is_config,
                'is_executable': is_executable,
                'source_root': str(source_root),
                'relative_path': str(relative_path),
                'last_modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'last_indexed': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }

            # Insertar o actualizar en la base de datos
            self.conn.execute('''
                INSERT OR REPLACE INTO dotfiles
                (path, filename, directory, extension, size_bytes, hash, mime_type,
                 is_config, is_executable, source_root, relative_path,
                 last_modified, last_indexed, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['path'], data['filename'], data['directory'], data['extension'],
                data['size_bytes'], data['hash'], data['mime_type'],
                data['is_config'], data['is_executable'], data['source_root'],
                data['relative_path'], data['last_modified'], data['last_indexed'],
                data['updated_at']
            ))

            return True

        except Exception as e:
            print(f"Error indexando {file_path}: {e}")
            return False

    def index_directory(self, directory: Path, recursive: bool = True,
                       progress_callback=None) -> Dict[str, int]:
        """Indexa todos los archivos en un directorio"""
        stats = {'indexed': 0, 'updated': 0, 'errors': 0, 'skipped': 0}

        if not directory.exists() or not directory.is_dir():
            print(f"Directorio no existe o no es accesible: {directory}")
            return stats

        print(f"Indexando: {directory}")

        # Obtener todos los archivos
        files_to_process = []
        try:
            if recursive:
                files_to_process = [f for f in directory.rglob('*') if f.is_file()]
            else:
                files_to_process = [f for f in directory.iterdir() if f.is_file()]
        except (PermissionError, OSError) as e:
            print(f"Error accediendo a {directory}: {e}")
            return stats

        total_files = len(files_to_process)
        print(f"Encontrados {total_files} archivos")

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
                elif (i + 1) % 100 == 0:  # Mostrar progreso cada 100 archivos
                    print(f"Procesados {i + 1}/{total_files} archivos... ({((i + 1) / total_files) * 100:.1f}%)")

                # Commit cada 200 archivos para mejorar rendimiento
                if (i + 1) % 200 == 0:
                    self.conn.commit()

            except Exception as e:
                stats['errors'] += 1
                print(f"Error procesando {file_path}: {e}")

        # Commit final para este directorio
        self.conn.commit()
        print(f"Completado {directory}: {stats['updated']} actualizados, {stats['skipped']} sin cambios, {stats['errors']} errores")

        return stats

    def cleanup_database(self):
        """Limpia archivos que ya no existen en el sistema"""
        print("Limpiando base de datos...")

        cursor = self.conn.execute('SELECT id, path FROM dotfiles')
        files_to_remove = []

        for file_id, path in cursor.fetchall():
            if not Path(path).exists():
                files_to_remove.append(file_id)

        if files_to_remove:
            placeholders = ','.join('?' * len(files_to_remove))
            self.conn.execute(
                f'DELETE FROM dotfiles WHERE id IN ({placeholders})',
                files_to_remove
            )
            print(f"Eliminados {len(files_to_remove)} archivos obsoletos")

        self.conn.commit()

    def get_stats(self) -> Dict[str, int]:
        """Obtiene estadísticas de la base de datos"""
        stats = {}

        cursor = self.conn.execute('SELECT COUNT(*) FROM dotfiles')
        stats['total_files'] = cursor.fetchone()[0]

        cursor = self.conn.execute('SELECT COUNT(*) FROM dotfiles WHERE is_config = 1')
        stats['config_files'] = cursor.fetchone()[0]

        cursor = self.conn.execute('SELECT COUNT(*) FROM dotfiles WHERE is_executable = 1')
        stats['executable_files'] = cursor.fetchone()[0]

        cursor = self.conn.execute('SELECT COUNT(DISTINCT source_root) FROM dotfiles')
        stats['source_roots'] = cursor.fetchone()[0]

        cursor = self.conn.execute('SELECT COUNT(DISTINCT directory) FROM dotfiles')
        stats['directories'] = cursor.fetchone()[0]

        cursor = self.conn.execute('SELECT COUNT(DISTINCT extension) FROM dotfiles WHERE extension IS NOT NULL')
        stats['extensions'] = cursor.fetchone()[0]

        # Estadísticas de tamaño
        cursor = self.conn.execute('SELECT SUM(size_bytes), AVG(size_bytes) FROM dotfiles')
        total_size, avg_size = cursor.fetchone()
        stats['total_size_mb'] = (total_size or 0) / (1024 * 1024)
        stats['avg_size_kb'] = (avg_size or 0) / 1024

        return stats

    def search_files(self, query: str, limit: int = 100) -> List[Dict]:
        """Busca archivos por nombre o ruta"""
        query_lower = f"%{query.lower()}%"

        cursor = self.conn.execute('''
            SELECT * FROM dotfiles_with_categories
            WHERE
                LOWER(filename) LIKE ? OR
                LOWER(relative_path) LIKE ? OR
                LOWER(path) LIKE ?
            ORDER BY
                CASE
                    WHEN LOWER(filename) = LOWER(?) THEN 1
                    WHEN LOWER(filename) LIKE ? THEN 2
                    WHEN LOWER(relative_path) LIKE ? THEN 3
                    ELSE 4
                END,
                filename
            LIMIT ?
        ''', (query_lower, query_lower, query_lower,
              query.lower(), f"{query.lower()}%", f"%{query.lower()}%", limit))

        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def run_full_index(self, force: bool = False):
        """Ejecuta una indexación completa"""
        print("=== Iniciando indexación de dotfiles ===")
        print(f"Rutas a indexar: {len(self.search_paths)}")
        for path in self.search_paths:
            print(f"  - {path}")

        print(f"Rutas excluidas: {len(self.exclude_paths)}")
        for path in list(self.exclude_paths)[:5]:  # Mostrar solo las primeras 5
            print(f"  - {path}")
        if len(self.exclude_paths) > 5:
            print(f"  ... y {len(self.exclude_paths) - 5} más")

        total_stats = {'indexed': 0, 'updated': 0, 'errors': 0, 'skipped': 0}

        # Indexar cada directorio
        for directory in self.search_paths:
            if directory.exists():
                stats = self.index_directory(directory, recursive=True)
                for key in total_stats:
                    total_stats[key] += stats[key]
            else:
                print(f"Directorio no encontrado: {directory}")

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
        print(f"Total de archivos: {db_stats['total_files']}")
        print(f"Archivos de configuración: {db_stats['config_files']}")
        print(f"Archivos ejecutables: {db_stats['executable_files']}")
        print(f"Directorios únicos: {db_stats['directories']}")
        print(f"Extensiones únicas: {db_stats['extensions']}")
        print(f"Tamaño total: {db_stats['total_size_mb']:.1f} MB")
        print(f"Tamaño promedio: {db_stats['avg_size_kb']:.1f} KB")

    def close(self):
        """Cierra la conexión a la base de datos"""
        if hasattr(self, 'conn'):
            self.conn.close()


def main():
    parser = argparse.ArgumentParser(description='Indexador de dotfiles para búsquedas rápidas')
    parser.add_argument('--force', '-f', action='store_true',
                       help='Forzar re-indexación completa')
    parser.add_argument('--db', type=str,
                       help='Ruta personalizada para la base de datos')
    parser.add_argument('--stats', '-s', action='store_true',
                       help='Mostrar solo estadísticas')
    parser.add_argument('--search', type=str,
                       help='Buscar archivos por nombre o ruta')

    args = parser.parse_args()

    indexer = DotfilesIndexer(args.db)

    try:
        if args.stats:
            stats = indexer.get_stats()
            print("=== Estadísticas de la base de datos ===")
            for key, value in stats.items():
                if key.endswith('_mb'):
                    print(f"{key.replace('_', ' ').title()}: {value:.1f} MB")
                elif key.endswith('_kb'):
                    print(f"{key.replace('_', ' ').title()}: {value:.1f} KB")
                else:
                    print(f"{key.replace('_', ' ').title()}: {value}")
        elif args.search:
            results = indexer.search_files(args.search)
            print(f"=== Resultados de búsqueda para: '{args.search}' ===")
            if results:
                for result in results:
                    config_marker = "[CONFIG]" if result['is_config'] else ""
                    exec_marker = "[EXEC]" if result['is_executable'] else ""
                    size_kb = result['size_bytes'] / 1024
                    print(f"{result['filename']} {config_marker}{exec_marker}")
                    print(f"  Ruta: {result['relative_path']}")
                    print(f"  Fuente: {result['source_root']}")
                    print(f"  Tamaño: {size_kb:.1f} KB")
                    if result['categories']:
                        print(f"  Categorías: {result['categories']}")
                    print()
            else:
                print("No se encontraron resultados.")
        else:
            indexer.run_full_index(args.force)
    finally:
        indexer.close()


if __name__ == '__main__':
    main()
