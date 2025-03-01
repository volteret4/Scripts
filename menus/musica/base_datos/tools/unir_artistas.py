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

def merge_artists(conn, keep_artist, merge_artist):
    """
    Fusiona dos artistas, manteniendo uno y eliminando el otro.
    keep_artist: Nombre del artista que se conservará
    merge_artist: Nombre del artista que se eliminará y fusionará con el primero
    """
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        # Primero, verificar que existan ambos artistas
        cursor.execute("SELECT id FROM artists WHERE name = ?", (keep_artist,))
        keep_artist_data = cursor.fetchone()
        
        cursor.execute("SELECT id FROM artists WHERE name = ?", (merge_artist,))
        merge_artist_data = cursor.fetchone()
        
        if not keep_artist_data:
            print(f"Error: El artista a conservar '{keep_artist}' no existe en la base de datos.")
            return False
            
        if not merge_artist_data:
            print(f"Error: El artista a fusionar '{merge_artist}' no existe en la base de datos.")
            return False
            
        keep_id = keep_artist_data[0]
        merge_id = merge_artist_data[0]
        
        # 1. Actualizar referencias en la tabla songs
        cursor.execute("UPDATE songs SET artist = ? WHERE artist = ?", 
                     (keep_artist, merge_artist))
        songs_artist_updated = cursor.rowcount
        
        cursor.execute("UPDATE songs SET album_artist = ? WHERE album_artist = ?", 
                     (keep_artist, merge_artist))
        songs_album_artist_updated = cursor.rowcount
        
        # 2. Actualizar álbumes del artista que se va a eliminar
        cursor.execute("UPDATE albums SET artist_id = ?, last_updated = ? WHERE artist_id = ?", 
                     (keep_id, timestamp, merge_id))
        albums_updated = cursor.rowcount
        
        # 3. Manejar posibles duplicados de álbumes
        # Identificar álbumes duplicados (mismo nombre pero diferentes artist_id)
        cursor.execute("""
            SELECT a1.id, a2.id, a1.name
            FROM albums a1
            JOIN albums a2 ON a1.name = a2.name
            WHERE a1.artist_id = ? AND a2.artist_id = ?
        """, (keep_id, merge_id))
        
        duplicate_albums = cursor.fetchall()
        
        for keep_album_id, merge_album_id, album_name in duplicate_albums:
            # Actualizar canciones que apuntan al álbum duplicado
            cursor.execute("""
                UPDATE songs 
                SET album_artist = ?
                WHERE album = ? AND (artist = ? OR album_artist = ?)
            """, (keep_artist, album_name, merge_artist, merge_artist))
            
            # Eliminar el álbum duplicado
            cursor.execute("DELETE FROM albums WHERE id = ?", (merge_album_id,))
            print(f"- Álbum duplicado '{album_name}' fusionado")
        
        # 4. Combinar información de artista (bio, tags, etc.) si es necesario
        # Obtener datos de ambos artistas
        cursor.execute("SELECT bio, tags, similar_artists FROM artists WHERE id = ?", (keep_id,))
        keep_artist_info = cursor.fetchone()
        
        cursor.execute("SELECT bio, tags, similar_artists FROM artists WHERE id = ?", (merge_id,))
        merge_artist_info = cursor.fetchone()
        
        # Combinar bio si la del artista principal está vacía y la del artista a fusionar no
        if (keep_artist_info[0] is None or keep_artist_info[0] == '') and merge_artist_info[0]:
            cursor.execute("UPDATE artists SET bio = ? WHERE id = ?", (merge_artist_info[0], keep_id))
            print(f"- Biografía transferida del artista '{merge_artist}' al artista '{keep_artist}'")
        
        # Combinar tags si hay datos útiles
        if merge_artist_info[1]:
            # Si ambos tienen tags, combinarlas evitando duplicados
            if keep_artist_info[1]:
                keep_tags = set(keep_artist_info[1].split(','))
                merge_tags = set(merge_artist_info[1].split(','))
                combined_tags = keep_tags.union(merge_tags)
                new_tags = ','.join(combined_tags)
                cursor.execute("UPDATE artists SET tags = ? WHERE id = ?", (new_tags, keep_id))
                print(f"- Tags combinados de ambos artistas")
            else:
                cursor.execute("UPDATE artists SET tags = ? WHERE id = ?", (merge_artist_info[1], keep_id))
                print(f"- Tags transferidos del artista '{merge_artist}' al artista '{keep_artist}'")
        
        # Actualizar la fecha de la última actualización
        cursor.execute("UPDATE artists SET last_updated = ? WHERE id = ?", (timestamp, keep_id))
        
        # 5. Eliminar el artista que se va a fusionar
        cursor.execute("DELETE FROM artists WHERE id = ?", (merge_id,))
        
        conn.commit()
        
        print(f"\nArtistas fusionados correctamente:")
        print(f"- El artista '{merge_artist}' (ID: {merge_id}) se ha fusionado con '{keep_artist}' (ID: {keep_id})")
        print(f"- {songs_artist_updated} canciones actualizadas en el campo 'artist'")
        print(f"- {songs_album_artist_updated} canciones actualizadas en el campo 'album_artist'")
        print(f"- {albums_updated} álbumes transferidos al artista principal")
        
        return True
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error al fusionar artistas: {e}")
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
            print(f"Total: {len(artists)} artistas")
        else:
            print("No se encontraron artistas.")
            
    except sqlite3.Error as e:
        print(f"Error al listar artistas: {e}")

