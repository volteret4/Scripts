import fitz  # PyMuPDF
from PyPDF2 import PdfReader
import sys
import os

def generar_marcadores(pdf_path, output_path, indice_paginas):
    """
    Genera un PDF con marcadores interactivos basados en un índice textual.
    """
    # Abre el PDF con PyMuPDF
    doc = fitz.open(pdf_path)
    total_pages = len(doc)

    # Filtrar índice para páginas válidas
    toc_entries = []
    for capitulo, pagina in indice_paginas.items():
        # Ajustar página base 0 y verificar rango válido
        pagina_real = pagina - 1
        if 0 <= pagina_real < total_pages:
            toc_entries.append([1, capitulo, pagina_real])
        else:
            print(f"Advertencia: Página {pagina} para '{capitulo}' está fuera de rango")

    # Establecer tabla de contenidos
    doc.set_toc(toc_entries)

    # Guarda el archivo con los marcadores
    doc.save(output_path)
    print(f"PDF con marcadores guardado en {output_path}")

def extraer_indice(pdf_path, indice_inicio, indice_fin):
    """
    Extrae un índice textual de un PDF y lo convierte en un diccionario.
    """
    pdf = PdfReader(pdf_path)
    indice_texto = ""

    # Extraer texto de las páginas del índice
    for i in range(indice_inicio - 1, indice_fin):
        indice_texto += pdf.pages[i].extract_text()

    # Procesar el texto para crear el diccionario {capítulo: página}
    indice_paginas = {}
    for linea in indice_texto.split("\n"):
        if linea.strip():
            # Intentar separar por espacios desde el final
            partes = linea.rsplit(maxsplit=1)
            if len(partes) == 2 and partes[1].isdigit():
                capitulo = partes[0].strip()
                pagina = int(partes[1])
                indice_paginas[capitulo] = pagina
    
    return indice_paginas

# Ruta al PDF y configuración
if len(sys.argv) < 3:
    print("Uso: python script.py <PDF_ORIGINAL> <PDF_SALIDA>")
    sys.exit(1)

pdf_original = sys.argv[1]
pdf_salida = sys.argv[2]
pagina_inicio_indice = 2  # Cambia según la página inicial del índice
pagina_fin_indice = 3  # Cambia según la página final del índice

# Extraer el índice y generar marcadores
indice = extraer_indice(pdf_original, pagina_inicio_indice, pagina_fin_indice)
generar_marcadores(pdf_original, pdf_salida, indice)