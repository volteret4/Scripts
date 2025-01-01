#!/usr/bin/env/ bash

# Variables
artist="$(deadbeef --nowplaying "%a" )"
album="$(deadbeef --nowplaying "%b"  )"
artista="$(echo $artist | sed 's/ /-/g' | sed 's/á/a/g' | sed 's/é/e/g' | sed 's/í/i/g' | sed 's/ó/o/g' | sed 's/ú/u/g' | sed "s/'/-/g" | sed 's/"/-/g'| sed 's/`/-/g' | sed 's/,/-/g' | sed 's/;/-/g' | sed 's/:/-/g')"
albuma="$(echo $album | sed 's/ /-/g' | sed 's/á/a/g' | sed 's/é/e/g' | sed 's/í/i/g' | sed 's/ó/o/g' | sed 's/ú/u/g' | sed "s/'/-/g" | sed 's/"/-/g' | sed 's/,/-/g' | sed 's/;/-/g' | sed 's/:/-/g')"

path_script="/home/pi/hugo/scripts/blog/vvmm/post/enlaces/spotify/spotify.py "$artista" "$albuma""

source_env="source /home/pi/scripts/python_venv/bin/activate"

# debug
# Verifica que las variables no estén vacías
if [[ -z "$artist" || -z "$album" ]]; then
    echo "Error: El artista o el álbum están vacíos. Verifica deadbeef."
    exit 1
fi

echo Artista: $artista
echo Album: $albuma


# Obtener url de spotify
url_spotify="$(ssh moode "$source_env && $path_script")"
if [[ -z "$url_spotify" ]]; then
    echo "Error: No se obtuvo la URL de Spotify."
    exit 1
fi

echo "$url_spotify"

# Obtener url odesli
python3 $HOME/Scripts/utilities/open_search_links/music_player/odesli_metadata.py "${url_spotify}"