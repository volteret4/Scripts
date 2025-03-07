#!/usr/bin/env python3
import os
import re
import importlib
import sys
import argparse
from collections import defaultdict
import subprocess
import importlib.metadata

# Solo unos pocos casos especiales que no podemos detectar automáticamente
SPECIAL_CASES = {
    "dotenv": "python-dotenv",
    "PIL": "pillow",
    "cv2": "opencv-python",
}

def find_python_files(directory):
    """Encuentra todos los archivos Python en el directorio y sus subdirectorios."""
    python_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    return python_files

def extract_imports(file_path):
    """Extrae todas las declaraciones de importación del archivo."""
    imports_data = {
        "direct_imports": set(),      # imports directos: import x, import x.y
        "from_imports": set(),        # imports from: from x import y, from x.y import z
        "import_froms": set(),        # la parte 'from' de los imports from
        "all_modules": set()          # conjunto de todos los módulos base (primer componente)
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            
            # Buscar imports directos (import xxx)
            import_pattern = re.compile(r'import\s+([\w\.,\s]+)')
            for match in import_pattern.finditer(content):
                for module_spec in match.group(1).split(','):
                    # Limpiar el nombre del módulo
                    module_spec = module_spec.strip().split(' as ')[0]
                    imports_data["direct_imports"].add(module_spec)
                    
                    # Agregamos el componente principal para compatibilidad
                    main_module = module_spec.split('.')[0]
                    imports_data["all_modules"].add(main_module)
            
            # Buscar imports from (from xxx import yyy)
            from_pattern = re.compile(r'from\s+([\w\.]+)\s+import')
            for match in from_pattern.finditer(content):
                module_spec = match.group(1)
                imports_data["from_imports"].add(module_spec)
                imports_data["import_froms"].add(module_spec)
                
                # También agregamos el componente principal
                main_module = module_spec.split('.')[0]
                imports_data["all_modules"].add(main_module)
                
    except Exception as e:
        print(f"Error al leer {file_path}: {e}")
    
    return imports_data

def normalize_module_name(name):
    """Normaliza el nombre del módulo para identificar duplicados con diferentes formatos."""
    # Eliminar espacios y convertir a minúsculas
    return name.strip().lower()

def find_installable_package(module_name):
    """
    Encuentra el paquete instalable para un módulo o submódulo.
    Devuelve una tupla (nombre_del_paquete, instalado, versión)
    """
    # Comprobar casos especiales primero
    if module_name in SPECIAL_CASES:
        package_name = SPECIAL_CASES[module_name]
        installed, version = check_package_installed(package_name)
        return package_name, installed, version
    
    # Si el módulo está directamente instalado, simplemente devolver su nombre
    installed, version = check_package_installed(module_name)
    if installed:
        return module_name, True, version
    
    # Para submódulos, tenemos que buscar a qué paquete pertenecen
    parts = module_name.split('.')
    
    # Probar cada parte progresivamente (de la más larga a la más corta)
    for i in range(len(parts), 0, -1):
        prefix = '.'.join(parts[:i])
        installed, version = check_package_installed(prefix)
        if installed:
            return prefix, True, version
    
    # Si llegamos aquí, no pudimos encontrar el paquete instalado
    # Intentar adivinar basado en el primer componente
    root_module = parts[0]
    
    # Realizar una búsqueda de pip para encontrar paquetes relacionados
    try:
        pip_search_result = subprocess.run(
            [sys.executable, '-m', 'pip', 'show', root_module],
            capture_output=True, text=True, check=False
        )
        if pip_search_result.returncode == 0:
            return root_module, True, extract_version_from_pip_output(pip_search_result.stdout)
    except Exception:
        pass
    
    # Como último recurso, devolver el nombre del módulo base y marcar como no instalado
    return root_module, False, None

def check_package_installed(package_name):
    """
    Verifica si un paquete está instalado y devuelve su versión.
    Devuelve una tupla (instalado, versión)
    """
    # Método 1: Intentar con importlib.metadata
    try:
        version = importlib.metadata.version(package_name)
        return True, version
    except importlib.metadata.PackageNotFoundError:
        pass
    
    # Método 2: Intentar importar el módulo directamente
    try:
        importlib.import_module(package_name)
        
        # Intenta obtener la versión con importlib (nueva alternativa a pkg_resources)
        try:
            version = importlib.metadata.version(package_name)
            return True, version
        except (importlib.metadata.PackageNotFoundError, Exception):
            pass
        
        # Método 3: Intentar obtener la versión usando pip
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'show', package_name],
                capture_output=True, text=True, check=False
            )
            if result.returncode == 0:
                version = extract_version_from_pip_output(result.stdout)
                return True, version
        except Exception:
            pass
        
        # Método 4: Intentar verificar el atributo __version__
        try:
            module = importlib.import_module(package_name)
            if hasattr(module, '__version__'):
                return True, module.__version__
        except Exception:
            pass
        
        # El módulo está instalado pero no podemos determinar la versión
        return True, "desconocida"
    
    except ImportError:
        # Método 5: Verificar con pip como último recurso
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'show', package_name],
                capture_output=True, text=True, check=False
            )
            if result.returncode == 0:
                version = extract_version_from_pip_output(result.stdout)
                return True, version
        except Exception:
            pass
        
        return False, None

