#!/usr/bin/env python3

import sys
import requests
import sqlite3
from bs4 import BeautifulSoup

def get_youtube_video_info(video_url):
    response = requests.get(video_url)
    soup = BeautifulSoup(response.text, 'html.parser')

    title = soup.find("meta", {"property": "og:title"})["content"]
    thumbnail_url = soup.find("meta", {"property": "og:image"})["content"]

    return title, thumbnail_url

def get_bandcamp_album_info(album_url):
    response = requests.get(album_url)
    soup = BeautifulSoup(response.text, 'html.parser')

    title = soup.find('h2', {'class': 'trackTitle'}).text.strip()
    thumbnail_url = soup.find('a', {'class': 'popupImage'}).find('img')['src']

    return title, thumbnail_url

def add_album_to_playlist(conn, playlist_id, title, album_url, thumbnail_url):
    cursor = conn.cursor()

    # Insertar la entrada del álbum en la tabla de streams
    cursor.execute("""
        INSERT INTO stream (title, url, thumbnail_url)
        VALUES (?, ?, ?)
    """, (title, album_url, thumbnail_url))
    stream_id = cursor.lastrowid

    # Obtener el índice máximo actual en la tabla playlist_stream_join para la playlist dada
    cursor.execute("""
        SELECT MAX(join_index) FROM playlist_stream_join WHERE pid = ?
    """, (playlist_id,))
    current_max_join_index = cursor.fetchone()[0]

    # Si no hay entradas en la playlist, establecer join_index en 0, de lo contrario incrementar en 1
    join_index = 0 if current_max_join_index is None else current_max_join_index + 1

    # Insertar la relación entre la playlist y la entrada del álbum en la tabla playlist_stream_join
    cursor.execute("""
        INSERT INTO playlist_stream_join (pid, sid, join_index)
        VALUES (?, ?, ?)
    """, (playlist_id, stream_id, join_index))

    conn.commit()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Por favor, proporciona la URL del álbum como argumento.")
        sys.exit(1)

    album_url = sys.argv[1]

    if "youtube.com" in album_url or "youtu.be" in album_url:
        title, thumbnail_url = get_youtube_video_info(album_url)
    elif "bandcamp.com" in album_url:
        title, thumbnail_url = get_bandcamp_album_info(album_url)
    else:
        print("URL no válida. Por favor, proporciona una URL de YouTube o Bandcamp.")
        sys.exit(1)

    database_path = "/home/huan/Documentos/newpipe.db"
    conn = sqlite3.connect(database_path)

    playlist_id = 17  # Reemplaza esto con el ID de la lista de reproducción que deseas modificar
    add_album_to_playlist(conn, playlist_id, title, album_url, thumbnail_url)

    conn.close()

    print("Título:", title)
    print("URL de la miniatura:", thumbnail_url)
    print("Álbum añadido a la lista de reproducción con éxito.")