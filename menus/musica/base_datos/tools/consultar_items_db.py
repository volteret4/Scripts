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