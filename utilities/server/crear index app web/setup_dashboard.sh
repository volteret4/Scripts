#!/bin/bash
# setup_dashboard.sh - Configura automáticamente el dashboard

echo "🚀 Configurando Dashboard del Servidor"
echo "======================================"

# Crear archivos de configuración
create_docker_compose() {
    cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  # Servidor web para el dashboard
  dashboard-web:
    image: nginx:alpine
    container_name: server-dashboard-web
    ports:
      - "8080:80"
    volumes:
      - ./dashboard:/usr/share/nginx/html:ro
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
    restart: unless-stopped
    networks:
      - dashboard

networks:
  dashboard:
    driver: bridge
EOF
    echo "✅ docker-compose.yml creado (versión simple)"
}

create_docker_compose_full() {
    cat > docker-compose-full.yml << 'EOF'
version: '3.8'

services:
  # Servidor web para el dashboard
  dashboard-web:
    image: nginx:alpine
    container_name: server-dashboard-web
    ports:
      - "8080:80"
    volumes:
      - ./dashboard:/usr/share/nginx/html:ro
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
    restart: unless-stopped
    networks:
      - dashboard

  # Generador automático del dashboard
  dashboard-generator:
    build:
      context: .
      dockerfile: Dockerfile.generator
    container_name: server-dashboard-generator
    volumes:
      - ./dashboard:/app/dashboard
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      - PYTHONUNBUFFERED=1
      - UPDATE_INTERVAL=300
    restart: unless-stopped
    networks:
      - dashboard
    depends_on:
      - dashboard-web

networks:
  dashboard:
    driver: bridge
EOF
    echo "✅ docker-compose-full.yml creado (con auto-actualización)"
}

create_nginx_config() {
    cat > nginx.conf << 'EOF'
server {
    listen 80;
    server_name localhost;
    
    root /usr/share/nginx/html;
    index index.html;
    
    # Configurar para Single Page Application
    location / {
        try_files $uri $uri/ /index.html;
        
        # Headers de seguridad
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    }
    
    # API endpoint para datos JSON
    location /api {
        alias /usr/share/nginx/html;
        try_files /apps.json =404;
        
        add_header Content-Type application/json;
        add_header Access-Control-Allow-Origin *;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }
    
    # Configurar caché para archivos estáticos
    location ~* \.(css|js|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        access_log off;
    }
    
    # Comprimir respuestas
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/json
        application/javascript
        application/xml+rss
        application/atom+xml
        image/svg+xml;
}
EOF
    echo "✅ nginx.conf creado"
}

create_dockerfile_generator() {
    cat > Dockerfile.generator << 'EOF'
FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    lsof \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python
RUN pip install --no-cache-dir requests psutil

# Copiar archivos del proyecto
COPY dashboard_generator.py .
COPY dashboard_extensions.py* ./
COPY config.py* ./

# Crear script de entrada
COPY <<EOF /app/docker-entrypoint.sh
#!/bin/bash
echo "🚀 Iniciando Dashboard Generator"
echo "   Intervalo de actualización: \${UPDATE_INTERVAL:-300} segundos"

while true; do
    echo "🔄 Actualizando dashboard - \$(date)"
    python dashboard_generator.py
    
    if [ \$? -eq 0 ]; then
        echo "✅ Dashboard actualizado correctamente"
    else
        echo "❌ Error actualizando dashboard"
    fi
    
    echo "⏳ Esperando \${UPDATE_INTERVAL:-300} segundos..."
    sleep \${UPDATE_INTERVAL:-300}
done
EOF

RUN chmod +x /app/docker-entrypoint.sh

CMD ["/app/docker-entrypoint.sh"]

EOF
    echo "✅ Dockerfile.generator creado"
}

create_env_file() {
    cat > .env << 'EOF'
# Puerto para el dashboard web
DASHBOARD_PORT=8080

# Intervalo de actualización en segundos (5 minutos)
UPDATE_INTERVAL=300

# Configuración de red
NETWORK_NAME=dashboard
EOF
    echo "✅ .env creado"
}

# Crear archivos
echo "📁 Creando archivos de configuración..."
create_docker_compose
create_docker_compose_full
create_nginx_config
create_dockerfile_generator
create_env_file

# Verificar que existe el dashboard
if [ ! -d "dashboard" ]; then
    echo "⚠️  Directorio 'dashboard' no encontrado"
    echo "   Ejecutando generador de dashboard..."
    python dashboard_generator.py
fi

# Verificar archivos necesarios
missing_files=()
[ ! -f "dashboard_generator.py" ] && missing_files+=("dashboard_generator.py")
[ ! -f "dashboard/index.html" ] && missing_files+=("dashboard/index.html")

if [ ${#missing_files[@]} -ne 0 ]; then
    echo "❌ Archivos faltantes: ${missing_files[*]}"
    echo "   Asegúrate de tener todos los archivos del dashboard"
    exit 1
fi

echo ""
echo "🎉 ¡Configuración completada!"
echo ""
echo "Archivos creados:"
echo "  📄 docker-compose.yml (versión simple - solo web)"
echo "  📄 docker-compose-full.yml (con auto-actualización)"
echo "  📄 nginx.conf (configuración nginx)"
echo "  📄 Dockerfile.generator (para auto-actualización)"
echo ""
echo "Para iniciar solo el servidor web:"
echo "  docker-compose up -d"
echo ""
echo "Para iniciar con auto-actualización:"
echo "  docker-compose -f docker-compose-full.yml up -d"
echo ""
echo "Para ver logs:"
echo "  docker-compose logs -f"
echo ""
echo "Dashboard disponible en:"
echo "  🌐 http://localhost:8080"
echo "  📊 http://localhost:8080/api (datos JSON)"
echo ""

# Preguntar si iniciar automáticamente
read -p "¿Quieres iniciar el dashboard ahora? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🚀 Iniciando dashboard..."
    docker-compose up -d
    
    echo ""
    echo "✅ Dashboard iniciado correctamente"
    echo "🌐 Disponible en: http://localhost:8080"
    
    # Esperar un poco y mostrar estado
    sleep 3
    docker-compose ps
fi