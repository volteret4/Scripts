#!/usr/bin/env bash
#
# Script Name: enviar torrents a dietpi
# Description: Mover torrents descargados a la carpeta WATCHED de deluge en dietpi
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:
#   Pendiente de cambiar a PROXMOX
#

temptorrent="$(mktemp)"
dir_descargas="${HOME}/Descargas"
find "$dir_descargas" -name '*.torrent' > "$temptorrent"
numero_t_pend="$(find "$dir_descargas" -name '*.torrent' | wc -l)"

if [[ $numero_t_pend = '0' ]]
    then
        yad --text="Error! No existen torrents en la carpeta de descarga" --fixed
        exit 1
fi

echo "$temptorrent"
echo CONTENIDO
cat "$temptorrent"
#   Enviar torrents de la carpeta Descargas
rsync -az -e ssh --no-relative --files-from="${temptorrent}" / dietpi:temptorrent/

sleep 1

echo ssh
#   Ejecutar script en dietpi que añadirá los torrents a deluge
ssh dietpi bash Scripts/MoverMusica/add_torrents_deluge.sh >&1

#   El script ejecutado mostrará unos resultados
echo -e "\n fin ssh \n \n"
#   Si todo va bien se borraran los archivos torrents locales, si no mostrará el resultado en zenity
if [ $? -eq 0 ]; then
    echo "El comando se ejecutó correctamente."
    notify-send "Se han enviado $numero_t_pend torrents a deluge"
    rm "$dir_descargas"/*.torrent
    echo "se borraron los archivos locales"
else
    echo "El comando fracaso estrepitosamente."
    texto="<b>$numero_t_pend</b>"
    yad --title="Mi diálogo" --text="Error al añadir $texto torrents" --markup --fixed
fi




