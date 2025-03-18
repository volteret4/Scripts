#!/usr/bin/env python3
import re
import json
import time
import sys

def json_escape(string):
    """Escapa correctamente los caracteres para JSON usando la biblioteca estándar"""
    return json.dumps(string)[1:-1]  # Elimina las comillas que json.dumps añade

def epoch(input_date):
    """Convierte una fecha YYYY-MM-DD a tiempo epoch"""
    y, m, d = map(int, input_date.split('-'))
    return int(time.mktime((y, m, d, 0, 0, 0, 0, 0, 0)))

def parse_todo_txt(filename):
    """Parsea un archivo todo.txt y genera un array JSON"""
    priority_map = {
        'a': 'H', 'b': 'M', 'c': 'L', 'd': 'L', 'e': 'L', 'f': 'L',
        'g': 'L', 'h': 'L', 'i': 'L', 'j': 'L', 'k': 'L', 'l': 'L',
        'm': 'L', 'n': 'L', 'o': 'L', 'p': 'L', 'q': 'L', 'r': 'L',
        's': 'L', 't': 'L', 'u': 'L', 'v': 'L', 'w': 'L', 'x': 'L',
        'y': 'L', 'z': 'L'
    }
    
    tasks = []
    
    with open(filename, 'r') as file:
        for todo in file:
            todo = todo.strip()
            if not todo:
                continue
                
            status = 'pending'
            priority = ''
            entry = ''
            end = ''
            projects = []
            contexts = []
            description = ''
            due = ''
            
            # pending + pri + entry
            match = re.match(r'^\(([A-Z])\)\s(\d{4}-\d{2}-\d{2})\s(.+)$', todo, re.I)
            if match:
                status, priority, entry, description = 'pending', match.group(1), epoch(match.group(2)), match.group(3)
            
            # pending + pri
            elif re.match(r'^\(([A-Z])\)\s(.+)$', todo, re.I):
                match = re.match(r'^\(([A-Z])\)\s(.+)$', todo, re.I)
                status, priority, description = 'pending', match.group(1), match.group(2)
            
            # pending + entry
            elif re.match(r'^(\d{4}-\d{2}-\d{2})\s(.+)$', todo, re.I):
                match = re.match(r'^(\d{4}-\d{2}-\d{2})\s(.+)$', todo, re.I)
                status, entry, description = 'pending', epoch(match.group(1)), match.group(2)
            
            # done + end + entry
            elif re.match(r'^x\s(\d{4}-\d{2}-\d{2})\s(\d{4}-\d{2}-\d{2})\s(.+)$', todo, re.I):
                match = re.match(r'^x\s(\d{4}-\d{2}-\d{2})\s(\d{4}-\d{2}-\d{2})\s(.+)$', todo, re.I)
                status, end, entry, description = 'completed', epoch(match.group(1)), epoch(match.group(2)), match.group(3)
            
            # done + end
            elif re.match(r'^x\s(\d{4}-\d{2}-\d{2})\s(.+)$', todo, re.I):
                match = re.match(r'^x\s(\d{4}-\d{2}-\d{2})\s(.+)$', todo, re.I)
                status, end, description = 'completed', epoch(match.group(1)), match.group(2)
            
            # done
            elif re.match(r'^x\s(.+)$', todo, re.I):
                match = re.match(r'^x\s(.+)$', todo, re.I)
                status, description = 'completed', match.group(1)
            
            # pending
            else:
                status, description = 'pending', todo
            
            # Project
            projects = re.findall(r'\+(\S+)', description, re.I)
            
            # Contexts
            contexts = re.findall(r'\@(\S+)', description, re.I)
            
            # Due
            due_match = re.search(r'\sdue:(\d{4}-\d{2}-\d{2})', todo, re.I)
            if due_match:
                due = epoch(due_match.group(1))
            
            # Map priorities
            if priority:
                priority = priority_map.get(priority.lower(), '')
            
            # Pick first project
            first_project = projects[0] if projects else None
            
            # Compose the JSON object
            task = {"status": status}
            if priority:
                task["priority"] = priority
            if first_project:
                task["project"] = first_project
            if entry:
                task["entry"] = str(entry)
            if end:
                task["end"] = str(end)
            if due:
                task["due"] = str(due)
            if contexts:
                task["tags"] = contexts
            
            task["description"] = description
            
            tasks.append(task)
    
    return tasks

def main():
    if len(sys.argv) != 2:
        print("Uso: python todotxt_to_json.py archivo_todo.txt")
        sys.exit(1)
    
    filename = sys.argv[1]
    tasks = parse_todo_txt(filename)
    print(json.dumps(tasks, indent=2))

if __name__ == "__main__":
    main()