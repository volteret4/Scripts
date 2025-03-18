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
source "$HOME/Scripts/utilities/aliases/barra_progreso.sh"		# CHANGE!!!
arg="$@"
# Recuento de lanzamiento de Scripts
# script_name=$(basename "$0")
# bash "${HOME}/Scripts/utilities/recuento_scripts.sh ${script_name}"


# Variables con rutas a calendarios para vdirsyncer
discos="d1573ec1-e837-6918-1dfe-bc0b6c04681d"		# CHANGE!!!
tareas="7c44de6e-69ac-8496-f46d-d6753c9eab1f"		# CHANGE!!!
musica="e2e4e951-3599-8f21-de6c-105ec980b1ec"		# CHANGE!!!

tododir="/mnt/windows/FTP/Wiki/Obsidian/Important/todotxt/todo"				# CHANGE!!!
tododir_root="/mnt/windows/FTP/Wiki/Obsidian/Important/todotxt/"				
# Pasar portapapeles al script
contenido=$(copyq clipboard)

titulo="$(yad --entry --entry-text "+" --text 'Tags @ | Categorias +')"
titulo="$(echo "$titulo" | tr -d '\n' | tr -d '\r' )"

# Si el portapapeles contiene enlace a yt,bc o sncd añadir tags y elegir calendario "discos" o "tareas"
if echo "$titulo" | grep -E -q "(youtu\.be|youtube\.com|bandcamp\.com|soundcloud\.com)"
	then 
		calendario="discos"
		echo "calendario: $calendario"
		todofile="${tododir_root}/albums/a_todo.txt"
		album="$(yt-dlp --get-title "${contenido}")"

	elif [[ -n ${arg} ]]; then
		calendario="tareas"
		todofile="${tododir_root}/todo/t_todo.todotxt"
		titulo="${arg}"

	else
		calendario="tareas"
		echo "calendario: $calendario"
		todofile="${tododir_root}/todo/t_todo.todotxt"
fi


# Crear categorias desde los tags introducidos en $titulo para caldav

	# Extraer todas las @word en un array
readarray -t categorias <<< "$(echo "$titulo" | grep -o '@[^ ]*')"

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
				if [[ -z "$categorias_unicas" ]]; then
					echo "sin tags"
				else
					for categoria in "${categorias[@]}"; do
						txt_cmd+=" \"$categoria\""
					done
				fi
				txt_cmd="$txt_cmd due:$nextyear"
				echo "$txt_cmd" >> "$todofile"
				echo "inicio perl"
				# Exportar a json para luego importar a taskwarrior
				perl "${HOME}"º ${tododir}/t_todo.todotxt > ${tododir}/tw_from_t_todo.json
				echo "fin perl"
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

# Función para mostrar archivos y añadir línea TODO para Obsidian tasks
function add_todo_to_obsidian() {
    local files=(
        # Lista hardcodeada de paths a archivos markdown
        "/mnt/windows/FTP/wiki/Obsidian/Spaces/Blogs/snipets y scripts/music-fuzzy/Aplicación música pollo.md"
        "/mnt/windows/FTP/wiki/Obsidian/Spaces/Blogs/snipets y scripts/music-fuzzy/creacion base de datos/Creación de la base de datos.md"
        "/mnt/windows/FTP/wiki/Obsidian/Spaces/Blogs/Tumtumpa/Recopilando Música.md"
        # Añade más rutas según sea necesario
    )
    
    local prefix=""
    local index=1
    local selection=""
    
    while true; do
        # Mostrar lista de archivos con prefijos solo con basename
        echo "Selecciona un archivo para añadir TODO:"
        for file in "${files[@]}"; do
            if (( index <= 9 )); then
                prefix="$index"
            else
                # Convertir a letras (a-z) después de los números 1-9
                prefix=$(printf "\\$(printf '%03o' $((96 + index - 9)))")
            fi
            
            echo "$prefix) $(basename "$file")"
            (( index++ ))
            
            # Limitar a 9 números + 26 letras
            if (( index > 35 )); then
                break
            fi
        done
        
        # Añadir opción para agregar nuevo archivo
        echo "+) Añadir nuevo archivo"
        echo "q) Salir"
        
        # Capturar la selección con read -n 1
        echo "Presiona la tecla correspondiente para seleccionar un archivo:"
        read -n 1 selection
        echo ""
        
        # Salir si se presiona 'q'
        if [[ "$selection" == "q" ]]; then
            return 0
        fi
        
        # Opción para añadir un nuevo archivo
        if [[ "$selection" == "+" ]]; then
            # Usar yad para mostrar un diálogo explorador
            new_file=$(yad --file --title="Selecciona un archivo markdown" --filename="/mnt/windows/FTP/Wiki/Obsidian/" --file-filter="*.md")
            
            # Verificar si se seleccionó un archivo
            if [[ -n "$new_file" ]]; then
                # Añadir el nuevo archivo a la lista hardcodeada
                # Crear un archivo temporal para guardar el script actualizado
                tmp_file=$(mktemp)
                
                # Obtener el contenido del script actual
                script_content=$(cat "$0")
                
                # Determinar la posición donde insertar el nuevo archivo en la lista
                insert_position=$(grep -n "# Lista hardcodeada de paths a archivos markdown" "$0" | cut -d: -f1)
                insert_position=$((insert_position + 1))
                
                # Insertar el nuevo archivo en la lista
                {
                    head -n "$insert_position" "$0"
                    echo "        \"$new_file\""
                    tail -n +$((insert_position + 1)) "$0"
                } > "$tmp_file"
                
                # Reemplazar el script actual con el nuevo contenido
                cat "$tmp_file" > "$0"
                rm "$tmp_file"
                
                # Añadir a la lista actual para esta ejecución
                files+=("$new_file")
                echo "Archivo añadido: $(basename "$new_file")"
            fi
            
            # Reiniciar el índice para mostrar la lista actualizada
            index=1
            continue
        fi
        
        # Determinar el índice seleccionado
        index_selected=0
        if [[ "$selection" =~ ^[1-9]$ ]]; then
            index_selected=$(( selection - 1 ))
        elif [[ "$selection" =~ ^[a-z]$ ]]; then
            # Convertir letra a índice (a=10, b=11, etc.)
            ascii_val=$(printf "%d" "'$selection")
            index_selected=$(( ascii_val - 97 + 9 ))
        else
            echo "Selección inválida."
            read -n 1 -s -r -p "Presiona cualquier tecla para continuar..."
            index=1
            continue
        fi
        
        # Verificar si el índice es válido
        if (( index_selected >= ${#files[@]} )); then
            echo "Índice fuera de rango."
            read -n 1 -s -r -p "Presiona cualquier tecla para continuar..."
            index=1
            continue
        fi
        
        # Usar la variable $title existente en lugar de solicitar un nuevo título
        # Añadir la línea TODO al archivo seleccionado para Obsidian tasks
		echo " " >> "${files[$index_selected]}"
		echo " " >> "${files[$index_selected]}"
        echo "- [ ] TODO: $titulo" >> "${files[$index_selected]}"
        echo "Añadido '- [ ] TODO: $titulo' a $(basename "${files[$index_selected]}")"
        
        # Preguntar si quiere añadir otro TODO
        echo "¿Deseas añadir otro TODO? (s/n)"
        read -n 1 resp
        echo ""
        
        if [[ "$resp" != "s" && "$resp" != "S" ]]; then
            break
        fi
        
        # Reiniciar el índice para mostrar la lista desde el principio
        index=1
    done
}

# Llamar a la función al final del script
add_todo_to_obsidian