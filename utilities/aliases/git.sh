#!/bin/bash

# Pedir al usuario el mensaje del commit
echo "Introduce el mensaje del commit:"
read commit_message

# Añadir todos los archivos al área de preparación
git add .

# Realizar el commit con el mensaje proporcionado por el usuario
git commit -m "$commit_message"

# Subir los cambios al repositorio remoto
git push
