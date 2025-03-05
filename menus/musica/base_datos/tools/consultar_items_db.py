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
        Obtiene el MBID de un álbum por artista
        
        :param artist: Nombre del artista
        :param album: Nombre del álbum
        :return: MBID del álbum o None si no se encuentra
        """
        query = """
        SELECT mbid FROM albums 
        JOIN artists ON albums.artist_id = artists.id 
        WHERE artists.name = ? AND albums.name = ?
        """
        self.cursor.execute(query, (artist, album))
        result = self.cursor.fetchone()
        return result[0] if result else None

    def get_mbid_by_album_track(self, album, track):
        """
        Obtiene el MBID de una canción en un álbum
        
        :param album: Nombre del álbum
        :param track: Nombre de la canción
        :return: MBID de la canción o None si no se encuentra
        """
        query = """
        SELECT songs.mbid FROM songs 
        JOIN albums ON songs.album_id = albums.id 
        WHERE albums.name = ? AND songs.title = ?
        """
        self.cursor.execute(query, (album, track))
        result = self.cursor.fetchone()
        return result[0] if result else None

    def get_album_links(self, artist, album):
        """
        Obtiene los links de servicios para un álbum
        
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
        WHERE albums.name = ?
        """
        self.cursor.execute(query, (album,))
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
        Obtiene los links de servicios para una canción
        
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
        FROM songs 
        JOIN song_links ON songs.id = song_links.song_id
        WHERE songs.album = ? AND songs.title = ?
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
        Obtiene el contenido de Wikipedia para un álbum
        
        :param artist: Nombre del artista
        :param album: Nombre del álbum
        :return: Contenido de Wikipedia o None
        """
        query = """
        SELECT albums.wikipedia_content 
        FROM albums 
        JOIN artists ON albums.artist_id = artists.id
        WHERE artists.name = ? AND albums.name = ?
        """
        self.cursor.execute(query, (artist, album))
        result = self.cursor.fetchone()
        return result[0] if result else None

    # Resto de métodos de la clase original...

    def close(self):
        """
        Cierra la conexión con la base de datos
        """
        self.conn.close()

    def get_artist_mbid(self, artist_name):
        """
        Obtiene el MBID de un artista
        
        :param artist_name: Nombre del artista
        :return: MBID del artista o None si no se encuentra
        """
        query = "SELECT mbid FROM artists WHERE name = ?"
        self.cursor.execute(query, (artist_name,))
        result = self.cursor.fetchone()
        return result[0] if result else None

    def get_artist_links(self, artist_name):
        """
        Obtiene los links de servicios para un artista
        
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
        FROM artists WHERE name = ?
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
        Obtiene el contenido de Wikipedia para un artista
        
        :param artist_name: Nombre del artista
        :return: Contenido de Wikipedia o None
        """
        query = "SELECT wikipedia_content FROM artists WHERE name = ?"
        self.cursor.execute(query, (artist_name,))
        result = self.cursor.fetchone()
        return result[0] if result else None

    def get_artist_albums(self, artist_name):
        """
        Obtiene los álbumes de un artista
        
        :param artist_name: Nombre del artista
        :return: Lista de álbumes
        """
        query = """
        SELECT albums.name, albums.year, albums.genre 
        FROM albums 
        JOIN artists ON albums.artist_id = artists.id 
        WHERE artists.name = ?
        """
        self.cursor.execute(query, (artist_name,))
        return self.cursor.fetchall()

    def get_albums_by_label(self, label):
        """
        Obtiene álbumes de un sello discográfico
        
        :param label: Nombre del sello
        :return: Lista de álbumes
        """
        query = "SELECT name, artist, year FROM albums WHERE label = ?"
        self.cursor.execute(query, (label,))
        return self.cursor.fetchall()

    def get_albums_by_year(self, year):
        """
        Obtiene álbumes de un año específico
        
        :param year: Año de los álbumes
        :return: Lista de álbumes
        """
        query = "SELECT name, artist, genre FROM albums WHERE year = ?"
        self.cursor.execute(query, (str(year),))
        return self.cursor.fetchall()

    def get_albums_by_genre(self, genre):
        """
        Obtiene álbumes de un género específico
        
        :param genre: Género musical
        :return: Lista de álbumes
        """
        query = "SELECT name, artist, year FROM albums WHERE genre = ?"
        self.cursor.execute(query, (genre,))
        return self.cursor.fetchall()

    def get_song_lyrics(self, song_title, artist_name=None):
        """
        Obtiene la letra de una canción
        
        :param song_title: Título de la canción
        :param artist_name: Nombre del artista (opcional)
        :return: Letra de la canción o None
        """
        if artist_name:
            query = """
            SELECT lyrics.lyrics 
            FROM lyrics 
            JOIN songs ON lyrics.track_id = songs.id 
            WHERE songs.title = ? AND songs.artist = ?
            """
            self.cursor.execute(query, (song_title, artist_name))
        else:
            query = """
            SELECT lyrics.lyrics 
            FROM lyrics 
            JOIN songs ON lyrics.track_id = songs.id 
            WHERE songs.title = ?
            """
            self.cursor.execute(query, (song_title,))
        
        result = self.cursor.fetchone()
        return result[0] if result else None

    def get_artist_genres(self, artist_name):
        """
        Obtiene los géneros de un artista
        
        :param artist_name: Nombre del artista
        :return: Lista de géneros
        """
        query = """
        SELECT DISTINCT genre 
        FROM songs 
        WHERE artist = ?
        """
        self.cursor.execute(query, (artist_name,))
        return [genre[0] for genre in self.cursor.fetchall() if genre[0]]

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

    args = parser.parse_args()

    try:
        db = MusicDatabaseQuery(args.db)
        # Nueva funcionalidad de obtención de MBID
        if args.mbid and args.artist and args.album:
            print(json.dumps(db.get_mbid_by_album_artist(args.artist, args.album)))
        
        if args.mbid and args.album and args.song:
            print(json.dumps(db.get_mbid_by_album_track(args.album, args.song)))
        
        # Nueva funcionalidad de obtención de links
        if args.links is not None and args.artist and args.album:
            print(json.dumps(db.get_album_links(args.artist, args.album)))
        
        if args.links is not None and args.album and args.song:
            print(json.dumps(db.get_track_links(args.album, args.song, args.links)))
        
        # Nueva funcionalidad de obtención de wiki de álbum
        if args.wiki and args.artist and args.album:
            print(db.get_album_wiki(args.artist, args.album))

        if args.mbid and args.artist:
            print(json.dumps(db.get_artist_mbid(args.artist)))
        
        if args.links and args.artist:
            print(json.dumps(db.get_artist_links(args.artist)))
        
        if args.wiki and args.artist:
            print(db.get_artist_wiki_content(args.artist))
        
        if args.artist_albums and args.artist:
            print(json.dumps(db.get_artist_albums(args.artist)))
        
        if args.label:
            print(json.dumps(db.get_albums_by_label(args.label)))
        
        if args.year:
            print(json.dumps(db.get_albums_by_year(args.year)))
        
        if args.genre:
            print(json.dumps(db.get_albums_by_genre(args.genre)))
        
        if args.lyrics and args.song:
            print(db.get_song_lyrics(args.song, args.artist))
        
        if args.artist_genres and args.artist:
            print(json.dumps(db.get_artist_genres(args.artist)))

        db.close()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()