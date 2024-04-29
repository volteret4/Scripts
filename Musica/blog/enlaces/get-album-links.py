import requests
import sys

def buscar_album(artist, album, api_key):
    url = "https://api.discogs.com/database/search"
    params = {
        "artist": artist,
        "release_title": album,
        "token": api_key
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()
        master_url = data["results"][0]["master_url"]
        return master_url
    except Exception as e:
        print("Error al buscar el álbum:", e)
        return None

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python script.py <artista> <álbum> <clave API de Discogs>")
        sys.exit(1)

    artist = sys.argv[1]
    album = sys.argv[2]
    api_key = "rJrVnScnzBmzrmDvhDYAXspwkfuacuHfUWnkhXmK"

    url_master_release = buscar_album(artist, album, api_key)
    if url_master_release:
        print("URL del master release:", url_master_release)
    else:
        print("No se pudo encontrar el álbum.")
