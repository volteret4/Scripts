#!/usr/bin/env bash
#
# Script Name: lidarr.sh 
# Description: Crear $var con el artista desde el portapapeles. Definir API key $var
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
#   - Replace hardcoded paths
# Notes:
#   .env content:
#       $LIDARR_URL    $LIDARR_API
#


nartista=$(xclip -o)
artistas_lidarr="${HOME}/Scripts/Musica/artistas_lidarr.json"   # CHANGE!!


# Solicitar listado actual de artistas en la biblioteca de Lidarr

curl "${URL}/artist\?apikey\=${API}" > "${HOME}/Scripts/Musica/artistas_lidarr.json"
listado_artista="$(cat "${HOME}/Scripts/Musica/artistas_lidarr.json" | jq '.[] .artistName')"
echo ${listado_artista} > "${HOME}/Scripts/Musica/artistas_lidarr_filtrados.json"


# Comprobar si existe el artista en la biblioteca de Lidarr.

add_artist="$(grep -io "${nartista}" /home/huan/Scripts/Musica/artistas_lidarr_filtrados.json)"
echo "${add_artist}"
if [ -z "${add_artist}" ]
    then
        acc=$(zenity --info --title 'Artista no está en Lidarr'\
        --text "Quieres añadir a ${nartista} a Lidarr"\
        --extra-button 'En verdad no' \
        --extra-button 'OmepoFavo' \
    )
    else
        zenity --info --text "Este artista ya estaba en Lidarr" --ok-label "No seas fatiga"
fi


# En caso de que no exista, añadirlo.

if [ "${acc}" = 'OmepoFavo' ]
    then

        curl  ${URL}/artist/lookup?term=${nartista}&apikey\=${API} > ${HOME}/Scripts/Musica/artista_nuevo.json

        for i in `seq 0 3`; do

            var5=$(cat ${HOME}/Scripts/Musica/artista_nuevo.json | jq ".[$i] .artistName,.[$i] .artistMetadataId, .[$i] .disambiguation" | awk 'NR == 2 {print $1}')
            overview=$(cat ${HOME}/Scripts/Musica/artista_nuevo.json | jq ".[$i] .overview")
            disamb=$(cat ${HOME}/Scripts/Musica/artista_nuevo.json | jq ".[$i] .disambiguation")
            if [ "${var5}" != 0 ]
                then
                    info=$(zenity --info --title "Información sobre ${nartist}"\
                    --text "${disamb} ${overview}"\
                    --ok-label "Enviar a Lidarr"\
                    --extra-button "Overview"\
                    )
            fi
        done
fi

#tr ' ' '\n'
