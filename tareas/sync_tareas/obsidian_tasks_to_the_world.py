#!/usr/bin/env python3
"""
Script Name: procesar_tareas_background.py
Description: Procesa tareas en segundo plano, similar a crear_tarea_caldav.py pero sin interfaz gráfica
             y con sistema de checkpoint para recordar la última fecha procesada
Author: Adaptado del script crear_tarea_caldav.py
"""

import os
import sys
import subprocess
import json
import datetime
from pathlib import Path
import re
import logging
import time
import hashlib

# Configuración - mantiene las mismas rutas y valores que en el script original
HOME = os.environ.get('HOME')
DISCOS = "d1573ec1-e837-6918-1dfe-bc0b6c04681d"  # CHANGE!!!
TAREAS = "7c44de6e-69ac-8496-f46d-d6753c9eab1f"  # CHANGE!!!
MUSICA = "e2e4e951-3599-8f21-de6c-105ec980b1ec"  # CHANGE!!!

TODO_DIR = Path("/mnt/windows/FTP/Wiki/Obsidian/Important/todotxt/todo")  # CHANGE!!!
TODO_DIR_ROOT = Path("/mnt/windows/FTP/Wiki/Obsidian/Important/todotxt/")
TASKS_FILE = Path("/mnt/windows/FTP/wiki/Obsidian/Important/Tareas.md")  # NUEVA RUTA PARA TAREAS

# Archivo de checkpoint - guarda la última fecha procesada
CHECKPOINT_FILE = Path(f"{HOME}/Scripts/.content/logs/procesar_tareas_checkpoint.json")

