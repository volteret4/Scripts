import os
import sys

def modificar_archivos(ruta_directorio):
    # Obtener la lista de archivos en el directorio
#    archivos = os.listdir(ruta_directorio)
    for directorio_actual, carpetas, archivos in os.walk(ruta_directorio):
        for archivo in archivos:

            # Comprobar si es un archivo de texto
            if archivo.endswith(('.sh', '.py')):  # Puedes cambiar la extensión según tus necesidades
                ruta_archivo = os.path.join(directorio_actual, archivo)
                # Leer el contenido del archivo
                with open(ruta_archivo, 'r') as f:
                    contenido = f.read()
                
                # Modificar el contenido
                nuevo_contenido = contenido.replace("# Script Name: replace_specific_line.py", f"# Script Name: {archivo}")
                
                # Escribir el nuevo contenido en el archivo
                with open(ruta_archivo, 'w') as f:
                    f.write(nuevo_contenido)

# Ruta del directorio donde se encuentran los archivos
ruta_directorio = sys.argv[1]  # Cambia esto por la ruta de tu directorio

# Llama a la función para modificar los archivos en el directorio especificado
modificar_archivos(ruta_directorio)