import os
import re
from pathlib import Path

def analyze_script_calls(directory):
    """
    Analyzes script files in a directory to find calls to other scripts.
    Returns a dictionary of scripts and their dependencies.
    """
    dependencies = {}
    
    # Patrones para encontrar llamadas a scripts
    patterns = {
        'sh': [
            r'\b(?:bash|sh|source|\.) ([^\s;&|]+\.sh)\b',  # Bash/sh calls
            r'\b(?:python|python3) ([^\s;&|]+\.py)\b',      # Python calls
            r'\b\.\/([^\s;&|]+\.(?:sh|py))\b',             # ./script calls
        ],
        'py': [
            r'(?:subprocess\.(?:call|run|Popen)|os\.system)\(["\']([^"\']*\.(?:sh|py))["\']',  # subprocess/os.system
            #r'import ([^\s,;]+)',                           # Python imports
            #r'from ([^\s]+) import',                        # From imports
        ]
    }

    # Encontrar todos los scripts
    script_files = []
    for ext in ['.sh', '.py']:
        script_files.extend(Path(directory).rglob(f'*{ext}'))

    for script_path in script_files:
        script_name = str(script_path.relative_to(directory))
        dependencies[script_name] = set()
        
        try:
            with open(script_path, 'r', encoding='utf-8') as file:
                content = file.read()
                
                # Determinar qué patrones usar basado en la extensión
                ext = script_path.suffix[1:]  # Remove the dot
                current_patterns = patterns.get(ext, [])
                
                # Buscar todas las coincidencias
                for pattern in current_patterns:
                    matches = re.finditer(pattern, content)
                    for match in matches:
                        called_script = match.group(1)
                        # Limpiar el nombre del script (remover comillas, espacios, etc)
                        called_script = called_script.strip('\'"')
                        if os.path.splitext(called_script)[1] in ['.sh', '.py']:
                            dependencies[script_name].add(called_script)
                            
        except Exception as e:
            print(f"Error analyzing {script_name}: {e}")

    return dependencies

def print_dependencies(deps, indent="", visited=None):
    """
    Prints dependencies in a tree-like format.
    """
    if visited is None:
        visited = set()
        
    for script, calls in sorted(deps.items()):
        if script not in visited:
            print(f"{indent}📜 {script}")
            visited.add(script)
            for call in sorted(calls):
                if call in deps:  # Si tenemos información sobre este script
                    if call not in visited:  # Evitar ciclos infinitos
                        print(f"{indent}  └─➔ {call}")
                        print_dependencies({call: deps[call]}, indent + "    ", visited)
                else:  # Script externo o no encontrado
                    print(f"{indent}  └─➔ {call} (external/not found)")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python script_analyzer.py <directory>")
        sys.exit(1)
        
    directory = sys.argv[1]
    deps = analyze_script_calls(directory)
    print("\nScript Dependencies Tree:")
    print("------------------------")
    print_dependencies(deps)