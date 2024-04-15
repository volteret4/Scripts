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

mixxx="/mnt/Datos/Mix"        # CHANGE!!


# function urldecode() { : "${*//+/ }"; echo -e "${_//%/\\x}"; }

# player=$(playerctl -l)


# Obterner ruta del archivo en reproducción
deadbeef="$(deadbeef --nowplaying-tf "%artist%")"

if [ -z "$deadbeef" ]
      then
            dir=$(playerctl metadata xesam:url)
            dir2=$(sed 's/^file:\/\///' <<< "${dir}")

            # if [[ $player =~ 'quodlibet']]
            #       then
            #             urldecode $dir2
            #             echo $dir2
            # fi

            archivo=$(echo "${dir2}" | sed -n 's/^\(.*\/\)*\(.*\)/\2/p') # deja solo la ultima carpeta de una ruta, tras el último /
            archivo2="${archivo//&/and/}"
            cancion=$(playerctl -p strawberry metadata title) # obtener titulo de la canción
            dup=$(find /mnt/A26A-AAE7/Mix -iname "*$cancion*") # comprobar duplicados
      else
            dir2=$(deadbeef --nowplaying-tf "%path%")
            archivo=$(deadbeef --nowplaying-tf "%filename_ext%")
            cancion=$(deadbeef --nowplaying-tf "%filename_ext%")
            dup=$(find /mnt/Datos/Mix -iname "*${cancion}*") # comprobar duplicados
fi


# Ruta de la carpeta que contiene las subcarpetas
ruta_carpeta="$mixxx"

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
#    botones+="--extra-button $subcarpeta "
    primera_letra="${subcarpeta:0:1}"
    botones+="${subcarpeta}:${primera_letra} "
done

#carpeta_seleccionada="$(python3 $HOME/Scripts/utilities/menu_pollo2.py $botones | awk 'NR==1 {print $1}')"

#echo "carpeta_seleccionada________________${carpeta_seleccionada}"

# Buscar duplicados
if [ -z "$dup" ]
      then
            # # Mostrar el cuadro de diálogo con los botones generados dinámicamente
            # carpeta_seleccionada=$(zenity --info --title 'Copiando a Mixx' \
            # --text "En qué carpeta copiamos $archivo2" \
            # --extra-button "|___...Añadir Otra Carpeta...___|"\
            # --ok-label "En verdad paso..." \
            # $botones)
            carpeta_seleccionada="$(python3 $HOME/Scripts/utilities/menu_pollo2.py $botones | awk 'NR==1 {print $1}')"

            echo "AAAAAAAAAAAAAAA>>>>   $carpeta_seleccionada"
            # Si se presiona "Añadir carpeta...", solicitar al usuario el nombre de la nueva carpeta
            if [[ "$carpeta_seleccionada" == *"Otra"* ]]; then
                nombre_nueva_carpeta=$(zenity --entry --title "Crear nueva carpeta")
                if [[ -n "$nombre_nueva_carpeta" ]]; then
                    nueva_carpeta="$ruta_carpeta/$nombre_nueva_carpeta"
                    mkdir "$nueva_carpeta"
                    carpeta_seleccionada="$nombre_nueva_carpeta"
                fi
            fi

            # Copiar archivo en carpeta de Mixxx
            destino="/mnt/Datos/Mix/$carpeta_seleccionada"
            echo "carpeta destino: ${carpeta_seleccionada}"
            if [ ! -z "$carpeta_seleccionada" ]
                  then
                        echo "ok ${dir}_$destino"
                        scp "${dir2}" "${destino}"
            fi

            # tags
            copia="$destino/$archivo"
            echo "copia: ${copia}"
            echo "esperando 5s a que se copie para renombrar archivo"
            sleep 5
            tagutil -Yp rename:"%artist - %title [%year - %album]" "$copia" # renombra nueva canción

      else
            # En caso de existir la canción en Mixxx
            porcohone=$(zenity --info --title 'Canción en Mixxx'\
                  --text "Canción encontrada en:\n $dup"\
                  --ok-label 'Ah! Perdona'\
                  --extra-button 'Copiar'\
                  )
fi
echo "${porcohone}"

# Copiar / sobreescribir
if [[ "${porcohone}" =~ 'Copiar' ]]
      then
            carpeta_seleccionada="$(python3 $HOME/Scripts/utilities/menu_pollo2.py $botones | awk 'NR==1 {print $1}')"
                           
            # carpeta_seleccionada=$(zenity --info --title 'Copiando a Mixx' \
            # --text "En qué carpeta copiamos $archivo2" \
            # --extra-button "|___...Añadir Otra Carpeta...___|"\
            # --ok-label Nolosé \
            # $botones)

            # Si se presiona "Otra carpeta...", solicitar al usuario el nombre de la nueva carpeta
            if [[ "$carpeta_seleccionada" == "Otra" ]]; then
                nombre_nueva_carpeta=$(zenity --entry --title "Crear nueva carpeta" --text "Ingresa el nombre de la nueva carpeta:")
                if [[ -n "$nombre_nueva_carpeta" ]]; then
                    nueva_carpeta="$ruta_carpeta/$nombre_nueva_carpeta"
                    mkdir "$nueva_carpeta"
                    carpeta_seleccionada="$nombre_nueva_carpeta"
                fi
            fi

            # Copiar archivo
            destino="/mnt/Datos/Mix/${carpeta_seleccionada}"
            echo "${carpeta_seleccionada}"
            if [ ! -z "${carpeta_seleccionada}" ]
                  then
                        echo "ok2"
                        scp "${dir2}" "${destino}"
            fi
            # Tags
            copia="$destino/$archivo"
            echo "${copia}"
            echo "sleeping 5"
            sleep 5
            tagutil -Yp rename:"%artist - %title [%date - %album]" "$copia"
fi