def extract_version_from_pip_output(pip_output):
    """Extrae la versión del paquete desde la salida del comando pip show."""
    for line in pip_output.split('\n'):
        if line.startswith('Version:'):
            return line.split(':', 1)[1].strip()
    return "desconocida"

def is_standard_library(module_name):
    """Verifica si un módulo es parte de la biblioteca estándar de Python."""
    if module_name in sys.builtin_module_names:
        return True
    
    # Lista de módulos estándar comunes
    standard_lib_modules = {
        'datetime', 'timedelta', 'traceback', 'uuid', 'unicodedata', 'typing',
        'pathlib', 'collections', 'json', 'os', 'sys', 're', 'time', 'math',
        'random', 'string', 'itertools', 'functools', 'operator', 'argparse',
        'logging', 'csv', 'xml', 'html', 'urllib', 'http', 'socket', 'email',
        'base64', 'hashlib', 'subprocess', 'threading', 'multiprocessing',
        'queue', 'asyncio', 'contextlib', 'pickle', 'shelve', 'dbm', 'sqlite3',
        'platform', 'shutil', 'glob', 'fnmatch', 'tempfile', 'warnings',
        'weakref', 'struct', 'copy', 'enum', 'types', 'inspect', 'gc',
        'io', 'zipfile', 'tarfile', 'gzip', 'bz2', 'lzma', 'zlib', 'codecs',
        'locale', 'textwrap', 'gettext', 'stat', 'unittest'
    }
    
    if normalize_module_name(module_name) in standard_lib_modules:
        return True
    
    try:
        path = importlib.util.find_spec(module_name)
        if path is None:
            return False
        
        # Si la ruta está dentro de la carpeta de Python, es probable que sea de la biblioteca estándar
        return 'site-packages' not in path.origin
    except (ImportError, AttributeError):
        return False

def create_requirements_file(package_info, output_file='requirements.txt'):
    """
    Crea un archivo requirements.txt con los paquetes.
    package_info debe ser un diccionario con formato {nombre_paquete: versión}
    """
    with open(output_file, 'w', encoding='utf-8') as file:
        for package_name, version in sorted(package_info.items()):
            if version and version != "desconocida":
                file.write(f"{package_name}=={version}\n")
            else:
                file.write(f"{package_name}\n")

