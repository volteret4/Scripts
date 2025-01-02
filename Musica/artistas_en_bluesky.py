
#!/usr/bin/env python
#
# Script Name: .py
# Description: Consultar en bluesky si existen los artistas proporcionados en /home/huan/Scripts/.content/artistas.txt
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# TODO: 
#   Modificar la ruta absoluta /home/huan/Scripts/.content/artistas.txt y home/huan/Scripts/.content/resultados_bluesky.txt
# Notes:
#   Dependencies:  - python3
#

import requests
import time

def check_bluesky_user(username):
    """
    Verifica si un usuario existe en Bluesky
    Retorna True si existe, False si no
    """
    # Normalizamos el nombre de usuario
    username = username.strip().lower()
    if not username:
        return False
        
    # Si no tiene el dominio .bsky.social, lo agregamos
    if not username.endswith('.bsky.social'):
        username = f"{username}.bsky.social"
    
    # URL de la API de Bluesky
    url = f"https://api.bsky.app/xrpc/com.atproto.identity.resolveHandle"
    params = {'handle': username}
    
    try:
        response = requests.get(url, params=params)
        return response.status_code == 200
    except:
        return False

def main():
    # Lee el archivo de usuarios
    with open('/home/huan/Scripts/.content/artistas.txt', 'r', encoding='utf-8') as file:
        artists = file.readlines()
    
    # Procesa cada artista
    results = []
    for artist in artists:
        artist = artist.strip()
        exists = check_bluesky_user(artist)
        results.append((artist, exists))
        # Pequeña pausa para no sobrecargar la API
        time.sleep(0.5)
    
    # Guarda los resultados
    with open('/home/huan/Scripts/.content/resultados_bluesky.txt', 'w', encoding='utf-8') as file:
        for artist, exists in results:
            status = "ENCONTRADO" if exists else "NO ENCONTRADO"
            file.write(f"{artist}: {status}\n")
            print(f"{artist}: {status}")

if __name__ == "__main__":
    main()