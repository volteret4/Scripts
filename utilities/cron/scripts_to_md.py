import os
import shutil




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


def sync_files(source_dir, dest_dir, exclude_dirs, exclude_extensions=None):
    # Si exclude_extensions es None, inicializamos como lista vacía
    if exclude_extensions is None:
        exclude_extensions = []
    
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

        # Verificar si necesitamos actualizar basado en fecha de modificación
        need_update = True
        if os.path.exists(dest_path):
            src_mtime = os.path.getmtime(src_path)
            dest_mtime = os.path.getmtime(dest_path)
            
            # Si el archivo destino es más reciente, verificamos contenido solo si es necesario
            if dest_mtime >= src_mtime:
                try:
                    # Leer el contenido original
                    with open(src_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    
                    new_content = f"```{language}\n" + content + "\n```\n"
                    
                    with open(dest_path, "r", encoding="utf-8") as f:
                        existing_content = f.read()
                    
                    if existing_content == new_content:
                        need_update = False
                except Exception as e:
                    print(f"Error al comparar archivos: {e}")
            
        # Si necesitamos actualizar, leer y escribir
        if need_update:
            try:
                # Si no se leyó antes, leer ahora
                if 'content' not in locals():
                    with open(src_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                
                new_content = f"```{language}\n" + content + "\n```\n"
                
                with open(dest_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print(f"Actualizado: {dest_path}")
            except Exception as e:
                print(f"Error al actualizar {dest_path}: {e}")
        else:
            print(f"Sin cambios: {dest_path}")

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
    source = "/home/huan/Scripts"
    destination = "/mnt/windows/FTP/wiki/Obsidian/Spaces/Scripts"
    exclude = [
        "/home/huan/Scripts/.git",
        "/home/huan/Scripts/.content",
        "/home/huan/Scripts/.venv",
        "/home/huan/Scripts/python_venv",
        "/home/huan/Scripts/.stfolder",
        "/home/huan/Scripts/menus/mmusica/__pycache__/",
        "/home/huan/Scripts/menus/mmusica/modules/__pycache__",
        "/home/huan/Scripts/menus/mmusica/.content",
        "/mnt/windows/FTP/wiki/Obsidian/Spaces/Scripts/utilities/tiddlywiki/wiki_obsidian.sqlite",
        "/mnt/windows/FTP/wiki/Obsidian/Spaces/Scripts/utilities/tiddlywiki/wiki_obsidian_plus.sqlite",
        "/home/huan/Scripts/.stignore",
    ]
    exclude_extensions = ["tmp", "bak", "log", "swp", "pyc", "db", "sqlite"]

    sync_files(source, destination, exclude, exclude_extensions)
