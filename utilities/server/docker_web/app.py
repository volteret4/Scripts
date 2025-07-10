#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, render_template, jsonify, request, send_from_directory
import sqlite3
import json
import os
from pathlib import Path
import configparser
import logging
from datetime import datetime
import subprocess
import threading
import time as time_module
import shutil

download_status = {}

class MusicExplorer:
    def __init__(self, config_file='config.ini'):
        self.config = configparser.ConfigParser()
        self.config.read(config_file)
        
        # Solo necesitamos acceso a la base de datos
        self.db_path = self.config.get('database', 'path')
        
        # Directorio de descarga local
        self.download_path = self.config.get('download', 'path', fallback='/downloads')
        
        # Configuración de logging
        log_level = self.config.get('logging', 'level', fallback='INFO')
        log_file = self.config.get('logging', 'file', fallback='/app/logs/music_web.log')
        
        # Crear directorio de logs si no existe
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        os.makedirs(self.download_path, exist_ok=True)
        
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def get_db_connection(self):
        """Obtiene conexión a la base de datos"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except Exception as e:
            self.logger.error(f"Error conectando a la base de datos: {e}")
            return None
    
    def search_artists(self, query, limit=50):
        """Busca artistas por nombre"""
        conn = self.get_db_connection()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT a.id, a.name, a.bio, a.origin, a.formed_year, 
                       a.img, a.wikipedia_content,
                       COUNT(DISTINCT al.id) as album_count,
                       COUNT(DISTINCT s.id) as song_count
                FROM artists a
                LEFT JOIN albums al ON a.id = al.artist_id AND al.origen = 'local'
                LEFT JOIN songs s ON a.id = (
                    SELECT ar2.id FROM artists ar2 WHERE ar2.name = s.artist AND s.origen = 'local'
                )
                WHERE a.name LIKE ? AND a.origen = 'local'
                GROUP BY a.id, a.name
                ORDER BY a.name COLLATE NOCASE
                LIMIT ?
            """, (f'%{query}%', limit))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'id': row['id'],
                    'name': row['name'],
                    'bio': row['bio'],
                    'origin': row['origin'],
                    'formed_year': row['formed_year'],
                    'img': row['img'],
                    'wikipedia_content': row['wikipedia_content'],
                    'album_count': row['album_count'],
                    'song_count': row['song_count']
                })
            
            conn.close()
            return results
        except Exception as e:
            self.logger.error(f"Error buscando artistas: {e}")
            conn.close()
            return []
    
    def get_artist_details(self, artist_id):
        """Obtiene detalles completos de un artista"""
        conn = self.get_db_connection()
        if not conn:
            return None
        
        try:
            # Información del artista
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM artists WHERE id = ? AND origen = 'local'
            """, (artist_id,))
            
            artist = cursor.fetchone()
            if not artist:
                conn.close()
                return None
            
            # Álbumes del artista CON CONTEO CORRECTO DE CANCIONES
            cursor.execute("""
                SELECT al.*, 
                    COUNT(s.id) as track_count,
                    MIN(s.file_path) as sample_path,
                    MIN(s.album_art_path_denorm) as album_art_from_songs
                FROM albums al
                LEFT JOIN songs s ON (al.name = s.album AND s.artist = ? AND s.origen = 'local')
                WHERE al.artist_id = ? AND al.origen = 'local'
                GROUP BY al.id, al.name
                ORDER BY al.year DESC, al.name
            """, (artist['name'], artist_id))
            
            albums = []
            for album_row in cursor.fetchall():
                album_dict = dict(album_row)
                
                # Extraer directorio del álbum si hay sample_path
                if album_dict['sample_path']:
                    song_path = Path(album_dict['sample_path'])
                    album_dict['album_directory'] = str(song_path.parent)
                else:
                    album_dict['album_directory'] = None
                
                # Usar la mejor imagen disponible
                if album_dict['album_art_path']:
                    album_dict['best_album_art'] = album_dict['album_art_path']
                elif album_dict['album_art_from_songs']:
                    album_dict['best_album_art'] = album_dict['album_art_from_songs']
                else:
                    album_dict['best_album_art'] = None
                    
                albums.append(album_dict)
            
            # Canciones populares (por reproducciones)  
            cursor.execute("""
                SELECT s.*, COALESCE(s.reproducciones, 1) as play_count
                FROM songs s
                WHERE s.artist = ? AND s.origen = 'local'
                ORDER BY play_count DESC, s.title
                LIMIT 20
            """, (artist['name'],))
            
            popular_songs = []
            for song_row in cursor.fetchall():
                popular_songs.append(dict(song_row))
            
            conn.close()
            
            return {
                'artist': dict(artist),
                'albums': albums,
                'popular_songs': popular_songs
            }
            
        except Exception as e:
            self.logger.error(f"Error obteniendo detalles del artista: {e}")
            conn.close()
            return None
    
    def get_album_details(self, album_id):
        """Obtiene detalles de un álbum"""
        conn = self.get_db_connection()
        if not conn:
            return None
        
        try:
            cursor = conn.cursor()
            
            # Información del álbum y artista
            cursor.execute("""
                SELECT al.*, ar.name as artist_name, ar.id as artist_id
                FROM albums al
                JOIN artists ar ON al.artist_id = ar.id
                WHERE al.id = ? AND al.origen = 'local'
            """, (album_id,))
            
            album = cursor.fetchone()
            if not album:
                conn.close()
                return None
            
            # Canciones del álbum
            cursor.execute("""
                SELECT s.*
                FROM songs s
                WHERE s.album = ? AND s.artist = ? AND s.origen = 'local'
                ORDER BY s.track_number, s.title
            """, (album['name'], album['artist_name']))
            
            tracks = []
            for track_row in cursor.fetchall():
                tracks.append(dict(track_row))
            
            conn.close()
            
            return {
                'album': dict(album),
                'tracks': tracks
            }
            
        except Exception as e:
            self.logger.error(f"Error obteniendo detalles del álbum: {e}")
            conn.close()
            return None
    
    def get_folder_structure(self, path=""):
        """Obtiene la estructura de carpetas desde la base de datos"""
        conn = self.get_db_connection()
        if not conn:
            return {'error': 'Error de base de datos'}
        
        try:
            cursor = conn.cursor()
            
            # Obtener carpetas únicas desde las rutas de archivos en la BD
            if not path:
                # Nivel raíz: obtener directorios principales de artistas
                cursor.execute("""
                    SELECT DISTINCT 
                        SUBSTR(file_path, 1, INSTR(file_path, '/') - 1) as folder_name,
                        SUBSTR(file_path, 1, INSTR(file_path, '/') - 1) as folder_path
                    FROM songs 
                    WHERE origen = 'local' AND file_path LIKE '%/%'
                    ORDER BY folder_name
                """)
            else:
                # Subdirectorios: buscar dentro del path especificado
                cursor.execute("""
                    SELECT DISTINCT 
                        SUBSTR(SUBSTR(file_path, LENGTH(?) + 2), 1, 
                               INSTR(SUBSTR(file_path, LENGTH(?) + 2), '/') - 1) as folder_name,
                        ? || '/' || SUBSTR(SUBSTR(file_path, LENGTH(?) + 2), 1, 
                                          INSTR(SUBSTR(file_path, LENGTH(?) + 2), '/') - 1) as folder_path
                    FROM songs 
                    WHERE origen = 'local' 
                    AND file_path LIKE ? || '/%'
                    AND LENGTH(SUBSTR(file_path, LENGTH(?) + 2)) > 0
                    AND INSTR(SUBSTR(file_path, LENGTH(?) + 2), '/') > 0
                    ORDER BY folder_name
                """, (path, path, path, path, path, path, path, path))
            
            items = []
            for row in cursor.fetchall():
                if row[0]:  # Solo si hay nombre de carpeta
                    items.append({
                        'name': row[0],
                        'type': 'folder',
                        'path': row[1],
                        'full_path': f"Desde BD: {row[1]}"
                    })
            
            conn.close()
            
            return {
                'current_path': path,
                'items': items,
                'parent_path': str(Path(path).parent) if path and path != '.' else None
            }
            
        except Exception as e:
            self.logger.error(f"Error obteniendo estructura de carpetas: {e}")
            conn.close()
            return {'error': str(e)}

# Crear instancia de la aplicación Flask
app = Flask(__name__)

explorer = MusicExplorer()

@app.route('/')
def index():
    """Página principal"""
    return render_template('index.html')

@app.route('/api/search/artists')
def search_artists():
    """API para buscar artistas"""
    query = request.args.get('q', '')
    limit = request.args.get('limit', 50, type=int)
    
    if len(query) < 2:
        return jsonify([])
    
    results = explorer.search_artists(query, limit)
    return jsonify(results)

@app.route('/api/artist/<int:artist_id>')
def get_artist(artist_id):
    """API para obtener detalles de un artista"""
    details = explorer.get_artist_details(artist_id)
    if details:
        return jsonify(details)
    else:
        return jsonify({'error': 'Artista no encontrado'}), 404

@app.route('/api/album/<int:album_id>')
def get_album(album_id):
    """API para obtener detalles de un álbum"""
    details = explorer.get_album_details(album_id)
    if details:
        return jsonify(details)
    else:
        return jsonify({'error': 'Álbum no encontrado'}), 404

@app.route('/api/folders')
def get_folders():
    """API para obtener estructura de carpetas"""
    path = request.args.get('path', '')
    structure = explorer.get_folder_structure(path)
    return jsonify(structure)

@app.route('/api/stats')
def get_stats():
    """API para obtener estadísticas generales"""
    conn = explorer.get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de base de datos'}), 500
    
    try:
        cursor = conn.cursor()
        
        # Estadísticas básicas
        cursor.execute("SELECT COUNT(*) FROM artists WHERE origen = 'local'")
        artist_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM albums WHERE origen = 'local'")
        album_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM songs WHERE origen = 'local'")
        song_count = cursor.fetchone()[0]
        
        # Artistas más escuchados
        cursor.execute("""
            SELECT s.artist, SUM(COALESCE(s.reproducciones, 1)) as total_plays
            FROM songs s
            WHERE s.origen = 'local'
            GROUP BY s.artist
            ORDER BY total_plays DESC
            LIMIT 10
        """)
        
        top_artists = []
        for row in cursor.fetchall():
            top_artists.append({
                'artist': row[0],
                'plays': row[1]
            })
        
        conn.close()
        
        return jsonify({
            'artist_count': artist_count,
            'album_count': album_count,
            'song_count': song_count,
            'top_artists': top_artists
        })
        
    except Exception as e:
        explorer.logger.error(f"Error obteniendo estadísticas: {e}")
        conn.close()
        return jsonify({'error': str(e)}), 500

@app.route('/api/album/<int:album_id>/download', methods=['POST'])
def download_album(album_id):
    """Endpoint para descargar álbum - VERSIÓN UNIFICADA"""
    
    # Verificar que el álbum existe y obtener información
    conn = explorer.get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de base de datos'}), 500
    
    try:
        cursor = conn.cursor()
        
        # Obtener información del álbum y artista
        cursor.execute("""
            SELECT al.*, ar.name as artist_name, ar.id as artist_id
            FROM albums al
            JOIN artists ar ON al.artist_id = ar.id
            WHERE al.id = ? AND al.origen = 'local'
        """, (album_id,))
        
        album = cursor.fetchone()
        if not album:
            conn.close()
            return jsonify({'error': 'Álbum no encontrado'}), 404
        
        # Obtener ruta del álbum desde las canciones
        cursor.execute("""
            SELECT DISTINCT file_path
            FROM songs s
            WHERE s.album = ? AND s.artist = ? AND s.origen = 'local'
            LIMIT 1
        """, (album['name'], album['artist_name']))
        
        song_result = cursor.fetchone()
        conn.close()
        
        if not song_result or not song_result['file_path']:
            return jsonify({'error': 'No se encontró ruta del álbum'}), 404
        
        # Extraer directorio del álbum de la ruta del archivo
        song_path = Path(song_result['file_path'])
        album_path = song_path.parent
        
        download_id = f"album_{album_id}_{int(time_module.time())}"
        
        # Logging para debug
        explorer.logger.info(f"Descarga solicitada - Álbum: {album['name']}, Artista: {album['artist_name']}, Ruta: {album_path}")
        
        # Iniciar descarga en hilo separado
        def perform_download():
            try:
                download_status[download_id] = {
                    'status': 'downloading',
                    'progress': 0,
                    'message': f'Iniciando descarga de "{album["name"]}"...',
                    'album_name': album['name'],
                    'artist_name': album['artist_name']
                }
                
                # Configuración SSH desde config
                ssh_host = explorer.config.get('download', 'ssh_host', fallback='pepecono')
                ssh_user = explorer.config.get('download', 'ssh_user', fallback='dietpi')
                
                # Crear directorio de destino
                dest_path = Path(explorer.download_path) / album['artist_name'] / album['name']
                dest_path.mkdir(parents=True, exist_ok=True)
                
                # Comando rsync como usuario dietpi
                rsync_cmd = [
                    'rsync',
                    '-avzh',
                    '--progress',
                    f"{ssh_user}@{ssh_host}:{album_path}/",
                    str(dest_path) + "/"
                ]
                
                explorer.logger.info(f"Ejecutando descarga como {os.getenv('USER', 'unknown')}: {' '.join(rsync_cmd)}")
                
                # Ejecutar rsync con el usuario actual (dietpi)
                process = subprocess.Popen(
                    rsync_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                # Monitorear progreso
                while True:
                    output = process.stdout.readline()
                    if output == '' and process.poll() is not None:
                        break
                    
                    if output:
                        download_status[download_id]['message'] = output.strip()
                        explorer.logger.info(f"Descarga {download_id}: {output.strip()}")
                
                # Verificar resultado
                return_code = process.poll()
                stderr_output = process.stderr.read()
                
                if return_code == 0:
                    download_status[download_id] = {
                        'status': 'completed',
                        'progress': 100,
                        'message': f'Álbum "{album["name"]}" descargado exitosamente',
                        'album_name': album['name'],
                        'artist_name': album['artist_name'],
                        'download_path': str(dest_path)
                    }
                    explorer.logger.info(f"Descarga completada: {download_id}")
                else:
                    download_status[download_id] = {
                        'status': 'error',
                        'progress': 0,
                        'message': f'Error en descarga: {stderr_output}',
                        'album_name': album['name'],
                        'artist_name': album['artist_name']
                    }
                    explorer.logger.error(f"Error en descarga {download_id}: {stderr_output}")
                    
            except Exception as e:
                download_status[download_id] = {
                    'status': 'error',
                    'progress': 0,
                    'message': f'Error interno: {str(e)}',
                    'album_name': album.get('name', 'Desconocido'),
                    'artist_name': album.get('artist_name', 'Desconocido')
                }
                explorer.logger.error(f"Excepción en descarga {download_id}: {e}")
        
        # Iniciar descarga en hilo separado
        download_thread = threading.Thread(target=perform_download)
        download_thread.daemon = True
        download_thread.start()
        
        return jsonify({
            'success': True,
            'download_id': download_id,
            'message': 'Descarga iniciada',
            'album_name': album['name'],
            'artist_name': album['artist_name'],
            'album_path': str(album_path)
        })
        
    except Exception as e:
        explorer.logger.error(f"Error iniciando descarga del álbum {album_id}: {e}")
        if conn:
            conn.close()
        return jsonify({'error': str(e)}), 500

@app.route('/api/download/<download_id>/status')
def get_download_status(download_id):
    """Obtener estado de una descarga"""
    if download_id in download_status:
        return jsonify(download_status[download_id])
    else:
        return jsonify({'error': 'Descarga no encontrada'}), 404

@app.route('/api/downloads/active')
def get_active_downloads():
    """Obtener todas las descargas activas"""
    active = {k: v for k, v in download_status.items() 
              if v['status'] in ['downloading', 'completed']}
    return jsonify(active)

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

@app.route('/api/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    """Manejar requests OPTIONS para CORS"""
    response = app.make_default_options_response()
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

if __name__ == '__main__':
    # Configuración del servidor
    host = explorer.config.get('web', 'host', fallback='0.0.0.0')
    port = explorer.config.getint('web', 'port', fallback=5157)
    debug = explorer.config.getboolean('web', 'debug', fallback=False)
    
    explorer.logger.info(f"Iniciando servidor en {host}:{port}")
    app.run(host=host, port=port, debug=debug)