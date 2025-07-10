#!/usr/bin/env bash
#
# Script Name: conciertos.sh 
# Description: Script que busca en ticket-master conciertos de aqui a un año 200 resultados (máximo establecido por ticketmaster)
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 

# Notes:
#
#



# Variable para indicar si ocurrió un error
# error_ocurrido=false
# 
#Función para manejar la señal ERR
# handle_error() {
 #   Solo ejecutar el script2 si ocurrió un error real
    # if [ "$error_ocurrido" = true ]; then
        # $HOME/Scripts/utilities/debug_scripts.sh "$@" 2>&1
        # exit 1
    # fi
# }
# 
#Asociar la función handle_error a la señal ERR
# trap 'error_ocurrido=true' ERR
# 
#error="$(echo "Ha ocurrido un error al ejecutar el script $0" && bash $HOME/Scripts/utilities/debug_scripts.sh)"


carpeta=$(dirname $(readlink "$0"))
source "${carpeta}/.env"

# Obtener la ruta del directorio del script actual
directorio_actual=$(dirname "$0")

# Especificar el archivo que está en la misma carpeta que el script
filtro="$directorio_actual/filtro.jq"
json_file="$directorio_actual/filtrado.json"
bak_file="$directorio_actual/filtrado.bak"

# Obtener fechas
fecha_actual="$(date +%Y-%m-%dT%H:%M:%SZ)"
fecha_proxima="$(date -d "1 year" +%Y-%m-%dT%H:%M:%SZ)"

# Crear copias del archivo json anterior
mv ${json_file} ${bak_file}

# Establecer consulta a la api de ticketmaster
url="https://app.ticketmaster.com/discovery/v2/events.json?size=200&classificationName=music&startDateTime=$fecha_actual&endDateTime=$fecha_proxima&countryCode=ES&apikey=$apikey"

json="$(curl ${url} )" # || ${error} )"
json="$(echo $json | jq .)" # || ${error} )"

#echo $json  # debug

# Guarda el resultado filtrad como un archivo json nuevo
echo $json | jq -f ${filtro}  > ${json_file}  #|| ${error}

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
#nuevo="$(comm -23 json.tmp bak.tmp)"

nuevo="$(jq -n '$json_file | . as $f1 | $bak_file | . as $f2 | ($f1 | keys) - ($f2 | keys)' $json_file $bak_file)" #|| ${error}


# Eliminar archivos temporales
rm json.tmp bak.tmp

# Enviar las nuevas entradas a ntfy/conciertos
if [ -n $nuevo ]; then
    echo ${nuevo} > "${directorio_actual}/seis-meses.txt"
    curl -H "Title: Ticketmaster" -H "Priority: min" -H "Tags: loudspeaker" -d "$nuevo" https://ntfy.pollete.duckdns.org/conciertos #|| ${error}
fi