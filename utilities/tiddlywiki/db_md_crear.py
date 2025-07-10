#!/usr/bin/env python3
"""
Script unificado para sincronización de wiki Obsidian con base de datos SQLite.
Combina creación, actualización y optimización de la base de datos.
Diseñado para ejecutarse con cron para mantener la base de datos actualizada.
"""

import os
import re
import json
import sqlite3
import hashlib
import time
import sys
import argparse
from datetime import datetime
from pathlib import Path

# Configuración por defecto
DEFAULT_CONFIG = {
    'db_path': 'wiki_obsidian.db',
    'root_dirs': [
        "/mnt/windows/FTP/wiki/Obsidian/Spaces/Wiki",
        "/mnt/windows/FTP/wiki/Obsidian/Spaces/Blogs", 
        "/mnt/windows/FTP/wiki/Obsidian/Spaces/Proyectos Interesantes",
        "/mnt/windows/FTP/wiki/Obsidian/Recortes"
    ],
    'excluded_paths': ['.git', '.gitignore', '.stfolder', '.obsidian'],
    'log_file': 'wiki_sync.log',
    'optimize_frequency': 7,  # días entre optimizaciones
    'backup_retention': 5     # número de backups a mantener
}

class WikiSyncLogger:
    """Logger simple para el script"""
    def __init__(self, log_file=None, verbose=False):
        self.log_file = log_file
        self.verbose = verbose
        
    def log(self, message, level='INFO'):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_message = f"[{timestamp}] {level}: {message}"
        
        if self.verbose or level in ['ERROR', 'WARNING']:
            print(log_message)
            
        if self.log_file:
            try:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(log_message + '\n')
            except Exception as e:
                print(f"Error escribiendo al log: {e}")
                
    def debug(self, message):
        """Log de debug que solo se muestra en modo verbose"""
        if self.verbose:
            self.log(message, 'DEBUG')

# Adaptadores para datetime en SQLite
def adapt_datetime(dt):
    return dt.isoformat()

def convert_datetime(s):
    return datetime.fromisoformat(s)

sqlite3.register_adapter(datetime, adapt_datetime)
sqlite3.register_converter("timestamp", convert_datetime)

