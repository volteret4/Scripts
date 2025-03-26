import os
import re
import json
import sqlite3
import hashlib
from datetime import datetime
import argparse



# Al principio del script, después de los imports
def adapt_datetime(dt):
    return dt.isoformat()

def convert_datetime(s):
    return datetime.fromisoformat(s)

# Registrar los adaptadores
sqlite3.register_adapter(datetime, adapt_datetime)
sqlite3.register_converter("timestamp", convert_datetime)


def extract_tags_from_content(content):
    """Extrae tags del contenido del archivo Markdown"""
    # Busca tags en el formato YAML frontmatter
    yaml_pattern = re.compile(r'---\s*\n.*?tags:\s*(.*?)(?:\n|$).*?---', re.DOTALL)
    tag_pattern = re.compile(r'---\s*\n.*?tag:\s*(.*?)(?:\n|$).*?---', re.DOTALL)
    
    yaml_match = yaml_pattern.search(content)
    tag_match = tag_pattern.search(content)
    
    tags = []
    
    if yaml_match:
        # Extrae tags del formato de lista YAML
        yaml_tags = yaml_match.group(1).strip()
        if yaml_tags:
            # Maneja diferentes formatos de tags en YAML
            if ',' in yaml_tags:
                tags.extend([tag.strip() for tag in yaml_tags.split(',')])
            elif '\n' in yaml_tags:
                # Maneja formato de lista con guiones
                for line in yaml_tags.split('\n'):
                    line = line.strip()
                    if line.startswith('-'):
                        tags.append(line[1:].strip())
                    elif line:
                        tags.append(line)
            else:
                tags.append(yaml_tags)
    
    if tag_match:
        # Extrae el tag individual
        tag = tag_match.group(1).strip()
        if tag:
            tags.append(tag)
    
    return list(set(tags))  # Elimina duplicados

def get_file_hash(file_path):
    """Calcula el hash MD5 del contenido del archivo"""
    with open(file_path, 'rb') as f:
        file_hash = hashlib.md5(f.read()).hexdigest()
    return file_hash

def extract_source_from_content(content):
    """Extrae la URL source del contenido si existe"""
    url_pattern = re.compile(r'(https?://[^\s]+)', re.IGNORECASE)
    matches = url_pattern.findall(content)
    if matches:
        return matches[0]  # Devuelve la primera URL encontrada
    return None

