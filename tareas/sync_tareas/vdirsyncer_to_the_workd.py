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

# Temp file for todoman output
TEMP_TODOMAN_FILE = Path(f"{HOME}/Scripts/.content/logs/todoman_tasks_temp.txt")

# Checkpoint file - saves the last processed date
CHECKPOINT_FILE = Path(f"{HOME}/Scripts/.content/logs/importar_tareas_todoman_checkpoint.json")

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

def load_existing_tasks():
    """
    Load tasks from Obsidian's Tareas.md file to avoid duplicates.
    Returns a set of task text content (normalized) for comparison.
    """
    existing_tasks = set()
    try:
        if TASKS_FILE.exists():
            # Read with error handling for encoding issues
            with open(TASKS_FILE, "r", encoding='utf-8', errors='replace') as f:
                content = f.read()
                
            # Find all task lines with "- [ ]"
            task_lines = re.findall(r'- \[ \] (.*?)(?:\n|$)', content)
            
            for task in task_lines:
                # Clean the task text to handle emojis and special characters
                task = clean_text(task)
                
                # Normalize task text for comparison (remove dates and formatting)
                normalized = re.sub(r' due:\d{4}-\d{2}-\d{2}', '', task)  # Remove due dates in text format
                normalized = re.sub(r' t:\d{4}-\d{2}-\d{2}', '', normalized)  # Remove start dates in text format
                normalized = re.sub(r' \d{4}-\d{2}-\d{2}', '', normalized)  # Remove any dates
                
                # Also handle emoji date formats
                normalized = re.sub(r' 📅 \d{4}-\d{2}-\d{2}', '', normalized)
                normalized = re.sub(r' ⏳ \d{4}-\d{2}-\d{2}', '', normalized)
                normalized = re.sub(r' 🛫 \d{4}-\d{2}-\d{2}', '', normalized)
                normalized = re.sub(r' ➕ \d{4}-\d{2}-\d{2}', '', normalized)
                
                # Remove priority markers
                normalized = re.sub(r'🔺|🔼|🔽|\(A\)|\(B\)|\(C\)', '', normalized)
                
                # Strip any remaining whitespace
                normalized = normalized.strip()
                
                existing_tasks.add(normalized)
                
    except Exception as e:
        logger.error(f"Error loading existing tasks: {e}")
    
    return existing_tasks

def task_exists_in_obsidian(task_text, existing_tasks):
    """
    Check if a task already exists in Obsidian's Tareas.md.
    Compares normalized task text.
    """
    # Clean the text first to handle encoding issues
    task_text = clean_text(task_text)
    
    # Normalize task text for comparison
    normalized = re.sub(r' due:\d{4}-\d{2}-\d{2}', '', task_text)  # Remove due dates in text format
    normalized = re.sub(r' t:\d{4}-\d{2}-\d{2}', '', normalized)  # Remove start dates in text format
    normalized = re.sub(r' \d{4}-\d{2}-\d{2}', '', normalized)  # Remove any dates
    
    # Also handle emoji date formats
    normalized = re.sub(r' 📅 \d{4}-\d{2}-\d{2}', '', normalized)
    normalized = re.sub(r' ⏳ \d{4}-\d{2}-\d{2}', '', normalized)
    normalized = re.sub(r' 🛫 \d{4}-\d{2}-\d{2}', '', normalized)
    normalized = re.sub(r' ➕ \d{4}-\d{2}-\d{2}', '', normalized)
    
    # Remove priority markers
    normalized = re.sub(r'🔺|🔼|🔽|\(A\)|\(B\)|\(C\)', '', normalized)
    
    # Strip any remaining whitespace
    normalized = normalized.strip()
    
    # Check if normalized text exists in the set of existing tasks
    return normalized in existing_tasks

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


