#!/bin/bash

# =============================================================================
# Script para convertir notas de Obsidian a posts de Hugo (dos blogs)
# =============================================================================

# Variables de configuración - Blog notas
BLOG_DIR="/mnt/NFS/blogs/notas"
BLOG_CONTENT_DIR="/mnt/NFS/blogs/notas/content/post/"
BLOG_STATIC_DIR="/mnt/NFS/blogs/notas/static/"

# Variables de configuración - Blog mihitas
BLOG_DIR_2="/mnt/NFS/blogs/mihitas"
BLOG_CONTENT_DIR_2="/mnt/NFS/blogs/mihitas/content/posts/"  # Corregido: posts en lugar de post
BLOG_STATIC_DIR_2="/mnt/NFS/blogs/mihitas/static/"

# Variables comunes
OBSIDIAN_IMG_DIR="/mnt/windows/FTP/wiki/Obsidian/Dibujos/img/"

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Función para mostrar mensajes de error
error() {
    echo -e "${RED}Error: $1${NC}" >&2
}

# Función para mostrar mensajes de éxito
success() {
    echo -e "${GREEN}$1${NC}"
}

# Función para mostrar mensajes de advertencia
warning() {
    echo -e "${YELLOW}$1${NC}"
}

# Verificar si yad está instalado
check_yad() {
    if ! command -v yad &> /dev/null; then
        error "yad no está instalado. Por favor instálalo: sudo apt install yad"
        exit 1
    fi
}

# Función para seleccionar el blog de destino
select_blog() {
    local blog_choice
    blog_choice=$(yad --list \
        --title="Seleccionar Blog" \
        --text="Selecciona el blog de destino:" \
        --column="Blog" \
        --column="Descripción" \
        --width=400 \
        --height=200 \
        --button="OK:0" \
        --button="Cancelar:1" \
        "notas" "Blog de notas personales" \
        "mihitas" "Blog mihitas")

    if [[ $? -eq 0 ]]; then
        echo "$blog_choice" | cut -d'|' -f1
    else
        echo ""
    fi
}

# Función para convertir el título
convert_title() {
    local filename="$1"
    # Remover extensión y reemplazar guiones por espacios, luego capitalizar
    echo "$filename" | sed 's/\.md$//' | sed 's/-/ /g' | sed 's/\b\w/\U&/g'
}

# Función para extraer tags de Obsidian
extract_tags() {
    local file="$1"
    local tags=""
    local tag_array=()

    # Debug: mostrar contenido del archivo para depuración
    echo "Debug - Primeras 10 líneas del archivo:" >&2
    head -10 "$file" >&2

    # Método 1: Buscar en frontmatter YAML (tags: [tag1, tag2])
    if grep -q "^tags:" "$file"; then
        echo "Debug - Encontrado frontmatter con tags:" >&2
        local tag_line=$(grep "^tags:" "$file")
        echo "Debug - Línea de tags: $tag_line" >&2

        # Extraer tags del formato [tag1, tag2, tag3]
        if [[ $tag_line =~ \[(.*)\] ]]; then
            local tag_content="${BASH_REMATCH[1]}"
            # Limpiar espacios y dividir por comas
            IFS=',' read -ra tag_array <<< "$tag_content"
            for tag in "${tag_array[@]}"; do
                # Limpiar espacios y comillas
                tag=$(echo "$tag" | sed 's/^[ "]*//;s/[ "]*$//')
                if [[ -n "$tag" ]]; then
                    tags+="\"$tag\", "
                fi
            done
        fi
    fi

    # Método 2: Buscar en frontmatter YAML (formato lista)
    if [[ -z "$tags" ]]; then
        local in_tags_section=false
        while IFS= read -r line; do
            if [[ $line =~ ^tags:$ ]]; then
                in_tags_section=true
                continue
            elif [[ $in_tags_section == true ]]; then
                if [[ $line =~ ^[[:space:]]*-[[:space:]]*(.+)$ ]]; then
                    local tag="${BASH_REMATCH[1]}"
                    tag=$(echo "$tag" | sed 's/^[ "]*//;s/[ "]*$//')
                    tags+="\"$tag\", "
                elif [[ $line =~ ^[[:alpha:]] ]]; then
                    # Nueva sección, salir
                    break
                fi
            fi
        done < "$file"
    fi

    # Método 3: Buscar tags inline (#tag) en todo el documento
    if [[ -z "$tags" ]]; then
        echo "Debug - Buscando tags inline (#tag)" >&2
        local inline_tags=$(grep -o "#[a-zA-Z0-9_-][a-zA-Z0-9_-]*" "$file" | sort -u)
        if [[ -n "$inline_tags" ]]; then
            echo "Debug - Tags inline encontrados: $inline_tags" >&2
            while IFS= read -r tag_line; do
                if [[ -n "$tag_line" ]]; then
                    local clean_tag=$(echo "$tag_line" | sed 's/#//')
                    tags+="\"$clean_tag\", "
                fi
            done <<< "$inline_tags"
        fi
    fi

    # Limpiar tags finales (remover última coma y espacio)
    tags=$(echo "$tags" | sed 's/, $//')

    echo "Debug - Tags extraídos: '$tags'" >&2
    echo "$tags"
}

