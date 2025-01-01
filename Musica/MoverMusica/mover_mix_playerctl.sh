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

mixxx="/mnt/windows/Mix"        # CHANGE!!

# function urldecode() { : "${*//+/ }"; echo -e "${_//%/\\x}"; }

# Obterner ruta del archivo en reproducción
deadbeef="$(deadbeef --nowplaying-tf "%artist%")"

if [ -z "$deadbeef" ]               # Detectar reproductor activo y obtener metadata de la canción en reproducción.
then                                                 
            dir=$(playerctl metadata xesam:url)
            dir2=$(sed 's/^file:\/\///' <<< "${dir}")

            archivo=$(echo "${dir2}" | sed -n 's/^\(.*\/\)*\(.*\)/\2/p') # deja solo la ultima carpeta de una ruta, tras la última "/" barra.
            archivo="$(echo ${archivo} | sed 's/[\":]//g')"
            #archivo2="${archivo//&/and/}"
            cancion=$(playerctl -p strawberry metadata title) # obtener titulo de la canción.
            dup=$(find ${mixxx} -iname "*$cancion*")  # comprobar duplicados.
      else
            dir2=$(deadbeef --nowplaying-tf "%path%")
            archivo=$(deadbeef --nowplaying-tf "%filename_ext%")
            archivo="$(echo ${archivo} | sed 's/[\":]//g')"
            cancion=$(deadbeef --nowplaying-tf "%artist% - %title%")
            dup=$(find ${mixxx} -iname "${cancion}*") # comprobar duplicados.           
fi

# Establecer TAG comentario.
if [[ -z ${dup} ]]; then
      comentario="$(yad --entry --title=comentario --text="COMENTARIO: $cancion")"
      if [[ -z  $comentario ]]; then notify-send -u critical -t 2000 "Cancelada copia a Mixx" ; exit 1 ; fi
fi


# Localizar carpeta original
cancion_path="$(dirname ${dir2})"
cancion_folder="$(basename ${cancion_path})"       # carpeta en que está el duplicado.

# Ruta de la carpeta que contiene las subcarpetas
ruta_carpeta="/mnt/windows/Mix"

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


# Buscar duplicados
if [ -z "$dup" ]
      then
            # Mostrar el cuadro de diálogo con los botones generados dinámicamente
            echo "BOTONES_ $botones"
            carpeta_seleccionada="$(python3 $HOME/Scripts/utilities/menu_pollo2.py $botones | awk 'NR==1 {print $1}')"
            if [[ -z $carpeta_seleccionada ]]; then 
                  notify-send -u critical -t 3000 "Cancelada la copia"
                  exit 0
            fi
            echo "AAAAAAAAAAAAAAA>>>>   $carpeta_seleccionada"
            # Si se presiona "Añadir carpeta...", solicitar al usuario el nombre de la nueva carpeta
            if [[ "$carpeta_seleccionada" == *"Otra"* ]]; then
                nombre_nueva_carpeta=$(yad --entry --text "Crear nueva carpeta")
                if [[ -n "$nombre_nueva_carpeta" ]]; then
                    nueva_carpeta="$ruta_carpeta/$nombre_nueva_carpeta"
                    mkdir "$nueva_carpeta"
                    carpeta_seleccionada="$nombre_nueva_carpeta"
                fi
            fi

            # Copiar archivo en carpeta de Mixxx
            destino="$mixxx/$carpeta_seleccionada"
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
            tagutil -Yp clear:comment $copia
            tagutil -Yp add:comment="${comentario}" $copia
            tagutil -Yp rename:"%artist - %title [%date - %album]" "$copia" # renombra nueva canción
            
                        
            # LOG.
            genero_ori="${cancion_folder}"
            genero_def="${carpeta_seleccionada}"
            

            
      else
            # En caso de existir la canción en Mixxx
            dup_path="$(dirname ${dup})"
            echo $dup_path
            dup_folder="$(basename ${dup_path})"       # carpeta en que está el duplicado.
            if [[ $dup_path =~ ${mixxx}/rebujo ]]; then
                  porcohone='Mover'
            else
                  porcohone=$(zenity --info --title 'Canción en Mixxx'\
                        --text "Canción encontrada en: $dup"\
                        --ok-label 'Ah! Perdona'\
                        --extra-button 'Copiar'\
                        --extra-button 'Mover'\
                        --extra-button 'Comentar TAG'\
                        )
            fi
fi
echo "${porcohone}"
if [[ ${porcohone} =~ 'Comentar TAG' ]]
      then
            com1="$(tagutil print ${dup} | grep "comment")"
            com2="$(echo ${com1} | sed 's/- comment: //')"
            echo $com2
            comentario="$(yad --entry --title=comentario --entry-text="${com2}, " --text="COMENTARIO: ${cancion} \n EN: ${dup_folder}")"
            tagutil -Yp set:comment="${comentario}" "${dup}"
