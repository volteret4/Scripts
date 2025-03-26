#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Formatter that ensures exact spacing:
- 2 blank lines after imports
- 3 blank lines between functions
- 5 blank lines between classes
"""

import re
import sys
import os


def exact_spacing(file_path):
    """Apply exact spacing rules to a file"""
    with open(file_path, "r") as file:
        content = file.read()

    # Primero elimina todos los espacios excesivos
    # Elimina espacios en blanco al final del archivo
    content = content.rstrip() + "\n"
    
    # Normaliza a una sola línea en blanco en todas partes
    content = re.sub(r'\n{2,}', '\n\n', content)
    
    # Ahora aplica las reglas específicas:
    
    # 1. Encuentra el final de las importaciones y añade exactamente 2 líneas en blanco
    # Busca el último import
    import_pattern = r'((?:from\s+[\w.]+\s+import\s+[\w.*,\s]+|import\s+[\w.,\s]+)+)\n+'
    content = re.sub(import_pattern, r'\1\n\n\n', content)
    
    # 2. Añade exactamente 3 líneas en blanco entre funciones (4 saltos de línea)
    function_pattern = r'(\ndef\s+[\w_]+\([^)]*\):.*?)(\ndef\s+)'
    content = re.sub(function_pattern, r'\1\n\n\n\n\2', content, flags=re.DOTALL)
    
    # 3. Añade exactamente 5 líneas en blanco entre clases (6 saltos de línea)
    class_pattern = r'(\nclass\s+[\w_]+.*?)(\nclass\s+)'
    content = re.sub(class_pattern, r'\1\n\n\n\n\n\n\2', content, flags=re.DOTALL)
    
    # 4. Añade exactamente 5 líneas en blanco antes de una clase que sigue a una función
    func_class_pattern = r'(\ndef\s+[\w_]+\([^)]*\):.*?)(\nclass\s+)'
    content = re.sub(func_class_pattern, r'\1\n\n\n\n\n\n\2', content, flags=re.DOTALL)
    
    # 5. Asegúrate de que no haya más de una línea en blanco en otros lugares
    other_spaces = r'([^\n])\n\n\n+([^\n])'
    content = re.sub(other_spaces, r'\1\n\n\2', content)

    # Escribe el contenido modificado de vuelta al archivo
    with open(file_path, "w") as file:
        file.write(content)


def main():
    """Main function to format Python files"""
    if len(sys.argv) < 2:
        print("Usage: python exact_formatter.py <file.py> [file2.py ...]")
        return

    for file_path in sys.argv[1:]:
        if not file_path.endswith(".py"):
            print(f"Skipping non-Python file: {file_path}")
            continue

        print(f"Applying exact spacing to {file_path}...")
        exact_spacing(file_path)
        print(f"Successfully formatted {file_path}")


if __name__ == "__main__":
    main()