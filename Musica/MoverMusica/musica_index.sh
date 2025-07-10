#!/usr/bin/env bash
#
# Script Name: musica_index.sh 
# Description: Script para centralizar todos los scripts que usan la canción que está sonando.
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:
#
#


opcion="$(zenity --info --title "musica"\
    --text "Que quieres hacer con lo que suena?"\
    --extra-button "Enviarlo a moode"\
    --extra-button "Enviarlo a Mix"\
    --extra-button "Enviarlo a playlist"\
    --extra-button "Crear post en blog"\
    --extra-button "Buscar informacion!"\
    --ok-label "paso"\
)"

if [[ $opcion =~ 'Enviarlo a moode' ]]
    then
        bash "$HOME/Scripts/MoverMusica/copiar_album_moode_temp.sh"
    elif [[ "$opcion" =~ 'Enviarlo a Mix' ]]
        then
            bash "$HOME/Scripts/MoverMusica/mover_mix_playerctl.sh"
    elif [[ "$opcion" =~ 'Enviarlo a playlist' ]]
        then
            bash "$HOME/Scripts/MoverMusica/playlist_spotify.sh"
    elif [[ "$opcion" =~ 'Crear post en blog' ]]
        then
            bash "$HOME/Scripts/wordpress/crear_post_gpt.sh"
    elif [[ "$opcion" =~ 'Buscar informacion' ]]
        then
            bash "$HOME/Scripts/wordpress/busqueda_multiple.sh"
fi