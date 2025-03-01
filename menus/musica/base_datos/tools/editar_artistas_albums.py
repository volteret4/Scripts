#!/usr/bin/env python
#
# Script Name: editar_artistas_albums.py
# Description: Modifica artistas y álbumes de la base de datos
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# TODO: 
# Notes:
#   Dependencies:  - python3, 
#

#   USO

# Listar artistas (para ver cuáles necesitan corrección):
# python music_db_corrector.py --db tu_base_de_datos.db list-artists

# Listar artistas con un patrón de búsqueda:
# python music_db_corrector.py --db tu_base_de_datos.db list-artists --pattern "Betle"

# Corregir nombre de un artista:
# python music_db_corrector.py --db tu_base_de_datos.db artist --old "The Betle" --new "The Beatles"

# Listar álbumes de un artista específico:
# python music_db_corrector.py --db tu_base_de_datos.db list-albums --artist "The Beatles"

# Corregir nombre de un álbum:
# python music_db_corrector.py --db tu_base_de_datos.db album --old "Abby Road" --new "Abbey Road" --artist "The Beatles"

# Encontrar artistas similares:
# python music_db_corrector.py --db tu_base_de_datos.db find-similar

# Fusionar dos artistas (manteniendo el primero):
# python music_db_corrector.py --db tu_base_de_datos.db merge --keep "The Beatles" --merge "The Beattles"

# Listar todos los artistas para buscar duplicados manualmente:
# python music_db_corrector.py --db tu_base_de_datos.db list-artists

# Buscar artistas con un patrón específico:
# python music_db_corrector.py --db tu_base_de_datos.db list-artists --pattern "Beat"

import sqlite3
import argparse
from datetime import datetime

def connect_to_database(db_path):
    """Conecta a la base de datos SQLite."""
    try:
        conn = sqlite3.connect(db_path)
        return conn
    except sqlite3.Error as e:
        print(f"Error al conectar a la base de datos: {e}")
        return None

def correct_artist_name(conn, old_name, new_name):
    """Corrige el nombre de un artista en todas las tablas relevantes."""
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        # Actualizar en la tabla artists
        cursor.execute("UPDATE artists SET name = ?, last_updated = ? WHERE name = ?", 
                     (new_name, timestamp, old_name))
        artists_updated = cursor.rowcount
        
        # Actualizar en la tabla songs (campo artist)
        cursor.execute("UPDATE songs SET artist = ? WHERE artist = ?", 
                     (new_name, old_name))
        songs_artist_updated = cursor.rowcount
        
        # Actualizar en la tabla songs (campo album_artist)
        cursor.execute("UPDATE songs SET album_artist = ? WHERE album_artist = ?", 
                     (new_name, old_name))
        songs_album_artist_updated = cursor.rowcount
        
        conn.commit()
        
        print(f"Nombre de artista actualizado de '{old_name}' a '{new_name}':")
        print(f"- {artists_updated} registros actualizados en la tabla 'artists'")
        print(f"- {songs_artist_updated} registros actualizados en el campo 'artist' de la tabla 'songs'")
        print(f"- {songs_album_artist_updated} registros actualizados en el campo 'album_artist' de la tabla 'songs'")
        
        return True
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error al actualizar el nombre del artista: {e}")
        return False

def correct_album_name(conn, old_name, new_name, artist_name=None):
    """Corrige el nombre de un álbum en todas las tablas relevantes."""
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        if artist_name:
            # Actualizar en la tabla albums con el nombre del artista especificado
            cursor.execute("""
                UPDATE albums SET name = ?, last_updated = ? 
                WHERE name = ? AND artist_id IN (SELECT id FROM artists WHERE name = ?)
                """, (new_name, timestamp, old_name, artist_name))
            
            # Actualizar en la tabla songs con el nombre del artista especificado
            cursor.execute("""
                UPDATE songs SET album = ? 
                WHERE album = ? AND (artist = ? OR album_artist = ?)
                """, (new_name, old_name, artist_name, artist_name))
        else:
            # Actualizar en la tabla albums sin especificar el artista
            cursor.execute("UPDATE albums SET name = ?, last_updated = ? WHERE name = ?", 
                         (new_name, timestamp, old_name))
            
            # Actualizar en la tabla songs sin especificar el artista
            cursor.execute("UPDATE songs SET album = ? WHERE album = ?", 
                         (new_name, old_name))
        
        albums_updated = cursor.rowcount
        conn.commit()
        
        print(f"Nombre de álbum actualizado de '{old_name}' a '{new_name}':")
        if artist_name:
            print(f"- Solo para el artista: '{artist_name}'")
        print(f"- {albums_updated} registros actualizados")
        
        return True
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error al actualizar el nombre del álbum: {e}")
        return False

