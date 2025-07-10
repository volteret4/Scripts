#!/usr/bin/env bash
#
# Script Name: funciones.sh 
# Description: Usar mostrar_barra_progreso en otros scripts
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:    Work in Progress 
#


function mostrar_barra_progreso() {
    local duracion=$1
    local intervalo=1
    local pasos=$((duracion / intervalo))

    for ((i = 0; i <= pasos; i++)); do
        porcentaje=$((i * 100 / pasos))
        barra="$(printf '#%.0s' $(seq 1 $((i * 50 / pasos))))"
        printf "[%-50s] %d%%\r" "$barra" "$porcentaje"
        sleep "$intervalo"
    done

    printf "\n"
}