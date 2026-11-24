#!/usr/bin/env python3
"""
Script para comparar dos directorios de música usando METADATOS.
Lee las etiquetas de artista y álbum de los archivos de audio.
"""

import os
import sys
from pathlib import Path
from collections import defaultdict

# Intentar importar mutagen
try:
    from mutagen import File as MutagenFile
    from mutagen.flac import FLAC
    from mutagen.mp3 import MP3
    from mutagen.easyid3 import EasyID3
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False
    print("="*70)
    print("ADVERTENCIA: La librería 'mutagen' no está instalada.")
    print("Para instalar: pip install mutagen --break-system-packages")
    print("="*70)
    print()

# Extensiones de audio soportadas
AUDIO_EXTENSIONS = {'.flac', '.mp3', '.m4a', '.aac', '.ogg', '.opus', '.wav', '.wma', '.ape'}

def obtener_metadata(archivo):
    """
    Extrae artista y álbum de los metadatos del archivo.
    Retorna (artista, album, directorio_del_archivo)
    """
    try:
        audio = MutagenFile(archivo, easy=True)
        if audio is None:
            return None, None, None

        # Intentar obtener artista
        artista = None
        for tag in ['artist', 'albumartist', 'ARTIST', 'ALBUMARTIST', 'Artist', 'AlbumArtist']:
            if tag in audio:
                artista = audio[tag]
                if isinstance(artista, list):
                    artista = artista[0] if artista else None
                break

        # Intentar obtener álbum
        album = None
        for tag in ['album', 'ALBUM', 'Album']:
            if tag in audio:
                album = audio[tag]
                if isinstance(album, list):
                    album = album[0] if album else None
                break

        # Si no encontramos metadatos, usar estructura de carpetas como fallback
        if not artista or not album:
            partes = archivo.parent.parts
            if len(partes) >= 2:
                album = partes[-1]  # Carpeta del álbum
                artista = partes[-2]  # Carpeta del artista
            elif len(partes) >= 1:
                album = partes[-1]
                artista = "Artista Desconocido"

        return str(artista).strip() if artista else None, str(album).strip() if album else None, str(archivo.parent)

    except Exception as e:
        # Fallback a estructura de carpetas
        partes = archivo.parent.parts
        if len(partes) >= 2:
            return partes[-2], partes[-1], str(archivo.parent)
        elif len(partes) >= 1:
            return "Artista Desconocido", partes[-1], str(archivo.parent)
        return None, None, None

def escanear_directorio(directorio):
    """
    Escanea un directorio y agrupa archivos por Artista - Álbum usando metadatos.
    Retorna:
    - albumes: dict con clave "Artista - Álbum" y valor = lista de rutas de archivos
    - albumes_dirs: dict con clave "Artista - Álbum" y valor = set de directorios donde se encontró
    """
    directorio = Path(directorio).resolve()
    albumes = defaultdict(list)
    albumes_dirs = defaultdict(set)

    if not directorio.exists():
        print(f"Error: El directorio {directorio} no existe")
        return albumes, albumes_dirs

    print(f"  Escaneando: {directorio}")
    archivos_procesados = 0
    archivos_con_metadata = 0

    # Buscar todos los archivos de audio
    for archivo in directorio.rglob('*'):
        if archivo.is_file() and archivo.suffix.lower() in AUDIO_EXTENSIONS:
            archivos_procesados += 1

            if MUTAGEN_AVAILABLE:
                artista, album, dir_album = obtener_metadata(archivo)
            else:
                # Fallback sin mutagen
                partes = archivo.parent.parts
                if len(partes) >= 2:
                    artista, album = partes[-2], partes[-1]
                elif len(partes) >= 1:
                    artista, album = "Artista Desconocido", partes[-1]
                else:
                    artista, album = "Desconocido", "Desconocido"
                dir_album = str(archivo.parent)

            if artista and album:
                clave = f"{artista} - {album}"
                albumes[clave].append(str(archivo))
                albumes_dirs[clave].add(dir_album)
                archivos_con_metadata += 1

            # Mostrar progreso cada 100 archivos
            if archivos_procesados % 100 == 0:
                print(f"    Procesados: {archivos_procesados} archivos...", end='\r')

    print(f"    Procesados: {archivos_procesados} archivos - {len(albumes)} álbumes únicos")
    if MUTAGEN_AVAILABLE:
        print(f"    Con metadatos: {archivos_con_metadata}/{archivos_procesados}")

    return albumes, albumes_dirs

