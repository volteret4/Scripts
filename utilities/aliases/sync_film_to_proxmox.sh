#!/bin/bash
# Script para copiar archivos listados en un archivo txt a otro servidor usando rsync
# Mejora: Solo elimina del archivo las líneas de archivos copiados exitosamente
# Uso: ./sync_files.sh

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

ARCHIVO_PATHS="$HOME/Scripts/.content/pelis_to_proxmox.txt"
SERVIDOR_DESTINO="proxmox:pelis/"
ARCHIVO_TEMP="${ARCHIVO_PATHS}.tmp"

# Verificar que el archivo existe
if [ ! -f "$ARCHIVO_PATHS" ]; then
    echo -e "${RED}Error: El archivo '$ARCHIVO_PATHS' no existe${NC}"
    exit 1
fi

# Verificar que rsync está instalado
if ! command -v rsync &> /dev/null; then
    echo -e "${RED}Error: rsync no está instalado${NC}"
    echo "Instálalo con: sudo apt-get install rsync (Debian/Ubuntu) o sudo yum install rsync (CentOS/RHEL)"
    exit 1
fi

echo -e "${GREEN}Iniciando sincronización de archivos...${NC}"
echo "Archivo de paths: $ARCHIVO_PATHS"
echo "Servidor destino: $SERVIDOR_DESTINO"
echo "----------------------------------------"

# Contadores
TOTAL=0
EXITOSOS=0
FALLIDOS=0

# Crear archivo temporal vacío
> "$ARCHIVO_TEMP"

# Leer el archivo línea por línea
while IFS= read -r path || [ -n "$path" ]; do
    # Mantener líneas vacías y comentarios en el archivo temporal
    if [ -z "$path" ] || [[ "$path" =~ ^[[:space:]]*# ]]; then
        echo "$path" >> "$ARCHIVO_TEMP"
        continue
    fi

    # Incrementar contador total
    ((TOTAL++))

    # Eliminar espacios al inicio y final
    path_limpio=$(echo "$path" | xargs)

    echo -e "\n${YELLOW}[$TOTAL] Procesando:${NC} $path_limpio"

    # Verificar si el archivo/directorio existe
    if [ ! -e "$path_limpio" ]; then
        echo -e "${RED}   ✗ No existe en el sistema local - se mantiene en la lista${NC}"
        echo "$path" >> "$ARCHIVO_TEMP"
        ((FALLIDOS++))
        continue
    fi

    # Copiar con rsync
    rsync -azP "$path_limpio" "${SERVIDOR_DESTINO}"

    # Verificar resultado de rsync
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}   ✓ Copiado exitosamente - se elimina de la lista${NC}"
        ((EXITOSOS++))
        # NO escribir esta línea en el archivo temporal (se elimina)
    else
        echo -e "${RED}   ✗ Error al copiar - se mantiene en la lista${NC}"
        echo "$path" >> "$ARCHIVO_TEMP"
        ((FALLIDOS++))
    fi
done < "$ARCHIVO_PATHS"

# Reemplazar archivo original con el temporal (solo contiene líneas fallidas)
mv "$ARCHIVO_TEMP" "$ARCHIVO_PATHS"

# Resumen final
echo -e "\n========================================"
echo -e "${GREEN}RESUMEN DE SINCRONIZACIÓN${NC}"
echo "========================================"
echo "Total de archivos procesados: $TOTAL"
echo -e "${GREEN}Exitosos: $EXITOSOS${NC}"
echo -e "${RED}Fallidos: $FALLIDOS${NC}"
echo "----------------------------------------"
if [ $FALLIDOS -gt 0 ]; then
    echo -e "${YELLOW}Se mantienen $FALLIDOS rutas en el archivo para reintentar${NC}"
else
    echo -e "${BLUE}El archivo de rutas está vacío - todos los archivos copiados${NC}"
fi
echo "========================================"

# Salir con código de error si hubo fallos
if [ $FALLIDOS -gt 0 ]; then
    exit 1
fi

exit 0
