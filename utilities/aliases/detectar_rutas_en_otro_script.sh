#!/bin/bash

if [ $# -ne 1 ]; then
    echo "Uso: $0 archivo_a_analizar"
    exit 1
fi

echo "Analizando rutas en $1..."
echo "------------------------"

# Buscar rutas absolutas (comienzan con /)
echo "Rutas absolutas:"
grep -o '/[[:alnum:]_/.-]\+' "$1" | sort -u

# Buscar rutas relativas (comienzan con ./ o ../)
echo -e "\nRutas relativas:"
grep -o '\.\{1,2\}/[[:alnum:]_/.-]\+' "$1" | sort -u

# Buscar nombres de archivo sin path completo (archivos locales)
echo -e "\nPosibles archivos locales:"
grep -o '[[:alnum:]_-]\+\.[[:alnum:]]\+' "$1" | sort -u