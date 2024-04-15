import os
import re
import subprocess
import sys

# Función para buscar la cadena en los archivos y abrirlos en VSCodium
def buscar_y_abrir_archivos(directorio, cadena):
    for root, dirs, files in os.walk(directorio):
        for file in files:
            ruta_archivo = os.path.join(root, file)
            try:
                with open(ruta_archivo, 'r', encoding='utf-8') as f:
                    contenido = f.read()
                    if re.search(r'\b\w{20,}\b', contenido):
                        subprocess.run(['vscodium', ruta_archivo])
            except UnicodeDecodeError:
                # Si hay un error de decodificación, omitir el archivo
                pass

# Directorio raíz donde buscar
directorio_raiz = sys.argv[1]

# Cadena a buscar (10 caracteres alfanuméricos o más)
cadena_a_buscar = r'\w{10,}'

# Llamar a la función para buscar y abrir archivos
buscar_y_abrir_archivos(directorio_raiz, cadena_a_buscar)