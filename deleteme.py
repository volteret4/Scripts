#!/bin/bash

# Verificar si se ha proporcionado una carpeta como argumento
if [ -z "$1" ]; then
  echo "Debe proporcionar una carpeta como argumento."
  exit 1
fi

# Asignar la carpeta proporcionada como argumento a una variable
CARPETA="$1"

# Verificar si la carpeta existe
if [ ! -d "$CARPETA" ]; then
  echo "La carpeta '$CARPETA' no existe."
  exit 1
fi

# Buscar todos los archivos en la carpeta y sus subdirectorios
find "$CARPETA" -name "*.md" -type f -exec sh -c '
    for file do
        #destino="$(echo ${ARCHIVO}| sed 's/ /\//g')"
        # Usar sed para reemplazar todas las líneas que comienzan con "tags" por "tags: linux"
        sed -i 's/^tags/tags: linux/' "${ARCHIVO}"
    done
'sh {} +

echo "Se han actualizado todas las líneas que comienzan con 'tags' en los archivos de '$CARPETA'."