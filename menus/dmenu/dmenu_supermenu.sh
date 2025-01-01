#!/usr/bin/env bash

declare options=("dotfiles
edit_scripts
web
yt_channels
yt_busqueda
search_google
mpd
mix
quit")

choice=$(echo -e "${options[@]}" | dmenu -l -i -p 'Elige dmenu: ')

case "$choice" in
	quit)
		echo "Program terminated." && exit 1
	;;
	yt_busqueda)
		choice="${HOME}/Scripts/menus/yt_busqueda.sh"					# CHANGE!!
	;;
    dotfiles)
		choice="${HOME}/Scripts/menus/dmenu/dmenu_dotfiles.sh"			# CHANGE!!
	;;
	edit_scripts)
		choice="${HOME}/Scripts/menus/dmenu/dmenu_edit_scripts.sh"		# CHANGE!!
	;;
	yt_channels)
		choice="${HOME}/Scripts/menus/yt_channels.sh"					# CHANGE!!
	;;
	web)
		choice="${HOME}/Scripts/menus/dmenu/dmenu_web.sh"				# CHANGE!!
	;;
	search_google)
		choice="${HOME}/Scripts/menus/dmenu/dmenu_search_google.sh"		# CHANGE!!
	;;
	mpd)
		choice="${HOME}/Scripts/menus/dmenu/dmenu_mpd.sh"
	;;				# CHANGE!!
	mix)
		choice="${HOME}/Scripts/menus/rofi/mix_fuzzy.sh"				# CHANGE!!
	;;
	*)
		exit 1
	;;
esac


bash "${choice}"