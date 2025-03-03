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

def sync_files(source_dir, dest_dir, exclude_dirs):
    # Paso 1: Obtener lista de archivos en origen (que deberían existir en destino)
    source_files = []
    for root, dirs, files in os.walk(source_dir):
        # Excluir directorios
        dirs[:] = [d for d in dirs if os.path.join(root, d) not in exclude_dirs]
        
        for file in files:
            src_path = os.path.join(root, file)
            if any(src_path.startswith(ex) for ex in exclude_dirs):
                continue
                
            rel_path = os.path.relpath(src_path, source_dir)
            source_files.append(rel_path)
    
    # Paso 2: Obtener lista de archivos en destino
    dest_files = []
    for root, dirs, files in os.walk(dest_dir):
        for file in files:
            dest_path = os.path.join(root, file)
            rel_path = os.path.relpath(dest_path, dest_dir)
            # Quitar la extensión .md para comparación
            if rel_path.endswith(".md"):
                rel_path_original = rel_path[:-3]
                dest_files.append((rel_path_original, rel_path))
    
    # Paso 3: Sincronizar - copiar/actualizar archivos
    for rel_path in source_files:
        src_path = os.path.join(source_dir, rel_path)
        dest_path = os.path.join(dest_dir, rel_path) + ".md"
        
        # Crear carpetas en destino si no existen
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        
        # Leer el contenido original
        with open(src_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        
        # Obtener la extensión del archivo
        ext = rel_path.split(".")[-1] if "." in rel_path else ""
        language = EXT_TO_LANG.get(ext, "")
        
        # Verificar si el archivo de destino ya existe
        new_content = f"```{language}\n" + content + "\n```\n"
        need_update = True
        
        if os.path.exists(dest_path):
            try:
                with open(dest_path, "r", encoding="utf-8") as f:
                    existing_content = f.read()
                if existing_content == new_content:
                    need_update = False
            except:
                pass  # Si hay error al leer, actualizamos de todas formas
        
        # Guardar el nuevo contenido solo si es necesario
        if need_update:
            with open(dest_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Actualizado: {dest_path}")
        else:
            print(f"Sin cambios: {dest_path}")
    
    # Paso 4: Eliminar archivos que ya no existen en el origen
    for orig_rel_path, full_rel_path in dest_files:
        # Si el archivo original no está en la lista de archivos fuente
        if orig_rel_path not in source_files:
            file_to_delete = os.path.join(dest_dir, full_rel_path)
            if os.path.exists(file_to_delete):
                os.remove(file_to_delete)
                print(f"Eliminado: {file_to_delete}")
    
    # Paso 5: Eliminar directorios vacíos en destino
    for root, dirs, files in os.walk(dest_dir, topdown=False):
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            if not os.listdir(dir_path):  # Si el directorio está vacío
                os.rmdir(dir_path)
                print(f"Eliminado directorio vacío: {dir_path}")

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
        "/home/huan/Scripts/menus/musica/__pycache__/",
        "/home/huan/Scripts/.stignore"
        ]
    sync_files(source, destination, exclude)