def find_similar_artists(conn, threshold=80):
    """Encuentra artistas con nombres similares que podrían ser candidatos para fusionar."""
    cursor = conn.cursor()
    
    try:
        # Obtener todos los artistas
        cursor.execute("SELECT id, name FROM artists ORDER BY name")
        artists = cursor.fetchall()
        
        print("\nPosibles artistas duplicados (verificar manualmente):")
        found_duplicates = False
        
        # Esta es una implementación simple. Para bases de datos grandes,
        # se recomendaría usar algoritmos más eficientes o librerías como FuzzyWuzzy
        for i, (id1, name1) in enumerate(artists):
            for id2, name2 in artists[i+1:]:
                # Comparación simple: eliminar espacios, convertir a minúsculas, eliminar acentos
                # Esto es una aproximación muy básica
                norm_name1 = name1.lower().replace(" ", "")
                norm_name2 = name2.lower().replace(" ", "")
                
                # Calcular similitud muy básica
                if norm_name1 == norm_name2:
                    print(f"ID: {id1}, Nombre: {name1} <===> ID: {id2}, Nombre: {name2}")
                    found_duplicates = True
                elif norm_name1 in norm_name2 or norm_name2 in norm_name1:
                    print(f"ID: {id1}, Nombre: {name1} <===> ID: {id2}, Nombre: {name2}")
                    found_duplicates = True
        
        if not found_duplicates:
            print("No se encontraron artistas potencialmente duplicados con este método simple.")
        
        print("\nNota: Para una detección más precisa de duplicados, considera:")
        print("1. Usar la librería 'fuzzywuzzy' para comparaciones de texto más avanzadas")
        print("2. Implementar algoritmos fonéticos como Soundex o Metaphone")
        print("3. Verificar manualmente los resultados antes de fusionar")
            
    except sqlite3.Error as e:
        print(f"Error al buscar artistas similares: {e}")

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
            print(f"Total: {len(albums)} álbumes")
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
    
    # Comando para fusionar artistas
    merge_parser = subparsers.add_parser('merge', help='Fusionar dos artistas')
    merge_parser.add_argument('--keep', required=True, help='Nombre del artista que se conservará')
    merge_parser.add_argument('--merge', required=True, help='Nombre del artista que se fusionará con el primero')
    
    # Comando para encontrar artistas similares
    find_similar_parser = subparsers.add_parser('find-similar', help='Encontrar artistas con nombres similares')
    
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
        elif args.command == 'merge':
            merge_artists(conn, args.keep, args.merge)
        elif args.command == 'find-similar':
            find_similar_artists(conn)
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