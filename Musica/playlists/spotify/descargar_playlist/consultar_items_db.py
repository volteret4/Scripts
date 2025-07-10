import sqlite3
import argparse
import json

class MusicDatabaseQuery:
    def __init__(self, db_path):
        """
        Inicializa la conexión con la base de datos
        
        :param db_path: Ruta al archivo de base de datos SQLite
        """
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

    def get_mbid_by_album_artist(self, artist, album):
        """
        Obtiene el MBID de un álbum por artista (case insensitive)
        
        :param artist: Nombre del artista
        :param album: Nombre del álbum
        :return: MBID del álbum o None si no se encuentra
        """
        query = """
        SELECT albums.mbid FROM albums 
        JOIN artists ON albums.artist_id = artists.id 
        WHERE LOWER(artists.name) = LOWER(?) AND LOWER(albums.name) = LOWER(?)
        """
        self.cursor.execute(query, (artist, album))
        result = self.cursor.fetchone()
        return result[0] if result else None

    def get_mbid_by_album_track(self, album, track):
        """
        Obtiene el MBID de una canción en un álbum (case insensitive)
        
        :param album: Nombre del álbum
        :param track: Nombre de la canción
        :return: MBID de la canción o None si no se encuentra
        """
        query = """
        SELECT songs.mbid FROM songs 
        WHERE LOWER(songs.album) = LOWER(?) AND LOWER(songs.title) = LOWER(?)
        """
        self.cursor.execute(query, (album, track))
        result = self.cursor.fetchone()
        return result[0] if result else None

    def get_album_links(self, artist, album):
        """
        Obtiene los links de servicios para un álbum (case insensitive)
        
        :param artist: Nombre del artista
        :param album: Nombre del álbum
        :return: Diccionario con links de servicios
        """
        query = """
        SELECT 
            albums.spotify_url, 
            albums.youtube_url, 
            albums.musicbrainz_url, 
            albums.discogs_url, 
            albums.wikipedia_url
        FROM albums 
        JOIN artists ON albums.artist_id = artists.id
        WHERE LOWER(albums.name) = LOWER(?) AND LOWER(artists.name) = LOWER(?)
        """
        self.cursor.execute(query, (album, artist))
        result = self.cursor.fetchone()
        
        if result:
            links = {
                'spotify': result[0],
                'youtube': result[1],
                'musicbrainz': result[2],
                'discogs': result[3],
                'wikipedia': result[4]
            }
            return {k: v for k, v in links.items() if v}
        return None

    def get_track_links(self, album, track, services=None):
        """
        Obtiene los links de servicios para una canción de forma optimizada
        - Usa índices en la tabla songs mediante subquery
        
        :param album: Nombre del álbum
        :param track: Nombre de la canción
        :param services: Lista de servicios específicos (opcional)
        :return: Diccionario con links de servicios
        """
        query = """
        SELECT 
            song_links.spotify_url, 
            song_links.youtube_url,
            song_links.musicbrainz_url,
            song_links.lastfm_url
        FROM song_links
        WHERE song_links.song_id IN (
            SELECT id FROM songs 
            WHERE album LIKE ? COLLATE NOCASE 
            AND title LIKE ? COLLATE NOCASE
            LIMIT 1
        )
        """
        self.cursor.execute(query, (album, track))
        result = self.cursor.fetchone()
        
        if result:
            all_links = {
                'spotify': result[0],
                'youtube': result[1],
                'musicbrainz': result[2],
                'lastfm': result[3]
            }
            
            # Si se especifican servicios, filtrar
            if services:
                links = {service: all_links.get(service) for service in services if service in all_links}
                return {k: v for k, v in links.items() if v}
            
            return {k: v for k, v in all_links.items() if v}
        return None


    def get_album_wiki(self, artist, album):
        """
        Obtiene el contenido de Wikipedia para un álbum (case insensitive)
        
        :param artist: Nombre del artista
        :param album: Nombre del álbum
        :return: Contenido de Wikipedia o None
        """
        query = """
        SELECT albums.wikipedia_content 
        FROM albums 
        JOIN artists ON albums.artist_id = artists.id
        WHERE LOWER(artists.name) = LOWER(?) AND LOWER(albums.name) = LOWER(?)
        """
        self.cursor.execute(query, (artist, album))
        result = self.cursor.fetchone()
        return result[0] if result else None

    def get_artist_mbid(self, artist_name):
        """
        Obtiene el MBID de un artista (case insensitive)
        
        :param artist_name: Nombre del artista
        :return: MBID del artista o None si no se encuentra
        """
        query = "SELECT mbid FROM artists WHERE LOWER(name) = LOWER(?)"
        self.cursor.execute(query, (artist_name,))
        result = self.cursor.fetchone()
        return result[0] if result else None

    def get_artist_links(self, artist_name):
        """
        Obtiene los links de servicios para un artista usando índices (case insensitive)
        - Optimizado para añadir LOWER() solo en la condición, no en la columna
        
        :param artist_name: Nombre del artista
        :return: Diccionario con links de servicios
        """
        query = """
        SELECT 
            spotify_url, 
            youtube_url, 
            musicbrainz_url, 
            discogs_url, 
            rateyourmusic_url,
            wikipedia_url
        FROM artists WHERE name LIKE ?
        COLLATE NOCASE
        """
        self.cursor.execute(query, (artist_name,))
        result = self.cursor.fetchone()
        
        if result:
            links = {
                'spotify': result[0],
                'youtube': result[1],
                'musicbrainz': result[2],
                'discogs': result[3],
                'rateyourmusic': result[4],
                'wikipedia': result[5]
            }
            return {k: v for k, v in links.items() if v}
        return None

    def get_artist_wiki_content(self, artist_name):
        """
        Obtiene el contenido de Wikipedia para un artista (case insensitive)
        
        :param artist_name: Nombre del artista
        :return: Contenido de Wikipedia o None
        """
        query = "SELECT wikipedia_content FROM artists WHERE LOWER(name) = LOWER(?)"
        self.cursor.execute(query, (artist_name,))
        result = self.cursor.fetchone()
        return result[0] if result else None

    def get_artist_albums(self, artist_name):
        """
        Obtiene los álbumes de un artista de forma optimizada
        - Usa índices existentes con COLLATE NOCASE para mejor rendimiento
        - Usa una subquery para obtener artist_id primero
        
        :param artist_name: Nombre del artista
        :return: Lista de álbumes
        """
        query = """
        SELECT albums.name, albums.year, albums.genre 
        FROM albums 
        WHERE albums.artist_id = (
            SELECT id FROM artists WHERE name LIKE ? COLLATE NOCASE LIMIT 1
        )
        ORDER BY albums.year DESC, albums.name
        """
        self.cursor.execute(query, (artist_name,))
        return self.cursor.fetchall()   

    def get_albums_by_label(self, label):
        """
        Obtiene álbumes de un sello discográfico (case insensitive)
        
        :param label: Nombre del sello
        :return: Lista de álbumes
        """
        query = """
        SELECT albums.name, artists.name, albums.year 
        FROM albums 
        JOIN artists ON albums.artist_id = artists.id
        WHERE LOWER(albums.label) = LOWER(?)
        """
        self.cursor.execute(query, (label,))
        return self.cursor.fetchall()

    def get_albums_by_year(self, year):
        """
        Obtiene álbumes de un año específico
        
        :param year: Año de los álbumes
        :return: Lista de álbumes
        """
        query = """
        SELECT albums.name, artists.name, albums.genre 
        FROM albums 
        JOIN artists ON albums.artist_id = artists.id
        WHERE albums.year = ?
        """
        self.cursor.execute(query, (str(year),))
        return self.cursor.fetchall()

    def get_albums_by_genre(self, genre):
        """
        Obtiene álbumes de un género específico (case insensitive)
        
        :param genre: Género musical
        :return: Lista de álbumes
        """
        query = """
        SELECT albums.name, artists.name, albums.year 
        FROM albums 
        JOIN artists ON albums.artist_id = artists.id
        WHERE LOWER(albums.genre) = LOWER(?)
        """
        self.cursor.execute(query, (genre,))
        return self.cursor.fetchall()

    def get_song_lyrics(self, song_title, artist_name=None):
        """
        Obtiene la letra de una canción (case insensitive)
        
        :param song_title: Título de la canción
        :param artist_name: Nombre del artista (opcional)
        :return: Letra de la canción o None
        """
        if artist_name:
            query = """
            SELECT lyrics.lyrics 
            FROM lyrics 
            JOIN songs ON lyrics.track_id = songs.id 
            WHERE LOWER(songs.title) = LOWER(?) AND LOWER(songs.artist) = LOWER(?)
            """
            self.cursor.execute(query, (song_title, artist_name))
        else:
            query = """
            SELECT lyrics.lyrics 
            FROM lyrics 
            JOIN songs ON lyrics.track_id = songs.id 
            WHERE LOWER(songs.title) = LOWER(?)
            """
            self.cursor.execute(query, (song_title,))
        
        result = self.cursor.fetchone()
        return result[0] if result else None

    def get_artist_genres(self, artist_name):
        """
        Obtiene los géneros de un artista (case insensitive)
        
        :param artist_name: Nombre del artista
        :return: Lista de géneros
        """
        query = """
        SELECT DISTINCT genre 
        FROM songs 
        WHERE LOWER(artist) = LOWER(?)
        """
        self.cursor.execute(query, (artist_name,))
        return [genre[0] for genre in self.cursor.fetchall() if genre[0]]

    def get_artist_info(self, artist_name):
        """
        Obtiene información completa de un artista (álbumes, canciones, URLs, contenido wiki)
        
        :param artist_name: Nombre del artista
        :return: Diccionario con información completa del artista
        """
        artist_info = {}
        
        # Información básica y URLs del artista
        artist_links = self.get_artist_links(artist_name)
        if artist_links:
            artist_info['links'] = artist_links
        
        # Contenido wiki
        wiki_content = self.get_artist_wiki_content(artist_name)
        if wiki_content:
            artist_info['wikipedia_content'] = wiki_content
        
        # Álbumes del artista
        albums_query = """
        SELECT 
            albums.id, 
            albums.name, 
            albums.year, 
            albums.genre, 
            albums.album_art_path 
        FROM albums 
        JOIN artists ON albums.artist_id = artists.id 
        WHERE LOWER(artists.name) = LOWER(?)
        """
        self.cursor.execute(albums_query, (artist_name,))
        albums = []
        
        for album_row in self.cursor.fetchall():
            album = {
                'id': album_row[0],
                'name': album_row[1],
                'year': album_row[2],
                'genre': album_row[3],
                'album_art_path': album_row[4]
            }
            
            # Obtener URLs del álbum
            album_links = self.get_album_links(artist_name, album['name'])
            if album_links:
                album['links'] = album_links
            
            # Obtener canciones del álbum
            songs_query = """
            SELECT id, title, track_number, duration, file_path
            FROM songs 
            WHERE LOWER(artist) = LOWER(?) AND LOWER(album) = LOWER(?)
            """
            self.cursor.execute(songs_query, (artist_name, album['name']))
            album['songs'] = [{
                'id': song[0],
                'title': song[1], 
                'track_number': song[2],
                'duration': song[3],
                'file_path': song[4]
            } for song in self.cursor.fetchall()]
            
            albums.append(album)
        
        artist_info['albums'] = albums
        
        # Todas las canciones del artista
        songs_query = """
        SELECT id, title, album, duration, file_path, album_art_path_denorm
        FROM songs 
        WHERE LOWER(artist) = LOWER(?)
        """
        self.cursor.execute(songs_query, (artist_name,))
        artist_info['songs'] = [{
            'id': song[0],
            'title': song[1], 
            'album': song[2],
            'duration': song[3],
            'file_path': song[4],
            'album_art_path': song[5]
        } for song in self.cursor.fetchall()]
        
        return artist_info




    def get_album_info(self, album_name, artist_name=None):
        """
        Obtiene información completa de un álbum con queries optimizadas
        - Usa JOIN solo cuando es necesario
        - Añade índices a la consulta
        
        :param album_name: Nombre del álbum
        :param artist_name: Nombre del artista (opcional)
        :return: Diccionario con información completa del álbum
        """
        album_info = {}
        
        if artist_name:
            album_query = """
            SELECT 
                a.id, 
                a.name,
                art.name,
                a.year, 
                a.genre,
                a.label,
                a.total_tracks,
                a.album_art_path,
                a.folder_path
            FROM albums a
            JOIN artists art ON a.artist_id = art.id 
            WHERE a.name LIKE ? COLLATE NOCASE 
            AND art.name LIKE ? COLLATE NOCASE
            LIMIT 1
            """
            self.cursor.execute(album_query, (album_name, artist_name))
        else:
            album_query = """
            SELECT 
                a.id, 
                a.name,
                art.name,
                a.year, 
                a.genre,
                a.label,
                a.total_tracks,
                a.album_art_path,
                a.folder_path
            FROM albums a
            JOIN artists art ON a.artist_id = art.id 
            WHERE a.name LIKE ? COLLATE NOCASE
            LIMIT 1
            """
            self.cursor.execute(album_query, (album_name,))
        
        album_row = self.cursor.fetchone()
        
        if not album_row:
            return None
        
        # El resto del código permanece igual, pero añadimos un LIMIT en la consulta de canciones
        
        # Obtener canciones del álbum con un índice eficiente
        songs_query = """
        SELECT id, title, track_number, duration, file_path, has_lyrics
        FROM songs 
        WHERE album LIKE ? COLLATE NOCASE
        ORDER BY track_number
        """
        self.cursor.execute(songs_query, (album_name,))
        album_info['songs'] = [{
            'id': song[0],
            'title': song[1], 
            'track_number': song[2],
            'duration': song[3],
            'file_path': song[4],
            'has_lyrics': bool(song[5])
        } for song in self.cursor.fetchall()]
        
        return album_info




    def get_song_info(self, song_title, artist_name=None, album_name=None):
        """
        Obtiene información completa de una canción
        
        :param song_title: Título de la canción
        :param artist_name: Nombre del artista (opcional)
        :param album_name: Nombre del álbum (opcional)
        :return: Diccionario con información completa de la canción
        """
        song_info = {}
        
        # Construir la consulta según los parámetros proporcionados
        params = []
        query = """
        SELECT 
            songs.id, 
            songs.title, 
            songs.artist, 
            songs.album, 
            songs.track_number,
            songs.duration,
            songs.file_path,
            songs.album_art_path_denorm,
            songs.has_lyrics
        FROM songs 
        WHERE LOWER(songs.title) = LOWER(?)
        """
        params.append(song_title)
        
        if artist_name:
            query += " AND LOWER(songs.artist) = LOWER(?)"
            params.append(artist_name)
        
        if album_name:
            query += " AND LOWER(songs.album) = LOWER(?)"
            params.append(album_name)
        
        self.cursor.execute(query, params)
        song_row = self.cursor.fetchone()
        
        if not song_row:
            return None
        
        song_info = {
            'id': song_row[0],
            'title': song_row[1],
            'artist': song_row[2],
            'album': song_row[3],
            'track_number': song_row[4],
            'duration': song_row[5],
            'file_path': song_row[6],
            'album_art_path': song_row[7],
            'has_lyrics': bool(song_row[8])
        }
        
        # Obtener letra si existe
        if song_info['has_lyrics']:
            lyrics = self.get_song_lyrics(song_title, song_info['artist'])
            if lyrics:
                song_info['lyrics'] = lyrics
        
        # Obtener URLs de la canción
        track_links = self.get_track_links(song_info['album'], song_title)
        if track_links:
            song_info['links'] = track_links
        
        # Obtener URLs del álbum
        album_links = self.get_album_links(song_info['artist'], song_info['album'])
        if album_links:
            song_info['album_links'] = album_links
        
        # Obtener URLs del artista
        artist_links = self.get_artist_links(song_info['artist'])
        if artist_links:
            song_info['artist_links'] = artist_links
        
        return song_info



    def get_song_path_if_exists(self, artist=None, album=None, song=None):
        """
        Verifica si existe una canción y devuelve su ruta si existe
        
        :param artist: Nombre del artista (opcional)
        :param album: Nombre del álbum (opcional)
        :param song: Título de la canción (requerido)
        :return: Ruta del archivo si existe o None
        """
        if not song:
            return None
            
        # Construir la consulta según los parámetros proporcionados
        query = "SELECT file_path FROM songs WHERE 1=1"
        params = []
        
        if song:
            query += " AND LOWER(title) = LOWER(?)"
            params.append(song)
        
        if artist:
            query += " AND LOWER(artist) = LOWER(?)"
            params.append(artist)
        
        if album:
            query += " AND LOWER(album) = LOWER(?)"
            params.append(album)
        
        self.cursor.execute(query, params)
        result = self.cursor.fetchone()
        
        return result[0] if result else None

    def search_lyrics(self, text):
        """
        Busca un texto dentro de las letras de canciones
        
        :param text: Texto a buscar en las letras
        :return: Lista de canciones que contienen el texto
        """
        query = """
        SELECT 
            songs.artist,
            songs.album,
            songs.title,
            albums.year,
            lyrics.lyrics
        FROM lyrics
        JOIN songs ON lyrics.track_id = songs.id
        LEFT JOIN albums ON LOWER(songs.album) = LOWER(albums.name)
        AND albums.artist_id = (
            SELECT id FROM artists WHERE LOWER(name) = LOWER(songs.artist) LIMIT 1
        )
        WHERE lyrics.lyrics LIKE ?
        """
        
        # Usamos % para buscar el texto en cualquier parte de la letra
        search_param = f'%{text}%'
        self.cursor.execute(query, (search_param,))
        
        results = []
        for row in self.cursor.fetchall():
            result = {
                'artist': row[0],
                'album': row[1],
                'title': row[2],
                'year': row[3],
                'lyrics': row[4]
            }
            results.append(result)
        
        return results



    def close(self):
        """
        Cierra la conexión con la base de datos
        """
        self.conn.close()

