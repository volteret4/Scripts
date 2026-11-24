#!/bin/bash

# ==========================================
# ARREGLO DE RED PARA SISTEMAS CON DOCKER
# ==========================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[✓]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[!]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }

echo "=========================================="
echo "  ARREGLO RED - DOCKER PRESENTE"
echo "=========================================="
echo ""

if [ "$EUID" -ne 0 ]; then
    log_error "Ejecuta con sudo"
    exit 1
fi

TEMPLATE="/var/lib/machines/arch-disposable"

if [ ! -d "$TEMPLATE/usr" ]; then
    log_error "Template no existe. Ejecuta primero: sudo ./reparar-todo.sh"
    exit 1
fi

log_info "Detectado Docker en el sistema"
log_info "Configurando contenedores para coexistir con Docker..."
echo ""

# 1. Crear script de arranque de red en el template
log_info "Creando script de configuración de red automática..."

cat > "$TEMPLATE/usr/local/bin/setup-container-network.sh" << 'NETSCRIPT'
#!/bin/bash
# Script para configurar red al arrancar contenedor

# Esperar a que la interfaz esté disponible
sleep 1

# Configurar host0
if ip link show host0 >/dev/null 2>&1; then
    # Levantar interfaz
    ip link set host0 up

    # Esperar DHCP (con timeout)
    timeout=10
    while [ $timeout -gt 0 ]; do
        if dhcpcd -q -t 5 host0 2>/dev/null; then
            echo "Red configurada correctamente"
            exit 0
        fi
        sleep 1
        timeout=$((timeout-1))
    done

    # Si DHCP falla, configurar IP estática en la red del host
    echo "DHCP falló, usando IP estática..."
    ip addr add 169.254.1.2/16 dev host0
    ip route add default via 169.254.1.1 || true
fi
NETSCRIPT

chmod +x "$TEMPLATE/usr/local/bin/setup-container-network.sh"

# 2. Instalar dhcpcd si no está
log_info "Asegurando que dhcpcd está instalado..."
systemd-nspawn -D "$TEMPLATE" --quiet \
    /bin/bash -c "pacman -S --noconfirm --needed dhcpcd 2>/dev/null" || true

# 3. Crear configuración de red simple (sin systemd-networkd)
log_info "Creando configuración de red simple..."

# Eliminar configuración de systemd-networkd
rm -f "$TEMPLATE/etc/systemd/network/"*.network

# Deshabilitar systemd-networkd (no lo necesitamos)
systemd-nspawn -D "$TEMPLATE" --quiet \
    /bin/bash -c "systemctl disable systemd-networkd 2>/dev/null" || true

# 4. Crear resolv.conf estático
log_info "Configurando DNS..."
rm -f "$TEMPLATE/etc/resolv.conf"
cat > "$TEMPLATE/etc/resolv.conf" << 'EOF'
nameserver 192.168.1.202
nameserver 192.168.1.111
nameserver 8.8.8.8
nameserver 1.1.1.1
EOF
chmod 644 "$TEMPLATE/etc/resolv.conf"

# 5. Habilitar IP forwarding en el host
log_info "Habilitando IP forwarding en el host..."
sysctl -w net.ipv4.ip_forward=1 >/dev/null
if ! grep -q "net.ipv4.ip_forward=1" /etc/sysctl.d/99-sysctl.conf 2>/dev/null; then
    echo "net.ipv4.ip_forward=1" >> /etc/sysctl.d/99-sysctl.conf
fi

# 6. Configurar bridge con una red diferente a Docker
log_info "Configurando puente de red..."

# Docker usa 172.17-29.x.x, usaremos 172.30.x.x
BRIDGE_NAME="br-systemd-nspawn"
BRIDGE_IP="172.30.0.1/16"

# Crear bridge si no existe
if ! ip link show "$BRIDGE_NAME" >/dev/null 2>&1; then
    ip link add name "$BRIDGE_NAME" type bridge
    ip addr add "$BRIDGE_IP" dev "$BRIDGE_NAME"
    ip link set "$BRIDGE_NAME" up
    log_info "Bridge $BRIDGE_NAME creado"
fi

# 7. Configurar NAT para el bridge
log_info "Configurando NAT..."

# Obtener interfaz de salida
OUT_IF=$(ip route | grep default | awk '{print $5}' | head -n1)

if command -v nft &>/dev/null && systemctl is-active --quiet nftables 2>/dev/null; then
    # nftables
    nft add table ip nat 2>/dev/null || true
    nft add chain ip nat postrouting { type nat hook postrouting priority 100 \; } 2>/dev/null || true
    nft add rule ip nat postrouting oifname "$OUT_IF" masquerade 2>/dev/null || true
    log_info "NAT configurado con nftables"
elif command -v iptables &>/dev/null; then
    # iptables
    iptables -t nat -C POSTROUTING -o "$OUT_IF" -j MASQUERADE 2>/dev/null || \
        iptables -t nat -A POSTROUTING -o "$OUT_IF" -j MASQUERADE
    log_info "NAT configurado con iptables"
fi

echo ""
echo "=========================================="
echo "  TEST DE CONECTIVIDAD"
echo "=========================================="
echo ""

log_info "Probando contenedor con bridge..."

# Test con el script de red personalizado
TEST_OUTPUT=$(timeout 15 systemd-nspawn -D "$TEMPLATE" \
    --network-bridge="$BRIDGE_NAME" \
    --ephemeral \
    /bin/bash -c "
    /usr/local/bin/setup-container-network.sh
    sleep 2
    echo '=== Interfaces ==='
    ip addr show
    echo ''
    echo '=== Rutas ==='
    ip route
    echo ''
    echo '=== Test ping IP ==='
    ping -c 2 -W 3 8.8.8.8 && echo 'IP: OK' || echo 'IP: FAIL'
    echo ''
    echo '=== Test ping DNS ==='
    ping -c 2 -W 3 google.com && echo 'DNS: OK' || echo 'DNS: FAIL'
    " 2>&1)

echo "$TEST_OUTPUT"
echo ""

if echo "$TEST_OUTPUT" | grep -q "IP: OK"; then
    log_info "✅ ¡CONECTIVIDAD FUNCIONA!"

    if echo "$TEST_OUTPUT" | grep -q "DNS: OK"; then
        log_info "✅ ¡DNS TAMBIÉN FUNCIONA!"
        echo ""
        log_info "Sistema listo. Ahora actualiza los scripts..."
    else
        log_warn "IP funciona pero DNS falla"
        log_info "Verifica tu pihole en 192.168.1.202"
    fi
else
    log_error "Conectividad sigue fallando"
    log_info "Revisa la salida de arriba para más detalles"
fi

echo ""
log_info "IMPORTANTE: Actualiza los scripts para usar --network-bridge"
echo ""
echo "Ejecuta esto para actualizar:"
echo "  sudo ./actualizar-scripts-bridge.sh"
echo ""
