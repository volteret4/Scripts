#!/usr/bin/env bash
#
# Script Name: actualizar_doc.sh
# Description: Actualiza la documentación de la app music fuzzy
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# Notes:
#   Dependencies:  - dunst 
#

# VARIABLES

# Carpetas
RAIZ_OBSIDIAN="/mnt/windows/FTP/wiki/Obsidian/Spaces/Blogs/snipets y scripts/music-fuzzy"
RAIZ_PEPE="/home/pepe/hugo/web/music-fuzzy-doc"

# FUNCIONES

# Función de limpieza
function limpieza {
# frontmatter
sed -i '1,/^---$/d;/^\.\.\.$/d' "$temp_file"
sed -i "1i +++\ntitle = $titulo\ntype = "chapter"\nweight = 2\n+++" "$temp_file"

# eliminar tareas
sed -i '/^```tasks$/,/^```$/d' "$temp_file"

}

# INSTALACIÓN

# Cambiar format del indice Instalación
introduccion="$RAIZ_OBSIDIAN/Aplicacion musica pollo.md"
temp_intro="/tmp/instalacion.md"

cp "$introduccion" "$temp_intro"

temp_file="$temp_intro"
titulo="instalacion"

limpieza

# copiar intro limpia
rsync -azh "$temp_intro" pepecono:"$RAIZ_PEPE/content/instalacion/_index.md"


# Pasos de la instalacion: config json y base de datos
configuracion_json="$RAIZ_OBSIDIAN/configuracion/config json.md"
configuracion_base_datos="$RAIZ_OBSIDIAN/configuracion/base_datos.md"

temp_c_json=/tmp/config_json.md
temp_c_db=/tmp/config_db.md

cp "$configuracion_json" "$temp_c_json"
cp "$configuracion_base_datos" "$temp_c_db"

# json
temp_file="$temp_c_json"
titulo="Config Json"
limpieza 

# json
temp_file="$temp_c_db"
titulo="Base de datos"
limpieza 

rsync -az "$temp_c_db" pepecono:"$RAIZ_PEPE/content/instalacion/base-de-datos/index.md"
rsync -az "$temp_c_json" pepecono:"$RAIZ_PEPE/content/instalacion/config-json/index.md"



# MODULOS


