#!/usr/bin/env bash
#
# Script Name: actualizar-todotxt.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:
#
#



echo "apagando" >> /home/huan/uptime
todo.sh deduplicate
rsync -ac /home/huan/.config/TODO/todo.txt /home/huan/Documentos/todotxt/todo.txt
