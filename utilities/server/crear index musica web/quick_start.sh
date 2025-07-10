#!/bin/bash
# Quick Start - Music Web Explorer
# Script para inicio rápido del sistema

# Colores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# Variables globales
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config.ini"

echo -e "${PURPLE}🎵 Music Web Explorer - Quick Start${NC}"
echo "===================================="
echo -e "${CYAN}Directorio: $SCRIPT_DIR${NC}"
echo

# Función para mostrar mensajes
show_step() {
    echo -e "${BLUE}[PASO $1]${NC} $2"
}

show_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

show_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

show_error() {
    echo -e "${RED}❌ $1${NC}"
}

show_info() {
    echo -e "${CYAN}ℹ️  $1${NC}"
}

# Función para mostrar spinner
show_spinner() {
    local pid=$1
    local delay=0.1
    local spinstr='|/-\'
    while [ "$(ps a | awk '{print $1}' | grep $pid)" ]; do
        local temp=${spinstr#?}
        printf " [%c]  " "$spinstr"
        local spinstr=$temp${spinstr%"$temp"}
        sleep $delay
        printf "\b\b\b\b\b\b"
    done
    printf "    \b\b\b\b"
}

# Verificar prerrequisitos
check_prerequisites() {
    local errors=0
    
    show_step "1" "Verificando prerrequisitos..."
    
    # Verificar que estamos en el directorio correcto
    if [ ! -f "app.py" ] || [ ! -f "$CONFIG_FILE" ]; then
        show_error "No estás en el directorio correcto del proyecto"
        echo "   Archivos requeridos: app.py, config.ini"
        echo "   Directorio actual: $SCRIPT_DIR"
        return 1
    fi
    
    # Verificar Python3
    if ! command -v python3 &> /dev/null; then
        show_error "python3 no está instalado"
        errors=$((errors + 1))
    else
        PYTHON_VERSION=$(python3 --version 2>&1)
        show_success "Python disponible: $PYTHON_VERSION"
    fi
    
    # Verificar pip3
    if ! command -v pip3 &> /dev/null; then
        show_warning "pip3 no encontrado"
        show_info "Instalar con: sudo apt install python3-pip"
        errors=$((errors + 1))
    fi
    
    # Verificar Flask
    if python3 -c "import flask" 2>/dev/null; then
        FLASK_VERSION=$(python3 -c "import flask; print(flask.__version__)" 2>/dev/null)
        show_success "Flask disponible: v$FLASK_VERSION"
    else
        show_warning "Flask no encontrado"
        show_info "Se instalará automáticamente si es necesario"
    fi
    
    return $errors
}

# Verificar configuración
check_configuration() {
    show_step "2" "Verificando configuración..."
    
    if ! python3 -c "
import configparser
import os
import sys

try:
    c = configparser.ConfigParser()
    c.read('$CONFIG_FILE')
    
    # Verificar base de datos
    db_path = c.get('database', 'path')
    if not os.path.exists(db_path):
        print('ERROR: Base de datos no encontrada:', db_path)
        sys.exit(1)
    
    # Verificar directorio de música
    music_path = c.get('music', 'root_path')
    if not os.path.exists(music_path):
        print('WARNING: Directorio de música no encontrado:', music_path)
    
    # Mostrar estadísticas básicas
    import sqlite3
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute(\"SELECT COUNT(*) FROM artists WHERE origen = 'local'\")
    artists = cursor.fetchone()[0]
    
    cursor.execute(\"SELECT COUNT(*) FROM albums WHERE origen = 'local'\")
    albums = cursor.fetchone()[0]
    
    cursor.execute(\"SELECT COUNT(*) FROM songs WHERE origen = 'local'\")
    songs = cursor.fetchone()[0]
    
    conn.close()
    
    print(f'STATS: {artists} artistas, {albums} álbumes, {songs} canciones')
    
except Exception as e:
    print('ERROR:', str(e))
    sys.exit(1)
" 2>/dev/null; then
        show_error "Problema con la configuración"
        echo "   Revisa tu archivo config.ini"
        return 1
    else
        # Capturar y mostrar estadísticas
        STATS=$(python3 -c "
import configparser, os, sqlite3
c = configparser.ConfigParser()
c.read('$CONFIG_FILE')
db_path = c.get('database', 'path')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute(\"SELECT COUNT(*) FROM artists WHERE origen = 'local'\")
artists = cursor.fetchone()[0]
cursor.execute(\"SELECT COUNT(*) FROM albums WHERE origen = 'local'\")
albums = cursor.fetchone()[0]
cursor.execute(\"SELECT COUNT(*) FROM songs WHERE origen = 'local'\")
songs = cursor.fetchone()[0]
conn.close()
print(f'{artists} artistas, {albums} álbumes, {songs} canciones')
" 2>/dev/null)
        
        show_success "Configuración OK - $STATS"
        return 0
    fi
}

# Instalar dependencias faltantes
install_dependencies() {
    show_step "3" "Verificando dependencias..."
    
    if ! python3 -c "import flask" 2>/dev/null; then
        show_warning "Flask no encontrado, instalando..."
        if pip3 install Flask --user; then
            show_success "Flask instalado correctamente"
        else
            show_error "Error instalando Flask"
            return 1
        fi
    fi
    
    if [ -f "requirements.txt" ]; then
        show_info "Verificando requirements.txt..."
        pip3 install -r requirements.txt --user --quiet
        show_success "Dependencias verificadas"
    fi
    
    return 0
}

# Probar conexión a base de datos con detalles
test_database() {
    show_info "Probando base de datos..."
    
    DB_INFO=$(python3 music_manager.py stats 2>/dev/null | head -10)
    if [ $? -eq 0 ]; then
        show_success "Base de datos accesible"
        echo "$DB_INFO" | sed 's/^/    /' | head -5
    else
        show_error "Problema accediendo a la base de datos"
        return 1
    fi
    
    return 0
}

# Verificar servicios del sistema
check_system_status() {
    show_info "Verificando estado del sistema..."
    
    # Verificar si hay servidor Flask ejecutándose
    if pgrep -f "python3.*app.py" > /dev/null; then
        FLASK_PID=$(pgrep -f "python3.*app.py")
        show_info "Servidor Flask ya ejecutándose (PID: $FLASK_PID)"
    fi
    
    # Verificar servicio systemd si existe
    if systemctl list-unit-files | grep -q "music-web.service"; then
        if systemctl is-active --quiet music-web; then
            show_info "Servicio systemd music-web activo"
        else
            show_info "Servicio systemd music-web disponible pero inactivo"
        fi
    fi
    
    # Verificar conectividad Tailscale
    if command -v tailscale &> /dev/null; then
        if ping -c 1 -W 2 100.90.91.96 >/dev/null 2>&1; then
            show_success "Tailscale: 100.90.91.96 alcanzable"
        else
            show_warning "Tailscale: 100.90.91.96 no alcanzable"
        fi
    fi
    
    # Verificar servidor web remoto
    WEB_SERVER=$(python3 -c "
import configparser
c = configparser.ConfigParser()
c.read('$CONFIG_FILE')
print(c.get('sync', 'web_server', fallback='192.168.1.180'))
" 2>/dev/null || echo "192.168.1.180")
    
    if ping -c 1 -W 2 "$WEB_SERVER" >/dev/null 2>&1; then
        show_success "Servidor web $WEB_SERVER alcanzable"
    else
        show_warning "Servidor web $WEB_SERVER no alcanzable"
    fi
}

# Menú principal mejorado
show_main_menu() {
    echo
    echo -e "${PURPLE}¿Qué quieres hacer?${NC}"
    echo "════════════════════"
    echo -e "${GREEN} 1)${NC} 🚀 Iniciar servidor Flask (desarrollo)"
    echo -e "${GREEN} 2)${NC} 📦 Hacer build local (generar archivos)"
    echo -e "${GREEN} 3)${NC} 🔄 Sincronizar a servidor web"
    echo -e "${GREEN} 4)${NC} 🧪 Probar sincronización (dry-run)"
    echo -e "${GREEN} 5)${NC} ⚙️  Setup completo automático"
    echo
    echo -e "${BLUE} 6)${NC} 🔍 Ver estadísticas detalladas"
    echo -e "${BLUE} 7)${NC} 🔎 Buscar en la colección"
    echo -e "${BLUE} 8)${NC} 🩺 Verificar integridad de BD"
    echo -e "${BLUE} 9)${NC} 📊 Generar reporte HTML"
    echo
    echo -e "${YELLOW}10)${NC} ⏰ Configurar cron automático"
    echo -e "${YELLOW}11)${NC} 📋 Ver logs del sistema"
    echo -e "${YELLOW}12)${NC} 🏥 Health check completo"
    echo
    echo -e "${CYAN} 0)${NC} 👋 Salir"
    echo
}

# Ejecutar servidor Flask con información detallada
start_flask_server() {
    show_step "4" "Iniciando servidor Flask..."
    
    # Verificar puerto disponible
    PORT=$(python3 -c "
import configparser
c = configparser.ConfigParser()
c.read('$CONFIG_FILE')
print(c.getint('web', 'port', fallback=5157))
" 2>/dev/null || echo "5157")
    
    if netstat -tuln 2>/dev/null | grep -q ":$PORT "; then
        show_warning "Puerto $PORT ya está en uso"
        show_info "¿Quieres intentar detener el proceso existente? (y/n)"
        read -r response
        if [[ $response =~ ^[Yy]$ ]]; then
            pkill -f "python3.*app.py" 2>/dev/null || true
            sleep 2
        fi
    fi
    
    echo
    show_info "Servidor iniciando en puerto $PORT..."
    show_info "URLs disponibles:"
    echo "   • http://localhost:$PORT/ - Interfaz web"
    echo "   • http://localhost:$PORT/api/stats - API de estadísticas"
    echo "   • http://localhost:$PORT/api/search/artists?q=<búsqueda> - Buscar artistas"
    echo
    show_info "Presiona Ctrl+C para detener el servidor"
    echo
    
    python3 app.py
}

# Build local mejorado
do_local_build() {
    show_step "4" "Generando build local..."
    
    if python3 deploy_music_web.py; then
        show_success "Build completado"
        
        if [ -d "./build" ]; then
            echo
            show_info "Archivos generados en ./build/:"
            ls -la ./build/ | sed 's/^/    /'
            echo
            show_info "Siguiente paso: sincronizar a servidor web (opción 3)"
        fi
    else
        show_error "Error en el build"
        return 1
    fi
}

# Sincronización con más información
do_sync() {
    local dry_run=$1
    local action_text="Sincronizando"
    
    if [ "$dry_run" = "true" ]; then
        action_text="Probando sincronización (dry-run)"
    fi
    
    show_step "4" "$action_text a servidor web..."
    
    # Verificar que existe el build
    if [ ! -d "./build" ]; then
        show_warning "No existe build local, generando primero..."
        if ! python3 deploy_music_web.py; then
            show_error "Error generando build"
            return 1
        fi
    fi
    
    # Ejecutar sincronización
    if [ "$dry_run" = "true" ]; then
        python3 sync_to_webserver.py --dry-run
    else
        python3 sync_to_webserver.py
    fi
    
    if [ $? -eq 0 ]; then
        if [ "$dry_run" != "true" ]; then
            WEB_SERVER=$(python3 -c "
import configparser
c = configparser.ConfigParser()
c.read('$CONFIG_FILE')
print(c.get('sync', 'web_server', fallback='192.168.1.180'))
" 2>/dev/null || echo "192.168.1.180")
            
            show_success "Sincronización completada"
            echo
            show_info "URLs disponibles:"
            echo "   • http://$WEB_SERVER/musica/ - Web principal"
            echo "   • http://$WEB_SERVER/musica/health.html - Health check"
            echo
            
            # Verificar que responde
            show_info "Verificando disponibilidad..."
            if curl -s -f "http://$WEB_SERVER/musica/" >/dev/null 2>&1; then
                show_success "Web verificada y disponible"
            else
                show_warning "Web sincronizada pero no responde (verifica nginx)"
            fi
        fi
    else
        show_error "Error en la sincronización"
        return 1
    fi
}

# Setup automático completo
do_complete_setup() {
    show_step "4" "Setup completo automático..."
    
    echo
    show_info "Este proceso hará:"
    echo "   1. Build local de archivos"
    echo "   2. Configurar servicio systemd" 
    echo "   3. Sincronizar a servidor web"
    echo "   4. Configurar cron automático"
    echo
    
    read -p "¿Continuar? (y/n): " -r
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        show_info "Setup cancelado"
        return 0
    fi
    
    # Build
    show_info "Paso 1/4: Build local..."
    if ! python3 deploy_music_web.py; then
        show_error "Error en build local"
        return 1
    fi
    
    # Servicio systemd
    show_info "Paso 2/4: Configurando servicio systemd..."
    if [ -f "./build/music-web.service" ]; then
        echo "   sudo cp ./build/music-web.service /etc/systemd/system/"
        echo "   sudo systemctl daemon-reload"
        echo "   sudo systemctl enable music-web"
        echo "   sudo systemctl start music-web"
        
        read -p "¿Ejecutar comandos de systemd ahora? (requiere sudo) (y/n): " -r
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            sudo cp ./build/music-web.service /etc/systemd/system/ && \
            sudo systemctl daemon-reload && \
            sudo systemctl enable music-web && \
            sudo systemctl start music-web
            
            if systemctl is-active --quiet music-web; then
                show_success "Servicio systemd configurado y activo"
            else
                show_warning "Problema con el servicio systemd"
            fi
        fi
    fi
    
    # Sincronización
    show_info "Paso 3/4: Sincronización..."
    do_sync false
    
    # Cron
    show_info "Paso 4/4: Configurando cron..."
    configure_cron_interactive
    
    show_success "Setup completo terminado"
}

# Búsqueda interactiva
do_interactive_search() {
    show_step "4" "Búsqueda interactiva..."
    
    echo
    read -p "Ingresa término de búsqueda: " search_term
    
    if [ -z "$search_term" ]; then
        show_warning "Término de búsqueda vacío"
        return 1
    fi
    
    echo
    read -p "Tipo de búsqueda (artists/albums/songs/all) [all]: " search_type
    search_type=${search_type:-all}
    
    show_info "Buscando '$search_term' en $search_type..."
    python3 music_manager.py search "$search_term" --type "$search_type"
}

# Configuración de cron interactiva
configure_cron_interactive() {
    show_info "Configurando cron automático..."
    
    CRON_SCRIPT="$SCRIPT_DIR/auto_sync.sh"
    chmod +x "$CRON_SCRIPT" 2>/dev/null
    
    echo
    echo "Opciones de frecuencia:"
    echo "1) Cada 30 minutos"
    echo "2) Cada hora"  
    echo "3) Cada 2 horas"
    echo "4) Personalizado"
    echo "0) No configurar"
    echo
    
    read -p "Selecciona frecuencia (0-4): " freq_option
    
    case $freq_option in
        1)
            CRON_EXPR="*/30 * * * *"
            CRON_DESC="cada 30 minutos"
            ;;
        2)
            CRON_EXPR="0 * * * *"
            CRON_DESC="cada hora"
            ;;
        3)
            CRON_EXPR="0 */2 * * *" 
            CRON_DESC="cada 2 horas"
            ;;
        4)
            read -p "Ingresa expresión cron personalizada: " CRON_EXPR
            CRON_DESC="personalizada: $CRON_EXPR"
            ;;
        0)
            show_info "Configuración de cron cancelada"
            return 0
            ;;
        *)
            show_error "Opción no válida"
            return 1
            ;;
    esac
    
    echo
    show_info "Se añadirá a cron: $CRON_EXPR $CRON_SCRIPT"
    show_info "Frecuencia: $CRON_DESC"
    
    read -p "¿Confirmar? (y/n): " -r
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        (crontab -l 2>/dev/null | grep -v "$CRON_SCRIPT"; echo "$CRON_EXPR $CRON_SCRIPT") | crontab -
        show_success "Cron configurado $CRON_DESC"
        
        # Mostrar cron actual
        show_info "Cron actual:"
        crontab -l | grep -E "(music|sync)" | sed 's/^/    /' || echo "    (sin entradas relacionadas)"
    fi
}

# Ver logs del sistema
show_system_logs() {
    show_step "4" "Mostrando logs del sistema..."
    
    echo
    echo "Selecciona log a ver:"
    echo "1) Logs de sincronización"
    echo "2) Logs de Flask (systemd)"
    echo "3) Logs de cron"
    echo "4) Todos los logs"
    echo "0) Volver"
    echo
    
    read -p "Selecciona opción (0-4): " log_option
    
    case $log_option in
        1)
            if [ -f "/tmp/music_web_sync.log" ]; then
                show_info "Últimas 50 líneas de logs de sincronización:"
                tail -50 /tmp/music_web_sync.log
            else
                show_warning "No se encontraron logs de sincronización"
            fi
            ;;
        2)
            if systemctl list-unit-files | grep -q "music-web.service"; then
                show_info "Logs del servicio music-web:"
                journalctl -u music-web --no-pager -n 50
            else
                show_warning "Servicio music-web no configurado"
            fi
            ;;
        3)
            show_info "Logs de cron (últimas 20 líneas):"
            grep -i "music\|sync" /var/log/syslog 2>/dev/null | tail -20 || \
            grep -i "music\|sync" /var/log/cron 2>/dev/null | tail -20 || \
            show_warning "No se encontraron logs de cron"
            ;;
        4)
            show_info "=== Logs de Sincronización ==="
            [ -f "/tmp/music_web_sync.log" ] && tail -20 /tmp/music_web_sync.log
            echo
            show_info "=== Logs de Flask ==="
            systemctl list-unit-files | grep -q "music-web.service" && journalctl -u music-web --no-pager -n 10
            echo
            show_info "=== Logs de Cron ==="
            grep -i "music\|sync" /var/log/syslog 2>/dev/null | tail -10
            ;;
        0)
            return 0
            ;;
        *)
            show_error "Opción no válida"
            ;;
    esac
    
    echo
    read -p "Presiona Enter para continuar..."
}

