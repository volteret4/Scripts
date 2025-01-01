#!/usr/bin/env bash
#
# Script Name: crear_tarea_caldav.sh 
# Description: Añadir tarea a calenario Tareas, a todotxc de obsidian y todofi.sh y a taskwarrior
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#	Dependencies:
#		vdirsyncer
#		copyq
#		todo
#		taskwarrior
#		todofi.sh
#		servidor caldav
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

tododir="/mnt/windows/FTP/Wiki/Obsidian/Important/todotxt"				# CHANGE!!!

# Pasar portapapeles al script
contenido=$(copyq clipboard)


# Si el portapapeles contiene enlace a yt,bc o sncd añadir tags y elegir calendario "discos" o "tareas"
if echo "$url" | grep -E -q "(youtu\.be|youtube\.com|bandcamp\.com|soundcloud\.com)"
	then 
		calendario="discos"
		echo "calendario: discos"
		todofile="${tododir}/albums/a_todo.txt"
		titulo="$(yad --entry --entry-text "+" --text 'Tags @ | Categorias +')"
		titulo="$(echo $titulo | tr -d '\n' | tr -d '\r' )"
		album="$(yt-dlp --get-title ${contenido})"
	elif [[ -n ${arg} ]]; then
		calendario="tareas"
		todofile="${tododir}/todo/t_todo.todotxt"
		titulo="${arg}"
		titulo="$(echo $titulo | tr -d '\n' | tr -d '\r' )"
	else
		calendario="tareas"
		echo "calendario: tareas"
		todofile="${tododir}/todo/t_todo.todotxt"
		titulo="$(yad --entry --text 'Tarea')"
		titulo="$(echo $titulo | tr -d '\n' | tr -d '\r' )"
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
fecha_hoy=$(date +%Y-%m-%d)
nextyear=$(date -d "+1 year" +%Y-%m-%d)


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
				# enviar al todotxt. (rofi y obsidian dependen de el)
				txt_cmd="${fecha_hoy} ${titulo}"
				# Iterar sobre el array y eliminar cada @categoria del titulo
				if [[ -z $categorias_unicas ]]; then
					echo "sin tags"
				else
					for categoria in "${categorias[@]}"; do
						txt_cmd+=" \"$categoria\""
					done
				fi
				txt_cmd="$txt_cmd due:$nextyear"
				echo "$txt_cmd" >> "$todofile"
				
				# Exportar a json para luego importar a taskwarrior
				perl ${HOME}/Scripts/tareas/json_a_todotxt.pl ${tododir}/t_todo.todotxt > ${tododir}/tw_from_t_todo.json
    			cat ${tododir}/tw_from_t_todo.json | task import
    			echo "importado en taskwarrior"


				# Llamar a todo new con las categorías
				todo_command="todo --config $HOME/.config/todoman/config_tareas.py new -l \"$tareas\" -s \"today\" -d \"one year\" -r \"$titulo\""
				
				# añadir categorias si existen
				if [[ -z $categorias_unicas ]]; then
					echo "sin tags"
				else
					for categoria in "${!categorias_unicas[@]}"; do
						todo_command+=" -c \"$categoria\""
					done
				fi
				
				# debug time
				echo "titulo: $titulo"
				echo "categoria: $categoria"
				echo "todocmd: $todo_command"
				eval "$todo_command" &
				notify-send "enviada tarea: ${titulo} ${categoria}"
				echo "enviad tarea: ${titulo} ${categoria}"
				
			elif [[ $calendario = discos ]]
				then
					echo DISCOS
					todo_command="todo new -l \"discos\" -s \"today\" -d \"one year\" -r \"$titulo\""
					eval "$todo_command" &
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
