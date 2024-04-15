#!/usr/bin/env bash
#
# Script Name: copiar_album_moode_temp.sh 
# Description: Copy album playing to rasberry with moode.
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#   Dependencies:
#       strawberry
#



# Extraer ruta de la canción que esté sonando en Strawberry

dir="$(lsof -wc strawberry | awk '$4~"[0-9]r" && $5=="REG"' | grep -o '/.*.flac$')"
echo "1 ${dir}" > "$HOME"/Scripts/MoverMusica/testing
dir="$(awk 'FNR <= 1' "$HOME"/Scripts/MoverMusica/testing)"
#dir="$(sed 's/ /\ /' <<< "${dir}")"

# 1. Recortar inico file:///

#dir2="$(sed 's/^file:\/\///' <<< "${dir}")"
#echo "${dir2}"


# 2. Recortar nombre de la canción, dejando ruta del album

dir3="$(readlink -f "${dir}")"
echo "2 ${dir3}"


# 3. Recortar y dejar solo el nombre del album

album="$(echo "${dir3}" | sed -n 's/^\(.*\/\)*\(.*\)/\2/p' )"
echo "3 ${album}"


# 4. Buscar duplicados en moode/temp. Si no los hay, copiar album

        #dup=$(find moode:/media/passport/Musica/Temp/ -iname "*$cancion*")
dupli="$(ssh moode ls /media/passport/Musica/temp | grep "${album}")"
echo "4 ${dupli}"
if [ -z "${dupli}" ]
    then
        destino="moode:/media/passport/Musica/temp/${album}"
        scp -r "${dir3}" "${destino}"
        copia="${destino}"/"${archivo}"
        echo "${copia}"
        else
            zenity --info --title 'Disco encontrado en moode temp'\
                --text "Disco encontrado en moode temp: ""${dupli}"""\
                --ok-label 'Ah Perdona'\
                --extra-button 'Copiar'\

fi