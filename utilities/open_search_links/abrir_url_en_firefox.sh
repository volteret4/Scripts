#!/usr/bin/env bash
#
# Script Name: abrir_url_en_firefox.sh 
# Description: send url from chrome to firefox
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#       Dependencies:
#               Firefox        Chromium  xdotool
#

var="$(xwininfo -id "$(xdotool getactivewindow)" | head -n2 | sed 's/^[^"]*"\([^"]*\)"/\1/')"
regex="Thorium$|Chromium$"


if [[ ${var} =~ ${regex} ]]
        then
                wid=$(xdotool search --name "Chromium")
                echo "$wid"
                xdotool windowfocus "${wid}"
                sleep 0.4
                xdotool key "ctrl+l"
                xdotool key "ctrl+c"
        else
                xdotool key "ctrl + c"
fi
url=$(xclip -o)
echo "${url}"
firefox "${url}" &