class WikiDatabase:
    """Clase para manejar operaciones de la base de datos"""
    
    def __init__(self, db_path, logger=None):
        self.db_path = db_path
        self.logger = logger or WikiSyncLogger()
        
    def create_database(self):
        """Crea la estructura completa de la base de datos"""
        conn = sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        cursor = conn.cursor()
        
        try:
            # Tabla principal de snippets
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS snippets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                path TEXT,
                directory TEXT,
                content TEXT,
                source TEXT,
                last_modified TIMESTAMP,
                file_hash TEXT,
                UNIQUE(path)
            )
            ''')
            
            # Tabla de tags
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE
            )
            ''')
            
            # Relación muchos a muchos
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS snippet_tags (
                snippet_id INTEGER,
                tag_id INTEGER,
                PRIMARY KEY (snippet_id, tag_id),
                FOREIGN KEY (snippet_id) REFERENCES snippets(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
            )
            ''')
            
            # Metadatos de sincronización
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_metadata (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # Índices básicos
            self._create_basic_indexes(cursor)
            
            # Tabla FTS
            cursor.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS snippet_fts USING fts5(
                filename, 
                content, 
                path,
                directory,
                source,
                content='snippets',
                content_rowid='id'
            )
            ''')
            
            conn.commit()
            self.logger.log("Base de datos creada/verificada correctamente")
            
        except sqlite3.Error as e:
            self.logger.log(f"Error creando base de datos: {e}", 'ERROR')
            raise
        finally:
            conn.close()
    
    def _create_basic_indexes(self, cursor):
        """Crea los índices básicos necesarios"""
        indexes = [
            'CREATE INDEX IF NOT EXISTS idx_snippets_path ON snippets(path)',
            'CREATE INDEX IF NOT EXISTS idx_snippets_filename ON snippets(filename)',
            'CREATE INDEX IF NOT EXISTS idx_snippets_directory ON snippets(directory)',
            'CREATE INDEX IF NOT EXISTS idx_snippets_last_modified ON snippets(last_modified)',
            'CREATE INDEX IF NOT EXISTS idx_snippets_hash ON snippets(file_hash)',
            'CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(name)',
            'CREATE INDEX IF NOT EXISTS idx_snippet_tags_snippet ON snippet_tags(snippet_id)',
            'CREATE INDEX IF NOT EXISTS idx_snippet_tags_tag ON snippet_tags(tag_id)'
        ]
        
        for index_sql in indexes:
            try:
                cursor.execute(index_sql)
            except sqlite3.Error as e:
                self.logger.log(f"Error creando índice: {e}", 'WARNING')
    
    def optimize_database(self):
        """Optimiza la base de datos para mejor rendimiento"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            self.logger.log("Iniciando optimización de base de datos")
            
            # Configuraciones de rendimiento
            cursor.execute("PRAGMA journal_mode = WAL")
            cursor.execute("PRAGMA synchronous = NORMAL")
            cursor.execute("PRAGMA cache_size = 10000")
            cursor.execute("PRAGMA temp_store = MEMORY")
            
            # Reconstruir FTS si es necesario
            cursor.execute("SELECT COUNT(*) FROM snippets")
            total_snippets = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM snippet_fts")
            fts_count = cursor.fetchone()[0]
            
            if fts_count != total_snippets:
                self.logger.log("Reconstruyendo índice FTS")
                cursor.execute("INSERT INTO snippet_fts(snippet_fts) VALUES('rebuild')")
            
            # VACUUM y ANALYZE
            conn.commit()
            conn.execute("VACUUM")
            conn.execute("ANALYZE")
            conn.execute("PRAGMA optimize")
            
            # Actualizar metadatos de optimización
            cursor.execute("""
                INSERT OR REPLACE INTO sync_metadata (key, value, updated_at) 
                VALUES ('last_optimization', ?, ?)
            """, (datetime.now().isoformat(), datetime.now()))
            
            conn.commit()
            self.logger.log("Optimización completada")
            
        except sqlite3.Error as e:
            self.logger.log(f"Error durante optimización: {e}", 'ERROR')
            raise
        finally:
            conn.close()
    
    def should_optimize(self, force=False):
        """Determina si es necesario optimizar la base de datos"""
        if force:
            return True
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT value FROM sync_metadata WHERE key = 'last_optimization'")
            result = cursor.fetchone()
            
            if not result:
                return True
                
            last_opt = datetime.fromisoformat(result[0])
            days_since = (datetime.now() - last_opt).days
            
            return days_since >= DEFAULT_CONFIG['optimize_frequency']
            
        except (sqlite3.Error, ValueError):
            return True
        finally:
            conn.close()

class WikiSync:
    """Clase principal para sincronización de wiki"""
    
    def __init__(self, config=None, logger=None):
        self.config = config or DEFAULT_CONFIG.copy()
        self.logger = logger or WikiSyncLogger(
            self.config.get('log_file'), 
            self.config.get('verbose', False)
        )
        self.db = WikiDatabase(self.config['db_path'], self.logger)
        self.stats = {
            'total_files': 0,
            'new_files': 0,
            'updated_files': 0,
            'unchanged_files': 0,
            'skipped_files': 0,
            'deleted_files': 0,
            'errors': 0
        }
    
    def extract_tags_from_content(self, content):
        """Extrae tags del contenido markdown"""
        tags = []
        
        try:
            # YAML frontmatter - patrón más específico
            frontmatter_pattern = re.compile(r'^---\s*\n(.*?)\n---', re.DOTALL | re.MULTILINE)
            frontmatter_match = frontmatter_pattern.search(content)
            
            if frontmatter_match:
                yaml_content = frontmatter_match.group(1)
                
                # Buscar tags en diferentes formatos
                # Formato: tags: [tag1, tag2, tag3]
                list_tags = re.search(r'tags:\s*\[(.*?)\]', yaml_content, re.IGNORECASE)
                if list_tags:
                    tag_string = list_tags.group(1)
                    extracted_tags = [tag.strip().strip('"\'') for tag in tag_string.split(',')]
                    tags.extend([tag for tag in extracted_tags if tag])
                
                # Formato: tags: tag1, tag2, tag3
                comma_tags = re.search(r'tags:\s*([^\n\[\]]+)', yaml_content, re.IGNORECASE)
                if comma_tags and not list_tags:  # Solo si no encontramos formato lista
                    tag_string = comma_tags.group(1).strip()
                    if ',' in tag_string:
                        extracted_tags = [tag.strip().strip('"\'') for tag in tag_string.split(',')]
                        tags.extend([tag for tag in extracted_tags if tag])
                    else:
                        clean_tag = tag_string.strip('"\'')
                        if clean_tag:
                            tags.append(clean_tag)
                
                # Formato multilínea:
                # tags:
                #   - tag1
                #   - tag2
                multiline_pattern = re.search(r'tags:\s*\n((?:\s*-\s*.+\n?)+)', yaml_content, re.IGNORECASE)
                if multiline_pattern:
                    multiline_content = multiline_pattern.group(1)
                    multiline_tags = re.findall(r'-\s*(.+)', multiline_content)
                    tags.extend([tag.strip().strip('"\'') for tag in multiline_tags if tag.strip()])
                
                # También buscar "tag:" (singular)
                single_tag = re.search(r'tag:\s*(.+)', yaml_content, re.IGNORECASE)
                if single_tag:
                    tag_value = single_tag.group(1).strip().strip('"\'')
                    if tag_value:
                        tags.append(tag_value)
            
            # Tags inline con # (excluyendo headers)
            # Buscar solo hashtags que no estén al inicio de línea (para evitar headers)
            inline_pattern = re.compile(r'(?<!^)(?<![\n\r])#([a-zA-Z0-9_/-]+)', re.MULTILINE)
            inline_tags = inline_pattern.findall(content)
            tags.extend(inline_tags)
            
        except Exception as e:
            self.logger.log(f"Error extrayendo tags: {e}", 'WARNING')
        
        # Eliminar duplicados, vacíos y normalizar
        unique_tags = []
        seen = set()
        for tag in tags:
            if tag and isinstance(tag, str):
                normalized_tag = tag.strip().lower()
                if normalized_tag and normalized_tag not in seen:
                    seen.add(normalized_tag)
                    unique_tags.append(tag.strip())
        
        return unique_tags
    
    def get_file_hash(self, file_path):
        """Calcula hash MD5 del archivo"""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            self.logger.log(f"Error calculando hash para {file_path}: {e}", 'ERROR')
            return None
    
    def extract_source_from_content(self, content):
        """Extrae URLs del contenido"""
        try:
            # Buscar URLs en diferentes contextos
            patterns = [
                r'source:\s*(https?://[^\s\)]+)',  # YAML frontmatter
                r'url:\s*(https?://[^\s\)]+)',     # YAML frontmatter
                r'\[.*?\]\((https?://[^\s\)]+)\)', # Enlaces markdown
                r'(https?://[^\s\)<>\[\]]+)'       # URLs sueltas
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    return matches[0]
                    
        except Exception as e:
            self.logger.log(f"Error extrayendo fuente: {e}", 'WARNING')
            
        return None
    
    def is_path_excluded(self, file_path, root_dir):
        """Verifica si una ruta debe ser excluida"""
        try:
            rel_path = os.path.relpath(file_path, root_dir)
            
            for excluded in self.config['excluded_paths']:
                if excluded in rel_path or rel_path.startswith(excluded):
                    return True
                    
            # Verificar si es un archivo temporal
            filename = os.path.basename(file_path)
            if filename.startswith('.') or filename.startswith('~'):
                return True
                
        except Exception as e:
            self.logger.log(f"Error verificando exclusión para {file_path}: {e}", 'WARNING')
            return True
            
        return False
    
    def sync_directory(self, root_dir, force_update=False):
        """Sincroniza un directorio específico"""
        if not os.path.exists(root_dir):
            self.logger.log(f"Directorio no encontrado: {root_dir}", 'WARNING')
            return
        
        self.logger.log(f"Sincronizando directorio: {root_dir}")
        
        conn = sqlite3.connect(self.db.db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        cursor = conn.cursor()
        
        try:
            # Normalizar la ruta del directorio para comparaciones consistentes
            normalized_root = os.path.normpath(root_dir)
            
            # Obtener archivos existentes en la base de datos para este directorio
            cursor.execute("SELECT path, file_hash FROM snippets WHERE path LIKE ? OR path LIKE ?", 
                          (f"{root_dir}%", f"{normalized_root}%"))
            existing_files = {row[0]: row[1] for row in cursor.fetchall()}
            
            self.logger.debug(f"Archivos existentes en BD para {root_dir}: {len(existing_files)}")
            
            processed_files = set()
            found_md_files = 0
            
            # Procesar archivos markdown
            for root, dirs, files in os.walk(root_dir):
                # Filtrar directorios excluidos
                dirs[:] = [d for d in dirs if not any(excl in d for excl in self.config['excluded_paths'])]
                
                for file in files:
                    if not file.endswith('.md'):
                        continue
                        
                    found_md_files += 1
                    file_path = os.path.normpath(os.path.join(root, file))
                    
                    if self.is_path_excluded(file_path, root_dir):
                        self.logger.debug(f"Archivo excluido: {file_path}")
                        self.stats['skipped_files'] += 1
                        continue
                    
                    processed_files.add(file_path)
                    
                    try:
                        self._process_file(cursor, file_path, root_dir, existing_files, force_update)
                    except Exception as e:
                        self.logger.log(f"Error procesando {file_path}: {e}", 'ERROR')
                        self.stats['errors'] += 1
                        # Continuar con el siguiente archivo
                        continue
            
            self.logger.debug(f"Archivos .md encontrados: {found_md_files}")
            self.logger.debug(f"Archivos procesados: {len(processed_files)}")
            
            # Detectar archivos eliminados - solo para este directorio
            deleted_files = []
            for existing_path in existing_files.keys():
                # Verificar si el archivo pertenece a este directorio
                if (existing_path.startswith(root_dir) or existing_path.startswith(normalized_root)):
                    if existing_path not in processed_files:
                        deleted_files.append(existing_path)
            
            for deleted_file in deleted_files:
                try:
                    self._remove_file_from_db(cursor, deleted_file)
                    self.stats['deleted_files'] += 1
                except Exception as e:
                    self.logger.log(f"Error eliminando {deleted_file}: {e}", 'ERROR')
            
            conn.commit()
            self.logger.log(f"Directorio {root_dir} sincronizado: {len(processed_files)} archivos procesados")
            
        except Exception as e:
            self.logger.log(f"Error sincronizando {root_dir}: {e}", 'ERROR')
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _process_file(self, cursor, file_path, root_dir, existing_files, force_update):
        """Procesa un archivo individual"""
        self.logger.debug(f"Procesando archivo: {file_path}")
        
        try:
            # Leer contenido
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        except Exception as e:
            self.logger.log(f"Error leyendo {file_path}: {e}", 'ERROR')
            raise
        
        # Calcular hash y metadatos
        file_hash = self.get_file_hash(file_path)
        if not file_hash:
            raise Exception("No se pudo calcular hash del archivo")
            
        last_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
        filename = os.path.basename(file_path)
        directory = os.path.relpath(os.path.dirname(file_path), root_dir)
        
        # Extraer información del contenido
        tags = self.extract_tags_from_content(content)
        
        # Añadir directorio como tag si no es el directorio raíz
        if directory and directory != '.':
            dir_parts = directory.split(os.sep)
            tags.extend(dir_parts)  # Agregar cada parte del path como tag
            
        source = self.extract_source_from_content(content)
        
        self.logger.debug(f"Archivo: {filename}, Tags: {tags}, Hash: {file_hash[:8]}...")
        
        # Verificar si necesita actualización
        if file_path in existing_files:
            if existing_files[file_path] == file_hash and not force_update:
                self.logger.debug(f"Archivo sin cambios: {filename}")
                self.stats['unchanged_files'] += 1
                return
            else:
                self.logger.debug(f"Actualizando archivo: {filename}")
                self._update_file_in_db(cursor, file_path, filename, directory, content, 
                                      source, last_modified, file_hash, tags)
                self.stats['updated_files'] += 1
        else:
            self.logger.debug(f"Insertando nuevo archivo: {filename}")
            self._insert_file_in_db(cursor, file_path, filename, directory, content,
                                  source, last_modified, file_hash, tags)
            self.stats['new_files'] += 1
        
        self.stats['total_files'] += 1
    
    def _update_file_in_db(self, cursor, file_path, filename, directory, content, 
                          source, last_modified, file_hash, tags):
        """Actualiza un archivo existente en la base de datos"""
        try:
            # Obtener ID del snippet
            cursor.execute('SELECT id FROM snippets WHERE path = ?', (file_path,))
            result = cursor.fetchone()
            
            if not result:
                self.logger.log(f"No se encontró snippet para actualizar: {file_path}", 'WARNING')
                # Insertar como nuevo archivo
                self._insert_file_in_db(cursor, file_path, filename, directory, content,
                                      source, last_modified, file_hash, tags)
                return
                
            snippet_id = result[0]
            
            # Actualizar snippet
            cursor.execute('''
                UPDATE snippets 
                SET filename = ?, directory = ?, content = ?, source = ?, 
                    last_modified = ?, file_hash = ?
                WHERE id = ?
            ''', (filename, directory, content, source, last_modified, file_hash, snippet_id))
            
            # Actualizar tags
            self._update_snippet_tags(cursor, snippet_id, tags)
            
            # Actualizar FTS
            cursor.execute('''
                INSERT OR REPLACE INTO snippet_fts(rowid, filename, content, path, directory, source) 
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (snippet_id, filename, content, file_path, directory, source or ''))
            
        except sqlite3.Error as e:
            self.logger.log(f"Error actualizando archivo {file_path}: {e}", 'ERROR')
            raise
    
    def _insert_file_in_db(self, cursor, file_path, filename, directory, content,
                          source, last_modified, file_hash, tags):
        """Inserta un nuevo archivo en la base de datos"""
        try:
            # Insertar snippet
            cursor.execute('''
                INSERT INTO snippets (filename, path, directory, content, source, last_modified, file_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (filename, file_path, directory, content, source, last_modified, file_hash))
            
            snippet_id = cursor.lastrowid
            
            # Insertar tags
            self._update_snippet_tags(cursor, snippet_id, tags)
            
            # Insertar en FTS
            cursor.execute('''
                INSERT INTO snippet_fts(rowid, filename, content, path, directory, source) 
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (snippet_id, filename, content, file_path, directory, source or ''))
            
        except sqlite3.Error as e:
            self.logger.log(f"Error insertando archivo {file_path}: {e}", 'ERROR')
            raise
    
    def _update_snippet_tags(self, cursor, snippet_id, tags):
        """Actualiza los tags de un snippet"""
        try:
            # Eliminar tags existentes
            cursor.execute('DELETE FROM snippet_tags WHERE snippet_id = ?', (snippet_id,))
            
            # Procesar tags únicos
            unique_tags = list(dict.fromkeys(tag.strip() for tag in tags if tag and tag.strip()))
            
            # Insertar nuevos tags
            for tag in unique_tags:
                try:
                    # Insertar tag si no existe
                    cursor.execute('INSERT OR IGNORE INTO tags (name) VALUES (?)', (tag,))
                    
                    # Obtener ID del tag
                    cursor.execute('SELECT id FROM tags WHERE name = ?', (tag,))
                    result = cursor.fetchone()
                    
                    if result:
                        tag_id = result[0]
                        # Insertar relación snippet-tag
                        cursor.execute('INSERT OR IGNORE INTO snippet_tags (snippet_id, tag_id) VALUES (?, ?)', 
                                      (snippet_id, tag_id))
                    else:
                        self.logger.log(f"No se pudo obtener ID para el tag: {tag}", 'WARNING')
                        
                except sqlite3.Error as e:
                    self.logger.log(f"Error procesando tag '{tag}' para snippet {snippet_id}: {e}", 'WARNING')
                    
        except sqlite3.Error as e:
            self.logger.log(f"Error actualizando tags para snippet {snippet_id}: {e}", 'ERROR')
            raise
    
    def _remove_file_from_db(self, cursor, file_path):
        """Elimina un archivo de la base de datos"""
        try:
            cursor.execute('SELECT id FROM snippets WHERE path = ?', (file_path,))
            result = cursor.fetchone()
            
            if result:
                snippet_id = result[0]
                # Las relaciones se eliminan automáticamente por CASCADE
                cursor.execute('DELETE FROM snippets WHERE id = ?', (snippet_id,))
                cursor.execute('DELETE FROM snippet_fts WHERE rowid = ?', (snippet_id,))
                self.logger.log(f"Archivo eliminado de la base de datos: {file_path}")
            else:
                self.logger.debug(f"Archivo no encontrado en BD para eliminar: {file_path}")
                
        except sqlite3.Error as e:
            self.logger.log(f"Error eliminando archivo {file_path}: {e}", 'ERROR')
            raise
    
    def run_sync(self, force_update=False, optimize=None):
        """Ejecuta la sincronización completa"""
        start_time = time.time()
        self.logger.log("Iniciando sincronización de wiki")
        
        try:
            # Crear/verificar base de datos
            self.db.create_database()
            
            # Sincronizar cada directorio
            for root_dir in self.config['root_dirs']:
                try:
                    self.sync_directory(root_dir, force_update)
                except Exception as e:
                    self.logger.log(f"Error sincronizando directorio {root_dir}: {e}", 'ERROR')
                    # Continuar con el siguiente directorio
                    continue
            
            # Actualizar metadatos de sincronización
            self._update_sync_metadata()
            
            # Optimizar si es necesario
            if optimize is None:
                optimize = self.db.should_optimize()
            
            if optimize:
                self.db.optimize_database()
            
            # Limpiar tags huérfanos
            self._cleanup_orphaned_tags()
            
            elapsed_time = time.time() - start_time
            self._log_summary(elapsed_time)
            
        except Exception as e:
            self.logger.log(f"Error durante sincronización: {e}", 'ERROR')
            raise
    
    def _update_sync_metadata(self):
        """Actualiza metadatos de sincronización"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        try:
            now = datetime.now()
            metadata_updates = [
                ('last_sync', now.isoformat()),
                ('total_snippets', str(self.stats['total_files'])),
                ('sync_stats', json.dumps(self.stats))
            ]
            
            for key, value in metadata_updates:
                cursor.execute('''
                    INSERT OR REPLACE INTO sync_metadata (key, value, updated_at) 
                    VALUES (?, ?, ?)
                ''', (key, value, now))
            
            conn.commit()
        except Exception as e:
            self.logger.log(f"Error actualizando metadatos: {e}", 'ERROR')
        finally:
            conn.close()
    
    def _cleanup_orphaned_tags(self):
        """Elimina tags que no están relacionados con ningún snippet"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                DELETE FROM tags 
                WHERE id NOT IN (SELECT DISTINCT tag_id FROM snippet_tags)
            ''')
            
            deleted_tags = cursor.rowcount
            if deleted_tags > 0:
                self.logger.log(f"Eliminados {deleted_tags} tags huérfanos")
            
            conn.commit()
        except Exception as e:
            self.logger.log(f"Error limpiando tags huérfanos: {e}", 'ERROR')
        finally:
            conn.close()
    
    def _log_summary(self, elapsed_time):
        """Registra el resumen de la sincronización"""
        summary = f"""
