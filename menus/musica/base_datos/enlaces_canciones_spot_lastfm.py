import sqlite3
import requests
import base64
import json
import time
from datetime import datetime
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import pylast
import argparse

# Configurar cliente Spotify
def configure_spotify(client_id, client_secret):
    return spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=client_id,
        client_secret=client_secret
    ))

# Configurar cliente Last.fm
def configure_lastfm(api_key, api_secret):
    return pylast.LastFMNetwork(
        api_key=api_key,
        api_secret=api_secret
    )

def crear_tabla_song_links(db_path):
    """Crear una tabla para almacenar los enlaces de las canciones"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS song_links (
        id INTEGER PRIMARY KEY,
        song_id INTEGER UNIQUE,
        spotify_url TEXT,
        spotify_id TEXT,
        lastfm_url TEXT,
        links_updated TIMESTAMP,
        FOREIGN KEY (song_id) REFERENCES songs (id)
    )
    ''')
    
    conn.commit()
    conn.close()

def buscar_en_spotify(sp, titulo, artista, album=None):
    """Buscar una canción en Spotify y devolver su URL"""
    try:
        # Construir una consulta de búsqueda
        query = f"track:{titulo} artist:{artista}"
        if album:
            query += f" album:{album}"
        
        # Realizar la búsqueda
        results = sp.search(q=query, type='track', limit=1)
        
        # Verificar si se encontraron resultados
        if results['tracks']['items']:
            track = results['tracks']['items'][0]
            return {
                'spotify_url': track['external_urls']['spotify'],
                'spotify_id': track['id']
            }
        else:
            # Intentar una búsqueda más simple si no se encontraron resultados
            results = sp.search(q=f"{titulo} {artista}", type='track', limit=1)
            if results['tracks']['items']:
                track = results['tracks']['items'][0]
                return {
                    'spotify_url': track['external_urls']['spotify'],
                    'spotify_id': track['id']
                }
            return None
    except Exception as e:
        print(f"Error al buscar en Spotify: {e}")
        return None

def buscar_en_lastfm(network, titulo, artista):
    """Buscar una canción en Last.fm y devolver su URL"""
    try:
        # Buscar la canción en Last.fm
        track = network.get_track(artista, titulo)
        return track.get_url()
    except Exception as e:
        print(f"Error al buscar en Last.fm: {e}")
        return None

def actualizar_song_links(db_path, sp, network, limit=None):
    """Obtener enlaces para las canciones en la base de datos"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Obtener todas las canciones que no tienen enlaces o que no se han actualizado recientemente
    cursor.execute('''
    SELECT s.id, s.title, s.artist, s.album
    FROM songs s
    LEFT JOIN song_links sl ON s.id = sl.song_id
    WHERE sl.id IS NULL OR sl.links_updated < datetime('now', '-30 day')
    ''')
    
    canciones = cursor.fetchall()
    if limit:
        canciones = canciones[:limit]
    
    total_canciones = len(canciones)
    print(f"Se procesarán {total_canciones} canciones" + (f" (limitado a {limit})" if limit else ""))
    
    for i, (song_id, titulo, artista, album) in enumerate(canciones):
        print(f"Procesando {i+1}/{total_canciones}: {artista} - {titulo}")
        
        # Buscar en Spotify
        spotify_info = buscar_en_spotify(sp, titulo, artista, album)
        spotify_url = spotify_info['spotify_url'] if spotify_info else None
        spotify_id = spotify_info['spotify_id'] if spotify_info else None
        
        # Buscar en Last.fm
        lastfm_url = buscar_en_lastfm(network, titulo, artista)
        
        # Primero verificar si existe un registro para esta canción
        cursor.execute('SELECT id FROM song_links WHERE song_id = ?', (song_id,))
        existing_record = cursor.fetchone()
        
        if existing_record:
            # Actualizar registro existente
            cursor.execute('''
            UPDATE song_links 
            SET spotify_url = ?, 
                spotify_id = ?,
                lastfm_url = ?,
                links_updated = datetime('now')
            WHERE song_id = ?
            ''', (spotify_url, spotify_id, lastfm_url, song_id))
        else:
            # Insertar nuevo registro
            cursor.execute('''
            INSERT INTO song_links (song_id, spotify_url, spotify_id, lastfm_url, links_updated)
            VALUES (?, ?, ?, ?, datetime('now'))
            ''', (song_id, spotify_url, spotify_id, lastfm_url))
        
        conn.commit()
        
        # Pausar brevemente para respetar los límites de tasa de las APIs
        time.sleep(0.5)
    
    conn.close()
    print("Proceso completado.")

