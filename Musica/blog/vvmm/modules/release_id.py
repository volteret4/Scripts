import sys
import unicodedata
from pathlib import Path
import os

def normalize_text(input_str):
    # Normalize and remove accents
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    normalized = ''.join([c for c in nfkd_form if not unicodedata.combining(c)])
    # Replace dashes with spaces
    normalized = normalized.replace('-', ' ')
    return normalized

def main():
    if len(sys.argv) < 2:
        print("Uso: python script.py <archivo> <cadena_busqueda>")
        return

    archivo = "/mnt/NFS/blogs/vvmm/releases.txt"
    cadena_busqueda = normalize_text(sys.argv[1].lower())  # Convertir y quitar acentos de la cadena de búsqueda

    try:
        with open(archivo, 'r', encoding='utf-8') as f:
            for linea in f:
                if cadena_busqueda in normalize_text(linea.lower()):
                    # Encontramos la línea que contiene la cadena de búsqueda
                    # Extraer el número de release del disco, que es el código numérico al final de la URL
                    partes = linea.strip().split(' - ')
                    if len(partes) == 3:
                        url = partes[2]
                        numero_release = url.split('/')[-1]
                        print(numero_release)
                        return  # Terminamos la búsqueda después de encontrar la primera coincidencia
            print("No se encontró la cadena de búsqueda en el archivo.")

    except FileNotFoundError:
        print(f"No se pudo abrir el archivo: {archivo}")

if __name__ == "__main__":
    main()