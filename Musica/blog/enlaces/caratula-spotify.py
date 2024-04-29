import requests
import base64
import sys

def get_access_token(client_id, client_secret):
    # Codificar el client_id y client_secret en base64
    encoded = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    # Hacer la solicitud POST para obtener el token de acceso
    response = requests.post(
        "https://accounts.spotify.com/api/token",
        headers={"Authorization": f"Basic {encoded}"},
        data={"grant_type": "client_credentials"}
    )

    # Extraer y devolver el token de acceso
    return response.json()["access_token"]

def get_album_cover(album_name, artist_name, access_token):
    # Realizar una búsqueda de álbumes en la API de Spotify
    response = requests.get(
        "https://api.spotify.com/v1/search",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"q": f"album:{album_name} artist:{artist_name}", "type": "album"}
    )

    # Extraer el enlace de la imagen de la carátula del primer álbum encontrado
    try:
        album_id = response.json()["albums"]["items"][0]["id"]
        cover_url = response.json()["albums"]["items"][0]["images"][0]["url"]
        return cover_url
    except IndexError:
        return None

def download_album_cover(album_name, artist_name, client_id, client_secret):
    # Obtener el token de acceso
    access_token = get_access_token(client_id, client_secret)

    # Obtener la URL de la carátula del álbum
    cover_url = get_album_cover(album_name, artist_name, access_token)

    if cover_url:
        # Descargar la carátula
        response = requests.get(cover_url)
        with open(f"image.jpeg", "wb") as f:
            f.write(response.content)
        print("Carátula descargada exitosamente.")
    else:
        print("No se encontró la carátula del álbum.")

if __name__ == "__main__":
    # Inserta aquí tus credenciales de la API de Spotify
    client_id = "1240f125bd9e43c4b1202989cf20fa5b"
    client_secret = "fcb63ee0897940f1bbef102582cda3ff"

    # Inserta aquí el nombre del álbum y el nombre del artista
    album_name = sys.argv[2]
    artist_name = sys.argv[1]

    # Descargar la carátula del álbum
    download_album_cover(album_name, artist_name, client_id, client_secret)