fi

# Copiar / sobreescribir
if [[ "${porcohone}" =~ 'Copiar' ]]
      then
            carpeta_seleccionada="$(python3 $HOME/Scripts/utilities/menu_pollo2.py $botones | awk 'NR==1 {print $1}')"
            if [[ -z $carpeta_seleccionada ]]; then 
                  notify-send -u critical -t 3000 "Copia cancelada por cohone"
                  exit 0
            fi
            # Si se presiona "Otra carpeta...", solicitar al usuario el nombre de la nueva carpeta
            if [[ "$carpeta_seleccionada" == "Otra" ]]; then
                nombre_nueva_carpeta=$(yad --entry --title "Crear nueva carpeta" --text "Ingresa el nombre de la nueva carpeta:")
                if [[ -n "$nombre_nueva_carpeta" ]]; then
                    nueva_carpeta="$ruta_carpeta/$nombre_nueva_carpeta"
                    mkdir "$nueva_carpeta"
                    carpeta_seleccionada="$nombre_nueva_carpeta"
                fi
            fi

            # Copiar archivo
            destino="${mixxx}/${carpeta_seleccionada}"
            echo "${carpeta_seleccionada}"
            if [ ! -z "${carpeta_seleccionada}" ]
                  then
                        echo "copia duplicada"
                        notify-send -u critical -t 5000 "Se esta creando una copia de ${dir2} en ${carpeta_seleccionada}"
                        scp "${dir2}" "${destino}"
                        # LOG.
                        genero_ori="${dup_folder}"
                        genero_def="${carpeta_seleccionada}"
            fi
            # Tags
            copia="$destino/$archivo"
            echo "${copia}"
            echo "sleeping 5"
#___            sleep 5
            comentario="$(yad --entry --title=comentario --text="COMENTARIO: $cancion")"
            tagutil -Yp clear:comment $copia
            tagutil -Yp add:comment="${comentario}"
            tagutil -Yp rename:"%artist - %title [%date - %album]" "$copia"
                       
fi

if [[ "${porcohone}" =~ 'Mover' ]]
      then
            carpeta_seleccionada="$(python3 $HOME/Scripts/utilities/menu_pollo2.py $botones | awk 'NR==1 {print $1}')"
            if [[ -z $carpeta_seleccionada ]]; then 
                  notify-send -u critical -t 3000 "Cancelado el movimiento"
                  exit 0
            fi

                  # Si se presiona "Otra carpeta...", solicitar al usuario el nombre de la nueva carpeta
            if [[ "$carpeta_seleccionada" == *"Otra"* ]]; then
                nombre_nueva_carpeta=$(yad --entry --text "Crear nueva carpeta")
                if [[ -n "$nombre_nueva_carpeta" ]]; then
                    nueva_carpeta="$ruta_carpeta/$nombre_nueva_carpeta"
                    mkdir "$nueva_carpeta"
                    carpeta_seleccionada="$nombre_nueva_carpeta"
                fi
            fi

            # if [[ "$carpeta_seleccionada" == *"old"* ]]; then
            #       genre="$(dirname "$dup")"
            #       genre2="$(basename "$genre")"
            #       carpeta_seleccionada=".old/$genre2/"
            #       echo "old genre2= $genre2"
            # fi

            # Añadir comentario
            com1="$(tagutil print ${dup} | grep "comment")"
            com2="$(echo ${com1} | sed 's/- comment: //')"
            echo $com2
            comentario="$(yad --entry --title=comentario --entry-text="${com2}, " --text="COMENTARIO: ${cancion} \n EN: ${dup_folder}")"
            tagutil -Yp set:comment="${comentario}" "${dup}"

            # MOVER archivo
            destino="${mixxx}/${carpeta_seleccionada}"
            echo "dup:        ${dup}"
            echo "dest:       ${destino}"
            if [ ! -z "${carpeta_seleccionada}" ]
                  then
                        echo "moviendo archivo"
                        notify-send -u critical -t 5000 "Se esta moviendo ${dir2} a ${carpeta_seleccionada}"
                        deadbeef --next
                        mv "${dup}" "${destino}"
                        # LOG.
                        fecha="$(date +%Y-%m-%d)"
                        file="${dup}"
                        genero_ori="${dup_folder}"
                        genero_def="${carpeta_seleccionada}"
            fi
fi      

# Actualizar playlists para Mixxx
rm ${mixxx}/*.m3u
cd ${mixxx}
for dir in *; do find "$dir" -type f > "${dir}.m3u"; done

bash "${HOME}/Scripts/Musica/playlists/spotify/spotify_add_song.sh"

# Log de movimiento de canciones

