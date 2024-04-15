import requests
from datetime import datetime
import xml.etree.ElementTree as ET
from dotenv import load_dotenv



def get_user_info(username, api_key):
    # URL de la API de Last.fm para obtener información del usuario
    url = f"http://ws.audioscrobbler.com/2.0/?method=user.getinfo&user={username}&api_key={api_key}&format=json"
    
    try:
        # Realizar la solicitud GET a la API de Last.fm
        response = requests.get(url)
        data = response.json()

        # Verificar si la solicitud fue exitosa
        if response.status_code == 200:
            # Obtener el número total de scrobbles del usuario
            total_scrobbles = int(data['user']['playcount'])
            return total_scrobbles
        else:
            print(f"Error: {data['message']}")
            return None
    except Exception as e:
        print(f"Error al consultar la API de Last.fm: {e}")
        return None

def get_artist_count(username, api_key):
    # Parámetros iniciales
    page = 1
    limit = 1000  # Este límite puede ser ajustado según tus necesidades

    total_artists = []
    
    while True:
        # URL de la API de Last.fm para obtener la lista de artistas escuchados por el usuario
        url = f"http://ws.audioscrobbler.com/2.0/?method=user.gettopartists&user={username}&api_key={api_key}&format=json&page={page}&limit={limit}"
        
        try:
            # Realizar la solicitud GET a la API de Last.fm
            response = requests.get(url)
            data = response.json()

            # Verificar si la solicitud fue exitosa
            if response.status_code == 200:
                # Obtener la lista de artistas en la página actual
                artists = data['topartists']['artist']
                total_artists.extend(artists)
                
                # Si la cantidad de artistas obtenidos en esta página es menor que el límite,
                # significa que no hay más páginas y podemos terminar el bucle.
                if len(artists) < limit:
                    break
                
                # Incrementar el número de página para obtener la siguiente página de resultados
                page += 1
            else:
                print(f"Error: {data['message']}")
                return None
        except Exception as e:
            print(f"Error al consultar la API de Last.fm: {e}")
            return None

    return len(total_artists)

def get_recent_tracks(username, api_key):
    # Obtener la fecha de hoy en el formato requerido por la API de Last.fm
    today_date = datetime.now().strftime("%d %b %Y").lower()

    # URL de la API de Last.fm para obtener las pistas escuchadas recientemente por el usuario
    url = f"http://ws.audioscrobbler.com/2.0/?method=user.getrecenttracks&user={username}&api_key={api_key}&format=xml"

    try:
        # Realizar la solicitud GET a la API de Last.fm
        response = requests.get(url)

        # Verificar si la solicitud fue exitosa
        if response.status_code == 200:
            # Parsear la respuesta XML
            root = ET.fromstring(response.text)

            # Filtrar las pistas escuchadas hoy
            today_tracks = []
            for track in root.findall('.//track'):
                date_element = track.find('date')
                if date_element is not None and date_element.text.lower().startswith(today_date):
                    artist = track.find('artist').text
                    song = track.find('name').text
                    today_tracks.append(f"{artist} - {song}")

            return today_tracks
        else:
            print(f"Error: {response.text}")
            return None
    except Exception as e:
        print(f"Error al consultar la API de Last.fm: {e}")
        return None

def main():
    load_dotenv()
    
    # Configuración: ingresa aquí tu nombre de usuario y tu API key de Last.fm
    username = os.getenv("username")
    api_key = os.getenv("apikey")
    
    
    # Obtener la cantidad de artistas escuchados
    artist_count = get_artist_count(username, api_key)
    if artist_count is not None:
        print(f"El usuario {username} ha escuchado {artist_count} artistas en Last.fm.")


    # Obtener el número total de scrobbles del usuario
    total_scrobbles = get_user_info(username, api_key)
    if total_scrobbles is not None:
        print(f"Total scrobbles: {total_scrobbles}")


    # Obtener las canciones escuchadas hoy
    today_tracks = get_recent_tracks(username, api_key)
    if today_tracks is not None:
        if len(today_tracks) > 0:
            print("Listado de scrobbles de hoy:")
            for track in today_tracks:
                print(track)
        else:
            print("No se han encontrado scrobbles para hoy.")


if __name__ == "__main__":
    main()