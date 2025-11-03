#!/bin/bash
#
# Script para actualizar automáticamente el sitio de GitHub Pages
# con nuevos embeds de FreshRSS
#
# Uso:
#   ./update_github_pages.sh
#

set -e  # Salir si hay algún error

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Función para imprimir con colores
print_step() {
    echo -e "${BLUE}==>${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}!${NC} $1"
}

# Banner
echo ""
echo "╔═══════════════════════════════════════════════╗"
echo "║   Actualización de GitHub Pages - FreshRSS   ║"
echo "╚═══════════════════════════════════════════════╝"
echo ""

# Configuración (editar según tus necesidades)
EMBEDS_DIR="$HOME/gits/freshrss_embeeds"
SITE_TITLE="FreshRSS Embeds"
SITE_DESCRIPTION="Embeds de música de mis feeds favoritos por leer"

# Verificar que estamos en el directorio correcto
if [ ! -f "freshrss_html_generator.py" ]; then
    print_error "No se encontró freshrss_html_generator.py"
    echo "  Asegúrate de ejecutar este script desde el directorio correcto"
    exit 1
fi

# Verificar que el directorio de embeds existe
if [ ! -d "$EMBEDS_DIR" ]; then
    print_warning "El directorio $EMBEDS_DIR no existe, se creará"
    mkdir -p "$EMBEDS_DIR"
fi

# Paso 1: Generar embeds desde FreshRSS
print_step "Generando embeds desde FreshRSS..."
echo ""

# Aquí debes ejecutar tu comando de FreshRSS
# Edita esta línea según tu configuración:

python freshrss_html_generator.py --server https://rss.pollete.duckdns.org --unread-only --username pollo --max-articles 0 --output-dir "$EMBEDS_DIR" --feeds Ambientblog "Ban Ban Ton Ton" "Depósito sonoro" "Lost Turntable" "FW Rare Jazz Vinyl Collector"
# O modo interactivo:
#python freshrss_html_generator_fixed.py --interactive

if [ $? -eq 0 ]; then
    print_success "Embeds generados exitosamente"
else
    print_error "Error al generar embeds"
    exit 1
fi

# Paso 2: Generar index.html
print_step "Generando index.html..."

if [ -f "generate_index.py" ]; then
    python freshrss_html_index.py --dir "$EMBEDS_DIR" --title "$SITE_TITLE" --description "$SITE_DESCRIPTION"

    if [ $? -eq 0 ]; then
        print_success "index.html generado"
    else
        print_error "Error al generar index.html"
        exit 1
    fi
else
    print_error "No se encontró generate_index.py"
    exit 1
fi

# Paso 3: Verificar que hay archivos HTML
cd "$EMBEDS_DIR"
HTML_COUNT=$(ls -1 *.html 2>/dev/null | wc -l)

if [ $HTML_COUNT -eq 0 ]; then
    print_error "No se encontraron archivos HTML para subir"
    exit 1
fi

print_success "Se encontraron $HTML_COUNT archivos HTML"

# Paso 4: Verificar si es un repositorio git
if [ ! -d ".git" ]; then
    print_warning "Este directorio no es un repositorio git"
    echo ""
    read -p "¿Deseas inicializar un repositorio git aquí? (s/n): " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Ss]$ ]]; then
        git init
        print_success "Repositorio git inicializado"

        # Pedir URL del repositorio remoto
        echo ""
        echo "Crea un repositorio en GitHub: https://github.com/new"
        echo ""
        read -p "Ingresa la URL del repositorio (ej: https://github.com/usuario/repo.git): " REPO_URL

        if [ -n "$REPO_URL" ]; then
            git remote add origin "$REPO_URL"
            git branch -M main
            print_success "Remoto configurado"
        else
            print_error "URL del repositorio vacía"
            exit 1
        fi
    else
        print_error "No se puede continuar sin un repositorio git"
        exit 1
    fi
fi

# Paso 5: Añadir cambios a git
print_step "Añadiendo archivos a git..."
git add *.html

if [ $? -eq 0 ]; then
    print_success "Archivos añadidos"
else
    print_error "Error al añadir archivos"
    exit 1
fi

# Paso 6: Commit
print_step "Creando commit..."
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
git commit -m "Update: $TIMESTAMP - $HTML_COUNT archivos"

if [ $? -eq 0 ]; then
    print_success "Commit creado"
elif [ $? -eq 1 ]; then
    print_warning "No hay cambios para commitear"
else
    print_error "Error al crear commit"
    exit 1
fi

# Paso 7: Push a GitHub
print_step "Subiendo a GitHub..."
git push origin main

if [ $? -eq 0 ]; then
    print_success "Cambios subidos exitosamente"
else
    print_error "Error al subir cambios"
    echo ""
    print_warning "Si es la primera vez, usa: git push -u origin main"
    exit 1
fi

# Obtener el nombre de usuario y repo
REMOTE_URL=$(git config --get remote.origin.url)
if [[ $REMOTE_URL =~ github\.com[:/]([^/]+)/([^/.]+) ]]; then
    USERNAME="${BASH_REMATCH[1]}"
    REPO="${BASH_REMATCH[2]}"
    SITE_URL="https://${USERNAME}.github.io/${REPO}/"

    echo ""
    echo "╔═══════════════════════════════════════════════╗"
    echo "║              ✓ ACTUALIZACIÓN COMPLETA         ║"
    echo "╚═══════════════════════════════════════════════╝"
    echo ""
    print_success "Sitio actualizado exitosamente"
    echo ""
    echo "🌐 URL del sitio: $SITE_URL"
    echo "📊 Archivos actualizados: $HTML_COUNT"
    echo ""
    print_warning "Los cambios pueden tardar 1-2 minutos en aparecer"
    echo ""
else
    echo ""
    print_success "Cambios subidos a GitHub"
    echo ""
fi

cd ..
