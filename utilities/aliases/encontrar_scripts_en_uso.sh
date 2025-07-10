#!/bin/bash

# Script Analyzer - Encuentra scripts en uso y opcionalmente los respalda
# Uso: ./script_analyzer.sh [--backup=/ruta/al/backup]

set -euo pipefail

# Configuración
SCRIPTS_DIR="$HOME/Scripts"
OUTPUT_FILE="$HOME/scripts_en_uso.txt"
BACKUP_DIR=""
TEMP_DIR="/tmp/script_analyzer_$$"

# Archivos y directorios donde buscar referencias
SEARCH_LOCATIONS=(
    "$HOME/.bashrc"
    "$HOME/.bash_aliases"
    "$HOME/.config/fish/config.fish"
    "$HOME/.tmux.conf"
    "$HOME/.local/bin"
    "$HOME/bin"
    #"$HOME/.config"
    "/usr/local/bin"
    "$HOME/.local/share/chezmoi"
    "$HOME/txt" # cron
)

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Función para logging
log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Función para mostrar ayuda
show_help() {
    cat << EOF
Script Analyzer - Encuentra scripts en uso y opcionalmente los respalda

Uso: $0 [--backup=/ruta/al/backup]

Opciones:
    --backup=RUTA    Crea una copia de seguridad de los scripts encontrados en la ruta especificada
    --help           Muestra esta ayuda

Descripción:
    Este script analiza el directorio $SCRIPTS_DIR y busca referencias a los scripts
    en archivos de configuración comunes (zsh_aliases, rc.lua, etc.) y directorios de binarios.

    Genera un archivo de reporte en: $OUTPUT_FILE

    Si se especifica --backup, copia todos los scripts encontrados (y sus dependencias)
    a la ruta de backup especificada.

EOF
}

# Procesar argumentos
for arg in "$@"; do
    case $arg in
        --backup=*)
            BACKUP_DIR="${arg#*=}"
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            error "Argumento desconocido: $arg"
            show_help
            exit 1
            ;;
    esac
done

# Verificar que existe el directorio de scripts
if [[ ! -d "$SCRIPTS_DIR" ]]; then
    error "El directorio de scripts no existe: $SCRIPTS_DIR"
    exit 1
fi

# Crear directorio temporal
mkdir -p "$TEMP_DIR"
trap "rm -rf $TEMP_DIR" EXIT

# Función para extraer rutas de scripts de una línea
extract_script_paths() {
    local line="$1"
    local found_scripts=()

    # Patrones para encontrar rutas de scripts
    local patterns=(
        "$SCRIPTS_DIR/[^'\" ]*\\.py"
        "$SCRIPTS_DIR/[^'\" ]*\\.sh"
        "$HOME/Scripts/[^'\" ]*\\.py"
        "$HOME/Scripts/[^'\" ]*\\.sh"
        "/home/[^/]*/Scripts/[^'\" ]*\\.py"
        "/home/[^/]*/Scripts/[^'\" ]*\\.sh"
    )

    for pattern in "${patterns[@]}"; do
        while IFS= read -r match; do
            [[ -n "$match" ]] && found_scripts+=("$match")
        done < <(echo "$line" | grep -oE "$pattern" || true)
    done

    printf '%s\n' "${found_scripts[@]}"
}