def main():
    # Configurar argumentos de línea de comandos
    parser = argparse.ArgumentParser(description='Escanear imports de Python y generar requirements.txt')
    parser.add_argument('directory', nargs='?', help='Directorio a escanear')
    parser.add_argument('-o', '--output', default='requirements.txt', help='Nombre del archivo de salida (por defecto: requirements.txt)')
    parser.add_argument('-a', '--all', action='store_true', help='Mostrar todos los imports, incluso los de la biblioteca estándar')
    parser.add_argument('-s', '--show-only', action='store_true', help='Solo mostrar los imports sin generar requirements.txt')
    parser.add_argument('-v', '--verbose', action='store_true', help='Mostrar información detallada sobre los imports')
    parser.add_argument('-d', '--debug', action='store_true', help='Mostrar información de depuración durante la ejecución')
    
    args = parser.parse_args()
    
    # Si no se proporciona un directorio como argumento, pedirlo
    directory = args.directory
    if not directory:
        directory = input("Introduce la ruta del directorio a escanear: ")
    
    if not os.path.isdir(directory):
        print(f"Error: '{directory}' no es un directorio válido.")
        return
    
    python_files = find_python_files(directory)
    print(f"Se encontraron {len(python_files)} archivos Python.")
    
    # Estructuras para almacenar los datos de los imports
    all_module_bases = set()  # Módulos base únicos (primer componente)
    all_imports = set()       # Todos los imports únicos
    all_from_imports = set()  # Todos los imports from únicos
    imports_by_file = {}      # Imports agrupados por archivo
    
    for file_path in python_files:
        imports_data = extract_imports(file_path)
        
        # Actualizar conjuntos globales
        all_module_bases.update(imports_data["all_modules"])
        all_imports.update(imports_data["direct_imports"])
        all_from_imports.update(imports_data["from_imports"])
        
        # Guardar imports para este archivo
        imports_by_file[file_path] = {
            "direct": imports_data["direct_imports"],
            "from": imports_data["import_froms"]
        }
    
    # Crear conjunto unificado de todos los imports para análisis
    unified_imports = set()
    unified_imports.update(all_imports)
    unified_imports.update(all_from_imports)
    
    # Encontrar paquetes instalables para cada import
    package_mapping = {}  # {import_spec: (package, installed, version)}
    for import_spec in unified_imports:
        package, installed, version = find_installable_package(import_spec)
        # No incluir si es parte de la biblioteca estándar
        if not args.all and is_standard_library(import_spec.split('.')[0]):
            continue
        package_mapping[import_spec] = (package, installed, version)
    
    if args.debug:
        print("\nMapeo de imports a paquetes:")
        for import_spec, (package, installed, version) in sorted(package_mapping.items()):
            status = "instalado" if installed else "no instalado"
            version_str = f" (v{version})" if version else ""
            print(f"  {import_spec} -> {package}{version_str} ({status})")
    
    # Mostrar imports por archivo
    if args.verbose:
        print("\nImports por archivo:")
        for file_path, imports in imports_by_file.items():
            if not imports["direct"] and not imports["from"]:
                continue
                
            relative_path = os.path.relpath(file_path, directory)
            print(f"\n{relative_path}:")
            
            # Mostrar imports directos
            if imports["direct"]:
                print("  Imports directos:")
                for import_spec in sorted(imports["direct"]):
                    show_import_info(import_spec, package_mapping, args)
            
            # Mostrar imports from
            if imports["from"]:
                print("  Imports from:")
                for import_spec in sorted(imports["from"]):
                    show_import_info(import_spec, package_mapping, args)
    
    # Preparar datos para requirements.txt
    requirements_packages = {}
    for import_spec, (package, installed, version) in package_mapping.items():
        if package and package not in requirements_packages:
            requirements_packages[package] = version
    
    # Crear archivo requirements.txt si no se está en modo "solo mostrar"
    if not args.show_only:
        create_requirements_file(requirements_packages, args.output)
        print(f"\nSe han encontrado {len(requirements_packages)} paquetes únicos para incluir.")
        print(f"Archivo '{args.output}' generado con éxito.")
    else:
        print("\nResumen de paquetes externos únicos:")
        for package_name, version in sorted(requirements_packages.items()):
            version_str = f" (v{version})" if version else " (versión desconocida)"
            print(f"  - {package_name}{version_str}")
        
        print(f"\nTotal de paquetes únicos: {len(requirements_packages)}")

def show_import_info(import_spec, package_mapping, args):
    """Muestra información detallada sobre un import."""
    if import_spec in package_mapping:
        package, installed, version = package_mapping[import_spec]
        status = "instalado" if installed else "no instalado"
        
        # Mostrar versión si está disponible
        version_str = f" (v{version})" if version else ""
        
        # Si el paquete es diferente del import, mostrar la relación
        package_info = f" → {package}" if package != import_spec else ""
        
        # Indicar si es biblioteca estándar
        if is_standard_library(import_spec.split('.')[0]):
            label = "biblioteca estándar"
        else:
            label = status
            
        print(f"    - {import_spec}{package_info}{version_str} ({label})")
    else:
        # Este import puede ser de la biblioteca estándar y estar filtrado
        if is_standard_library(import_spec.split('.')[0]):
            print(f"    - {import_spec} (biblioteca estándar)")
        else:
            print(f"    - {import_spec} (no analizado)")

if __name__ == "__main__":
    main()