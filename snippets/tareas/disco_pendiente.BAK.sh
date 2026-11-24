#!/usr/bin/env bash
#
# Script Name: disco_pendiente.BAK.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#
#



rc=1 # OK button return code =0 , all others =1
#while [ $rc -eq 1 ]; do
#do{
ans=$(zenity --info --title 'Qué género' \
      --text "Elige cuando quieres escuchar $(xclip -o)" \
      --ok-label Nolosé \
      --extra-button ambient \
      --extra-button deep \
      --extra-button ket \
      --extra-button awakenings \
      --extra-button techno \
      --extra-button metal \
      --extra-button jazz \
      )
rc=$?
# echo "${rc}-${ans}"
# echo $ans
if [[ $ans = "ambient" ]]
      then
            todo.sh -t add $(xclip -o) +ambient
      elif [[ $ans = "deep" ]]
      then
            todo.sh -t add $(xclip -o) +deep
      elif [[ $ans = "ket" ]]
      then
            todo.sh -t add $(xclip -o) +ket
      elif [[ $ans = "awakenings" ]]
      then
            todo.sh -t add $(xclip -o) +awakenings
      elif [[ $ans = "techno" ]]
      then
            todo.sh -t add $(xclip -o) +techno
      elif [[ $ans = "metal" ]]
      then
            todo.sh -t add $(xclip -o) +metal
      elif [[ $ans = "jazz" ]]
      then
            todo.sh -t add $(xclip -o) +jazz
fi