def exportar_a_json(db_path):
    """Exportar los datos de canciones con sus enlaces a un archivo JSON"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT 
        s.id, s.title, s.artist, s.album, s.genre, s.date,
        sl.spotify_url, sl.spotify_id, sl.lastfm_url
    FROM songs s
    LEFT JOIN song_links sl ON s.id = sl.song_id
    ''')
    
    rows = cursor.fetchall()
    result = []
    
    for row in rows:
        result.append({
            'id': row['id'],
            'title': row['title'],
            'artist': row['artist'],
            'album': row['album'],
            'genre': row['genre'],
            'year': row['date'],
            'spotify_url': row['spotify_url'],
            'spotify_id': row['spotify_id'],
            'lastfm_url': row['lastfm_url']
        })
    
    conn.close()
    
    with open('songs_links.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)
    
    print(f"Datos exportados a songs_links.json ({len(result)} canciones)")

def obtener_estadisticas(db_path):
    """Obtener estadísticas sobre los enlaces obtenidos"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Total de canciones
    cursor.execute("SELECT COUNT(*) FROM songs")
    total_canciones = cursor.fetchone()[0]
    
    # Canciones con enlaces a Spotify
    cursor.execute("SELECT COUNT(*) FROM song_links WHERE spotify_url IS NOT NULL")
    canciones_spotify = cursor.fetchone()[0]
    
    # Canciones con enlaces a Last.fm
    cursor.execute("SELECT COUNT(*) FROM song_links WHERE lastfm_url IS NOT NULL")
    canciones_lastfm = cursor.fetchone()[0]
    
    # Canciones con ambos enlaces
    cursor.execute("SELECT COUNT(*) FROM song_links WHERE spotify_url IS NOT NULL AND lastfm_url IS NOT NULL")
    canciones_ambos = cursor.fetchone()[0]
    
    # Canciones sin ningún enlace
    cursor.execute('''
    SELECT COUNT(*) FROM songs s
    LEFT JOIN song_links sl ON s.id = sl.song_id
    WHERE sl.spotify_url IS NULL AND sl.lastfm_url IS NULL
    ''')
    canciones_sin_enlaces = cursor.fetchone()[0]
    
    conn.close()
    
    print("\nEstadísticas:")
    print(f"Total de canciones: {total_canciones}")
    print(f"Canciones con enlaces a Spotify: {canciones_spotify} ({canciones_spotify/total_canciones*100:.2f}%)")
    print(f"Canciones con enlaces a Last.fm: {canciones_lastfm} ({canciones_lastfm/total_canciones*100:.2f}%)")
    print(f"Canciones con ambos enlaces: {canciones_ambos} ({canciones_ambos/total_canciones*100:.2f}%)")
    print(f"Canciones sin ningún enlace: {canciones_sin_enlaces} ({canciones_sin_enlaces/total_canciones*100:.2f}%)")

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description='Navegador de música')
    parser.add_argument('db_path', help='Ruta a la base de datos SQLite')
    parser.add_argument('--spotify_client_id', help='Cliente ID de Spotify')
    parser.add_argument('--spotify_client_secret', help='Secret de Spotify')
    parser.add_argument('--lastfm_api_key', help='Clave API de Last.fm')
    parser.add_argument('--lastfm_api_secret', help='Secret de Last.fm')
    parser.add_argument('--limit', type=int, help='Límite de canciones a procesar (opcional)')
    args = parser.parse_args()
    
    # Configuración
    db_path = args.db_path
    
    # Configurar clientes de API
    sp = configure_spotify(args.spotify_client_id, args.spotify_client_secret)
    network = configure_lastfm(args.lastfm_api_key, args.lastfm_api_secret)

    print("Iniciando proceso de obtención de enlaces para canciones...")
    
    # Crear la tabla si no existe
    crear_tabla_song_links(db_path)
    
    # Actualizar los enlaces con el límite opcional
    actualizar_song_links(db_path, sp, network, args.limit)
    
    # Mostrar estadísticas
    obtener_estadisticas(db_path)
    
    # Exportar a JSON
    exportar_a_json(db_path)