import requests
import time
import json

class MusicButlerAPI:
    def __init__(self, session_cookie, csrf_token):
        self.base_url = "https://www.musicbutler.io"
        self.headers = {
            "Cookie": session_cookie,
            "X-CSRFToken": csrf_token,
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "https://www.musicbutler.io/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:128.0) Gecko/20100101 Firefox/128.0",
            "Accept": "*/*",
            "Origin": "https://www.musicbutler.io",
            "HX-Request": "true",
            "HX-Current-URL": "https://www.musicbutler.io/",
            "DNT": "1"
        }
    
    def add_artist(self, artist_id):
        """
        Añade un artista a tu cuenta de Music Butler usando HTMX
        """
        endpoint = f"{self.base_url}/api-add-artist/"
        
        # Los datos necesitan estar en formato form-urlencoded
        data = {
            "artist_id": artist_id
        }
        
        print(f"\nEnviando petición para artista ID: {artist_id}")
        print(f"URL: {endpoint}")
        print(f"Headers: {json.dumps(self.headers, indent=2)}")
        print(f"Data: {data}")
        
        try:
            response = requests.post(
                endpoint,
                headers=self.headers,
                data=data
            )
            
            print(f"Código de respuesta: {response.status_code}")
            print(f"Respuesta del servidor: {response.text[:200]}...")  # Mostramos solo el inicio
            
            if response.status_code == 200:
                return True, "Añadido correctamente"
            else:
                return False, f"Error: {response.status_code}"
                
        except Exception as e:
            print(f"Excepción: {str(e)}")
            return False, f"Error de conexión: {str(e)}"

    def search_artist(self, artist_name):
        """
        Busca un artista para obtener su ID
        """
        endpoint = f"{self.base_url}/search/"
        params = {"q": artist_name}
        
        try:
            response = requests.get(endpoint, headers=self.headers, params=params)
            if response.status_code == 200:
                # Aquí necesitaríamos parsear el HTML para encontrar el ID del artista
                # Por ahora, imprimimos la respuesta para debug
                print(f"Respuesta de búsqueda: {response.text[:200]}...")
                return None  # Por ahora retornamos None
            return None
        except Exception as e:
            print(f"Error en búsqueda: {str(e)}")
            return None

def main():
    print("Por favor, desde las herramientas de desarrollo del navegador (F12):")
    print("1. Busca en los headers de cualquier petición:")
    print("   - El valor completo de la cookie (incluyendo 'csrftoken=' y 'sessionid=')")
    print("   - El valor del header 'X-CSRFToken'")
    
    cookie = input("\nIngresa el valor completo de la cookie: ")
    csrf_token = input("Ingresa el X-CSRFToken: ")
    
    # Prueba con un ID específico
    print("\nPor ahora, necesitamos el ID del artista.")
    print("Puedes encontrarlo en el botón de seguir en la web (follow-button-for-artist-XXXXX)")
    artist_id = input("Ingresa el ID del artista para probar: ")
    
    mb_api = MusicButlerAPI(cookie, csrf_token)
    success, message = mb_api.add_artist(artist_id)
    print(f"\nResultado: {'Éxito' if success else 'Fallo'} - {message}")

if __name__ == "__main__":
    main()