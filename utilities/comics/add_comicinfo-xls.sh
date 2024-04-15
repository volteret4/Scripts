#!/usr/bin/env bash
#
# Script Name: add_comicinfo-xls.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#
#


# Carpeta donde se encuentran los archivos .cbr
carpeta="$1"
echo $carpeta

# Cambiar al directorio de la carpeta
cd "$carpeta" || exit

# Bucle for para iterar sobre los archivos .cbr
for archivo_cbr in *.cbr; do
    # Obtener el número de la edición
    issue=$(echo "$archivo_cbr" | grep -Po '\d+(?=\.[^.]*$)')

    # Cambiar la extensión a .rar
    archivo_rar="${archivo_cbr%.cbr}.rar"
    mv "$archivo_cbr" "$archivo_rar"

    # Crear el archivo comicinfo.xml dentro de la carpeta
    cat <<EOF > ComicInfo.xml
<?xml version='1.0' encoding='utf-8'?>
<ComicInfo xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <Title></Title>
  <Series>Fables</Series>
  <Number>$issue</Number>
  <Publisher>DC Comics</Publisher>

</ComicInfo>
EOF
    rar a "$archivo_rar" ComicInfo.xml
    mv "$archivo_rar" "$archivo_cbr"
    rm ComicInfo.xml
    
done
tree
