#!/usr/bin/env bash
#
# Script Name: save_playlist.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#
#



player=$(xdotool search --onlyvisible --name "\- mpv$")
xdotool windowfocus "${player}"
xdotool key k
xdotool key --repeat 25 --delay 50 BackSpace
sleep 1
xdotool type --delay 40 --window "${player}" "${MPV}"
sleep 1
xdotool key Enter