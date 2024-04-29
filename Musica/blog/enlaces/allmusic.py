import requests
from bs4 import BeautifulSoup
import sys

def get_album_info(artist_name, album_name):
    try:
        # Construye la URL de búsqueda en AllMusic
        search_url = f"https://www.allmusic.com/search/albums/{album_name} {artist_name}"

        # Realiza la solicitud GET a AllMusic y obtiene el contenido HTML
        response = requests.get(search_url)
        response.raise_for_status()  # Lanza una excepción si hay un error en la solicitud
        html_content = response.text
        
        print(html_content)  # Imprimir el contenido HTML para depuración

        # Analiza el HTML con BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')

        # Encuentra el primer resultado de álbum
        album_result = soup.find("section", class_="search-results").find("a")

        # Obtiene el enlace al álbum
        album_url = album_result["href"] if album_result else None

        return album_url

    except requests.exceptions.RequestException as e:
        print("Error al hacer la solicitud a AllMusic:", e)
        return None

if __name__ == "__main__":
    # Verifica que se pasen los argumentos correctos
    if len(sys.argv) != 3:
        print("Uso: python allmusic_scraper.py <artista> <álbum>")
        sys.exit(1)

    # Obtén los argumentos del artista y el álbum de la línea de comandos
    artist_name = sys.argv[1]
    album_name = sys.argv[2]

    # Obtiene la URL del álbum especificado en AllMusic
    album_url = get_album_info(artist_name, album_name)

    if album_url:
        print(f"Enlace al álbum '{album_name}' de '{artist_name}' en AllMusic: {album_url}")
