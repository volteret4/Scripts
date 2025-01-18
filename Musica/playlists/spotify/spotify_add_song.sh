#!/usr/bin/env bash
#
# Script Name: spotify_add_song.sh
# Description: Script para orquestar la inclusión de la canción en reproducción al
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# TODO: 
# Notes:
#   Dependencies: 
#

# Directorios y variables:
scr_dir="$HOME/Scripts/Musica/playlists/spotify"
hugo_dir="/home/pi/hugo/hugo_scripts/playlists/spotify"

#python_env="$(source /home/pi/scripts/python_venv/bin/activate)"
# Actualiza listas de reproducción de spotify.
ssh moode "source /home/pi/scripts/python_venv/bin/activate ; python3 ${hugo_dir}/sp_playlist.py"

# Descarga el listado.
rsync -avzh moode:"${hugo_dir}"/playlists.txt $HOME/Scripts/Musica/playlists/spotify/playlists.txt

# Obtener artista y titulo de la canción actual
variables="$(bash $HOME/Scripts/utilities/aliases/en_reproduccion.sh)"

# Asigna los valores capturados a variables.
artista="$(echo "$variables" | awk '{print $1}')"
titulo="$(echo "$variables" | awk '{print $2}')"
album="$(echo "$variables" | awk '{print $3}')"



artista="$(bash $HOME/Scripts/utilities/aliases/limpia_var.sh ${artista})"
titulo="$(echo $titulo | sed -E 's/\([^)]*\)|\[[^\]]*\]|\{[^}]*\}//g')"
titulo="$(bash $HOME/Scripts/utilities/aliases/limpia_var.sh ${titulo})"
album="$(bash $HOME/Scripts/utilities/aliases/limpia_var.sh ${album})"



echo "$artista $titulo $album"

# Busca cancion en spotify.
song_id="$(ssh moode "source /home/pi/scripts/python_venv/bin/activate ; python3 ${hugo_dir}/sp_busca_cancion.py ${artista} ${titulo}")"

if [[ -z $song_id ]]; then
    notify-send -u critical -t 5000 " error en el script "
    exit 0
    elif [[ $song_id =~ 'notoken' ]] ; then
        notify-send -u critical -t 5000 " fallo con el token "
        exit 0
    elif [[ $song_id =~ 'nocancion' ]] ; then
        notify-send -u critical -t 5000 "fallo con la id de la canción... reintentando"
        artist_song="$(yad --entry --entry-text="$artista - $titulo" --entry-label="artista - cancion")"
        song_id="$(ssh moode "source /home/pi/scripts/python_venv/bin/activate ; python3 ${hugo_dir}/sp_busca_cancion.py ${artist_song}")"
        if [[ $song_id =~ 'nocancion' ]] ; then
            notify-send -u critical -t 5000 " fallo DEFINITIVO con la id de la canción"
        fi
fi

id=$(echo "$song_id" | awk 'NR==1')
url=$(echo "$song_id" | awk 'NR==2')

# Muestra menú con playlists
playlist="$(python3 $scr_dir/sp_menu_playlists.py)"

if [[ $playlist =~ "nuevalista" ]]; then
    pl_name="$(yad --entry --entry-label="Nombre de la playlist")"
    playlist="$(ssh moode "python3 ${hugo_dir}/sp_crear_playlist.py ${pl_name}")"
fi

# dup="$(ssh hugo "python3 ${hugo_dir}/sp_duplicate.py")"
# echo "$dup"

# if [[ $dup =~ "nota" ]]; then
ssh moode "python3 ${hugo_dir}/sp_add_song_to_playlist.py ${id} ${playlist}"
# else
#     yad --text="${titulo} ya se ha añadido a la playlist: ${pl_name}" --timeout=2
#     exit 0
# fi

# Descargar caratula
sp_portada="${hugo_dir}/blog/vvmm/post/portadas/caratula-spotify.py"

ssh moode "python3 $sp_portada $artista $album"
rsync moode:hugo/image.jpeg .
ssh moode "rm hugo/image.jpeg"
url_def="https://open.spotify.com/playlist/${playlist}"  

if [[ -f image.jpeg ]]; then
    pregunta="$(yad --picture \
        --size=fit \
        --width=500 --height=500 \
        --filename="image.jpeg" \
        --timeout=5 \
        --text="$artista - $album" \
        --button="abrir playlist:2"
    )"
    # yad --button='!image.jpeg!Name:bash -c "chromium ${url_def}"'
            #--timeout-indicator=bottom \
    # rm image.jpeg
else
    yad --text="$artista - $titulo ($album)" \
        --timeout=5 \
        --button="abrir playlist:2"
fi

ret=$?
if [[ $ret -eq 2 ]]; then chromium $url_def ; fi
rm image.jpeg

bash "${HOME}"/Scripts/Musica/playlists/local/mirror_sp_pl.sh "${pl_name}"