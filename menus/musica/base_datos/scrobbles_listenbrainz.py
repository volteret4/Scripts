#!/usr/bin/env python3
import sqlite3
import requests
import json
import argparse
import datetime
import time
import os
from pathlib import Path

def parse_args():
    parser = argparse.ArgumentParser(description='Obtener listens de ListenBrainz y añadirlos a la base de datos')
    parser.add_argument('--user', type=str, required=True, help='Usuario de ListenBrainz (MusicBrainz ID)')
    parser.add_argument('--token', type=str, required=True, help='Token de ListenBrainz')
    parser.add_argument('--db-path', type=str, required=True, help='Ruta al archivo de base de datos SQLite')
    parser.add_argument('--force-update', action='store_true', help='Forzar actualización completa')
    parser.add_argument('--output-json', type=str, help='Ruta para guardar todos los listens en formato JSON (opcional)')
    parser.add_argument('--debug', action='store_true', help='Usar servidor de desarrollo local')
    return parser.parse_args()

def setup_database(conn):
    """Configura la base de datos con las tablas necesarias para listens"""
    cursor = conn.cursor()
    
    # Crear tabla de listens si no existe
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS listens (
        id INTEGER PRIMARY KEY,
        track_name TEXT NOT NULL,
        album_name TEXT,
        artist_name TEXT NOT NULL,
        timestamp INTEGER NOT NULL,
        listen_date TIMESTAMP NOT NULL,
        listenbrainz_url TEXT,
        song_id INTEGER,
        album_id INTEGER,
        artist_id INTEGER,
        FOREIGN KEY (song_id) REFERENCES songs(id),
        FOREIGN KEY (album_id) REFERENCES albums(id),
        FOREIGN KEY (artist_id) REFERENCES artists(id)
    )
    """)
    
    # Crear índice para búsquedas eficientes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_listens_timestamp ON listens(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_listens_artist ON listens(artist_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_listens_song_id ON listens(song_id)")
    
    # Crear tabla para configuración
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS listenbrainz_config (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        username TEXT,
        last_timestamp INTEGER,
        last_updated TIMESTAMP
    )
    """)
    
    conn.commit()

def get_existing_items(conn):
    """Obtiene los artistas, álbumes y canciones existentes en la base de datos"""
    cursor = conn.cursor()
    
    # Obtener artistas existentes
    cursor.execute("SELECT id, name FROM artists")
    artists_rows = cursor.fetchall()
    artists = {row[1].lower(): row[0] for row in artists_rows}
    
    # Obtener álbumes existentes
    cursor.execute("""
        SELECT a.id, a.name, ar.name, a.artist_id
        FROM albums a 
        JOIN artists ar ON a.artist_id = ar.id
    """)
    albums_rows = cursor.fetchall()
    albums = {(row[1].lower(), row[2].lower()): (row[0], row[3]) for row in albums_rows}
    
    # Obtener canciones existentes
    cursor.execute("""
        SELECT s.id, s.title, s.artist, s.album
        FROM songs s
    """)
    songs_rows = cursor.fetchall()
    songs = {(row[1].lower(), row[2].lower(), row[3].lower() if row[3] else None): row[0] 
             for row in songs_rows}
    
    return artists, albums, songs

def get_last_timestamp(conn):
    """Obtiene el timestamp del último listen procesado desde la tabla de configuración"""
    cursor = conn.cursor()
    cursor.execute("SELECT last_timestamp FROM listenbrainz_config WHERE id = 1")
    result = cursor.fetchone()
    
    if result:
        return result[0]
    return 0

def save_last_timestamp(conn, timestamp, username):
    """Guarda el timestamp del último listen procesado en la tabla de configuración"""
    cursor = conn.cursor()
    
    # Intentar actualizar primero
    cursor.execute("""
        UPDATE listenbrainz_config 
        SET last_timestamp = ?, username = ?, last_updated = datetime('now')
        WHERE id = 1
    """, (timestamp, username))
    
    # Si no se actualizó ninguna fila, insertar
    if cursor.rowcount == 0:
        cursor.execute("""
            INSERT INTO listenbrainz_config (id, username, last_timestamp, last_updated)
            VALUES (1, ?, ?, datetime('now'))
        """, (username, timestamp))
    
    conn.commit()

def get_listenbrainz_listens(username, token, debug=False, min_ts=None, count=100):
    """Obtiene los listens de ListenBrainz para un usuario desde un timestamp específico"""
    all_tracks = []
    root = 'http://localhost:8100' if debug else 'https://api.listenbrainz.org'
    auth_header = {"Authorization": f"Token {token}"}
    
    # Para paginación
    next_min_ts = None
    has_more = True
    
    while has_more:
        # Usar el último timestamp como punto de partida para la siguiente página
        if next_min_ts is not None:
            current_min_ts = next_min_ts
        else:
            current_min_ts = min_ts
        
        params = {
            "count": count,
        }
        
        # Solo agregar min_ts si tenemos un valor
        if current_min_ts:
            params["min_ts"] = current_min_ts
        
        url = f"{root}/1/user/{username}/listens"
        response = requests.get(url, params=params, headers=auth_header)
        
        if response.status_code != 200:
            print(f"Error al obtener listens: {response.status_code}")
            if all_tracks:  # Si hemos obtenido algunos listens, devolvemos lo que tenemos
                break
            else:
                return []
        
        data = response.json()
        
        # Comprobar si hay tracks
        if 'payload' not in data or 'listens' not in data['payload'] or not data['payload']['listens']:
            has_more = False
            break
        
        # Añadir tracks a la lista
        tracks = data['payload']['listens']
        all_tracks.extend(tracks)
        
        print(f"Obtenidos {len(tracks)} listens (total: {len(all_tracks)})")
        
        # Determinar si hay más datos que recuperar
        if len(tracks) < count:
            has_more = False
        else:
            # Obtener el timestamp del último elemento para usar en la siguiente solicitud
            next_min_ts = tracks[-1]['listened_at'] + 1
        
        # Pequeña pausa para no saturar la API
        time.sleep(0.25)
    
    return all_tracks

