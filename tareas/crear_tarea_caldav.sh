#!/usr/bin/env bash
#
# Script Name: crear_tarea_caldav.sh 
# Description: Añadir tarea a calenario Musica
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#	Dependencies:
#		vdirsyncer
#		copyq
#		todo
#


# Control errors script
source "$HOME/Scripts/utilities/funciones.sh"		# CHANGE!!!
arg="$@"
# Recuento de lanzamiento de Scripts
# script_name=$(basename "$0")
# bash "${HOME}/Scripts/utilities/recuento_scripts.sh ${script_name}"


# Variables con rutas a calendarios para vdirsyncer
discos="d1573ec1-e837-6918-1dfe-bc0b6c04681d"		# CHANGE!!!
tareas="7c44de6e-69ac-8496-f46d-d6753c9eab1f"		# CHANGE!!!
musica="e2e4e951-3599-8f21-de6c-105ec980b1ec"		# CHANGE!!!

tododir="/mnt/Datos/FTP/Wiki/todotxt/"				# CHANGE!!!

# Pasar portapapeles al script
contenido=$(copyq clipboard)


# Si el portapapeles contiene enlace a yt,bc o sncd añadir tags y elegir calendario "discos" o "tareas"
if echo "$url" | grep -E -q "(youtu\.be|youtube\.com|bandcamp\.com|soundcloud\.com)"
	then 
		calendario="discos"
		echo "calendario: discos"
		todofile="${tododir}/albums/a_todo.txt"
		titulo=$(zenity --entry --entry-text "+" --text 'Tags @ | Categorias +')
		album="$(yt-dlp --get-title ${contenido})"
	elif [[ -n ${arg} ]]; then
		calendario="tareas"
		todofile="${tododir}/todo/t_todo.txt"
		titulo="${arg}"
	else
		calendario="tareas"
		echo "calendario: tareas"
		todofile="${tododir}/todo/t_todo.txt"
		titulo=$(zenity --entry --text 'Tarea')
fi


# Crear categorias desde los tags introducidos en $titulo para caldav

	# Extraer todas las @word en un array
readarray -t categorias <<< $(echo "$titulo" | grep -o '@[^ ]*')

	# Crear un conjunto para almacenar categorías únicas
declare -A categorias_unicas

# Iterar sobre el array, eliminar el símbolo "@" y agregar cada @word al conjunto
for categoria in "${categorias[@]}"; do
    categoria_sin_arroba="${categoria/@/}"  # Eliminar el símbolo "@"
    categorias_unicas=($(echo "${categoria_sin_arroba}" | tr ' ' '\n' | sort -u | tr '\n' ' '))
done

# Imprimir cada @word en una variable separada
# for i in "${!categorias[@]}"; do
#     declare "categoria$((i+1))=${categorias[$i]}"
# done

# Establecer fechas
fecha_hoy=$(date +%Y/%m/%d)
nextyear=$(date -d "+1 year" +%Y/%m/%d)


# Sincronizar y comprobar errores
vdirsyncer sync
ans="$?"
echo "fin de sincronizacion"
echo "${ans}"


# Adaptar portapapeles eliminando carácteres especiales
contenido=$(printf "%s" "${contenido}" | sed 's/\\/\\\\/g; s/"/\\"/g; s/\([$!`]\)/\\\1/g')


#	continuar si no ha habido errores en la sincronizacion
if [ ${ans} -eq 0 ]
	then
		if [[ ${calendario} = tareas ]]
			then
				# enviar="${titulo} ${contenido}"
				echo "${fecha_hoy} ${titulo} due:${nextyear}" >> "${todofile}"
				# Iterar sobre el array y eliminar cada @word del titulo
				for categoria in "${categorias[@]}"; do
				    titulo=${titulo//$categoria/}
				done
				# todo new -l "$musica" -s "today" -d "one year" -c "$categoria" -r "$titulo" &

				# Llamar a todo new con las categorías
				todo_command="todo new -l \"$tareas\" -s \"today\" -d \"one year\" -r \"$titulo\""
				for categoria in "${!categorias_unicas[@]}"; do
			    	todo_command+=" -c \"$categoria\""
				done
				echo "titulo: $titulo"
				echo "categoria: $categoria"
				echo "todocmd: $todo_command"
				eval "$todo_command" &
				notify-send "enviada tarea: ${titulo} ${categoria}"
				echo "enviad tarea: ${titulo} ${categoria}"
			elif [[ $calendario = discos ]]
				then
					echo D1
					notify-send "enviado disco: ${album} ${contenido} ${titulo}"
					echo "${fecha_hoy} ${album} ${contenido} ${titulo}" >> "${todofile}"
					echo "enviado disco: ${album} ${contenido} ${titulo}"
	    	else
				echo "Error"
				notify-send -u critical "Error"
				yad --text="Error al añadir tarea a radicale" --markup --fixed
		fi
fi

# Dormir para asegurar que se crean todos los archivos
mostrar_barra_progreso 10 &
pid_mostrar_barra=$!
echo "${pid_mostrar_barra}"
wait "${pid_mostrar_barra}"
echo "fin"
#sleep 50

# Sincronizar con vdirsyncer
vdirsyncer sync
