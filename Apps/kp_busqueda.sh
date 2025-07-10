#!/usr/bin/env bash
#
# Script Name: kp_busqueda.sh 
# Description: Abrir keepassxc con el cajon de busqueda enfocado
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:
#
#


keepassxc
wid=$(xdotool search --name "KeePassXC$")
xdotool windowfocus "${wid}"
sleep 0.5
xdotool key Control+F