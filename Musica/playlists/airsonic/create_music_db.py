#!/usr/bin/env python3
"""
Script para crear una base de datos SQLite con información de archivos de música
en el servidor NFS.
"""

import os
import sqlite3
import argparse
from pathlib import Path
from mutagen import File
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from mutagen.id3 import ID3
import sys

def get_metadata(file_path):
    """
    Extrae metadata (artista, álbum, título) de un archivo de audio.
    """
    try:
        audio = File(file_path, easy=True)
        if audio is None:
            return None, None, None

        # Intentar obtener metadata
        artist = audio.get('artist', [None])[0] if audio.get('artist') else None
        album = audio.get('album', [None])[0] if audio.get('album') else None
        title = audio.get('title', [None])[0] if audio.get('title') else None

        # Si easy=True no funciona, intentar con el formato específico
        if not artist and not album and not title:
            audio = File(file_path, easy=False)
            if isinstance(audio, FLAC):
                artist = audio.get('artist', [None])[0] if audio.get('artist') else None
                album = audio.get('album', [None])[0] if audio.get('album') else None
                title = audio.get('title', [None])[0] if audio.get('title') else None

        return artist, album, title
    except Exception as e:
        print(f"Error leyendo metadata de {file_path}: {e}", file=sys.stderr)
        return None, None, None

