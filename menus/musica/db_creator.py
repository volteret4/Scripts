import os
import sys
import argparse
import json
import importlib.util
from base_module import PROJECT_ROOT

def load_script_module(script_path):
    """Carga dinámicamente un script Python como módulo"""
    spec = importlib.util.spec_from_file_location("module.name", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def load_config(config_file):
    """Carga la configuración desde un archivo JSON"""
    with open(config_file, 'r') as f:
        return json.load(f)

def resolve_paths_recursive(obj, PROJECT_ROOT):
    """
    Resuelve rutas relativas recursivamente en cualquier estructura de datos.
    """
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key.endswith('_path') and isinstance(value, str) and not os.path.isabs(value):
                obj[key] = os.path.join(PROJECT_ROOT, value)
            else:
                obj[key] = resolve_paths_recursive(value, PROJECT_ROOT)
        return obj
    elif isinstance(obj, list):
        return [resolve_paths_recursive(item, PROJECT_ROOT) for item in obj]
    else:
        return obj

def resolve_paths(config):
    """Wrapper para la función recursiva"""
    return resolve_paths_recursive(config, PROJECT_ROOT)

def main():
    parser = argparse.ArgumentParser(description='Ejecuta la cadena de scripts')
    parser.add_argument('--config', required=True, help='Archivo de configuración JSON')
    parser.add_argument('--scripts', nargs='+', help='Scripts específicos a ejecutar')
    args = parser.parse_args()
    
    # Cargar configuración
    config = load_config(args.config)
    config = resolve_paths(config)
    
    # Obtener lista de scripts a ejecutar
    scripts_to_run = args.scripts if args.scripts else config.get('scripts_order', [])
    
    if not scripts_to_run:
        print("Error: No se especificaron scripts para ejecutar")
        return 1
    
    # Ejecutar cada script
    for script_name in scripts_to_run:
        script_path = os.path.join(PROJECT_ROOT, "base_datos", f"{script_name}.py")
        
        if not os.path.exists(script_path):
            print(f"Error: No se encontró el script: {script_path}")
            continue
        
        print(f"\n=== Ejecutando {script_name} ===")
        
        # Extraer configuración específica para este script
        script_config = {}
        script_config.update(config.get("common", {}))
        script_config.update(config.get(script_name, {}))
        
        try:
            # Cargar el script como módulo
            script_module = load_script_module(script_path)
            
            # Llamar a la función main y pasarle la configuración directamente
            if hasattr(script_module, 'main'):
                # Verificar si main acepta argumentos
                import inspect
                sig = inspect.signature(script_module.main)
                if len(sig.parameters) > 0:
                    script_module.main(script_config)
                else:
                    # Configurar una variable global en el módulo
                    setattr(script_module, 'CONFIG', script_config)
                    script_module.main()
            else:
                print(f"Advertencia: El script {script_name} no tiene función main")
                
        except Exception as e:
            print(f"Error al ejecutar {script_name}: {e}")

if __name__ == "__main__":
    sys.exit(main())