import os
import shutil
import filecmp

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
    for root, dirs, files in os.walk(source_dir):
        # Excluir directorios
        dirs[:] = [d for d in dirs if os.path.join(root, d) not in exclude_dirs]
        
        for file in files:
            src_path = os.path.join(root, file)
            rel_path = os.path.relpath(src_path, source_dir)
            dest_path = os.path.join(dest_dir, rel_path) + ".md"  # Solo mantener los .md en destino
            
            # Excluir archivos específicos
            if any(src_path.startswith(ex) for ex in exclude_dirs):
                print(f"Excluido: {src_path}")
                continue
            
            # Crear carpetas en destino si no existen
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            
            # Leer el contenido original
            with open(src_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            
            # Obtener la extensión del archivo
            ext = file.split(".")[-1] if "." in file else ""
            language = EXT_TO_LANG.get(ext, "")
            
            # Modificar el contenido con bloques de código
            new_content = f"```{language}\n" + content + "\n```\n"
            
            # Guardar el nuevo contenido en el archivo renombrado
            with open(dest_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            
            print(f"Procesado: {dest_path}")

if __name__ == "__main__":
    # source = input("Introduce la ruta de la carpeta origen: ")
    # destination = input("Introduce la ruta de la carpeta destino: ")
    # exclude = input("Introduce las carpetas a excluir (separadas por comas): ").split(',')
    source = "/home/huan/Scripts"
    destination = "/mnt/windows/FTP/wiki/Obsidian/Spaces/Scripts"
    exclude = ["/home/huan/Scripts/.git", "/home/huan/Scripts/.content", "/home/huan/Scripts/.venv", "/home/huan/Scripts/python_venv", "/home/huan/Scripts/.stfolder", "/home/huan/Scripts/.stignore"]
    sync_files(source, destination, exclude)

