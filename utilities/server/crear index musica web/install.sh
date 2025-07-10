#!/bin/bash
# Script de instalación automática para Music Web Explorer

set -e  # Salir si hay algún error

echo "=== Music Web Explorer - Instalación Automática ==="
echo "Fecha: $(date)"
echo

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Función para mostrar mensajes
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

# Verificar si estamos ejecutando como root para algunas operaciones
check_root() {
    if [[ $EUID -eq 0 ]]; then
        show_warning "Ejecutándose como root. Algunas operaciones pueden requerir permisos específicos."
    fi
}

# Verificar dependencias del sistema
check_dependencies() {
    show_info "Verificando dependencias del sistema..."
    
    # Python3
    if ! command -v python3 &> /dev/null; then
        show_error "python3 no está instalado"
        exit 1
    fi
    show_success "Python3 encontrado: $(python3 --version)"
    
    # pip3
    if ! command -v pip3 &> /dev/null; then
        show_warning "pip3 no encontrado, instalando..."
        sudo apt update
        sudo apt install -y python3-pip
    fi
    show_success "pip3 disponible"
    
    # sqlite3
    if ! command -v sqlite3 &> /dev/null; then
        show_warning "sqlite3 no encontrado, instalando..."
        sudo apt install -y sqlite3
    fi
    show_success "sqlite3 disponible"
}

# Instalar dependencias Python
install_python_deps() {
    show_info "Instalando dependencias Python..."
    
    if [ -f "requirements.txt" ]; then
        pip3 install -r requirements.txt --user
        show_success "Dependencias Python instaladas"
    else
        show_warning "requirements.txt no encontrado, instalando manualmente..."
        pip3 install Flask --user
        show_success "Flask instalado"
    fi
}

# Verificar archivos necesarios
check_files() {
    show_info "Verificando archivos necesarios..."
    
    required_files=("app.py" "config.ini" "templates/index.html" "deploy_music_web.py")
    
    for file in "${required_files[@]}"; do
        if [ ! -f "$file" ]; then
            show_error "Archivo requerido no encontrado: $file"
            exit 1
        fi
    done
    
    show_success "Todos los archivos necesarios están presentes"
}

# Verificar configuración
check_config() {
    show_info "Verificando configuración..."
    
    if [ ! -f "config.ini" ]; then
        show_error "config.ini no encontrado"
        exit 1
    fi
    
    # Verificar que la base de datos existe
    DB_PATH=$(python3 -c "import configparser; c=configparser.ConfigParser(); c.read('config.ini'); print(c.get('database', 'path'))")
    
    if [ ! -f "$DB_PATH" ]; then
        show_error "Base de datos no encontrada en: $DB_PATH"
        show_info "Por favor, verifica la ruta en config.ini"
        exit 1
    fi
    
    show_success "Base de datos encontrada: $DB_PATH"
    
    # Verificar directorio de música
    MUSIC_PATH=$(python3 -c "import configparser; c=configparser.ConfigParser(); c.read('config.ini'); print(c.get('music', 'root_path'))")
    
    if [ ! -d "$MUSIC_PATH" ]; then
        show_warning "Directorio de música no encontrado: $MUSIC_PATH"
        show_info "Por favor, verifica la ruta en config.ini"
    else
        show_success "Directorio de música encontrado: $MUSIC_PATH"
    fi
}

# Crear estructura de directorios
create_directories() {
    show_info "Creando estructura de directorios..."
    
    mkdir -p templates static logs
    
    show_success "Directorios creados"
}

# Ejecutar deployment
run_deployment() {
    show_info "Ejecutando script de deployment..."
    
    python3 deploy_music_web.py
    
    show_success "Deployment completado"
}

# Verificar instalación
test_installation() {
    show_info "Probando la instalación..."
    
    # Probar que Flask puede importarse
    if python3 -c "import flask; print('Flask OK')" 2>/dev/null; then
        show_success "Flask se puede importar correctamente"
    else
        show_error "Problema con la instalación de Flask"
        exit 1
    fi
    
    # Probar conexión a la base de datos
    if python3 -c "
import sqlite3
import configparser
c = configparser.ConfigParser()
c.read('config.ini')
db_path = c.get('database', 'path')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM artists WHERE origen = \"local\"')
count = cursor.fetchone()[0]
print(f'Artistas locales en DB: {count}')
conn.close()
" 2>/dev/null; then
        show_success "Conexión a la base de datos OK"
    else
        show_error "Problema conectando a la base de datos"
        exit 1
    fi
}

# Mostrar instrucciones finales
show_final_instructions() {
    echo
    echo "=========================================="
    show_success "¡Instalación completada!"
    echo "=========================================="
    echo
    show_info "Siguientes pasos:"
    echo
    echo "1. Para iniciar el servidor Flask:"
    echo "   python3 app.py"
    echo
    echo "2. Para deployment completo en servidor web:"
    echo "   - Revisa el archivo README_DEPLOYMENT.md generado"
    echo "   - Configura nginx según las instrucciones"
    echo "   - Instala el servicio systemd"
    echo
    echo "3. Para acceder a la aplicación:"
    echo "   - API: http://localhost:5157/"
    echo "   - Web: http://localhost:5157/ (o tu servidor configurado)"
    echo
    show_info "Logs se guardarán en el directorio 'logs/'"
    echo
}

# Función principal
main() {
    echo "Iniciando instalación..."
    echo
    
    check_root
    check_dependencies
    install_python_deps
    check_files
    check_config
    create_directories
    run_deployment
    test_installation
    show_final_instructions
    
    echo
    show_success "¡Instalación completada exitosamente!"
}

# Ejecutar si es llamado directamente
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi