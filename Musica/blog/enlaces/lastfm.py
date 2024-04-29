import requests
import sys

def get_album_info(artist_name, album_name):
    # Define la URL base de la API de Last.fm y tu API key
    base_url = "http://ws.audioscrobbler.com/2.0/"
    api_key = "5fa1d91a9fd9c425b3c584911d893ae8"

    # Construye la URL para buscar el álbum por artista y nombre de álbum
    search_url = f"{base_url}?method=album.search&album={album_name}&artist={artist_name}&api_key={api_key}&format=json"

    try:
        # Realiza la solicitud GET a la API de Last.fm
        response = requests.get(search_url)
        response.raise_for_status()  # Lanza una excepción si hay un error en la solicitud

        # Analiza la respuesta JSON
        data = response.json()

        # Comprueba si se encontraron resultados
        if not data["results"]["albummatches"]["album"]:
            print("No se encontraron resultados para el álbum especificado.")
            return None

        # Obtiene la URL del álbum del primer resultado
        album_url = data["results"]["albummatches"]["album"][0]["url"]

        return album_url

    except requests.exceptions.RequestException as e:
        print("Error al hacer la solicitud a la API de Last.fm:", e)
        return None

if __name__ == "__main__":
    # Verifica que se pasen los argumentos correctos
    if len(sys.argv) != 3:
        print("Uso: python lastfm_api.py <artista> <álbum>")
        sys.exit(1)

    # Obtén los argumentos del artista y el álbum de la línea de comandos
    artist_name = sys.argv[1]
    album_name = sys.argv[2]

    # Obtiene la URL del álbum especificado
    album_url = get_album_info(artist_name, album_name)

    if album_url:
        print(f"{album_url}")
