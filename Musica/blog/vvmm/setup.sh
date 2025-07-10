#!/usr/bin/env bash
#
# Script Name: setup.sh
# Description: Script de instalación y configuración para VVMM Post Creator
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:

set -euo pipefail

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
RESET='\033[0m'

# Variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

log_info() {
    echo -e "${GREEN}[INFO]${RESET} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${RESET} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${RESET} $1"
}

log_debug() {
    echo -e "${BLUE}[DEBUG]${RESET} $1"
}

show_banner() {
    echo -e "${CYAN}"
    cat << 'EOF'
╔═══════════════════════════════════════════════════════════════╗
║                  VVMM POST CREATOR SETUP                     ║
║              Configuración e Instalación                     ║
╚═══════════════════════════════════════════════════════════════╝
EOF
    echo -e "${RESET}"
}

check_requirements() {
    log_info "Verificando requisitos del sistema..."
    
    local required_commands=(
        "python3"
        "pip3"
        "hugo"
        "git"
        "yad"
        "notify-send"
        "qutebrowser"
        "curl"
        "jq"
    )
    
    local missing_commands=()
    
    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            missing_commands+=("$cmd")
        fi
    done
    
    if [[ ${#missing_commands[@]} -gt 0 ]]; then
        log_error "Comandos faltantes: ${missing_commands[*]}"
        log_info "Instala los comandos faltantes y ejecuta el setup nuevamente"
        
        # Sugerir comandos de instalación según la distribución
        if command -v apt &> /dev/null; then
            log_info "Para Ubuntu/Debian, prueba:"
            echo "sudo apt update && sudo apt install python3 python3-pip hugo git yad libnotify-bin qutebrowser curl jq"
        elif command -v dnf &> /dev/null; then
            log_info "Para Fedora, prueba:"
            echo "sudo dnf install python3 python3-pip hugo git yad libnotify curl jq qutebrowser"
        elif command -v pacman &> /dev/null; then
            log_info "Para Arch Linux, prueba:"
            echo "sudo pacman -S python python-pip hugo git yad libnotify curl jq qutebrowser"
        fi
        
        return 1
    fi
    
    log_info "Todos los comandos requeridos están disponibles ✓"
    return 0
}

create_directory_structure() {
    log_info "Creando estructura de directorios..."
    
    local directories=(
        "$PROJECT_ROOT/.content"
        "$PROJECT_ROOT/.content/logs"
        "$PROJECT_ROOT/.content/cache"
        "$PROJECT_ROOT/modules"
        "/mnt/NFS/blogs/vvmm"
    )
    
    for dir in "${directories[@]}"; do
        if [[ ! -d "$dir" ]]; then
            log_debug "Creando directorio: $dir"
            mkdir -p "$dir" 2>/dev/null || {
                if [[ "$dir" == "/mnt/NFS/blogs/vvmm" ]]; then
                    log_warn "No se pudo crear $dir - verifica que el punto de montaje NFS existe"
                    log_info "Puedes cambiar la ruta del blog en el archivo .env"
                else
                    log_error "No se pudo crear el directorio: $dir"
                    return 1
                fi
            }
        else
            log_debug "Directorio ya existe: $dir"
        fi
    done
    
    log_info "Estructura de directorios creada ✓"
}

setup_python_environment() {
    log_info "Configurando entorno Python..."
    
    # Crear entorno virtual si no existe
    local venv_path="$PROJECT_ROOT/venv"
    if [[ ! -d "$venv_path" ]]; then
        log_debug "Creando entorno virtual en $venv_path"
        python3 -m venv "$venv_path"
    fi
    
    # Activar entorno virtual
    source "$venv_path/bin/activate"
    
    # Actualizar pip
    pip install --upgrade pip
    
    # Instalar dependencias Python
    log_debug "Instalando dependencias Python..."
    pip install \
        spotipy \
        python-dotenv \
        requests \
        beautifulsoup4 \
        lxml \
        google-api-python-client \
        wikipediaapi \
        papaparse
    
    log_info "Entorno Python configurado ✓"
    
    # Actualizar .env con la ruta del entorno virtual
    if [[ -f "$PROJECT_ROOT/.env" ]]; then
        sed -i "s|PYTHON_VENV_PATH=.*|PYTHON_VENV_PATH=$venv_path|" "$PROJECT_ROOT/.env"
    fi
}

setup_env_file() {
    log_info "Configurando archivo de variables de entorno..."
    
    local env_file="$PROJECT_ROOT/.env"
    
    if [[ -f "$env_file" ]]; then
        log_warn "El archivo .env ya existe"
        read -p "¿Quieres sobrescribirlo? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Manteniendo archivo .env existente"
            return 0
        fi
    fi
    
    # Crear archivo .env desde template
    cat > "$env_file" << 'EOF'
# =============================================================================
# VVMM Post Creator - Configuración de Variables de Entorno
# =============================================================================

# -----------------------------------------------------------------------------
# SPOTIFY API
# -----------------------------------------------------------------------------
SPOTIFY_CLIENT=
SPOTIFY_SECRET=

# -----------------------------------------------------------------------------
# DISCOGS API
# -----------------------------------------------------------------------------
DISCOGS_TOKEN=

# -----------------------------------------------------------------------------
# LAST.FM API (Opcional)
# -----------------------------------------------------------------------------
LASTFM_API_KEY=

# -----------------------------------------------------------------------------
# YOUTUBE API (Opcional)
# -----------------------------------------------------------------------------
YT_TOKEN=

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE PYTHON
# -----------------------------------------------------------------------------
PYTHON_VENV_PATH=./venv

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE COMPORTAMIENTO
# -----------------------------------------------------------------------------
ENABLE_PREVIEW=true
ENABLE_GIT_PUSH=true
DEBUG_MODE=false

# -----------------------------------------------------------------------------
# CONFIGURACIÓN AVANZADA
# -----------------------------------------------------------------------------
MAX_API_RETRIES=3
HTTP_TIMEOUT=30
MAX_SEARCH_RESULTS=10
EOF
    
    log_info "Archivo .env creado ✓"
    log_warn "IMPORTANTE: Debes configurar las credenciales de API en $env_file"
}

copy_modules() {
    log_info "Copiando módulos al directorio modules/..."
    
    # Lista de archivos que deben estar en modules/
    local modules=(
        "limpia_var.sh"
        "limpiar_var.sh"
        "bandcamp.py"
        "lastfm.sh"
        "musicbrainz.py"
        "spotify.py"
        "youtube.py"
        "wikipedia.py"
        "discogs.py"
        "release_id.py"
        "caratula-spotify.py"
        "caratula-alternativa.py"
        "sp_playlist.py"
        "sp_playlist_md.py"
        "sp_busca_cancion.py"
        "sp_crear_playlist.py"
        "sp_duplicate.py"
        "sp_add_song_to_playlist.py"
        "info_discogs.py"
        "info_masterid_extraartist.py"
        "info_release_discogs.py"
        "info_release_discogs_extraartists.py"
    )
    
    local found_modules=0
    local total_modules=${#modules[@]}
    
    for module in "${modules[@]}"; do
        # Buscar el módulo en el directorio actual
        if [[ -f "$PROJECT_ROOT/$module" ]]; then
            cp "$PROJECT_ROOT/$module" "$PROJECT_ROOT/modules/"
            chmod +x "$PROJECT_ROOT/modules/$module"
            ((found_modules++))
            log_debug "Copiado: $module"
        else
            log_warn "Módulo no encontrado: $module"
        fi
    done
    
    log_info "Módulos copiados: $found_modules/$total_modules"
    
    if [[ $found_modules -lt $total_modules ]]; then
        log_warn "Algunos módulos no se encontraron. Asegúrate de tener todos los archivos necesarios."
    fi
}

setup_hugo_blog() {
    log_info "Configurando blog Hugo..."
    
    local blog_dir="/mnt/NFS/blogs/vvmm"
    
    if [[ ! -d "$blog_dir" ]]; then
        log_warn "Directorio del blog no encontrado: $blog_dir"
        read -p "¿Quieres crear un blog Hugo nuevo en este directorio? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            mkdir -p "$(dirname "$blog_dir")"
            cd "$(dirname "$blog_dir")"
            hugo new site "$(basename "$blog_dir")"
            log_info "Blog Hugo creado en $blog_dir"
        else
            log_warn "Deberás configurar manualmente la ruta del blog"
            return 0
        fi
    fi
    
    # Verificar estructura básica de Hugo
    local required_hugo_dirs=(
        "$blog_dir/content"
        "$blog_dir/content/posts"
        "$blog_dir/static"
        "$blog_dir/static/links"
        "$blog_dir/static/links/svg"
    )
    
    for dir in "${required_hugo_dirs[@]}"; do
        if [[ ! -d "$dir" ]]; then
            mkdir -p "$dir"
            log_debug "Creado directorio Hugo: $dir"
        fi
    done
    
    # Crear archivo about.md.skel si no existe
    local about_skel="$blog_dir/content/about.md.skel"
    if [[ ! -f "$about_skel" ]]; then
        cat > "$about_skel" << 'EOF'
---
title: "About"
date: 2023-01-01
draft: false
---

# Sobre VVMM

Blog de música generado automáticamente.

## Playlists de Spotify

EOF
        log_debug "Creado archivo about.md.skel"
    fi
    
    log_info "Blog Hugo configurado ✓"
}

setup_git_repository() {
    log_info "Configurando repositorio Git..."
    
    local blog_dir="/mnt/NFS/blogs/vvmm"
    
    if [[ -d "$blog_dir" ]]; then
        cd "$blog_dir"
        
        if [[ ! -d ".git" ]]; then
            git init
            log_debug "Repositorio Git inicializado"
        fi
        
        # Configurar .gitignore si no existe
        if [[ ! -f ".gitignore" ]]; then
            cat > ".gitignore" << 'EOF'
# Hugo
/public/
/resources/
.hugo_build.lock

# Logs
*.log

# Temporary files
*.tmp
*.temp
releases.txt

# Cache
.cache/

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
EOF
            log_debug "Archivo .gitignore creado"
        fi
        
        log_info "Repositorio Git configurado ✓"
    else
        log_warn "Directorio del blog no encontrado, saltando configuración Git"
    fi
}

setup_permissions() {
    log_info "Configurando permisos..."
    
    # Hacer ejecutables los scripts principales
    chmod +x "$PROJECT_ROOT/vvmm_post_creator.sh"
    chmod +x "$PROJECT_ROOT/setup.sh"
    
    # Hacer ejecutables todos los módulos
    find "$PROJECT_ROOT/modules" -name "*.sh" -exec chmod +x {} \;
    find "$PROJECT_ROOT/modules" -name "*.py" -exec chmod +x {} \;
    
    log_info "Permisos configurados ✓"
}

validate_setup() {
    log_info "Validando configuración..."
    
    local validation_errors=0
    
    # Verificar estructura de directorios
    local required_dirs=(
        "$PROJECT_ROOT/.content"
        "$PROJECT_ROOT/.content/logs"
        "$PROJECT_ROOT/.content/cache"
        "$PROJECT_ROOT/modules"
    )
    
    for dir in "${required_dirs[@]}"; do
        if [[ ! -d "$dir" ]]; then
            log_error "Directorio faltante: $dir"
            ((validation_errors++))
        fi
    done
    
    # Verificar archivos principales
    local required_files=(
        "$PROJECT_ROOT/vvmm_post_creator.sh"
        "$PROJECT_ROOT/.env"
    )
    
    for file in "${required_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            log_error "Archivo faltante: $file"
            ((validation_errors++))
        fi
    done
    
    # Verificar algunos módulos críticos
    local critical_modules=(
        "limpia_var.sh"
        "spotify.py"
        "discogs.py"
    )
    
    for module in "${critical_modules[@]}"; do
        if [[ ! -f "$PROJECT_ROOT/modules/$module" ]]; then
            log_error "Módulo crítico faltante: modules/$module"
            ((validation_errors++))
        fi
    done
    
    if [[ $validation_errors -eq 0 ]]; then
        log_info "Validación completada ✓"
        return 0
    else
        log_error "Validación falló con $validation_errors errores"
        return 1
    fi
}

show_configuration_help() {
    echo -e "${CYAN}"
    cat << 'EOF'
╔═══════════════════════════════════════════════════════════════╗
║                    CONFIGURACIÓN REQUERIDA                   ║
╚═══════════════════════════════════════════════════════════════╝
EOF
    echo -e "${RESET}"
    
    log_info "Para completar la configuración, necesitas:"
    echo
    echo -e "${YELLOW}1. Credenciales de APIs:${RESET}"
    echo "   • Spotify: https://developer.spotify.com/dashboard/"
    echo "   • Discogs: https://www.discogs.com/settings/developers"
    echo "   • Last.fm (opcional): https://www.last.fm/api/account/create"
    echo "   • YouTube (opcional): https://console.cloud.google.com/"
    echo
    echo -e "${YELLOW}2. Editar el archivo .env:${RESET}"
    echo "   nano $PROJECT_ROOT/.env"
    echo
    echo -e "${YELLOW}3. Configurar reproductores de música:${RESET}"
    echo "   • Deadbeef o Strawberry Music Player"
    echo "   • Playerctl para control de media"
    echo
    echo -e "${YELLOW}4. Verificar rutas:${RESET}"
    echo "   • Blog Hugo: /mnt/NFS/blogs/vvmm"
    echo "   • Scripts de reproducción: /home/huan/Scripts/utilities/aliases/"
    echo "   • Menú de playlists: /home/huan/Scripts/menus/spotify/"
    echo
    echo -e "${GREEN}Una vez configurado, ejecuta:${RESET}"
    echo "   ./vvmm_post_creator.sh --validate-only"
    echo "   ./vvmm_post_creator.sh"
}

show_usage() {
    cat << EOF
VVMM Post Creator Setup

USO:
    $0 [opciones]

OPCIONES:
    -h, --help              Mostrar esta ayuda
    --check-requirements    Solo verificar requisitos del sistema
    --setup-python         Solo configurar entorno Python
    --setup-dirs           Solo crear estructura de directorios
    --setup-env            Solo configurar archivo .env
    --validate             Solo validar configuración existente
    --full                 Instalación completa (por defecto)

EJEMPLOS:
    $0                     # Instalación completa
    $0 --check-requirements # Solo verificar requisitos
    $0 --validate          # Solo validar configuración
EOF
}

main() {
    local action="full"
    
    # Procesar argumentos
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_usage
                exit 0
                ;;
            --check-requirements)
                action="check"
                ;;
            --setup-python)
                action="python"
                ;;
            --setup-dirs)
                action="dirs"
                ;;
            --setup-env)
                action="env"
                ;;
            --validate)
                action="validate"
                ;;
            --full)
                action="full"
                ;;
            *)
                log_error "Opción desconocida: $1"
                show_usage
                exit 1
                ;;
        esac
        shift
    done
    
    show_banner
    
    case $action in
        check)
            check_requirements
            ;;
        python)
            setup_python_environment
            ;;
        dirs)
            create_directory_structure
            ;;
        env)
            setup_env_file
            ;;
        validate)
            validate_setup
            ;;
        full)
            log_info "Iniciando instalación completa..."
            
            # Verificar requisitos
            if ! check_requirements; then
                log_error "Faltan requisitos del sistema. Instálalos y ejecuta el setup nuevamente."
                exit 1
            fi
            
            # Ejecutar todos los pasos de setup
            create_directory_structure
            setup_env_file
            copy_modules
            setup_python_environment
            setup_hugo_blog
            setup_git_repository
            setup_permissions
            
            # Validar configuración final
            if validate_setup; then
                echo
                echo -e "${GREEN}🎉 ¡Instalación completada exitosamente! 🎉${RESET}"
                echo
                show_configuration_help
            else
                log_error "La instalación se completó pero la validación falló"
                exit 1
            fi
            ;;
    esac
}

# Manejo de errores
set -e
trap 'log_error "Error en línea $LINENO. Código de salida: $?"' ERR

# Ejecutar función principal
main "$@"