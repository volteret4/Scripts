#!/usr/bin/env bash
#
# Script Name: tw_cald_sync.sh 
# Description:  Script para sincronizar tareas entre Caldav, Todo, y Taskwarrior
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:  Requieres caldav server (radicale?) and this git
#
#


notify-send "prepara clave gpg"
py_env="${HOME}/Documentos/python_envs/taskwarrior-caldav/bin/activate"
arg1="$1"


# manda a dormir usando o no el argumento
source ${py_env}
if [[ -z $arg1 ]]
  then
    echo "durmiendo 20"
    sleep 20
  else
    echo "durmiendo ${arg1}"
    sleep "${arg1}"
fi


# sincronizacion de Taskwarrior y Caldav
tw_caldav_sync --caldav-url "http://192.168.1.199:5232" --caldav-user "pollo" --caldav-passwd-pass-path "radicale.gpg"  --caldav-calendar "Tareas" --all
#tw_caldav_sync --combination Tareas____None__.yaml
echo "durmiendo 3"
sleep 3


#tempfile="/mnt/A26A-AAE7/FTP/Wiki/todotxt/todo/temp"
jsonfile="/mnt/A26A-AAE7/FTP/Wiki/todotxt/todo/tw_json.txt"
todofile="/mnt/A26A-AAE7/FTP/Wiki/todotxt/todo/t_todo.txt"
donefile="/mnt/A26A-AAE7/FTP/Wiki/todotxt/todo/t_done.txt"
script="${HOME}/Scripts/tareas/tw_2_todo/convert.py"
compras="/mnt/A26A-AAE7/FTP/Wiki/Compras/t_compras.md"


# Exportando de  Taskwarrior a TODO.txt
task export > ${jsonfile}
python3 ${script} -i ${jsonfile} -o ${todofile} -a ${donefile}


# Extraer compras y añadirlas a la lista
grep -E '[@+]compras' ${todofile} > ${compras}


# Sincronizar con vdirsyncer
vdirsyncer sync