def create_database(db_path):
    """
    Crea la base de datos SQLite con la estructura necesaria.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS music_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE NOT NULL,
            artist TEXT,
            album TEXT,
            title TEXT,
            filename TEXT
        )
    ''')

    # Crear índices para búsquedas rápidas
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_artist ON music_files(artist)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_album ON music_files(album)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_artist_album ON music_files(artist, album)')

    conn.commit()
    return conn

def scan_directory(directory, conn, base_path, update_mode=False):
    """
    Escanea un directorio recursivamente y añade archivos de música a la base de datos.
    Si update_mode=True, también elimina archivos que ya no existen.
    """
    cursor = conn.cursor()

    # Extensiones de audio soportadas
    audio_extensions = {'.flac', '.mp3', '.m4a', '.ogg', '.opus', '.wav', '.aiff', '.ape', '.wv'}

    total_files = 0
    added_files = 0
    updated_files = 0

    # Si estamos en modo actualización, obtener lista de archivos existentes en BD
    existing_files = set()
    if update_mode:
        print("Obteniendo lista de archivos existentes en la base de datos...")
        cursor.execute('SELECT file_path FROM music_files')
        existing_files = {row[0] for row in cursor.fetchall()}
        print(f"Base de datos contiene {len(existing_files)} archivos")

    print(f"Escaneando directorio: {directory}")

    # Conjunto para rastrear archivos encontrados en el escaneo
    scanned_files = set()

    for root, dirs, files in os.walk(directory):
        # Filtrar directorios ocultos
        dirs[:] = [d for d in dirs if not d.startswith('.')]

        for file in files:
            if any(file.lower().endswith(ext) for ext in audio_extensions):
                total_files += 1
                file_path = os.path.join(root, file)
                scanned_files.add(file_path)

                # Obtener metadata
                artist, album, title = get_metadata(file_path)

                # Insertar o actualizar en la base de datos
                try:
                    if update_mode and file_path in existing_files:
                        # Archivo ya existe, actualizar metadata si es necesario
                        cursor.execute('''
                            UPDATE music_files
                            SET artist = ?, album = ?, title = ?, filename = ?
                            WHERE file_path = ?
                        ''', (artist, album, title, file, file_path))

                        if cursor.rowcount > 0:
                            updated_files += 1
                    else:
                        # Archivo nuevo, insertar
                        cursor.execute('''
                            INSERT OR IGNORE INTO music_files (file_path, artist, album, title, filename)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (file_path, artist, album, title, file))

                        if cursor.rowcount > 0:
                            added_files += 1

                    if (added_files + updated_files) % 100 == 0:
                        print(f"Procesados: {total_files}, añadidos: {added_files}, actualizados: {updated_files}", end='\r')
                        conn.commit()

                except sqlite3.IntegrityError:
                    pass  # El archivo ya existe y no se pudo añadir

    conn.commit()

    # Si estamos en modo actualización, eliminar archivos que ya no existen
    deleted_files = 0
    if update_mode:
        print(f"\n\nBuscando archivos eliminados...")
        files_to_delete = existing_files - scanned_files

        if files_to_delete:
            print(f"Eliminando {len(files_to_delete)} archivos que ya no existen...")
            for file_path in files_to_delete:
                cursor.execute('DELETE FROM music_files WHERE file_path = ?', (file_path,))
                deleted_files += 1

                if deleted_files % 100 == 0:
                    print(f"Eliminados: {deleted_files}/{len(files_to_delete)}", end='\r')
                    conn.commit()

            conn.commit()
            print(f"\nEliminados: {deleted_files} archivos")

    print(f"\n{'='*50}")
    print(f"Total procesados: {total_files} archivos")
    print(f"Añadidos a la base de datos: {added_files} archivos")
    if update_mode:
        print(f"Actualizados en la base de datos: {updated_files} archivos")
        print(f"Eliminados de la base de datos: {deleted_files} archivos")
    print(f"{'='*50}")

    return total_files, added_files, updated_files, deleted_files

def main():
    parser = argparse.ArgumentParser(
        description='Crea una base de datos SQLite con información de archivos de música del servidor NFS.'
    )
    parser.add_argument(
        '--music-dir',
        required=True,
        help='Directorio raíz de la música en el servidor NFS (ej: /mnt/NFS/moode/moode/)'
    )
    parser.add_argument(
        '--db',
        default='music_database.db',
        help='Ruta de la base de datos SQLite (por defecto: music_database.db)'
    )
    parser.add_argument(
        '--update',
        action='store_true',
        help='Actualizar base de datos existente (añade nuevos archivos, actualiza metadata, elimina archivos que ya no existen)'
    )

    args = parser.parse_args()

    # Verificar que el directorio existe
    if not os.path.isdir(args.music_dir):
        print(f"Error: El directorio {args.music_dir} no existe", file=sys.stderr)
        sys.exit(1)

    # Crear o actualizar la base de datos
    db_exists = os.path.exists(args.db)

    if not args.update and db_exists:
        response = input(f"La base de datos {args.db} ya existe. ¿Sobrescribir? (s/n): ")
        if response.lower() != 's':
            print("Operación cancelada")
            sys.exit(0)
        os.remove(args.db)
        db_exists = False

    if args.update and not db_exists:
        print(f"Modo --update especificado pero la base de datos {args.db} no existe.")
        print("Creando nueva base de datos...")
        args.update = False

    conn = create_database(args.db)

    # Mostrar modo de operación
    if args.update:
        print(f"\n{'='*60}")
        print("MODO: Actualización de base de datos existente")
        print("- Se añadirán archivos nuevos")
        print("- Se actualizará metadata de archivos existentes")
        print("- Se eliminarán archivos que ya no existen en disco")
        print(f"{'='*60}\n")
    else:
        print(f"\n{'='*60}")
        print("MODO: Creación de nueva base de datos")
        print(f"{'='*60}\n")

    # Escanear el directorio
    total, added, updated, deleted = scan_directory(
        args.music_dir,
        conn,
        args.music_dir,
        update_mode=args.update
    )

    # Mostrar estadísticas finales
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM music_files')
    total_in_db = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM music_files WHERE artist IS NOT NULL AND album IS NOT NULL')
    with_metadata = cursor.fetchone()[0]

    print(f"\n{'='*60}")
    print(f"RESUMEN FINAL")
    print(f"{'='*60}")
    print(f"Base de datos: {args.db}")
    print(f"Total de archivos en la base de datos: {total_in_db}")
    print(f"Archivos con metadata completa: {with_metadata} ({with_metadata*100//total_in_db if total_in_db > 0 else 0}%)")
    if args.update:
        print(f"\nCambios en esta actualización:")
        print(f"  - Archivos nuevos añadidos: {added}")
        print(f"  - Archivos actualizados: {updated}")
        print(f"  - Archivos eliminados: {deleted}")
    print(f"{'='*60}")

    conn.close()

if __name__ == '__main__':
    main()
