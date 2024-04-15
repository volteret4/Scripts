#!/usr/bin/env bash
#
# Script Name: verificar_sig.sh 
# Description: Verifica el último archivo descargado que pese mas de 2MB* para que evite coger la firma con la que se comprobaran los hashes.
#       EN PROCESO AUN
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#
#



# Ruta a la carpeta que contiene los archivos descargados
download_dir="${HOME}/Descargas"

# Comprobar si hay archivos en la carpeta
if [ ! "$(ls -A "${download_dir}")" ]; then
    echo "No se encontraron archivos en la carpeta de descargas"
    exit 1
fi

# Encontrar el último archivo descargado en la carpeta
latest_file="$(find "${download_dir}" -type f -size +2M -printf "%T@\t%p\n" | sort -nr | head -n 1 | cut -f2-)" # *Aqui se especifica que ha de ser mayor a 2MB


# Verificar si existe un archivo .sig, checksum o txt para el último archivo descargado
if [ -f "${download_dir}/${latest_file}.sig" ]; then
    sig_file="${download_dir}/${latest_file}.sig"
    echo "${sigfile}"
elif [ -f "${download_dir}/checksum" ]; then
    sig_file="${download_dir}/checksum"
    echo "${sigfile}"
elif [ -f "${download_dir}/SHA256SUMS" ]; then
    sig_file="${download_dir}/SHA256SUMS"
    echo "${sigfile}"
elif [ -f "${download_dir}/CHECKSUM" ]; then
    sig_file="${download_dir}/CHECKSUM"
    echo "${sigfile}"
elif [ -f "${download_dir}/${latest_file}.txt" ]; then
    sig_file="${download_dir}/${latest_file}.txt"
    echo "${sigfile}"
else
    sig_file="$(zenity --file-selection --title="Selecciona un archivo" --text="No se ha encontrado checksum...)"
    echo "No se encontró ningún archivo .sig, checksum o txt y acabas de elegir uno"
fi

# Verificar el último archivo descargado con GPG si hay un archivo .sig
if gpg --verify "${sig_file}" "${download_dir}"/"${latest_file}"; then
        notify-send "El archivo ${latest_file} fue verificado con éxito con GPG" "Info" -t 2000
    else
        notify-send "El archivo ${latest_file} no pudo ser verificado con GPG" "Error" -t 2000
fi

