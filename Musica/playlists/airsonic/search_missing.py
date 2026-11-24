#!/usr/bin/env python3
"""
Script interactivo para buscar manualmente canciones que no se encontraron
automáticamente en la base de datos.
"""

import os
import sqlite3
import json
import argparse
import sys
from pathlib import Path

def get_artists(conn):
    """Obtiene lista de artistas de la base de datos."""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT artist FROM music_files
        WHERE artist IS NOT NULL
        ORDER BY artist COLLATE NOCASE
    ''')
    return [row[0] for row in cursor.fetchall()]

def search_artists(conn, query):
    """Busca artistas que coincidan con el query."""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT artist FROM music_files
        WHERE artist LIKE ?
        ORDER BY artist COLLATE NOCASE
    ''', (f'%{query}%',))
    return [row[0] for row in cursor.fetchall()]

def get_albums_by_artist(conn, artist):
    """Obtiene álbumes de un artista."""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT album FROM music_files
        WHERE artist = ? AND album IS NOT NULL
        ORDER BY album COLLATE NOCASE
    ''', (artist,))
    return [row[0] for row in cursor.fetchall()]

def search_albums(conn, query):
    """Busca álbumes que coincidan con el query."""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT artist, album FROM music_files
        WHERE album LIKE ? AND album IS NOT NULL
        ORDER BY artist COLLATE NOCASE, album COLLATE NOCASE
    ''', (f'%{query}%',))
    return cursor.fetchall()