# Health check completo
do_health_check() {
    show_step "4" "Health check completo..."
    
    echo
    show_info "=== HEALTH CHECK COMPLETO ==="
    echo
    
    # 1. Archivos locales
    show_info "1. Archivos locales:"
    local required_files=("app.py" "config.ini" "templates/index.html" "music_manager.py")
    for file in "${required_files[@]}"; do
        if [ -f "$file" ]; then
            echo "   ✅ $file"
        else
            echo "   ❌ $file (faltante)"
        fi
    done
    
    # 2. Base de datos
    echo
    show_info "2. Base de datos:"
    if python3 -c "
import configparser, sqlite3
c = configparser.ConfigParser()
c.read('$CONFIG_FILE')
db_path = c.get('database', 'path')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute('PRAGMA integrity_check')
result = cursor.fetchone()[0] 
print('   ✅ Integridad:', result if result == 'ok' else '❌ ' + result)
conn.close()
" 2>/dev/null; then
        :
    else
        echo "   ❌ Error accediendo a la base de datos"
    fi
    
    # 3. Servicios
    echo
    show_info "3. Servicios:"
    if pgrep -f "python3.*app.py" > /dev/null; then
        echo "   ✅ Flask ejecutándose"
    else
        echo "   ⚠️  Flask no ejecutándose"
    fi
    
    if systemctl list-unit-files | grep -q "music-web.service"; then
        if systemctl is-active --quiet music-web; then
            echo "   ✅ Servicio systemd activo"
        else
            echo "   ⚠️  Servicio systemd inactivo"
        fi
    else
        echo "   ⚠️  Servicio systemd no configurado"
    fi
    
    # 4. Conectividad
    echo
    show_info "4. Conectividad:"
    
    # Tailscale
    if command -v tailscale &> /dev/null; then
        if ping -c 1 -W 2 100.90.91.96 >/dev/null 2>&1; then
            echo "   ✅ 100.90.91.96 alcanzable"
        else
            echo "   ❌ 100.90.91.96 no alcanzable"
        fi
    else
        echo "   ⚠️  Tailscale no instalado"
    fi
    
    # Servidor web
    WEB_SERVER=$(python3 -c "
import configparser
c = configparser.ConfigParser()
c.read('$CONFIG_FILE')
print(c.get('sync', 'web_server', fallback='192.168.1.180'))
" 2>/dev/null || echo "192.168.1.180")
    
    if ping -c 1 -W 2 "$WEB_SERVER" >/dev/null 2>&1; then
        echo "   ✅ $WEB_SERVER alcanzable"
        
        # Verificar web
        if curl -s -f "http://$WEB_SERVER/musica/" >/dev/null 2>&1; then
            echo "   ✅ Web respondiendo"
        else
            echo "   ⚠️  Web no responde"
        fi
    else
        echo "   ❌ $WEB_SERVER no alcanzable"
    fi
    
    # 5. Archivos de build
    echo
    show_info "5. Build:"
    if [ -d "./build" ]; then
        BUILD_COUNT=$(ls -1 ./build/ 2>/dev/null | wc -l)
        echo "   ✅ Directorio build existe ($BUILD_COUNT archivos)"
    else
        echo "   ⚠️  Directorio build no existe"
    fi
    
    echo
    show_success "Health check completado"
    echo
    read -p "Presiona Enter para continuar..."
}

# Función principal mejorada
main() {
    cd "$SCRIPT_DIR"
    
    # Verificaciones iniciales
    if ! check_prerequisites; then
        show_error "Prerrequisitos no cumplidos"
        exit 1
    fi
    
    if ! check_configuration; then
        show_error "Problema con la configuración"
        exit 1
    fi
    
    if ! install_dependencies; then
        show_error "Error instalando dependencias"
        exit 1
    fi
    
    if ! test_database; then
        show_error "Problema con la base de datos"
        exit 1
    fi
    
    check_system_status
    
    # Menú principal
    while true; do
        show_main_menu
        read -p "Selecciona una opción (0-12): " option
        
        case $option in
            1) start_flask_server ;;
            2) do_local_build ;;
            3) do_sync false ;;
            4) do_sync true ;;
            5) do_complete_setup ;;
            6) python3 music_manager.py stats ;;
            7) do_interactive_search ;;
            8) python3 music_manager.py check ;;
            9) 
                read -p "Nombre del archivo HTML [web_report.html]: " report_name
                report_name=${report_name:-web_report.html}
                python3 music_manager.py report --output "$report_name"
                show_success "Reporte generado: $report_name"
                ;;
            10) configure_cron_interactive ;;
            11) show_system_logs ;;
            12) do_health_check ;;
            0)
                echo
                show_success "👋 ¡Hasta luego!"
                echo
                show_info "Comandos útiles para recordar:"
                echo "  • ./quick_start.sh                        # Este menú"
                echo "  • python3 app.py                         # Servidor Flask"
                echo "  • python3 sync_to_webserver.py           # Sincronizar"
                echo "  • python3 music_manager.py stats         # Estadísticas"
                echo "  • tail -f /tmp/music_web_sync.log        # Ver logs sync"
                echo
                exit 0
                ;;
            *)
                show_error "Opción no válida"
                sleep 1
                ;;
        esac
        
        if [ "$option" != "1" ]; then
            echo
            read -p "Presiona Enter para volver al menú principal..."
            clear
            echo -e "${PURPLE}🎵 Music Web Explorer - Quick Start${NC}"
            echo "===================================="
            echo
        fi
    done
}

