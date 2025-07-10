#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para convertir archivos Markdown de Obsidian a formato Hugo.
"""

import re
import shutil
import argparse
import yaml
import ast
import subprocess
import json
import logging
import sys
import os
from datetime import datetime



def setup_logging(script_name="hugo_blog_script", log_level=logging.INFO):
    """
    Configura un sistema de logging robusto que muestra en consola y guarda en archivo.
    """
    # Crear nombre del archivo de log con timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"{script_name}_{timestamp}.log"
    
    # Configurar el logger
    logger = logging.getLogger(script_name)
    logger.setLevel(log_level)
    
    # Limpiar handlers existentes
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Crear formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handler para consola con flush forzado
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Handler para archivo
    try:
        file_handler = logging.FileHandler(log_filename, mode='w', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.info(f"Log guardándose en: {log_filename}")
    except Exception as e:
        logger.warning(f"No se pudo crear archivo de log: {e}")
    
    # Forzar flush inmediato
    sys.stdout.flush()
    sys.stderr.flush()
    
    return logger


def execute_sync_script(app_path):
    """Ejecuta el script de sincronización de archivos Python a Markdown."""
    sync_script_path = os.path.join(app_path, "sync_scripts_to_md.py")
    
    if os.path.exists(sync_script_path):
        try:
            result = subprocess.run([
                'python3', sync_script_path, app_path
            ], capture_output=True, text=True, check=True)
            print(f"- Script de sincronización ejecutado exitosamente")
            if result.stdout:
                print(f"  Output: {result.stdout.strip()}")
        except subprocess.CalledProcessError as e:
            print(f"- Error ejecutando script de sincronización: {e}")
            if e.stderr:
                print(f"  Error: {e.stderr.strip()}")
        except FileNotFoundError:
            print(f"- Script de sincronización no encontrado en: {sync_script_path}")
    else:
        print(f"- Script de sincronización no existe: {sync_script_path}")

def debug_print(message, force_flush=True):
    """
    Función de print mejorada que fuerza el flush y añade timestamp.
    """
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")
    
    if force_flush:
        sys.stdout.flush()
        sys.stderr.flush()

def find_script_file(script_name, app_path, folder_exclusions=None, file_exclusions=None):
    """Busca un archivo de script en app_path y sus subcarpetas, respetando exclusiones."""
    # El script_name viene como "db_music_path_module.py"
    # Necesitamos buscar "db_music_path_module.py.md"
    
    # Si el script_name ya termina en .py, agregar .md
    if script_name.endswith('.py'):
        script_md_name = f"{script_name}.md"
    else:
        # Si no termina en .py, agregarlo y luego .md
        script_md_name = f"{script_name}.py.md"
    
    print(f"  - Buscando archivo: {script_md_name}")
    
    for root, dirs, files in os.walk(app_path):
        # Filtrar directorios excluidos in-place
        if folder_exclusions:
            dirs[:] = [d for d in dirs if not should_exclude_path(os.path.join(root, d), folder_exclusions, [])]
        
        if script_md_name in files:
            found_path = os.path.join(root, script_md_name)
            
            # Verificar si el archivo encontrado debe ser excluido
            if should_exclude_path(found_path, folder_exclusions, file_exclusions):
                print(f"  - Archivo excluido por filtros: {found_path}")
                continue
            
            print(f"  - Encontrado en: {found_path}")
            return found_path
    
    print(f"  - No encontrado: {script_md_name}")
    return None


def extract_code_from_md(file_path):
    """Extrae el código Python de un archivo markdown que contiene bloques de código."""
    if not os.path.exists(file_path):
        print(f"    - El archivo no existe: {file_path}")
        return None
    
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
    except Exception as e:
        print(f"    - Error leyendo archivo {file_path}: {e}")
        return None
    
    print(f"    - Archivo leído exitosamente, tamaño: {len(content)} caracteres")
    
    # Buscar bloques de código Python con diferentes variantes
    code_patterns = [
        r'```python\n(.*?)\n```',     # ```python
        r'```py\n(.*?)\n```',         # ```py  
        r'```\n(.*?)\n```',           # ``` sin especificar lenguaje
    ]
    
    for pattern in code_patterns:
        code_blocks = re.findall(pattern, content, re.DOTALL)
        if code_blocks:
            print(f"    - Encontrado bloque de código con patrón: {pattern}")
            # Retornar el primer bloque de código encontrado
            return code_blocks[0]
    
    print(f"    - No se encontraron bloques de código en el archivo")
    # Mostrar una muestra del contenido para depuración
    print(f"    - Muestra del contenido (primeros 200 chars): {content[:200]}")
    
    return None


def parse_python_arguments(code_content):
    """Versión mejorada que detecta argumentos de múltiples formas."""
    if not code_content:
        return []
    
    arguments = []
    seen_args = set()  # Para evitar duplicados
    
    print(f"    - Analizando argumentos en código Python...")
    
    # 1. Patrones de argparse más robustos
    argparse_patterns = [
        # Patrón principal con múltiples opciones
        r'add_argument\s*\(\s*[\'"]([^\'\"]+)[\'"](?:.*?help\s*=\s*[\'"]([^\'\"]*)[\'"])?(?:.*?type\s*=\s*(\w+))?(?:.*?action\s*=\s*[\'"]([^\'\"]*)[\'"])?(?:.*?default\s*=\s*([^,)]+))?',
        # Patrón para argumentos con nombres largos y cortos
        r'add_argument\s*\(\s*[\'"]([^\'\"]+)[\'"],\s*[\'"]([^\'\"]+)[\'"](?:.*?help\s*=\s*[\'"]([^\'\"]*)[\'"])?',
        # Patrón simplificado
        r'parser\.add_argument\s*\(\s*[\'"]([^\'\"]+)[\'"]',
    ]
    
    for pattern in argparse_patterns:
        matches = re.findall(pattern, code_content, re.DOTALL)
        for match in matches:
            if isinstance(match, tuple) and len(match) >= 1:
                arg_name = match[0].strip()
                
                if arg_name in seen_args:
                    continue
                seen_args.add(arg_name)
                
                help_text = match[1].strip() if len(match) > 1 and match[1] else ''
                arg_type = match[2].strip() if len(match) > 2 and match[2] else ''
                action = match[3].strip() if len(match) > 3 and match[3] else ''
                default = match[4].strip() if len(match) > 4 and match[4] else ''
                
                # Determinar tipo basado en diferentes criterios
                if action == 'store_true' or action == 'store_false':
                    type_name = 'Flag'
                elif arg_type:
                    type_name = arg_type.capitalize()
                elif arg_name.startswith('--'):
                    type_name = 'Opcional'
                else:
                    type_name = 'Posicional'
                
                # Mejorar descripción
                description = help_text or f'Argumento {arg_name}'
                if default:
                    description += f' (default: {default})'
                
                arguments.append({
                    'name': arg_name,
                    'type': type_name,
                    'description': description
                })
    
    # 2. Detectar argumentos de sys.argv
    argv_patterns = [
        r'sys\.argv\[(\d+)\].*?#\s*(.*?)$',  # sys.argv[1] # comentario
        r'if\s+len\s*\(\s*sys\.argv\s*\)\s*[><=]+\s*(\d+)',  # if len(sys.argv) > 1
        r'argv\[(\d+)\]',  # argv[1] directo
    ]
    
    for pattern in argv_patterns:
        matches = re.findall(pattern, code_content, re.MULTILINE)
        for match in matches:
            if isinstance(match, tuple):
                arg_pos = match[0]
                comment = match[1] if len(match) > 1 else ''
                arg_name = f'argv[{arg_pos}]'
            else:
                arg_name = f'argv[{match}]'
                comment = ''
            
            if arg_name not in seen_args:
                seen_args.add(arg_name)
                arguments.append({
                    'name': arg_name,
                    'type': 'Posicional',
                    'description': comment or f'Argumento posicional {arg_pos}'
                })
    
    # 3. Detectar configuraciones que sugieren argumentos
    config_arg_patterns = [
        (r'config\s*\[\s*[\'"]([^\'\"]+)[\'"]', 'Configuración'),
        (r'CONFIG\.([A-Z_]+)', 'Configuración'),
        (r'os\.environ\.get\s*\(\s*[\'"]([^\'\"]+)[\'"]', 'Variable de entorno'),
        (r'getenv\s*\(\s*[\'"]([^\'\"]+)[\'"]', 'Variable de entorno'),
    ]
    
    for pattern, arg_type in config_arg_patterns:
        matches = re.findall(pattern, code_content)
        for match in matches:
            arg_name = f'--{match.lower().replace("_", "-")}' if arg_type == 'Configuración' else match
            
            if arg_name not in seen_args:
                seen_args.add(arg_name)
                arguments.append({
                    'name': arg_name,
                    'type': arg_type,
                    'description': f'{arg_type} {match}'
                })
    
    # 4. Detectar argumentos de funciones main()
    main_func_pattern = r'def\s+main\s*\(\s*([^)]+)\s*\):'
    main_matches = re.findall(main_func_pattern, code_content)
    
    for params in main_matches:
        # Dividir parámetros y procesarlos
        param_list = [p.strip() for p in params.split(',')]
        for param in param_list:
            if '=' in param:
                param_name = param.split('=')[0].strip()
                default_val = param.split('=')[1].strip()
            else:
                param_name = param.strip()
                default_val = None
            
            if param_name and param_name not in seen_args:
                seen_args.add(param_name)
                desc = f'Parámetro de función main'
                if default_val:
                    desc += f' (default: {default_val})'
                
                arguments.append({
                    'name': param_name,
                    'type': 'Parámetro',
                    'description': desc
                })
    
    # 5. Detectar patrones de input() interactivo
    input_patterns = [
        r'input\s*\(\s*[\'"]([^\'\"]+)[\'"]',
        r'raw_input\s*\(\s*[\'"]([^\'\"]+)[\'"]',
    ]
    
    for pattern in input_patterns:
        matches = re.findall(pattern, code_content)
        for match in matches:
            arg_name = f'input: {match}'
            if arg_name not in seen_args:
                seen_args.add(arg_name)
                arguments.append({
                    'name': 'input',
                    'type': 'Interactivo',
                    'description': match
                })
    
    print(f"    - Argumentos encontrados: {len(arguments)}")
    for arg in arguments:
        print(f"      • {arg['name']} ({arg['type']}): {arg['description']}")
    
    return arguments



def parse_python_files_and_paths(code_content):
    """Analiza el código Python para extraer rutas de archivos y logs."""
    if not code_content:
        return []
    
    files_info = []
    
    # Patrones más amplios para diferentes tipos de archivos
    file_patterns = [
        (r'[\'"]([^\'\"]*\.log)[\'"]', 'Logs'),
        (r'[\'"]([^\'\"]*\.json)[\'"]', 'Caché'),
        (r'[\'"]([^\'\"]*\.db)[\'"]', 'Base de datos'),
        (r'[\'"]([^\'\"]*\.sqlite)[\'"]', 'Base de datos'),
        (r'[\'"]([^\'\"]*\.png)[\'"]', 'Depuración'),
        (r'[\'"]([^\'\"]*\.jpg)[\'"]', 'Depuración'),
        (r'[\'"]([^\'\"]*\.jpeg)[\'"]', 'Depuración'),
        (r'[\'"]([^\'\"]*\.csv)[\'"]', 'Archivo'),
        (r'[\'"]([^\'\"]*\.txt)[\'"]', 'Archivo'),
        (r'[\'"]([^\'\"]*\.xml)[\'"]', 'Archivo'),
        (r'[\'"]([^\'\"]*\.yaml)[\'"]', 'Configuración'),
        (r'[\'"]([^\'\"]*\.yml)[\'"]', 'Configuración'),
    ]
    
    # Buscar patrones de archivos
    for pattern, file_type in file_patterns:
        matches = re.findall(pattern, code_content)
        for match in matches:
            # Filtrar rutas que parecen ser archivos reales
            if not match.startswith(('http', 'ftp', '/')):  # Evitar URLs y rutas absolutas del sistema
                files_info.append({
                    'type': file_type,
                    'path': match,
                    'description': f'Archivo {file_type.lower()} generado/usado por el script'
                })
    
    # Buscar patrones específicos de logging
    log_patterns = [
        r'logging\.getLogger\([\'"]([^\'\"]*)[\'"]',
        r'log_file\s*=\s*[\'"]([^\'\"]*)[\'"]',
        r'\.log\([\'"]([^\'\"]*)[\'"]',
    ]
    
    for pattern in log_patterns:
        matches = re.findall(pattern, code_content)
        for match in matches:
            if not any(f['path'] == match for f in files_info):
                files_info.append({
                    'type': 'Logs',
                    'path': match,
                    'description': 'Archivo de log del script'
                })
    
    # Buscar patrones de cache
    cache_patterns = [
        r'cache[_/]([^\'\"]*\.json)',
        r'cache[_/]([^\'\"]*\.db)',
    ]
    
    for pattern in cache_patterns:
        matches = re.findall(pattern, code_content)
        for match in matches:
            if not any(f['path'] == match for f in files_info):
                files_info.append({
                    'type': 'Caché',
                    'path': match,
                    'description': 'Archivo de caché del script'
                })
    
    print(f"    - Archivos encontrados: {len(files_info)}")
    for file_info in files_info:
        print(f"      • {file_info['type']}: {file_info['path']}")
    
    return files_info



def parse_python_credentials(code_content):
    """Analiza el código Python para extraer información sobre credenciales."""
    if not code_content:
        return []
    
    credentials = []
    
    # Servicios conocidos y sus credenciales típicas
    service_patterns = {
        'spotify': ['client_id', 'client_secret'],
        'lastfm': ['api_key', 'api_secret'],
        'discogs': ['token', 'consumer_key', 'consumer_secret'],
        'musicbrainz': ['user_agent'],
        'youtube': ['api_key'],
        'listenbrainz': ['token'],
        'database': ['host', 'user', 'password', 'database'],
        'api': ['key', 'secret', 'token']
    }
    
    # Buscar patrones de credenciales en el código
    for service, cred_types in service_patterns.items():
        found_creds = []
        
        for cred_type in cred_types:
            # Patrones de búsqueda para credenciales
            patterns = [
                rf'{service}.*?{cred_type}',
                rf'{cred_type}.*?{service}',
                rf'[\'"]({service}_{cred_type})[\'"]',
                rf'[\'"]({cred_type})[\'"].*?{service}',
                rf'{service.upper()}_{cred_type.upper()}',
            ]
            
            for pattern in patterns:
                if re.search(pattern, code_content, re.IGNORECASE):
                    if cred_type not in found_creds:
                        found_creds.append(cred_type)
                    break
        
        if found_creds:
            credentials.append({
                'service': service.capitalize(),
                'credentials': ', '.join([f'`{cred}`' for cred in found_creds]),
                'description': f'Credenciales para {service.capitalize()}'
            })
    
    # Buscar patrones genéricos de API keys y tokens
    generic_patterns = [
        r'api[_-]?key',
        r'api[_-]?secret',
        r'access[_-]?token',
        r'client[_-]?id',
        r'client[_-]?secret',
        r'consumer[_-]?key',
        r'consumer[_-]?secret',
    ]
    
    generic_creds = []
    for pattern in generic_patterns:
        if re.search(pattern, code_content, re.IGNORECASE):
            generic_creds.append(pattern.replace('[_-]?', '_'))
    
    if generic_creds and not any(cred['service'] == 'API' for cred in credentials):
        credentials.append({
            'service': 'API',
            'credentials': ', '.join([f'`{cred}`' for cred in set(generic_creds)]),
            'description': 'Credenciales de API genéricas'
        })
    
    print(f"    - Credenciales encontradas: {len(credentials)}")
    for cred in credentials:
        print(f"      • {cred['service']}: {cred['credentials']}")
    
    return credentials


def parse_python_database_tables(code_content):
    """Versión mejorada que detecta más patrones de bases de datos."""
    if not code_content:
        return {}
    
    tables = {}
    print(f"    - Analizando estructura de base de datos...")
    
    # 1. Patrones de CREATE TABLE más robustos
    create_table_patterns = [
        # SQL estándar en strings de Python
        r'[\'\"]{1,3}CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s*\((.*?)\)[\'\"]{1,3}',
        r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s*\((.*?)(?:\);|\'\'\'})',
        # SQL en formato heredoc o multiline
        r'sql\s*=\s*[\'\"]{3}(.*?)CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s*\((.*?)\)[\'\"]{3}',
        # Patrones para SQLAlchemy
        r'Table\s*\(\s*[\'"](\w+)[\'"].*?\[(.*?)\]',
    ]
    
    for pattern in create_table_patterns:
        matches = re.findall(pattern, code_content, re.DOTALL | re.IGNORECASE)
        
        for match in matches:
            if len(match) == 2:
                table_name, columns_text = match
            elif len(match) == 3:
                _, table_name, columns_text = match
            else:
                continue
                
            columns = parse_table_columns(columns_text)
            if columns:
                tables[table_name] = columns
    
    # 2. Detectar patrones de ORM (SQLAlchemy, Django, etc.)
    orm_patterns = [
        # SQLAlchemy models
        r'class\s+(\w+)\s*\([^)]*Model[^)]*\):(.*?)(?=class|\Z)',
        r'class\s+(\w+)\s*\([^)]*Base[^)]*\):(.*?)(?=class|\Z)',
        # Django models
        r'class\s+(\w+)\s*\([^)]*models\.Model[^)]*\):(.*?)(?=class|\Z)',
    ]
    
    for pattern in orm_patterns:
        matches = re.findall(pattern, code_content, re.DOTALL)
        
        for table_name, class_body in matches:
            columns = parse_orm_fields(class_body)
            if columns:
                tables[table_name.lower()] = columns
    
    # 3. Detectar operaciones INSERT/UPDATE que revelan estructura
    dml_patterns = [
        # INSERT statements
        r'INSERT\s+INTO\s+(\w+)\s*\((.*?)\)\s*VALUES',
        r'INSERT\s+INTO\s+(\w+)\s+SET\s+(.*?)(?:WHERE|$)',
        # UPDATE statements
        r'UPDATE\s+(\w+)\s+SET\s+(.*?)(?:WHERE|$)',
        # Diccionarios que mapean a tablas
        r'(\w+)_data\s*=\s*\{(.*?)\}',
        r'(\w+)_fields\s*=\s*\[(.*?)\]',
    ]
    
    for pattern in dml_patterns:
        matches = re.findall(pattern, code_content, re.DOTALL | re.IGNORECASE)
        
        for match in matches:
            if len(match) >= 2:
                table_name = match[0]
                fields_text = match[1]
                
                # Solo crear entrada si no existe ya una más completa
                if table_name not in tables:
                    columns = parse_field_list(fields_text)
                    if columns:
                        tables[table_name] = columns
    
    # 4. Detectar patrones de consultas SELECT
    select_patterns = [
        r'SELECT\s+(.*?)\s+FROM\s+(\w+)',
        r'cursor\.execute\s*\(\s*[\'"]SELECT\s+(.*?)\s+FROM\s+(\w+)',
    ]
    
    for pattern in select_patterns:
        matches = re.findall(pattern, code_content, re.IGNORECASE)
        
        for fields, table_name in matches:
            if table_name not in tables and fields.strip() != '*':
                columns = []
                field_list = [f.strip() for f in fields.split(',')]
                for field in field_list:
                    if field and not field.upper().startswith(('COUNT', 'SUM', 'AVG', 'MAX', 'MIN')):
                        columns.append({
                            'field': f'`{field}`',
                            'type': 'UNKNOWN',
                            'description': f'Campo detectado en SELECT'
                        })
                
                if columns:
                    tables[table_name] = columns
    
    # 5. Detectar diccionarios de configuración de BD
    db_config_patterns = [
        r'(\w+)_schema\s*=\s*\{(.*?)\}',
        r'(\w+)_structure\s*=\s*\{(.*?)\}',
        r'TABLES\s*=\s*\{(.*?)\}',
    ]
    
    for pattern in db_config_patterns:
        matches = re.findall(pattern, code_content, re.DOTALL)
        
        for match in matches:
            if len(match) == 2:
                table_name, structure = match
                # Intentar parsear la estructura como Python dict
                try:
                    import ast
                    parsed = ast.literal_eval('{' + structure + '}')
                    if isinstance(parsed, dict):
                        columns = []
                        for key, value in parsed.items():
                            columns.append({
                                'field': f'`{key}`',
                                'type': str(type(value).__name__).upper(),
                                'description': f'Campo de configuración'
                            })
                        
                        if columns:
                            tables[table_name] = columns
                except:
                    pass
    
    print(f"    - Tablas encontradas: {len(tables)}")
    for table_name, columns in tables.items():
        print(f"      • {table_name}: {len(columns)} columnas")
    
    return tables


def parse_python_configuration(code_content):
    """Versión mejorada que solo genera configuración si encuentra datos útiles."""
    if not code_content:
        return ""
    
    print(f"    - Analizando configuración en el código Python")
    
    config_data = {}
    found_useful_config = False
    
    # 1. Buscar patrones de JSON válidos en el código
    json_patterns = [
        r'config\s*=\s*(\{[^}]*\})',
        r'CONFIG\s*=\s*(\{[^}]*\})',
        r'settings\s*=\s*(\{[^}]*\})',
        r'SETTINGS\s*=\s*(\{[^}]*\})',
    ]
    
    for pattern in json_patterns:
        matches = re.findall(pattern, code_content, re.DOTALL | re.IGNORECASE)
        for match in matches:
            try:
                import json
                parsed = json.loads(match)
                if parsed:  # Solo si no está vacío
                    config_data.update(parsed)
                    found_useful_config = True
                    print(f"    - JSON válido encontrado: {len(parsed)} elementos")
            except json.JSONDecodeError:
                continue
    
    # 2. Buscar patrones específicos de servicios conocidos
    service_configs = detect_service_configurations(code_content)
    if service_configs:
        config_data.update(service_configs)
        found_useful_config = True
    
    # 3. Buscar patrones de archivos de configuración
    config_file_patterns = detect_config_file_patterns(code_content)
    if config_file_patterns:
        config_data.update(config_file_patterns)
        found_useful_config = True
    
    # 4. Solo generar JSON si encontramos configuración útil
    if found_useful_config and config_data:
        import json
        config_json = json.dumps(config_data, indent=2, ensure_ascii=False)
        print(f"    - Configuración generada con {len(config_data)} secciones")
        return config_json
    
    print(f"    - No se encontró configuración útil")
    return ""


def detect_config_file_patterns(code_content):
    """Detecta patrones que indican uso de archivos de configuración."""
    config_data = {}
    
    # Buscar referencias a archivos de configuración
    config_file_patterns = [
        r'[\'"]([^\'\"]*config[^\'\"]*\.json)[\'"]',
        r'[\'"]([^\'\"]*settings[^\'\"]*\.json)[\'"]',
        r'[\'"]([^\'\"]*\.env)[\'"]',
        r'[\'"]([^\'\"]*config[^\'\"]*\.yaml)[\'"]',
        r'[\'"]([^\'\"]*config[^\'\"]*\.yml)[\'"]',
    ]
    
    config_files_found = []
    for pattern in config_file_patterns:
        matches = re.findall(pattern, code_content, re.IGNORECASE)
        config_files_found.extend(matches)
    
    if config_files_found:
        config_data['archivos_configuracion'] = {
            'descripcion': 'Archivos de configuración detectados en el código',
            'archivos': list(set(config_files_found))
        }
        print(f"      • Archivos de configuración detectados: {config_files_found}")
    
    # Buscar variables de entorno
    env_patterns = [
        r'os\.environ\.get\([\'"]([^\'\"]+)[\'"]',
        r'os\.getenv\([\'"]([^\'\"]+)[\'"]',
        r'getenv\([\'"]([^\'\"]+)[\'"]',
    ]
    
    env_vars = []
    for pattern in env_patterns:
        matches = re.findall(pattern, code_content)
        env_vars.extend(matches)
    
    if env_vars:
        config_data['variables_entorno'] = {
            'descripcion': 'Variables de entorno utilizadas',
            'variables': list(set(env_vars))
        }
        print(f"      • Variables de entorno detectadas: {env_vars}")
    
    return config_data


def detect_service_configurations(code_content):
    """Detecta configuraciones específicas de servicios conocidos."""
    config_data = {}
    
    # Patrones específicos de servicios
    service_patterns = {
        'spotify': {
            'indicators': ['spotify', 'client_id', 'client_secret'],
            'config': {
                'client_id': 'tu_spotify_client_id',
                'client_secret': 'tu_spotify_client_secret'
            }
        },
        'database': {
            'indicators': ['database', 'db_host', 'db_user', 'sqlite', 'mysql', 'postgresql'],
            'config': {
                'host': 'localhost',
                'user': 'usuario',
                'password': 'contraseña',
                'database': 'nombre_db'
            }
        },
        'lastfm': {
            'indicators': ['lastfm', 'last.fm', 'api_key'],
            'config': {
                'api_key': 'tu_lastfm_api_key',
                'api_secret': 'tu_lastfm_secret'
            }
        },
        'discogs': {
            'indicators': ['discogs', 'consumer_key', 'consumer_secret'],
            'config': {
                'consumer_key': 'tu_discogs_key',
                'consumer_secret': 'tu_discogs_secret',
                'token': 'tu_discogs_token'
            }
        },
        'logging': {
            'indicators': ['logging', 'log_level', 'log_file'],
            'config': {
                'level': 'INFO',
                'file': 'app.log',
                'format': '%(asctime)s - %(levelname)s - %(message)s'
            }
        }
    }
    
    # Verificar cada servicio
    for service_name, service_info in service_patterns.items():
        indicators_found = 0
        for indicator in service_info['indicators']:
            if re.search(rf'\b{re.escape(indicator)}\b', code_content, re.IGNORECASE):
                indicators_found += 1
        
        # Si encontramos al menos 2 indicadores, incluir la configuración
        if indicators_found >= 2:
            config_data[service_name] = service_info['config']
            print(f"      • Servicio detectado: {service_name} ({indicators_found} indicadores)")
    
    return config_data


def update_section_in_content(content, section_name, new_data, data_type):
    """Versión mejorada de update_section_in_content que evita duplicados."""
    if data_type == 'arguments':
        return update_arguments_section(content, new_data)
    elif data_type == 'files':
        return update_files_section(content, new_data)
    elif data_type == 'credentials':
        return update_credentials_section(content, new_data)
    elif data_type == 'tables':
        return update_tables_section(content, new_data)
    elif data_type == 'configuration':
        return update_configuration_section(content, new_data)
    
    return content

def update_configuration_section(content, config_json):
    """Versión mejorada que evita JSON vacío y duplicados."""
    if not config_json or config_json.strip() == '{}':
        print(f"      • Omitiendo configuración vacía")
        return content
    
    # Crear bloque de configuración JSON
    config_block = f"```json\n{config_json}\n```"
    
    # 1. Buscar sección de configuración existente
    config_pattern = r'(####\s+Configuración[^\n]*\n)(.*?)(?=####|\Z)'
    config_match = re.search(config_pattern, content, re.DOTALL)
    
    if config_match:
        existing_content = config_match.group(2).strip()
        
        # Verificar si ya existe contenido útil
        if existing_content and not existing_content.startswith('```json\n{}'):
            # Ya existe configuración útil, verificar si es diferente
            if config_json not in existing_content:
                # Agregar nueva configuración al final de la sección existente
                print(f"      • Agregando configuración adicional a sección existente")
                new_content = config_match.group(1) + existing_content + '\n\n' + config_block + '\n\n'
                content = content[:config_match.start()] + new_content + content[config_match.end():]
            else:
                print(f"      • Configuración ya existe, omitiendo")
        else:
            # Reemplazar configuración vacía o inexistente
            print(f"      • Reemplazando configuración vacía")
            new_content = config_match.group(1) + '\n' + config_block + '\n\n'
            content = content[:config_match.start()] + new_content + content[config_match.end():]
    else:
        # No existe la sección, crearla
        print(f"      • Creando nueva sección de configuración")
        # Buscar la posición antes de la última sección ####
        last_section_pattern = r'(####[^#].*?)(?=\Z)'
        last_match = None
        for match in re.finditer(r'####[^#]', content):
            last_match = match
        
        if last_match:
            # Insertar antes de la última sección
            insert_pos = last_match.start()
            new_section = f"#### Configuración\n\n{config_block}\n\n"
            content = content[:insert_pos] + new_section + content[insert_pos:]
        else:
            # Si no hay secciones, añadir al final
            content += f"\n\n#### Configuración\n\n{config_block}\n"
    
    return content


def clean_empty_configuration_sections(content):
    """Limpia secciones de configuración que solo contienen JSON vacío."""
    
    # Patrón para encontrar secciones de configuración con JSON vacío
    empty_config_patterns = [
        r'####\s+Configuración[^\n]*\n\s*```json\s*\{\s*\}\s*```\s*\n',
        r'####\s+Configuración[^\n]*\n\s*```json\s*\{\s*\}\s*```\s*(?=####|\Z)',
        r'####\s+Configuración[^\n]*\n\s*```json\s*\{\s*\}\s*```\s*$',
    ]
    
    original_content = content
    
    for pattern in empty_config_patterns:
        content = re.sub(pattern, '', content, flags=re.MULTILINE | re.DOTALL)
    
    # Limpiar múltiples líneas vacías consecutivas
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    if content != original_content:
        print("      • Secciones de configuración vacías eliminadas")
    
    return content

def update_arguments_section(content, arguments_data):
    """Actualiza la sección de argumentos en el contenido."""
    if not arguments_data:
        return content
    
    # Crear tabla de argumentos
    table_lines = [
        "| Argumento | Tipo | Descripción |",
        "| --------- | ---- | ----------- |"
    ]
    
    for arg in arguments_data:
        name = arg.get('name', '').replace('|', '\\|')
        arg_type = arg.get('type', '').replace('|', '\\|')
        desc = arg.get('description', '').replace('|', '\\|')
        table_lines.append(f"| `{name}` | {arg_type} | {desc} |")
    
    new_table = '\n'.join(table_lines)
    
    # Buscar y reemplazar la sección de argumentos
    pattern = r'(####\s+Argumentos[^\n]*\n)(.*?)(?=####|\Z)'
    match = re.search(pattern, content, re.DOTALL)
    
    if match:
        new_content = match.group(1) + '\n' + new_table + '\n\n'
        content = content[:match.start()] + new_content + content[match.end():]
    
    return content


def update_files_section(content, files_data):
    """Actualiza la sección de archivos en el contenido."""
    if not files_data:
        return content
    
    # Crear tabla de archivos
    table_lines = [
        "| Tipo | Ruta | Descripción |",
        "| ---- | ---- | ----------- |"
    ]
    
    for file_info in files_data:
        file_type = file_info.get('type', '').replace('|', '\\|')
        path = file_info.get('path', '').replace('|', '\\|')
        desc = file_info.get('description', '').replace('|', '\\|')
        table_lines.append(f"| {file_type} | `{path}` | {desc} |")
    
    new_table = '\n'.join(table_lines)
    
    # Buscar y reemplazar la sección de archivos
    pattern = r'(####\s+Archivos[^\n]*\n)(.*?)(?=####|\Z)'
    match = re.search(pattern, content, re.DOTALL)
    
    if match:
        new_content = match.group(1) + '\n' + new_table + '\n\n'
        content = content[:match.start()] + new_content + content[match.end():]
    
    return content


def update_credentials_section(content, credentials_data):
    """Actualiza la sección de credenciales en el contenido."""
    if not credentials_data:
        return content
    
    # Crear tabla de credenciales
    table_lines = [
        "| Servicio | Credenciales | Descripción |",
        "| -------- | ------------ | ----------- |"
    ]
    
    for cred in credentials_data:
        service = cred.get('service', '').replace('|', '\\|')
        credentials = cred.get('credentials', '').replace('|', '\\|')
        desc = cred.get('description', '').replace('|', '\\|')
        table_lines.append(f"| {service} | {credentials} | {desc} |")
    
    new_table = '\n'.join(table_lines)
    
    # Buscar y reemplazar la sección de credenciales
    pattern = r'(####\s+Credenciales[^\n]*\n)(.*?)(?=####|\Z)'
    match = re.search(pattern, content, re.DOTALL)
    
    if match:
        new_content = match.group(1) + '\n' + new_table + '\n\n'
        content = content[:match.start()] + new_content + content[match.end():]
    
    return content


def update_tables_section(content, tables_data):
    """Actualiza la sección de datos/tablas en el contenido."""
    if not tables_data:
        return content
    
    # Crear contenido para las tablas
    tables_content = []
    
    for table_name, columns in tables_data.items():
        table_lines = [
            f"##### Tabla {table_name}",
            "",
            "| Campo | Tipo | Descripción |",
            "| ----- | ---- | ----------- |"
        ]
        
        for col in columns:
            field = col.get('field', '').replace('|', '\\|')
            col_type = col.get('type', '').replace('|', '\\|')
            desc = col.get('description', '').replace('|', '\\|')
            table_lines.append(f"| {field} | {col_type} | {desc} |")
        
        table_lines.append("")  # Línea vacía entre tablas
        tables_content.extend(table_lines)
    
    new_tables = '\n'.join(tables_content)
    
    # Buscar y reemplazar la sección de datos
    pattern = r'(####\s+Datos[^\n]*\n)(.*?)$'
    match = re.search(pattern, content, re.DOTALL)
    
    if match:
        new_content = match.group(1) + '\n' + new_tables + '\n'
        content = content[:match.start()] + new_content
    
    return content


def parse_table_columns(columns_text):
    """Parsea texto de columnas SQL y devuelve lista estructurada."""
    columns = []
    
    # Dividir por comas pero respetando paréntesis
    column_lines = []
    paren_count = 0
    current_column = ""
    
    for char in columns_text:
        if char == '(':
            paren_count += 1
        elif char == ')':
            paren_count -= 1
        elif char == ',' and paren_count == 0:
            column_lines.append(current_column.strip())
            current_column = ""
            continue
        current_column += char
    
    if current_column.strip():
        column_lines.append(current_column.strip())
    
    for line in column_lines:
        # Limpiar línea
        line = re.sub(r'--.*$', '', line).strip()  # Remover comentarios
        if not line or line.upper().startswith(('PRIMARY', 'FOREIGN', 'UNIQUE', 'CHECK', 'CONSTRAINT', 'INDEX')):
            continue
        
        # Extraer nombre y tipo de columna
        parts = line.split()
        if len(parts) >= 2:
            col_name = parts[0].strip('`"[]')
            col_type = parts[1].upper()
            
            # Limpiar tipo de datos adicionales
            col_type = re.sub(r'\(.*?\)', '', col_type)
            
            # Generar descripción más detallada
            description = f"Campo {col_name}"
            if 'NOT NULL' in line.upper():
                description += " (requerido)"
            if 'AUTO_INCREMENT' in line.upper() or 'AUTOINCREMENT' in line.upper():
                description += " (auto-incremento)"
            if 'PRIMARY KEY' in line.upper():
                description += " (clave primaria)"
            if 'FOREIGN KEY' in line.upper():
                description += " (clave foránea)"
            
            columns.append({
                'field': f'`{col_name}`',
                'type': col_type,
                'description': description
            })
    
    return columns


def parse_orm_fields(class_body):
    """Parsea campos de modelos ORM."""
    columns = []
    
    # Patrones para diferentes tipos de ORM
    orm_field_patterns = [
        # SQLAlchemy
        r'(\w+)\s*=\s*Column\s*\(\s*(\w+)',
        r'(\w+)\s*=\s*db\.Column\s*\(\s*(\w+)',
        # Django
        r'(\w+)\s*=\s*models\.(\w+Field)',
        # General
        r'(\w+)\s*=\s*(\w+Field)\s*\(',
    ]
    
    for pattern in orm_field_patterns:
        matches = re.findall(pattern, class_body)
        
        for field_name, field_type in matches:
            # Mapear tipos comunes
            type_mapping = {
                'CharField': 'VARCHAR',
                'TextField': 'TEXT',
                'IntegerField': 'INTEGER',
                'FloatField': 'FLOAT',
                'BooleanField': 'BOOLEAN',
                'DateTimeField': 'DATETIME',
                'DateField': 'DATE',
                'String': 'VARCHAR',
                'Integer': 'INTEGER',
                'Boolean': 'BOOLEAN',
                'DateTime': 'DATETIME',
            }
            
            mapped_type = type_mapping.get(field_type, field_type.upper())
            
            columns.append({
                'field': f'`{field_name}`',
                'type': mapped_type,
                'description': f'Campo ORM {field_name}'
            })
    
    return columns

def parse_field_list(fields_text):
    """Parsea lista de campos de operaciones DML."""
    columns = []
    
    # Dividir por comas y limpiar
    fields = [f.strip() for f in fields_text.split(',')]
    
    for field in fields:
        # Limpiar el campo de operadores SQL
        field = re.sub(r'\s*=\s*[^,]+', '', field)  # Remover = value
        field = field.strip('() \'"')
        
        if field and len(field) < 50:  # Evitar texto muy largo
            columns.append({
                'field': f'`{field}`',
                'type': 'UNKNOWN',
                'description': f'Campo detectado en operación DML'
            })
    
    return columns[:10]  # Limitar a 10 campos para evitar spam


def detect_service_configurations(code_content):
    """Detecta configuraciones específicas de servicios conocidos."""
    config_data = {}
    
    # Patrones específicos de servicios
    service_patterns = {
        'spotify': {
            'indicators': ['spotify', 'client_id', 'client_secret'],
            'config': {
                'client_id': 'tu_spotify_client_id',
                'client_secret': 'tu_spotify_client_secret'
            }
        },
        'database': {
            'indicators': ['database', 'db_host', 'db_user', 'sqlite', 'mysql', 'postgresql'],
            'config': {
                'host': 'localhost',
                'user': 'usuario',
                'password': 'contraseña',
                'database': 'nombre_db'
            }
        },
        'lastfm': {
            'indicators': ['lastfm', 'last.fm', 'api_key'],
            'config': {
                'api_key': 'tu_lastfm_api_key',
                'api_secret': 'tu_lastfm_secret'
            }
        },
        'discogs': {
            'indicators': ['discogs', 'consumer_key', 'consumer_secret'],
            'config': {
                'consumer_key': 'tu_discogs_key',
                'consumer_secret': 'tu_discogs_secret',
                'token': 'tu_discogs_token'
            }
        },
        'logging': {
            'indicators': ['logging', 'log_level', 'log_file'],
            'config': {
                'level': 'INFO',
                'file': 'app.log',
                'format': '%(asctime)s - %(levelname)s - %(message)s'
            }
        }
    }
    
    # Verificar cada servicio
    for service_name, service_info in service_patterns.items():
        indicators_found = 0
        for indicator in service_info['indicators']:
            if re.search(rf'\b{re.escape(indicator)}\b', code_content, re.IGNORECASE):
                indicators_found += 1
        
        # Si encontramos al menos 2 indicadores, incluir la configuración
        if indicators_found >= 2:
            config_data[service_name] = service_info['config']
            print(f"      • Servicio detectado: {service_name} ({indicators_found} indicadores)")
    
    return config_data

def detect_config_file_patterns(code_content):
    """Detecta patrones que indican uso de archivos de configuración."""
    config_data = {}
    
    # Buscar referencias a archivos de configuración
    config_file_patterns = [
        r'[\'"]([^\'\"]*config[^\'\"]*\.json)[\'"]',
        r'[\'"]([^\'\"]*settings[^\'\"]*\.json)[\'"]',
        r'[\'"]([^\'\"]*\.env)[\'"]',
        r'[\'"]([^\'\"]*config[^\'\"]*\.yaml)[\'"]',
        r'[\'"]([^\'\"]*config[^\'\"]*\.yml)[\'"]',
    ]
    
    config_files_found = []
    for pattern in config_file_patterns:
        matches = re.findall(pattern, code_content, re.IGNORECASE)
        config_files_found.extend(matches)
    
    if config_files_found:
        config_data['archivos_configuracion'] = {
            'descripcion': 'Archivos de configuración detectados en el código',
            'archivos': list(set(config_files_found))
        }
        print(f"      • Archivos de configuración detectados: {config_files_found}")
    
    # Buscar variables de entorno
    env_patterns = [
        r'os\.environ\.get\([\'"]([^\'\"]+)[\'"]',
        r'os\.getenv\([\'"]([^\'\"]+)[\'"]',
        r'getenv\([\'"]([^\'\"]+)[\'"]',
    ]
    
    env_vars = []
    for pattern in env_patterns:
        matches = re.findall(pattern, code_content)
        env_vars.extend(matches)
    
    if env_vars:
        config_data['variables_entorno'] = {
            'descripcion': 'Variables de entorno utilizadas',
            'variables': list(set(env_vars))
        }
        print(f"      • Variables de entorno detectadas: {env_vars}")
    
    return config_data

def update_configuration_section(content, config_json):
    """Versión mejorada que evita JSON vacío y duplicados."""
    if not config_json or config_json.strip() == '{}':
        print(f"      • Omitiendo configuración vacía")
        return content
    
    # Crear bloque de configuración JSON
    config_block = f"```json\n{config_json}\n```"
    
    # 1. Buscar sección de configuración existente
    config_pattern = r'(####\s+Configuración[^\n]*\n)(.*?)(?=####|\Z)'
    config_match = re.search(config_pattern, content, re.DOTALL)
    
    if config_match:
        existing_content = config_match.group(2).strip()
        
        # Verificar si ya existe contenido útil
        if existing_content and not existing_content.startswith('```json\n{}'):
            # Ya existe configuración útil, verificar si es diferente
            if config_json not in existing_content:
                # Agregar nueva configuración al final de la sección existente
                print(f"      • Agregando configuración adicional a sección existente")
                new_content = config_match.group(1) + existing_content + '\n\n' + config_block + '\n\n'
                content = content[:config_match.start()] + new_content + content[config_match.end():]
            else:
                print(f"      • Configuración ya existe, omitiendo")
        else:
            # Reemplazar configuración vacía o inexistente
            print(f"      • Reemplazando configuración vacía")
            new_content = config_match.group(1) + '\n' + config_block + '\n\n'
            content = content[:config_match.start()] + new_content + content[config_match.end():]
    else:
        # No existe la sección, crearla
        print(f"      • Creando nueva sección de configuración")
        # Buscar la posición antes de la última sección ####
        last_section_pattern = r'(####[^#].*?)(?=\Z)'
        last_match = None
        for match in re.finditer(r'####[^#]', content):
            last_match = match
        
        if last_match:
            # Insertar antes de la última sección
            insert_pos = last_match.start()
            new_section = f"#### Configuración\n\n{config_block}\n\n"
            content = content[:insert_pos] + new_section + content[insert_pos:]
        else:
            # Si no hay secciones, añadir al final
            content += f"\n\n#### Configuración\n\n{config_block}\n"
    
    return content

def clean_empty_configuration_sections(content):
    """Limpia secciones de configuración que solo contienen JSON vacío."""
    
    # Patrón para encontrar secciones de configuración con JSON vacío
    empty_config_patterns = [
        r'####\s+Configuración[^\n]*\n\s*```json\s*\{\s*\}\s*```\s*\n',
        r'####\s+Configuración[^\n]*\n\s*```json\s*\{\s*\}\s*```\s*(?=####|\Z)',
        r'####\s+Configuración[^\n]*\n\s*```json\s*\{\s*\}\s*```\s*$',
    ]
    
    original_content = content
    
    for pattern in empty_config_patterns:
        content = re.sub(pattern, '', content, flags=re.MULTILINE | re.DOTALL)
    
    # Limpiar múltiples líneas vacías consecutivas
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    if content != original_content:
        print("      • Secciones de configuración vacías eliminadas")
    
    return content

def detect_and_update_script_references(content, app_path, folder_exclusions=None, file_exclusions=None):
    """Versión mejorada que evita configuraciones vacías y respeta exclusiones."""
    script_refs = re.findall(r'!\[\[([^]]+)\]\]', content)
    
    if not script_refs:
        print("      • No se encontraron referencias a scripts")
        return content

    print(f"- Referencias encontradas: {script_refs}")
    
    for script_ref in script_refs:
        print(f"- Procesando referencia: {script_ref}")
        
        script_file_path = find_script_file(script_ref, app_path, folder_exclusions, file_exclusions)
        
        if script_file_path:
            print(f"- Script encontrado: {script_ref}")
            
            code_content = extract_code_from_md(script_file_path)
            
            if code_content:
                print(f"  - Código extraído exitosamente ({len(code_content)} caracteres)")
                
                # Analizar el código
                arguments = parse_python_arguments(code_content)
                files = parse_python_files_and_paths(code_content)
                credentials = parse_python_credentials(code_content)
                tables = parse_python_database_tables(code_content)
                configuration = parse_python_configuration(code_content)
                
                # Actualizar secciones solo si hay datos útiles
                original_content = content
                
                if arguments:
                    content = update_section_in_content(content, 'Argumentos', arguments, 'arguments')
                    print(f"  - Argumentos actualizados: {len(arguments)} encontrados")
                
                if files:
                    content = update_section_in_content(content, 'Archivos', files, 'files')
                    print(f"  - Archivos actualizados: {len(files)} encontrados")
                
                if credentials:
                    content = update_section_in_content(content, 'Credenciales', credentials, 'credentials')
                    print(f"  - Credenciales actualizadas: {len(credentials)} encontradas")
                
                if tables:
                    content = update_section_in_content(content, 'Datos', tables, 'tables')
                    print(f"  - Tablas actualizadas: {len(tables)} encontradas")
                
                if configuration:
                    content = update_section_in_content(content, 'Configuración', configuration, 'configuration')
                    print(f"  - Configuración actualizada con datos útiles")
                else:
                    print(f"  - No se encontró configuración útil, omitiendo sección")
                
                if content == original_content:
                    print(f"  - No se encontraron datos relevantes en el script")
            else:
                print(f"  - No se pudo extraer código del archivo: {script_file_path}")
        else:
            print(f"  - Script no encontrado: {script_ref}")
    
    return content



def process_content_folder_scripts(content_folder, app_path, folder_exclusions=None, file_exclusions=None):
    """Versión mejorada que incluye limpieza de configuraciones vacías y respeta exclusiones."""
    if not os.path.exists(content_folder):
        print(f"La carpeta de contenido no existe: {content_folder}")
        return
    
    if not os.path.exists(app_path):
        print(f"La carpeta de aplicación no existe: {app_path}")
        return
    
    print(f"Procesando scripts en carpeta de contenido: {content_folder}")
    print(f"Buscando scripts en: {app_path}")
    if folder_exclusions:
        print(f"Excluyendo carpetas: {folder_exclusions}")
    if file_exclusions:
        print(f"Excluyendo archivos: {file_exclusions}")
    
    processed_files = 0
    cleaned_files = 0
    
    for root, dirs, files in os.walk(content_folder):
        # Filtrar directorios excluidos in-place
        if folder_exclusions:
            dirs[:] = [d for d in dirs if not should_exclude_path(os.path.join(root, d), folder_exclusions, [])]
        
        for file in files:
            if file.endswith('.md'):
                file_path = os.path.join(root, file)
                
                # Verificar si el archivo debe ser excluido
                if should_exclude_path(file_path, folder_exclusions, file_exclusions):
                    print(f"- Archivo excluido: {os.path.relpath(file_path, content_folder)}")
                    continue
                
                print(f"\n- Procesando archivo: {os.path.relpath(file_path, content_folder)}")
                
                # Leer contenido del archivo
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except Exception as e:
                    print(f"  - Error leyendo archivo: {e}")
                    continue
                
                # 1. Limpiar configuraciones vacías existentes
                cleaned_content = clean_empty_configuration_sections(content)
                if cleaned_content != content:
                    cleaned_files += 1
                
                # 2. Detectar y actualizar referencias a scripts (con exclusiones)
                updated_content = detect_and_update_script_references(
                    cleaned_content, app_path, folder_exclusions, file_exclusions
                )
                
                # 3. Escribir de vuelta si hubo cambios
                if updated_content != content:
                    try:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(updated_content)
                        print(f"  - Archivo actualizado: {file}")
                        processed_files += 1
                    except Exception as e:
                        print(f"  - Error escribiendo archivo: {e}")
                else:
                    print(f"  - Sin cambios en: {file}")
    
    print(f"\nTotal de archivos procesados: {processed_files}")
    if cleaned_files > 0:
        print(f"Total de archivos con configuraciones vacías limpiadas: {cleaned_files}")


# Función modificada process_obsidian_file (nueva versión)
def process_obsidian_file_enhanced(base_file, destination_folder, content_folder, 
                                  base_weight=1, img_path=None, img_dest=None, app_path=None,
                                  exclude_folders=None, exclude_files=None):
    """Versión mejorada con limpieza de configuraciones vacías y filtros de exclusión."""
    
    # Parsear patrones de exclusión
    folder_exclusions, file_exclusions = [], []
    if exclude_folders or exclude_files:
        folder_exclusions, _ = parse_exclusion_patterns(exclude_folders) if exclude_folders else ([], [])
        _, file_exclusions = parse_exclusion_patterns(exclude_files) if exclude_files else ([], [])
    
    # 1. Ejecutar script de sincronización si app_path está definido
    if app_path:
        print("=== Paso 1: Ejecutando sincronización de scripts ===")
        execute_sync_script(app_path)
        
        # 2. Detectar y actualizar scripts en archivos de contenido (con limpieza y filtros)
        print("\n=== Paso 2: Detectando y actualizando referencias a scripts ===")
        process_content_folder_scripts(content_folder, app_path, folder_exclusions, file_exclusions)
        
        # También procesar el archivo base
        print(f"- Procesando archivo base: {os.path.basename(base_file)}")
        with open(base_file, 'r', encoding='utf-8') as f:
            base_content = f.read()
        
        # Limpiar configuraciones vacías primero
        cleaned_base_content = clean_empty_configuration_sections(base_content)
        
        # Luego actualizar referencias (con filtros)
        updated_base_content = detect_and_update_script_references(
            cleaned_base_content, app_path, folder_exclusions, file_exclusions
        )
        
        if updated_base_content != base_content:
            with open(base_file, 'w', encoding='utf-8') as f:
                f.write(updated_base_content)
            print(f"- Archivo base actualizado: {os.path.basename(base_file)}")
        
        print("\n=== Paso 3: Continuando con el proceso normal ===")
    
    # 3. Continuar con el proceso normal
    os.makedirs(destination_folder, exist_ok=True)
    
    base_filename = os.path.basename(base_file)
    base_name_without_ext = os.path.splitext(base_filename)[0]
    
    main_file_path = os.path.join(destination_folder, '_index.md')
    
    with open(base_file, 'r', encoding='utf-8') as file:
        content = file.read()
    
    _, content_without_fm = parse_frontmatter(content)
    new_frontmatter = create_frontmatter(base_name_without_ext, base_weight)
    
    content_without_fm = convert_markdown_images(content_without_fm, img_path, destination_folder)
    copy_images_to_hugo(content_without_fm, img_path, destination_folder)
    
    content_without_sections = extract_sections_to_files(
        content_without_fm, destination_folder, base_name_without_ext, 
        start_weight=2, img_path=img_path
    )
    
    new_content = new_frontmatter + content_without_sections
    
    with open(main_file_path, 'w', encoding='utf-8') as file:
        file.write(new_content)
    
    # Resto del procesamiento
    all_refs = re.findall(r'!\[\[(.*?)\]\]', content_without_sections)
    
    image_refs = []
    file_refs = []
    
    img_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.bmp', '.tiff']
    
    for ref in all_refs:
        if any(ref.lower().endswith(ext) for ext in img_extensions):
            image_refs.append(ref)
        else:
            file_refs.append(ref)
    
    for ref in file_refs:
        ref_file_path = find_file_in_folder(ref, content_folder)
        
        if ref_file_path:
            ref_folder_path = os.path.join(destination_folder, ref)
            os.makedirs(ref_folder_path, exist_ok=True)
            
            ref_dest_path = os.path.join(ref_folder_path, '_index.md')
            
            with open(ref_file_path, 'r', encoding='utf-8') as file:
                ref_content = file.read()
            
            _, ref_content_without_fm = parse_frontmatter(ref_content)
            
            ref_content_without_fm = convert_markdown_images(ref_content_without_fm, img_path, ref_folder_path)
            copy_images_to_hugo(ref_content_without_fm, img_path, ref_folder_path)
            
            ref_new_frontmatter = create_frontmatter(ref, 1)
            
            ref_content_without_sections = extract_sections_to_files(
                ref_content_without_fm, ref_folder_path, ref, 
                start_weight=2, img_path=img_path
            )
            
            ref_new_content = ref_new_frontmatter + ref_content_without_sections
            
            with open(ref_dest_path, 'w', encoding='utf-8') as file:
                file.write(ref_new_content)
            
            print(f"- Archivo referenciado: {ref}/_index.md (weight: 1)")
            
            new_content = new_content.replace(f'![[{ref}]]', '')
    
    with open(main_file_path, 'w', encoding='utf-8') as file:
        file.write(new_content)
    
    print(f"Proceso completado. Archivos generados en: {destination_folder}")
    print(f"- Archivo principal: _index.md (weight: {base_weight})")
    if image_refs:
        print(f"- Imágenes procesadas: {len(image_refs)}")

def parse_frontmatter(content):
    """Extrae el frontmatter de un archivo markdown y elimina patrones específicos."""
    # Enfoque simple: si empieza con '---', elimina hasta el segundo '---'
    if content.strip().startswith('---'):
        first_marker = content.find('---')
        second_marker = content.find('---', first_marker + 3)
        
        if second_marker != -1:
            # Extraer todo después del segundo '---'
            content_without_fm = content[second_marker + 3:].strip()
        else:
            content_without_fm = content
    else:
        content_without_fm = content
    
    # Eliminar líneas con el patrón ^[[foo]] |
    content_without_fm = re.sub(r'^\^?\[\[.*?\]\]\s*\|.*$', '', content_without_fm, flags=re.MULTILINE)
    
    # Eliminar líneas vacías adicionales al principio
    content_without_fm = content_without_fm.lstrip()
    
    return {}, content_without_fm


def create_frontmatter(title, weight):
    """Crea un frontmatter para Hugo."""
    fm = {
        'title': title,
        'weight': weight
    }
    return f"---\n{yaml.dump(fm, default_flow_style=False)}---\n\n"


def find_file_in_folder(filename, folder_path):
    """Busca un archivo en una carpeta y sus subcarpetas."""
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file == filename + '.md':
                return os.path.join(root, file)
    return None


def transform_headers_to_code_blocks(content):
    """
    Función que ahora simplemente devuelve el contenido sin transformar.
    Se mantiene para compatibilidad con el resto del código.
    """
    # Devuelve el contenido sin modificar
    return content


def convert_markdown_images(content, img_path, img_dest):
    """
    Convierte las imágenes de formato Obsidian al formato estándar de Markdown.
    Actualiza las referencias para usar guiones en lugar de espacios.
    """
    if not img_path:
        return content  # Si no se proporciona ruta de imágenes, devolver contenido sin cambios
    
    # Extensiones de imagen comunes
    img_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.bmp', '.tiff']
    
    # Regex para encontrar imágenes en formato Obsidian ![[imagen.png]]
    obsidian_img_pattern = r'!\[\[(.*?)\]\]'
    
    def replace_obsidian_img(match):
        img_filename = match.group(1).strip()
        
        # Verificar si tiene extensión de imagen
        if any(img_filename.lower().endswith(ext) for ext in img_extensions):
            # Generar el nuevo nombre de archivo con guiones en lugar de espacios
            # PARA LA REFERENCIA EN MARKDOWN
            new_img_filename = img_filename.replace(' ', '-')
            
            # Es una imagen, convertir al formato estándar de Markdown
            return f'![{img_filename}]({new_img_filename})'
        else:
            # No es una imagen, mantener el formato original
            return match.group(0)
    
    # Reemplazar solo las coincidencias que tengan extensión de imagen
    updated_content = re.sub(obsidian_img_pattern, replace_obsidian_img, content)
    
    # También procesar imágenes en formato estándar de markdown ![alt](path)
    std_img_pattern = r'!\[(.*?)\]\((.*?)\)'
    
    def replace_std_img(match):
        alt_text = match.group(1)
        img_src = match.group(2)
        
        # Solo renombrar si parece ser un nombre de archivo local (sin http/https)
        if not img_src.startswith(('http://', 'https://')):
            # Extraer solo el nombre del archivo y renombrarlo
            img_filename = os.path.basename(img_src)
            new_img_filename = img_filename.replace(' ', '-')
            
            # Mantener el texto alternativo original
            return f'![{alt_text}]({new_img_filename})'
        
        # Si es una URL, mantener sin cambios
        return match.group(0)
    
    # Reemplazar imágenes en formato estándar
    updated_content = re.sub(std_img_pattern, replace_std_img, updated_content)
    
    return updated_content


def copy_images_to_hugo(content, img_path, dest_folder):
    """
    Identifica imágenes en contenido markdown de Obsidian y las copia al mismo directorio
    donde se encuentra el archivo markdown que las referencia.
    Busca las imágenes originales con espacios y las copia con guiones en su lugar.
    """
    if not img_path or not os.path.exists(img_path):
        return  # Salir si no hay ruta de imágenes o no existe
    
    if not dest_folder:
        return  # Salir si no hay ruta de destino
    
    # Asegurarse de que la carpeta de destino existe
    os.makedirs(dest_folder, exist_ok=True)
    
    # Extensiones de imagen comunes
    img_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.bmp', '.tiff']
    
    # Regex para encontrar imágenes en formato Obsidian ![[imagen.png]]
    obsidian_img_pattern = r'!\[\[(.*?)\]\]'
    obsidian_img_matches = re.findall(obsidian_img_pattern, content)
    
    # Filtrar solo las referencias que terminen con extensión de imagen
    image_files = [ref.strip() for ref in obsidian_img_matches 
                   if any(ref.strip().lower().endswith(ext) for ext in img_extensions)]
    
    # Regex para encontrar imágenes en formato markdown estándar ![alt](path)
    std_img_pattern = r'!\[(.*?)\]\((.*?)\)'
    std_img_matches = re.findall(std_img_pattern, content)
    
    # Copiar cada imagen encontrada en formato Obsidian
    for img_filename in image_files:
        # Buscar la imagen en la carpeta de origen CON EL NOMBRE ORIGINAL (con espacios)
        img_path_original = os.path.join(img_path, img_filename)
        
        # Verificar si existe el archivo
        if os.path.exists(img_path_original):
            # Generar nuevo nombre de archivo con guiones en lugar de espacios
            new_img_filename = img_filename.replace(' ', '-')
            
            # Nombre del archivo de destino
            dest_file = os.path.join(dest_folder, new_img_filename)
            
            # Copiar la imagen
            shutil.copy2(img_path_original, dest_file)
            print(f"- Imagen copiada: {img_filename} -> {new_img_filename}")
        else:
            # Verificar si existe una versión con guiones en lugar de espacios
            img_filename_with_dashes = img_filename.replace('-', ' ')
            img_path_with_spaces = os.path.join(img_path, img_filename_with_dashes)
            
            if os.path.exists(img_path_with_spaces):
                # Generar nuevo nombre de archivo con guiones
                new_img_filename = img_filename
                
                # Nombre del archivo de destino
                dest_file = os.path.join(dest_folder, new_img_filename)
                
                # Copiar la imagen
                shutil.copy2(img_path_with_spaces, dest_file)
                print(f"- Imagen copiada: {img_filename_with_dashes} -> {new_img_filename}")
            else:
                print(f"- Advertencia: No se encontró la imagen {img_filename}")
    
    # Copiar cada imagen encontrada en formato estándar
    for match in std_img_matches:
        alt_text = match[0]
        img_src = match[1]
        
        # Solo procesar si parece ser un nombre de archivo local (sin http/https)
        if not img_src.startswith(('http://', 'https://')):
            # Extraer nombre del archivo
            img_filename = os.path.basename(img_src)
            
            # Buscar la imagen por el nombre original (que puede contener espacios)
            img_path_original = os.path.join(img_path, img_filename)
            
            # Verificar si existe el archivo
            if os.path.exists(img_path_original):
                # Generar nuevo nombre de archivo con guiones en lugar de espacios
                new_img_filename = img_filename.replace(' ', '-')
                
                # Nombre del archivo de destino
                dest_file = os.path.join(dest_folder, new_img_filename)
                
                # Copiar la imagen
                shutil.copy2(img_path_original, dest_file)
                print(f"- Imagen copiada: {img_filename} -> {new_img_filename}")
            else:
                # Intentar con una versión con espacios en lugar de guiones
                img_filename_with_spaces = img_filename.replace('-', ' ')
                img_path_with_spaces = os.path.join(img_path, img_filename_with_spaces)
                
                if os.path.exists(img_path_with_spaces):
                    # Generar nuevo nombre de archivo con guiones
                    new_img_filename = img_filename
                    
                    # Nombre del archivo de destino
                    dest_file = os.path.join(dest_folder, new_img_filename)
                    
                    # Copiar la imagen
                    shutil.copy2(img_path_with_spaces, dest_file)
                    print(f"- Imagen copiada: {img_filename_with_spaces} -> {new_img_filename}")
                else:
                    print(f"- Advertencia: No se encontró la imagen {img_filename}")


def extract_sections_to_files(content, destination_folder, base_title, start_weight=2, img_path=None):
    """
    Extrae las secciones con encabezados específicos a archivos separados.
    Devuelve el contenido sin esas secciones.
    """
    # Definir los headers que queremos extraer
    headers_to_extract = ['Argumentos', 'Credenciales', 'Datos', 'Archivos', 'Configuración']    
    
    # Lista para almacenar el resultado reconstruido
    result = []
    
    # Diccionario para almacenar las secciones extraídas
    extracted_sections = {}
    
    # Buscar específicamente la sección "Datos" primero (caso especial)
    datos_pattern = r'(####\s+Datos[^\n]*\n)(.*?)$'
    datos_match = re.search(datos_pattern, content, re.DOTALL)
    
    if datos_match:
        # Extraer la sección "Datos" completa hasta el final
        datos_header = datos_match.group(1).strip()
        datos_content = datos_match.group(2).strip()
        
        # Guardar la sección "Datos"
        extracted_sections['Datos'] = datos_content
        
        # Remover la sección "Datos" del contenido
        content = content[:datos_match.start()]
    
    # Ahora procesar el resto de headers normalmente
    # Dividir el contenido por encabezados de nivel 4
    parts = re.split(r'(?=####\s+[^\n]+\n)', content)
    
    # Procesar cada parte
    for part in parts:
        # Si la parte está vacía, saltar
        if not part.strip():
            continue
            
        # Verificar si esta parte comienza con un encabezado que queremos extraer
        match = re.match(r'####\s+([^\n]+)\n', part)
        
        if match:
            header_name = match.group(1).strip()
            
            # Verificar si es uno de los headers que queremos extraer (excluyendo "Datos" ya procesado)
            if any(header_name.startswith(h) for h in headers_to_extract if h != 'Datos'):
                # Extraer el contenido (todo lo que viene después del encabezado)
                header_content = part[match.end():]
                
                # Almacenar la sección extraída
                extracted_sections[header_name] = header_content.strip()
            else:
                # Mantener la parte sin cambios
                result.append(part)
        else:
            # Mantener la parte sin cambios
            result.append(part)
    
    # Unir todas las partes para el contenido principal
    main_content = ''.join(result)
    
    # Crear archivos para las secciones extraídas
    weight = start_weight
    for header_name in sorted(extracted_sections.keys()):
        section_content = extracted_sections[header_name]
        # Crear nombre de archivo basado en el encabezado
        file_name = header_name.lower().replace(' ', '_') + '.md'
        file_path = os.path.join(destination_folder, file_name)
        
        # Procesar imágenes en el contenido de la sección si img_path existe
        if img_path:
            # Ruta de destino para imágenes es la misma carpeta del archivo
            section_dest_folder = destination_folder
            
            # Procesar imágenes en la sección
            section_content = convert_markdown_images(section_content, img_path, section_dest_folder)
            
            # Copiar imágenes al directorio donde se creará el archivo
            copy_images_to_hugo(section_content, img_path, section_dest_folder)
        
        # Crear frontmatter para el archivo
        fm = create_frontmatter(header_name, weight)
        
        # Escribir el archivo
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(fm + section_content)
        
        print(f"- Sección extraída: {file_name} (weight: {weight})")
        weight += 1
    
    return main_content


def process_obsidian_file(base_file, destination_folder, content_folder, base_weight=1, img_path=None, img_dest=None):
    """Procesa un archivo de Obsidian para convertirlo a formato Hugo."""
    # Crear carpeta de destino si no existe
    os.makedirs(destination_folder, exist_ok=True)
    
    # Obtener el nombre del archivo base sin extensión
    base_filename = os.path.basename(base_file)
    base_name_without_ext = os.path.splitext(base_filename)[0]
    
    # Definir la ruta del archivo principal en el destino
    main_file_path = os.path.join(destination_folder, '_index.md')
    
    # Leer el contenido del archivo base
    with open(base_file, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Eliminar frontmatter duplicado y obtener contenido limpio
    _, content_without_fm = parse_frontmatter(content)
    
    # Crear nuevo frontmatter con el peso especificado
    new_frontmatter = create_frontmatter(base_name_without_ext, base_weight)
    
    # Procesar imágenes en formato markdown
    content_without_fm = convert_markdown_images(content_without_fm, img_path, destination_folder)
    
    # Copiar imágenes al directorio destino (ahora mismo directorio que el archivo)
    copy_images_to_hugo(content_without_fm, img_path, destination_folder)
    
    # Extraer secciones específicas a archivos separados
    content_without_sections = extract_sections_to_files(
        content_without_fm, destination_folder, base_name_without_ext, 
        start_weight=2, img_path=img_path
    )
    
    # Combinar frontmatter y contenido sin secciones extraídas
    new_content = new_frontmatter + content_without_sections
    
    # Escribir el archivo principal
    with open(main_file_path, 'w', encoding='utf-8') as file:
        file.write(new_content)
    
    # Encontrar todas las referencias a archivos en el formato ![[archivo]]
    all_refs = re.findall(r'!\[\[(.*?)\]\]', content_without_sections)
    
    # Dividir las referencias en imágenes y archivos no imágenes
    image_refs = []
    file_refs = []
    
    # Extensiones de imagen comunes
    img_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.bmp', '.tiff']
    
    for ref in all_refs:
        # Verificar si termina con una extensión de imagen
        if any(ref.lower().endswith(ext) for ext in img_extensions):
            image_refs.append(ref)
        else:
            file_refs.append(ref)
    
    # Procesar cada referencia a archivos (no imágenes)
    for ref in file_refs:
        # Buscar el archivo referenciado
        ref_file_path = find_file_in_folder(ref, content_folder)
        
        if ref_file_path:
            # Crear una carpeta con el nombre del archivo referenciado
            ref_folder_path = os.path.join(destination_folder, ref)
            os.makedirs(ref_folder_path, exist_ok=True)
            
            # Definir nombre de archivo en destino (_index.md en la carpeta)
            ref_dest_path = os.path.join(ref_folder_path, '_index.md')
            
            # Leer el contenido del archivo referenciado
            with open(ref_file_path, 'r', encoding='utf-8') as file:
                ref_content = file.read()
            
            # Eliminar frontmatter duplicado y obtener contenido limpio
            _, ref_content_without_fm = parse_frontmatter(ref_content)
            
            # Procesar imágenes en formato markdown para el archivo referenciado
            ref_content_without_fm = convert_markdown_images(ref_content_without_fm, img_path, ref_folder_path)
            
            # Copiar imágenes al directorio de la referencia para el archivo referenciado
            copy_images_to_hugo(ref_content_without_fm, img_path, ref_folder_path)
            
            # Crear nuevo frontmatter para el archivo principal de la referencia
            ref_new_frontmatter = create_frontmatter(ref, 1)
            
            # Extraer secciones específicas a archivos separados en la carpeta de referencia
            ref_content_without_sections = extract_sections_to_files(
                ref_content_without_fm, ref_folder_path, ref, 
                start_weight=2, img_path=img_path
            )
            
            # Combinar frontmatter y contenido sin secciones extraídas
            ref_new_content = ref_new_frontmatter + ref_content_without_sections
            
            # Guardar el archivo procesado
            with open(ref_dest_path, 'w', encoding='utf-8') as file:
                file.write(ref_new_content)
            
            print(f"- Archivo referenciado: {ref}/_index.md (weight: 1)")
            
            # Eliminar la referencia del archivo principal
            new_content = new_content.replace(f'![[{ref}]]', '')
    
    # Actualizar el archivo principal con las referencias a archivos eliminadas
    with open(main_file_path, 'w', encoding='utf-8') as file:
        file.write(new_content)
    
    print(f"Proceso completado. Archivos generados en: {destination_folder}")
    print(f"- Archivo principal: _index.md (weight: {base_weight})")
    if image_refs:
        print(f"- Imágenes procesadas: {len(image_refs)}")

def parse_exclusion_patterns(exclusions_str):
    """
    Parsea una cadena de patrones de exclusión separados por comas.
    Retorna listas separadas para carpetas y archivos.
    """
    if not exclusions_str:
        return [], []
    
    patterns = [p.strip() for p in exclusions_str.split(',') if p.strip()]
    folder_patterns = []
    file_patterns = []
    
    for pattern in patterns:
        # Si termina con / o es claramente una carpeta, tratarlo como carpeta
        if pattern.endswith('/') or ('.' not in pattern and not pattern.startswith('*')):
            folder_patterns.append(pattern.rstrip('/'))
        else:
            file_patterns.append(pattern)
    
    return folder_patterns, file_patterns

def should_exclude_path(path, folder_exclusions=None, file_exclusions=None):
    """
    Verifica si una ruta debe ser excluida basándose en los patrones de exclusión.
    """
    import fnmatch
    
    if not folder_exclusions:
        folder_exclusions = []
    if not file_exclusions:
        file_exclusions = []
    
    # Obtener nombre del archivo y carpeta padre
    filename = os.path.basename(path)
    dirname = os.path.dirname(path)
    
    # Verificar exclusiones de archivos
    for pattern in file_exclusions:
        if fnmatch.fnmatch(filename, pattern):
            return True
    
    # Verificar exclusiones de carpetas (cualquier parte del path)
    path_parts = path.split(os.sep)
    for pattern in folder_exclusions:
        for part in path_parts:
            if fnmatch.fnmatch(part, pattern):
                return True
    
    return False




def main():
    parser = argparse.ArgumentParser(description='Convierte archivos Markdown de Obsidian a formato Hugo.')
    parser.add_argument('--md-base-file', required=True, help='Archivo Markdown base de Obsidian')
    parser.add_argument('--destino-md', required=True, help='Carpeta de destino para los archivos generados')
    parser.add_argument('--content-folder', required=True, help='Carpeta donde buscar los archivos referenciados')
    parser.add_argument('--base-weight', type=int, default=1, help='Peso (weight) para el archivo base (default: 1)')
    parser.add_argument('--img-path', help='Ruta donde se encuentran las imágenes referenciadas en markdown')
    parser.add_argument('--app-path', help='Ruta donde se encuentran los scripts de la aplicación en formato .py.md')
    parser.add_argument('--exclude-folders', help='Carpetas a excluir separadas por comas (ej: __pycache__,test,temp)')
    parser.add_argument('--exclude-files', help='Archivos a excluir separados por comas (ej: *.pyc,test_*.py,backup.*)')
    
    args = parser.parse_args()
    
    # Usar la función mejorada si se proporciona app_path
    if args.app_path:
        process_obsidian_file_enhanced(
            args.md_base_file, 
            args.destino_md, 
            args.content_folder,
            args.base_weight,
            args.img_path,
            None,  # img_dest no se usa
            args.app_path,
            args.exclude_folders,
            args.exclude_files
        )
    else:
        # Usar la función original
        process_obsidian_file(
            args.md_base_file, 
            args.destino_md, 
            args.content_folder,
            args.base_weight,
            args.img_path
        )

if __name__ == "__main__":
    main()