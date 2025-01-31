import os
import datetime
import locale
from pathlib import Path

# Configurar la localización en español
locale.setlocale(locale.LC_TIME, "es_ES.utf8")

# Ruta base del vault de Obsidian
VAULT_PATH = "/mnt/windows/FTP/wiki/Obsidian"
# Rutas de los directorios a monitorear
# DIRECTORIES = [
#     "/home/huan/.dotfiles",
#     "/home/huan/.config",
# ]
DIRECTORIES = []
# Incluir todas las carpetas y archivos ocultos de /home/huan
hidden_directories = [str(path) for path in Path("/home/huan").iterdir() if path.name.startswith(".")]
DIRECTORIES.extend(hidden_directories)

# Obtener la fecha actual
now = datetime.datetime.now()
year = now.strftime("%Y")
month = now.strftime("%m")
day = now.strftime("%Y-%m-%d-%A").lower()

# Ruta de la nota del día
journal_path = Path(VAULT_PATH) / "journals" / year / month / f"{day}.md"

# Obtener archivos modificados hoy
def get_modified_files(base_paths):
    today = now.date()
    modified_files = []
    
    for base_path in base_paths:
        for root, _, files in os.walk(base_path):
            for file in files:
                file_path = Path(root) / file
                
                try:
                    mtime = datetime.datetime.fromtimestamp(file_path.stat().st_mtime).date()
                    if mtime == today:
                        modified_files.append((file_path.relative_to(base_path), base_path))
                except Exception as e:
                    print(f"Error con {file_path}: {e}")
    return modified_files

# Obtener archivos creados hoy
def get_created_files(base_paths):
    today = now.date()
    created_files = []
    
    for base_path in base_paths:
        for root, _, files in os.walk(base_path):
            for file in files:
                file_path = Path(root) / file
                
                try:
                    ctime = datetime.datetime.fromtimestamp(file_path.stat().st_ctime).date()
                    if ctime == today:
                        created_files.append((file_path.relative_to(base_path), base_path))
                except Exception as e:
                    print(f"Error con {file_path}: {e}")
    return created_files

# Generar tabla Markdown
def generate_markdown_table(files):
    table = "| Archivo | Ubicación | Última Modificación |\n"
    table += "|---------|-----------|---------------------|\n"
    for file, base_path in files:
        file_path = Path(file)
        mod_time = datetime.datetime.fromtimestamp((Path(base_path) / file).stat().st_mtime)
        formatted_time = mod_time.strftime("%Y-%m-%d %H:%M:%S")
        table += f"| [{file_path.name}]({file_path}) | {base_path} | {formatted_time} |\n"
    return table

# Obtener archivos modificados y creados hoy
modified_files = get_modified_files(DIRECTORIES)
created_files = get_created_files(DIRECTORIES)

modified_table = generate_markdown_table(modified_files)
created_table = generate_markdown_table(created_files)

# Guardar tablas en archivos independientes
modified_file_path = Path(VAULT_PATH) / "modified_files_today.md"
created_file_path = Path(VAULT_PATH) / "created_files_today.md"

with open(modified_file_path, "w", encoding="utf-8") as f:
    f.write(modified_table)

with open(created_file_path, "w", encoding="utf-8") as f:
    f.write(created_table)

# Adjuntar las tablas a la nota del día
journal_path.parent.mkdir(parents=True, exist_ok=True)  # Crear directorios si no existen
with open(journal_path, "a", encoding="utf-8") as f:
    f.write(f"\n## Archivos modificados hoy ({now.strftime('%Y-%m-%d')})\n")
    f.write(modified_table)
    f.write(f"\n## Archivos creados hoy ({now.strftime('%Y-%m-%d')})\n")
    f.write(created_table)

# Eliminar los archivos temporales
modified_file_path.unlink(missing_ok=True)
created_file_path.unlink(missing_ok=True)

print(f"Tabla de archivos modificados guardada en {modified_file_path}")
print(f"Tabla de archivos creados guardada en {created_file_path}")
print(f"Tablas adjuntadas a {journal_path}")