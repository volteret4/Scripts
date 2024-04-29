from googleapiclient.discovery import build
import sys

def buscar_playlist(artist, album, api_key):
    youtube = build('youtube', 'v3', developerKey=api_key)

    # Realizar la búsqueda de videos relacionados con el artista y el álbum
    search_response = youtube.search().list(
        q=f'{artist} {album} playlist',
        part='id',
        maxResults=5
    ).execute()

    # Obtener el ID de la playlist si se encuentra
    for item in search_response['items']:
        if item['id']['kind'] == 'youtube#playlist':
            playlist_id = item['id']['playlistId']
            return f'https://www.youtube.com/playlist?list={playlist_id}'

    return None

# Ejemplo de uso
if __name__ == "__main__":
    artist = sys.argv[1]
    album = sys.argv[2]
    api_key = "AIzaSyA-oDQyAiUHCX65dOp0920b3483mcc2SB4"

    url_playlist = buscar_playlist(artist, album, api_key)
    if url_playlist:
        print(url_playlist)
#    else:
#      print("No se encontró ninguna playlist.")