# Función para obtener descripción mediante diálogo
get_description() {
    local description
    description=$(yad --entry \
        --title="Descripción del post" \
        --text="Introduce una breve descripción para el post:" \
        --width=500 \
        --height=100 \
        --button="OK:0" \
        --button="Cancelar:1")

    if [[ $? -eq 0 ]]; then
        echo "$description"
    else
        echo ""
    fi
}

# Función para obtener categoría mediante diálogo
get_category() {
    local category
    category=$(yad --entry \
        --title="Categoria del post" \
        --text="Introduce una categoria para el post:" \
        --width=500 \
        --height=100 \
        --button="OK:0" \
        --button="Cancelar:1")

    if [[ $? -eq 0 ]]; then
        echo "$category"
    else
        echo ""
    fi
}

# Función para generar el frontmatter de Hugo (blog notas) - SIN WEIGHT
generate_frontmatter_notas() {
    local title="$1"
    local tags="$2"
    local description="$3"
    local categoria="$4"
    local date
    date=$(date +"%Y-%m-%d")

    cat << EOF
---
title : "$title"
date : "$date"
image : ""
tags : [$tags]
categories : [$categoria]
description : "$description"
---

EOF
}

# Función para generar el frontmatter de Hugo (blog mihitas) - SIN WEIGHT
generate_frontmatter_mihitas() {
    local title="$1"
    local tags="$2"
    local description="$3"
    local date
    date=$(date +"%Y-%m-%d")

    cat << EOF
+++
title = "$title"
date = "$date"
author = "volteret4"
cover = ""
tags = [${tags}]
keywords = [${tags}]
description = "$description"
showFullContent = false
readingTime = true
hideComments = false
+++

EOF
}

# Función para comprobar longitud y modificar mihitas si es necesario
check_long() {
    local output_file="$1"
    local blog_name="$2"
    local output_dir="$3"
    local length
    length="$(cat "$output_file" | wc -l)"

    if [[ $length -lt 25 ]]; then
        warning "Longitud corta: $length líneas"

        # Solo modificar si es el blog mihitas
        if [[ "$blog_name" == "mihitas" ]]; then
            # Usar sed para cambiar showFullContent = false por showFullContent = true
            sed -i 's/showFullContent = false/showFullContent = true/' "$output_file"
            success "Post corto detectado - showFullContent cambiado a true en mihitas"
        fi
    else
        success "Longitud normal: $length líneas - Iniciando selector de imágenes..."

        # Lanzar selector de imágenes para posts largos
        launch_image_selector "$output_dir" "$blog_name"
    fi
}

# Función para lanzar el selector de imágenes
launch_image_selector() {
    local output_dir="$1"
    local blog_name="$2"

    # Verificar si Python y PyQt6 están disponibles
    if ! command -v python3 &> /dev/null; then
        warning "Python3 no está disponible. Saltando selector de imágenes."
        return
    fi

    # Verificar si el script de Python existe
    local script_dir="$(dirname "$0")"
    local image_selector_script="${script_dir}/image_selector.py"

    if [[ ! -f "$image_selector_script" ]]; then
        warning "Script image_selector.py no encontrado en $image_selector_script"
        warning "Por favor, coloca image_selector.py en el mismo directorio que este script"
        return
    fi

    success "Lanzando selector de imágenes para: $blog_name"

    # Ejecutar el script de Python
    if python3 "$image_selector_script" "$output_dir"; then
        # Verificar si se descargó la imagen
        local image_path="${output_dir}/image.png"
        if [[ -f "$image_path" ]]; then
            success "Imagen descargada: $image_path"

            # Modificar frontmatter según el blog
            update_frontmatter_with_image "$output_dir" "$blog_name"
        else
            warning "No se descargó ninguna imagen"
        fi
    else
        warning "Selector de imágenes cancelado o falló"
    fi
}

