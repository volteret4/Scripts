import requests
from bs4 import BeautifulSoup
import sys

def get_album_info(artist_name, album_name):
    try:
        # Construye la URL de búsqueda en Bandcamp
        search_url = f"https://bandcamp.com/search?q={artist_name.replace(' ', '-')}+{album_name.replace(' ', '-')}"

        # Realiza la solicitud GET a Bandcamp y obtiene el contenido HTML
        response = requests.get(search_url)
        response.raise_for_status()  # Lanza una excepción si hay un error en la solicitud
        html_content = response.text

        # Analiza el HTML con BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')

        # Encuentra la etiqueta <a> dentro de la clase "itemurl"
        album_link_tag = soup.find("div", class_="itemurl").find("a")

        # Obtiene el enlace al álbum si se encontró la etiqueta
        album_link = album_link_tag["href"] if album_link_tag else None

        return album_link

    except requests.exceptions.RequestException as e:
        print("Error al hacer la solicitud a Bandcamp:", e)
        return None

if __name__ == "__main__":
    # Verifica que se pasen los argumentos correctos
    if len(sys.argv) != 3:
        print("Uso: python bandcamp_scraper.py <artista> <álbum>")
        sys.exit(1)

    # Obtén los argumentos del artista y el álbum de la línea de comandos
    artist_name = sys.argv[1]
    album_name = sys.argv[2]

    # Obtiene el enlace del álbum especificado en Bandcamp
    album_link = get_album_info(artist_name, album_name)

    if album_link:
        print(f"{album_link}")
