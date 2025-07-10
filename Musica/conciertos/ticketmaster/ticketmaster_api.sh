#!/usr/bin/env bash
#
# Script Name: conciertos.sh 
# Description: Script que busca en Ticketmaster conciertos de los artistas de la lista y dentro de un año (200 resultados)
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 

# Notes:
#
# Obtener la ruta del directorio del script actual
directorio_actual="$(dirname "$0")"

source "$directorio_actual"/.env

echo "$APIKEY"

# Leer la lista de artistas desde el archivo
artistas_lista=$(cat "$directorio_actual/artistas.txt")

# Especificar el archivo que está en la misma carpeta que el script
filtro="$directorio_actual/filtro.jq"
json_file="$directorio_actual/filtrado.json"
bak_file="$directorio_actual/filtrado.bak"

# Obtener fechas
fecha_actual="$(date +%Y-%m-%dT%H:%M:%SZ)"
fecha_proxima="$(date -d "1 year" +%Y-%m-%dT%H:%M:%SZ)"

# Crear copias del archivo json anterior
mv ${json_file} ${bak_file}
country_code="ES"

# Obtener datos de la API de Ticketmaster
url="https://app.ticketmaster.com/discovery/v2/events.json?size=200&classificationName=music&startDateTime=$fecha_actual&endDateTime=$fecha_proxima&countryCode=$country_code&apikey=$APIKEY"

json="$(curl ${url})"
json="$(echo $json | jq .)"

echo "$json" > test

# Filtrar los conciertos según los artistas
conciertos_filtrados=""

for artista in $artistas_lista; do
    conciertos_filtrados+=$(echo "$json" | jq --arg artista "$artista" '.events[] | select(.name | contains($artista))')
done

# Si no hay conciertos para los artistas, termina
if [ -z "$conciertos_filtrados" ]; then
    echo "No se encontraron conciertos para los artistas especificados."
    exit 1
fi

# Guardar los conciertos filtrados como un archivo JSON
echo "$conciertos_filtrados" > "$json_file"

# Comprueba que existen ambos archivos
if [ ! -f "$json_file" ]; then
  echo "Error: El archivo '$json_file' no existe." >&2
  curl -H "Title: Ticketmaster ERROR" -H "Tags: rotating_light" -d "Error: El archivo '$json_file' no existe." -H "Priority: max" https://ntfy.pollete.duckdns.org/conciertos
  exit 1
fi

if [ ! -f "$bak_file" ]; then
  echo "Error: El archivo '$bak_file' no existe." >&2
  curl -H "Title: Ticketmaster ERROR" -H "Tags: rotating_light" -d "Error: El archivo '$bak_file' no existe." -H "Priority: max" https://ntfy.pollete.duckdns.org/conciertos
  exit 1
fi

# Convertir JSON a líneas con jq
jq -r '.[]' "$json_file" > json.tmp
jq -r '.[]' "$bak_file" > bak.tmp

# Usar comm para encontrar las nuevas adiciones
nuevo="$(comm -23 json.tmp bak.tmp)"

# Eliminar archivos temporales
rm json.tmp bak.tmp

# Enviar las nuevas entradas a ntfy/conciertos
if [ -n "$nuevo" ]; then
    echo "$nuevo" > "${directorio_actual}/seis-meses.txt"
    curl -H "Title: Ticketmaster" -H "Priority: min" -H "Tags: loudspeaker" -d "$nuevo" https://ntfy.pollete.duckdns.org/conciertos
fi