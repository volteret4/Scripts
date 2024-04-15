#!/usr/bin/env bash
#
# Script Name: crear_playlist_spotify.sh 
# Description: Crear playlist de spotify 
#               Usuario: pollo
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#
#

#   Definir venv de python

spotify_venv="${HOME}"/Documentos/python_envs/spotify/spotify


#   Definir archivo con titulo y descripción de la playlist.

playlist_file="${HOME}"/Documentos/python_envs/spotify/spotify/playlist.txt
songs_file="${HOME}"/Documentos/python_envs/spotify/spotify/canciones.txt
playlist="$(head -1 < "${playlist_file}")"


#   Establecer reproductor activo

players="$(playerctl -l)"
current_player=""

for player in $players; do
    player_status="$(playerctl -p "$player" status)"
    if [[ $player_status =~ "Playing" ]]; then
        current_player="$player"
        break
    fi
done


#   Obetener artista y titulo y añadirlo a la lista de canciones

if [[ -z $current_player ]]
    then
        notify-send 'No hay ninguna canción reproduciendose' 'Error' -t 10000
    elif [[ "$current_player" =~ 'firefox' || "$current_player" =~ 'chromium' ]]
        then
            song="$(playerctl -p "$current_player" metadata title)"
            song="$(zenity --entry --text "El reproductor actual es el siguiente...$current_player" --entry-text="$song")"
            echo "$song" > "$songs_file"
        else
            artist="$(playerctl -p "$current_player" metadata artist)"
            song="$(playerctl -p "$current_player" metadata title)"
            echo "$artist - $song" > "$songs_file"
fi

#   Elegir camino a elegir

camino="$(zenity --info --text "Por donde vas a tirar"\
    --extra-button "Nueva playlist"\
    --extra-button "Añadir canciones a $playlist"\
    --extra-button "Actualizar una existente"\
    )"

if [[ "$camino" =~ 'Nueva playlist' ]]

    #   Crear nueva playlist en caso de no querer la anterior
    then
        playlist="$(zenity --entry --title="playlist" --text="Introduce el titulo")"
        comentario="$(zenity --entry --title="playlist" --text="Introduce el comentario")"
        echo "${playlist}" > "${playlist_file}"
        echo "${comentario}" >> "${playlist_file}"
    elif [[ "$camino" =~ 'Añadir canciones' ]]
        then
            playlist="$(head -1 < "${playlist_file}")"
    elif [[ "$camino" =~ 'Actualizar una existente' ]]
        then
            #source "${spotify_venv}"/bin/activate
            error="$(mktemp)"
            python3 "${spotify_venv}"/playlist_actuales_spotify.py 2>"${error}"
            cat "ERROR: ${error} *_*"
            pick="$(awk -F',' '{print $1 "|" $2 "|" $3}' playlist_actuales_ids.txt | zenity --list --separator='|' --column "Canción")"
            pick_id="$(echo "$pick" | awk -F'|' '{for(i=NF;i>=1;i--) if($i!="") {print $i; break}}')"
            elegido="$(echo "$pick_id" | awk -F ' - ' '{print $NF}')"
            echo "$elegido" > "$playlist_file"
fi


#   Añadir canciones manualmente

manual="$(zenity --info --text="Quieres añadir canciones a ${playlist}"\
    --extra-button "Si ome")"

if [[ $manual =~ 'Si ome' ]]
    then
        lista="$(zenity --forms\
        --add-entry=1\
        --add-entry 2\
        --add-entry 3\
        --add-entry 4\
        --add-entry 5\
        --add-entry 6\
        --add-entry 7\
        --add-entry 8\
        --add-entry 9\
        --add-entry 0\
        )"

        #   Guardar lista en archivo temporal
        temp_file=$(mktemp)
        echo "${lista}" >> "${temp_file}"

        # Lee el archivo en una variable
        file_contents=$(cat "${temp_file}")

        # Reemplaza el carácter delimitador con un salto de línea
        new_contents=$(sed 's/|/\n/g' <<< "${file_contents}")

        # Elimina las líneas vacías
        new_contents=$(echo "${new_contents}" | tr -s '\n')

        # Muestra el resultado
        echo "${new_contents}" >> "${songs_file}"
fi


#   Actualizar playlist
if [[ "$camino" != 'Actualizar una existente' ]]
    then
        error2="$(mktemp)"
        #source "${spotify_venv}"/bin/activate
        python3 "${spotify_venv}"/spotify_playlist.py 2>"${error2}"
        echo "error 2 *_*"
        cat "{error2}"
        echo "error 2 *_*"
    else
        error3="$(mktemp)"
        python3 "${spotify_venv}"/actualizar_playlist_spotify.py 2>"${error3}"
        echo "error 3 *_*"
        cat "{$error3}"
        echo "error 3 *_*"
fi