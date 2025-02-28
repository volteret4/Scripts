import os
import sqlite3
import sys
from datetime import datetime

# Configuración de la base de datos
DB_PATH = "ruta_a_tu_base_de_datos.db"  # Reemplaza con la ruta real a tu base de datos

def conectar_bd():
    """Establece conexión con la base de datos."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"Error al conectar a la base de datos: {e}")
        sys.exit(1)

def obtener_albumes_y_canciones(conn):
    """Obtiene todos los álbumes y sus canciones asociadas."""
    cursor = conn.cursor()
    
    # Consulta para obtener álbumes junto con sus canciones
    query = """
    SELECT a.id as album_id, a.name as album_name, a.artist_id, 
           art.name as artist_name, s.id as song_id, s.file_path
    FROM albums a
    JOIN artists art ON a.artist_id = art.id
    JOIN songs s ON s.album = a.name AND (s.album_artist = art.name OR s.artist = art.name)
    ORDER BY a.id, s.id
    """
    
    cursor.execute(query)
    return cursor.fetchall()

def verificar_albumes(conn):
    """Verifica qué álbumes tienen archivos que ya no existen y los elimina."""
    albumes_a_eliminar = {}
    albumes_y_canciones = obtener_albumes_y_canciones(conn)
    
    # Agrupar canciones por álbum
    album_canciones = {}
    for fila in albumes_y_canciones:
        album_id = fila['album_id']
        if album_id not in album_canciones:
            album_canciones[album_id] = {
                'album_name': fila['album_name'],
                'artist_name': fila['artist_name'],
                'canciones': []
            }
        album_canciones[album_id]['canciones'].append({
            'song_id': fila['song_id'],
            'file_path': fila['file_path']
        })
    
    # Verificar cada álbum
    for album_id, info in album_canciones.items():
        canciones_inexistentes = []
        for cancion in info['canciones']:
            if not os.path.exists(cancion['file_path']):
                canciones_inexistentes.append(cancion['song_id'])
        
        # Si todas las canciones del álbum no existen, marcar álbum para eliminación
        if canciones_inexistentes and len(canciones_inexistentes) == len(info['canciones']):
            albumes_a_eliminar[album_id] = {
                'album_name': info['album_name'],
                'artist_name': info['artist_name'],
                'canciones_ids': canciones_inexistentes
            }
    
    return albumes_a_eliminar

def eliminar_albumes(conn, albumes_a_eliminar):
    """Elimina los álbumes y sus referencias de la base de datos."""
    cursor = conn.cursor()
    
    try:
        for album_id, info in albumes_a_eliminar.items():
            # Iniciar transacción
            conn.execute("BEGIN TRANSACTION")
            
            # Eliminar registros de canciones
            for song_id in info['canciones_ids']:
                # Primero eliminar de lyrics si existe referencia
                cursor.execute("DELETE FROM lyrics WHERE track_id = ?", (song_id,))
                # Eliminar la canción
                cursor.execute("DELETE FROM songs WHERE id = ?", (song_id,))
            
            # Eliminar el álbum
            cursor.execute("DELETE FROM albums WHERE id = ?", (album_id,))
            
            # Confirmar los cambios
            conn.commit()
            print(f"Eliminado: {info['artist_name']} - {info['album_name']} (ID: {album_id})")
            
    except sqlite3.Error as e:
        # Revertir cambios en caso de error
        conn.rollback()
        print(f"Error durante la eliminación: {e}")

def main():
    """Función principal del script."""
    print("=== Verificación de álbumes con archivos inexistentes ===")
    print(f"Fecha de ejecución: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Conectando a la base de datos...")
    
    conn = conectar_bd()
    
    print("Verificando álbumes...")
    albumes_a_eliminar = verificar_albumes(conn)
    
    if not albumes_a_eliminar:
        print("No se encontraron álbumes con archivos inexistentes.")
    else:
        print(f"\nSe encontraron {len(albumes_a_eliminar)} álbumes con archivos inexistentes:")
        for album_id, info in albumes_a_eliminar.items():
            print(f"- {info['artist_name']} - {info['album_name']} (ID: {album_id})")
        
        confirmacion = input("\n¿Desea eliminar estos álbumes de la base de datos? (s/n): ")
        if confirmacion.lower() == 's':
            print("\nEliminando álbumes...")
            eliminar_albumes(conn, albumes_a_eliminar)
            print("\nProceso completado. Se eliminaron los álbumes de la base de datos.")
        else:
            print("\nOperación cancelada. No se realizaron cambios en la base de datos.")
    
    conn.close()

if __name__ == "__main__":
    main()