def parse_todoman_tasks_from_file(file_path):
    """
    Parses todoman tasks from a saved output file.
    Format example:
    [ ] 83  15/04/25 22:38:01 crear script que lea TODOS de scripts y los añada a todotxt
    [ ] 55  24/03/25 16:37:01 ansible proxmox  [server]
    [ ] 62 ! (no due date) The best albums and EPs of the year 2023 so far - Music - Mixmag
    """
    tasks = []
    
    try:
        # Read file with error handling for encoding issues
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        
        for line in lines:
            # Clean the line to handle encoding issues and remove ANSI color codes
            line = clean_ansi_codes(clean_text(line.strip()))
            if not line or not line.startswith('[ ]'):
                continue
            
            try:
                # Extract task ID - make sure to only get the numeric ID
                id_match = re.match(r'\[ \] (\d+)', line)
                if not id_match:
                    continue
                
                task_id = id_match.group(1)
                
                # Remove the '[ ] ID' prefix to get the rest of the content
                remaining = line[line.find(task_id) + len(task_id):].strip()
                
                # Check for priority markers (!)
                priority = 0
                if '!' in remaining:
                    exclamation_match = re.match(r'^(\s*!+)', remaining)
                    if exclamation_match:
                        priority = len(exclamation_match.group(1).strip())
                        remaining = remaining[exclamation_match.end():].strip()
                
                # Parse the due date
                due_date = None
                if '(no due date)' in remaining:
                    remaining = remaining.replace('(no due date)', '').strip()
                else:
                    # Try to extract the date pattern DD/MM/YY HH:MM:SS
                    date_match = re.match(r'(\d{2}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})\s+(.*)', remaining)
                    if date_match:
                        date_str = date_match.group(1)
                        remaining = date_match.group(2)
                        try:
                            due_date = datetime.datetime.strptime(date_str, '%d/%m/%y %H:%M:%S').strftime('%Y-%m-%d')
                        except ValueError:
                            logger.warning(f"Could not parse date: {date_str}")
                
                # Extract categories if present [cat1, cat2]
                categories = []
                cat_match = re.search(r'\[(.*?)\]$', remaining)
                if cat_match:
                    categories_str = cat_match.group(1)
                    categories = [cat.strip() for cat in categories_str.split(',')]
                    remaining = remaining[:cat_match.start()].strip()
                
                # The remaining part is the task text
                text = remaining
                
                # Create hash for deduplication
                task_hash = hashlib.md5(f"{task_id}-{text}".encode('utf-8', errors='ignore')).hexdigest()
                
                # Create task data with all information from the list output
                task_data = {
                    "id": task_id,
                    "text": text,
                    "summary": text,  # Use text as summary since we have it
                    "priority": priority,  # 0=normal, 1=!, 2=!!
                    "due_date": due_date,
                    "categories": categories,
                    "hash": task_hash
                }
                tasks.append(task_data)
                
            except Exception as e:
                logger.warning(f"Could not parse task line: {line}. Error: {e}")
    
    except Exception as e:
        logger.error(f"Error reading todoman tasks file: {e}")
    
    return tasks

def get_todoman_task_details(task_id):
    """
    Gets detailed information about a task using todoman's show command.
    """
    cmd = f'todo --colour --config "/home/huan/.config/todoman/config_tareas.py" show {task_id}'
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
        if start_date_str != '':
            try:
                # Convert date string to ISO format
                start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d %H:%M:%S')
                details['start_date'] = start_date.strftime('%Y-%m-%d')
            except ValueError:
                logger.warning(f"Could not parse start date: {start_date_str}")
    
    due_match = re.search(due_pattern, output)
    if due_match:
        due_date_str = due_match.group(1).strip()
        if due_date_str != '':
            try:
                # Convert date string to ISO format
                due_date = datetime.datetime.strptime(due_date_str, '%Y-%m-%d %H:%M:%S')
                details['due_date'] = due_date.strftime('%Y-%m-%d')
            except ValueError:
                logger.warning(f"Could not parse due date: {due_date_str}")
    
    return details

def get_todoman_tasks():
    """
    Gets tasks from todoman in JSON format.
    """
    cmd = 'todo --config "/home/huan/.config/todoman/config_tareas.py" --porcelain --colour never list'
    output, return_code = run_command(cmd, shell=True)
    
    if return_code != 0:
        logger.error(f"Error getting tasks from todoman: {output}")
        return []
    
    try:
        tasks = json.loads(output)
        processed_tasks = []
        
        for task in tasks:
            # Extract the required fields
            task_data = {
                "id": task["id"],
                "text": task["summary"],
                "summary": task["summary"],
                "description": task["description"],
                "priority": max(0, 9 - task["priority"]) if task["priority"] else 0,  # Convert todoman priority (0-9) to your scale
                "due_date": datetime.datetime.fromtimestamp(task["due"]).strftime('%Y-%m-%d') if task["due"] else None,
                "start_date": datetime.datetime.fromtimestamp(task["start"]).strftime('%Y-%m-%d') if task["start"] else None,
                "categories": task["categories"],
                "hash": hashlib.md5(f"{task['id']}-{task['summary']}".encode('utf-8', errors='ignore')).hexdigest()
            }
            processed_tasks.append(task_data)
            
        return processed_tasks
    except json.JSONDecodeError:
        logger.error(f"Error parsing JSON output from todoman: {output}")
        return []

