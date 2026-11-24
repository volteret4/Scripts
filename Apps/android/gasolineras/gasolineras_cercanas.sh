#!/usr/bin/env bash


carpeta=$(dirname $(readlink "$0"))
source "${carpeta}/.env"

R=6371
radius=5
gasolina=/home/huan/gasolina_filtro.txt
# Coordenadas de referencia
ref_lat=40.4168
ref_lon=-3.7038

# Convertir la distancia a grados
dLat=$(echo "scale=10; $radius/($R * 3.141592653 / 180)" | bc -l)
dLon=$(echo "scale=10; $radius/($R * 3.141592653 / 180 / c($ref_lat * 3.141592653 / 180))" | bc -l)

# Filtro de coordenadas
min_lat=$(echo "$ref_lat - $dLat" | bc -l)
max_lat=$(echo "$ref_lat + $dLat" | bc -l)
min_lon=$(echo "$ref_lon - $dLon" | bc -l)
max_lon=$(echo "$ref_lon + $dLon" | bc -l)

# Leer el archivo json
#cat $gasolina | jq --arg min_lat "$min_lat" --arg max_lat "$max_lat" --arg min_lon "$min_lon" --arg max_lon "$max_lon" '[.[] | select(.Latitud >= ($min_lat) and .Latitud <= ($max_lat) and (.Longitud // "0") >= ($min_lon) and (.Longitud // "0") <= ($max_lon))]' > /home/huan/gasolineras_cercanas.json
#grep -E "\"Latitud\": ($min_lat|$max_lat)|\"Longitud\": ($min_lon|$max_lon)" $gasolina > /home/huan/gasolineras_cercanas.json
grep -E "\"Latitud\": ($min_lat|$max_lat)|\"Longitud\": ($min_lon|$max_lon)" $gasolina | tee /home/huan/gasolineras_cercanas.json
