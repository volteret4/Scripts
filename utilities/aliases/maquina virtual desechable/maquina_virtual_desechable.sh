#!/bin/bash

# ==========================================
# Contenedor Desechable Arch - VERSIÓN DOCKER
# Funciona con Docker presente usando bridge
# ==========================================

set -e

CONTAINER_BASE="/var/lib/machines"
TEMPLATE_NAME="arch-disposable"
BRIDGE_NAME="br-systemd-nspawn"

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Verificar que el bridge existe
check_bridge() {
    if ! ip link show "$BRIDGE_NAME" >/dev/null 2>&1; then
        log_error "Bridge $BRIDGE_NAME no existe"
        log_info "Ejecuta primero: sudo ./arreglar-red-docker.sh"
        exit 1
    fi
}

# Shell efímero rápido
quick_shell() {
    check_bridge
    log_info "Iniciando shell efímero..."

    sudo systemd-nspawn -D "$CONTAINER_BASE/$TEMPLATE_NAME" \
        --ephemeral \
        --network-bridge="$BRIDGE_NAME" \
        /bin/bash -c "/usr/local/bin/setup-container-network.sh && /bin/bash"

    log_info "Contenedor eliminado"
}

# Shell efímero con paquetes
quick_with_packages() {
    check_bridge
    echo -n "Paquetes a instalar (ej: vim git python): "
    read -r packages

    if [ -z "$packages" ]; then
        quick_shell
        return
    fi

    log_info "Instalando: $packages"

    sudo systemd-nspawn -D "$CONTAINER_BASE/$TEMPLATE_NAME" \
        --ephemeral \
        --network-bridge="$BRIDGE_NAME" \
        --bind=/var/cache/pacman/pkg:/var/cache/pacman/pkg \
        /bin/bash -c "/usr/local/bin/setup-container-network.sh && pacman -Sy --noconfirm $packages && exec /bin/bash"

    log_info "Contenedor eliminado"
}

# Crear contenedor persistente
create_persistent() {
    check_bridge
    local NAME="disposable-$(date +%s)"

    log_info "Creando contenedor $NAME..."

    # Clonar
    if [[ $(df -T "$CONTAINER_BASE" | tail -1 | awk '{print $2}') == "btrfs" ]]; then
        sudo btrfs subvolume snapshot "$CONTAINER_BASE/$TEMPLATE_NAME" "$CONTAINER_BASE/$NAME"
    else
        sudo cp -a "$CONTAINER_BASE/$TEMPLATE_NAME" "$CONTAINER_BASE/$NAME"
    fi

    # Arrancar
    log_info "Arrancando..."
    sudo systemd-nspawn -bD "$CONTAINER_BASE/$NAME" \
        --network-bridge="$BRIDGE_NAME" \
        --machine="$NAME" &

    sleep 3

    log_info "Contenedor: $NAME"
    log_info "Conectar: sudo machinectl shell $NAME"

    echo "$NAME"
}

# Listar
list_containers() {
    log_info "Contenedores activos:"
    sudo machinectl list || echo "  (ninguno)"

    echo ""
    log_info "En disco:"
    ls -1 "$CONTAINER_BASE" 2>/dev/null | grep -v "$TEMPLATE_NAME" || echo "  (ninguno)"
}

# Eliminar
destroy_container() {
    echo -n "Nombre del contenedor: "
    read NAME

    log_warn "¿Eliminar $NAME? (s/n)"
    read -r response

    if [[ "$response" =~ ^[Ss]$ ]]; then
        sudo machinectl terminate "$NAME" 2>/dev/null || true
        sleep 1

        if [[ $(df -T "$CONTAINER_BASE" | tail -1 | awk '{print $2}') == "btrfs" ]]; then
            sudo btrfs subvolume delete "$CONTAINER_BASE/$NAME" 2>/dev/null || \
                sudo rm -rf "$CONTAINER_BASE/$NAME"
        else
            sudo rm -rf "$CONTAINER_BASE/$NAME"
        fi

        log_info "Eliminado"
    fi
}

# Menú
show_menu() {
    echo ""
    echo "=========================================="
    echo "   Contenedores Arch (Versión Docker)"
    echo "=========================================="
    echo "1) Shell efímero rápido"
    echo "2) Efímero con paquetes"
    echo "3) Crear persistente"
    echo "4) Conectar a contenedor"
    echo "5) Listar contenedores"
    echo "6) Eliminar contenedor"
    echo "7) Salir"
    echo "=========================================="
    echo -n "Opción: "
}

main() {
    if [ ! -d "$CONTAINER_BASE/$TEMPLATE_NAME" ]; then
        log_error "Template no existe"
        log_info "Ejecuta: sudo ./reparar-todo.sh"
        exit 1
    fi

    # Atajos de línea de comandos
    if [ "$1" == "quick" ]; then
        quick_shell
        exit 0
    fi

    if [ "$1" == "pkg" ]; then
        shift
        if [ -n "$*" ]; then
            check_bridge
            sudo systemd-nspawn -D "$CONTAINER_BASE/$TEMPLATE_NAME" \
                --ephemeral --network-bridge="$BRIDGE_NAME" \
                --bind=/var/cache/pacman/pkg:/var/cache/pacman/pkg \
                /bin/bash -c "/usr/local/bin/setup-container-network.sh && pacman -Sy --noconfirm $* && exec /bin/bash"
        else
            quick_with_packages
        fi
        exit 0
    fi

    while true; do
        show_menu
        read -r option

        case $option in
            1) quick_shell ;;
            2) quick_with_packages ;;
            3) create_persistent ;;
            4)
                echo -n "Nombre: "
                read NAME
                sudo machinectl shell "$NAME"
                ;;
            5) list_containers ;;
            6) destroy_container ;;
            7)
                log_info "¡Adiós!"
                exit 0
                ;;
            *)
                log_error "Opción inválida"
                ;;
        esac
    done
}

main "$@"
