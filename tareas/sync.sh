# perl ${HOME}/Scripts/tareas/json_a_todotxt.pl ${ruta}/t_todo.todotxt > ${ruta}/tw_from_t_todo.json
# cat ${ruta}/tw_from_t_todo.json | task import
# echo "importado en taskwarrior"


raya="$(tail --lines 1 /mnt/Datos/FTP/Wiki/Obsidian/Important/todotxt/todo/t_done.txt)"
echo $raya
titulito="$(echo $raya | awk -F ' ' '{for (i=4; $i !~ /@|due/; i++) printf "%s ", $i}')"
echo $titulito
codigo="$(todo list | grep $titulito | awk '{print $3}')"
echo $codigo
todo done $codigo
vdirsyncer sync