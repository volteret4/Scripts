#!/usr/bin/env python3
"""
Script para convertir playlists m3u locales a playlists m3u que apunten
al servidor NFS, buscando las canciones por artista y álbum.
"""

import os
import sqlite3
import argparse
import json
from pathlib import Path
from mutagen import File
import sys

def read_m3u(m3u_path):
    """
    Lee un archivo m3u y devuelve una lista de rutas de archivos.
    """
    paths = []
    with open(m3u_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Ignorar líneas vacías y comentarios
            if line and not line.startswith('#'):
                paths.append(line)
    return paths

def get_metadata(file_path):
    """
    Extrae metadata (artista, álbum, título) de un archivo de audio.
    """
    try:
        audio = File(file_path, easy=True)
        if audio is None:
            return None, None, None

        artist = audio.get('artist', [None])[0] if audio.get('artist') else None
        album = audio.get('album', [None])[0] if audio.get('album') else None
        title = audio.get('title', [None])[0] if audio.get('title') else None

        return artist, album, title
    except Exception as e:
        print(f"Error leyendo metadata de {file_path}: {e}", file=sys.stderr)
        return None, None, None

def search_in_database(conn, artist, album, title=None):
    """
    Busca un archivo en la base de datos por artista, álbum y opcionalmente título.
    Devuelve la ruta del archivo encontrado o None.
    """
    cursor = conn.cursor()

    # Intentar búsqueda exacta con título
    if title:
        cursor.execute('''
            SELECT file_path FROM music_files
            WHERE artist = ? AND album = ? AND title = ?
            LIMIT 1
        ''', (artist, album, title))
        result = cursor.fetchone()
        if result:
            return result[0]

    # Si no se encontró con título, buscar solo por artista y álbum
    # y tomar el primer resultado
    if artist and album:
        cursor.execute('''
            SELECT file_path FROM music_files
            WHERE artist = ? AND album = ?
            LIMIT 1
        ''', (artist, album))
        result = cursor.fetchone()
        if result:
            return result[0]

    # Búsqueda más flexible (case insensitive)
    if artist and album:
        cursor.execute('''
            SELECT file_path FROM music_files
            WHERE LOWER(artist) = LOWER(?) AND LOWER(album) = LOWER(?)
            LIMIT 1
        ''', (artist, album))
        result = cursor.fetchone()
        if result:
            return result[0]

    return None

def convert_path(nfs_path, nfs_base='/mnt/NFS/moode/moode/', music_prefix='/music/'):
    """
    Convierte una ruta del NFS al formato /music/...
    """
    if nfs_path.startswith(nfs_base):
        relative_path = nfs_path[len(nfs_base):]
        return music_prefix + relative_path
    return nfs_path

def process_m3u(m3u_path, conn, output_dir, nfs_base, music_prefix):
    """
    Procesa un archivo m3u, busca las canciones en la base de datos
    y crea un nuevo m3u con rutas al servidor NFS.
    """
    print(f"\nProcesando: {m3u_path}")

    # Leer el m3u original
    original_paths = read_m3u(m3u_path)

    # Estadísticas
    total = len(original_paths)
    found = 0
    not_found_list = []

    # Lista para el nuevo m3u
    new_paths = []

    for original_path in original_paths:
        # Si la ruta es relativa, hacerla absoluta basada en la ubicación del m3u
        if not os.path.isabs(original_path):
            m3u_dir = os.path.dirname(m3u_path)
            original_path = os.path.normpath(os.path.join(m3u_dir, original_path))

        # Verificar si el archivo existe
        if not os.path.exists(original_path):
            print(f"  ⚠ Archivo no encontrado: {original_path}")
            not_found_list.append({
                'file_path': original_path,
                'reason': 'file_not_found',
                'artist': None,
                'album': None,
                'title': None,
                'filename': os.path.basename(original_path),
                'playlist': os.path.basename(m3u_path)
            })
            continue

        # Obtener metadata
        artist, album, title = get_metadata(original_path)

        if not artist or not album:
            print(f"  ⚠ Sin metadata suficiente: {os.path.basename(original_path)}")
            not_found_list.append({
                'file_path': original_path,
                'reason': 'no_metadata',
                'artist': artist,
                'album': album,
                'title': title,
                'filename': os.path.basename(original_path),
                'playlist': os.path.basename(m3u_path)
            })
            continue

        # Buscar en la base de datos
        nfs_path = search_in_database(conn, artist, album, title)

        if nfs_path:
            # Convertir la ruta al formato /music/...
            music_path = convert_path(nfs_path, nfs_base, music_prefix)
            new_paths.append(music_path)
            found += 1
            print(f"  ✓ {artist} - {album}: {os.path.basename(original_path)}")
        else:
            print(f"  ✗ No encontrado en NFS: {artist} - {album} - {title or 'sin título'}")
            not_found_list.append({
                'file_path': original_path,
                'reason': 'not_in_database',
                'artist': artist,
                'album': album,
                'title': title,
                'filename': os.path.basename(original_path),
                'playlist': os.path.basename(m3u_path)
            })

    # Crear el nuevo m3u
    if new_paths:
        output_path = os.path.join(output_dir, os.path.basename(m3u_path))
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('#EXTM3U\n')
            for path in new_paths:
                f.write(f'{path}\n')

        print(f"\n  📝 Playlist creada: {output_path}")
        print(f"  📊 Encontradas: {found}/{total} ({found*100//total if total > 0 else 0}%)")

        if not_found_list:
            print(f"  ⚠ No encontradas: {len(not_found_list)}")
    else:
        print(f"  ⚠ No se encontraron canciones, no se creó playlist")

    return found, total, not_found_list

def main():
    parser = argparse.ArgumentParser(
        description='Convierte playlists m3u locales a m3u que apunten al servidor NFS.'
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--m3u',
        help='Archivo m3u individual a procesar'
    )
    group.add_argument(
        '--dir',
        help='Directorio con archivos m3u a procesar'
    )

    parser.add_argument(
        '--db',
        default='music_database.db',
        help='Ruta de la base de datos SQLite (por defecto: music_database.db)'
    )
    parser.add_argument(
        '--output',
        required=True,
        help='Directorio donde se crearán las nuevas playlists m3u'
    )
    parser.add_argument(
        '--nfs-base',
        default='/mnt/NFS/moode/moode/',
        help='Ruta base del montaje NFS (por defecto: /mnt/NFS/moode/moode/)'
    )
    parser.add_argument(
        '--music-prefix',
        default='/music/',
        help='Prefijo para las rutas en las nuevas playlists (por defecto: /music/)'
    )

    args = parser.parse_args()

    # Verificar que la base de datos existe
    if not os.path.exists(args.db):
        print(f"Error: La base de datos {args.db} no existe", file=sys.stderr)
        print("Ejecuta primero create_music_db.py para crear la base de datos", file=sys.stderr)
        sys.exit(1)

    # Crear directorio de salida si no existe
    os.makedirs(args.output, exist_ok=True)

    # Conectar a la base de datos
    conn = sqlite3.connect(args.db)

    # Obtener lista de archivos m3u a procesar
    m3u_files = []
    if args.m3u:
        if not os.path.exists(args.m3u):
            print(f"Error: El archivo {args.m3u} no existe", file=sys.stderr)
            sys.exit(1)
        m3u_files.append(args.m3u)
    elif args.dir:
        if not os.path.isdir(args.dir):
            print(f"Error: El directorio {args.dir} no existe", file=sys.stderr)
            sys.exit(1)
        m3u_files = [
            os.path.join(args.dir, f)
            for f in os.listdir(args.dir)
            if f.lower().endswith('.m3u')
        ]

    if not m3u_files:
        print("No se encontraron archivos m3u para procesar", file=sys.stderr)
        sys.exit(1)

    print(f"{'='*60}")
    print(f"Procesando {len(m3u_files)} playlist(s)")
    print(f"Base de datos: {args.db}")
    print(f"Directorio de salida: {args.output}")
    print(f"{'='*60}")

    # Procesar cada m3u
    total_found = 0
    total_tracks = 0
    all_not_found = []

    for m3u_file in m3u_files:
        found, total, not_found = process_m3u(
            m3u_file, conn, args.output, args.nfs_base, args.music_prefix
        )
        total_found += found
        total_tracks += total
        all_not_found.extend(not_found)

    # Guardar JSON con canciones no encontradas
    if all_not_found:
        json_path = os.path.join(args.output, 'not_found.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(all_not_found, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Guardado archivo con canciones no encontradas: {json_path}")
        print(f"   Usa search_missing.py para buscar manualmente estas canciones")

    # Resumen final
    print(f"\n{'='*60}")
    print(f"RESUMEN FINAL")
    print(f"{'='*60}")
    print(f"Playlists procesadas: {len(m3u_files)}")
    print(f"Canciones encontradas: {total_found}/{total_tracks} ({total_found*100//total_tracks if total_tracks > 0 else 0}%)")
    print(f"Canciones no encontradas: {len(all_not_found)}")

    conn.close()

if __name__ == '__main__':
    main()
