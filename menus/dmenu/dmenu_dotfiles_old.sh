#!/usr/bin/env bash
#
# Script Name: dmenu_dotfiles_old.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#
#




# ---------------------------------------------------------
# Name:   			dmenu-edit-configs
# Author: 			Cyr4x3
# Orig. Author: Derek Taylor
# Descr.: 			Dmenu script for editing some of my more
# 							frequently edited config files.
# ---------------------------------------------------------

# NOTE:
# -----
# This script uses the .dotfiles folder, as I am a user of
# rcm. This may not be the case for you and the paths
# displayed here may not work.
# Don't forget to change the path to the configs' path in
# your system.


declare options=("alacritty
awesomewm
bash
bash_aliases
copyq
dmenurc
filezilla
flameshot
geany
hexchat
KeePass
keepassxc
khal
mpdnotify
mpv
neovim
rofi
strawberry
syncthing
termite
thunar
taskrc
TODO
todoman
transmission-remote-gtk
vdirsyncer
vim
vlc
VSCodium
xbindkeysrc
xfce4-terminal
xfce4-taskmanager
xinitrc
Xmodmap
ytfzf
zsh_aliases
zshrc
zsh_confs
quit")

choice=$(echo -e "${options[@]}" | dmenu -l -i -p 'Edit config file: ')

case "$choice" in
	quit)
		echo "Program terminated." && exit 1
	;;
	alacritty)
		choice="$HOME/.dotfiles/config/alacritty/alacritty.yml"
	;;
	bash)
		choice="$HOME/.dotfiles/bashrc"
	;;
	bash_aliases)
		choice="$HOME/.dotfiles/bash_aliases"
	;;
	awesomewm)
		choice="$HOME/.dotfiles/config/awesomewm/rc.lua"
	;;
	copyq)
		choice="$HOME/.dotfiles/config/copyq/copyq.conf"
	;;
	dmenurc)
		choice="$HOME/.dotfiles/dmrc"
	;;
	geany)
		choice="$HOME/.dotfiles/config/geany/geany.conf"
	;;
	mpv)
		choice="$HOME/.dotfiles/config/mpv/mpv.conf"
	;;
	taskrc)
		choice="$HOME/.dotfiles/taskrc"
	;;
	mpdnotify)
		choice="$HOME/.dotfiles/config/mpdnotify.conf"
	;;
	termite)
		choice="$HOME/.dotfiles/config/termite/config"
	;;
	neovim)
		choice="$HOME/.config/nvim/init.vim"
	;;
	thunar)
		choice="$HOME/.dotfiles/config/Thunar/uca.xml"
	;;
	khal)
		choice="$HOME/.dotfiles/khal/config"
	;;
	vdirsyncer)
		choice="$HOME/.dotfiles/config/vdirsyncer"
	;;
	rofi)
		choice="$HOME/.dotfiles/config/rofi/config.rasi"
	;;
	quickmarks)
		choice="$HOME/.config/qutebrowser/quickmarks"
#	;;
#	qutebrowser)
#		choice="$HOME/.config/qutebrowser/autoconfig.yml"
	;;
	VSCodium)
		choice="$HOME/.dotfiles/config/VSCodium/User/settings.json"
	;;
	st)
		choice="$HOME/.bin/suckless-builds/st-0.8.4/config.def.h"
	;;
	startpages)
		choice="$HOME/Documents/Linux/Personalizacion/Firefox/Startpages"
	;;
	terminator)
		choice="$HOME/.dotfiles/config/terminator/config"
	;;
	vifm)
		choice="$HOME/.dotfiles/config/vifm/vifmrc"
#	;;
#	vim)
#		choice="$HOME/.vimrc"
	;;
	weechat)
		choice="$HOME/.dotfiles/weechat"
	;;
	xmobar)
		choice="$HOME/.dotfiles/config/xmobar/xmobarrc"
	;;
	xmonad)
		choice="$HOME/.dotfiles/xmonad/xmonad.hs"
	;;
	xresources)
		choice="$HOME/.Xresources"
	;;
	ytfzf)
		choice="$HOME/.dotfiles/config/ytfzf/conf.sh"
	;;
	zshrc)
		choice="$HOME/.dotfiles/zshrc"
	;;
	zsh_confs)
		choice="$HOME/.dotfiles/config/zsh"
	;;
	*)
		exit 1
	;;
esac

termite -e "vim "${choice}""