#!/usr/bin/env python
#
# Script Name: sinc_spotify.py 
# Description: Edita las playlist de moode a un path correcto; crea playlist para spotify leyendo tags
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#
#

import os
from mutagen.flac import FLAC
import sys

def obtener_tags(archivo_nuevo):
    try:
        audiofile = FLAC(archivo_nuevo)
        artista = audiofile.get('artist', [None])[0]
        titulo = audiofile.get('title', [None])[0]
        return artista, titulo
    except Exception as e:
        print(f"No se pudo obtener información de tags para {archivo_nuevo}: {e}")
        return None, None

def procesar_playlist(ruta_playlist, carpeta_destino, carpeta_spotify):
    # Implementa la lógica para obtener los tags del archivo
    # Esta función debería devolver artista y titulo
    # Puedes dejar el cuerpo vacío por ahora o implementarla según tus necesidades
    pass

ruta_playlist = sys.argv[1]
carpeta_origen = '/home/pi/python_venv/spotify/playlist/originales/'
carpeta_destino = '/home/pi/python_venv/spotify/playlist/temporales/'
carpeta_spotify = '/home/pi/python_venv/spotify/playlist/spotify/'

nombre_nuevo_archivo_temporal = os.path.join(carpeta_destino, os.path.basename(ruta_playlist))
nombre_nuevo_archivo_spotify = os.path.join(carpeta_spotify, f"{os.path.basename(ruta_playlist)}.txt")

# Abrir el archivo original y los nuevos archivos
with open(ruta_playlist, 'r') as archivo_original, \
        open(nombre_nuevo_archivo_temporal, 'w') as archivo_nuevo_temporal, \
        open(nombre_nuevo_archivo_spotify, 'w') as archivo_nuevo_spotify:

    lineas = archivo_original.readlines()
    
    for linea in lineas:
        # Reemplazar "USB" por "/media" al inicio de cada línea
        nueva_linea = linea.replace("USB", "/media", 1)

        # Escribir la nueva línea en el archivo temporal
        archivo_nuevo_temporal.write(nueva_linea)

        ruta_archivo = nueva_linea.strip()  # Elimina espacios en blanco y saltos de línea
                
        if os.path.exists(ruta_archivo):
            artista, titulo = obtener_tags(ruta_archivo)
            
            if artista and titulo:
                print(f"Artista: {artista}, Título: {titulo}")
                print(f"Ruta de carpeta Spotify: {carpeta_spotify}")
                
                # Escribir el título y artista en el archivo de Spotify
                archivo_nuevo_spotify.write(f"{titulo} {artista}\n")
            else:
                print(f"No se pudieron obtener los tags para: {ruta_archivo}")
        else:
            print(f"El archivo no existe: {ruta_archivo}")
# Reemplaza 'ruta_a_tu_playlist.txt' con la ruta real de tu playlist
ruta_playlist = sys.argv[1]
# carpeta_origen = '/home/pi/python_venv/spotify/playlist/originales/'
# carpeta_destino = '/home/pi/python_venv/spotify/playlist/temporales/'
# carpeta_spotify = '/home/pi/python_venv/spotify/playlist/spotify/'

# Obtener el nombre del archivo de la ruta de la playlist
nombre_playlist = os.path.basename(ruta_playlist)

# Crear la ruta completa para la carpeta de Spotify con el nombre de la playlist
ruta_carpeta_spotify = os.path.join(carpeta_spotify, nombre_playlist)

procesar_playlist(ruta_playlist, carpeta_destino, carpeta_spotify)