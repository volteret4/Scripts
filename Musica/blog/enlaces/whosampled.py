import sys
import requests
from lxml import html

def buscar_artist(artist):
    # Formatear la URL de búsqueda en WhoSampled
    url = f"https://www.whosampled.com/search/?q={artist}"

    # Realizar la solicitud GET a la página del artista
    response = requests.get(url)

    # Verificar si la solicitud fue exitosa
    if response.status_code == 200:
        # Parsear el HTML de la página
        tree = html.fromstring(response.content)

        # Extraer la URL del artista utilizando XPath
        artist_url = tree.xpath('/html/body/div/main/div[3]/div/div[1]/div[3]/div[2]/a/@href')
        if artist_url:
            return "https://www.whosampled.com" + artist_url[0]

    return None

# Ejemplo de uso
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python script.py <nombre_del_artista>")
        sys.exit(1)

    artist = sys.argv[1]

    artist_url = buscar_artist(artist)
    if artist_url:
        print(artist_url)
#    else:
#        print("No se encontró información sobre el artista en WhoSampled.")

