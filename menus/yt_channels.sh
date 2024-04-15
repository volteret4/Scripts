#!/usr/bin/env bash
#
# Script Name: yt_channels.sh 
# Description: Open list of channels of different files with ytfzf.
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
#	- Change termite
# Notes:
#	Dependencies:
#		ytfzf
#		termite
#

declare options=("entretenimiento
musica
humor
sonido
sellos
deep
ambient
sesiones
techno_house
quit")

choice=$(echo -e "${options[@]}" | dmenu -l -i -p 'Youtube Canales: ')

case "$choice" in
	quit)
		echo "Program terminated." && exit 1
	;;
	ambient)
		choice="${HOME}/.dotfiles/config/ytfzf/ambient"
	;;
    deep)
		choice="${HOME}/.dotfiles/config/ytfzf/deep"
	;;
    sonido)
		choice="${HOME}/.dotfiles/config/ytfzf/sonido"
	;;
	entretenimiento)
		choice="${HOME}/.dotfiles/config/ytfzf/entretenimiento"
	;;
	musica)
		choice="${HOME}/.dotfiles/config/ytfzf/musica"
	;;
	sesiones)
		choice="${HOME}/.dotfiles/config/ytfzf/sesiones"
	;;
	humor)
		choice="${HOME}/.dotfiles/config/ytfzf/humor"
    ;;
	sellos)
		choice="${HOME}/.dotfiles/config/ytfzf/sellos"
    ;;
	techno_house)
		choice="${HOME}/.dotfiles/config/ytfzf/techno_house"
	;;
	*)
		exit 1
	;;
esac

cp "${choice}" "${HOME}"/.config/ytfzf/subscriptions
sleep 0.5
termite --hold -e "ytfzf -tcSI"
