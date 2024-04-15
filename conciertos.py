#!/usr/bin/env bash
#
# Script Name: conciertos.py 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#
#

import requests
from dotenv import load_dotenv

load_dotenv()

# Reemplaza "ARTISTA" con el nombre del artista que deseas buscar
artista = "Karol G"

# Tu clave API de Ticketmaster
api_key = os.getenv("APIKEY")

# URL base de la API Discovery
url_base = "https://app.ticketmaster.com/discovery/v2/events.json"

# Parametros de consulta
parametros = {
    "apikey": api_key,
    "keyword": artista
}

# Consulta a la API
respuesta = requests.get(url_base, params=parametros)

# Si la consulta fue exitosa
if respuesta.status_code == 200:

    # Decodifica la respuesta JSON
    datos = respuesta.json()

    # Extrae la información de los eventos (máximo 50 por consulta)
    eventos = datos["_embedded"]["events"]

    # Imprime la información de cada evento
    for evento in eventos:
        print("Nombre:", evento["name"])
        print("Fecha:", evento["dates"]["start"]["localDate"])
        print("Lugar:", evento["_embedded"]["venues"][0]["name"])
        print("--------")

else:
    print("Error al consultar la API:", respuesta.status_code)