# Función para analizar un script y encontrar scripts hijos
analyze_script_dependencies() {
    local script_path="$1"
    local dependencies_file="$2"

    if [[ ! -f "$script_path" ]]; then
        return
    fi

    log "Analizando dependencias de: $script_path"

    # Buscar llamadas a otros scripts en el contenido
    local patterns=(
        "python3?\s+$SCRIPTS_DIR/[^'\" ]*\\.py"
        "bash\s+$SCRIPTS_DIR/[^'\" ]*\\.sh"
        "sh\s+$SCRIPTS_DIR/[^'\" ]*\\.sh"
        "\./[^'\" ]*\\.py"
        "\./[^'\" ]*\\.sh"
        "$SCRIPTS_DIR/[^'\" ]*\\.py"
        "$SCRIPTS_DIR/[^'\" ]*\\.sh"
    )

    while IFS= read -r line; do
        for pattern in "${patterns[@]}"; do
            while IFS= read -r match; do
                if [[ -n "$match" ]]; then
                    # Limpiar el match (remover comandos como python3, bash, etc.)
                    local clean_path=$(echo "$match" | sed -E 's/^(python3?|bash|sh)\s+//' | sed 's/^.\///')

                    # Si es una ruta relativa, hacerla absoluta
                    if [[ "$clean_path" != /* ]]; then
                        clean_path="$SCRIPTS_DIR/$clean_path"
                    fi

                    if [[ -f "$clean_path" ]]; then
                        echo "$clean_path" >> "$dependencies_file"
                        log "  └── Dependencia encontrada: $clean_path"
                    fi
                fi
            done < <(echo "$line" | grep -oE "$pattern" || true)
        done
    done < "$script_path"
}

# Inicializar archivos de resultados
> "$TEMP_DIR/found_scripts.txt"
> "$TEMP_DIR/all_dependencies.txt"

log "Iniciando análisis de scripts en: $SCRIPTS_DIR"
log "Archivo de reporte: $OUTPUT_FILE"

# Buscar referencias en archivos de configuración
log "Buscando referencias en archivos de configuración..."

for location in "${SEARCH_LOCATIONS[@]}"; do
    if [[ -f "$location" ]]; then
        log "Analizando: $location"
        while IFS= read -r line; do
            extract_script_paths "$line" >> "$TEMP_DIR/found_scripts.txt"
        done < "$location"
    elif [[ -d "$location" ]]; then
        log "Buscando en directorio: $location"
        find "$location" -type f \( -name "*.sh" -o -name "*.py" -o -name "*.lua" -o -name "*.fish" -o -name "*.conf" -o -name ".*rc" -o -name "*aliases*" \) 2>/dev/null | while read -r file; do
            log "  Analizando archivo: $file"
            while IFS= read -r line; do
                extract_script_paths "$line" >> "$TEMP_DIR/found_scripts.txt"
            done < "$file"
        done
    fi
done

# Remover duplicados y ordenar
sort -u "$TEMP_DIR/found_scripts.txt" > "$TEMP_DIR/unique_scripts.txt"

# Analizar dependencias de cada script encontrado
log "Analizando dependencias de scripts encontrados..."
cp "$TEMP_DIR/unique_scripts.txt" "$TEMP_DIR/all_dependencies.txt"

while IFS= read -r script_path; do
    if [[ -f "$script_path" ]]; then
        analyze_script_dependencies "$script_path" "$TEMP_DIR/all_dependencies.txt"
    fi
done < "$TEMP_DIR/unique_scripts.txt"

# Remover duplicados finales
sort -u "$TEMP_DIR/all_dependencies.txt" > "$TEMP_DIR/final_scripts.txt"

# Generar reporte
log "Generando reporte..."

cat > "$OUTPUT_FILE" << EOF
# REPORTE DE SCRIPTS EN USO
# Generado el: $(date)
# Directorio analizado: $SCRIPTS_DIR

## RESUMEN
EOF

total_scripts=$(find "$SCRIPTS_DIR" -type f \( -name "*.py" -o -name "*.sh" \) 2>/dev/null | wc -l)
used_scripts=$(wc -l < "$TEMP_DIR/final_scripts.txt")

cat >> "$OUTPUT_FILE" << EOF
- Total de scripts en $SCRIPTS_DIR: $total_scripts
- Scripts en uso encontrados: $used_scripts
- Scripts potencialmente sin uso: $((total_scripts - used_scripts))

## SCRIPTS EN USO
EOF

while IFS= read -r script_path; do
    if [[ -f "$script_path" ]]; then
        echo "✓ $script_path" >> "$OUTPUT_FILE"
    else
        echo "✗ $script_path (no encontrado)" >> "$OUTPUT_FILE"
    fi
done < "$TEMP_DIR/final_scripts.txt"

cat >> "$OUTPUT_FILE" << EOF

## SCRIPTS POSIBLEMENTE SIN USO
EOF

find "$SCRIPTS_DIR" -type f \( -name "*.py" -o -name "*.sh" \) 2>/dev/null | while read -r script; do
    if ! grep -q "^$script$" "$TEMP_DIR/final_scripts.txt"; then
        echo "? $script" >> "$OUTPUT_FILE"
    fi
done

log "Reporte generado en: $OUTPUT_FILE"

# Crear backup si se solicitó
if [[ -n "$BACKUP_DIR" ]]; then
    log "Creando backup en: $BACKUP_DIR"

    if [[ ! -d "$BACKUP_DIR" ]]; then
        mkdir -p "$BACKUP_DIR"
    fi

    backup_count=0
    while IFS= read -r script_path; do
        if [[ -f "$script_path" ]]; then
            # Crear estructura de directorios manteniendo la estructura interna de Scripts
            # Obtener la ruta relativa desde el directorio Scripts
            relative_path=${script_path#$SCRIPTS_DIR/}
            backup_file_path="$BACKUP_DIR/$relative_path"
            backup_dir_path=$(dirname "$backup_file_path")

            mkdir -p "$backup_dir_path"
            cp "$script_path" "$backup_file_path"
            log "  └── Copiado: $script_path → $backup_file_path"
            ((backup_count++))
        else
            warn "  └── No se pudo copiar (no existe): $script_path"
        fi
    done < "$TEMP_DIR/final_scripts.txt"

    log "Backup completado: $backup_count archivos copiados"

    # Crear un manifiesto del backup
    cat > "$BACKUP_DIR/MANIFEST.txt" << EOF
# BACKUP DE SCRIPTS EN USO
# Creado el: $(date)
# Scripts respaldados: $backup_count

EOF

    while IFS= read -r script_path; do
        echo "$script_path" >> "$BACKUP_DIR/MANIFEST.txt"
    done < "$TEMP_DIR/final_scripts.txt"
fi

# Mostrar estadísticas finales
echo
echo -e "${BLUE}=== ESTADÍSTICAS FINALES ===${NC}"
echo -e "Scripts totales en $SCRIPTS_DIR: ${YELLOW}$total_scripts${NC}"
echo -e "Scripts en uso: ${GREEN}$used_scripts${NC}"
echo -e "Scripts posiblemente sin uso: ${RED}$((total_scripts - used_scripts))${NC}"
echo -e "Reporte guardado en: ${BLUE}$OUTPUT_FILE${NC}"

if [[ -n "$BACKUP_DIR" ]]; then
    echo -e "Backup creado en: ${BLUE}$BACKUP_DIR${NC}"
fi

log "Análisis completado!"