def normalizar_nombre(nombre):
    """Normaliza nombres para comparación más flexible"""
    import unicodedata
    # Remover acentos
    nombre = unicodedata.normalize('NFD', nombre)
    nombre = ''.join(char for char in nombre if unicodedata.category(char) != 'Mn')
    # Convertir a minúsculas y limpiar
    nombre = nombre.lower().strip()
    # Remover caracteres especiales comunes
    for char in ['_', '-', '.', ',', ':', ';', '!', '?']:
        nombre = nombre.replace(char, ' ')
    # Normalizar espacios
    nombre = ' '.join(nombre.split())
    return nombre

def comparar_directorios(dir_base, dir_secundario, modo='flexible'):
    """
    Compara dos directorios usando metadatos de archivos de audio.
    """
    print(f"\n{'='*70}")
    print(f"Comparador de Música por Metadatos")
    print(f"{'='*70}")
    print(f"Directorio BASE:       {dir_base}")
    print(f"Directorio SECUNDARIO: {dir_secundario}")
    print(f"Modo de comparación:   {modo}")
    print(f"{'='*70}\n")

    if not MUTAGEN_AVAILABLE:
        print("⚠️  MODO FALLBACK: Sin mutagen, usando estructura de carpetas")
        print("   Instala mutagen para lectura precisa de metadatos:")
        print("   pip install mutagen --break-system-packages\n")

    print("Escaneando directorio BASE...")
    albumes_base, dirs_base = escanear_directorio(dir_base)

    print("\nEscaneando directorio SECUNDARIO...")
    albumes_secundario, dirs_secundario = escanear_directorio(dir_secundario)

    print(f"\n{'='*70}")
    print(f"Álbumes encontrados:")
    print(f"  BASE:       {len(albumes_base)} álbumes únicos")
    print(f"  SECUNDARIO: {len(albumes_secundario)} álbumes únicos")
    print(f"{'='*70}\n")

    # Encontrar álbumes faltantes
    faltantes = []
    posibles_duplicados = []

    if modo == 'estricto':
        # Comparación exacta
        for album_key in sorted(albumes_secundario.keys()):
            if album_key not in albumes_base:
                faltantes.append((album_key, albumes_secundario[album_key], dirs_secundario[album_key]))
    else:
        # Comparación flexible
        # Crear índice normalizado del directorio base
        base_normalizado = {}
        for album_key in albumes_base.keys():
            norm = normalizar_nombre(album_key)
            if norm not in base_normalizado:
                base_normalizado[norm] = []
            base_normalizado[norm].append(album_key)

        # Comparar
        for album_key in sorted(albumes_secundario.keys()):
            norm = normalizar_nombre(album_key)

            if norm in base_normalizado:
                # Posible duplicado con nombre diferente
                if album_key not in albumes_base:
                    posibles_duplicados.append((album_key, base_normalizado[norm]))
            else:
                # Álbum faltante
                faltantes.append((album_key, albumes_secundario[album_key], dirs_secundario[album_key]))

    # Mostrar resultados
    print(f"{'='*70}")
    print(f"ÁLBUMES FALTANTES EN BASE: {len(faltantes)}")
    print(f"{'='*70}\n")

    if faltantes:
        for i, (album, archivos, dirs) in enumerate(faltantes, 1):
            print(f"{i}. {album}")
            print(f"   Archivos: {len(archivos)} en {len(dirs)} ubicación(es)")
            print()
    else:
        print("✓ No faltan álbumes. El directorio base tiene todos los álbumes del secundario.\n")

    # Mostrar posibles duplicados
    if modo == 'flexible' and posibles_duplicados:
        print(f"{'='*70}")
        print(f"POSIBLES DUPLICADOS (nombres diferentes): {len(posibles_duplicados)}")
        print(f"{'='*70}\n")

        for album_sec, albums_base in posibles_duplicados:
            print(f"En SECUNDARIO: {album_sec}")
            print(f"  Posible(s) coincidencia(s) en BASE:")
            for ab in albums_base:
                print(f"    - {ab}")
            print()

    return faltantes, posibles_duplicados

