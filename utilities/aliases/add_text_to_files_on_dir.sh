#!/usr/bin/env bash
#
# Script Name: 
# Description: 
# Author: volteret4
# Repository: 
# License: 
# TODO: 
# Notes:
#

# Definir la información del encabezado
header_bash="#!/usr/bin/env bash
#
# Script Name: add_text_to_files_on_dir.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#
#


"
header_bash_correcto="#!/usr/bin/env bash
#
# Script Name:"

header_python="#!/usr/bin/env python
#
# Script Name: add_text_to_files_on_dir.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#
#


"
header_python_correcto="#!/usr/bin/env python
#
# Script Name:"

# Directorio del proyecto
PROJECT_DIR="$1"

# Recorrer todos los archivos en el directorio del proyecto
find "$PROJECT_DIR" -type f -exec bash -c '
    for file do
        # Verificar si el archivo es un archivo regular y tiene permisos de escritura
        if [ -f "$file" ] && [ -w "$file" ]; then
            # Obtener la extensión del archivo
            extension="${file##*.}"

            # Leer la primera línea del archivo
            first_line=$(head -n 3 "$file")

            # Verificar si la primera línea es un shebang y es específicamente para bash
            if [[ $first_line =~ "$header_bash_correcto" ]]; then
                echo "El archivo $file ya tiene un shebang específico para bash. No se realizarán cambios."
                continue
            elif [[ $first_line =~ "$header_python_correcto" ]]; then
                echo "El archivo $file ya tiene un shebang específico para Python. No se realizarán cambios."
                continue
            else
                # Agregar el encabezado correspondiente según la extensión del archivo
                if [ "$extension" = "sh" ]; then
                    header="$header_bash"
                elif [ "$extension" = "py" ]; then
                    header="$header_python"
                else
                    echo "Extensión de archivo no compatible para agregar un shebang."
                    continue
                fi

                # Agregar el encabezado al principio del archivo
                echo "$header" >"$file.tmp"  # Crear un archivo temporal con el encabezado
                cat "$file" >>"$file.tmp"  # Agregar el contenido original del archivo después del encabezado
                mv "$file.tmp" "$file"  # Sobrescribir el archivo original con el contenido actualizado
            fi
        fi
    done
' bash {} +