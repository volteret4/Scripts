#!/bin/bash

# ==========================================
# CONTENEDOR DESECHABLE - DOCKER + ARCH
# Simple, rápido, y funciona siempre
# ==========================================

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[✓]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[!]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }

# Verificar Docker
if ! command -v docker &> /dev/null; then
    log_error "Docker no está instalado"
    exit 1
fi

if ! docker info &> /dev/null; then
    log_error "Docker no está corriendo o no tienes permisos"
    log_info "Prueba: sudo usermod -aG docker $USER"
    log_info "Luego cierra sesión y vuelve a entrar"
    exit 1
fi

# Shell desechable básico
quick_shell() {
    log_info "Iniciando Arch desechable (se borra al salir)..."

    docker run --rm -it \
        --hostname arch-disposable \
        archlinux:latest \
        /bin/bash
}

# Shell con paquetes preinstalados
with_packages() {
    local packages="$@"

    if [ -z "$packages" ]; then
        echo -n "Paquetes a instalar (ej: vim git npm): "
        read packages

        if [ -z "$packages" ]; then
            quick_shell
            return
        fi
    fi

    log_info "Creando contenedor con: $packages"

    docker run --rm -it \
        --hostname arch-disposable \
        archlinux:latest \
        /bin/bash -c "pacman -Sy --noconfirm $packages && exec /bin/bash"
}

# Shell con directorio compartido
with_volume() {
    local dir="${1:-.}"
    local abs_dir=$(realpath "$dir")

    log_info "Compartiendo: $abs_dir → /mnt/shared"

    docker run --rm -it \
        --hostname arch-disposable \
        -v "$abs_dir:/mnt/shared" \
        -w /mnt/shared \
        archlinux:latest \
        /bin/bash
}

# Shell persistente (guarda cambios)
persistent() {
    local name="${1:-arch-dev}"

    log_info "Contenedor persistente: $name"

    # Verificar si ya existe
    if docker ps -a --format '{{.Names}}' | grep -q "^${name}$"; then
        log_info "Contenedor $name ya existe, arrancando..."
        docker start -ai "$name"
    else
        log_info "Creando nuevo contenedor $name..."
        docker run -it \
            --name "$name" \
            --hostname "$name" \
            archlinux:latest \
            /bin/bash
    fi
}

# Listar contenedores
list_containers() {
    log_info "Contenedores en ejecución:"
    docker ps

    echo ""
    log_info "Todos los contenedores (incluso detenidos):"
    docker ps -a
}

# Eliminar contenedor persistente
destroy() {
    local name="$1"

    if [ -z "$name" ]; then
        echo -n "Nombre del contenedor a eliminar: "
        read name
    fi

    log_warn "¿Eliminar contenedor $name? (s/n)"
    read -r response

    if [[ "$response" =~ ^[Ss]$ ]]; then
        docker rm -f "$name" 2>/dev/null && log_info "Eliminado" || log_error "No existe"
    fi
}

# Limpiar todos los contenedores detenidos
cleanup() {
    log_warn "¿Limpiar TODOS los contenedores detenidos? (s/n)"
    read -r response

    if [[ "$response" =~ ^[Ss]$ ]]; then
        docker container prune -f
        log_info "Limpieza completada"
    fi
}

# Menú
show_menu() {
    echo ""
    echo "=========================================="
    echo "   Contenedores Desechables - Docker"
    echo "=========================================="
    echo "1) Shell desechable rápido"
    echo "2) Shell con paquetes"
    echo "3) Shell con directorio compartido"
    echo "4) Shell persistente (guarda cambios)"
    echo "5) Listar contenedores"
    echo "6) Eliminar contenedor"
    echo "7) Limpiar contenedores detenidos"
    echo "8) Salir"
    echo "=========================================="
    echo -n "Opción: "
}

# Main
if [ "$1" == "quick" ]; then
    quick_shell
    exit 0
fi

if [ "$1" == "pkg" ]; then
    shift
    with_packages "$@"
    exit 0
fi

if [ "$1" == "vol" ]; then
    shift
    with_volume "$@"
    exit 0
fi

if [ "$1" == "persist" ]; then
    shift
    persistent "$@"
    exit 0
fi

while true; do
    show_menu
    read -r option

    case $option in
        1) quick_shell ;;
        2) with_packages ;;
        3)
            echo -n "Directorio a compartir [.]: "
            read dir
            with_volume "${dir:-.}"
            ;;
        4)
            echo -n "Nombre del contenedor [arch-dev]: "
            read name
            persistent "${name:-arch-dev}"
            ;;
        5) list_containers ;;
        6) destroy ;;
        7) cleanup ;;
        8)
            log_info "¡Adiós!"
            exit 0
            ;;
        *)
            log_error "Opción inválida"
            ;;
    esac
done
