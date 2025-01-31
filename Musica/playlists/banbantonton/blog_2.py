import requests
from bs4 import BeautifulSoup
from mpd import MPDClient

url = "https://banbantonton.com/2024/12/14/2024-a-lucky-7-compilations/" 

playlist_file = "playlist.txt"


busqueda = ["youtube", "soundcloud", "bandcamp"]

# Send HTTP request to the website
response = requests.get(url)

# Parse the HTML content of the page
soup = BeautifulSoup(response.text, 'html.parser')

# Find all the anchor tags that contain links
links = soup.find_all('a')

# Extract and print the URLs
with open(playlist_file, "w") as file:
    for link in links:
        href = link.get('href')
        if href and  any(url in href for url in busqueda):
            print(href)
            file.write(href + "\n")  # Guardamos cada URL en una nueva línea
print(f"Playlist guardada en {playlist_file}")


# Crear cliente MPD
client = MPDClient()
client.connect("localhost", 6600)  # Ajusta la IP y el puerto si es necesario

# Limpiar la lista de reproducción
client.clear()

# Cargar las URLs de la playlist
with open("playlist.txt", "r") as file:
    for line in file:
        client.add(line.strip())

# Reproducir
client.play()

print("Reproduciendo la lista de reproducción.")
