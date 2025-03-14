#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse
import glob
from mutagen import File

def check_dependencies():
    """Verifica que las dependencias necesarias estén instaladas."""
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        print("Error: ffmpeg no está instalado. Por favor instálalo antes de continuar.")
        return False
        
    try:
        subprocess.run(['r128gain', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        print("Error: r128gain no está instalado. Por favor instálalo con 'pip install r128gain'.")
        return False
    
    return True

def get_audio_files(directory):
    """Obtiene todos los archivos de audio en el directorio dado."""
    extensions = ['mp3', 'flac', 'ogg', 'm4a', 'wma', 'wav']
    audio_files = []
    
    for ext in extensions:
        pattern = os.path.join(directory, f"**/*.{ext}")
        audio_files.extend(glob.glob(pattern, recursive=True))
        
        # También buscar con extensiones en mayúsculas
        pattern = os.path.join(directory, f"**/*.{ext.upper()}")
        audio_files.extend(glob.glob(pattern, recursive=True))
    
    return audio_files

def needs_replaygain(file_path):
    """Verifica si el archivo necesita procesamiento de ReplayGain."""
    try:
        audio = File(file_path)
        
        # Verificar ReplayGain en diferentes formatos
        if audio is None:
            return False
        
        # Para MP3 (ID3)
        if hasattr(audio, 'tags') and audio.tags:
            for key in audio.tags.keys():
                if 'REPLAYGAIN' in key:
                    return False
        
        # Para FLAC
        if hasattr(audio, '_REPLAYGAIN_TRACK_GAIN'):
            return False
        
        # Para Vorbis (OGG)
        if hasattr(audio, 'get') and callable(audio.get):
            for key in audio:
                if isinstance(key, str) and 'replaygain' in key.lower():
                    return False
        
        return True
    except Exception as e:
        print(f"Error al procesar {file_path}: {e}")
        return False

def process_directory(directory, dry_run=False):
    """Procesa los archivos en el directorio para aplicar ReplayGain."""
    if not os.path.isdir(directory):
        print(f"Error: El directorio {directory} no existe.")
        return
    
    print(f"Escaneando archivos en {directory}...")
    audio_files = get_audio_files(directory)
    print(f"Se encontraron {len(audio_files)} archivos de audio.")
    
    files_to_process = []
    for file_path in audio_files:
        if needs_replaygain(file_path):
            files_to_process.append(file_path)
    
    print(f"Se necesita procesar {len(files_to_process)} archivos.")
    
    if not files_to_process:
        print("No hay archivos para procesar. ¡Todo está al día!")
        return
    
    if dry_run:
        print("Modo de prueba activado. No se realizarán cambios.")
        for file_path in files_to_process:
            print(f"Se procesaría: {file_path}")
        return
    
    # Agrupar archivos por directorio para procesamiento por álbum
    directories = {}
    for file_path in files_to_process:
        dir_path = os.path.dirname(file_path)
        if dir_path not in directories:
            directories[dir_path] = []
        directories[dir_path].append(file_path)
    
    # Procesar cada directorio como un álbum
    for dir_path, files in directories.items():
        print(f"\nProcesando directorio: {dir_path}")
        try:
            cmd = ['r128gain', '-a'] + files
            print(f"Ejecutando: {' '.join(cmd)}")
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            if result.returncode == 0:
                print(f"ReplayGain aplicado exitosamente a {len(files)} archivos.")
            else:
                print(f"Error al aplicar ReplayGain: {result.stderr}")
        except Exception as e:
            print(f"Error al ejecutar r128gain: {e}")

def main():
    parser = argparse.ArgumentParser(description='Escanea archivos de música y aplica ReplayGain.')
    parser.add_argument('directory', help='Directorio para escanear archivos de música')
    parser.add_argument('--dry-run', action='store_true', help='Solo muestra qué archivos serían procesados sin realizar cambios')
    
    args = parser.parse_args()
    
    if not check_dependencies():
        sys.exit(1)
    
    process_directory(args.directory, args.dry_run)

if __name__ == '__main__':
    main()