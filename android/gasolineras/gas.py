#!/usr/bin/env python
import json
import os
from dotenv import load_dotenv

load_dotenv()

ruta_archivo = "/home/huan/gasolina_filtro.json"
lat_or =  os.getenv("LAT")
long_or = os.getenv("LON")

with open(ruta_archivo, 'r', encoding='utf-8-sig') as f:
    data = json.load(f)

print("Se ha cargado el archivo con éxito")

# Reemplazar las comas en los precios del gasoleo/gasolina 95 / 98 por puntos
for entry in data:
    entry['Precio Gasoleo A'] = entry['Precio Gasoleo A'].replace(',', '.')

for entry in data:
    entry['Precio Gasolina 95 E5'] = entry['Precio Gasolina 95 E5'].replace(',', '.')

for entry in data:
    entry['Precio Gasolina 98 E5'] = entry['Precio Gasolina 98 E5'].replace(',', '.')

# Filtrar las entradas del archivo JSON
filtered_data = []

for entry in data:
    lat = float(entry["Latitud"].replace(",", "."))
    lon = float(entry["Longitud (WGS84)"].replace(",", "."))

    if lat_or - 0.1 <= lat <= lat_or + 0.1 and long_or - 0.1 <= lon <= long_or + 0.1:
        filtered_data.append(entry)

print("Se han filtrado las entradas con éxito")
print("Las entradas filtradas son:")
print(filtered_data)

filtered_data_sorted = sorted(filtered_data, key=lambda x: float(x['Precio Gasoleo A']))

# Escribir los resultados en el archivo gasolineras_cercanas.json
ruta_archivo_cercanas = "/home/huan/gasolineras_cercanas.json"
try:
    with open(ruta_archivo_cercanas, "w") as f:
        json.dump(filtered_data_sorted[:10], f, indent=4)
        print("Se han guardado las gasolineras cercanas en gasolineras_cercanas.json")
except Exception as e:
    print("Ha ocurrido un error al guardar las gasolineras cercanas: ", e)
