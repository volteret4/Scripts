import requests
import sys
import subprocess

# Verifica que se haya proporcionado un argumento
if len(sys.argv) != 2:
    print("Uso: python script.py <URL>")
    sys.exit(1)

# Enlace inicial del álbum
url = sys.argv[1]

# Endpoint de la API de Odesli
api_endpoint = "https://api.song.link/v1-alpha.1/links"

# Solicitud GET con el parámetro URL
response = requests.get(api_endpoint, params={"url": url})

# Verifica el estado de la solicitud
if response.status_code == 200:
    data = response.json()
    # Obtén el enlace genérico del álbum
    page_url = data.get("pageUrl")
    
    # Copiar al portapapeles usando CopyQ
    subprocess.run(["copyq", "add", page_url])
    
    # Enviar notificación
    subprocess.run(["notify-send", "-t", "5000", "Odesli Link", f"Copiado al portapapeles:\n{page_url}"])
    
    # Imprime el enlace en la terminal (opcional)
    print(f"{page_url}")
else:
    error_msg = f"Error en la solicitud: {response.status_code}"
    # Enviar notificación de error
    subprocess.run(["notify-send", "Error en Odesli API", error_msg])
    print(error_msg)