# Configuración de logging
LOG_FILE = Path(f"{HOME}/Scripts/.content/logs/procesar_tareas.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Lista de archivos markdown con títulos - definir proyectos y sus archivos
PROYECTOS = [
    {
        "path": "/mnt/windows/FTP/wiki/Obsidian/Spaces/Blogs/snipets y scripts/music-fuzzy/Aplicación música pollo.md",
        "title": "Aplicacion_musica_pollo"
    },
    {
        "path": "/mnt/windows/FTP/wiki/Obsidian/Spaces/Blogs/snipets y scripts/music-fuzzy/creacion base de datos/Creación de la base de datos.md",
        "title": "Creacion_de_la_base_de_datos"
    },
    {
        "path": "/mnt/windows/FTP/wiki/Obsidian/Spaces/Blogs/Tumtumpa/Recopilando Música.md",
        "title": "Recopilando_Música"
    }
]

# Fuente de datos donde buscar nuevas tareas - adaptar según necesidades
SOURCES = [
    {
        "path": "/mnt/windows/FTP/Wiki/Obsidian/Important/Tareas.md",
        "default_project": "Aplicacion_musica_pollo"  # Proyecto por defecto si no se especifica
    }
]

def run_command(cmd, shell=False):
    """Ejecuta un comando y devuelve su salida."""
    if shell:
        result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    else:
        result = subprocess.run(cmd, text=True, capture_output=True)
    
    return result.stdout.strip(), result.returncode

def convert_tags_to_hashtags(text):
    """Convierte @foo y +bar a #foo y #bar respectivamente."""
    # Reemplazar +palabra con #palabra
    text = re.sub(r'\+(\w+)', r'#\1', text)
    # Reemplazar @palabra con #palabra
    text = re.sub(r'@(\w+)', r'#\1', text)
    return text

def extract_categories(text):
    """Extrae categorías (@palabras) del texto."""
    pattern = r'@(\w+)'
    matches = re.findall(pattern, text)
    return set(matches)

def extract_project(text):
    """
    Extrae el proyecto principal (#proyecto) del texto.
    Considera el primer #proyecto encontrado como el principal.
    """
    pattern = r'#(\w+)'
    matches = re.findall(pattern, text)
    return matches[0] if matches else None

def check_task_query_exists(file_path, project_name):
    """Verifica si la consulta de tareas ya existe en el archivo."""
    try:
        with open(file_path, "r", encoding='utf-8') as f:
            content = f.read()
            query_pattern = r'```task\s+notdone\s+tags include #' + re.escape(project_name)
            return bool(re.search(query_pattern, content))
    except FileNotFoundError:
        return False

def add_task_query(file_path, project_name):
    """Añade un bloque de consulta de tareas al archivo si no existe."""
    if not check_task_query_exists(file_path, project_name):
        with open(file_path, "a", encoding='utf-8') as f:
            f.write("\n\n")
            f.write(f"```task\nnotdone\ntags include #{project_name}\nsort by due\nsort by priority\nsort by scheudled\n```\n")
        logger.info(f"Añadida consulta de tareas para #{project_name} en {file_path}")

def create_todotxt_for_export():
    """
    Crea un archivo todotxt temporal para la exportación a JSON.
    """
    # Crear una ruta para el archivo temporal
    temp_file_path = TODO_DIR_ROOT / "temp_export.todotxt"
    
    try:
        # Crear el archivo vacío
        with open(temp_file_path, "w", encoding='utf-8') as f:
            pass  # Sólo crear el archivo vacío
        
        return temp_file_path
    except Exception as e:
        logger.error(f"Error al crear archivo todotxt temporal: {e}")
        return None

def get_checkpoint():
    """Recupera la fecha del último checkpoint y las tareas ya procesadas."""
    try:
        if CHECKPOINT_FILE.exists():
            with open(CHECKPOINT_FILE, "r") as f:
                data = json.load(f)
                return {
                    "last_run": datetime.datetime.fromisoformat(data.get("last_run", "2000-01-01T00:00:00")),
                    "processed_tasks": data.get("processed_tasks", [])
                }
        else:
            return {
                "last_run": datetime.datetime(2000, 1, 1),
                "processed_tasks": []
            }
    except Exception as e:
        logger.error(f"Error al leer checkpoint: {e}")
        return {
            "last_run": datetime.datetime(2000, 1, 1),
            "processed_tasks": []
        }

def save_checkpoint(processed_tasks):
    """Guarda la fecha actual y lista de tareas procesadas como checkpoint."""
    try:
        # Crear directorio padre si no existe
        CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        with open(CHECKPOINT_FILE, "w") as f:
            json.dump({
                "last_run": datetime.datetime.now().isoformat(),
                "processed_tasks": processed_tasks
            }, f)
        logger.info(f"Checkpoint guardado: {datetime.datetime.now().isoformat()}")
    except Exception as e:
        logger.error(f"Error al guardar checkpoint: {e}")

def extract_tasks_from_file(file_path, processed_tasks):
    """
    Extrae tareas nuevas de un archivo que no han sido procesadas previamente.
    """
    new_tasks = []
    
    try:
        if not os.path.exists(file_path):
            return []
        
        # Intentar con diferentes codificaciones
        encodings = ['utf-8', 'latin-1', 'cp1252']
        lines = []
        
        for encoding in encodings:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    lines = f.readlines()
                logger.info(f"Archivo leído correctamente con codificación: {encoding}")
                break  # Si no hay error, salir del bucle
            except UnicodeDecodeError:
                continue
        
        if not lines:
            logger.error(f"No se pudo leer el archivo con ninguna codificación: {file_path}")
            return []
            
        for line in lines:
            if line.strip().startswith("- [ ]"):
                # Extraer el texto de la tarea (sin el "- [ ]")
                task_text = line.strip()[5:].strip()
                
                # Crear un hash simple para identificar la tarea, pero primero limpiamos
                # los emojis para que no afecten al hash
                task_text_clean = re.sub(r'➕\s*\d{4}-\d{2}-\d{2}', '', task_text)
                task_text_clean = re.sub(r'🛫\s*\d{4}-\d{2}-\d{2}', '', task_text_clean)
                task_text_clean = re.sub(r'⏳\s*\d{4}-\d{2}-\d{2}', '', task_text_clean)
                task_text_clean = re.sub(r'📅\s*\d{4}-\d{2}-\d{2}', '', task_text_clean)
                task_text_clean = re.sub(r'[🔺🔼🔽]', '', task_text_clean).strip()
                
                task_hash = hashlib.md5(task_text_clean.encode('utf-8', errors='ignore')).hexdigest()
                
                # Verificar si esta tarea ya fue procesada
                if task_hash not in processed_tasks:
                    new_tasks.append({
                        "text": task_text,
                        "hash": task_hash
                    })
        
        logger.info(f"Se encontraron {len(new_tasks)} tareas nuevas en {file_path}")
        return new_tasks
    except Exception as e:
        logger.error(f"Error al extraer tareas de {file_path}: {e}")
        return []

def process_task(task_text, default_project=None, todo_file=None):
    """
    Procesa una tarea y la añade utilizando el comando todo.
    """
    try:
        # Establecer fechas predeterminadas
        fecha_hoy = datetime.date.today().strftime("%Y-%m-%d")
        fecha_inicio = fecha_hoy
        fecha_fin = (datetime.date.today() + datetime.timedelta(days=30)).strftime("%Y-%m-%d")
        
        # Hacer una copia del texto original para debug
        original_text = task_text
        logger.info(f"Procesando tarea original: {original_text}")
        
        # Extraer fechas de los iconos de Obsidian
        # Fecha de creación ➕ YYYY-MM-DD
        created_match = re.search(r'➕\s*(\d{4}-\d{2}-\d{2})', task_text)
        if created_match:
            # Quitar la fecha del texto de la tarea
            task_text = task_text.replace(created_match.group(0), "").strip()
        
        # Fecha programada 🛫 YYYY-MM-DD
        scheduled_match = re.search(r'🛫\s*(\d{4}-\d{2}-\d{2})', task_text)
        if scheduled_match:
            fecha_inicio = scheduled_match.group(1)
            # Quitar la fecha del texto de la tarea
            task_text = task_text.replace(scheduled_match.group(0), "").strip()
        
        # Alternativa para fecha programada ⏳ YYYY-MM-DD
        alt_scheduled_match = re.search(r'⏳\s*(\d{4}-\d{2}-\d{2})', task_text)
        if alt_scheduled_match:
            fecha_inicio = alt_scheduled_match.group(1)
            # Quitar la fecha del texto de la tarea
            task_text = task_text.replace(alt_scheduled_match.group(0), "").strip()
        
        # Fecha de vencimiento 📅 YYYY-MM-DD
        due_match = re.search(r'📅\s*(\d{4}-\d{2}-\d{2})', task_text)
        if due_match:
            fecha_fin = due_match.group(1)
            # Quitar la fecha del texto de la tarea
            task_text = task_text.replace(due_match.group(0), "").strip()
        
        # Prioridad 🔼 (equivale a (B)), 🔺 (equivale a (A)), 🔽 (equivale a (C))
        priority = ""
        if "🔺" in task_text:
            priority = "(A) "
            task_text = task_text.replace("🔺", "").strip()
        elif "🔼" in task_text:
            priority = "(B) "
            task_text = task_text.replace("🔼", "").strip()
        elif "🔽" in task_text:
            priority = "(C) "
            task_text = task_text.replace("🔽", "").strip()
        
        # Eliminar cualquier otro emoji o caracteres especiales que queden
        task_text = re.sub(r'[^\x00-\x7F]+', '', task_text).strip()
        logger.info(f"Texto de tarea después de limpieza: {task_text}")
        
        # Extraer todas las categorías (tanto @ como + y #)
        categorias = set()
        
        # Extraer @categorias
        at_pattern = r'@(\w+)'
        at_matches = re.findall(at_pattern, task_text)
        categorias.update(at_matches)
        
        # Extraer +categorias
        plus_pattern = r'\+(\w+)'
        plus_matches = re.findall(plus_pattern, task_text)
        categorias.update(plus_matches)
        
        # Extraer #categorias (excepto el principal proyecto si existe)
        hash_pattern = r'#(\w+)'
        hash_matches = re.findall(hash_pattern, task_text)
        categorias.update(hash_matches)
        
        # Determinar el proyecto principal (primer #proyecto)
        project = extract_project(task_text)
        if not project:
            project = default_project
            if project:
                task_text = f"#{project} {task_text}"
                # Añadir el proyecto a las categorías también
                categorias.add(project)
        else:
            # Asegurarnos de que el proyecto principal esté en las categorías
            categorias.add(project)
        
        # Limpiar el texto de la tarea eliminando las etiquetas que ya hemos procesado
        clean_task_text = task_text
        for categoria in at_matches:
            clean_task_text = re.sub(r'@' + re.escape(categoria) + r'\b', '', clean_task_text)
        for categoria in plus_matches:
            clean_task_text = re.sub(r'\+' + re.escape(categoria) + r'\b', '', clean_task_text)
        for categoria in hash_matches:
            # Solo removemos las etiquetas #categoria que no son el proyecto principal
            if categoria != project:
                clean_task_text = re.sub(r'#' + re.escape(categoria) + r'\b', '', clean_task_text)
        
        # Limpiar espacios extras que puedan quedar
        clean_task_text = re.sub(r'\s+', ' ', clean_task_text).strip()
        
        # Buscar el archivo correspondiente al proyecto
        proyecto_info = None
        for p in PROYECTOS:
            if p["title"] == project:
                proyecto_info = p
                break
        
        # Si no se encuentra el proyecto, usar un valor por defecto
        if not proyecto_info and project:
            # Añadir a la lista de proyectos
            PROYECTOS.append({
                "path": f"/mnt/windows/FTP/wiki/Obsidian/Projects/{project}.md",
                "title": project
            })
            proyecto_info = PROYECTOS[-1]
            
            # Crear el archivo si no existe
            if not os.path.exists(proyecto_info["path"]):
                os.makedirs(os.path.dirname(proyecto_info["path"]), exist_ok=True)
                with open(proyecto_info["path"], "w", encoding='utf-8') as f:
                    f.write(f"# {project}\n\n")
        
        if not proyecto_info:
            logger.error(f"No se pudo determinar el proyecto para la tarea: {task_text}")
            return False
        
        # Añadir bloque de consulta de tareas al archivo del proyecto si no existe
        add_task_query(proyecto_info["path"], project)
        
        # Convertir el título para todotxt (con hashtags)
        titulo_todotxt = clean_task_text
        
        # Determinar si es una tarea de música o estándar
        music_sites = ["youtu.be", "youtube.com", "bandcamp.com", "soundcloud.com"]
        if any(site in titulo_todotxt for site in music_sites):
            calendario = "discos"
            todofile = TODO_DIR_ROOT / "albums" / "a_todo.txt"
            # Obtener título del álbum si hay un enlace
            album_match = re.search(r'(https?://[^\s]+)', titulo_todotxt)
            if album_match:
                album_url = album_match.group(1)
                album, _ = run_command(f'yt-dlp --get-title "{album_url}"', shell=True)
            else:
                album = ""
        else:
            calendario = "tareas"
            todofile = todo_file if todo_file else TODO_DIR_ROOT / "todo" / "t_todo.todotxt"
        
        # Asegurar que solo usemos caracteres ASCII para el título
        titulo_ascii = clean_argument_string(titulo_todotxt)
        
        # Usado para exportar al JSON después (todavía necesario)
        if todo_file:
            # Preparar línea para el archivo todo.txt
            clean_txt_cmd = f"{fecha_hoy} {priority}{titulo_todotxt}"
            
            # Añadir categorías para todo.sh
            for categoria in categorias:
                clean_txt_cmd += f' +{categoria}'
            
            # Añadir fechas para todo.sh
            clean_txt_cmd += f" due:{fecha_fin}"
            if fecha_inicio != fecha_hoy:
                clean_txt_cmd += f" t:{fecha_inicio}"
            
            # Añadir al archivo todo.txt temporal
            try:
                with open(todo_file, "a", encoding='utf-8') as f:
                    f.write(clean_txt_cmd + "\n")
                logger.info(f"Añadida tarea a {todo_file} (para exportación)")
                # Limpiar el archivo después de escribir todas las tareas
                clean_todo_file(todo_file)
            except Exception as e:
                logger.error(f"Error al escribir en todo.txt temporal: {e}")
                # Intentar con codificación alternativa
                with open(todo_file, "a", encoding='latin-1') as f:
                    f.write(clean_txt_cmd + "\n")
        
        # Usar el comando todo para crear la tarea en el calendario
        if calendario == "tareas":
            # Construir comando todo base con --config y --list
            todo_cmd = f'todo --config "{HOME}/.config/todoman/config_tareas.py" new --list {TAREAS}'
            
            # Editar titulo para evitar contenido obsidian
            titulo_nuevo = re.sub(r'\bTODO\b|[#@]\S+', '', titulo_ascii).strip()
            
            # Añadir resumen limpio y seguro para línea de comandos
            todo_cmd += f' "{titulo_nuevo}"'
            
            # Añadir fechas
            todo_cmd += f' --start {fecha_inicio} --due {fecha_fin}'
            
            # Añadir categorías una por una con -c/--category
            for categoria in categorias:
                categoria_limpia = clean_argument_string(categoria)
                todo_cmd += f' -c "{categoria_limpia}"'
            
            # Añadir prioridad si existe
            if priority:
                if priority.startswith("(A)"):
                    todo_cmd += " --priority high"
                elif priority.startswith("(B)"):
                    todo_cmd += " --priority medium"
                elif priority.startswith("(C)"):
                    todo_cmd += " --priority low"
            
            # Ejecutar comando
            logger.info(f"Ejecutando comando: {todo_cmd}")
            output, status = run_command(todo_cmd, shell=True)
            if status != 0:
                logger.error(f"Error al crear tarea con todo: {output}")
                return False
            
            logger.info(f"Tarea creada con todo: {titulo_ascii}")
            run_command(f'notify-send "Enviada tarea: {titulo_ascii} ({fecha_inicio} → {fecha_fin})"', shell=True)
            
        elif calendario == "discos":
            # Para discos usamos el mismo formato pero la lista diferente
            album_limpio = clean_argument_string(album) if album else ""
            titulo_limpio = clean_argument_string(titulo_ascii)
            
            todo_cmd = f'todo --config "{HOME}/.config/todoman/config_tareas.py" new --list {DISCOS}'
            todo_cmd += f' --summary "{titulo_limpio}"'
            todo_cmd += f' --start {fecha_inicio} --due {fecha_fin}'
            
            # Añadir categorías una por una con -c/--category
            for categoria in categorias:
                categoria_limpia = clean_argument_string(categoria)
                todo_cmd += f' -c "{categoria_limpia}"'
            
            # Ejecutar comando
            logger.info(f"Ejecutando comando: {todo_cmd}")
            output, status = run_command(todo_cmd, shell=True)
            if status != 0:
                logger.error(f"Error al crear tarea de disco con todo: {output}")
                return False
            
            logger.info(f"Tarea de disco creada con todo: {titulo_limpio}")
            run_command(f'notify-send "Enviado disco: {album_limpio if album_limpio else ""} {titulo_limpio}"', shell=True)
            
        else:
            logger.error("Error al añadir tarea a radicale")
            run_command('notify-send -u critical "Error en la operación"', shell=True)
            return False
        
        return True
    except Exception as e:
        logger.error(f"Error al procesar tarea '{task_text}': {e}")
        return False


def clean_todo_file(todo_file_path):
    """
    Limpia un archivo todo.txt eliminando caracteres no ASCII y reemplazando
    emojis y caracteres especiales que puedan causar problemas.
    """
    try:
        with open(todo_file_path, "r", encoding='utf-8') as f:
            lines = f.readlines()
        
        cleaned_lines = []
        for line in lines:
            # Eliminar caracteres no ASCII excepto saltos de línea
            cleaned_line = re.sub(r'[^\x00-\x7F\n]+', '', line)
            # Reemplazar emojis específicos con sus equivalentes en texto
            cleaned_line = cleaned_line.replace("🔺", "(A) ").replace("🔼", "(B) ").replace("🔽", "(C) ")
            cleaned_line = cleaned_line.replace("📅", "due:").replace("🛫", "t:").replace("⏳", "t:").replace("➕", "")
            cleaned_lines.append(cleaned_line)
        
        with open(todo_file_path, "w", encoding='utf-8') as f:
            f.writelines(cleaned_lines)
        
        logger.info(f"Archivo todo.txt limpiado: {todo_file_path}")
        return True
    except Exception as e:
        logger.error(f"Error al limpiar archivo todo.txt: {e}")
        return False

def clean_argument_string(text):
    """
    Limpia una cadena de texto para que sea segura para usar como argumento en línea de comandos.
    Elimina caracteres no ASCII y escapa caracteres especiales.
    """
    # Eliminar caracteres no ASCII
    text = re.sub(r'[^\x00-\x7F]+', '', text)
    # Escapar caracteres especiales para shell
    text = text.replace('"', '\\"').replace('$', '\\$').replace('`', '\\`')
    # Eliminar caracteres que puedan causar problemas en la línea de comandos
    text = text.replace('\n', ' ').replace('\r', '')
    return text.strip()


def main():
    try:
        # Obtener el último checkpoint y tareas procesadas
        checkpoint_data = get_checkpoint()
        last_run = checkpoint_data["last_run"]
        processed_tasks = checkpoint_data["processed_tasks"]
        logger.info(f"Último checkpoint: {last_run.isoformat()}")
        logger.info(f"Tareas previamente procesadas: {len(processed_tasks)}")
        
        # Variable para contar tareas procesadas y nueva lista de hashes
        processed_count = 0
        new_processed_tasks = processed_tasks.copy()
        
        # Crear archivo todotxt temporal para exportación
        todo_file = create_todotxt_for_export()
        if not todo_file:
            logger.error("No se pudo crear archivo todotxt temporal")
            return 1
        
        # Procesar todas las fuentes de datos
        for source in SOURCES:
            tasks = extract_tasks_from_file(source["path"], processed_tasks)
            logger.info(f"Encontradas {len(tasks)} tareas nuevas en {source['path']}")
            
            for task in tasks:
                if process_task(task["text"], source["default_project"], todo_file):
                    processed_count += 1
                    new_processed_tasks.append(task["hash"])
        
        # Si se procesaron tareas, exportar a JSON y sincronizar
        if processed_count > 0:
            # Limpiar el archivo todo.txt antes de exportarlo
            clean_todo_file(todo_file)
            
            # Exportar a JSON para taskwarrior
            json_path = f"{TODO_DIR_ROOT}/tw_from_t_todo.json"
            export_cmd = f'python "{HOME}/Scripts/tareas/json_todotxt.py" "{todo_file}" > "{json_path}"'
            run_command(export_cmd, shell=True)
            logger.info(f"Exportado JSON para taskwarrior: {json_path}")
            
            # Importar a taskwarrior
            import_cmd = f'cat "{json_path}" | task import'
            run_command(import_cmd, shell=True)
            logger.info("Tareas importadas a taskwarrior")
            
            # Sincronizar con vdirsyncer
            run_command("vdirsyncer sync", shell=True)
            logger.info("Sincronización con vdirsyncer completada")
            
            logger.info(f"Procesadas {processed_count} tareas correctamente")
            run_command(f'notify-send "Tareas procesadas" "{processed_count} tareas nuevas procesadas"', shell=True)
        else:
            logger.info("No se encontraron tareas nuevas para procesar")
        
        # Eliminar archivo temporal
        if os.path.exists(todo_file):
            os.remove(todo_file)
            logger.info(f"Archivo temporal eliminado: {todo_file}")
        
        # Guardar checkpoint solo si todo ha ido bien
        save_checkpoint(new_processed_tasks)
        return 0
    except Exception as e:
        logger.error(f"Error general en el script: {e}")
        run_command('notify-send -u critical "Error en el procesamiento de tareas" "Revisa el log para más detalles"', shell=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())