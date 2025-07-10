#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import subprocess
import sys
import re
import tempfile
import os

def obtener_tareas_alternativo():
    """
    Obtiene todas las tareas de taskwarrior usando un enfoque alternativo
    que procesa cada tarea individualmente.
    """
    try:
        # Usar una aproximación diferente: obtener IDs y luego detalles por ID
        resultado = subprocess.run(
            ['task', 'status:pending', 'ids'],
            capture_output=True,
            text=True,
            check=True
        )
        
        ids = resultado.stdout.strip().split()
        tareas = []
        
        for id_tarea in ids:
            if not id_tarea.isdigit():
                continue
                
            try:
                # Obtener detalles de cada tarea por separado
                detalle = subprocess.run(
                    ['task', id_tarea, 'export'],
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                try:
                    # Intentar parsear el JSON de cada tarea
                    tarea_json = json.loads(detalle.stdout)
                    # Si devuelve una lista, tomar el primer elemento
                    if isinstance(tarea_json, list) and tarea_json:
                        tareas.append(tarea_json[0])
                    else:
                        tareas.append(tarea_json)
                except json.JSONDecodeError:
                    print(f"Error al procesar la tarea ID {id_tarea}, omitiendo...")
            except subprocess.CalledProcessError:
                print(f"Error al obtener detalles de la tarea ID {id_tarea}, omitiendo...")
        
        return tareas
    
    except subprocess.CalledProcessError as e:
        print(f"Error al obtener los IDs de tareas: {e}")
        return []

def obtener_tareas_con_archivo_temporal():
    """
    Guarda la salida de 'task export' en un archivo temporal y lo procesa
    línea por línea para extraer información de las tareas.
    """
    try:
        # Crear archivo temporal
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
            temp_path = temp_file.name
            
        # Ejecutar task export y guardar en archivo temporal
        subprocess.run(['task', 'export'], stdout=open(temp_path, 'w'), check=True)
            
        # Procesar el archivo manualmente
        tareas = []
        
        with open(temp_path, 'r') as f:
            contenido = f.read()
            
        # Eliminar caracteres de control y formatear correctamente
        contenido = re.sub(r'[\x00-\x1F\x7F]', ' ', contenido)
        
        # Intentar extraer objetos JSON individuales
        try:
            # Primero intentar cargar todo el JSON
            json_data = json.loads(contenido)
            if isinstance(json_data, list):
                return json_data
        except json.JSONDecodeError:
            pass  # Si falla, continuamos con el enfoque alternativo
            
        # Enfoque por expresiones regulares para extraer tareas
        pattern = r'{[^{}]*"uuid"[^{}]*}'
        matches = re.findall(pattern, contenido)
        
        for match in matches:
            try:
                # Limpiar y formatear el JSON
                cleaned = re.sub(r',\s*}', '}', match)
                tarea = json.loads(cleaned)
                tareas.append(tarea)
            except json.JSONDecodeError:
                continue
                
        # Limpiar archivo temporal
        os.unlink(temp_path)
        
        return tareas
            
    except Exception as e:
        print(f"Error al procesar tareas con archivo temporal: {e}")
        return []

def obtener_tareas():
    """
    Intenta obtener las tareas de taskwarrior usando diferentes métodos
    hasta que uno funcione.
    """
    print("Intentando obtener tareas usando la exportación directa...")
    try:
        resultado = subprocess.run(
            ['task', 'export'],
            capture_output=True,
            text=True,
            check=True
        )
        
        try:
            return json.loads(resultado.stdout)
        except json.JSONDecodeError:
            print("Error al decodificar la salida JSON. Intentando método alternativo...")
    except subprocess.CalledProcessError:
        print("Error al ejecutar 'task export'. Intentando método alternativo...")
    
    print("Intentando obtener tareas procesando IDs individuales...")
    tareas = obtener_tareas_alternativo()
    if tareas:
        return tareas
    
    print("Intentando obtener tareas mediante archivo temporal...")
    tareas = obtener_tareas_con_archivo_temporal()
    if tareas:
        return tareas
    
    print("No se pudo obtener las tareas usando ningún método.")
    sys.exit(1)

def normalizar_descripcion(descripcion):
    """Normaliza una descripción para comparación, eliminando espacios extra."""
    return ' '.join(descripcion.split())

def eliminar_duplicados_por_descripcion(tareas):
    """
    Identifica y elimina tareas duplicadas basándose en la descripción normalizada.
    Conserva la tarea más antigua de cada conjunto de duplicados.
    """
    # Agrupar por descripción normalizada
    agrupadas_por_descripcion = {}
    for tarea in tareas:
        if not isinstance(tarea, dict):
            continue
            
        descripcion = tarea.get('description', '')
        if not descripcion:
            continue
            
        desc_norm = normalizar_descripcion(descripcion)
        if desc_norm in agrupadas_por_descripcion:
            agrupadas_por_descripcion[desc_norm].append(tarea)
        else:
            agrupadas_por_descripcion[desc_norm] = [tarea]
    
    # Identificar duplicados para eliminar
    tareas_a_eliminar = []
    duplicados_encontrados = 0
    
    for desc_norm, grupo_tareas in agrupadas_por_descripcion.items():
        if len(grupo_tareas) > 1:
            duplicados_encontrados += len(grupo_tareas) - 1
            descripcion_original = grupo_tareas[0].get('description', 'Desconocida')
            print(f"Descripción duplicada: '{descripcion_original}' ({len(grupo_tareas)} tareas)")
            
            # Ordenar por fecha de entrada (entry) para conservar la más antigua
            grupo_tareas.sort(key=lambda t: t.get('entry', ''))
            
            # Mostrar información sobre la tarea que se conservará
            tarea_conservar = grupo_tareas[0]
            print(f"  Conservando: ID={tarea_conservar.get('id')}, UUID={tarea_conservar.get('uuid')}")
            
            # Añadir todas excepto la primera (más antigua) a la lista de eliminación
            for tarea in grupo_tareas[1:]:
                print(f"  Eliminando: ID={tarea.get('id')}, UUID={tarea.get('uuid')}")
                uuid = tarea.get('uuid')
                if uuid:
                    tareas_a_eliminar.append(uuid)
            
            print("")  # Línea en blanco para separar grupos
    
    print(f"Total de tareas duplicadas encontradas: {duplicados_encontrados}")
    return tareas_a_eliminar

def eliminar_tareas(uuids):
    """Elimina las tareas con los UUIDs proporcionados."""
    eliminadas = 0
    
    for uuid in uuids:
        try:
            print(f"Eliminando tarea con UUID: {uuid}")
            
            # Añadir 'yes' para confirmar automáticamente la eliminación
            proceso = subprocess.Popen(['task', uuid, 'delete'], 
                                     stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE)
            proceso.communicate(input=b'yes\n')
            
            eliminadas += 1
            print(f"  Tarea eliminada correctamente.")
        except Exception as e:
            print(f"  Error al eliminar la tarea {uuid}: {e}")
    
    return eliminadas

def main():
    print("Obteniendo tareas de taskwarrior...")
    try:
        tareas = obtener_tareas()
        print(f"Se encontraron {len(tareas)} tareas en total.")
        
        uuids_a_eliminar = eliminar_duplicados_por_descripcion(tareas)
        
        if not uuids_a_eliminar:
            print("No se encontraron tareas duplicadas.")
            return
        
        print(f"Se encontraron {len(uuids_a_eliminar)} tareas para eliminar.")
        
        # respuesta = input("¿Desea eliminar estas tareas duplicadas? (s/n): ")
        # if respuesta.lower() in ['s', 'si', 'sí', 'y', 'yes']:
        eliminadas = eliminar_tareas(uuids_a_eliminar)
        print(f"Proceso completado. Se eliminaron {eliminadas} tareas duplicadas.")
        # else:
        #     print("Operación cancelada.")
    except Exception as e:
        print(f"Error inesperado: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()