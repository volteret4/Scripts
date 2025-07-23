#!/bin/bash
# setup_notifications.sh
# Script para configurar el servicio de notificaciones

echo "🔔 Configurando servicio de notificaciones de artistas..."

# Obtener directorio actual
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"

# Verificar que existe el archivo de notificaciones
if [ ! -f "$PROJECT_DIR/notifications.py" ]; then
    echo "❌ Error: No se encuentra notifications.py en $PROJECT_DIR"
    exit 1
fi

# Verificar que existe la base de datos
if [ ! -f "$PROJECT_DIR/artist_tracker.db" ]; then
    echo "⚠️  Advertencia: No se encuentra artist_tracker.db"
    echo "   Asegúrate de ejecutar bot.py primero para crear la base de datos"
fi

# Función para ejecutar las notificaciones manualmente
if [ "$1" = "run" ]; then
    echo "🚀 Ejecutando servicio de notificaciones..."
    cd "$PROJECT_DIR"
    python3 notifications.py
    exit 0
fi

# Función para probar las notificaciones
if [ "$1" = "test" ]; then
    echo "🧪 Probando servicio de notificaciones (1 minuto)..."
    cd "$PROJECT_DIR"
    timeout 60 python3 notifications.py
    exit 0
fi

# Función para instalar como servicio systemd
if [ "$1" = "install" ]; then
    echo "📦 Instalando como servicio systemd..."

    # Verificar que se ejecuta como root
    if [ "$EUID" -ne 0 ]; then
        echo "❌ Error: Debes ejecutar 'sudo $0 install' para instalar el servicio"
        exit 1
    fi

    # Obtener usuario actual (no root)
    ACTUAL_USER=$(logname 2>/dev/null || echo $SUDO_USER)

    if [ -z "$ACTUAL_USER" ]; then
        echo "❌ Error: No se pudo determinar el usuario actual"
        exit 1
    fi

    # Crear archivo de servicio
    cat > /etc/systemd/system/artist-notifications.service << EOF
[Unit]
Description=Artist Concert Notifications Service
After=network.target

[Service]
Type=simple
User=$ACTUAL_USER
WorkingDirectory=$PROJECT_DIR
Environment=TELEGRAM_BOT_CONCIERTOS=\${TELEGRAM_BOT_CONCIERTOS}
Environment=TICKETMASTER_API_KEY=\${TICKETMASTER_API_KEY}
Environment=SPOTIFY_CLIENT_ID=\${SPOTIFY_CLIENT_ID}
Environment=SPOTIFY_CLIENT_SECRET=\${SPOTIFY_CLIENT_SECRET}
Environment=SETLISTFM_API_KEY=\${SETLISTFM_API_KEY}
Environment=DB_PATH=$PROJECT_DIR/artist_tracker.db
ExecStart=/usr/bin/python3 $PROJECT_DIR/notifications.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    # Recargar systemd
    systemctl daemon-reload

    # Habilitar el servicio
    systemctl enable artist-notifications.service

    echo "✅ Servicio instalado correctamente"
    echo ""
    echo "📋 Comandos útiles:"
    echo "   sudo systemctl start artist-notifications    # Iniciar servicio"
    echo "   sudo systemctl stop artist-notifications     # Detener servicio"
    echo "   sudo systemctl status artist-notifications   # Ver estado"
    echo "   sudo journalctl -u artist-notifications -f   # Ver logs en tiempo real"
    echo ""
    echo "⚠️  Recuerda configurar las variables de entorno en /etc/environment o ~/.bashrc"

    exit 0
fi

# Función para desinstalar el servicio
if [ "$1" = "uninstall" ]; then
    echo "🗑️  Desinstalando servicio systemd..."

    if [ "$EUID" -ne 0 ]; then
        echo "❌ Error: Debes ejecutar 'sudo $0 uninstall' para desinstalar el servicio"
        exit 1
    fi

    # Detener y deshabilitar servicio
    systemctl stop artist-notifications.service 2>/dev/null
    systemctl disable artist-notifications.service 2>/dev/null

    # Eliminar archivo de servicio
    rm -f /etc/systemd/system/artist-notifications.service

    # Recargar systemd
    systemctl daemon-reload

    echo "✅ Servicio desinstalado correctamente"
    exit 0
fi

# Mostrar ayuda por defecto
echo "📖 Uso: $0 [comando]"
echo ""
echo "Comandos disponibles:"
echo "   run        - Ejecutar servicio de notificaciones manualmente"
echo "   test       - Probar servicio por 1 minuto"
echo "   install    - Instalar como servicio systemd (requiere sudo)"
echo "   uninstall  - Desinstalar servicio systemd (requiere sudo)"
echo ""
echo "Ejemplos:"
echo "   $0 run                    # Ejecutar manualmente"
echo "   $0 test                   # Probar por 1 minuto"
echo "   sudo $0 install           # Instalar servicio"
echo "   sudo systemctl start artist-notifications  # Iniciar servicio"
echo ""
echo "📁 Directorio del proyecto: $PROJECT_DIR"

# Verificar variables de entorno importantes
echo ""
echo "🔧 Variables de entorno:"
if [ -n "$TELEGRAM_BOT_CONCIERTOS" ]; then
    echo "   ✅ TELEGRAM_BOT_CONCIERTOS configurado"
else
    echo "   ❌ TELEGRAM_BOT_CONCIERTOS no configurado"
fi

if [ -n "$TICKETMASTER_API_KEY" ]; then
    echo "   ✅ TICKETMASTER_API_KEY configurado"
else
    echo "   ⚠️  TICKETMASTER_API_KEY no configurado"
fi

if [ -n "$SPOTIFY_CLIENT_ID" ]; then
    echo "   ✅ SPOTIFY_CLIENT_ID configurado"
else
    echo "   ⚠️  SPOTIFY_CLIENT_ID no configurado"
fi

if [ -n "$SETLISTFM_API_KEY" ]; then
    echo "   ✅ SETLISTFM_API_KEY configurado"
else
    echo "   ⚠️  SETLISTFM_API_KEY no configurado"
fi
