#!/bin/bash
# Auto Sync - Script para cron
# Sincroniza automáticamente la web al servidor remoto

# Configuración
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/tmp/music_web_sync.log"
LOCK_FILE="/tmp/music_web_sync.lock"

# Función de logging
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

# Verificar si ya hay otro proceso ejecutándose
if [ -f "$LOCK_FILE" ]; then
    PID=$(cat "$LOCK_FILE")
    if ps -p $PID > /dev/null 2>&1; then
        log_message "ERROR: Otro proceso de sync ya está ejecutándose (PID: $PID)"
        exit 1
    else
        # El proceso ya no existe, eliminar lock file
        rm -f "$LOCK_FILE"
    fi
fi

# Crear lock file
echo $$ > "$LOCK_FILE"

# Función de limpieza
cleanup() {
    rm -f "$LOCK_FILE"
}
trap cleanup EXIT

log_message "INFO: Iniciando sincronización automática"

cd "$SCRIPT_DIR"

# Verificar que estamos en el directorio correcto
if [ ! -f "app.py" ] || [ ! -f "sync_to_webserver.py" ]; then
    log_message "ERROR: No se encontraron archivos necesarios en $SCRIPT_DIR"
    exit 1
fi

# Verificar que el servicio Flask está ejecutándose
if ! pgrep -f "python3.*app.py" > /dev/null; then
    log_message "WARNING: Servicio Flask no está ejecutándose, intentando iniciar..."
    
    # Intentar iniciar el servicio si está configurado como systemd
    if systemctl is-enabled music-web >/dev/null 2>&1; then
        systemctl start music-web
        sleep 5
        
        if systemctl is-active music-web >/dev/null 2>&1; then
            log_message "INFO: Servicio music-web iniciado correctamente"
        else
            log_message "ERROR: No se pudo iniciar el servicio music-web"
            exit 1
        fi
    else
        log_message "WARNING: Servicio systemd no configurado, Flask podría no estar disponible"
    fi
fi

# Verificar que pepecono es alcanzable via Tailscale
if ! ping -c 1 -W 5 100.90.91.96 >/dev/null 2>&1; then
    log_message "ERROR: 100.90.91.96 no es alcanzable"
    exit 1
fi

# Verificar que el servidor web es alcanzable
WEB_SERVER=$(python3 -c "
import configparser
c = configparser.ConfigParser()
c.read('config.ini')
print(c.get('sync', 'web_server', fallback='192.168.1.180'))
" 2>/dev/null || echo "192.168.1.180")

if ! ping -c 1 -W 5 "$WEB_SERVER" >/dev/null 2>&1; then
    log_message "ERROR: Servidor web $WEB_SERVER no es alcanzable"
    exit 1
fi

# Verificar si hay cambios en la base de datos (opcional)
DB_PATH=$(python3 -c "
import configparser
c = configparser.ConfigParser()
c.read('config.ini')
print(c.get('database', 'path'))
" 2>/dev/null)

if [ -f "$DB_PATH" ]; then
    DB_MODIFIED=$(stat -c %Y "$DB_PATH" 2>/dev/null || echo "0")
    LAST_SYNC_FILE="/tmp/last_web_sync"
    
    if [ -f "$LAST_SYNC_FILE" ]; then
        LAST_SYNC=$(cat "$LAST_SYNC_FILE")
    else
        LAST_SYNC="0"
    fi
    
    # Solo sincronizar si la DB ha cambiado (o si es la primera vez)
    if [ "$DB_MODIFIED" -le "$LAST_SYNC" ] && [ "$LAST_SYNC" != "0" ]; then
        log_message "INFO: Base de datos no ha cambiado desde la última sincronización"
        
        # Pero verificar que la web esté disponible
        if curl -s -f "http://$WEB_SERVER/musica/health.html" >/dev/null 2>&1; then
            log_message "INFO: Web está disponible, no es necesario sincronizar"
            exit 0
        else
            log_message "WARNING: Web no disponible, forzando sincronización"
        fi
    fi
fi

# Ejecutar sincronización
log_message "INFO: Ejecutando sincronización web..."

if python3 sync_to_webserver.py >> "$LOG_FILE" 2>&1; then
    log_message "INFO: Sincronización completada exitosamente"
    
    # Actualizar timestamp de última sincronización
    echo "$(date +%s)" > "$LAST_SYNC_FILE"
    
    # Verificar que la web responde
    sleep 5
    if curl -s -f "http://$WEB_SERVER/musica/health.html" >/dev/null 2>&1; then
        log_message "INFO: Web verificada, respondiendo correctamente"
    else
        log_message "WARNING: Web sincronizada pero no responde correctamente"
    fi
    
else
    log_message "ERROR: Falló la sincronización"
    exit 1
fi

# Limpiar logs antiguos (mantener solo últimos 7 días)
find /tmp -name "music_web_sync.log*" -mtime +7 -delete 2>/dev/null || true

log_message "INFO: Proceso de sincronización automática completado"