# Función para actualizar frontmatter con la imagen
update_frontmatter_with_image() {
    local output_dir="$1"
    local blog_name="$2"
    local output_file="${output_dir}/index.md"

    if [[ "$blog_name" == "notas" ]]; then
        # Para blog notas (formato YAML): image : ""
        sed -i 's/image : ""/image : "image.png"/' "$output_file"
        success "Frontmatter actualizado para notas: image.png"
    else
        # Para blog mihitas (formato TOML): cover = ""
        sed -i 's/cover = ""/cover = "image.png"/' "$output_file"
        success "Frontmatter actualizado para mihitas: image.png"
    fi
}

# Función para hacer commit a git
commit_git() {
    local blog_dir="$1"
    cd "$blog_dir" || return
    eval "$(ssh-agent -s)"
    ssh-add ~/.ssh/keys/github
    git add .
    git commit -m "$(curl -s https://whatthecommit.com/index.txt)"
    git push
}

# Función para procesar un blog específico
process_blog() {
    local blog_name="$1"
    local obsidian_file="$2"
    local title="$3"
    local tags="$4"
    local description="$5"
    local category="$6"

    # Configurar variables según el blog
    local current_blog_dir
    local current_content_dir
    local current_static_dir

    if [[ "$blog_name" == "notas" ]]; then
        current_blog_dir="$BLOG_DIR"
        current_content_dir="$BLOG_CONTENT_DIR"
        current_static_dir="$BLOG_STATIC_DIR"
    else
        current_blog_dir="$BLOG_DIR_2"
        current_content_dir="$BLOG_CONTENT_DIR_2"
        current_static_dir="$BLOG_STATIC_DIR_2"
    fi

    # Crear directorios si no existen
    mkdir -p "$current_content_dir"
    mkdir -p "$current_static_dir"
    mkdir -p "${current_static_dir}images/"

    # Obtener nombre del archivo
    local filename
    filename=$(basename "$obsidian_file")
    name="${filename%.*}"

    # Crear carpeta
    local output_dir="${current_content_dir}${name}"
    mkdir -p "$output_dir"

    # Generar archivo de salida
    local output_file="${output_dir}/index.md"

    success "Procesando blog: $blog_name"

    # Generar frontmatter según el blog (SIN WEIGHT)
    if [[ "$blog_name" == "notas" ]]; then
        generate_frontmatter_notas "$title" "$tags" "$description" "$category" > "$output_file"
    else
        generate_frontmatter_mihitas "$title" "$tags" "$description" > "$output_file"
    fi

    # Procesar contenido (saltando el frontmatter existente de Obsidian si existe)
    local content_started=false
    local in_frontmatter=false

    while IFS= read -r line; do
        # Detectar inicio de frontmatter YAML
        if [[ $line == "---" ]]; then
            if [[ $content_started == false ]]; then
                in_frontmatter=true
                content_started=true
                continue
            elif [[ $in_frontmatter == true ]]; then
                in_frontmatter=false
                continue
            fi
        fi

        # Saltar líneas del frontmatter
        if [[ $in_frontmatter == true ]]; then
            continue
        fi

        # Procesar el contenido
        content_started=true
        echo "$line"
    done < "$obsidian_file" | while IFS= read -r line; do
        # Procesar imágenes
        if [[ $line =~ !\[\[([^]]+\.(png|jpg|jpeg|gif|webp))\]\] ]]; then
            local img_name="${BASH_REMATCH[1]}"
            local img_path="${OBSIDIAN_IMG_DIR}${img_name}"

            if [[ -f "$img_path" ]]; then
                # Copiar imagen al directorio static del blog seleccionado
                cp "$img_path" "${current_static_dir}images/"
                success "Imagen copiada: $img_name (blog: $blog_name)"

                # Reemplazar sintaxis de Obsidian por Hugo
                echo "![${img_name}](/images/${img_name})"
            else
                warning "Imagen no encontrada: $img_path"
                echo "<!-- Imagen no encontrada: $img_name -->"
            fi
        else
            echo "$line"
        fi
    done >> "$output_file"

    success "Post convertido exitosamente para $blog_name: $output_file"

    # Comprobar longitud y modificar si es necesario
    check_long "$output_file" "$blog_name" "$output_dir"

    # Github
    commit_git "$current_blog_dir"
    echo "Post añadido a github para blog: $blog_name"

    echo "[$blog_name] - Archivo destino: $output_file"
}

