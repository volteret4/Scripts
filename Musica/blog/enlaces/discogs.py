import requests
import sys

def get_master_release_id(artist_name, album_name):
    # Define la URL base de la API de Discogs y tu token de autenticación
    base_url = "https://api.discogs.com"
    token = "LspjLeBvGcPphiSRHHDjwmOyPNhSuvBKQChNwucQ"

    # Construye la URL para buscar el álbum por artista y nombre de álbum
    search_url = f"{base_url}/database/search?q={artist_name} {album_name}&type=master&token={token}"

    try:
        # Realiza la solicitud GET a la API de Discogs
        response = requests.get(search_url)
        response.raise_for_status()  # Lanza una excepción si hay un error en la solicitud

        # Analiza la respuesta JSON
        data = response.json()

        # Comprueba si se encontraron resultados
        if data['pagination']['items'] == 0:
            print("No se encontraron resultados para el álbum especificado.")
            return None

        # Obtiene el ID del master release del primer resultado
        master_release_id = data['results'][0]['id']

        return master_release_id

    except requests.exceptions.RequestException as e:
        print("Error al hacer la solicitud a la API de Discogs:", e)
        return None

if __name__ == "__main__":
    # Verifica que se pasen los argumentos correctos
    if len(sys.argv) != 3:
        print("Uso: python discogs_api.py <artista> <álbum>")
        sys.exit(1)

    # Obtén los argumentos del artista y el álbum de la línea de comandos
    artist_name = sys.argv[1]
    album_name = sys.argv[2]

    # Obtiene el ID del master release del álbum especificado
    master_release_id = get_master_release_id(artist_name, album_name)

    if master_release_id:
        print(f"https://www.discogs.com/master/{master_release_id}")
