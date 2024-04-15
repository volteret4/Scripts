#!/usr/bin/env bash
#
# Script Name: convertir_mp3_320.sh 
# Description: Convert flac to mp3 320kbps to sen to a vps of choice.
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#	Dependencies:
#		ffprobe
#



#variables
flacs="${HOME}/Musica/Arch/Musica/"
# oracle="ubuntu@143.47.33.148 -i ${HOME}/.ssh/config" 			#si esta configurado .ssh/config no se necesita esta linea


# seleccionar carpeta con diálogo del explorador de archivos
source="$(zenity --file-selection --filename="${flacs}" --directory)"
echo "${source}"


# preguntar si quiere enviar los archivos a gonic
tag=$(zenity --info --title "enviar disco subsonic"\
    --text "¿Quieres enviar este disco a subsonic?"\
    --extra-button "aro pish"\
    --ok-label "paso"\
) &


# seleccionar un archivo de la carpeta
file1="$(find "$source" -name "*.flac" -exec realpath {} \;  | head -n 1)"
echo "${file1}"


# obtener ARTIST de dicho archivo
artist1="$(ffprobe -v quiet -show_entries format_tags=album_artist -select_streams a:0 -of default=noprint_wrappers=1 "${file1}")"

if [[ -z ${artist1} ]]
	then
		artist1="$(ffprobe -v quiet -show_entries format_tags=artist -select_streams a:0 -of default=noprint_wrappers=1 "${file1}")"
fi
artist="$(echo "${artist1}" | cut -d'=' -f2-)"
echo "${artist}"


# obetener year de dicho archivo
year1="$(ffprobe -v quiet -show_entries format_tags=year -select_streams a:0 -of default=noprint_wrappers=1 "${file1}")"
if [[ -z ${year1} ]]
	then
		year1="$(ffprobe -v quiet -show_entries format_tags=date -select_streams a:0 -of default=noprint_wrappers=1 "${file1}")"
fi
year="$(echo "${year1}" | cut -d'=' -f2-)"
echo "${year}"


# obtener ALBUM de dicho archivo
album1="$(ffprobe -v quiet -show_entries format_tags=album -select_streams a:0 -of default=noprint_wrappers=1 "${file1}")"
album="$(echo "${album1}" | cut -d'=' -f2-)"
echo "${album}"


# crear carpeta de destino_mp3 del mp3
destino_mp3="/home/huan/Musica/Arch/mp3/${artist}/${year} - ${album}"
echo "${destino_mp3}"
mkdir -p "${destino_mp3}"
carpeta="/home/huan/Musica/Arch/mp3/${artist}"


# convertir a mp3 en la ruta elegida, con el mismo nombre de archivo
for f in "${source}"/*.flac ; do
	nombre_archivo=$(basename "$f")
	archivo_destino="${destino_mp3}/${nombre_archivo%.*}.mp3"
	ffmpeg -n -i "$f" -acodec libmp3lame -b:a 320k "$archivo_destino"
done


# copiar archivos de imagenes a la carpeta
cp "${source}"/*.jpeg "${destino_mp3}"
cp "${source}"/*.jpg "${destino_mp3}"
cp "${source}"/*.png "${destino_mp3}"
cp "${source}"/*.tiff "${destino_mp3}"
cp "${source}"/*.gif "${destino_mp3}"

# si no se ha rellenado $tag se vuelve a pedir
if [[ -z ${tag} ]]
	then
		tag=$(zenity --info --title "tw"\
			--text "¿Quieres enviar este disco a subsonic?"\
			--extra-button "aro pish"\
			--ok-label "paso"\
			)
fi


# declarar destino en servidor
destino="/home/ubuntu/contenedores/musica/archivos/albums/"


# enviar en caso afirmativo
if [[ "${tag}" =~ "aro pish" ]]
	then
		#ssh oracle mkdir -p "${destino}"
		rsync -avzh "${carpeta}" oracle:"${destino}"
		echo "archivos enviados"

		# borrar archivos mp3
		rm -rf "${destino_mp3}"
fi

echo "THE END"
