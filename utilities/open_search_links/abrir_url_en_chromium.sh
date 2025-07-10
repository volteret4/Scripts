#!/usr/bin/env bash
#
# Script Name: abrir_url_en_chromium.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:
#       Dependencies:
#               Firefox        Thorium-browser  xdotool
#

var="$(xwininfo -id "$(xdotool getactivewindow)" | head -n2 | sed 's/^[^"]*"\([^"]*\)"/\1/')"
regex="Firefox$"


if [[ ${var} =~ ${regex} ]]
        then
                wid=$(xdotool search --name "Mozilla Mirefox")
                xdotool windowfocus "${wid}"
                sleep 0.5
                xdotool key "ctrl+l"
                xdotool key "ctrl+c"
        else
                xdotool key "ctrl + c"
fi

url=$(xclip -o)
echo "${url}"
thorium-browser "${url}" &
