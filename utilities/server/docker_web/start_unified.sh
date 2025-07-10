#!/bin/bash
# Script de inicio simplificado para Music Web Explorer unificado

set -e

# Colores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}🎵 Music Web Explorer - Inicio Unificado${NC}"
echo "================================================"
echo

# Verificar que estamos en el directorio correcto
if [ ! -f "app.py" ] || [ ! -f "config.ini" ]; then
    echo -e "${RED}❌ Error: No estás en el directorio correcto${NC}"
    echo "   Archivos requeridos: app.py, config.ini"
    exit 1
fi

# Crear directorios necesarios
echo -e "${BLUE}📁 Creando directorios...${NC}"
mkdir -p logs downloads data static

# Verificar configuración
echo -e "${BLUE}🔧 Verificando configuración...${NC}"
if python3 -c "
import configparser
import os
c = configparser.ConfigParser()
c.read('config.ini')

# Verificar base de datos
db_path = c.get('database', 'path')
if not os.path.exists(db_path):
    print('ERROR: Base de datos no encontrada:', db_path)
    exit(1)

# Verificar directorio de música
music_path = c.get('music', 'root_path')
if not os.path.exists(music_path):
    print('WARNING: Directorio de música no encontrado:', music_path)

print('OK: Configuración válida')
" 2>/dev/null; then
    echo -e "${GREEN}✅ Configuración verificada${NC}"
else
    echo -e "${RED}❌ Error en la configuración${NC}"
    exit 1
fi

# Verificar dependencias Python
echo -e "${BLUE}🐍 Verificando dependencias Python...${NC}"
if python3 -c "import flask" 2>/dev/null; then
    echo -e "${GREEN}✅ Flask disponible${NC}"
else
    echo -e "${YELLOW}⚠️  Instalando Flask...${NC}"
    pip3 install Flask --user
fi

# Verificar puerto disponible
PORT=$(python3 -c "
import configparser
c = configparser.ConfigParser()
c.read('config.ini')
print(c.getint('web', 'port', fallback=5157))
" 2>/dev/null || echo "5157")

if netstat -tuln 2>/dev/null | grep -q ":$PORT "; then
    echo -e "${YELLOW}⚠️  Puerto $PORT ya está en uso${NC}"
    echo "¿Quieres detener el proceso existente? (y/n)"
    read -r response
    if [[ $response =~ ^[Yy]$ ]]; then
        pkill -f "python3.*app.py" 2>/dev/null || true
        sleep 2
    fi
fi

# Mostrar información del sistema
echo -e "${BLUE}📊 Información del sistema:${NC}"
DB_STATS=$(python3 -c "
import sqlite3
import configparser
c = configparser.ConfigParser()
c.read('config.ini')
db_path = c.get('database', 'path')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM artists WHERE origen = \"local\"')
artists = cursor.fetchone()[0]
cursor.execute('SELECT COUNT(*) FROM albums WHERE origen = \"local\"')
albums = cursor.fetchone()[0]
cursor.execute('SELECT COUNT(*) FROM songs WHERE origen = \"local\"')
songs = cursor.fetchone()[0]
conn.close()
print(f'{artists} artistas, {albums} álbumes, {songs} canciones')
" 2>/dev/null)

echo "   📁 Colección: $DB_STATS"
echo "   🌐 Puerto: $PORT"
echo "   📥 Descargas: $(pwd)/downloads"
echo "   📋 Logs: $(pwd)/logs"

echo
echo -e "${GREEN}🚀 Iniciando servidor...${NC}"
echo "   • URL principal: http://localhost:$PORT/"
echo "   • Health check: http://localhost:$PORT/static/health.html"
echo "   • Directorio descargas: $(pwd)/downloads"
echo
echo -e "${YELLOW}Presiona Ctrl+C para detener el servidor${NC}"
echo

# Crear health check básico
cat > static/health.html << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>Music Explorer - Health Check</title>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial; text-align: center; margin: 40px; }
        .status { padding: 20px; margin: 20px; border-radius: 10px; background: #d4edda; color: #155724; }
    </style>
</head>
<body>
    <h1>🎵 Music Web Explorer</h1>
    <h2>Health Check</h2>
    <div class="status">✅ Servidor funcionando</div>
    <p><a href="/">Ir a la aplicación</a></p>
</body>
</html>
EOF

# Iniciar aplicación Flask
python3 app.py