def process_task(task_data, processed_tasks, existing_obsidian_tasks, use_task_show=False):
    """
    Processes a task and adds it to the systems.
    If use_task_show is True, gets additional details using todoman show command.
    """
    # Check if already processed by hash
    if task_data['hash'] in processed_tasks:
        logger.info(f"Task {task_data['id']} already processed by hash, skipping")
        return False
    
    try:
        # Get more details about the task if requested
        if use_task_show:
            details = get_todoman_task_details(task_data['id'])
            # Merge details with existing task data
            task_data.update(details)
        
        # Extract text and dates - clean the text to handle encoding issues
        task_text = clean_text(task_data.get('summary', task_data['text']))
        fecha_hoy = datetime.date.today().strftime("%Y-%m-%d")
        
        # Use task dates or default values
        fecha_inicio = task_data.get("start_date", fecha_hoy)
        fecha_fin = task_data.get("due_date", None)
        
        # Extract categories
        categorias = task_data.get("categories", [])
        
        # Determine if it's a music-related task
        music_sites = ["youtu.be", "youtube.com", "bandcamp.com", "soundcloud.com", "mixmag"]
        is_music = any(site.lower() in task_text.lower() for site in music_sites)
        
        # Determine project
        project = None
        for categoria in categorias:
            categoria = categoria.strip().lower()
            if categoria == "m_fuzzy" or categoria == "enlaces":
                project = "Aplicacion_musica_pollo"
                is_music = True
                break
            elif categoria == "server":
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
        
        # Prepare tags for Obsidian
        tags = []
        
        # Add main project tag
        tags.append(f"#{project}")
        
        # Add categories as tags
        for categoria in categorias:
            categoria = categoria.strip()
            if categoria and categoria.lower() != project.lower():
                tags.append(f"#{categoria}")
        
        # Join tags with spaces
        tags_str = " ".join(tags)
        
        # Format task text for Obsidian (without tags, as they'll be added separately)
        obsidian_task = task_text
        
        # Check if task already exists in Obsidian
        full_task_text = f"{tags_str} {obsidian_task}"
        if task_exists_in_obsidian(full_task_text, existing_obsidian_tasks):
            logger.info(f"Task already exists in Obsidian: {full_task_text}")
            # Add to processed tasks to prevent future processing
            return True
        
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
        
        # 1. Add task to Obsidian with proper formatting
        with open(TASKS_FILE, "a", encoding='utf-8') as f:
            # Start with task marker
            task_line = f"- [ ] "
            
            # Add creation date if it's not today
            if fecha_inicio and fecha_inicio != fecha_hoy:
                task_line += f"➕ {fecha_inicio} "
            
            # Add tags 
            task_line += f"{tags_str} "
            
            # Add priority marker if present
            if task_data['priority'] >= 2:
                task_line += "🔺 "  # Highest priority
            elif task_data['priority'] == 1:
                task_line += "🔼 "  # Medium priority
            
            # Add scheduled/start date if it's not the creation date
            if fecha_inicio and fecha_inicio != fecha_hoy:
                task_line += f"🛫 {fecha_inicio} "
            
            # Add due date if present
            if fecha_fin:
                task_line += f"📅 {fecha_fin} "
            
            # Add the actual task text
            task_line += obsidian_task
            
            # Write the task
            f.write("\n")
            f.write(task_line)
            
        logger.info(f"Added task to {TASKS_FILE}: {task_line}")
        
        # Add task query block to project file if it doesn't exist
        add_task_query(proyecto_info["path"], project)
        
        # 2. Add to todo.sh
        todo_txt = f"{fecha_hoy} {task_text}"
        
        # Add project
        todo_txt += f" +{project}"
        
        # Add categories
        for categoria in categorias:
            categoria = categoria.strip()
            if categoria and not categoria.lower() == project.lower():
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
        todo_sh_cmd = f'todo.sh add "{clean_text_for_shell(todo_txt)}"'
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
            run_command(f'notify-send "Imported album: {album if album else ""} {tags_str} {obsidian_task}"', shell=True)
        else:
            run_command(f'notify-send "Imported task: {tags_str} {obsidian_task} ({fecha_inicio} → {fecha_fin if fecha_fin else "no due date"})"', shell=True)
        
        return True
    except Exception as e:
        logger.error(f"Error processing task {task_data['id']} '{task_data['text']}': {e}")
        return False


