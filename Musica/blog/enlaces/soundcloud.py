import requests
from bs4 import BeautifulSoup
import sys

def get_soundcloud_album(url):
    try:
        # Realiza la solicitud GET a la URL específica en SoundCloud y obtiene el contenido HTML
        response = requests.get(url)
        response.raise_for_status()  # Lanza una excepción si hay un error en la solicitud
        html_content = response.text

        # Analiza el HTML con BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')

        # Encuentra el primer enlace al álbum utilizando el selector CSS proporcionado
        album_link_tag = soup.select_one("#content > div > div > div.l-main > div > div > div > ul > li:nth-child(2) > div > div > div > div.sound__content > div.sound__header.sc-mb-1\\.5x.sc-px-2x > div > div > div.soundTitle__usernameTitleContainer.sc-mb-0\\.5x > a")

        # Si se encuentra la etiqueta <a>, obtén su enlace
        if album_link_tag:
            album_link = album_link_tag['href']
            return album_link
        else:
            print("No se encontró el enlace al álbum en la página.")
            return None

    except requests.exceptions.RequestException as e:
        print("Error al hacer la solicitud a SoundCloud:", e)
        return None

if __name__ == "__main__":
    # Verifica que se pase la URL correcta como argumento
    if len(sys.argv) != 2:
        print("Uso: python soundcloud_scraper.py <URL>")
        sys.exit(1)

    # Obtén la URL de la línea de comandos
    url = sys.argv[1]

    # Obtiene el enlace al álbum especificado en SoundCloud
    album_link = get_soundcloud_album(url)

    if album_link:
        print(f"Enlace al álbum en SoundCloud: {album_link}")
    else:
        print("No se encontró el enlace al álbum en SoundCloud.")
