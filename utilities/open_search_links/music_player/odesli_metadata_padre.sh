#!/usr/bin/env bash
#
# Script Name: .sh
# Description: 
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# Notes:
#   Dependencies:  - dunst 
#


source "/home/huan/Scripts/utilities/notificaciones/debug/debug.sh"
setup_error_trap


# Variables
artist="$(deadbeef --nowplaying "%a" )"
album="$(deadbeef --nowplaying "%b"  )"
artista="$(echo $artist | sed 's/ /-/g' | sed 's/á/a/g' | sed 's/é/e/g' | sed 's/í/i/g' | sed 's/ó/o/g' | sed 's/ú/u/g' | sed "s/'/-/g" | sed 's/"/-/g'| sed 's/`/-/g' | sed 's/,/-/g' | sed 's/;/-/g' | sed 's/:/-/g')"
albuma="$(echo $album | sed 's/ /-/g' | sed 's/á/a/g' | sed 's/é/e/g' | sed 's/í/i/g' | sed 's/ó/o/g' | sed 's/ú/u/g' | sed "s/'/-/g" | sed 's/"/-/g' | sed 's/,/-/g' | sed 's/;/-/g' | sed 's/:/-/g')"
path_album="$(dirname "$(deadbeef --nowplaying-tf "%path%")")"
echo "$path_album"

path_script="python3 /home/pi/hugo/hugo_scripts/blog/vvmm/post/enlaces/spotify/spotify.py $artista $albuma"

source_env="source /home/pi/scripts/python_venv/bin/activate"

# debug
# Verifica que las variables no estén vacías
if [[ -z "$artist" || -z "$album" ]]; then
    echo "Error: El artista o el álbum están vacíos. Verifica deadbeef."
    notify_error "Artista o álbum vacio" "$0" "¿Se está ejecutando deadbeef?" "000"
    exit 1
fi
# Verifica que las variables no estén vacías
if [[ "$artist"  =~ "nothing" || "$album"  =~ "nothing" ]]; then
    echo "Error: El artista o el álbum están vacíos. Verifica deadbeef."
    notify_error "Artista o álbum vacio" "$0" "¿Se está ejecutando deadbeef?" "000"
    exit 1
fi


echo Artista_formateado: $artista
echo Album_formateado: $albuma


# Obtener url de spotify
url_spotify="$(ssh moode "$source_env && $path_script")"
if [[ -z "$url_spotify" ]]; then
    echo "Error: No se obtuvo la URL de Spotify."
    exit 1
fi

echo "$url_spotify"

# Obtener url odesli
url="$(python3 "$HOME"/Scripts/utilities/open_search_links/music_player/odesli_metadata.py "${url_spotify}" "${artista}" "${albuma}")"
if [[ -z "$url" ]]; then
    echo "Error: No se obtuvo la URL de Odesli."
    notify_error "Error Odesli" "$0" "No se obtuvo la URL de Odesli." "000"
    exit 1
fi


# Obtener portada desde la carpeta
portada=1
cover="$(find "$path_album" -iname "cover.png" -or -iname "cover.jpg" -or -iname "cover.jpeg")"
echo "cover_ $cover"
if [[ -z "$cover" ]]; then
    folder="$(find "$path_album" -iname "folder.png" -or -iname "folder.jpg" -or -iname "folder.jpeg")"
    echo "folder_ $folder"
    elif [[ -z "$folder" ]] && [[ -z "$cover" ]]; then
        echo "Error: No se encontró la portada."
        portada=0
    
fi

# Notificar
if [[ $portada -eq 0 ]]; then
    export DISPLAY=":0" && dunstify -t 5000 "${artist} - ${album} ${url}"
    echo "No se encontró la portada."
elif [[ -n "$cover" ]]; then
    export DISPLAY=":0" && dunstify -t 5000 -i "$cover" "<b>${artist} - ${album}</b> \n ${url}"
    echo "cover"
elif [[ -n "$folder" ]]; then
    export DISPLAY=":0" && dunstify -t 5000 "${artist} - ${album} ${url}" -I "$folder"
    echo "folder"
fi