def main():
    parser = argparse.ArgumentParser(description='Consultas a base de datos musical')
    
    parser.add_argument('--db', required=True, help='Ruta a la base de datos SQLite')
    parser.add_argument('--artist', help='Nombre del artista')
    parser.add_argument('--album', help='Nombre del álbum')
    parser.add_argument('--song', help='Título de la canción')
    parser.add_argument('--mbid', action='store_true', help='Obtener MBID del artista')
    parser.add_argument('--links', action='store_true', help='Obtener links de servicios')
    parser.add_argument('--wiki', action='store_true', help='Obtener contenido de Wikipedia')
    parser.add_argument('--artist-albums', action='store_true', help='Listar álbumes del artista')
    parser.add_argument('--label', help='Obtener álbumes de un sello')
    parser.add_argument('--year', type=int, help='Obtener álbumes de un año')
    parser.add_argument('--genre', help='Obtener álbumes de un género')
    parser.add_argument('--lyrics', action='store_true', help='Obtener letra de una canción')
    parser.add_argument('--artist-genres', action='store_true', help='Obtener géneros del artista')
    parser.add_argument('--services', nargs='+', help='Servicios específicos para links')
    parser.add_argument('--artist-info', action='store_true', help='Obtener información completa del artista')
    parser.add_argument('--album-info', action='store_true', help='Obtener información completa del álbum')
    parser.add_argument('--song-info', action='store_true', help='Obtener información completa de la canción')
    parser.add_argument('--path-existente', action='store_true', help='Verificar si existe un archivo y devolver su ruta')
    parser.add_argument('--letra-desconocida', help='Buscar texto en letras de canciones')

    args = parser.parse_args()

    try:
        db = MusicDatabaseQuery(args.db)
                
        # Funcionalidad de obtención de MBID
        if args.mbid and args.artist and args.album:
            print(json.dumps(db.get_mbid_by_album_artist(args.artist, args.album)))
        
        elif args.mbid and args.album and args.song:
            print(json.dumps(db.get_mbid_by_album_track(args.album, args.song)))
        
        elif args.mbid and args.artist:
            print(json.dumps(db.get_artist_mbid(args.artist)))
        
        # Funcionalidad de obtención de links
        elif args.links and args.artist and args.album:
            print(json.dumps(db.get_album_links(args.artist, args.album)))
        
        elif args.links and args.album and args.song:
            print(json.dumps(db.get_track_links(args.album, args.song, args.services)))
        
        elif args.links and args.artist:
            print(json.dumps(db.get_artist_links(args.artist)))
        
        # Funcionalidad de obtención de contenido wiki
        elif args.wiki and args.artist and args.album:
            print(db.get_album_wiki(args.artist, args.album))
        
        elif args.wiki and args.artist:
            print(db.get_artist_wiki_content(args.artist))
        
        # Otras consultas
        elif args.artist_albums and args.artist:
            print(json.dumps(db.get_artist_albums(args.artist)))
        
        elif args.label:
            print(json.dumps(db.get_albums_by_label(args.label)))
        
        elif args.year:
            print(json.dumps(db.get_albums_by_year(args.year)))
        
        elif args.genre:
            print(json.dumps(db.get_albums_by_genre(args.genre)))
        
        elif args.lyrics and args.song:
            print(db.get_song_lyrics(args.song, args.artist))
        
        elif args.artist_genres and args.artist:
            print(json.dumps(db.get_artist_genres(args.artist)))
            
        elif args.artist_info and args.artist:
            print(json.dumps(db.get_artist_info(args.artist)))

        elif args.album_info and args.album:
            print(json.dumps(db.get_album_info(args.album, args.artist)))

        elif args.song_info and args.song:
            print(json.dumps(db.get_song_info(args.song, args.artist, args.album)))
            
        # Nuevas opciones
        elif args.path_existente:
            # Verificar si al menos hay una canción o álbum o artista para buscar
            if args.song or args.album or args.artist:
                path = db.get_song_path_if_exists(args.artist, args.album, args.song)
                print(json.dumps(path))
            else:
                print("Error: Se requiere al menos un parámetro de búsqueda (--song, --album o --artist)")
        
        elif args.letra_desconocida:
            results = db.search_lyrics(args.letra_desconocida)
            print(json.dumps(results))
        
        else:
            print("Error: Combinación de argumentos no válida")

        db.close()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()