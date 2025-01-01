#!/usr/bin/env bash
#
# Script Name: crear_obs_md.sh 
# Description: Crear archivo formato Markdown en la carpeta sincronizada de Obsidian
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: Manejo de errores
# Notes:
#
#



# Variable para indicar si ocurrió un error
# error_ocurrido=false

# # Función para manejar la señal ERR
# handle_error() {
#     # Solo ejecutar el script2 si ocurrió un error real
#     if [ "$error_ocurrido" = true ]; then
#         $HOME/Scripts/utilities/debug_scripts.sh "$@" 2>&1
#         exit 1
#     fi
# }

# # Asociar la función handle_error a la señal ERR
# trap 'error_ocurrido=true' ERR

# Comprobar si la ventana activa pertenece a uno de estos navegadores.
browser="$(xdotool getactivewindow getwindowname)"
dir="/mnt/Datos/FTP/Wiki/Obsidian/Spaces/Wiki"

# Crear nuevas variables para título y contenido.
titulo=$(copyq read 1)
content=$(copyq read 0)

# Obtener el nombre de la ventana activa
active_window_id=$(xdotool getactivewindow)
active_window_name=$(xdotool getwindowname "$active_window_id")

# Crear array para almacenar los nombres de las subcarpetas
subcarpetas=()


# Leer las subcarpetas y almacenar sus nombres en el array
while IFS= read -r subcarpeta; do
    if [[ "$subcarpeta" != ".space" ]]; then
        subcarpetas+=("$subcarpeta")
    fi
done < <(find "$dir" -mindepth 1 -maxdepth 1 -type d -printf "%f\n")


# Ordenar las subcarpetas
IFS=$'\n' sorted_subcarpetas=($(sort <<<"${subcarpetas[*]}"))
unset IFS


# Agregar un botón para cada subcarpeta
botones=""
for subcarpeta in "${subcarpetas[@]}"; do
#    botones+="--extra-button $subcarpeta "
    primera_letra="${subcarpeta:0:1}"
    botones+="${subcarpeta}:${primera_letra} "
done
echo "primera letra__$primera_letra"
echo "botones_$botones"
tag="$(python3 $HOME/Scripts/utilities/menu_pollo2.py ${botones} | awk 'NR==1 {print $1}')"

if [[ -z $tag ]]; then
    exit 0
fi


# Si se presiona "Añadir carpeta...", solicitar al usuario el nombre de la nueva carpeta
if [[ "$tag" == *"Otra_Carpeta"* ]]; then
    nombre_nueva_carpeta=$(yad --entry --text "Crear nueva carpeta")
    if [[ -n "$nombre_nueva_carpeta" ]]; then
        nueva_carpeta="$dir/$nombre_nueva_carpeta"
        mkdir -p "$nueva_carpeta"
        tag="$nombre_nueva_carpeta"
    fi
fi

# Define una lista de aplicaciones y sus nombres de ventana
declare -A apps
apps=(
    ["firefox"]="Mozilla Firefox$"
    ["chromium"]="\\- Chromium$"
    ["floorp"]="Floorp$"
    ["thorium"]="Thorium$"
)

# Itera sobre las aplicaciones
for app_name in "${!apps[@]}"; do
    if [[ "$active_window_name" =~ ${apps[$app_name]} ]]; then
        echo "App name: $app_name"
        # Utilizar el ID de la ventana activa directamente
        wid=$active_window_id
        if [[ -n "$wid" ]]; then
            xdotool windowfocus --sync "${wid}"
            sleep 0.2
            xdotool key --window "${wid}" ctrl+l
            xdotool key --window "${wid}" ctrl+c
            sleep 2
            url=$(copyq read 0)
            xdotool key --clearmodifiers --window "${wid}" Escape
        else
            echo "No se encontró la ventana para ${app_name}"
        fi
        break
    fi
done


# Añadir la línea de la URL solo si la variable no está vacía
if [ -n "${url}" ]; then
    contenido="> ${url}"
    contenido="${contenido}\n${content}"
    else
    contenido="${content}"
fi

# Enviar nuevo elemento a Obsidian
mkdir "${dir}/${tag}"

echo "dir: ${dir}"
echo "url: ${url}"
echo "tag: ${tag}"
echo "titulo: ${titulo}"
echo "contenido: $contenido"

nota="${dir}/${tag}/${titulo}.md"
#nota="${nota}.md"

echo -e "${contenido}" >> "${nota}"
echo "FILE: ${nota}"
if [[ -z $url ]]; then
    elementos=2
else
    elementos=3
fi
for i in {1..$elementos}; do
    copyq remove 0
done