def create_database():
    """Crea la base de datos SQLite con los índices necesarios"""
    conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
    cursor = conn.cursor()
    
    # Crear tabla para los snippets
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
    
    # Crear tabla para los tags
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE
    )
    ''')
    
    # Crear tabla para la relación muchos a muchos entre snippets y tags
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS snippet_tags (
        snippet_id INTEGER,
        tag_id INTEGER,
        PRIMARY KEY (snippet_id, tag_id),
        FOREIGN KEY (snippet_id) REFERENCES snippets(id) ON DELETE CASCADE,
        FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
    )
    ''')
    
    # Crear índices para búsqueda rápida
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_snippets_path ON snippets(path)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_snippets_filename ON snippets(filename)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_snippets_source ON snippets(source)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_snippets_directory ON snippets(directory)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_snippets_last_modified ON snippets(last_modified)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_snippet_tags ON snippet_tags(snippet_id, tag_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_snippet_tags_tag_id ON snippet_tags(tag_id)')
    
    # Crear tabla para almacenar metadatos de indexación
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS indexing_metadata (
        last_indexed TIMESTAMP,
        total_files INTEGER
    )
    ''')
    
    # Crear tabla virtual para búsqueda de texto completo
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
    conn.close()

def update_database(root_dir, force_update=False, excluded_paths=None, db_path='wiki_obsidian.db'):
    """Actualiza la base de datos con los archivos Markdown en el directorio"""
    if excluded_paths is None:
        excluded_paths = []
    
    # Verificar si la base de datos existe y crearla si no
    if not os.path.exists(db_path):
        create_database()
    
    # Convertir rutas excluidas a absolutas si son relativas
    abs_excluded_paths = []
    for path in excluded_paths:
        if os.path.isabs(path):
            abs_excluded_paths.append(path)
        else:
            abs_excluded_paths.append(os.path.join(root_dir, path))
    
    conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
    cursor = conn.cursor()
    
    # Verificar si las tablas existen
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='snippets'")
    if not cursor.fetchone():
        conn.close()
        create_database()
        conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        cursor = conn.cursor()
    
    # Contador de archivos procesados
    total_files = 0
    new_files = 0
    updated_files = 0
    unchanged_files = 0
    skipped_files = 0
    
    # Obtener todos los archivos markdown
    for root, dirs, files in os.walk(root_dir):
        # Verificar si el directorio actual debe ser excluido
        if any(root.startswith(excluded) for excluded in abs_excluded_paths):
            # Eliminar todos los directorios para que no se exploren más
            dirs[:] = []
            continue
            
        for file in files:
            if file.endswith('.md'):
                file_path = os.path.join(root, file)
                
                # Verificar si el archivo está en una ruta excluida
                if any(file_path.startswith(excluded) for excluded in abs_excluded_paths):
                    skipped_files += 1
                    continue
                    
                # Obtener el directorio relativo a la raíz para usar como categoría
                rel_path = os.path.relpath(root, root_dir)
                file_directory = rel_path if rel_path != '.' else ''
                
                # Leer el contenido del archivo
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except Exception as e:
                    print(f"Error leyendo {file_path}: {e}")
                    continue
                
                # Obtener tags del contenido
                content_tags = extract_tags_from_content(content)
                
                # Añadir el nombre de la carpeta como tag
                if file_directory:
                    content_tags.append(os.path.basename(file_directory))
                
                # Extraer posible URL source del contenido
                source = extract_source_from_content(content)
                
                # Última modificación y hash del archivo
                last_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
                file_hash = get_file_hash(file_path)
                
                # Verificar si el archivo ya existe en la base de datos
                cursor.execute('SELECT id, file_hash FROM snippets WHERE path = ?', (file_path,))
                existing_file = cursor.fetchone()
                
                if existing_file:
                    # Si existe, verificar si ha cambiado
                    if existing_file[1] != file_hash or force_update:
                        # Actualizar el archivo existente
                        cursor.execute('''
                        UPDATE snippets 
                        SET content = ?, source = ?, last_modified = ?, file_hash = ?, filename = ?, directory = ?
                        WHERE id = ?
                        ''', (content, source, last_modified, file_hash, file, file_directory, existing_file[0]))
                        
                        # Eliminar tags antiguos
                        cursor.execute('DELETE FROM snippet_tags WHERE snippet_id = ?', (existing_file[0],))
                        
                        # Insertar nuevos tags
                        for tag in content_tags:
                            # Insertar el tag si no existe
                            cursor.execute('INSERT OR IGNORE INTO tags (name) VALUES (?)', (tag,))
                            
                            # Obtener el ID del tag
                            cursor.execute('SELECT id FROM tags WHERE name = ?', (tag,))
                            tag_id = cursor.fetchone()[0]
                            
                            # Relacionar el tag con el snippet
                            cursor.execute('INSERT OR IGNORE INTO snippet_tags (snippet_id, tag_id) VALUES (?, ?)', 
                                        (existing_file[0], tag_id))
                        
                        # Actualizar índice de búsqueda
                        cursor.execute('INSERT OR REPLACE INTO snippet_fts(rowid, filename, content, path, directory, source) VALUES (?, ?, ?, ?, ?, ?)',
                                     (existing_file[0], file, content, file_path, file_directory, source))
                        
                        updated_files += 1
                    else:
                        unchanged_files += 1
                else:
                    # Insertar nuevo archivo
                    cursor.execute('''
                    INSERT INTO snippets (filename, path, directory, content, source, last_modified, file_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (file, file_path, file_directory, content, source, last_modified, file_hash))
                    
                    snippet_id = cursor.lastrowid
                    
                    # Insertar tags
                    for tag in content_tags:
                        # Insertar el tag si no existe
                        cursor.execute('INSERT OR IGNORE INTO tags (name) VALUES (?)', (tag,))
                        
                        # Obtener el ID del tag
                        cursor.execute('SELECT id FROM tags WHERE name = ?', (tag,))
                        tag_id = cursor.fetchone()[0]
                        
                        # Relacionar el tag con el snippet
                        cursor.execute('INSERT OR IGNORE INTO snippet_tags (snippet_id, tag_id) VALUES (?, ?)', 
                                    (snippet_id, tag_id))
                    
                    # Insertar en índice de búsqueda
                    cursor.execute('INSERT INTO snippet_fts(rowid, filename, content, path, directory, source) VALUES (?, ?, ?, ?, ?, ?)',
                                 (snippet_id, file, content, file_path, file_directory, source))
                    
                    new_files += 1
                
                total_files += 1
    
    # Actualizar metadatos de indexación
    cursor.execute('DELETE FROM indexing_metadata')
    cursor.execute('INSERT INTO indexing_metadata (last_indexed, total_files) VALUES (?, ?)', 
                 (datetime.now(), total_files))
    
    conn.commit()
    conn.close()
    
    return {
        'total_files': total_files,
        'new_files': new_files,
        'updated_files': updated_files,
        'unchanged_files': unchanged_files,
        'skipped_files': skipped_files
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Actualiza la base de datos de snippets')
    parser.add_argument('--root', required=True, help='Directorio raíz para buscar archivos markdown')
    parser.add_argument('--force', action='store_true', help='Forzar actualización de todos los archivos')
    parser.add_argument('--excluded-paths', nargs='+', default=['.git', '.gitignore', '.stfolder'], 
                        help='Rutas a excluir de la indexación (relativas al directorio raíz o absolutas)')
    parser.add_argument('--db-path', default='wiki_obsidian.db',help='Ruta a la base de datos)')
    args = parser.parse_args()
    
    db_path = args.db_path

    # Asegurarnos de que la base de datos existe antes de cualquier operación
    create_database()
    
    # Actualizar base de datos
    stats = update_database(args.root, args.force, args.excluded_paths, args.db_path)
    
    print(f"Indexación completada:")
    print(f"Total de archivos procesados: {stats['total_files']}")
    print(f"Archivos nuevos: {stats['new_files']}")
    print(f"Archivos actualizados: {stats['updated_files']}")
    print(f"Archivos sin cambios: {stats['unchanged_files']}")
    print(f"Archivos omitidos (en rutas excluidas): {stats['skipped_files']}")