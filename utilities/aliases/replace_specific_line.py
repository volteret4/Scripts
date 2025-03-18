import os
import sys
import difflib
import argparse

def obtener_contexto(contenido, posicion, lineas=3):
    """Obtiene el contexto de líneas alrededor de una posición."""
    lineas_contenido = contenido.splitlines()
    linea_actual = contenido[:posicion].count('\n')
    
    inicio = max(0, linea_actual - lineas)
    fin = min(len(lineas_contenido), linea_actual + lineas + 1)
    
    return lineas_contenido[inicio:fin], inicio


def modificar_archivos(ruta_directorio, cadena_buscar, cadena_reemplazar, modo):
    archivos_modificados = []
    total_coincidencias = 0
    archivos_procesados = 0
    
    print(f"Buscando archivos en: {ruta_directorio}")
    
    # Recorrer todos los archivos y subdirectorios
    for directorio_actual, carpetas, archivos in os.walk(ruta_directorio):
        for archivo in archivos:
            ruta_archivo = os.path.join(directorio_actual, archivo)
            
            # Verificar si debemos procesar este archivo
            # Incluir todos los archivos, sin filtrar por extensión
            try:
                # Leer el contenido del archivo
                with open(ruta_archivo, 'r', encoding='utf-8') as f:
                    try:
                        contenido = f.read()
                        archivos_procesados += 1
                    except UnicodeDecodeError:
                        # Si hay error de codificación, probablemente no es un archivo de texto
                        continue
            except Exception as e:
                # Si hay error al abrir, saltamos este archivo
                continue
            
            # Verificar si hay coincidencias
            if cadena_buscar in contenido:
                coincidencias_en_archivo = contenido.count(cadena_buscar)
                total_coincidencias += coincidencias_en_archivo
                
                # Modo interactivo
                if modo == "interactivo":
                    print(f"\nArchivo: {ruta_archivo}")
                    print(f"Contiene {coincidencias_en_archivo} coincidencia(s).")
                    
                    # Mostrar contexto para cada coincidencia
                    posicion_inicio = 0
                    for i in range(coincidencias_en_archivo):
                        posicion = contenido.find(cadena_buscar, posicion_inicio)
                        if posicion == -1:
                            break
                            
                        contexto, num_linea_inicio = obtener_contexto(contenido, posicion)
                        
                        print(f"\nCoincidencia {i+1}/{coincidencias_en_archivo}:")
                        print(f"Líneas {num_linea_inicio+1}-{num_linea_inicio+len(contexto)}:")
                        print("-" * 50)
                        
                        for j, linea in enumerate(contexto):
                            num_linea = num_linea_inicio + j + 1
                            # Marcar la línea que contiene la coincidencia
                            if cadena_buscar in linea:
                                print(f"{num_linea:4d} >>> {linea}")
                            else:
                                print(f"{num_linea:4d}     {linea}")
                        
                        print("-" * 50)
                        posicion_inicio = posicion + len(cadena_buscar)
                    
                    respuesta = input(f"¿Reemplazar en este archivo? (s/n) [s]: ").lower()
                    if respuesta != 'n':
                        nuevo_contenido = contenido.replace(cadena_buscar, cadena_reemplazar)
                        try:
                            with open(ruta_archivo, 'w', encoding='utf-8') as f:
                                f.write(nuevo_contenido)
                            archivos_modificados.append(ruta_archivo)
                            print(f"Archivo modificado: {ruta_archivo}")
                        except Exception as e:
                            print(f"Error al escribir en {ruta_archivo}: {e}")
                else:
                    # Para el modo auto, solo acumulamos las coincidencias
                    archivos_modificados.append(ruta_archivo)
    
    print(f"\nArchivos procesados: {archivos_procesados}")
    
    # Si estamos en modo auto, preguntar una sola vez al final
    if modo == "auto" and total_coincidencias > 0:
        print(f"\nSe encontraron {total_coincidencias} coincidencias en {len(archivos_modificados)} archivos.")
        respuesta = input(f"¿Reemplazar todas las coincidencias? (s/n) [s]: ").lower()
        
        if respuesta != 'n':
            archivos_realmente_modificados = []
            
            for ruta_archivo in archivos_modificados:
                try:
                    with open(ruta_archivo, 'r', encoding='utf-8') as f:
                        contenido = f.read()
                    
                    nuevo_contenido = contenido.replace(cadena_buscar, cadena_reemplazar)
                    
                    with open(ruta_archivo, 'w', encoding='utf-8') as f:
                        f.write(nuevo_contenido)
                    
                    archivos_realmente_modificados.append(ruta_archivo)
                except Exception as e:
                    print(f"Error al modificar {ruta_archivo}: {e}")
            
            archivos_modificados = archivos_realmente_modificados
        else:
            archivos_modificados = []
    
    return archivos_modificados, total_coincidencias
    
    # Si estamos en modo auto, preguntar una sola vez al final
    if modo == "auto" and total_coincidencias > 0:
        print(f"\nSe encontraron {total_coincidencias} coincidencias en {len(archivos_modificados)} archivos.")
        respuesta = input(f"¿Reemplazar todas las coincidencias? (s/n) [s]: ").lower()
        
        if respuesta != 'n':
            archivos_realmente_modificados = []
            
            for ruta_archivo in archivos_modificados:
                try:
                    with open(ruta_archivo, 'r', encoding='utf-8') as f:
                        contenido = f.read()
                    
                    nuevo_contenido = contenido.replace(cadena_buscar, cadena_reemplazar)
                    
                    with open(ruta_archivo, 'w', encoding='utf-8') as f:
                        f.write(nuevo_contenido)
                    
                    archivos_realmente_modificados.append(ruta_archivo)
                except Exception as e:
                    print(f"Error al modificar {ruta_archivo}: {e}")
            
            archivos_modificados = archivos_realmente_modificados
        else:
            archivos_modificados = []
    
    return archivos_modificados, total_coincidencias

