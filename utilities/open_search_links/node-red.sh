#!/usr/bin/env bash
#
# Script Name: node-red.sh 
# Description: start node-red and open url. 
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:    Sin uso actual
#   Dependencies:
#       Firefox     Thorium-browser  Chromium   qutebrowser xdotool node-red
#

#busqueda=$(xclip -o)
node-red
app_actual=$(xdotool getactivewindow getwindowname)
thorium="Thorium$"
chromium="Chromium"
firefox="Mozilla Firefox"

url_1="https://localhost:1880"
url_2="https://192.168.1.132:1880"

if [[ ${app_actual} =~ ${thorium} ]]
    then
        thorium-browser "${url_1}" &
        thorium-browser "${url_2}" &
    elif [[ ${app_actual} =~ ${firefox} ]]; then
        firefox "${url_2}" &
        firefox "${url_1}" &
    elif [[ ${app_actual} =~ ${chromium} ]]; then
        chromium "${url_1}" &
        firefox "${url_2}" &
    else
        echo "${busqueda}"
        qutebrowser --target window "${url_1}" &
        qutebrowser --target window "${url_2}" &
fi


