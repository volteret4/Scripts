#!/usr/bin/env bash
#
# Script Name: disco_pendiente.sh 
# Description: Añadir album a la lista de tareas todotxt para escuchar por genero
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:
#     HOTKEY: 
#



bash "${HOME}/Scripts/snippets/if_firefox_active.sh"
sleep 0.2
album=$(xclip -o | sed 's,\?label.*,,')
#rc=1 # OK button return code =0 , all others =1   # Abre un diálogo con las siguientes opciones:
#while [ $rc -eq 1 ]; do
#do{
ans=$(zenity --info --title 'Que genero' \
      --text "${album}" \
      --ok-label Nolose \
      --extra-button ambient \
      --extra-button deep \
      --extra-button ket \
      --extra-button awakenings \
      --extra-button techno \
      --extra-button metal \
      --extra-button jazz \
      --extra-button 'otro tag' \
      )
#rc=$?
# echo "${rc}-${ans}"
# echo $ans
if [[ $ans = "ambient" ]]                                   # Realizará una tarea dependiendo del botón seleccionado
      then
            todo.sh -t add "${album}" +ambient
            /home/huan/Scripts/actualizar-todotxt.sh
      elif [[ $ans = "deep" ]]
      then
            todo.sh -t add "${album}" +deep
            /home/huan/Scripts/actualizar-todotxt.sh
      elif [[ $ans = "ket" ]]
      then
            todo.sh -t add "${album}" +ket
            /home/huan/Scripts/actualizar-todotxt.sh
      elif [[ $ans = "awakenings" ]]
      then
            todo.sh -t add "${album}" +awakenings
            /home/huan/Scripts/actualizar-todotxt.sh
      elif [[ $ans = "techno" ]]
      then
            todo.sh -t add "${album}" +techno
            /home/huan/Scripts/actualizar-todotxt.sh
      elif [[ $ans = "metal" ]]
      then
            todo.sh -t add "${album}" +metal
            /home/huan/Scripts/actualizar-todotxt.sh
      elif [[ $ans = "jazz" ]]
      then
            todo.sh -t add "${album}" +jazz
            /home/huan/Scripts/actualizar-todotxt.sh
      elif [[ $ans = "otro tag" ]]
      then
            if var=$(zenity --entry --title "escribe tag")
            then
                  todo.sh -t add "${album}" $var
                  /home/huan/Scripts/actualizar-todotxt.sh
                  else echo error
            fi
fi
sleep 0.2
xdotool key ctrl+w