# Manejo de señales
trap 'echo; show_warning "Proceso interrumpido"; exit 130' INT
trap 'echo; show_error "Proceso terminado"; exit 143' TERM

# Ejecutar función principal
main "$@" $1${NC}"
}

# Verificar que estamos en el directorio correcto
if [ ! -f "app.py" ] || [ ! -f "config.ini" ]; then
    show_error "No estás en el directorio correcto del proyecto"
    echo "Asegúrate de estar en el directorio donde están app.py y config.ini"
    exit 1
fi

# Paso 1: Verificar configuración
show_step "1" "Verificando configuración..."

if python3 -c "
import configparser
import os
c = configparser.ConfigParser()
c.read('config.ini')
db_path = c.get('database', 'path')
music_path = c.get('music', 'root_path')
if not os.path.exists(db_path):
    print('ERROR: Base de datos no encontrada:', db_path)
    exit(1)
if not os.path.exists(music_path):
    print('WARNING: Directorio de música no encontrado:', music_path)
print('Configuración OK')
" 2>/dev/null; then
    show_success "Configuración verificada"
else
    show_error "Problema con la configuración"
    echo "Revisa tu archivo config.ini"
    exit 1
fi

# Paso 2: Verificar dependencias
show_step "2" "Verificando dependencias..."

