#!/bin/bash

# Lista de usuarios predefinidos (puedes añadir más)
usuarios=("alberto_gu" "BipolarMuzik" "bloodinmyhand" "EliasJ72" "Frikomid" "GabredMared" "Lonsonxd" "Mister_Dimentio" "Music-is-Crap" "Nubis84" "paqueradejere" "Rocky_stereo" "sdecandelario")

# Si se pasa un argumento, usarlo como usuario
if [ -n "$1" ]; then
    user="$1"
else
    # Mostrar opciones si no se pasa un argumento
    echo "Selecciona un usuario:"
    for i in "${!usuarios[@]}"; do
        echo "$((i+1))) ${usuarios[$i]}"
    done

    # Leer entrada del usuario
    read -p "Número: " opcion

    # Verificar que la opción es válida
    if [[ "$opcion" =~ ^[0-9]+$ ]] && ((opcion >= 1 && opcion <= ${#usuarios[@]})); then
        user="${usuarios[$((opcion-1))]}"
    else
        echo "Opción inválida. Saliendo..."
        exit 1
    fi
fi

echo "Usando el usuario: $user"

# Ejecutar la petición y reproducir la playlist
curl -s "https://www.last.fm/player/station/user/$user/recommended" \
| jq -r '.playlist[].playlinks[].url' \
| shuf \
| mpv --playlist=- --no-video