def get_tracklist(conn, artist, album):
    """Obtiene las canciones de un álbum específico."""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT title, file_path, filename FROM music_files
        WHERE artist = ? AND album = ?
        ORDER BY filename
    ''', (artist, album))
    return cursor.fetchall()

def convert_path(nfs_path, nfs_base='/mnt/NFS/moode/moode/', music_prefix='/music/'):
    """Convierte una ruta del NFS al formato /music/..."""
    if nfs_path.startswith(nfs_base):
        relative_path = nfs_path[len(nfs_base):]
        return music_prefix + relative_path
    return nfs_path

def show_menu(options, title="Selecciona una opción:"):
    """Muestra un menú y devuelve la opción seleccionada."""
    print(f"\n{title}")
    print("=" * 60)
    for i, option in enumerate(options, 1):
        print(f"{i}. {option}")
    print("0. Saltar/Cancelar")
    print("=" * 60)

    while True:
        try:
            choice = input("Elige una opción: ").strip()
            if choice == '0':
                return None
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return options[idx]
            print(f"Por favor, elige un número entre 0 y {len(options)}")
        except ValueError:
            print("Por favor, introduce un número válido")
        except KeyboardInterrupt:
            print("\n\nCancelado por el usuario")
            return None

def search_interactive(conn):
    """Búsqueda interactiva en la base de datos."""
    print("\n" + "=" * 60)
    print("BÚSQUEDA MANUAL")
    print("=" * 60)

    search_type = show_menu(
        ["Buscar por artista", "Buscar por álbum"],
        "¿Qué quieres buscar?"
    )

    if not search_type:
        return None

    query = input("\nIntroduce el término de búsqueda: ").strip()
    if not query:
        print("Búsqueda cancelada")
        return None

    if "artista" in search_type:
        # Buscar por artista
        artists = search_artists(conn, query)

        if not artists:
            print(f"\n❌ No se encontraron artistas que coincidan con '{query}'")
            return None

        artist = show_menu(artists, f"Artistas encontrados ({len(artists)}):")
        if not artist:
            return None

        # Mostrar álbumes del artista
        albums = get_albums_by_artist(conn, artist)

        if not albums:
            print(f"\n❌ No se encontraron álbumes para '{artist}'")
            return None

        album = show_menu(albums, f"Álbumes de {artist} ({len(albums)}):")
        if not album:
            return None

    else:
        # Buscar por álbum
        albums = search_albums(conn, query)

        if not albums:
            print(f"\n❌ No se encontraron álbumes que coincidan con '{query}'")
            return None

        album_choices = [f"{artist} - {album}" for artist, album in albums]
        selected = show_menu(album_choices, f"Álbumes encontrados ({len(albums)}):")

        if not selected:
            return None

        # Extraer artista y álbum
        idx = album_choices.index(selected)
        artist, album = albums[idx]

    # Mostrar tracklist
    tracks = get_tracklist(conn, artist, album)

    if not tracks:
        print(f"\n❌ No se encontraron canciones en '{album}' de '{artist}'")
        return None

    track_choices = []
    for title, file_path, filename in tracks:
        display_name = title if title else filename
        track_choices.append((display_name, file_path))

    print(f"\n{'='*60}")
    print(f"Tracklist: {artist} - {album}")
    print(f"{'='*60}")
    for i, (name, _) in enumerate(track_choices, 1):
        print(f"{i}. {name}")
    print("0. Ninguna (saltar)")
    print(f"{'='*60}")

    while True:
        try:
            choice = input("Elige una canción: ").strip()
            if choice == '0':
                return None
            idx = int(choice) - 1
            if 0 <= idx < len(track_choices):
                _, file_path = track_choices[idx]
                return file_path
            print(f"Por favor, elige un número entre 0 y {len(track_choices)}")
        except ValueError:
            print("Por favor, introduce un número válido")
        except KeyboardInterrupt:
            print("\n\nCancelado por el usuario")
            return None

def process_missing_songs(json_path, conn, nfs_base, music_prefix):
    """Procesa las canciones no encontradas una por una."""

    # Leer JSON
    with open(json_path, 'r', encoding='utf-8') as f:
        missing_songs = json.load(f)

    if not missing_songs:
        print("No hay canciones pendientes de búsqueda")
        return

    print(f"\n{'='*60}")
    print(f"CANCIONES NO ENCONTRADAS: {len(missing_songs)}")
    print(f"{'='*60}")

    # Diccionario para guardar coincidencias encontradas
    matches = {}

    for i, song in enumerate(missing_songs, 1):
        print(f"\n[{i}/{len(missing_songs)}]")
        print("=" * 60)
        print(f"Canción: {song['filename']}")
        print(f"Artista: {song.get('artist', 'Desconocido')}")
        print(f"Álbum: {song.get('album', 'Desconocido')}")
        print(f"Título: {song.get('title', 'Desconocido')}")
        print(f"Playlist: {song['playlist']}")
        print(f"Razón: {song['reason']}")

        # Preguntar si quiere buscar
        action = show_menu(
            ["Buscar manualmente", "Saltar esta canción"],
            "¿Qué quieres hacer?"
        )

        if not action or "Saltar" in action:
            continue

        # Búsqueda interactiva
        found_path = search_interactive(conn)

        if found_path:
            # Convertir la ruta
            music_path = convert_path(found_path, nfs_base, music_prefix)

            # Guardar coincidencia
            matches[song['file_path']] = {
                'original': song,
                'found_path': found_path,
                'music_path': music_path
            }

            print(f"\n✅ Coincidencia guardada: {music_path}")

    # Guardar coincidencias
    if matches:
        matches_path = os.path.join(os.path.dirname(json_path), 'manual_matches.json')
        with open(matches_path, 'w', encoding='utf-8') as f:
            json.dump(matches, f, indent=2, ensure_ascii=False)

        print(f"\n{'='*60}")
        print(f"✅ Se encontraron {len(matches)} coincidencias")
        print(f"💾 Guardadas en: {matches_path}")
        print(f"{'='*60}")
    else:
        print(f"\n{'='*60}")
        print("No se encontraron nuevas coincidencias")
        print(f"{'='*60}")

def main():
    parser = argparse.ArgumentParser(
        description='Búsqueda manual interactiva de canciones no encontradas.'
    )
    parser.add_argument(
        '--json',
        required=True,
        help='Archivo JSON con canciones no encontradas (generado por convert_m3u.py)'
    )
    parser.add_argument(
        '--db',
        default='music_database.db',
        help='Ruta de la base de datos SQLite (por defecto: music_database.db)'
    )
    parser.add_argument(
        '--nfs-base',
        default='/mnt/NFS/moode/moode/',
        help='Ruta base del montaje NFS (por defecto: /mnt/NFS/moode/moode/)'
    )
    parser.add_argument(
        '--music-prefix',
        default='/music/',
        help='Prefijo para las rutas en las playlists (por defecto: /music/)'
    )

    args = parser.parse_args()

    # Verificar archivos
    if not os.path.exists(args.json):
        print(f"Error: El archivo JSON {args.json} no existe", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(args.db):
        print(f"Error: La base de datos {args.db} no existe", file=sys.stderr)
        sys.exit(1)

    # Conectar a la base de datos
    conn = sqlite3.connect(args.db)

    # Procesar canciones
    process_missing_songs(args.json, conn, args.nfs_base, args.music_prefix)

    conn.close()

if __name__ == '__main__':
    main()