def list_artists(conn, pattern=None):
    """Lista todos los artistas que coinciden con un patrón opcional."""
    cursor = conn.cursor()
    
    try:
        if pattern:
            cursor.execute("SELECT id, name FROM artists WHERE name LIKE ? ORDER BY name", (f"%{pattern}%",))
        else:
            cursor.execute("SELECT id, name FROM artists ORDER BY name")
        
        artists = cursor.fetchall()
        
        if artists:
            print("\nArtistas encontrados:")
            for artist_id, name in artists:
                print(f"ID: {artist_id}, Nombre: {name}")
        else:
            print("No se encontraron artistas.")
            
    except sqlite3.Error as e:
        print(f"Error al listar artistas: {e}")

def list_albums(conn, pattern=None, artist_name=None):
    """Lista todos los álbumes que coinciden con un patrón opcional y/o un artista específico."""
    cursor = conn.cursor()
    
    try:
        if artist_name and pattern:
            cursor.execute("""
                SELECT a.id, a.name, ar.name 
                FROM albums a 
                JOIN artists ar ON a.artist_id = ar.id 
                WHERE a.name LIKE ? AND ar.name = ? 
                ORDER BY ar.name, a.name
                """, (f"%{pattern}%", artist_name))
        elif artist_name:
            cursor.execute("""
                SELECT a.id, a.name, ar.name 
                FROM albums a 
                JOIN artists ar ON a.artist_id = ar.id 
                WHERE ar.name = ? 
                ORDER BY a.name
                """, (artist_name,))
        elif pattern:
            cursor.execute("""
                SELECT a.id, a.name, ar.name 
                FROM albums a 
                JOIN artists ar ON a.artist_id = ar.id 
                WHERE a.name LIKE ? 
                ORDER BY ar.name, a.name
                """, (f"%{pattern}%",))
        else:
            cursor.execute("""
                SELECT a.id, a.name, ar.name 
                FROM albums a 
                JOIN artists ar ON a.artist_id = ar.id 
                ORDER BY ar.name, a.name
                """)
        
        albums = cursor.fetchall()
        
        if albums:
            print("\nÁlbumes encontrados:")
            for album_id, album_name, artist_name in albums:
                print(f"ID: {album_id}, Álbum: {album_name}, Artista: {artist_name}")
        else:
            print("No se encontraron álbumes.")
            
    except sqlite3.Error as e:
        print(f"Error al listar álbumes: {e}")

def main():
    parser = argparse.ArgumentParser(description='Corregir nombres de artistas y álbumes en la base de datos musical.')
    parser.add_argument('--db', required=True, help='Ruta al archivo de la base de datos SQLite')
    
    subparsers = parser.add_subparsers(dest='command', help='Comandos disponibles')
    
    # Comando para corregir nombres de artistas
    artist_parser = subparsers.add_parser('artist', help='Corregir nombre de artista')
    artist_parser.add_argument('--old', required=True, help='Nombre actual del artista (incorrecto)')
    artist_parser.add_argument('--new', required=True, help='Nuevo nombre del artista (correcto)')
    
    # Comando para corregir nombres de álbumes
    album_parser = subparsers.add_parser('album', help='Corregir nombre de álbum')
    album_parser.add_argument('--old', required=True, help='Nombre actual del álbum (incorrecto)')
    album_parser.add_argument('--new', required=True, help='Nuevo nombre del álbum (correcto)')
    album_parser.add_argument('--artist', help='Nombre del artista (opcional, para limitar la corrección)')
    
    # Comando para listar artistas
    list_artists_parser = subparsers.add_parser('list-artists', help='Listar artistas')
    list_artists_parser.add_argument('--pattern', help='Patrón para filtrar nombres (opcional)')
    
    # Comando para listar álbumes
    list_albums_parser = subparsers.add_parser('list-albums', help='Listar álbumes')
    list_albums_parser.add_argument('--pattern', help='Patrón para filtrar nombres de álbumes (opcional)')
    list_albums_parser.add_argument('--artist', help='Filtrar por nombre de artista (opcional)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    conn = connect_to_database(args.db)
    if not conn:
        return
    
    try:
        if args.command == 'artist':
            correct_artist_name(conn, args.old, args.new)
        elif args.command == 'album':
            correct_album_name(conn, args.old, args.new, args.artist)
        elif args.command == 'list-artists':
            list_artists(conn, args.pattern)
        elif args.command == 'list-albums':
            list_albums(conn, args.pattern, args.artist)
    finally:
        conn.close()

if __name__ == "__main__":
    main()