def main():
    parser = argparse.ArgumentParser(description="Script para reemplazar texto en archivos.")
    parser.add_argument("--modo", choices=["interactivo", "auto"], required=True,
                        help="Modo de operación: interactivo para confirmar cada archivo, auto para confirmar todo al final")
    parser.add_argument("--ruta", help="Ruta del directorio donde buscar (opcional)")
    parser.add_argument("--buscar", help="Cadena a buscar (opcional)")
    parser.add_argument("--reemplazar", help="Cadena con que reemplazar (opcional)")
    
    args = parser.parse_args()
    
    # Solicitar los parámetros que no se proporcionaron como argumentos
    ruta_directorio = args.ruta if args.ruta else input("Carpeta donde buscar archivos: ").strip()
    if not os.path.isdir(ruta_directorio):
        print(f"Error: '{ruta_directorio}' no es un directorio válido.")
        return
    
    cadena_buscar = args.buscar if args.buscar else input("Cadena a buscar: ").strip()
    if not cadena_buscar:
        print("Error: La cadena a buscar no puede estar vacía.")
        return
    
    cadena_reemplazar = args.reemplazar if args.reemplazar else input("Cadena con que reemplazar: ").strip()
    
    print(f"\nModo: {args.modo}")
    print(f"Buscando '{cadena_buscar}' para reemplazar con '{cadena_reemplazar}' en '{ruta_directorio}'")
    
    # Llamar a la función para modificar los archivos
    archivos_modificados, total_coincidencias = modificar_archivos(ruta_directorio, cadena_buscar, cadena_reemplazar, args.modo)
    
    # Mostrar resumen
    print("\n" + "=" * 50)
    print(f"RESUMEN:")
    print(f"Se encontraron {total_coincidencias} coincidencias")
    print(f"Se modificaron {len(archivos_modificados)} archivos:")
    
    for ruta in archivos_modificados:
        print(f"  - {ruta}")
    
    print("=" * 50)

if __name__ == "__main__":
    main()