#!/usr/bin/env bash
#
# Script Name: crear_tarea_TODO.sh 
# Description:  Crear tarea normal
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:
#	Dependencies:
#		copyq
#		vdirsyncer
#		todo
#		yad
#


# script_name=$(basename "$0")
# bash "${HOME}/Scripts/utilities/recuento_scripts.sh ${script_name}"
contenido=$(copyq clipboard)

if echo "$url" | grep -E -q "(youtube\.com|bandcamp\.com|soundcloud\.com)"
	then 
		calendario="musica"
		todofile="/home/huan/Documentos/todotxt/todo.txt"
	else
		calendario="tareas"
		titulo=$(zenity --entry --text 'Tarea')
fi


#~ if [ -z "${titulo}" ]
    #~ then
        #~ exit 1
    #~ else
        #~ vdirsyncer sync &
#~ fi
vdirsyncer sync

#hoy=$(date +%d/%m/%Y)
#nextyear=$(date -d "+1 year" +%d/%m/%Y)

discos="d1573ec1-e837-6918-1dfe-bc0b6c04681d"		# CHANGE!!
tareas="7c44de6e-69ac-8496-f46d-d6753c9eab1f"		# CHANGE!!
musica="e2e4e951-3599-8f21-de6c-105ec980b1ec"		# CHANGE!!

fecha=$(date +%Y-%m-%d)
# echo ${hoy}
# echo ${nextyear}
# echo ${titulo}
# echo ${contenido}


#	continuar si no ha habido errores en la sincronizacion
ans=$?
if [ $ans -eq 0 ]
	then
		if [[ -z "$titulo" ]]
			then
				todo new -l "${calendario}" -s "today" -d "one year" -r "${contenido}"
				echo "${fecha} ${titulo}" >> "${todofile}"
				notify-send "creado nuevo evento \n $contenido"
				echo "enviado portapapeles"
			else
				todo new -l "${calendario}" -s "today" -d "one year" -r "${titulo}"
				echo "${fecha} ${contenido}" >> "${todofile}"
				echo "enviado titulo"
		fi    
	    
	else
		yad --text="Error al añadir tarea a radicale" --markup --fixed
		notify-send -u critical "Error al añadir tarea a radicale"
fi


sleep 10

vdirsyncer sync