# Función principal
main() {
    # Verificar dependencias
    check_yad

    # Variables para argumentos
    local all_blogs=false
    local obsidian_file=""

    # Procesar argumentos
    while [[ $# -gt 0 ]]; do
        case $1 in
            --all)
                all_blogs=true
                shift
                ;;
            *)
                obsidian_file="$1"
                shift
                ;;
        esac
    done

    # Verificar que se proporcionó un archivo
    if [[ -z "$obsidian_file" ]]; then
        error "Uso: $0 [--all] <archivo_obsidian.md>"
        error "  --all: Publicar en todos los blogs"
        exit 1
    fi

    # Verificar que el archivo existe
    if [[ ! -f "$obsidian_file" ]]; then
        error "El archivo '$obsidian_file' no existe"
        exit 1
    fi

    # Verificar que es un archivo markdown
    if [[ ! "$obsidian_file" =~ \.md$ ]]; then
        error "El archivo debe tener extensión .md"
        exit 1
    fi

    # Obtener nombre del archivo
    local filename
    filename=$(basename "$obsidian_file")

    local title
    title=$(convert_title "$filename")

    # Extraer tags
    local tags
    tags=$(extract_tags "$obsidian_file")

    # Obtener descripción
    local description
    description=$(get_description)

    if [[ -z "$description" ]]; then
        warning "No se proporcionó descripción, continuando sin ella..."
        description=""
    fi

    local category=""

    if [[ "$all_blogs" == true ]]; then
        # Procesar todos los blogs
        success "Procesando post para TODOS los blogs..."

        # Para el blog notas necesitamos categoría
        category=$(get_category)

        # Variables para manejar imágenes
        local image_downloaded=false
        local first_blog_dir=""

        # Procesar blog notas primero
        process_blog "notas" "$obsidian_file" "$title" "$tags" "$description" "$category"
        first_blog_dir="${BLOG_CONTENT_DIR}${filename%.*}"

        # Verificar si se descargó una imagen en el primer blog
        if [[ -f "${first_blog_dir}/image.png" ]]; then
            image_downloaded=true
            success "Imagen descargada detectada, copiando a blog mihitas..."
        fi

        # Procesar blog mihitas
        process_blog "mihitas" "$obsidian_file" "$title" "$tags" "$description" "$category"

        # Si se descargó imagen en notas, copiarla a mihitas
        if [[ "$image_downloaded" == true ]]; then
            local mihitas_blog_dir="${BLOG_CONTENT_DIR_2}${filename%.*}"
            cp "${first_blog_dir}/image.png" "${mihitas_blog_dir}/image.png"

            # Actualizar frontmatter de mihitas con la imagen
            update_frontmatter_with_image "$mihitas_blog_dir" "mihitas"

            # Hacer commit adicional para mihitas con la imagen
            cd "$BLOG_DIR_2" || return
            eval "$(ssh-agent -s)"
            ssh-add ~/.ssh/keys/github
            git add .
            git commit -m "Add image to mihitas blog post"
            git push

            success "Imagen copiada y frontmatter actualizado en blog mihitas"
        fi

        # Mostrar resumen final
        echo ""
        echo "=== RESUMEN COMPLETO ==="
        echo "- Archivo origen: $obsidian_file"
        echo "- Título: $title"
        echo "- Tags: $tags"
        echo "- Descripción: $description"
        echo "- Categoría (solo notas): $category"
        echo "- Blogs procesados: notas, mihitas"
        if [[ "$image_downloaded" == true ]]; then
            echo "- Imagen: ✅ Descargada y añadida a ambos blogs"
        fi
        echo "- Estado: ✅ Publicado en todos los blogs"
    else
        # Seleccionar blog específico
        local selected_blog
        selected_blog=$(select_blog)

        if [[ -z "$selected_blog" ]]; then
            error "No se seleccionó ningún blog"
            exit 1
        fi

        # Si es blog notas, obtener categoría
        if [[ "$selected_blog" == "notas" ]]; then
            category=$(get_category)
        fi

        # Procesar blog seleccionado
        process_blog "$selected_blog" "$obsidian_file" "$title" "$tags" "$description" "$category"

        # Mostrar resumen
        echo ""
        echo "=== RESUMEN ==="
        echo "- Blog seleccionado: $selected_blog"
        echo "- Archivo origen: $obsidian_file"
        echo "- Título: $title"
        echo "- Tags: $tags"
        echo "- Descripción: $description"
        if [[ "$selected_blog" == "notas" ]]; then
            echo "- Categoría: $category"
        fi
    fi
}

# Ejecutar función principal
main "$@"
