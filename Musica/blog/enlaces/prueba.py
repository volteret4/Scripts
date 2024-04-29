import requests

def buscar_artist(artist):
    # Formatear la URL de búsqueda en WhoSampled
    url = f"https://www.whosampled.com/search/?q={artist}"

    # Realizar la solicitud GET a la página del artista
    response = requests.get(url)

    # Verificar si la solicitud fue exitosa
#    if response.status_code == 200:
        # Imprimir el contenido HTML de la página para depuración
    print(response.text)

        # Continuar con el análisis del HTML y la extracción de la URL del artista
        # ...

# Ejemplo de uso
if __name__ == "__main__":
    artist = input("Ingrese el nombre del artista: ")

    buscar_artist(artist)
