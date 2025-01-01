#!/bin/bash

# Extraer las familias de fuentes únicas desde /usr/share/fonts/TTF
fonts=($(fc-list | cut -d':' -f2 | cut -d',' -f1 | sort -u))

# Si la lista de fuentes está vacía, termina el script
if [ ${#fonts[@]} -eq 0 ]; then
    echo "No se encontraron fuentes."
    exit 1
fi

# Obtén la fuente actual desde kitty.conf
current_font=$(grep -Po '(?<=^font_family ).*' ~/.config/kitty/kitty.conf)

# Encuentra la siguiente fuente en la lista
next_font=${fonts[0]}  # Por defecto, selecciona la primera fuente
for i in "${!fonts[@]}"; do
    if [[ "${fonts[$i]}" == "$current_font" ]]; then
        next_font=${fonts[$(( (i + 1) % ${#fonts[@]} ))]}
        break
    fi
done

# Reemplaza la fuente en kitty.conf
sed -i "s/^font_family .*/font_family $next_font/" ~/.config/kitty/kitty.conf

# Recarga la configuración de Kitty para aplicar el cambio de fuente
kitty @ set-font --name "$next_font"

# Mensaje de confirmación
echo "Fuente cambiada a: $next_font"
