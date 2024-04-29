#!/usr/bin/env bash
#
# Script Name: crear_obs_md.sh 
# Description: Crear archivo formato Markdown en la carpeta sincronizada de Obsidian
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
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
var="$(xdotool getactivewindow getwindowname)"
dir="/mnt/Datos/FTP/Wiki/Obsidian/Notas/Wiki"
firefox="Mozilla Firefox$"
chromium="\- Chromium$"
thorium="Thorium$"


# En dicho caso copiar URL al portapapeles.
if [[ $var =~ $firefox ]]
    then
                wid=$(xdotool search --name "Mozilla Firefox$")
                xdotool windowfocus $wid
                sleep 0.3
                xdotool key ctrl+l
                xdotool key ctrl+c
                xdotool key Escape
                url=$(copyq read 0)
                copyq remove 0
    elif [[ $var =~ $chromium ]]
        then
                wid=$(xdotool search --name "\- Chromium$")
                xdotool windowfocus $wid
                sleep 0.3
                xdotool key ctrl+l
                xdotool key ctrl+c
                xdotool key Escape
                url=$(copyq read 0)
                copyq remove 0
    elif [[ $var =~ $thorium ]]
        then
                wid=$(xdotool search --name "\- Thorium$")
                xdotool windowfocus $wid
                sleep 0.3
                xdotool key ctrl+l
                xdotool key ctrl+c
                xdotool key Escape
                url=$(copyq read 0)
                copyq remove 0
                echo "browser thorium"
fi


sleep 0.5

# Crear nuevas variables para título y contenido.
titulo=$(copyq read 1)
content=$(copyq read 0 )


# Array para almacenar los nombres de las subcarpetas
subcarpetas=()

# Leer las subcarpetas y almacenar sus nombres en el array
while IFS= read -r subcarpeta; do
    if [[ "$subcarpeta" != ".space" ]]; then
        subcarpetas+=("$subcarpeta")
    fi
done < <(find "$dir" -mindepth 1 -maxdepth 1 -type d -printf "%f\n")

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


# Elegir TAG.
# tag=$(zenity --info --title 'Copiando a Mixx' \
#             --text "En qué carpeta creamos $titulo" \
#             --extra-button "|___...Añadir Otro Tag / Carpeta...___|"\
#             --ok-label "En verdad paso..." \
#             $botones)
# Ruta de la carpeta que contiene las subcarpetas



# Si se presiona "Añadir carpeta...", solicitar al usuario el nombre de la nueva carpeta
if [[ "$tag" == *"Otra_Carpeta"* ]]; then
    nombre_nueva_carpeta=$(zenity --entry --title "Crear nueva carpeta")
    if [[ -n "$nombre_nueva_carpeta" ]]; then
        nueva_carpeta="$dir/$nombre_nueva_carpeta"
        mkdir -p "$nueva_carpeta"
        tag="$nombre_nueva_carpeta"
    fi
fi

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
