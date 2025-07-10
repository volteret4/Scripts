
#!/usr/bin/env python
#
# Script Name: .py
# Description: 
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:

# Notes:
#   Dependencies:  - python3, 
#
#   Requiere 2 argumentos, release_id y nombre del archivo de salida
#       ejemplo de release id: 31065680 de https://www.discogs.com/release/31065680-Somos-La-Herencia-Dolo
#

import requests
import sys
from dotenv import load_dotenv
import os

# Acceder a las variables de entorno
release_id = sys.argv[1]

# Nombre del archivo de salida
output_file_name = sys.argv[2]

# Cargar las variables de entorno desde el archivo .env
load_dotenv()
DISCOGS_TOKEN = os.getenv("DISCOGS_TOKEN")

def get_artist_url(artist_id):
    return f'https://www.discogs.com/artist/{artist_id}'

def get_artist_profile(artist_id):
    artist_url = f'https://api.discogs.com/artists/{artist_id}'
    response = requests.get(artist_url)
    data = response.json()
    return data.get('profile', 'Perfil no disponible')

def clean_profile(profile):
    # Eliminar saltos de línea y espacios dobles
    cleaned_profile = profile.replace('\n', ' ').replace('  ', ' ')
    # Dividir el perfil en palabras y tomar solo las primeras 7 palabras
    words = cleaned_profile.split()[:7]
    # Unir las palabras en una cadena
    shortened_profile = ' '.join(words).strip()
    # Añadir puntos suspensivos si hay más de 7 palabras originales
    if len(profile.split()) > 7:
        shortened_profile += '...'
    return shortened_profile

def get_album_info(release_id):
    # Construye la URL para obtener información del release
    album_url = f'https://api.discogs.com/releases/{release_id}'
    
    # Realiza la solicitud para obtener la información del release
    response = requests.get(album_url)
    data = response.json()
    
    # Verifica si se encontraron resultados
    if 'status' in data and data['status'] == 'error':
        return None
    
    # Extrae la información del release
    album_info = {}
    
    # Fecha de lanzamiento
    if 'year' in data:
        album_info['**Fecha de lanzamiento**'] = data['year']
    else:
        album_info['**Fecha de lanzamiento**'] = "Desconocida"
    
    # Géneros y Estilos
    if 'genres' in data:
        genres_str = ', '.join(data['genres'])
        album_info['**Géneros**'] = genres_str
    else:
        album_info['**Géneros**'] = "Desconocidos"

    if 'styles' in data:
        styles_str = ', '.join(data['styles'])
        album_info['**Estilos**'] = styles_str
    else:
        album_info['**Estilos**'] = "Desconocidos"
    
    # Tracklist
    if 'tracklist' in data:
        tracklist = []
        for track in data['tracklist']:
            featuring = ""
            if 'extraartists' in track:
                extra_artists = []
                for artist in track['extraartists']:
                    artist_name = artist['name']
                    artist_id = artist['id']
                    artist_url = get_artist_url(artist_id)
                    artist_profile = get_artist_profile(artist_id)
                    cleaned_profile = clean_profile(artist_profile)
                    if artist_url:
                        # Construye el enlace con el perfil como tooltip
                        artist_link = f"[{artist_name}]({artist_url} '{cleaned_profile}')"
                        extra_artists.append(artist_link)
                    else:
                        extra_artists.append(artist_name)
                featuring = f"\n(feat. {' & '.join(extra_artists)})"
            track_info = f"{track['position']}. {track['title']} {featuring}   {track['duration']}"
            tracklist.append(track_info)
        album_info['Tracklist'] = tracklist
    else:
        album_info['Tracklist'] = "Desconocida"
    
    return album_info

if __name__ == "__main__":
    if len(sys.argv) <= 2:
        print("Uso: python discogs_album.py [release_id] [output_file_name]")
        sys.exit(1)
    
    # Abrir el archivo en modo de escritura
    with open(output_file_name, "a") as output_file:
        # Redirigir la salida estándar al archivo
        sys.stdout = output_file

        # Obtener la información del álbum
        album_info = get_album_info(release_id)
        
        if album_info:
            print("> Información del álbum facilitada por discogs.com:\n")
            for key, value in album_info.items():
                if isinstance(value, list):
                    print(f"{key}:")
                    for item in value:
                        if isinstance(item, dict):
                            for k, v in item.items():
                                print(f"  {k}: {v}")
                            print()  # Agrega un salto de línea adicional entre elementos de la lista
                        else:
                            print(f"  {item}")
                    print()
                    print()  # Agrega un salto de línea adicional después de la lista completa
                elif isinstance(value, dict):
                    print(f"{key}:")
                    for k, v in value.items():
                        print(f"  {k}: {v}")
                    print()  # Agrega un salto de línea adicional después del diccionario completo
                else:
                    print(f"{key}: {value}")
                    print()  # Agrega un salto de línea adicional después de cada entrada simple
            print()  # Agrega un salto de línea adicional al final de toda la información del álbum
        else:
            print(f"No se encontró información para el release_id '{release_id}'.")
    
    # Restaurar la salida estándar a la consola
    sys.stdout = sys.__stdout__

    print(f"Se ha guardado la información del álbum en '{output_file_name}'.")