def guardar_resultados(faltantes, dir_secundario, dir_base):
    """Guarda los resultados en archivos"""

    if not faltantes:
        print("No hay álbumes faltantes para guardar.")
        return

    # Archivo con listado simple: Artista - Álbum
    listado_file = Path('albumes_faltantes.txt')
    with open(listado_file, 'w', encoding='utf-8') as f:
        f.write(f"Álbumes en '{dir_secundario}' que faltan en '{dir_base}'\n")
        f.write("="*70 + "\n")
        f.write(f"Total: {len(faltantes)} álbumes\n")
        f.write("="*70 + "\n\n")

        for album, archivos, dirs in sorted(faltantes):
            f.write(f"{album}\n")

    # Archivo con rutas completas de directorios
    rutas_file = Path('rutas_albumes_faltantes.txt')
    with open(rutas_file, 'w', encoding='utf-8') as f:
        f.write(f"# Rutas de álbumes faltantes en '{dir_base}'\n")
        f.write(f"# Total: {len(faltantes)} álbumes\n")
        f.write(f"# Fuente: {dir_secundario}\n")
        f.write("#" + "="*69 + "\n\n")

        for album, archivos, dirs in sorted(faltantes):
            # Si el álbum está en múltiples ubicaciones, listar todas
            for dir_path in sorted(dirs):
                f.write(f"{dir_path}\n")

    print(f"{'='*70}")
    print(f"Archivos generados:")
    print(f"  📄 {listado_file.resolve()}")
    print(f"     (Listado: Artista - Álbum)")
    print(f"  📁 {rutas_file.resolve()}")
    print(f"     (Rutas completas de directorios)")
    print(f"{'='*70}")

def main():
    if len(sys.argv) < 3:
        print("Uso: python comparar_musica.py <directorio_base> <directorio_secundario> [modo]")
        print()
        print("Parámetros:")
        print("  directorio_base:       El directorio principal (tu colección)")
        print("  directorio_secundario: Directorio con posibles álbumes adicionales")
        print("  modo:                  'estricto' o 'flexible' (por defecto: flexible)")
        print()
        print("El script lee los METADATOS (tags ID3, etc.) de los archivos de audio")
        print("para identificar Artista y Álbum, no se basa en la estructura de carpetas.")
        print()
        print("Ejemplo:")
        print("  python comparar_musica.py /music/biblioteca /music/backup flexible")
        print()
        if not MUTAGEN_AVAILABLE:
            print("⚠️  IMPORTANTE: Instala 'mutagen' para lectura de metadatos:")
            print("  pip install mutagen --break-system-packages")
        sys.exit(1)

    dir_base = sys.argv[1]
    dir_secundario = sys.argv[2]
    modo = sys.argv[3] if len(sys.argv) > 3 else 'flexible'

    if modo not in ['estricto', 'flexible']:
        print(f"Error: Modo '{modo}' no válido. Usa 'estricto' o 'flexible'")
        sys.exit(1)

    faltantes, duplicados = comparar_directorios(dir_base, dir_secundario, modo)
    guardar_resultados(faltantes, dir_secundario, dir_base)

if __name__ == "__main__":
    main()
