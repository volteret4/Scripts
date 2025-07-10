#!/bin/bash
set -e

echo "🎵 Iniciando Music Web Explorer..."

# Crear directorios necesarios
mkdir -p /app/data /app/music /downloads /app/logs /app/static

# Verificar permisos SOLO en directorios de escritura (no :ro)
echo "📁 Configurando permisos..."

# Solo cambiar permisos en directorios de escritura
if [ -w "/downloads" ]; then
    chown -R dietpi:dietpi /downloads 2>/dev/null || echo "⚠️  No se pudieron cambiar permisos de /downloads"
fi

if [ -w "/app/logs" ]; then
    chown -R dietpi:dietpi /app/logs 2>/dev/null || echo "⚠️  No se pudieron cambiar permisos de /app/logs"
fi

if [ -w "/app/static" ]; then
    chown -R www-data:www-data /app/static 2>/dev/null || echo "⚠️  No se pudieron cambiar permisos de /app/static"
fi

# Verificar base de datos (pero NO cambiar permisos - es solo lectura)
if [ -f "/app/data/musica.sqlite" ]; then
    echo "✅ Base de datos encontrada en /app/data/musica.sqlite"
    # Verificar que sea legible
    if [ -r "/app/data/musica.sqlite" ]; then
        echo "✅ Base de datos es legible"
    else
        echo "❌ Base de datos no es legible"
    fi
else
    echo "⚠️  Base de datos no encontrada en /app/data/musica.sqlite"
    echo "   Asegúrate de montar el volumen con la base de datos"
fi

# Configurar SSH para el usuario dietpi
if [ -d "/home/dietpi/.ssh" ]; then
    echo "🔑 Configuración SSH encontrada para dietpi"
    if [ -w "/home/dietpi/.ssh" ]; then
        chown -R dietpi:dietpi /home/dietpi/.ssh 2>/dev/null || true
        chmod 700 /home/dietpi/.ssh 2>/dev/null || true
        chmod 600 /home/dietpi/.ssh/* 2>/dev/null || true
    fi
    
    # Verificar conectividad SSH (solo si ssh está disponible)
    if command -v ssh >/dev/null 2>&1; then
        if su - dietpi -c "ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no dietpi@pepecono 'echo OK'" 2>/dev/null; then
            echo "✅ Conectividad SSH con pepecono verificada"
        else
            echo "⚠️  No se puede conectar SSH a pepecono"
            echo "   Verifica las claves SSH y la conectividad de red"
        fi
    else
        echo "⚠️  SSH no disponible en el contenedor"
    fi
else
    echo "⚠️  No se encontró configuración SSH para dietpi"
    echo "   Las descargas SSH no funcionarán sin acceso a pepecono"
fi

# Crear página de health check
cat > /app/static/health.html << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>Music Explorer - Health Check</title>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial; text-align: center; margin: 40px; }
        .status { padding: 20px; margin: 20px; border-radius: 10px; }
        .ok { background: #d4edda; color: #155724; }
        .error { background: #f8d7da; color: #721c24; }
    </style>
</head>
<body>
    <h1>🎵 Music Web Explorer</h1>
    <h2>Container Health Check</h2>
    <div class="status ok">✅ Contenedor funcionando</div>
    <p><a href="/">Ir a la aplicación</a></p>
    <div style="margin-top: 20px; font-size: 12px; color: #666;">
        Timestamp: $(date)
    </div>
</body>
</html>
EOF

echo "✅ Configuración inicial completada"
echo "🌐 Acceso web: http://localhost:8447"
echo "🔌 API directa: http://localhost:5157"
echo "📁 Directorio de descargas: /downloads"

# Verificar que supervisord existe antes de ejecutarlo
if [ -f "/usr/bin/supervisord" ] && [ -f "/etc/supervisor/conf.d/supervisord.conf" ]; then
    echo "🚀 Iniciando servicios con supervisor..."
    exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
else
    echo "⚠️  Supervisor no encontrado, iniciando Flask directamente..."
    cd /app
    exec python3 app.py
fi