
#!/usr/bin/env python
#
# Script Name: 2_get_torrents_.py
# Description: 
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# Notes:
#   Dependencies:  - python3, 
# TODO: mostrar tamaño del álbum a descargar
#

import requests
import json
import sys
import os
import argparse
from datetime import datetime
import subprocess

def load_config(config_file):
    """Load configuration from a JSON file."""
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print(f"Configuration loaded from {config_file}")
        return config
    except Exception as e:
        print(f"Error loading configuration file: {e}")
        sys.exit(1)

def buscar_en_lidarr(artista, album, lidarr_url, lidarr_api_key):
    """Busca el artista y álbum en Lidarr para obtener detalles."""
    print(f"Buscando información para '{artista} - {album}' en Lidarr...")
    
    # Primero buscar el artista
    url = f"{lidarr_url}/api/v1/artist/lookup"
    params = {
        "term": artista,
        "apikey": lidarr_api_key
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        resultados_artista = response.json()
        
        if not resultados_artista:
            print(f"No se encontró el artista '{artista}' en Lidarr.")
            return None, None
        
        # Tomar el primer resultado como el artista correcto
        artista_id = resultados_artista[0]["foreignArtistId"]
        
        # Ahora buscar el álbum usando el artista ID
        url = f"{lidarr_url}/api/v1/album/lookup"
        params = {
            "term": f"{artista_id} {album}",
            "apikey": lidarr_api_key
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        resultados_album = response.json()
        
        # Filtrar por álbumes que coincidan mejor con el término de búsqueda
        albums_filtrados = [a for a in resultados_album if album.lower() in a["title"].lower()]
        
        if not albums_filtrados:
            print(f"No se encontró el álbum '{album}' para el artista '{artista}' en Lidarr.")
            return resultados_artista[0], None
        
        return resultados_artista[0], albums_filtrados[0]
        
    except requests.exceptions.RequestException as e:
        print(f"Error al comunicarse con Lidarr: {e}")
        return None, None

def buscar_en_jackett(artista, album, jackett_url, jackett_api_key, indexador="rutracker", solo_flac=False):
    """Busca torrents directamente en Jackett para el artista y álbum, con opción de filtrar por FLAC."""
    print(f"Buscando torrents para '{artista} - {album}' en Jackett ({indexador}){' (solo FLAC)' if solo_flac else ''}...")
    
    url = f"{jackett_url}/api/v2.0/indexers/{indexador}/results/torznab"
    
    # Si queremos solo FLAC, lo añadimos a la búsqueda
    query = f"{artista} {album}"
    if solo_flac:
        query += " flac"
    
    params = {
        "apikey": jackett_api_key,
        "t": "music",
        "cat": "3000", # Categoría de música
        "q": query.replace(" ", "+")
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        # Jackett devuelve XML, pero podemos procesarlo para obtener los enlaces
        xml_response = response.text
        
        # Procesamiento simple de XML para extraer torrents
        resultados = []
        import xml.etree.ElementTree as ET
        
        root = ET.fromstring(xml_response)
        namespace = {"torznab": "http://torznab.com/schemas/2015/feed"}
        
        for item in root.findall(".//item"):
            titulo = item.find("title").text
            enlace = item.find("link").text
            pubDate = item.find("pubDate").text
            
            # Obtener atributos torznab específicos
            size = None
            seeders = None
            for attr in item.findall(".//torznab:attr", namespace):
                if attr.get("name") == "size":
                    size = int(attr.get("value"))
                elif attr.get("name") == "seeders":
                    seeders = int(attr.get("value"))
            
            # Si solo queremos FLAC, verificamos que el título contenga "flac"
            if solo_flac and "flac" not in titulo.lower():
                continue
                
            resultados.append({
                "titulo": titulo,
                "enlace": enlace,
                "fecha": pubDate,
                "tamaño": size,
                "semillas": seeders,
                # Añadir campo para saber si coincide exactamente con el patrón "artista - album"
                "coincidencia_exacta": f"{artista.lower()} - {album.lower()}" in titulo.lower()
            })
        
        return resultados
        
    except requests.exceptions.RequestException as e:
        print(f"Error al comunicarse con Jackett: {e}")
        return []
    except Exception as e:
        print(f"Error al procesar respuesta de Jackett: {e}")
        return []

def formatear_tamaño(bytes):
    """Convierte bytes a formato legible."""
    if bytes is None:
        return "Desconocido"
        
    unidades = ['B', 'KB', 'MB', 'GB', 'TB']
    i = 0
    while bytes >= 1024 and i < len(unidades)-1:
        bytes /= 1024
        i += 1
    return f"{bytes:.2f} {unidades[i]}"

def formatear_resultados(resultados):
    """Formatea los resultados de búsqueda para mostrarlos."""
    if not resultados:
        return "No se encontraron resultados."
    
    # Ordenar primero por coincidencia exacta y luego por número de semillas (descendente)
    resultados_ordenados = sorted(resultados, key=lambda x: (-x.get("coincidencia_exacta", False), -x.get("semillas", 0)))
    
    salida = "Resultados encontrados:\n"
    salida += "-" * 80 + "\n"
    
    for i, res in enumerate(resultados_ordenados, 1):
        # Añadir indicador si es una coincidencia exacta
        match_indicator = " ✓" if res.get("coincidencia_exacta", False) else ""
        salida += f"{i}. {res['titulo']}{match_indicator}\n"
        salida += f"   Enlace: {res['enlace']}\n"
        if res.get("tamaño"):
            salida += f"   Tamaño: {formatear_tamaño(res['tamaño'])}\n"
        if res.get("semillas"):
            salida += f"   Semillas: {res['semillas']}\n"
        if res.get("fecha"):
            salida += f"   Fecha: {res['fecha']}\n"
        salida += "-" * 80 + "\n"
    
    return salida

def leer_json_file(json_file):
    """Lee un archivo JSON con información de discos a buscar."""
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        print(f"Error al leer el archivo JSON: {e}")
        sys.exit(1)

def actualizar_json_file(json_file, discos_descargados):
    """Actualiza el archivo JSON para marcar qué discos se han descargado."""
    try:
        # Leer el archivo actual
        discos = leer_json_file(json_file)
        
        # Actualizar solo los discos que se han descargado
        contador_descargados = 0
        for disco in discos:
            clave = f"{disco.get('artista', '')}-{disco.get('album', '')}"
            if clave in discos_descargados:
                disco['descargado'] = True
                contador_descargados += 1
        
        # Guardar el archivo actualizado
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(discos, f, indent=2, ensure_ascii=False)
        
        print(f"Archivo JSON actualizado. {contador_descargados} discos marcados como descargados.")
        return contador_descargados
    except Exception as e:
        print(f"Error al actualizar el archivo JSON: {e}")
        return 0

def iniciar_script_fondo(num_torrents, output_path, json_file, temp_server_port):
    """Inicia el script y muestra su salida en tiempo real."""
    try:
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '3_servidor_playlist.py')
        
        if not os.path.exists(script_path):
            print("Advertencia: No se encontró el script. Por favor, asegúrate de que '3_servidor_playlist.py' existe.")
            return None
            
        # Ejecutar el script directamente (no en segundo plano)
        cmd = [
            'python3', 
            script_path,
            "--numero-torrents", str(num_torrents),
            "--json-file", json_file,
            "--output-path", output_path,
            "--temp_server_port", str(temp_server_port)
        ]
        
        print(f"Ejecutando script con comando: {' '.join(cmd)}")
        
        # Usar run en lugar de Popen para ver la salida en tiempo real
        return subprocess.run(cmd, check=True)
        
    except Exception as e:
        print(f"Error al iniciar el script: {e}")
        return None


def modo_interactivo(resultados):
    """Permite al usuario elegir cuál de los torrents descargar."""
    if not resultados:
        print("No hay resultados para seleccionar.")
        return None
    
    # Ordenar primero por coincidencia exacta y luego por número de semillas (descendente)
    resultados_ordenados = sorted(resultados, key=lambda x: (-x.get("coincidencia_exacta", False), -x.get("semillas", 0)))
    
    print("\nModo interactivo - Selecciona un torrent para descargar:")
    for i, res in enumerate(resultados_ordenados, 1):
        # Añadir indicador si es una coincidencia exacta
        match_indicator = " ✓" if res.get("coincidencia_exacta", False) else ""
        print(f"{i}. {res['titulo']}{match_indicator} ({formatear_tamaño(res.get('tamaño', 0))}, {res.get('semillas', 0)} semillas)")
    
    while True:
        try:
            seleccion = input("\nIngresa el número del torrent a descargar (o 'q' para salir): ")
            if seleccion.lower() == 'q':
                return None
                
            seleccion = int(seleccion)
            if 1 <= seleccion <= len(resultados_ordenados):
                return resultados_ordenados[seleccion-1]
            else:
                print(f"Por favor, ingresa un número entre 1 y {len(resultados_ordenados)}.")
        except ValueError:
            print("Por favor, ingresa un número válido.")

def modo_automatico(resultados):
    """Elige automáticamente el torrent con preferencia por coincidencia exacta y luego por número de seeders."""
    if not resultados:
        print("No hay resultados disponibles.")
        return None
    
    # Primero buscar coincidencias exactas
    coincidencias_exactas = [r for r in resultados if r.get("coincidencia_exacta", False)]
    
    # Si hay coincidencias exactas, elegir la que tenga más semillas
    if coincidencias_exactas:
        mejor_torrent = sorted(coincidencias_exactas, key=lambda x: x.get("semillas", 0), reverse=True)[0]
        print("Seleccionado torrent con coincidencia exacta de artista-album:")
    else:
        # Si no hay coincidencias exactas, elegir el que tenga más semillas
        mejor_torrent = sorted(resultados, key=lambda x: x.get("semillas", 0), reverse=True)[0]
        print("No hay coincidencias exactas, seleccionando torrent con más semillas:")
    
    print(f"Título: {mejor_torrent['titulo']}")
    print(f"Semillas: {mejor_torrent.get('semillas', 'Desconocido')}")
    print(f"Tamaño: {formatear_tamaño(mejor_torrent.get('tamaño', 0))}")
    
    return mejor_torrent

def descargar_torrent(torrent, carpeta_torrents_temporales):
    """Función para descargar el torrent seleccionado en una carpeta específica."""
    if not torrent:
        print("No se seleccionó ningún torrent para descargar.")
        return None
    
    print(f"\nDescargando torrent: {torrent['titulo']}")
    print(f"Enlace: {torrent['enlace']}")
    
    # Verifica que carpeta_torrents_temporales sea válida
    if not carpeta_torrents_temporales:
        print("ERROR: carpeta_torrents_temporales es None o vacía")
        return None
        
    # Crear carpeta de destino si no existe
    try:
        if not os.path.exists(carpeta_torrents_temporales):
            os.makedirs(carpeta_torrents_temporales)
            print(f"Carpeta creada: {carpeta_torrents_temporales}")
    except Exception as e:
        print(f"ERROR al crear carpeta de torrents: {e}")
        return None
    
    try:
        # Descargar el torrent
        import urllib.request
        nombre_archivo = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_torrent.torrent"
        ruta_archivo = os.path.join(carpeta_torrents_temporales, nombre_archivo)
        print(f"Intentando descargar a: {ruta_archivo}")
        
        # Añadir más información para depurar
        print(f"URL del torrent: {torrent['enlace']}")
        
        # Intentar descargar con más control de errores
        try:
            urllib.request.urlretrieve(torrent['enlace'], ruta_archivo)
            print(f"Torrent descargado como: {ruta_archivo}")
        except Exception as e:
            print(f"ERROR durante la descarga: {e}")
            return None
            
        # Verificar que el archivo realmente existe y tiene tamaño
        if os.path.exists(ruta_archivo):
            tamaño = os.path.getsize(ruta_archivo)
            print(f"Verificado: El archivo existe en {ruta_archivo} (Tamaño: {tamaño} bytes)")
            if tamaño == 0:
                print("ADVERTENCIA: El archivo descargado tiene 0 bytes")
                return None
            return ruta_archivo
        else:
            print(f"ERROR: El archivo no existe en {ruta_archivo} después de la descarga")
            return None
    except Exception as e:
        print(f"Error al descargar el torrent: {e}")
        return None

def copiar_torrents_a_carpeta(torrents_descargados, carpeta_watchfolder):
    """Copia todos los torrents descargados a una carpeta específica."""
    
    print(f"watchfolder: {carpeta_watchfolder}")

    if not torrents_descargados:
        print("No hay torrents para copiar.")
        return
    
    if not carpeta_watchfolder:
        print("Error: No se ha especificado una carpeta de destino.")
        return
    
    # Crear carpeta de destino si no existe
    try:
        if not os.path.exists(carpeta_watchfolder):
            os.makedirs(carpeta_watchfolder)
            print(f"Carpeta creada: {carpeta_watchfolder}")
        elif not os.path.isdir(carpeta_watchfolder):
            print(f"Error: La ruta {carpeta_watchfolder} existe pero no es un directorio.")
            return
        elif not os.access(carpeta_watchfolder, os.W_OK):
            print(f"Error: No tienes permisos de escritura en {carpeta_watchfolder}")
            return
    except Exception as e:
        print(f"Error al crear/verificar la carpeta de destino: {e}")
        return
    
    import shutil
    copiados = 0
    for i, torrent_path in enumerate(torrents_descargados, 1):
        try:
            if os.path.exists(torrent_path):
                nombre_archivo = os.path.basename(torrent_path)
                destino = os.path.join(carpeta_watchfolder, nombre_archivo)
                
                # Verificar si el archivo ya existe en el destino
                if os.path.exists(destino):
                    print(f"[{i}/{len(torrents_descargados)}] El archivo ya existe en el destino: {destino}")
                    # Opcionalmente reemplazar con un archivo renombrado
                    nombre_base, extension = os.path.splitext(nombre_archivo)
                    timestamp = datetime.now().strftime("%H%M%S")
                    nuevo_nombre = f"{nombre_base}_{timestamp}{extension}"
                    destino = os.path.join(carpeta_watchfolder, nuevo_nombre)
                    print(f"Usando nombre alternativo: {nuevo_nombre}")
                
                shutil.copy2(torrent_path, destino)
                copiados += 1
                print(f"[{i}/{len(torrents_descargados)}] Copiado: {nombre_archivo} -> {destino}")
            else:
                print(f"[{i}/{len(torrents_descargados)}] Archivo no encontrado: {torrent_path}")
        except Exception as e:
            print(f"[{i}/{len(torrents_descargados)}] Error al copiar {torrent_path}: {e}")
    
    print(f"Se han copiado {copiados} de {len(torrents_descargados)} torrents a {carpeta_watchfolder}")

def main():
    parser = argparse.ArgumentParser(description='Buscar torrents de música por artista y álbum')
    parser.add_argument('--artista', help='Nombre del artista')
    parser.add_argument('--album', help='Nombre del álbum')
    parser.add_argument('--indexador', default='rutracker', help='Indexador de Jackett a usar (por defecto: rutracker)')
    parser.add_argument('--json-file', help='Archivo JSON con lista de discos a buscar')
    parser.add_argument('--config-file', help='Archivo JSON de configuración')
    parser.add_argument('--flac', action='store_true', help='Filtrar resultados para mostrar solo archivos en formato FLAC')
    parser.add_argument('--modo', choices=['automatico', 'interactivo', 'manual'], default='interactivo', 
                        help='Modo de selección de torrents (automatico, interactivo, manual)')
    parser.add_argument('--carpeta-torrents-temporales', help='Carpeta temporal para los torrents')
    parser.add_argument('--carpeta-descargas-qbitorrent', help='Carpeta descargas de qbitorrent, donde descarga tus cositas')
    parser.add_argument('--carpeta-watchfolder', help='Carpeta vigilada por qbitorrent')
    parser.add_argument('--output-path', help='Carpeta final para las canciones')
    parser.add_argument('--lidarr-url', help='url lidarr')
    parser.add_argument('--lidarr-api-key', help='lidarr api key')
    parser.add_argument('--jackett-url', help='jackett url')
    parser.add_argument('--jackett-api-key', help='jackett api key')
    parser.add_argument('--path-destino', help='Ruta de destino para los archivos')
    parser.add_argument('--temp-server-port', type=int, default=8584, 
                        help='Puerto del servidor (por defecto: 8584)')
    

    args = parser.parse_args()

    # Inicializar torrents_descargados antes de usarlo
    torrents_descargados = []
    # Diccionario para seguir qué discos se han descargado (clave: "artista-album")
    discos_descargados = {}

    # Variables de configuración con valores predeterminados
    config = {
        "path_destino_flac": None,
        "carpeta_watchfolder": None,
        "carpeta_torrents_temporales": None,
        "carpeta_descargas_qbitorrent": None,
        "output_path": None,
        "modo": "interactivo",
        "json_file": None,
        "lidarr_url": None,
        "lidarr_api_key": None,
        "jackett_url": None,
        "jackett_api_key": None,
        "indexador": "rutracker",
        "skip_torrents": False,
        "flac": True,
        "temp_server_port": 8584
    }

    # Primero, cargar configuración desde archivo si se proporciona
    if args.config_file:
        config_file = args.config_file
        config_from_file = load_config(config_file)
        # Actualizar configuración con valores del archivo
        for key, value in config_from_file.items():
            if key in config:
                config[key] = value
        # Imprimimos los valores que estamos ignorando para depuración
        ignored_keys = [key for key in config_from_file if key not in config]
        if ignored_keys:
            print(f"Nota: Ignorando las siguientes claves del archivo de configuración: {', '.join(ignored_keys)}")

    # Después, sobrescribir con argumentos de línea de comandos solo si no son None
    if args.artista is not None:
        config["artista"] = args.artista
    if args.album is not None:
        config["album"] = args.album
    if args.indexador is not None:
        config["indexador"] = args.indexador
    if args.json_file is not None:
        config["json_file"] = args.json_file
    if args.flac:
        config["flac"] = True
    if args.modo is not None:
        config["modo"] = args.modo
    # FIX: Use the correct argument name with hyphens
    if hasattr(args, 'carpeta_torrents_temporales'):
        config["carpeta_torrents_temporales"] = args.carpeta_torrents_temporales
    elif hasattr(args, 'carpeta-torrents-temporales'):
        config["carpeta_torrents_temporales"] = getattr(args, 'carpeta-torrents-temporales')
    if args.carpeta_watchfolder is not None:
        config["carpeta_watchfolder"] = args.carpeta_watchfolder
    if args.carpeta_descargas_qbitorrent is not None:
        config["carpeta_descargas_qbitorrent"] = args.carpeta_descargas_qbitorrent
    if args.output_path is not None:
        config["output_path"] = args.output_path
    if args.lidarr_url is not None:
        config["lidarr_url"] = args.lidarr_url
    if args.lidarr_api_key is not None:
        config["lidarr_api_key"] = args.lidarr_api_key
    if args.jackett_url is not None:
        config["jackett_url"] = args.jackett_url
    if args.jackett_api_key is not None:
        config["jackett_api_key"] = args.jackett_api_key
    if hasattr(args, 'path_destino_flac') and args.path_destino_flac is not None:
        config["path_destino_flac"] = args.path_destino_flac
    if args.temp_server_port is not None:
        config["temp_server_port"] = args.temp_server_port
    
    # Handle command-line parameters that use hyphens in their names
    for arg_name, arg_value in vars(args).items():
        # Convert hyphens to underscores for config dictionary keys
        config_key = arg_name.replace('-', '_')
        if arg_value is not None and config_key in config:
            config[config_key] = arg_value
    
    # Ahora puedes imprimir los valores para depuración
    print("\nDEPURACIÓN - Valores clave:")
    print(f"carpeta_torrents_temporales: {config.get('carpeta_torrents_temporales')}")
    print(f"carpeta_watchfolder: {config.get('carpeta_watchfolder')}")
    print(f"output_path: {config.get('output_path')}")
    print(f"Número de torrents descargados: {len(torrents_descargados)}")

    # Tratar "manual" como sinónimo de "interactivo"
    if config["modo"].lower() == "manual":
        config["modo"] = "interactivo"

    # Verificar si se proporciona la información necesaria
    if not ((config.get("artista") and config.get("album")) or config.get("json_file")):
        print("Debes proporcionar tanto el artista como el álbum, o un archivo JSON con la lista de discos.")
        parser.print_help()
        sys.exit(1)
    
    # Procesamiento según el modo de entrada (argumentos o archivo JSON)
    if config.get("json_file") and not (config.get("artista") and config.get("album")):
        discos = leer_json_file(config["json_file"])
        print(f"Leyendo {len(discos)} discos del archivo JSON.")
        
        for i, disco in enumerate(discos, 1):
            print(f"\n[{i}/{len(discos)}] Procesando: {disco.get('artista', '')} - {disco.get('album', '')}")
            
            # CAMBIO: Aquí verificamos que el disco tenga los campos necesarios
            artista = disco.get('artista', '')
            album = disco.get('album', '')
            
            # Ignora campos extra que no necesita este script
            ignored_fields = [key for key in disco if key not in ['artista', 'album']]
            if ignored_fields:
                print(f"Ignorando campos adicionales en el disco: {', '.join(ignored_fields)}")
            
            if not artista or not album:
                print("Error: Falta información de artista o álbum en el disco.")
                continue
            
            # Saltar descarga de torrents si se especifica en la configuración
            if config.get("skip_torrents", False):
                print("Saltando descarga de torrents según configuración.")
                continue
                
            # Buscar información en Lidarr
            artista_info, album_info = buscar_en_lidarr(artista, album, config["lidarr_url"], config["lidarr_api_key"])
            
            # Si se encontró información en Lidarr, usar esos términos para buscar
            if artista_info and album_info:
                print(f"Información encontrada en Lidarr: {artista_info['artistName']} - {album_info['title']}")
                busqueda_artista = artista_info['artistName']
                busqueda_album = album_info['title']
            else:
                # Usar los términos proporcionados directamente
                busqueda_artista = artista
                busqueda_album = album
            
            # Buscar torrents en Jackett, aplicando filtro FLAC si corresponde
            resultados = buscar_en_jackett(busqueda_artista, busqueda_album, 
                                         config["jackett_url"], config["jackett_api_key"], 
                                         config["indexador"], config["flac"])
            
            # Mostrar resultados
            print(formatear_resultados(resultados))
            
            # Procesar según el modo seleccionado
            if config["modo"].lower() == 'interactivo':
                torrent_seleccionado = modo_interactivo(resultados)
            else:  # modo automático
                torrent_seleccionado = modo_automatico(resultados)
            
            # Descargar torrent si se seleccionó alguno
            if torrent_seleccionado:
                ruta_torrent = descargar_torrent(torrent_seleccionado, config["carpeta_torrents_temporales"])
                if ruta_torrent:
                    # Añadir explícitamente a la lista
                    torrents_descargados.append(ruta_torrent)
                    # Marcar el disco como descargado
                    disco_key = f"{artista}-{album}"
                    discos_descargados[disco_key] = True
                    print(f"Torrent añadido a la lista. Total: {len(torrents_descargados)}")
    
    
    else:
        # Modo con artista y álbum específicos
        artista = config.get("artista")
        album = config.get("album")
        
        # Saltar descarga de torrents si se especifica en la configuración
        if config.get("skip_torrents", False):
            print("Saltando descarga de torrents según configuración.")
            sys.exit(0)
            
        # Buscar información en Lidarr
        artista_info, album_info = buscar_en_lidarr(artista, album, config["lidarr_url"], config["lidarr_api_key"])
        
        # Si se encontró información en Lidarr, usar esos términos para buscar
        if artista_info and album_info:
            print(f"Información encontrada en Lidarr: {artista_info['artistName']} - {album_info['title']} ({album_info.get('releaseDate', '').split('T')[0]})")
            busqueda_artista = artista_info['artistName']
            busqueda_album = album_info['title']
        else:
            # Usar los términos proporcionados directamente
            busqueda_artista = artista
            busqueda_album = album
        
        # Buscar torrents en Jackett, aplicando filtro FLAC si corresponde
        resultados = buscar_en_jackett(busqueda_artista, busqueda_album, 
                                     config["jackett_url"], config["jackett_api_key"], 
                                     config["indexador"], config["flac"])
        
        # Mostrar resultados
        print(formatear_resultados(resultados))
        
        # Procesar según el modo seleccionado
        if config["modo"].lower() == 'interactivo':
            torrent_seleccionado = modo_interactivo(resultados)
        else:  # modo automático
            torrent_seleccionado = modo_automatico(resultados)
        
        # Descargar torrent si se seleccionó alguno
        if torrent_seleccionado:
            ruta_torrent = descargar_torrent(torrent_seleccionado, config["carpeta_torrents_temporales"])
            if ruta_torrent:
                torrents_descargados.append(ruta_torrent)
    
    # Mostrar el recuento de torrents descargados
    num_torrents = len(torrents_descargados)
    print(f"\nSe han descargado {num_torrents} torrents.")
    for i, t in enumerate(torrents_descargados, 1):
        print(f"  {i}. {t}")

    
    print(f"torrents descargados {torrents_descargados}")
    # Copiar todos los torrents a la carpeta final
    if torrents_descargados:
        if not config.get("carpeta_watchfolder"):
            print("\nError: No se ha especificado una carpeta final para los torrents.")
            print("Por favor, proporciona el parámetro --carpeta-watchfolder o añádelo a tu archivo de configuración.")
        else:
            print(f"\nCopiando todos los torrents a la carpeta watchfolder: {config['carpeta_watchfolder']}")
            carpeta_watchfolder = config.get('carpeta_watchfolder')
            print(f"timaginas {carpeta_watchfolder}")
            copiar_torrents_a_carpeta(torrents_descargados, carpeta_watchfolder)
    
    # Iniciar script de fondo con el número de torrents descargados
    if config.get("json_file") and num_torrents > 0:
        proceso_fondo = iniciar_script_fondo(num_torrents, config["carpeta_watchfolder"], config["json_file"], config["temp_server_port"])

    # Terminar el script mostrando información del proceso en segundo plano
    if 'proceso_fondo' in locals() and proceso_fondo:
        print("\nEl script principal ha finalizado pero el script de fondo continúa ejecutándose.")
        print(f"PID del script de fondo: {proceso_fondo.pid}")
        print(f"Número de torrents enviados al script de fondo: {num_torrents}")

if __name__ == "__main__":
    main()