#!/usr/bin/env bash
#
# Script Name: mover_mix.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:
#
#



# buscar canción en reproducción

dir=$(lsof -wc vlc | awk '$4~"[0-9]r" && $5=="REG"' | grep -o '/.*.flac$')
      # dir=$(sed "s/ |^ | $|\[|\]|\{|\}|\(|\)/\\\ /g" <<<"$dir")


# obtener nombre de archivo

archivo=$(lsof -wc vlc | awk '$4~"[0-9]r" && $5=="REG"' | grep -o '[^/]*.flac$')


# elegir carpeta a la que copiar

carpeta=$(zenity --info --title 'Copiando a Mixx' \
      --text "En que carpeta copiamos ${archivo}" \
      --ok-label Nolosé\
      --extra-button ambient\
      --extra-button deep\
      --extra-button keet\
      --extra-button jazz\
      --extra-button disco\
      --extra-button techno\
      --extra-button 'temas sueltos'\
      --extra-button 'añadir tag...'\
      )


# Copiar archivo a la carpeta seleccionada

destino="/mnt/Datos/Mix/${carpeta}/"
copia="$destino/$archivo"
echo "${carpeta}"

if [ -n "${carpeta}" ]
      then
            scp "${dir}" "${destino}"
fi


# Renombrar archivo copiado

tagutil -Yp rename:"%artist - %title [%date - %album]" "${copia}"