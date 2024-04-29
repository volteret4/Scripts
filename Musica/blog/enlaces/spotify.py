import requests
import sys
import base64

def get_access_token(client_id, client_secret):
    try:
        # Construye las credenciales codificadas en base64
        credentials = f"{client_id}:{client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()

        # Construye el cuerpo de la solicitud para obtener el token de acceso
        data = {"grant_type": "client_credentials"}
        headers = {"Authorization": f"Basic {encoded_credentials}"}

        # Realiza la solicitud POST para obtener el token de acceso
        response = requests.post("https://accounts.spotify.com/api/token", data=data, headers=headers)
        response.raise_for_status()  # Lanza una excepción si hay un error en la solicitud
        access_token = response.json()["access_token"]

        return access_token

    except requests.exceptions.RequestException as e:
        print("Error al obtener el token de acceso:", e)
        return None

def search_album(artist_name, album_name, access_token):
    try:
        # Construye la URL de búsqueda en la API de Spotify
        search_url = f"https://api.spotify.com/v1/search?q=album:{album_name} artist:{artist_name}&type=album"

        # Realiza la solicitud GET a la API de Spotify
        response = requests.get(search_url, headers={"Authorization": f"Bearer {access_token}"})
        response.raise_for_status()  # Lanza una excepción si hay un error en la solicitud
        data = response.json()

        # Encuentra el primer resultado de álbum
        if "albums" in data and "items" in data["albums"] and len(data["albums"]["items"]) > 0:
            album_url = data["albums"]["items"][0]["external_urls"]["spotify"]
            return album_url
        else:
#            print("No se encontraron resultados para el álbum especificado.")
            return None

    except requests.exceptions.RequestException as e:
        print("Error al hacer la solicitud a la API de Spotify:", e)
        return None

if __name__ == "__main__":
    # Verifica que se pasen los argumentos correctos
    if len(sys.argv) != 3:
        print("Uso: python spotify_api.py <artista> <álbum> <client_id> <client_secret>")
        sys.exit(1)

    # Obtén los argumentos del artista, el álbum, el Client ID y el Client Secret de la línea de comandos
    artist_name = sys.argv[1]
    album_name = sys.argv[2]
    client_id = "1240f125bd9e43c4b1202989cf20fa5b"
    client_secret = "fcb63ee0897940f1bbef102582cda3ff"

    # Obtiene el token de acceso de Spotify
    access_token = get_access_token(client_id, client_secret)

    if access_token:
        # Busca el álbum y obtén su URL en Spotify
        album_url = search_album(artist_name, album_name, access_token)

        if album_url:
            print(f"{album_url}")
