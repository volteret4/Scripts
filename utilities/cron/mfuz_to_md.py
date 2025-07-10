import os
import shutil
from datetime import datetime, timedelta
import re
from pathlib import Path


# Mapeo de extensiones a lenguajes de bloque de código
EXT_TO_LANG = {
    "sh": "bash",
    "py": "python",
    "yaml": "yaml",
    "yml": "yaml",
    "json": "json",
    "js": "javascript",
    "html": "html",
    "css": "css",
    "cpp": "cpp",
    "c": "c",
    "java": "java",
    "rs": "rust",
    "go": "go",
    "lua": "lua",
    "txt": "text",
    "md": "markdown",
    "log": "text",
    "ts": "typescript",
    "toml": "toml",
    "config": "ini",
}


def extract_todos(content, filename):
    """
    Extract TODO comments from file content.
    
    Args:
        content (str): File content
        filename (str): Name of the file
    
    Returns:
        list: List of extracted TODO lines
    """
    # Regular expressions to match TODO comments with or without #
    todo_patterns = [
        r'#\s*TODO:?\s*(.+)',  # Matches #TODO: or # TODO 
        r'\s*TODO:?\s*(.+)'    # Matches TODO: without #
    ]
    
    todos = []
    for pattern in todo_patterns:
        matches = re.findall(pattern, content, re.MULTILINE)
        for todo in matches:
            todos.append(todo.strip())
    
    return todos

def add_todos_to_task_file(todos, filename):
    """
    Add extracted TODOs to the task file.
    
    Args:
        todos (list): List of TODO lines
        filename (str): Source filename
    """
    task_file_path = "/mnt/windows/FTP/Obsidian/Important/Tareas.md"
    
    # Get current and future dates
    today = datetime.now().date()
    three_months_later = today + timedelta(days=90)
    
    # Prepare task filename tag (remove .md extension)
    filename_tag = os.path.splitext(filename)[0]
    
    # Prepare new TODO entries
    new_todos = []
    for todo in todos:
        todo_entry = f"-  [ ] TODO: #{filename_tag} {todo} 🛫 {today} 📅 {three_months_later}"
        new_todos.append(todo_entry)
    
    # Read existing content
    existing_content = []
    if os.path.exists(task_file_path):
        with open(task_file_path, 'r', encoding='utf-8') as f:
            existing_content = f.readlines()
    
    # Append new TODOs if they don't already exist
    updated_content = existing_content.copy()
    for todo_entry in new_todos:
        if todo_entry + '\n' not in existing_content:
            updated_content.append(todo_entry + '\n')
    
    # Write back to the task file
    with open(task_file_path, 'w', encoding='utf-8') as f:
        f.writelines(updated_content)


