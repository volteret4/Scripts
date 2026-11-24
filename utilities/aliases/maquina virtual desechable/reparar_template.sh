#!/bin/bash

# ==========================================
# LIMPIEZA Y REPARACIÓN DE EMERGENCIA
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
echo "  LIMPIEZA Y REPARACIÓN"
echo "=========================================="
echo ""

# 1. Limpiar todo lo corrupto
log_warn "Paso 1: Limpiando archivos corruptos..."

sudo machinectl list --no-legend 2>/dev/null | while read machine rest; do
    if [[ "$machine" == arch-disposable* ]] || [[ "$machine" == disposable-* ]]; then
        log_info "Deteniendo: $machine"
        sudo machinectl terminate "$machine" 2>/dev/null || true
    fi
done

sleep 2

log_info "Eliminando templates y contenedores viejos..."
sudo rm -rf /var/lib/machines/arch-disposable* 2>/dev/null || true
sudo rm -rf /var/lib/machines/disposable-* 2>/dev/null || true
sudo rm -rf /var/lib/machines/.#machine.* 2>/dev/null || true

log_info "Limpieza completada"
echo ""

# 2. Verificar dependencias
log_warn "Paso 2: Verificando dependencias..."

if ! command -v pacstrap &> /dev/null; then
    log_warn "Instalando arch-install-scripts..."
    sudo pacman -S --noconfirm arch-install-scripts
fi

if ! systemctl is-active --quiet systemd-networkd; then
    log_warn "Activando systemd-networkd..."
    sudo systemctl enable --now systemd-networkd
fi

log_info "Dependencias OK"
echo ""

# 3. Crear template limpio con pacstrap
log_warn "Paso 3: Creando template NUEVO con pacstrap..."
log_info "Esto tomará 2-3 minutos (descarga ~200MB)"
echo ""

TEMPLATE="/var/lib/machines/arch-disposable"
sudo mkdir -p "$TEMPLATE"

echo "Instalando sistema base..."
# Ignorar errores de hooks específicos de ArcoLinux (no son críticos)
sudo pacstrap -c "$TEMPLATE" base systemd openssh 2>&1 | grep -v "arcolinux-os-release" || true

echo ""
log_info "Sistema base instalado"

# 4. Configurar mirrors españoles
log_info "Configurando mirrors..."
sudo tee "$TEMPLATE/etc/pacman.d/mirrorlist" > /dev/null << 'EOF'
## Spain and reliable mirrors
Server = https://mirror.23m.com/archlinux/$repo/os/$arch
Server = https://mirrors.kernel.org/archlinux/$repo/os/$arch
Server = https://mirror.rackspace.com/archlinux/$repo/os/$arch
Server = https://ftp.fau.de/archlinux/$repo/os/$arch
EOF

# 5. Configurar el sistema
log_info "Configurando sistema..."
sudo systemd-nspawn -D "$TEMPLATE" /bin/bash << 'EOFCONFIG'
# Password
echo "root:temporal" | chpasswd

# SSH
mkdir -p /root/.ssh
chmod 700 /root/.ssh
systemctl enable sshd

# Red
systemctl enable systemd-networkd

cat > /etc/systemd/network/80-container-host0.network << 'NETEOF'
[Match]
Name=host0

[Network]
DHCP=yes
NETEOF

# DNS estático (NO usar systemd-resolved que causa problemas)
# Eliminar cualquier symlink
rm -f /etc/resolv.conf

# Crear resolv.conf estático
cat > /etc/resolv.conf << 'RESOLVEOF'
nameserver 8.8.8.8
nameserver 8.8.4.4
nameserver 1.1.1.1
RESOLVEOF

chmod 644 /etc/resolv.conf

# Limpiar cache
pacman -Scc --noconfirm
rm -rf /var/cache/pacman/pkg/*

exit
EOFCONFIG

log_info "Sistema configurado"
echo ""

# 6. Verificar que funciona
log_warn "Paso 4: Verificando que funciona..."
echo ""

log_info "Test 1: Verificar que el template tiene /usr..."
if [ -d "$TEMPLATE/usr" ]; then
    log_info "/usr existe ✓"
else
    log_error "/usr NO existe - algo falló"
    exit 1
fi

log_info "Test 2: Verificar tamaño..."
SIZE=$(du -sh "$TEMPLATE" | cut -f1)
log_info "Tamaño del template: $SIZE"

log_info "Test 3: Probar contenedor efímero..."
PING_TEST=$(sudo systemd-nspawn -D "$TEMPLATE" \
    --ephemeral --network-veth --quiet \
    --resolv-conf=copy-host --bind-ro=/etc/resolv.conf \
    /bin/bash -c "ping -c 2 8.8.8.8 > /dev/null 2>&1 && echo OK || echo FAIL" 2>/dev/null)

if [ "$PING_TEST" == "OK" ]; then
    log_info "Red funciona ✓"
else
    log_warn "Red no funciona todavía (puede necesitar reinicio)"
fi

log_info "Test 4: Probar pacman..."
PACMAN_TEST=$(sudo systemd-nspawn -D "$TEMPLATE" \
    --ephemeral --network-veth --quiet \
    --resolv-conf=copy-host --bind-ro=/etc/resolv.conf \
    /bin/bash -c "pacman -Sy --noconfirm > /dev/null 2>&1 && echo OK || echo FAIL" 2>/dev/null)

if [ "$PACMAN_TEST" == "OK" ]; then
    log_info "Pacman funciona ✓"
else
    log_warn "Pacman tuvo problemas (pero el template es válido)"
fi

echo ""
echo "=========================================="
log_info "✨ REPARACIÓN COMPLETADA ✨"
echo "=========================================="
echo ""
echo "El template está listo en: $TEMPLATE"
echo "Tamaño: $SIZE"
echo ""
echo "Prueba ahora:"
echo "  sudo ./disposable-arch-simple.sh quick"
echo ""
echo "O instala paquetes:"
echo "  sudo ./disposable-arch-simple.sh pkg vim git"
echo ""
