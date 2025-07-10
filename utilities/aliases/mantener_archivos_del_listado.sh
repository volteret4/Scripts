#!/bin/bash

# Script para mantener solo los archivos listados en listado.txt
# IMPORTANTE: Hacer backup antes de ejecutar

LISTADO_FILE="$HOME/lista_interno.txt"
LOG_FILE="$HOME/Scripts/.content/logs/archivos_eliminados.log"
DRY_RUN=false # Cambiar a false para ejecutar realmente

# Verificar que existe el archivo de listado
if [ ! -f "$LISTADO_FILE" ]; then
    echo "Error: No se encuentra el archivo $LISTADO_FILE"
    exit 1
fi

# Crear directorio temporal para backup si no existe
mkdir -p backup_logs

echo "=== SCRIPT PARA MANTENER ARCHIVOS DEL LISTADO ==="
echo "Archivo de listado: $LISTADO_FILE"
echo "Modo de prueba: $DRY_RUN"
echo ""

# Leer el directorio base del primer archivo para determinar el alcance
BASE_DIR=$(head -n1 "$LISTADO_FILE" | sed 's|/[^/]*$||' | sed 's|/Disc.*||' | sed 's|/CD.*||')
echo "Directorio base detectado: $BASE_DIR"

# Función para verificar si un archivo está en el listado
archivo_en_listado() {
    local archivo="$1"
    grep -Fxq "$archivo" "$LISTADO_FILE"
}

# Encontrar todos los archivos en el directorio base
echo "Buscando archivos en: $BASE_DIR"
echo ""

# Contadores
total_encontrados=0
total_a_eliminar=0
total_conservados=0

# Crear lista temporal de archivos encontrados
TEMP_FOUND="/tmp/archivos_encontrados.txt"
find "$BASE_DIR" -type f > "$TEMP_FOUND"

echo "Analizando archivos..."

while IFS= read -r archivo_actual; do
    ((total_encontrados++))
    
    if archivo_en_listado "$archivo_actual"; then
        echo "✓ CONSERVAR: $archivo_actual"
        ((total_conservados++))
    else
        echo "✗ ELIMINAR: $archivo_actual"
        ((total_a_eliminar++))
        
        # Si no es modo de prueba, eliminar el archivo
        if [ "$DRY_RUN" = false ]; then
            rm -f "$archivo_actual"
            echo "$archivo_actual" >> "$LOG_FILE"
        fi
    fi
done < "$TEMP_FOUND"

# Limpiar archivo temporal
rm -f "$TEMP_FOUND"

echo ""
echo "=== RESUMEN ==="
echo "Total archivos encontrados: $total_encontrados"
echo "Archivos a conservar: $total_conservados"
echo "Archivos a eliminar: $total_a_eliminar"

if [ "$DRY_RUN" = true ]; then
    echo ""
    echo "*** MODO DE PRUEBA ACTIVADO ***"
    echo "No se eliminó ningún archivo."
    echo "Para ejecutar realmente, cambia DRY_RUN=false en el script"
else
    echo ""
    echo "Archivos eliminados registrados en: $LOG_FILE"
fi

echo ""
echo "Script completado."