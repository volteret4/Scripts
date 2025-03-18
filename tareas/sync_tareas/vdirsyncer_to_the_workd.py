#!/usr/bin/env python3
"""
Script Name: importar_tareas_todoman.py
Description: Imports tasks from todoman to todo.txt, taskwarrior and Obsidian
Author: Based on importar_tareas_vdirsyncer.py
"""

import os
import sys
import subprocess
import json
import datetime
import re
import logging
import time
import hashlib
import uuid
from pathlib import Path

# Configuration
HOME = os.environ.get('HOME')
TODO_DIR = Path("/mnt/windows/FTP/Wiki/Obsidian/Important/todotxt/todo")  # CHANGE if needed
TODO_DIR_ROOT = Path("/mnt/windows/FTP/Wiki/Obsidian/Important/todotxt/")
TASKS_FILE = Path("/mnt/windows/FTP/wiki/Obsidian/Important/Tareas.md")

# Checkpoint file - saves the last processed date
CHECKPOINT_FILE = Path(f"{HOME}/Scripts/.content/logs/importar_tareas_todo_checkpoint.json")

# Logging configuration
LOG_FILE = Path(f"{HOME}/Scripts/.content/logs/importar_tareas_todoman.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# List of markdown files with titles - define projects and their files
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

def run_command(cmd, shell=False):
    """Runs a command and returns its output."""
    if shell:
        result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    else:
        result = subprocess.run(cmd, text=True, capture_output=True)
    
    return result.stdout.strip(), result.returncode

def convert_tags_to_hashtags(text):
    """Converts @foo and +bar to #foo and #bar respectively."""
    # Replace +word with #word
    text = re.sub(r'\+(\w+)', r'#\1', text)
    # Replace @word with #word
    text = re.sub(r'@(\w+)', r'#\1', text)
    return text

def clean_todo_file(todo_file_path):
    """
    Cleans the todo.txt file for proper export.
    Creates a clean copy of the file without problematic elements.
    """
    # Create a path for the clean file
    clean_file_path = todo_file_path.with_suffix('.clean.todotxt')
    
    # Read the content of the original file
    try:
        with open(todo_file_path, "r", encoding='utf-8') as f:
            lines = f.readlines()
        
        # Clean each line
        cleaned_lines = []
        for line in lines:
            # Remove problematic elements like "@<icalendar.prop.vCategory object at 0x...>"
            cleaned_line = re.sub(r'@<icalendar\.prop\.vCategory object at 0x[0-9a-f]+>', '', line)
            # Convert +word to #word (for the clean file)
            cleaned_line = re.sub(r'\+(\w+)', r'#\1', cleaned_line)
            cleaned_lines.append(cleaned_line)
        
        # Write the cleaned content to the new file
        with open(clean_file_path, "w", encoding='utf-8') as f:
            f.writelines(cleaned_lines)
        
        return clean_file_path
    except Exception as e:
        logger.error(f"Error cleaning file: {e}")
        return todo_file_path  # Return the original path in case of error

def check_task_query_exists(file_path, project_name):
    """Checks if the task query already exists in the file."""
    try:
        with open(file_path, "r", encoding='utf-8') as f:
            content = f.read()
            query_pattern = r'```task\s+notdone\s+tags include #' + re.escape(project_name)
            return bool(re.search(query_pattern, content))
    except FileNotFoundError:
        return False

def add_task_query(file_path, project_name):
    """Adds a task query block to the file if it doesn't exist."""
    if not check_task_query_exists(file_path, project_name):
        with open(file_path, "a", encoding='utf-8') as f:
            f.write("\n\n")
            f.write(f"```task\nnotdone\ntags include #{project_name}\nsort by due\nsort by priority\nsort by scheduled\n```\n")
        logger.info(f"Added task query for #{project_name} in {file_path}")

def get_checkpoint():
    """Retrieves the date of the last checkpoint and processed tasks."""
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
        logger.error(f"Error reading checkpoint: {e}")
        return {
            "last_run": datetime.datetime(2000, 1, 1),
            "processed_tasks": []
        }

def save_checkpoint(processed_tasks):
    """Saves the current date and list of processed tasks as checkpoint."""
    try:
        # Create parent directory if it doesn't exist
        CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        with open(CHECKPOINT_FILE, "w") as f:
            json.dump({
                "last_run": datetime.datetime.now().isoformat(),
                "processed_tasks": processed_tasks
            }, f)
        logger.info(f"Checkpoint saved: {datetime.datetime.now().isoformat()}")
    except Exception as e:
        logger.error(f"Error saving checkpoint: {e}")

def parse_todoman_tasks(output):
    """
    Parses the output of todoman's list command and extracts the tasks.
    Format example:
    [ ] 83  15/04/25 22:38:01 crear script que lea TODOS de scripts y los añada a todotxt
    [ ] 55  24/03/25 16:37:01 ansible proxmox  [server]
    [ ] 62 ! (no due date) The best albums and EPs of the year 2023 so far - Music - Mixmag
    """
    tasks = []
    
    # Regular expression to match todoman task lines
    pattern = r'\[ \] (\d+)\s+(!*)?\s*(\d{2}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}|\(no due date\))\s+(.+?)(?:\s+\[([^]]+)\])?$'
    
    lines = output.strip().split('\n')
    for line in lines:
        match = re.match(pattern, line)
        if match:
            task_id = match.group(1)
            priority = match.group(2)  # ! or !! for priority
            due_str = match.group(3)
            text = match.group(4).strip()
            categories = match.group(5).split(',') if match.group(5) else []
            
            # Parse due date
            due_date = None
            if due_str != '(no due date)':
                try:
                    due_date = datetime.datetime.strptime(due_str, '%d/%m/%y %H:%M:%S').strftime('%Y-%m-%d')
                except ValueError:
                    logger.warning(f"Could not parse date: {due_str}")
            
            # Create task data
            task_data = {
                "id": task_id,
                "text": text,
                "priority": len(priority) if priority else 0,  # 0=normal, 1=!, 2=!!
                "due_date": due_date,
                "categories": categories,
                "hash": hashlib.md5(f"{task_id}-{text}".encode()).hexdigest()
            }
            tasks.append(task_data)
    
    return tasks

def get_todoman_task_details(task_id):
    """
    Gets detailed information about a task using todoman's show command.
    """
    cmd = f'todo --config "/home/huan/.config/todoman/config_tareas.py" show {task_id}'
    output, return_code = run_command(cmd, shell=True)
    
    if return_code != 0:
        logger.error(f"Error getting task details for {task_id}: {output}")
        return {}
    
    # Parse the output to extract more details
    details = {}
    
    # Regular expressions for extracting information
    summary_pattern = r'Summary: (.+)'
    description_pattern = r'Description: (.+)'
    start_pattern = r'Start: (.+)'
    due_pattern = r'Due: (.+)'
    
    # Extract data
    summary_match = re.search(summary_pattern, output)
    if summary_match:
        details['summary'] = summary_match.group(1).strip()
    
    description_match = re.search(description_pattern, output)
    if description_match:
        details['description'] = description_match.group(1).strip()
    
    start_match = re.search(start_pattern, output)
    if start_match:
        start_date_str = start_match.group(1).strip()
        try:
            # Convert date string to ISO format
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d %H:%M:%S')
            details['start_date'] = start_date.strftime('%Y-%m-%d')
        except ValueError:
            logger.warning(f"Could not parse start date: {start_date_str}")
    
    due_match = re.search(due_pattern, output)
    if due_match:
        due_date_str = due_match.group(1).strip()
        try:
            # Convert date string to ISO format
            due_date = datetime.datetime.strptime(due_date_str, '%Y-%m-%d %H:%M:%S')
            details['due_date'] = due_date.strftime('%Y-%m-%d')
        except ValueError:
            logger.warning(f"Could not parse due date: {due_date_str}")
    
    return details

def process_task(task_data, processed_tasks):
    """
    Processes a task and adds it to the systems.
    """
    # Check if already processed
    if task_data['hash'] in processed_tasks:
        logger.info(f"Task {task_data['id']} already processed, skipping")
        return False
    
    try:
        # Get more details about the task
        details = get_todoman_task_details(task_data['id'])
        
        # Merge details with existing task data
        task_data.update(details)
        
        # Extract text and dates
        task_text = task_data.get('summary', task_data['text'])
        fecha_hoy = datetime.date.today().strftime("%Y-%m-%d")
        
        # Use task dates or default values
        fecha_inicio = task_data.get("start_date", fecha_hoy)
        fecha_fin = task_data.get("due_date", (datetime.date.today() + datetime.timedelta(days=30)).strftime("%Y-%m-%d"))
        
        # Extract categories
        categorias = task_data.get("categories", [])
        
        # Determine if it's a music-related task
        music_sites = ["youtu.be", "youtube.com", "bandcamp.com", "soundcloud.com"]
        is_music = any(site.lower() in task_text.lower() for site in music_sites)
        
        # Determine project
        project = None
        for categoria in categorias:
            if categoria.strip().lower() == "m_fuzzy":
                project = "Aplicacion_musica_pollo"
                is_music = True
                break
            elif categoria.strip().lower() == "server":
                project = "Server_management"
                break
        
        # If no project, determine by default
        if not project:
            project = "Enlaces" if is_music else "General"
        
        # Find or create project
        proyecto_info = None
        for p in PROYECTOS:
            if p["title"] == project:
                proyecto_info = p
                break
        
        if not proyecto_info:
            proyecto_path = f"/mnt/windows/FTP/wiki/Obsidian/Projects/{project}.md"
            PROYECTOS.append({
                "path": proyecto_path,
                "title": project
            })
            proyecto_info = PROYECTOS[-1]
            
            # Create project file if it doesn't exist
            if not os.path.exists(proyecto_path):
                os.makedirs(os.path.dirname(proyecto_path), exist_ok=True)
                with open(proyecto_path, "w", encoding='utf-8') as f:
                    f.write(f"# {project}\n\n")
        
        # Prepare task text
        task_text_with_project = f"#{project} {task_text}"
        
        # Convert title for Obsidian (with hashtags)
        titulo_obsidian = convert_tags_to_hashtags(task_text_with_project)
        
        # Determine task type (music or standard)
        if is_music:
            todofile = TODO_DIR_ROOT / "albums" / "a_todo.txt"
            # Get album title if there's a link
            album_match = re.search(r'(https?://[^\s]+)', task_text)
            if album_match:
                album_url = album_match.group(1)
                album, _ = run_command(f'yt-dlp --get-title "{album_url}"', shell=True)
            else:
                album = ""
        else:
            todofile = TODO_DIR_ROOT / "todo" / "t_todo.todotxt"
            album = ""
        
        # Ensure parent directories exist
        todofile.parent.mkdir(parents=True, exist_ok=True)
        
        # 1. Add task to Obsidian
        with open(TASKS_FILE, "a", encoding='utf-8') as f:
            f.write("\n")
            f.write(f"- [ ] {titulo_obsidian}")
            if fecha_fin:
                f.write(f" 📅 {fecha_fin}")
            if fecha_inicio and fecha_inicio != fecha_hoy:
                f.write(f" ⏳ {fecha_inicio}")
        logger.info(f"Added task to {TASKS_FILE}: {titulo_obsidian}")
        
        # Add task query block to project file if it doesn't exist
        add_task_query(proyecto_info["path"], project)
        
        # 2. Add to todo.sh
        todo_txt = f"{fecha_hoy} {task_text}"
        
        # Add project
        todo_txt += f" +{project}"
        
        # Add categories
        for categoria in categorias:
            categoria = categoria.strip()
            if categoria:
                todo_txt += f" +{categoria}"
        
        # Add priority (A, B, C)
        if task_data['priority'] >= 2:
            todo_txt = f"(A) {todo_txt}"  # Highest priority (!! = A)
        elif task_data['priority'] == 1:
            todo_txt = f"(B) {todo_txt}"  # Medium priority (! = B)
        
        # Add dates for todo.sh
        if fecha_fin:
            todo_txt += f" due:{fecha_fin}"
        if fecha_inicio and fecha_inicio != fecha_hoy:
            todo_txt += f" t:{fecha_inicio}"
        
        # Add to todo.txt file
        with open(todofile, "a", encoding='utf-8') as f:
            f.write(todo_txt + "\n")
        logger.info(f"Added task to {todofile} (todo.sh)")
        
        # Import to todo.sh
        todo_sh_cmd = f'todo.sh add "{todo_txt}"'
        run_command(todo_sh_cmd, shell=True)
        logger.info("Task imported to todo.sh")
        
        # 3. Create clean version for taskwarrior
        clean_todofile = clean_todo_file(todofile)
        
        # 4. Export to json for taskwarrior
        json_path = f"{TODO_DIR_ROOT}/tw_from_{'a' if is_music else 't'}_todo.json"
        export_cmd = f'python "{HOME}/Scripts/tareas/json_todotxt.py" "{clean_todofile}" > "{json_path}"'
        run_command(export_cmd, shell=True)
        logger.info(f"Exported JSON for taskwarrior: {json_path}")
        
        # 5. Import to taskwarrior
        import_cmd = f'cat "{json_path}" | task import'
        run_command(import_cmd, shell=True)
        logger.info("Task imported to taskwarrior")
        
        # Notify about success
        if is_music or album:
            run_command(f'notify-send "Imported album: {album if album else ""} {titulo_obsidian}"', shell=True)
        else:
            run_command(f'notify-send "Imported task: {titulo_obsidian} ({fecha_inicio} → {fecha_fin})"', shell=True)
        
        return True
    except Exception as e:
        logger.error(f"Error processing task {task_data['id']} '{task_data['text']}': {e}")
        return False

def main():
    try:
        # First sync with vdirsyncer
        logger.info("Syncing with vdirsyncer...")
        sync_output, sync_result = run_command("vdirsyncer sync", shell=True)
        if sync_result != 0:
            logger.error(f"Error syncing with vdirsyncer: {sync_output}")
            run_command('notify-send -u critical "Error syncing with vdirsyncer"', shell=True)
            return 1
        
        # Get the last checkpoint and processed tasks
        checkpoint_data = get_checkpoint()
        last_run = checkpoint_data["last_run"]
        processed_tasks = checkpoint_data["processed_tasks"]
        logger.info(f"Last checkpoint: {last_run.isoformat()}")
        logger.info(f"Previously processed tasks: {len(processed_tasks)}")
        
        # Variable to count processed tasks and new list of hashes
        processed_count = 0
        new_processed_tasks = processed_tasks.copy()
        
        # Get tasks from todoman
        cmd = 'todo --config "/home/huan/.config/todoman/config_tareas.py" list'
        output, result = run_command(cmd, shell=True)
        
        if result != 0:
            logger.error(f"Error getting tasks from todoman: {output}")
            run_command('notify-send -u critical "Error getting tasks from todoman"', shell=True)
            return 1
        
        # Parse tasks
        tasks = parse_todoman_tasks(output)
        logger.info(f"Found {len(tasks)} tasks in todoman")
        
        # Process each task
        for task in tasks:
            if process_task(task, processed_tasks):
                processed_count += 1
                new_processed_tasks.append(task["hash"])
        
        # Notify results
        if processed_count > 0:
            logger.info(f"Processed {processed_count} tasks successfully")
            run_command(f'notify-send "Tasks imported" "{processed_count} tasks imported from todoman"', shell=True)
        else:
            logger.info("No new tasks found to import")
        
        # Save checkpoint only if everything went well
        save_checkpoint(new_processed_tasks)
        return 0
    except Exception as e:
        logger.error(f"General error in script: {e}")
        run_command('notify-send -u critical "Error importing tasks" "Check the log for more details"', shell=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())