if python3 -c "import flask" 2>/dev/null; then
    show_success "Flask disponible"
else
    show_warning "Flask no encontrado, instalando..."
    pip3 install Flask --user
fi

# Paso 3: Probar base de datos
show_step "3" "Probando conexión a base de datos..."

STATS=$(python3 music_manager.py stats 2>/dev/null | grep -E "(Artistas|Álbumes|Canciones)" | head -3)
if [ $? -eq 0 ]; then
    show_success "Base de datos accesible"
    echo "$STATS" | sed 's/^/    /'
else
    show_error "Problema accediendo a la base de datos"
    exit 1
fi

# Paso 4: Opciones de inicio
echo
echo "¿Qué quieres hacer?"
echo "1) Iniciar servidor Flask (desarrollo)"
echo "2) Hacer deployment completo"
echo "3) Solo probar la API"
echo "4) Ver estadísticas detalladas"
echo "5) Buscar en la colección"
echo "6) Sincronizar a servidor web (192.168.1.180)"
echo "7) Probar sincronización (dry-run)"
echo "8) Configurar cron automático"
echo "0) Salir"
echo

read -p "Selecciona una opción (0-8): " option

case $option in
    1)
        show_step "4" "Iniciando servidor Flask..."
        echo "Servidor disponible en: http://localhost:5157"
        echo "Presiona Ctrl+C para detener"
        echo
        python3 app.py
        ;;
    2)
        show_step "4" "Ejecutando deployment completo..."
        python3 deploy_music_web.py
        show_success "Deployment completado"
        echo "Revisa README_DEPLOYMENT.md para los siguientes pasos"
        ;;
    3)
        show_step "4" "Probando API..."
        echo "Iniciando servidor en segundo plano..."
        python3 app.py &
        SERVER_PID=$!
        sleep 3
        
        echo "Probando endpoints:"
        curl -s http://localhost:5157/api/stats | python3 -m json.tool 2>/dev/null || echo "API no responde"
        
        kill $SERVER_PID 2>/dev/null
        show_success "Prueba completada"
        ;;
    4)
        show_step "4" "Mostrando estadísticas detalladas..."
        python3 music_manager.py stats
        ;;
    5)
        echo
        read -p "Ingresa término de búsqueda: " search_term
        if [ ! -z "$search_term" ]; then
            show_step "4" "Buscando '$search_term'..."
            python3 music_manager.py search "$search_term"
        fi
        ;;
    6)
        show_step "4" "Sincronizando a servidor web..."
        python3 sync_to_webserver.py
        show_success "Sincronización completada"
        echo "Web disponible en: http://192.168.1.180/musica/"
        ;;
    7)
        show_step "4" "Probando sincronización (dry-run)..."
        python3 sync_to_webserver.py --dry-run
        show_success "Dry-run completado"
        ;;
    8)
        show_step "4" "Configurando cron automático..."
        CRON_SCRIPT="$(pwd)/auto_sync.sh"
        chmod +x auto_sync.sh
        
        echo "Añade esta línea a tu crontab (crontab -e):"
        echo "# Sincronizar web cada 30 minutos"
        echo "*/30 * * * * $CRON_SCRIPT"
        echo
        echo "O para sincronizar cada hora:"
        echo "0 * * * * $CRON_SCRIPT"
        
        read -p "¿Quieres que lo añada automáticamente cada hora? (y/n): " add_cron
        if [[ $add_cron =~ ^[Yy]$ ]]; then
            (crontab -l 2>/dev/null; echo "0 * * * * $CRON_SCRIPT") | crontab -
            show_success "Cron configurado para ejecutarse cada hora"
        fi
        ;;
    0)
        echo "👋 ¡Hasta luego!"
        exit 0
        ;;
    *)
        show_error "Opción no válida"
        exit 1
        ;;
esac

echo
show_success "Operación completada"
echo
echo "Comandos útiles:"
echo "  • python3 app.py                           # Iniciar servidor Flask"
echo "  • python3 sync_to_webserver.py            # Sincronizar a web server"
echo "  • python3 sync_to_webserver.py --dry-run  # Probar sincronización"
echo "  • python3 music_manager.py stats          # Ver estadísticas"
echo "  • python3 music_manager.py search <término>  # Buscar"
echo "  • ./auto_sync.sh                          # Sync manual"
echo "  • tail -f /tmp/music_web_sync.log         # Ver logs de sync"
echo