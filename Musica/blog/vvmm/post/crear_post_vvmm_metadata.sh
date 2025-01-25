#!/usr/bin/env bash
#
# Script Name: mover_mix_playerctl.sh 
# Description: Mover canción sonando actualmente a subcarpeta de la ruta establecida en Mix
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#     La idea de este script es poder tener en una carpeta aparte una selección de música con otro criterio (género por ej.)
#


# function urldecode() { : "${*//+/ }"; echo -e "${_//%/\\x}"; }

# player=$(playerctl -l)

# Función para verificar el estado y enviar notificaciones
check_status() {
    local status=$1
    local success_message=$2
    local error_message=$3

    case $status in
        0)
            notify-send -t 3 "Éxito" "$success_message"
            ;;
        1)
            notify-send -t 10 "Error" "$error_message: Error general."
            exit 0
            ;;
        2)
            notify-send -t 10 "Error" "$error_message: Error de uso incorrecto de la aplicación."
            exit 0
            ;;
        127)
            notify-send -t 10 "Error" "$error_message: Comando no encontrado."
            exit 0
            ;;
        130)
            notify-send -t 10 "Error" "$error_message: Proceso interrumpido por el usuario."
            exit 0
            ;;
        *)
            notify-send -t 10 "Error" "$error_message: Código desconocido $status."
            exit 0
            ;;
    esac
}


# Obterner ruta del archivo en reproducción
deadbeef="$(deadbeef --nowplaying-tf "%artist%")"
echo $deadbeef

if [[ -z "$deadbeef" ]]; then              # Detectar reproductor activo y obtener metadata de la canción en reproducción.
    album="$(playerctl -p strawberry metadata album) # obtener titulo de la canción."
    artist="$(playerctl -p strawberry metadata artist)"
else
    artist="$(deadbeef --nowplaying-tf "%artist%")"
    album="$(deadbeef --nowplaying-tf "%album%")"
    genre="$(deadbeef --nowplaying-tf "%genre%")"
fi

artista="$(echo "$artist" | sed -E "s/[áÁ]/-/g; s/\(.*\)//g; s/&/and/g; s/[éÉ]/e/g; s/[íÍ]/i/g; s/[óÓ]/o/g; s/[úÚ]/u/g; s/['\`]/-/g; s/---/-/g; s/--/-/g; s/\ //g; s/^-//g; s/-$//g")"
echo "A $artista"
albuma="$(echo "$album" | sed -E "s/[áÁ]/-/g; s/\(.*\)//g; s/&/and/g; s/[éÉ]/e/g; s/[íÍ]/i/g; s/[óÓ]/o/g; s/[úÚ]/u/g; s/['\`]/-/g;  s/---/-/g; s/--/-/g; s/\ //g; s/^-//g; s/-$//g")"
echo "B $album"
genre="$(echo $genre | sed 's/\// /g' | tr '[:upper:]' '[:lower:]' | sed 's/electronic//I' | sed 's/electronica//I' | sed 's/electrónica//I' | sed 's/indie//I' | sed 's/`/-/g')"
echo "C $genre"

artista_utf8="$(echo "$artista" | iconv -f UTF-8 -t UTF-8)"
albuma_utf8="$(echo "$albuma" | iconv -f UTF-8 -t UTF-8)"

# artista="$(echo "$artista_utf8" | tr 'àèìòùáéíóúÁÉÍÓÚüÜñÑäëïöüÄËÏÖÜÀÈÌÒÙ' 'aeiouaeiouAEIOUuUnNaeiouAEIOUAEIOU')"
# albuma="$(echo "$album_utf8" | tr 'àèìòùáéíóúÁÉÍÓÚüÜñÑäëïöüÄËÏÖÜÀÈÌÒÙ' 'aeiouaeiouAEIOUuUnNaeiouAEIOUAEIOU')"

echo "$artista $albuma"

tags="$(yad --entry --title=comentario --entry-text="$genre" --text="$artista $albuma \n TAGS [x z y]: $cancion")"

if [[ -z $tags ]]; then notify-send -u critical "Cancelando post sin TAGS"  ; exit 0 ; fi

if [[ $tags == 'r' ]]; then
    artista="$(yad --entry --text=artista --entry-text="$artista")"
    if [[ -z $artista ]]; then notify-send "Saliendo" ; exit 0 ; fi
    albuma="$(yad --entry --text=album --entry-text="$albuma")"
    if [[ -z $albuma ]]; then notify-send "Saliendo" ; exit 0 ; fi
    tags="$(yad --entry --title=comentario --entry-text="$genre" --text="$artista $albuma \n TAGS [x z y]: $cancion")"
fi

if [[ $tags =~ 'pollo' ]]; then
    touch /tmp/pollo.txt /tmp/pollo2.txt
    yad --text-info --editable < /tmp/pollo.txt > /tmp/pollo2.txt
    tags="$(yad --entry --title=comentario --entry-text="$genre" --text="$artista $albuma \n TAGS [x z y]: $cancion")"
    rm /tmp/pollo.txt
    cp /tmp/pollo2.txt /tmp/pollo.txt
    rm /tmp/pollo2.txt
    rsync /tmp/pollo.txt hugo:
fi

echo "ssh moode"
ssh moode "bash /home/pi/hugo/hugo_scripts//blog/vvmm/post/get-links.sh ${artista} ${albuma} $tags"
check_status $? "Links obtenidos." "Error al obtener links."

#copyq add "https://volteret4.github.io/vvmm/posts/${artista}-_-${albuma}"


# Añadir canción a playlist de spotify también.
bash "${HOME}/Scripts/Musica/playlists/spotify/spotify_add_song.sh"
echo "add song"

ssh moode "cd /home/pi/hugo/web/vvmm/ && hugo server --bind 0.0.0.0 --baseURL 192.168.1.33 &"
HUGO_PID=$!

sleep 1

qutebrowser --target auto "http://192:168.1.33:1313/post/${artista}-_-${albuma}"
QUTE_PID=$!


# Esperar a que qutebrowser termine o pasen 20 segundos
timeout=20
count=0
while [ $count -lt $timeout ] && kill -0 $QUTE_PID 2>/dev/null; do
    sleep 1
    ((count++))
done

# Matar el proceso de Hugo
kill $HUGO_PID 2>/dev/null

# Asegurarse de que qutebrowser también se cierre si alcanzó el timeout
kill $QUTE_PID 2>/dev/null


# Ejecutar el script remoto y capturar la salida y el error
# post=$(ssh hugo "bash /home/ansible/scripts/blog/vvmm/post/get-links.sh ${artista} ${albuma} $tags" 2> "$logfile")

# # Leer el contenido del archivo temporal
# log=$(cat "$logfile")

# # Comprobar si el comando tuvo éxito
# if [[ -z $post ]]; then
#     notify-send -u critical "Ha habido un error al postear en vvmm"
#     # Mostrar el log en la notificación o en el terminal
#     notify-send -u critical "Log del error" "$log"
# else
#     notify-send "Creado post de \
#         ${artist} ${album}"
# fi

# # Eliminar el archivo temporal
# rm "$logfile"