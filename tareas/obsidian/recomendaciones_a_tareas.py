import os
import sys
import argparse
from typing import List, Optional

def leer_recomendaciones(directorio: str) -> List[dict]:
    """
    Lee recomendaciones de archivos Markdown en un directorio, 
    ignorando secciones entre separadores y líneas en blanco.
    
    :param directorio: Ruta del directorio con archivos de recomendaciones
    :return: Lista de diccionarios con recomendaciones
    """
    recomendaciones = []
    for archivo in os.listdir(directorio):
        if archivo.endswith('.md'):
            # Obtener el tag del nombre del archivo (sin extensión)
            tag = os.path.splitext(archivo)[0]
            ruta_completa = os.path.join(directorio, archivo)
            
            with open(ruta_completa, 'r', encoding='utf-8') as f:
                dentro_separador = False
                for linea in f:
                    linea = linea.strip()
                    
                    # Ignorar líneas en blanco
                    if not linea:
                        continue
                    
                    # Manejar separadores
                    if linea == '---':
                        dentro_separador = not dentro_separador
                        continue
                    
                    # Ignorar contenido dentro de separadores
                    if dentro_separador:
                        continue
                    
                    # Añadir recomendación
                    recomendaciones.append({
                        'recomendacion': linea,
                        'tag': tag
                    })
    
    return recomendaciones

def extraer_contenido_tarea(tarea: str) -> str:
    """
    Extrae el contenido de una tarea, eliminando el checkbox, tags y espacios.
    
    :param tarea: Línea completa de tarea
    :return: Contenido de la tarea sin formato
    """
    # Eliminar checkbox y tags
    partes = tarea.split('#')[0].strip()
    contenido = partes.replace('- [ ]', '').replace('- [x]', '').strip()
    return contenido

def tarea_existe(archivo_tareas: str, contenido_tarea: str) -> bool:
    """
    Verifica si una tarea ya existe en el archivo de tareas.
    
    :param archivo_tareas: Ruta del archivo de tareas
    :param contenido_tarea: Contenido de la tarea a verificar
    :return: True si la tarea existe, False en caso contrario
    """
    if not os.path.exists(archivo_tareas):
        return False
    
    with open(archivo_tareas, 'r', encoding='utf-8') as f:
        for linea in f:
            if contenido_tarea in extraer_contenido_tarea(linea):
                return True
    
    return False

def crear_tarea(recomendacion: str, tag: str, tags_adicionales: Optional[List[str]] = None) -> str:
    """
    Crea una línea de tarea para Obsidian.
    
    :param recomendacion: Texto de la recomendación
    :param tag: Tag base del recomendador
    :param tags_adicionales: Lista de tags adicionales a añadir
    :return: Línea de tarea formateada
    """
    # Tags base y adicionales, añadiendo #recomendaciones por defecto
    tags_totales = [tag, 'recomendaciones']
    if tags_adicionales:
        tags_totales.extend(tags_adicionales)
    
    # Formatear tags
    tags_str = ' '.join([f'#{t}' for t in tags_totales])
    
    return f"- [ ] {recomendacion} {tags_str}"

def agregar_tareas_a_archivo(recomendaciones: List[dict], archivo_tareas: str, interactivo: bool = False):
    """
    Agrega recomendaciones como tareas a un archivo.
    
    :param recomendaciones: Lista de recomendaciones a convertir
    :param archivo_tareas: Ruta del archivo de tareas
    :param interactivo: Modo interactivo para confirmación y edición
    """
    with open(archivo_tareas, 'a', encoding='utf-8') as f:
        for rec in recomendaciones:
            # Verificar si la tarea ya existe
            if tarea_existe(archivo_tareas, rec['recomendacion']):
                print(f"\nLa tarea ya existe, omitiendo: {rec['recomendacion']}")
                continue
            
            print(f"\nRecomendación para convertir a tarea:")
            print(f"Texto: {rec['recomendacion']}")
            print(f"Tag base: {rec['tag']}")
            
            if interactivo:
                # Modo interactivo: preguntar confirmación y posibles tags
                respuesta = input("¿Quieres añadir esta tarea? (s/n): ").lower()
                if respuesta != 's':
                    continue
                
                tags_input = input("Tags adicionales (separados por espacios, enter para omitir): ").strip()
                tags_adicionales = tags_input.split() if tags_input else None
                
                tarea_editable = crear_tarea(rec['recomendacion'], rec['tag'], tags_adicionales)
                tarea_final = input("Edita la tarea si lo deseas (o presiona enter para mantener): ") or tarea_editable
            else:
                # Modo automático
                tarea_final = crear_tarea(rec['recomendacion'], rec['tag'])
            
            f.write(tarea_final + '\n')
            print(f"Tarea añadida: {tarea_final}")

def main():
    parser = argparse.ArgumentParser(description='Convertir recomendaciones de Markdown a tareas de Obsidian')
    parser.add_argument('directorio', help='Directorio con archivos de recomendaciones')
    parser.add_argument('--interactivo', action='store_true', help='Modo interactivo para añadir tareas')
    parser.add_argument('--archivo-tareas', 
                        default='/mnt/windows/FTP/wiki/Obsidian/Important/Tareas.md', 
                        help='Ruta del archivo de tareas')
    
    args = parser.parse_args()
    
    try:
        recomendaciones = leer_recomendaciones(args.directorio)
        if not recomendaciones:
            print("No se encontraron recomendaciones.")
            return
        
        agregar_tareas_a_archivo(recomendaciones, args.archivo_tareas, args.interactivo)
    
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()