Sincronización completada en {elapsed_time:.2f} segundos:
- Archivos procesados: {self.stats['total_files']}
- Archivos nuevos: {self.stats['new_files']}
- Archivos actualizados: {self.stats['updated_files']}
- Archivos sin cambios: {self.stats['unchanged_files']}
- Archivos omitidos: {self.stats['skipped_files']}
- Archivos eliminados: {self.stats['deleted_files']}
- Errores: {self.stats['errors']}
        """.strip()
        
        self.logger.log(summary)

def load_config(config_path):
    """Carga configuración desde archivo JSON"""
    if not os.path.exists(config_path):
        return DEFAULT_CONFIG.copy()
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            user_config = json.load(f)
        
        config = DEFAULT_CONFIG.copy()
        config.update(user_config)
        return config
    except Exception as e:
        print(f"Error cargando configuración: {e}")
        return DEFAULT_CONFIG.copy()

def save_default_config(config_path):
    """Guarda configuración por defecto"""
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_CONFIG, f, indent=4, ensure_ascii=False)
        print(f"Configuración por defecto guardada en: {config_path}")
    except Exception as e:
        print(f"Error guardando configuración: {e}")

def main():
    parser = argparse.ArgumentParser(description='Sincronización unificada de wiki Obsidian')
    parser.add_argument('--config', '-c', default='wiki_sync_config.json',
                        help='Archivo de configuración JSON')
    parser.add_argument('--force', '-f', action='store_true',
                        help='Forzar actualización de todos los archivos')
    parser.add_argument('--optimize', action='store_true',
                        help='Forzar optimización de base de datos')
    parser.add_argument('--no-optimize', action='store_true',
                        help='Saltar optimización automática')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Mostrar información detallada')
    parser.add_argument('--create-config', action='store_true',
                        help='Crear archivo de configuración por defecto')
    parser.add_argument('--dry-run', action='store_true',
                        help='Simular ejecución sin hacer cambios')
    parser.add_argument('--debug', action='store_true',
                        help='Activar logs de debug detallados')
    
    args = parser.parse_args()
    
    if args.create_config:
        save_default_config(args.config)
        return
    
    # Cargar configuración
    config = load_config(args.config)
    config['verbose'] = args.verbose or args.debug
    
    if args.dry_run:
        print("Modo simulación activado - no se realizarán cambios")
        config['db_path'] = ':memory:'
    
    # Determinar si optimizar
    optimize = None
    if args.optimize:
        optimize = True
    elif args.no_optimize:
        optimize = False
    
    try:
        # Crear logger
        logger = WikiSyncLogger(
            config.get('log_file') if not args.dry_run else None,
            config.get('verbose', False)
        )
        
        # Ejecutar sincronización
        sync = WikiSync(config, logger)
        sync.run_sync(force_update=args.force, optimize=optimize)
        
    except KeyboardInterrupt:
        print("\nSincronización interrumpida por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"Error fatal: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()