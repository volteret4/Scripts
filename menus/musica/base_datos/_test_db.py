#!/usr/bin/env python3

# TLDR MANPAGE

# # Buscar canciones que contengan "love"
# python music_search.py --db mi_musica.db "love"

# # Buscar artistas de "españa"
# python music_search.py --db mi_musica.db --type artist "españa"

# # Buscar álbumes del 2020
# python music_search.py --db mi_musica.db --type album --field year "2020"

# # Buscar letras con la palabra "corazón"
# python music_search.py --db mi_musica.db --type lyrics "corazón"

# # Ver detalles de una canción por ID
# python music_search.py --db mi_musica.db --song-id 123

# # Limitar resultados a 5
# python music_search.py --db mi_musica.db --limit 5 "rock"

import sqlite3
import argparse
import os
import textwrap
from datetime import datetime
import sys

class MusicDatabaseSearcher:
    def __init__(self, db_path):
        """Inicializa el buscador con la ruta a la base de datos"""
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        
    def connect(self):
        """Establece conexión con la base de datos"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
            return True
        except sqlite3.Error as e:
            print(f"Error al conectar a la base de datos: {e}")
            return False
            
    def close(self):
        """Cierra la conexión con la base de datos"""
        if self.conn:
            self.conn.close()
            
    def search_songs(self, search_term, field=None, limit=10):
        """Busca canciones en la base de datos"""
        if not self.connect():
            return []
            
        try:
            if field and field in [
                'id', 'title', 'artist', 'album', 'genre', 'date',
                'track_number', 'album_artist', 'label', 'mbid'
            ]:
                query = f"""
                SELECT s.id, s.title, s.artist, s.album, s.genre, s.date, s.duration, s.file_path 
                FROM songs s 
                WHERE s.{field} LIKE ? 
                ORDER BY s.artist, s.album, s.track_number 
                LIMIT ?
                """
                self.cursor.execute(query, (f"%{search_term}%", limit))
            else:
                # Búsqueda general en múltiples campos
                query = """
                SELECT s.id, s.title, s.artist, s.album, s.genre, s.date, s.duration, s.file_path 
                FROM songs s 
                WHERE s.title LIKE ? OR s.artist LIKE ? OR s.album LIKE ? OR s.genre LIKE ? 
                ORDER BY s.artist, s.album, s.track_number 
                LIMIT ?
                """
                params = [f"%{search_term}%"] * 4 + [limit]
                self.cursor.execute(query, params)
                
            results = self.cursor.fetchall()
            return results
        except sqlite3.Error as e:
            print(f"Error en la búsqueda de canciones: {e}")
            return []
        finally:
            self.close()
    
    def search_artists(self, search_term, field=None, limit=10):
        """Busca artistas en la base de datos"""
        if not self.connect():
            return []
            
        try:
            if field and field in ['id', 'name', 'origin', 'tags', 'formed_year']:
                query = f"""
                SELECT a.id, a.name, a.origin, a.formed_year, a.total_albums, a.tags 
                FROM artists a 
                WHERE a.{field} LIKE ? 
                ORDER BY a.name 
                LIMIT ?
                """
                self.cursor.execute(query, (f"%{search_term}%", limit))
            else:
                # Búsqueda general
                query = """
                SELECT a.id, a.name, a.origin, a.formed_year, a.total_albums, a.tags 
                FROM artists a 
                WHERE a.name LIKE ? OR a.origin LIKE ? OR a.tags LIKE ? 
                ORDER BY a.name 
                LIMIT ?
                """
                params = [f"%{search_term}%"] * 3 + [limit]
                self.cursor.execute(query, params)
                
            results = self.cursor.fetchall()
            return results
        except sqlite3.Error as e:
            print(f"Error en la búsqueda de artistas: {e}")
            return []
        finally:
            self.close()
    
    def search_albums(self, search_term, field=None, limit=10):
        """Busca álbumes en la base de datos"""
        if not self.connect():
            return []
            
        try:
            if field and field in ['id', 'name', 'year', 'label', 'genre']:
                query = f"""
                SELECT alb.id, alb.name, art.name, alb.year, alb.label, alb.genre, alb.total_tracks 
                FROM albums alb 
                JOIN artists art ON alb.artist_id = art.id 
                WHERE alb.{field} LIKE ? 
                ORDER BY art.name, alb.year 
                LIMIT ?
                """
                self.cursor.execute(query, (f"%{search_term}%", limit))
            else:
                # Búsqueda general incluyendo artista
                query = """
                SELECT alb.id, alb.name, art.name, alb.year, alb.label, alb.genre, alb.total_tracks 
                FROM albums alb 
                JOIN artists art ON alb.artist_id = art.id 
                WHERE alb.name LIKE ? OR art.name LIKE ? OR alb.label LIKE ? OR alb.genre LIKE ? 
                ORDER BY art.name, alb.year 
                LIMIT ?
                """
                params = [f"%{search_term}%"] * 4 + [limit]
                self.cursor.execute(query, params)
                
            results = self.cursor.fetchall()
            return results
        except sqlite3.Error as e:
            print(f"Error en la búsqueda de álbumes: {e}")
            return []
        finally:
            self.close()
    
    def search_lyrics(self, search_term, limit=5):
        """Busca letras que contengan el término de búsqueda"""
        if not self.connect():
            return []
            
        try:
            query = """
            SELECT l.id, s.title, s.artist, l.lyrics 
            FROM lyrics l 
            JOIN songs s ON l.track_id = s.id 
            WHERE l.lyrics LIKE ? 
            LIMIT ?
            """
            self.cursor.execute(query, (f"%{search_term}%", limit))
            results = self.cursor.fetchall()
            return results
        except sqlite3.Error as e:
            print(f"Error en la búsqueda de letras: {e}")
            return []
        finally:
            self.close()
    
    def get_song_details(self, song_id):
        """Obtiene los detalles completos de una canción por su ID"""
        if not self.connect():
            return None
            
        try:
            query = """
            SELECT s.*, l.lyrics 
            FROM songs s 
            LEFT JOIN lyrics l ON s.lyrics_id = l.id 
            WHERE s.id = ?
            """
            self.cursor.execute(query, (song_id,))
            song = self.cursor.fetchone()
            
            if song:
                # Obtener columnas para mapeo
                columns = [desc[0] for desc in self.cursor.description]
                # Crear diccionario con los datos
                song_dict = {columns[i]: song[i] for i in range(len(columns))}
                return song_dict
            return None
        except sqlite3.Error as e:
            print(f"Error al obtener detalles de la canción: {e}")
            return None
        finally:
            self.close()
    
    def get_artist_details(self, artist_id):
        """Obtiene los detalles completos de un artista por su ID"""
        if not self.connect():
            return None
            
        try:
            # Obtener información del artista
            query_artist = "SELECT * FROM artists WHERE id = ?"
            self.cursor.execute(query_artist, (artist_id,))
            artist = self.cursor.fetchone()
            
            if not artist:
                return None
                
            # Obtener columnas para mapeo
            artist_columns = [desc[0] for desc in self.cursor.description]
            # Crear diccionario con los datos
            artist_dict = {artist_columns[i]: artist[i] for i in range(len(artist_columns))}
            
            # Obtener álbumes del artista
            query_albums = """
            SELECT id, name, year, label, genre, total_tracks 
            FROM albums 
            WHERE artist_id = ? 
            ORDER BY year
            """
            self.cursor.execute(query_albums, (artist_id,))
            albums = self.cursor.fetchall()
            
            # Añadir álbumes al diccionario
            artist_dict['albums'] = []
            for album in albums:
                album_dict = {
                    'id': album[0],
                    'name': album[1],
                    'year': album[2],
                    'label': album[3],
                    'genre': album[4],
                    'total_tracks': album[5]
                }
                artist_dict['albums'].append(album_dict)
                
            return artist_dict
        except sqlite3.Error as e:
            print(f"Error al obtener detalles del artista: {e}")
            return None
        finally:
            self.close()
    
    def get_album_details(self, album_id):
        """Obtiene los detalles completos de un álbum por su ID"""
        if not self.connect():
            return None
            
        try:
            # Obtener información del álbum
            query_album = """
            SELECT alb.*, art.name as artist_name 
            FROM albums alb 
            JOIN artists art ON alb.artist_id = art.id 
            WHERE alb.id = ?
            """
            self.cursor.execute(query_album, (album_id,))
            album = self.cursor.fetchone()
            
            if not album:
                return None
                
            # Obtener columnas para mapeo
            album_columns = [desc[0] for desc in self.cursor.description]
            # Crear diccionario con los datos
            album_dict = {album_columns[i]: album[i] for i in range(len(album_columns))}
            
            # Obtener canciones del álbum
            query_songs = """
            SELECT id, title, track_number, duration, artist 
            FROM songs 
            WHERE album = ? AND artist = ? 
            ORDER BY track_number
            """
            self.cursor.execute(query_songs, (album_dict['name'], album_dict['artist_name']))
            songs = self.cursor.fetchall()
            
            # Añadir canciones al diccionario
            album_dict['songs'] = []
            for song in songs:
                song_dict = {
                    'id': song[0],
                    'title': song[1],
                    'track_number': song[2],
                    'duration': song[3],
                    'artist': song[4]
                }
                album_dict['songs'].append(song_dict)
                
            return album_dict
        except sqlite3.Error as e:
            print(f"Error al obtener detalles del álbum: {e}")
            return None
        finally:
            self.close()

    # Añadimos nuevos métodos para estadísticas
    def get_statistics(self):
        """Obtiene estadísticas generales de la base de datos de música"""
        if not self.connect():
            return None
            
        try:
            stats = {}
            
            # Contar canciones
            self.cursor.execute("SELECT COUNT(*) FROM songs")
            stats['total_songs'] = self.cursor.fetchone()[0]
            
            # Contar artistas
            self.cursor.execute("SELECT COUNT(*) FROM artists")
            stats['total_artists'] = self.cursor.fetchone()[0]
            
            # Contar álbumes únicos
            self.cursor.execute("SELECT COUNT(*) FROM albums")
            stats['total_albums'] = self.cursor.fetchone()[0]
            
            # Contar géneros únicos
            self.cursor.execute("SELECT COUNT(DISTINCT genre) FROM songs WHERE genre IS NOT NULL AND genre != ''")
            stats['total_genres'] = self.cursor.fetchone()[0]
            
            # Duración total de la música (en segundos)
            self.cursor.execute("SELECT SUM(duration) FROM songs WHERE duration IS NOT NULL")
            total_duration = self.cursor.fetchone()[0]
            stats['total_duration'] = total_duration if total_duration else 0
            
            # Canciones por artista (promedio)
            if stats['total_artists'] > 0:
                stats['avg_songs_per_artist'] = stats['total_songs'] / stats['total_artists']
            else:
                stats['avg_songs_per_artist'] = 0
                
            # Álbumes por artista (promedio)
            if stats['total_artists'] > 0:
                stats['avg_albums_per_artist'] = stats['total_albums'] / stats['total_artists']
            else:
                stats['avg_albums_per_artist'] = 0
                
            # Distribución por década
            self.cursor.execute("""
                SELECT 
                    CASE 
                        WHEN date LIKE '195%' THEN '1950s'
                        WHEN date LIKE '196%' THEN '1960s'
                        WHEN date LIKE '197%' THEN '1970s'
                        WHEN date LIKE '198%' THEN '1980s'
                        WHEN date LIKE '199%' THEN '1990s'
                        WHEN date LIKE '200%' THEN '2000s'
                        WHEN date LIKE '201%' THEN '2010s'
                        WHEN date LIKE '202%' THEN '2020s'
                        ELSE 'Desconocido'
                    END as decade,
                    COUNT(*) as count
                FROM songs
                GROUP BY decade
                ORDER BY 
                    CASE decade
                        WHEN '1950s' THEN 1
                        WHEN '1960s' THEN 2
                        WHEN '1970s' THEN 3
                        WHEN '1980s' THEN 4
                        WHEN '1990s' THEN 5
                        WHEN '2000s' THEN 6
                        WHEN '2010s' THEN 7
                        WHEN '2020s' THEN 8
                        ELSE 9
                    END
            """)
            stats['decade_distribution'] = {decade: count for decade, count in self.cursor.fetchall()}
            
            # Top géneros
            self.cursor.execute("""
                SELECT genre, COUNT(*) as count 
                FROM songs 
                WHERE genre IS NOT NULL AND genre != '' 
                GROUP BY genre 
                ORDER BY count DESC 
                LIMIT 10
            """)
            stats['top_genres'] = {genre: count for genre, count in self.cursor.fetchall()}
            
            # Top artistas por cantidad de canciones
            self.cursor.execute("""
                SELECT artist, COUNT(*) as count 
                FROM songs 
                GROUP BY artist 
                ORDER BY count DESC 
                LIMIT 10
            """)
            stats['top_artists_by_songs'] = {artist: count for artist, count in self.cursor.fetchall()}
            
            # Artistas con más álbumes
            self.cursor.execute("""
                SELECT art.name, COUNT(DISTINCT alb.id) as album_count
                FROM artists art
                JOIN albums alb ON art.id = alb.artist_id
                GROUP BY art.id
                ORDER BY album_count DESC
                LIMIT 10
            """)
            stats['top_artists_by_albums'] = {artist: count for artist, count in self.cursor.fetchall()}
            
            # Estadísticas de letras
            self.cursor.execute("SELECT COUNT(*) FROM lyrics")
            stats['total_lyrics'] = self.cursor.fetchone()[0]
            
            # Porcentaje de canciones con letras
            if stats['total_songs'] > 0:
                stats['lyrics_coverage'] = (stats['total_lyrics'] / stats['total_songs']) * 100
            else:
                stats['lyrics_coverage'] = 0
                
            return stats
        except sqlite3.Error as e:
            print(f"Error al obtener estadísticas: {e}")
            return None
        finally:
            self.close()
    
    def get_genre_statistics(self):
        """Obtiene estadísticas detalladas por género"""
        if not self.connect():
            return None
            
        try:
            # Obtener todos los géneros con su conteo
            self.cursor.execute("""
                SELECT genre, COUNT(*) as count 
                FROM songs 
                WHERE genre IS NOT NULL AND genre != '' 
                GROUP BY genre 
                ORDER BY count DESC
            """)
            
            genres = []
            for genre, count in self.cursor.fetchall():
                # Para cada género, obtener artistas más representativos
                self.cursor.execute("""
                    SELECT artist, COUNT(*) as count 
                    FROM songs 
                    WHERE genre = ? 
                    GROUP BY artist 
                    ORDER BY count DESC 
                    LIMIT 5
                """, (genre,))
                top_artists = {artist: count for artist, count in self.cursor.fetchall()}
                
                # Obtener distribución por década para este género
                self.cursor.execute("""
                    SELECT 
                        CASE 
                            WHEN date LIKE '195%' THEN '1950s'
                            WHEN date LIKE '196%' THEN '1960s'
                            WHEN date LIKE '197%' THEN '1970s'
                            WHEN date LIKE '198%' THEN '1980s'
                            WHEN date LIKE '199%' THEN '1990s'
                            WHEN date LIKE '200%' THEN '2000s'
                            WHEN date LIKE '201%' THEN '2010s'
                            WHEN date LIKE '202%' THEN '2020s'
                            ELSE 'Desconocido'
                        END as decade,
                        COUNT(*) as count
                    FROM songs
                    WHERE genre = ?
                    GROUP BY decade
                    ORDER BY decade
                """, (genre,))
                decade_dist = {decade: count for decade, count in self.cursor.fetchall()}
                
                genres.append({
                    'name': genre,
                    'count': count,
                    'top_artists': top_artists,
                    'decade_distribution': decade_dist
                })
                
            return genres
        except sqlite3.Error as e:
            print(f"Error al obtener estadísticas de géneros: {e}")
            return None
        finally:
            self.close()
    
    def get_artist_statistics(self):
        """Obtiene estadísticas agregadas de artistas"""
        if not self.connect():
            return None
            
        try:
            stats = {}
            
            # Distribución de artistas por década de formación
            self.cursor.execute("""
                SELECT 
                    CASE 
                        WHEN formed_year < 1960 THEN 'Pre-1960s'
                        WHEN formed_year >= 1960 AND formed_year < 1970 THEN '1960s'
                        WHEN formed_year >= 1970 AND formed_year < 1980 THEN '1970s'
                        WHEN formed_year >= 1980 AND formed_year < 1990 THEN '1980s'
                        WHEN formed_year >= 1990 AND formed_year < 2000 THEN '1990s'
                        WHEN formed_year >= 2000 AND formed_year < 2010 THEN '2000s'
                        WHEN formed_year >= 2010 AND formed_year < 2020 THEN '2010s'
                        WHEN formed_year >= 2020 THEN '2020s'
                        ELSE 'Desconocido'
                    END as decade,
                    COUNT(*) as count
                FROM artists
                WHERE formed_year IS NOT NULL
                GROUP BY decade
                ORDER BY 
                    CASE decade
                        WHEN 'Pre-1960s' THEN 1
                        WHEN '1960s' THEN 2
                        WHEN '1970s' THEN 3
                        WHEN '1980s' THEN 4
                        WHEN '1990s' THEN 5
                        WHEN '2000s' THEN 6
                        WHEN '2010s' THEN 7
                        WHEN '2020s' THEN 8
                        ELSE 9
                    END
            """)
            stats['formation_by_decade'] = {decade: count for decade, count in self.cursor.fetchall()}
            
            # Distribución por países de origen
            self.cursor.execute("""
                SELECT origin, COUNT(*) as count 
                FROM artists 
                WHERE origin IS NOT NULL AND origin != '' 
                GROUP BY origin 
                ORDER BY count DESC 
                LIMIT 15
            """)
            stats['origin_countries'] = {origin: count for origin, count in self.cursor.fetchall()}
            
            # Artistas más productivos (más canciones)
            self.cursor.execute("""
                SELECT art.name, COUNT(s.id) as song_count
                FROM artists art
                JOIN albums alb ON art.id = alb.artist_id
                JOIN songs s ON alb.name = s.album AND art.name = s.artist
                GROUP BY art.id
                ORDER BY song_count DESC
                LIMIT 10
            """)
            stats['most_productive'] = {artist: count for artist, count in self.cursor.fetchall()}
            
            return stats
        except sqlite3.Error as e:
            print(f"Error al obtener estadísticas de artistas: {e}")
            return None
        finally:
            self.close()
    
    def get_year_statistics(self):
        """Obtiene estadísticas por año de lanzamiento"""
        if not self.connect():
            return None
            
        try:
            # Extraer año de la fecha y contar canciones por año
            self.cursor.execute("""
                SELECT 
                    CASE
                        WHEN date LIKE '____-__-__' THEN SUBSTR(date, 1, 4)
                        WHEN date LIKE '____-__' THEN SUBSTR(date, 1, 4)
                        WHEN date LIKE '____' THEN date
                        ELSE NULL
                    END as year,
                    COUNT(*) as count
                FROM songs
                WHERE date IS NOT NULL AND date != ''
                GROUP BY year
                HAVING year IS NOT NULL
                ORDER BY year
            """)
            
            years_data = {}
            for year, count in self.cursor.fetchall():
                # Para cada año, obtener los géneros más populares
                self.cursor.execute("""
                    SELECT genre, COUNT(*) as count
                    FROM songs
                    WHERE (date LIKE ? OR date LIKE ? OR date = ?) AND genre IS NOT NULL AND genre != ''
                    GROUP BY genre
                    ORDER BY count DESC
                    LIMIT 5
                """, (f"{year}-%-%", f"{year}-%", year))
                top_genres = {genre: count for genre, count in self.cursor.fetchall()}
                
                # Obtener los álbumes más destacados de ese año
                self.cursor.execute("""
                    SELECT album, artist, COUNT(*) as track_count
                    FROM songs
                    WHERE (date LIKE ? OR date LIKE ? OR date = ?)
                    GROUP BY album, artist
                    ORDER BY track_count DESC
                    LIMIT 5
                """, (f"{year}-%-%", f"{year}-%", year))
                top_albums = [{
                    'name': album,
                    'artist': artist,
                    'tracks': count
                } for album, artist, count in self.cursor.fetchall()]
                
                years_data[year] = {
                    'count': count,
                    'top_genres': top_genres,
                    'top_albums': top_albums
                }
                
            return years_data
        except sqlite3.Error as e:
            print(f"Error al obtener estadísticas por año: {e}")
            return None
        finally:
            self.close()

def format_duration(seconds):
    """Formatea segundos a formato mm:ss"""
    if seconds is None:
        return "??:??"
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{minutes}:{secs:02d}"

def print_songs_results(results):
    """Imprime los resultados de la búsqueda de canciones"""
    if not results:
        print("\n🔍 No se encontraron resultados.")
        return
        
    print(f"\n🔍 Se encontraron {len(results)} canciones:")
    print("-" * 80)
    print(f"{'ID':<5} {'TÍTULO':<30} {'ARTISTA':<25} {'ÁLBUM':<20}")
    print("-" * 80)
    
    for song in results:
        song_id, title, artist, album = song[0:4]
        # Truncar strings largos
        title = (title[:27] + '...') if len(title) > 30 else title
        artist = (artist[:22] + '...') if len(artist) > 25 else artist
        album = (album[:17] + '...') if len(album) > 20 else album
        
        print(f"{song_id:<5} {title:<30} {artist:<25} {album:<20}")
    print("-" * 80)

def print_artists_results(results):
    """Imprime los resultados de la búsqueda de artistas"""
    if not results:
        print("\n🔍 No se encontraron resultados.")
        return
        
    print(f"\n🔍 Se encontraron {len(results)} artistas:")
    print("-" * 80)
    print(f"{'ID':<5} {'NOMBRE':<35} {'ORIGEN':<20} {'AÑO':<6} {'ÁLBUMES':<8}")
    print("-" * 80)
    
    for artist in results:
        artist_id, name, origin, formed_year, total_albums = artist[0:5]
        # Truncar strings largos
        name = (name[:32] + '...') if len(name) > 35 else name
        origin = (origin[:17] + '...') if origin and len(origin) > 20 else (origin or "Desconocido")
        
        print(f"{artist_id:<5} {name:<35} {origin:<20} {formed_year or '????':<6} {total_albums or 0:<8}")
    print("-" * 80)

def print_albums_results(results):
    """Imprime los resultados de la búsqueda de álbumes"""
    if not results:
        print("\n🔍 No se encontraron resultados.")
        return
        
    print(f"\n🔍 Se encontraron {len(results)} álbumes:")
    print("-" * 80)
    print(f"{'ID':<5} {'ÁLBUM':<30} {'ARTISTA':<25} {'AÑO':<6} {'GÉNERO':<15}")
    print("-" * 80)
    
    for album in results:
        album_id, name, artist_name, year, label, genre = album[0:6]
        # Truncar strings largos
        name = (name[:27] + '...') if len(name) > 30 else name
        artist_name = (artist_name[:22] + '...') if len(artist_name) > 25 else artist_name
        genre = (genre[:12] + '...') if genre and len(genre) > 15 else (genre or "Desconocido")
        
        print(f"{album_id:<5} {name:<30} {artist_name:<25} {year or '????':<6} {genre:<15}")
    print("-" * 80)

def print_lyrics_results(results):
    """Imprime los resultados de la búsqueda de letras"""
    if not results:
        print("\n🔍 No se encontraron resultados en las letras.")
        return
        
    print(f"\n🔍 Se encontraron {len(results)} coincidencias en letras:")
    
    for i, lyric in enumerate(results, 1):
        lyric_id, title, artist, lyrics = lyric
        print(f"\n{i}. {title} - {artist} (ID: {lyric_id})")
        print("-" * 60)
        
        # Extracto de las letras (primeras 5 líneas)
        lyrics_preview = '\n'.join(lyrics.split('\n')[:5])
        if len(lyrics.split('\n')) > 5:
            lyrics_preview += "\n..."
            
        print(lyrics_preview)
        print("-" * 60)

def print_song_details(song_dict):
    """Imprime los detalles completos de una canción"""
    if not song_dict:
        print("\n❌ Canción no encontrada.")
        return
        
    width = 80
    print("\n" + "=" * width)
    print(f"📄 DETALLES DE LA CANCIÓN (ID: {song_dict['id']})")
    print("=" * width)
    
    print(f"🎵 Título:     {song_dict['title']}")
    print(f"👤 Artista:    {song_dict['artist']}")
    print(f"💿 Álbum:      {song_dict['album']}")
    if song_dict['album_artist'] and song_dict['album_artist'] != song_dict['artist']:
        print(f"👥 Artista del álbum: {song_dict['album_artist']}")
    print(f"🔢 Pista:      {song_dict['track_number'] or '?'}")
    print(f"📅 Fecha:      {song_dict['date'] or 'Desconocida'}")
    print(f"🎭 Género:     {song_dict['genre'] or 'Desconocido'}")
    if song_dict['label']:
        print(f"🏢 Sello:      {song_dict['label']}")
    print(f"⏱️  Duración:   {format_duration(song_dict['duration'])}")
    
    # Detalles técnicos
    print("\n📊 Información técnica:")
    print(f"   Bitrate:       {song_dict['bitrate'] or '?'} kbps")
    if song_dict['bit_depth']:
        print(f"   Profundidad:   {song_dict['bit_depth']} bits")
    if song_dict['sample_rate']:
        print(f"   Sample rate:   {song_dict['sample_rate']} Hz")
        
    # Información de archivo
    print(f"\n📂 Ruta del archivo:")
    print(f"   {song_dict['file_path']}")
    
    # Fechas
    if song_dict['added_timestamp']:
        added_date = datetime.fromisoformat(song_dict['added_timestamp'])
        print(f"\n🕒 Añadido:      {added_date.strftime('%d/%m/%Y %H:%M')}")
    if song_dict['last_modified']:
        modified_date = datetime.fromisoformat(song_dict['last_modified'])
        print(f"🕒 Modificado:    {modified_date.strftime('%d/%m/%Y %H:%M')}")
        
    # Letras
    if 'lyrics' in song_dict and song_dict['lyrics']:
        print("\n📝 Letras:")
        print("-" * width)
        print(song_dict['lyrics'])
        print("-" * width)
    elif 'lyrics_id' in song_dict and song_dict['lyrics_id']:
        print("\n📝 Letras disponibles (use la opción --lyrics)")
    else:
        print("\n📝 Letras no disponibles")
        
    print("=" * width)

def print_artist_details(artist_dict):
    """Imprime los detalles completos de un artista"""
    if not artist_dict:
        print("\n❌ Artista no encontrado.")
        return
        
    width = 80
    print("\n" + "=" * width)
    print(f"👤 DETALLES DEL ARTISTA (ID: {artist_dict['id']})")
    print("=" * width)
    
    print(f"🎤 Nombre:     {artist_dict['name']}")
    if artist_dict['origin']:
        print(f"🌍 Origen:     {artist_dict['origin']}")
    if artist_dict['formed_year']:
        print(f"📅 Formado en: {artist_dict['formed_year']}")
    if artist_dict['tags']:
        print(f"🏷️  Etiquetas:  {artist_dict['tags']}")
    if artist_dict['bio']:
        print("\n📖 Biografía:")
        print("-" * width)
        print(textwrap.fill(artist_dict['bio'], width=width))
        print("-" * width)
        
    # Enlaces
    links = []
    if artist_dict['spotify_url']:
        links.append(f"Spotify: {artist_dict['spotify_url']}")
    if artist_dict['youtube_url']:
        links.append(f"YouTube: {artist_dict['youtube_url']}")
    if artist_dict['musicbrainz_url']:
        links.append(f"MusicBrainz: {artist_dict['musicbrainz_url']}")
    if artist_dict['discogs_url']:
        links.append(f"Discogs: {artist_dict['discogs_url']}")
    if artist_dict['rateyourmusic_url']:
        links.append(f"RateYourMusic: {artist_dict['rateyourmusic_url']}")
        
    if links:
        print("\n🔗 Enlaces:")
        for link in links:
            print(f"   {link}")
            
    # Álbumes
    if 'albums' in artist_dict and artist_dict['albums']:
        print(f"\n💿 Álbumes ({len(artist_dict['albums'])}):")
        print("-" * width)
        print(f"{'ID':<5} {'ÁLBUM':<40} {'AÑO':<6} {'TRACKS':<6} {'GÉNERO':<20}")
        print("-" * width)
        
        for album in artist_dict['albums']:
            name = (album['name'][:37] + '...') if len(album['name']) > 40 else album['name']
            genre = (album['genre'][:17] + '...') if album['genre'] and len(album['genre']) > 20 else (album['genre'] or "Desconocido")
            print(f"{album['id']:<5} {name:<40} {album['year'] or '????':<6} {album['total_tracks'] or '?':<6} {genre:<20}")
        
    print("=" * width)

def print_album_details(album_dict):
    """Imprime los detalles completos de un álbum"""
    if not album_dict:
        print("\n❌ Álbum no encontrado.")
        return
        
    width = 80
    print("\n" + "=" * width)
    print(f"💿 DETALLES DEL ÁLBUM (ID: {album_dict['id']})")
    print("=" * width)
    
    print(f"📀 Título:     {album_dict['name']}")
    print(f"👤 Artista:    {album_dict['artist_name']}")
    print(f"📅 Año:        {album_dict['year'] or 'Desconocido'}")
    if album_dict['label']:
        print(f"🏢 Sello:      {album_dict['label']}")
    print(f"🎭 Género:     {album_dict['genre'] or 'Desconocido'}")
    print(f"🔢 Pistas:     {album_dict['total_tracks'] or '?'}")
    
    if album_dict['album_art_path']:
        print(f"\n🖼️  Portada:    {album_dict['album_art_path']}")
        
    # Enlaces
    links = []
    if album_dict['spotify_url']:
        links.append(f"Spotify: {album_dict['spotify_url']}")
    if album_dict['spotify_id']:
        links.append(f"Spotify ID: {album_dict['spotify_id']}")
    if album_dict['youtube_url']:
        links.append(f"YouTube: {album_dict['youtube_url']}")
    if album_dict['musicbrainz_url']:
        links.append(f"MusicBrainz: {album_dict['musicbrainz_url']}")
    if album_dict['discogs_url']:
        links.append(f"Discogs: {album_dict['discogs_url']}")
    if album_dict['rateyourmusic_url']:
        links.append(f"RateYourMusic: {album_dict['rateyourmusic_url']}")
        
    if links:
        print("\n🔗 Enlaces:")
        for link in links:
            print(f"   {link}")
            
    # Canciones
    if 'songs' in album_dict and album_dict['songs']:
        print(f"\n🎵 Canciones ({len(album_dict['songs'])}):")
        print("-" * width)
        print(f"{'#':<4} {'ID':<5} {'TÍTULO':<50} {'DURACIÓN':<8}")
        print("-" * width)
        
        for song in album_dict['songs']:
            track_num = song['track_number'] or '?'
            title = (song['title'][:47] + '...') if len(song['title']) > 50 else song['title']
            duration = format_duration(song['duration'])
            print(f"{track_num:<4} {song['id']:<5} {title:<50} {duration:<8}")
        
    print("=" * width)
    

# Funciones para imprimir estadísticas

def format_duration_long(seconds):
    """Formatea segundos a formato horas, minutos y segundos"""
    if seconds is None:
        return "Desconocido"
    hours = int(seconds) // 3600
    minutes = (int(seconds) % 3600) // 60
    secs = int(seconds) % 60
    
    if hours > 0:
        return f"{hours} horas, {minutes} minutos y {secs} segundos"
    elif minutes > 0:
        return f"{minutes} minutos y {secs} segundos"
    else:
        return f"{secs} segundos"

def print_general_statistics(stats):
    """Imprime las estadísticas generales de la biblioteca de música"""
    if not stats:
        print("\n📊 No se pudieron obtener estadísticas.")
        return
        
    width = 80
    print("\n" + "=" * width)
    print("📊 ESTADÍSTICAS GENERALES DE LA BIBLIOTECA")
    print("=" * width)
    
    # Estadísticas básicas
    print(f"🎵 Total de canciones:   {stats['total_songs']:,}")
    print(f"👤 Total de artistas:    {stats['total_artists']:,}")
    print(f"💿 Total de álbumes:     {stats['total_albums']:,}")
    print(f"🎭 Total de géneros:     {stats['total_genres']:,}")
    print(f"📝 Canciones con letras: {stats['total_lyrics']:,} ({stats['lyrics_coverage']:.1f}%)")
    
    # Duración total
    total_hours = stats['total_duration'] // 3600
    total_days = total_hours // 24
    print(f"⏱️  Duración total:      {format_duration_long(stats['total_duration'])}")
    print(f"                       ({total_days:.1f} días de música continua)")
    
    # Promedios
    print(f"📊 Canciones por artista: {stats['avg_songs_per_artist']:.1f}")
    print(f"📊 Álbumes por artista:   {stats['avg_albums_per_artist']:.1f}")
    
    # Distribución por década
    if stats['decade_distribution']:
        print("\n📅 Distribución por década:")
        print("-" * width)
        for decade, count in stats['decade_distribution'].items():
            percentage = (count / stats['total_songs']) * 100
            bar_length = int((count / stats['total_songs']) * 40)
            bar = "█" * bar_length
            print(f"{decade:<10} {count:>6} canciones ({percentage:>5.1f}%) {bar}")
    
    # Top géneros
    if stats['top_genres']:
        print("\n🎭 Top géneros musicales:")
        print("-" * width)
        for genre, count in stats['top_genres'].items():
            percentage = (count / stats['total_songs']) * 100
            print(f"{genre:<20} {count:>6} canciones ({percentage:>5.1f}%)")
    
    # Top artistas por canciones
    if stats['top_artists_by_songs']:
        print("\n👥 Artistas con más canciones:")
        print("-" * width)
        for artist, count in stats['top_artists_by_songs'].items():
            print(f"{artist:<30} {count:>5} canciones")
    
    # Top artistas por álbumes
    if stats['top_artists_by_albums']:
        print("\n👥 Artistas con más álbumes:")
        print("-" * width)
        for artist, count in stats['top_artists_by_albums'].items():
            print(f"{artist:<30} {count:>5} álbumes")
    
    print("=" * width)

def print_genre_statistics(genres_stats):
    """Imprime estadísticas detalladas por género"""
    if not genres_stats:
        print("\n📊 No se pudieron obtener estadísticas de géneros.")
        return
        
    width = 80
    print("\n" + "=" * width)
    print("🎭 ESTADÍSTICAS POR GÉNEROS MUSICALES")
    print("=" * width)
    
    # Total de géneros
    print(f"Total de géneros únicos: {len(genres_stats)}")
    print("-" * width)
    
    # Mostrar los primeros 15 géneros más populares
    top_genres = sorted(genres_stats, key=lambda x: x['count'], reverse=True)[:15]
    
    for i, genre in enumerate(top_genres, 1):
        print(f"{i}. {genre['name']} ({genre['count']} canciones)")
        
        # Top artistas del género
        if genre['top_artists']:
            print("   Artistas destacados:")
            for artist, count in genre['top_artists'].items():
                print(f"   - {artist} ({count} canciones)")
        
        # Distribución por década
        if genre['decade_distribution']:
            decades = []
            for decade, count in genre['decade_distribution'].items():
                decades.append(f"{decade}: {count}")
            print(f"   Épocas: {', '.join(decades)}")
            
        print()
    
    print("=" * width)

def print_artist_statistics(artist_stats):
    """Imprime estadísticas agregadas de artistas"""
    if not artist_stats:
        print("\n📊 No se pudieron obtener estadísticas de artistas.")
        return
        
    width = 80
    print("\n" + "=" * width)
    print("👤 ESTADÍSTICAS DE ARTISTAS")
    print("=" * width)
    
    # Distribución por década de formación
    if 'formation_by_decade' in artist_stats and artist_stats['formation_by_decade']:
        print("📅 Distribución por década de formación:")
        print("-" * width)
        for decade, count in artist_stats['formation_by_decade'].items():
            print(f"{decade:<10} {count:>5} artistas")
        print()
    
    # Distribución por país de origen
    if 'origin_countries' in artist_stats and artist_stats['origin_countries']:
        print("🌍 Distribución por país de origen:")
        print("-" * width)
        for country, count in artist_stats['origin_countries'].items():
            print(f"{country:<25} {count:>5} artistas")
        print()
    
    # Artistas más productivos
    if 'most_productive' in artist_stats and artist_stats['most_productive']:
        print("🏆 Artistas más productivos:")
        print("-" * width)
        for artist, count in artist_stats['most_productive'].items():
            print(f"{artist:<30} {count:>5} canciones")
    
    print("=" * width)

def print_year_statistics(year_stats):
    """Imprime estadísticas por año de lanzamiento"""
    if not year_stats:
        print("\n📊 No se pudieron obtener estadísticas por año.")
        return
        
    width = 80
    print("\n" + "=" * width)
    print("📅 ESTADÍSTICAS POR AÑO DE LANZAMIENTO")
    print("=" * width)
    
    # Ordenar años cronológicamente
    sorted_years = sorted(year_stats.keys())
    
    # Agrupar en décadas para facilitar la visualización
    decades = {}
    for year in sorted_years:
        decade = f"{year[:3]}0s"  # Ejemplo: "198" -> "1980s"
        if decade not in decades:
            decades[decade] = 0
        decades[decade] += year_stats[year]['count']
    
    # Mostrar distribución por década
    print("Canciones por década:")
    print("-" * width)
    for decade, count in sorted(decades.items()):
        print(f"{decade:<10} {count:>6} canciones")
    print()
    
    # Mostrar años con más lanzamientos (top 10)
    print("Años con más lanzamientos:")
    print("-" * width)
    top_years = sorted([(year, year_stats[year]['count']) for year in year_stats], 
                      key=lambda x: x[1], reverse=True)[:10]
                      
    for year, count in top_years:
        print(f"{year:<6} {count:>6} canciones")
        
        # Mostrar géneros destacados para ese año
        if year_stats[year]['top_genres']:
            genres = []
            for genre, genre_count in year_stats[year]['top_genres'].items():
                genres.append(f"{genre} ({genre_count})")
            print(f"       Géneros: {', '.join(genres[:3])}")
            
        # Mostrar álbumes destacados
        if year_stats[year]['top_albums']:
            print(f"       Álbumes destacados:")
            for album in year_stats[year]['top_albums'][:3]:
                print(f"       - {album['name']} por {album['artist']} ({album['tracks']} pistas)")
        
        print()
    
    print("=" * width)

# Modificar la función main() para incluir las nuevas opciones

def main():
    parser = argparse.ArgumentParser(description='Buscador y analizador para base de datos de música')
    
    # Argumentos principales
    parser.add_argument('--db', dest='database', default='music.db',
                      help='Ruta a la base de datos SQLite (default: music.db)')
    parser.add_argument('--type', '-t', dest='search_type', 
                      choices=['song', 'artist', 'album', 'lyrics', 'stats'],
                      default='song', help='Tipo de búsqueda o análisis (default: song)')
    parser.add_argument('--field', '-f', dest='field',
                      help='Campo específico para buscar (depende del tipo de búsqueda)')
    parser.add_argument('--limit', '-l', dest='limit', type=int, default=10,
                      help='Límite de resultados (default: 10)')
    
    # Argumentos para mostrar detalles
    detail_group = parser.add_argument_group('Detalles')
    detail_group.add_argument('--song-id', dest='song_id', type=int,
                          help='Mostrar detalles de una canción por ID')
    detail_group.add_argument('--artist-id', dest='artist_id', type=int,
                          help='Mostrar detalles de un artista por ID')
    detail_group.add_argument('--album-id', dest='album_id', type=int,
                          help='Mostrar detalles de un álbum por ID')
    
    # Argumentos para estadísticas
    stats_group = parser.add_argument_group('Estadísticas')
    stats_group.add_argument('--stats', dest='stats_type', 
                         choices=['general', 'genres', 'artists', 'years', 'all'],
                         help='Tipo de estadísticas a mostrar')
    
    # Argumento posicional para el término de búsqueda
    parser.add_argument('search_term', nargs='?', default='',
                      help='Término de búsqueda')
    
    args = parser.parse_args()
    
    # Verificar que la base de datos existe
    if not os.path.exists(args.database):
        print(f"Error: Base de datos '{args.database}' no encontrada.")
        sys.exit(1)
    
    searcher = MusicDatabaseSearcher(args.database)
    
    # Priorizar los comandos de mostrar detalles
    if args.song_id is not None:
        song_details = searcher.get_song_details(args.song_id)
        print_song_details(song_details)
        return
        
    if args.artist_id is not None:
        artist_details = searcher.get_artist_details(args.artist_id)
        print_artist_details(artist_details)
        return
        
    if args.album_id is not None:
        album_details = searcher.get_album_details(args.album_id)
        print_album_details(album_details)
        return
    
    # Comprobar si se solicitan estadísticas
    if args.stats_type or args.search_type == 'stats':
        stats_type = args.stats_type if args.stats_type else 'general'
        
        if stats_type == 'general' or stats_type == 'all':
            stats = searcher.get_statistics()
            print_general_statistics(stats)
            
        if stats_type == 'genres' or stats_type == 'all':
            genres_stats = searcher.get_genre_statistics()
            print_genre_statistics(genres_stats)
            
        if stats_type == 'artists' or stats_type == 'all':
            artist_stats = searcher.get_artist_statistics()
            print_artist_statistics(artist_stats)
            
        if stats_type == 'years' or stats_type == 'all':
            year_stats = searcher.get_year_statistics()
            print_year_statistics(year_stats)
            
        return
    
    # Para búsquedas normales, verificar que se proporcionó un término
    if not args.search_term and args.search_type != 'stats':
        parser.print_help()
        print("\nError: Debe proporcionar un término de búsqueda o solicitar estadísticas.")
        sys.exit(1)
    
    # Ejecutar la búsqueda según el tipo
    if args.search_type == 'song':
        results = searcher.search_songs(args.search_term, args.field, args.limit)
        print_songs_results(results)
    elif args.search_type == 'artist':
        results = searcher.search_artists(args.search_term, args.field, args.limit)
        print_artists_results(results)
    elif args.search_type == 'album':
        results = searcher.search_albums(args.search_term, args.field, args.limit)
        print_albums_results(results)
    elif args.search_type == 'lyrics':
        results = searcher.search_lyrics(args.search_term, args.limit)
        print_lyrics_results(results)

if __name__ == "__main__":
    main()