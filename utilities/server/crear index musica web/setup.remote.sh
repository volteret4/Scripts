#!/bin/bash
# Setup para servidor remoto 192.168.1.180
# Ejecutar como root en el servidor web

set -e

WEB_ROOT="/var/www/html/musica"
WEB_USER="www-data"

echo "=== Setup Music Web Explorer en servidor remoto ==="
echo "Fecha: $(date)"
echo

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

show_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

show_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

show_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

show_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Verificar que somos root
if [[ $EUID -ne 0 ]]; then
   show_error "Este script debe ejecutarse como root"
   exit 1
fi

# Crear directorios web
show_info "Creando estructura de directorios..."
mkdir -p "$WEB_ROOT"
mkdir -p "$WEB_ROOT/static"
mkdir -p "$WEB_ROOT/static/css"
mkdir -p "$WEB_ROOT/static/js"
mkdir -p "$WEB_ROOT/static/images"
mkdir -p "$WEB_ROOT/logs"

# Cambiar propietario
chown -R $WEB_USER:$WEB_USER "$WEB_ROOT"
chmod -R 755 "$WEB_ROOT"

show_success "Directorios creados en $WEB_ROOT"

# Verificar nginx
if ! command -v nginx &> /dev/null; then
    show_warning "nginx no instalado, instalando..."
    apt update
    apt install -y nginx
fi

show_success "nginx disponible"

# Verificar que nginx está ejecutándose
if ! systemctl is-active --quiet nginx; then
    show_info "Iniciando nginx..."
    systemctl start nginx
    systemctl enable nginx
fi

show_success "nginx está ejecutándose"

# Crear página de prueba temporal
cat > "$WEB_ROOT/index.html" << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>Music Web Explorer - Setup</title>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; text-align: center; margin: 50px; }
        .container { max-width: 600px; margin: 0 auto; }
        .status { padding: 20px; background: #f0f0f0; border-radius: 10px; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎵 Music Web Explorer</h1>
        <div class="status">
            <h2>Setup Completado</h2>
            <p>El servidor web está listo para recibir archivos.</p>
            <p>Ejecuta la sincronización desde pepecono.</p>
        </div>
        <p>Generado: $(date)</p>
    </div>
</body>
</html>
EOF

# Crear configuración nginx básica
cat > /etc/nginx/sites-available/musica << 'EOF'
server {
    listen 80;
    server_name 192.168.1.180;
    
    root /var/www/html/musica;
    index index.html;
    
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    location /musica/ {
        alias /var/www/html/musica/;
        try_files $uri $uri/ /index.html;
    }
    
    # Logs
    access_log /var/log/nginx/musica_access.log;
    error_log /var/log/nginx/musica_error.log;
}
EOF

# Habilitar sitio
ln -sf /etc/nginx/sites-available/musica /etc/nginx/sites-enabled/

# Probar configuración nginx
if nginx -t; then
    systemctl reload nginx
    show_success "Configuración nginx aplicada"
else
    show_error "Error en configuración nginx"
    exit 1
fi

# Verificar conectividad a pepecono (si Tailscale está instalado)
if command -v tailscale &> /dev/null; then
    if ping -c 1 -W 5 100.90.91.96 >/dev/null 2>&1; then
        show_success "100.90.91.96 es alcanzable"
    else
        show_warning "100.90.91.96 no es alcanzable (¿Tailscale configurado?)"
    fi
else
    show_warning "Tailscale no instalado - se necesita para conectar con pepecono"
    show_info "Instala Tailscale: curl -fsSL https://tailscale.com/install.sh | sh"
fi

# Crear script de verificación
cat > "$WEB_ROOT/verify.sh" << 'EOF'
#!/bin/bash
echo "=== Verificación Music Web Explorer ==="
echo "Fecha: $(date)"
echo

# Verificar archivos
echo "Archivos en /var/www/html/musica:"
ls -la /var/www/html/musica/

echo
echo "Estado nginx:"
systemctl status nginx --no-pager -l

echo
echo "Conectividad pepecono:"
if ping -c 1 -W 5 100.90.91.96 >/dev/null 2>&1; then
    echo "✅ 100.90.91.96 alcanzable"
else
    echo "❌ 100.90.91.96 NO alcanzable"
fi

echo
echo "Test web local:"
curl -s -o /dev/null -w "HTTP Status: %{http_code}\n" http://localhost/musica/
EOF

chmod +x "$WEB_ROOT/verify.sh"

echo
show_success "¡Setup completado!"
echo
echo "Próximos pasos:"
echo "1. Verificar: http://192.168.1.180/musica/"
echo "2. Ejecutar sincronización desde pepecono"
echo "3. Verificar estado: $WEB_ROOT/verify.sh"
echo
echo "Logs nginx:"
echo "  - Access: /var/log/nginx/musica_access.log"
echo "  - Error: /var/log/nginx/musica_error.log"