def process_listens(conn, tracks, existing_artists, existing_albums, existing_songs):
    """Procesa los listens y actualiza la base de datos con los nuevos listens"""
    cursor = conn.cursor()
    processed_count = 0
    linked_count = 0
    unlinked_count = 0
    newest_timestamp = 0
    
    # Verificar si hay listens duplicados
    cursor.execute("SELECT timestamp FROM listens ORDER BY timestamp DESC LIMIT 1")
    last_db_timestamp = cursor.fetchone()
    last_db_timestamp = last_db_timestamp[0] if last_db_timestamp else 0
    
    for track in tracks:
        metadata = track['track_metadata']
        
        # Extraer información del track
        artist_name = metadata['artist_name']
        track_name = metadata['track_name']
        timestamp = track['listened_at']
        listen_date = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        
        # El álbum puede no estar presente
        album_name = metadata.get('release_name', None)
        
        # ListenBrainz no proporciona URLs directas a las pistas como Last.fm
        # Podríamos construir una URL basada en el usuario y timestamp
        listenbrainz_url = None
        
        # Actualizar el timestamp más reciente
        newest_timestamp = max(newest_timestamp, timestamp)
        
        # Verificar si el listen ya existe en la base de datos para evitar duplicados
        cursor.execute("SELECT id FROM listens WHERE timestamp = ? AND artist_name = ? AND track_name = ?", 
                      (timestamp, artist_name, track_name))
        if cursor.fetchone():
            continue  # El listen ya existe, continuamos con el siguiente
        
        # Buscar IDs existentes en la base de datos
        artist_id = existing_artists.get(artist_name.lower())
        album_id = None
        song_id = None
        
        if album_name and (album_name.lower(), artist_name.lower()) in existing_albums:
            album_id, _ = existing_albums.get((album_name.lower(), artist_name.lower()))
        
        song_key = (track_name.lower(), artist_name.lower(), album_name.lower() if album_name else None)
        if song_key in existing_songs:
            song_id = existing_songs.get(song_key)
        
        # Insertar el listen en la tabla
        cursor.execute("""
            INSERT INTO listens 
            (track_name, album_name, artist_name, timestamp, listen_date, listenbrainz_url, song_id, album_id, artist_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (track_name, album_name, artist_name, timestamp, listen_date, listenbrainz_url, song_id, album_id, artist_id))
        
        processed_count += 1
        
        # Contabilizar si se pudo enlazar con la base de datos
        if song_id:
            linked_count += 1
            
            # Actualizar song_links si el song_id existe
            cursor.execute("""
                INSERT OR REPLACE INTO song_links (song_id, listenbrainz_url, links_updated)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(song_id) DO UPDATE SET
                listenbrainz_url = COALESCE(listenbrainz_url, excluded.listenbrainz_url),
                links_updated = excluded.links_updated
            """, (song_id, listenbrainz_url))
        else:
            unlinked_count += 1
    
    conn.commit()
    return processed_count, linked_count, unlinked_count, newest_timestamp

def main():
    args = parse_args()
    
    # Conectar a la base de datos
    conn = sqlite3.connect(args.db_path)
    
    try:
        # Configurar la base de datos
        setup_database(conn)
        
        # Obtener elementos existentes
        existing_artists, existing_albums, existing_songs = get_existing_items(conn)
        print(f"Elementos existentes: {len(existing_artists)} artistas, {len(existing_albums)} álbumes, {len(existing_songs)} canciones")
        
        # Obtener el último timestamp procesado
        from_timestamp = 0 if args.force_update else get_last_timestamp(conn)
        if from_timestamp > 0:
            print(f"Obteniendo listens desde {datetime.datetime.fromtimestamp(from_timestamp).strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print("Obteniendo todos los listens (esto puede tardar)")
        
        # Obtener listens
        tracks = get_listenbrainz_listens(args.user, args.token, args.debug, from_timestamp)
        print(f"Obtenidos {len(tracks)} listens")
        
        # Guardar todos los listens en JSON si se especificó
        if args.output_json and tracks:
            with open(args.output_json, 'w') as f:
                json.dump(tracks, f, indent=2)
            print(f"Guardados todos los listens en {args.output_json}")
        
        # Procesar listens
        if tracks:
            processed, linked, unlinked, newest_timestamp = process_listens(
                conn, tracks, existing_artists, existing_albums, existing_songs
            )
            print(f"Procesados {processed} listens: {linked} enlazados, {unlinked} no enlazados")
            
            # Guardar el timestamp más reciente para la próxima ejecución
            if newest_timestamp > 0:
                save_last_timestamp(conn, newest_timestamp, args.user)
                print(f"Guardado último timestamp: {datetime.datetime.fromtimestamp(newest_timestamp).strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print("No se encontraron nuevos listens para procesar")
        
        # Mostrar estadísticas generales
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM listens")
        total_listens = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM listens WHERE song_id IS NOT NULL")
        matched_listens = cursor.fetchone()[0]
        
        match_percentage = 0
        if total_listens > 0:
            match_percentage = matched_listens/total_listens*100
        
        print(f"Estadísticas generales: {total_listens} listens totales, {matched_listens} enlazados con canciones ({match_percentage:.1f}% de coincidencia)")
    
    finally:
        conn.close()

if __name__ == "__main__":
    main()