def read_file_content(file_path):
    """
    Safely read file content with proper encoding handling.
    
    Args:
        file_path (str): Path to the file to read
        
    Returns:
        str: File content or None if error
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:
        print(f"Error leyendo archivo {file_path}: {e}")
        return None


def files_are_identical(src_content, dest_path, language):
    """
    Check if source content matches destination file content.
    
    Args:
        src_content (str): Source file content
        dest_path (str): Destination file path
        language (str): Programming language for markdown formatting
        
    Returns:
        bool: True if files are identical
    """
    try:
        expected_content = f"```{language}\n{src_content}\n```\n"
        
        if not os.path.exists(dest_path):
            return False
            
        with open(dest_path, "r", encoding="utf-8") as f:
            existing_content = f.read()
            
        return existing_content == expected_content
    except Exception as e:
        print(f"Error comparando archivos: {e}")
        return False


def sync_files(source_dir, dest_dir, exclude_dirs, exclude_extensions=None):
    # Si exclude_extensions es None, inicializamos como lista vacía
    if exclude_extensions is None:
        exclude_extensions = ['sqlite', 'db', 'bak', 'tmp', 'log', 'swp', 'mb']
    
    # Normalizar las rutas de exclusión para comparaciones consistentes
    exclude_dirs = [os.path.normpath(path) for path in exclude_dirs]
    
    # Paso 1: Obtener lista de archivos en origen (que deberían existir en destino)
    source_files = []
    print("Escaneando directorio fuente...")
    for root, dirs, files in os.walk(source_dir):
        # Filtrar directorios a nivel de lista para evitar recorrer subdirectorios excluidos
        dirs[:] = [d for d in dirs if not any(os.path.normpath(os.path.join(root, d)).startswith(ex) for ex in exclude_dirs)]
        
        for file in files:
            src_path = os.path.join(root, file)
            
            # Excluir archivos por extensión - más eficiente
            file_ext = file.split('.')[-1] if '.' in file else ""
            if file_ext in exclude_extensions:
                continue
                
            rel_path = os.path.relpath(src_path, source_dir)
            source_files.append(rel_path)
    
    # Paso 2: Obtener lista de archivos en destino
    dest_files = []
    print("Escaneando directorio destino...")
    for root, dirs, files in os.walk(dest_dir):
        for file in files:
            if file.endswith(".md"):
                dest_path = os.path.join(root, file)
                rel_path = os.path.relpath(dest_path, dest_dir)
                # Quitar la extensión .md para comparación
                rel_path_original = rel_path[:-3]
                dest_files.append((rel_path_original, rel_path))
    
    # Crear un conjunto para búsqueda más rápida
    source_files_set = set(source_files)
    dest_files_dict = {orig: full for orig, full in dest_files}
    
    # Contador para mostrar progreso
    total_files = len(source_files)
    processed = 0
    
    # Paso 3: Sincronizar - copiar/actualizar archivos
    print(f"Sincronizando {total_files} archivos...")
    for rel_path in source_files:
        processed += 1
        if processed % 100 == 0:  # Mostrar progreso cada 100 archivos
            print(f"Progreso: {processed}/{total_files} archivos")
            
        src_path = os.path.join(source_dir, rel_path)
        dest_path = os.path.join(dest_dir, rel_path) + ".md"

        # Crear carpetas en destino si no existen
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        # Obtener la extensión del archivo
        ext = rel_path.split(".")[-1] if "." in rel_path else ""
        language = EXT_TO_LANG.get(ext, "")

        # Leer el contenido del archivo fuente
        content = read_file_content(src_path)
        if content is None:
            print(f"Error: No se pudo leer {src_path}")
            continue

        # Verificar si necesitamos actualizar
        need_update = True
        if os.path.exists(dest_path):
            src_mtime = os.path.getmtime(src_path)
            dest_mtime = os.path.getmtime(dest_path)
            
            # Si el archivo destino es más reciente o igual, verificar contenido
            if dest_mtime >= src_mtime:
                if files_are_identical(content, dest_path, language):
                    need_update = False
                    print(f"Sin cambios: {dest_path}")
        
        # Actualizar archivo si es necesario
        if need_update:
            try:
                new_content = f"```{language}\n{content}\n```\n"
                
                with open(dest_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print(f"Actualizado: {dest_path}")
                
                # Extraer TODOs después de actualizar
                if ext in ['py', 'js', 'sh', 'txt', 'md']:
                    todos = extract_todos(content, os.path.basename(rel_path))
                    if todos:
                        add_todos_to_task_file(todos, os.path.basename(rel_path))
                        print(f"TODOs extraídos de {rel_path}")
                        
            except Exception as e:
                print(f"Error al actualizar {dest_path}: {e}")

    # Paso 4: Eliminar archivos que ya no existen en el origen
    print("Eliminando archivos obsoletos...")
    files_to_delete = []
    for orig_rel_path in dest_files_dict:
        if orig_rel_path not in source_files_set:
            full_rel_path = dest_files_dict[orig_rel_path]
            file_to_delete = os.path.join(dest_dir, full_rel_path)
            files_to_delete.append(file_to_delete)
    
    # Eliminar en un solo paso para evitar recorrer el árbol múltiples veces
    for file_path in files_to_delete:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Eliminado: {file_path}")
        except Exception as e:
            print(f"Error al eliminar {file_path}: {e}")

    # Paso 5: Eliminar directorios vacíos en destino
    print("Limpiando directorios vacíos...")
    for root, dirs, files in os.walk(dest_dir, topdown=False):
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            try:
                if not os.listdir(dir_path):  # Si el directorio está vacío
                    os.rmdir(dir_path)
                    print(f"Eliminado directorio vacío: {dir_path}")
            except Exception as e:
                print(f"Error al eliminar directorio {dir_path}: {e}")


if __name__ == "__main__":
    # source = input("Introduce la ruta de la carpeta origen: ")
    # destination = input("Introduce la ruta de la carpeta destino: ")
    # exclude = input("Introduce las carpetas a excluir (separadas por comas): ").split(',')
    source = "/home/huan/gits/pollo/music-fuzzy"
    destination = "/mnt/windows/FTP/wiki/Obsidian/Spaces/Blogs/snipets y scripts/music-fuzzy/scripts"
    exclude = [
        "/home/huan/gits/pollo/music-fuzzy/.git",
        "/home/huan/gits/pollo/music-fuzzy/.content",
        "/home/huan/gits/pollo/music-fuzzy/.venv",
        "/home/huan/gits/pollo/music-fuzzy/.stfolder",
        "/home/huan/gits/pollo/music-fuzzy/__pycache__/",
        "/home/huan/gits/pollo/music-fuzzy/modules/__pycache__",
        "/home/huan/gits/pollo/music-fuzzy/ui",
        "**/__pycache__",
        "**/.qtcreator",
        "/home/huan/gits/pollo/music-fuzzy/db/sqlite",
        ".qtcreator",
        "/home/huan/gits/pollo/music-fuzzy/.qtcreator"

        
    ]
    exclude_extensions = ["ui","qrc", "csv", "tmp", "bak", "log", "swp", "pyc", "db", "sqlite", "json", "txt", "cache", "env"]

    sync_files(source, destination, exclude, exclude_extensions)

    config_example = Path("/home/huan/gits/pollo/music-fuzzy/config/config_database_creator_example.json")
    config_dest_md = Path("/mnt/windows/FTP/wiki/Obsidian/Spaces/Blogs/snipets y scripts/music-fuzzy/scripts/config/config_database_creator_example.json.md")

    # Copiar archivo
    shutil.copy(config_example, config_dest_md)

    # Leer, modificar y sobrescribir
    contenido = config_dest_md.read_text(encoding="utf-8")
    nuevo_contenido = "```json\n" + contenido + "\n```"
    config_dest_md.write_text(nuevo_contenido, encoding="utf-8")