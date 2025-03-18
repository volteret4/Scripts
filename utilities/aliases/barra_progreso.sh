function mostrar_barra_progreso() {
    local duracion=$1
    local incremento=$(echo "scale=2; 100/$duracion" | bc)
    local progreso=0
    
    for ((i=0; i<$duracion; i++)); do
        progreso=$(echo "scale=0; $progreso + $incremento" | bc)
        echo "$progreso"
        sleep 1
    done | yad --progress --auto-close --text="Procesando..." --percentage=0
}