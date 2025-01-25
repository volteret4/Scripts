#!/usr/bin/env bash
#
# Script Name: dmenu_search.sh 
# Description: google search on rofi
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO:  
# Notes:
#       WORK IN PROGRESS
#



dir="${HOME}/Scripts/menus/dmenu"

if [ -f "${HOME}"/.dmenurc ]; then
    . "${HOME}"/.dmenurc
else
    DMENU='rofi -show drun -i'
fi

echo "${GS}"
GS="$(cat "${dir}"/.{gs}hist | "${DMENU}" $*)"
echo "2 ""${GS}"""
if grep -q "${GS}" "$dir/.{gs}hist" ; then
    echo already exists in history
else
    echo "${GS}" | sed 's/^(\ +)?(m|i)?(\ +)?//' >> ${dir}/.{gs}hist
fi
echo "3 ""${GS}"""
# Añadidos pollo
#
# Si fuera una de las siguientes webs realizar la busqueda en su propio motor.

musica="^(\ +)?m\ +"
informatica="^(\ +)?i\ +"
if [[ ${GS} =~ ${musica} ]]
    then
        GS="${GS//^(\ +)?m(\ +)?//}"
        firefox <"${GS}" &
        firefox https://bandcamp.com/search?q="${GS}" &
    elif [[ ${GS} =~ ${informatica} ]] ;  then
            GS="${GS//^(\ +)?i(\ +)?//}"
            firefox https://stackoverflow.com/search?q="${GS}" &
            firefox https://github.com/search?q="${GS}" &
            firefox https://www.quora.com/search?q="${GS}" &
    else
        firefox https://www.google.es/search?q="${GS}" &
fi


