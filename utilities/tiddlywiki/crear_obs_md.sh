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
error_ocurrido=false

# Función para manejar la señal ERR
handle_error() {
    # Solo ejecutar el script2 si ocurrió un error real
    if [ "$error_ocurrido" = true ]; then
        $HOME/Scripts/utilities/debug_scripts.sh "$@" 2>&1
        exit 1
    fi
}

# Asociar la función handle_error a la señal ERR
trap 'error_ocurrido=true' ERR

# Comprobar si la ventana activa pertenece a uno de estos navegadores.
var="$(xdotool getactivewindoow getwindowname)"
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


# Ruta de la carpeta que contiene las subcarpetas
ruta_carpeta="$dir"

# Array para almacenar los nombres de las subcarpetas
subcarpetas=()

# Leer las subcarpetas y almacenar sus nombres en el array
while IFS= read -r subcarpeta; do
    if [[ "$subcarpeta" != ".stfolder" ]]; then
        subcarpetas+=("$subcarpeta")
    fi
done < <(find "$ruta_carpeta" -mindepth 1 -maxdepth 1 -type d -printf "%f\n")

# Agregar un botón para cada subcarpeta
botones=""
for subcarpeta in "${subcarpetas[@]}"; do
    botones+="--extra-button $subcarpeta "
done


# Elegir TAG.
tag=$(zenity --info --title 'Copiando a Mixx' \
            --text "En qué carpeta creamos $titulo" \
            --extra-button "|___...Añadir Otro Tag / Carpeta...___|"\
            --ok-label "En verdad paso..." \
            $botones)


# Si se presiona "Añadir carpeta...", solicitar al usuario el nombre de la nueva carpeta
if [[ "$tag" == *"Otro"* ]]; then
    nombre_nueva_carpeta=$(zenity --entry --title "Crear nueva carpeta")
    if [[ -n "$nombre_nueva_carpeta" ]]; then
        nueva_carpeta="$ruta_carpeta/$nombre_nueva_carpeta"
        mkdir -p "$nueva_carpeta"
        tag="$nombre_nueva_carpeta"
    fi
fi

# tag="$(zenity --info --title "tw"\
#     --text "¿En donde quieres guardar el documento de Obsidian? T: $titulo C: $contenido"\
#     --extra-button "Linux"\
#     --extra-button "AHK"\
#     --extra-button "Docker"\
#     --extra-button "Tasker"\
#     --extra-button "Raspberry"\
#     --extra-button "Tiddlywiki"\
#     --extra-button "Vim"\
#     --extra-button "NixOS"\
#     --extra-button "ArchLinux"\
#     --ok-label "paso"\
# )"

#  Preparar contenido
# contenido="#${titulo}
# ---
# ${tag}
# ---
# > ${url}
# ${content}"


# Añadir la línea de la URL solo si la variable no está vacía
if [ -n "${url}" ]; then
    contenido="${url}"
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
