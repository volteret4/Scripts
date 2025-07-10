#!/usr/bin/env python3
# debug_db_queries.py - Script para debuggear las consultas de BD

import sqlite3
import configparser
from pathlib import Path

def debug_database():
    """Debuggear consultas de base de datos"""
    
    # Leer configuración
    config = configparser.ConfigParser()
    config.read('config.ini')
    db_path = config.get('database', 'path')
    
    print(f"🔍 Debug de base de datos: {db_path}")
    print("=" * 50)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. Verificar un artista específico
    cursor.execute("""
        SELECT id, name FROM artists 
        WHERE origen = 'local' 
        ORDER BY name 
        LIMIT 5
    """)
    
    print("📋 Primeros 5 artistas:")
    artists = cursor.fetchall()
    for artist in artists:
        print(f"  {artist['id']}: {artist['name']}")
    
    if not artists:
        print("❌ No se encontraron artistas locales")
        return
    
    # Tomar el primer artista para hacer tests
    test_artist = artists[0]
    print(f"\n🧪 Usando artista de prueba: {test_artist['name']} (ID: {test_artist['id']})")
    
    # 2. Verificar álbumes de este artista
    cursor.execute("""
        SELECT id, name, year, album_art_path, total_tracks
        FROM albums 
        WHERE artist_id = ? AND origen = 'local'
        ORDER BY name
    """, (test_artist['id'],))
    
    albums = cursor.fetchall()
    print(f"\n💿 Álbumes de {test_artist['name']} ({len(albums)} encontrados):")
    for album in albums:
        print(f"  {album['id']}: {album['name']} ({album['year']}) - Art: {album['album_art_path']}")
    
    if albums:
        test_album = albums[0]
        print(f"\n🧪 Usando álbum de prueba: {test_album['name']} (ID: {test_album['id']})")
        
        # 3. Verificar canciones de este álbum (consulta actual - problemática)
        print("\n❌ Consulta ACTUAL (problemática):")
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM songs s
            WHERE s.album = ? AND s.artist = ? AND s.origen = 'local'
        """, (test_album['id'], test_artist['name']))  # ❌ MALO: compara album.id con song.album (texto)
        
        bad_count = cursor.fetchone()['count']
        print(f"  Canciones encontradas (consulta mala): {bad_count}")
        
        # 4. Verificar canciones de este álbum (consulta CORREGIDA)
        print("\n✅ Consulta CORREGIDA:")
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM songs s
            WHERE s.album = ? AND s.artist = ? AND s.origen = 'local'
        """, (test_album['name'], test_artist['name']))  # ✅ BIEN: compara nombres
        
        good_count = cursor.fetchone()['count']
        print(f"  Canciones encontradas (consulta correcta): {good_count}")
        
        # 5. Mostrar algunas canciones para verificar
        cursor.execute("""
            SELECT title, album, artist, file_path, album_art_path_denorm
            FROM songs s
            WHERE s.album = ? AND s.artist = ? AND s.origen = 'local'
            LIMIT 3
        """, (test_album['name'], test_artist['name']))
        
        songs = cursor.fetchall()
        print(f"\n🎵 Canciones de ejemplo:")
        for song in songs:
            print(f"  • {song['title']}")
            print(f"    Álbum en song: '{song['album']}'")
            print(f"    Artista en song: '{song['artist']}'")
            print(f"    Imagen: {song['album_art_path_denorm']}")
            print(f"    Archivo: {song['file_path']}")
            print()
        
        # 6. Verificar si hay discrepancias en nombres
        cursor.execute("""
            SELECT DISTINCT s.album, s.artist
            FROM songs s
            WHERE s.artist LIKE ? AND s.origen = 'local'
            LIMIT 5
        """, (f"%{test_artist['name'][:10]}%",))
        
        song_variations = cursor.fetchall()
        print(f"🔍 Variaciones de nombres en canciones para '{test_artist['name']}':")
        for var in song_variations:
            print(f"  Artista: '{var['artist']}' | Álbum: '{var['album']}'")
    
    # 7. Consulta JOIN corregida para get_artist_details
    print(f"\n🔧 Probando consulta JOIN corregida:")
    cursor.execute("""
        SELECT al.id, al.name, al.year, al.album_art_path,
               COUNT(s.id) as track_count,
               MIN(s.file_path) as sample_path,
               MIN(s.album_art_path_denorm) as album_art_from_songs
        FROM albums al
        LEFT JOIN songs s ON (al.name = s.album AND s.artist = ? AND s.origen = 'local')
        WHERE al.artist_id = ? AND al.origen = 'local'
        GROUP BY al.id, al.name
        ORDER BY al.year DESC, al.name
    """, (test_artist['name'], test_artist['id']))
    
    corrected_albums = cursor.fetchall()
    print(f"💿 Álbumes con conteo corregido:")
    for album in corrected_albums:
        best_art = album['album_art_path'] or album['album_art_from_songs'] or 'Sin imagen'
        print(f"  {album['name']} ({album['year']}) - {album['track_count']} pistas - Img: {best_art}")
    
    conn.close()
    print("\n✅ Debug completado")

if __name__ == '__main__':
    debug_database()