def clean_ansi_codes(text):
    """Remove ANSI color codes from text."""
    ansi_pattern = re.compile(r'\x1B\[[0-9;]*[mK]')
    return ansi_pattern.sub('', text)



def clean_text(text):
    """
    Cleans a string by handling encoding issues and replacing emojis
    with their text equivalents when needed.
    """
    try:
        if not text:
            return ""
            
        # If we're dealing with bytes, decode properly
        if isinstance(text, bytes):
            text = text.decode('utf-8', errors='replace')
        
        # For normal processing (keeping emojis intact), just return the text
        return text
    except Exception as e:
        # If there's any exception in processing, fall back to ASCII
        logger.warning(f"Error in clean_text: {e}")
        return str(text).encode('ascii', errors='ignore').decode('ascii')


def clean_argument_string(text):
    """
    Cleans a string to be safe for use as a command line argument.
    Removes non-ASCII characters and escapes special characters.
    """
    # Remove non-ASCII characters
    text = re.sub(r'[^\x00-\x7F]+', '', text)
    # Escape special characters for shell
    text = text.replace('"', '\\"').replace('$', '\\$').replace('`', '\\`')
    # Remove characters that might cause problems in command line
    text = text.replace('\n', ' ').replace('\r', '')
    return text.strip()



def clean_text_for_shell(text):
    """
    Cleans a string by removing non-ASCII characters and replacing emojis
    with their text equivalents for shell command usage.
    """
    if not text:
        return ""
        
    # Convert Path objects to string if needed
    if isinstance(text, Path):
        text = str(text)
        
    # Handle bytes if needed
    if isinstance(text, bytes):
        text = text.decode('utf-8', errors='replace')
        
    # Replace emojis with their text equivalents
    text = text.replace("🔺", "(A) ").replace("🔼", "(B) ").replace("🔽", "(C) ")
    text = text.replace("📅", "due:").replace("🛫", "t:").replace("⏳", "t:").replace("➕", "")
    
    # Remove other non-ASCII characters for shell compatibility
    text = re.sub(r'[^\x00-\x7F\n]+', '', text)
    
    # Escape special characters for shell
    text = text.replace('"', '\\"').replace('$', '\\$').replace('`', '\\`')
    
    # Remove characters that might cause problems in command line
    text = text.replace('\n', ' ').replace('\r', '')
    
    return text.strip()


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
        
        # Load existing tasks from Obsidian
        existing_obsidian_tasks = load_existing_tasks()
        logger.info(f"Loaded {len(existing_obsidian_tasks)} existing tasks from Obsidian")
        
        # Variable to count processed tasks and new list of hashes
        processed_count = 0
        new_processed_tasks = processed_tasks.copy()
        
        # Get tasks directly from todoman in JSON format
        tasks = get_todoman_tasks()
        logger.info(f"Found {len(tasks)} tasks in todoman")
        
        # Process each task
        for task in tasks:
            # Force re-processing if checkpoint was recently deleted
            force_reprocess = not CHECKPOINT_FILE.exists() or (
                CHECKPOINT_FILE.exists() and 
                datetime.datetime.fromtimestamp(CHECKPOINT_FILE.stat().st_mtime) > 
                datetime.datetime.now() - datetime.timedelta(minutes=5)
            )
            
            if force_reprocess or task["hash"] not in processed_tasks:
                if process_task(task, processed_tasks if not force_reprocess else [], existing_obsidian_tasks, 
                               use_task_show=False):  # No need for task show as we have all details
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