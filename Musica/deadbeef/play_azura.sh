#!/bin/bash



source "/home/huan/Scripts/Musica/deadbeef/.env"

sleep 2


# URL del archivo CSS
URL="$(bash ${HOME}/Scripts/snippets/if_firefox_active.sh)"
CSS_URL="${URL}/styles.css"

echo "$CSS_URL"

# Credenciales
AZURA_USR="$AZURA_USR"
AZURA_PWD="$AZURA_PWD"
echo $AZURA_USR
# Descargar el contenido del archivo CSS y almacenarlo en una variable usando autenticación básica
CSS_CONTENT=$(curl -s --basic -u "$AZURA_USR:$AZURA_PWD" $CSS_URL)
touch styles.css
echo $CSS_CONTENT > styles.css
# Verificar si la descarga fue exitosa
if [ $? -eq 0 ]; then
    echo "Archivo CSS descargado con éxito."
else
    echo "Error al descargar el archivo CSS."
    exit 1
fi

# Selector CSS que deseas extraer
CSS_SELECTOR=".breadcrumb-item:nth-child(3) > a"

# Escapar caracteres especiales en el selector CSS para usar con grep
ESCAPED_SELECTOR=$(echo "$CSS_SELECTOR" | sed 's/[]\/$*.^|[]/\\&/g')

# Extraer el bloque de estilo correspondiente al selector CSS
CSS_BLOCK=$(echo "$CSS_CONTENT" | sed -n "/$ESCAPED_SELECTOR/,/}/p")

# Verificar si el selector fue encontrado
if [ -n "$CSS_BLOCK" ]; then
    echo "Selector CSS encontrado:"
    echo "$CSS_BLOCK"
else
    echo "Selector CSS no encontrado."
fi