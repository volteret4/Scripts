#!/usr/bin/env bash
#
# Script Name: discogs_collection_manager.sh
# Description: Gestor automático de colección de Discogs para crear posts individuales
# Author: volteret4
# Dependencies: jq, yad (para confirmación), discogs API access

set -euo pipefail

# =============================================================================
# CONFIGURACIÓN Y VARIABLES GLOBALES
# =============================================================================

# Obtener directorio del script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

# Cargar variables de entorno
if [[ -f "$PROJECT_ROOT/.env" ]]; then
    source "$PROJECT_ROOT/.env"
else
    echo "Error: No se encontró el archivo .env en $PROJECT_ROOT"
    exit 1
fi

# Rutas del proyecto
MODULES_DIR="$PROJECT_ROOT/modules"
CONTENT_DIR="$PROJECT_ROOT/.content"
LOGS_DIR="$CONTENT_DIR/logs"
CACHE_DIR="$CONTENT_DIR/cache"
BLOG_DIR="/mnt/NFS/blogs/vvmm"
COLLECTION_DIR="$BLOG_DIR/content/coleccion"

# Archivos de control
COLLECTION_REGISTRY="$CACHE_DIR/discogs_collection_registry.json"
COLLECTION_INDEX="$COLLECTION_DIR/index.md"
LOG_FILE="$LOGS_DIR/discogs_collection_$(date +%Y%m%d).log"

# Crear directorios necesarios
mkdir -p "$LOGS_DIR" "$CACHE_DIR" "$COLLECTION_DIR"

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
RESET='\033[0m'

# =============================================================================
# FUNCIONES DE UTILIDAD
# =============================================================================

log_info() {
    local message="$1"
    echo -e "${GREEN}[INFO]${RESET} $message" | tee -a "$LOG_FILE"
}

log_warn() {
    local message="$1"
    echo -e "${YELLOW}[WARN]${RESET} $message" | tee -a "$LOG_FILE"
}

log_error() {
    local message="$1"
    echo -e "${RED}[ERROR]${RESET} $message" | tee -a "$LOG_FILE"
}

log_debug() {
    local message="$1"
    if [[ "${DEBUG_MODE:-false}" == "true" ]]; then
        echo -e "${BLUE}[DEBUG]${RESET} $message" | tee -a "$LOG_FILE"
    fi
}

# =============================================================================
# FUNCIONES DE TEST Y DEBUG
# =============================================================================

test_discogs_api() {
    log_info "=== Test de conectividad con Discogs API ==="

    # 1. Test de identidad
    log_info "1. Verificando identidad..."
    local identity_response
    identity_response=$(curl -s -w "HTTP_CODE:%{http_code}" \
        -H "Authorization: Discogs token=$DISCOGS_TOKEN" \
        -H "User-Agent: DiscogsBlogManager/1.0" \
        "https://api.discogs.com/oauth/identity")

    local http_code=$(echo "$identity_response" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
    local json_response=$(echo "$identity_response" | sed 's/HTTP_CODE:[0-9]*$//')

    if [[ "$http_code" == "200" ]]; then
        local username=$(echo "$json_response" | jq -r '.username')
        local id=$(echo "$json_response" | jq -r '.id')
        log_info "✅ Autenticación exitosa: $username (ID: $id)"

        # Actualizar username si es diferente
        if [[ "${DISCOGS_USERNAME:-$(whoami)}" != "$username" ]]; then
            log_warn "Actualizando username de $(whoami) a $username"
            DISCOGS_USERNAME="$username"
        fi
    else
        log_error "❌ Error de autenticación (HTTP $http_code)"
        echo "$json_response" | jq '.' 2>/dev/null || echo "$json_response"
        return 1
    fi

    # 2. Test de colección
    log_info "2. Verificando acceso a colección..."
    local collection_response
    collection_response=$(curl -s -w "HTTP_CODE:%{http_code}" \
        -H "Authorization: Discogs token=$DISCOGS_TOKEN" \
        -H "User-Agent: DiscogsBlogManager/1.0" \
        "https://api.discogs.com/users/$DISCOGS_USERNAME/collection/folders/0/releases?page=1&per_page=1")

    http_code=$(echo "$collection_response" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
    json_response=$(echo "$collection_response" | sed 's/HTTP_CODE:[0-9]*$//')

    if [[ "$http_code" == "200" ]]; then
        local total_items=$(echo "$json_response" | jq -r '.pagination.items // 0')
        local total_pages=$(echo "$json_response" | jq -r '.pagination.pages // 0')
        log_info "✅ Acceso a colección exitoso: $total_items items en $total_pages páginas"

        if [[ "$total_items" == "0" ]]; then
            log_warn "⚠️  La colección está vacía"
            return 2
        fi

        # Mostrar ejemplo del primer item
        local first_item=$(echo "$json_response" | jq -r '.releases[0]')
        if [[ "$first_item" != "null" ]]; then
            local example_artist=$(echo "$first_item" | jq -r '.basic_information.artists[0].name')
            local example_title=$(echo "$first_item" | jq -r '.basic_information.title')
            log_info "📀 Ejemplo: $example_artist - $example_title"
        fi
    else
        log_error "❌ Error accediendo a colección (HTTP $http_code)"
        echo "$json_response" | jq '.' 2>/dev/null || echo "$json_response"
        return 1
    fi

    # 3. Test de rate limiting
    log_info "3. Verificando rate limiting..."
    local rate_limit_info=$(echo "$collection_response" | grep -i "x-discogs-ratelimit" || echo "No disponible")
    log_debug "Rate limit info: $rate_limit_info"

    log_info "✅ Todos los tests pasaron correctamente"
    return 0
}

# =============================================================================
# FUNCIONES DE DISCOGS API
# =============================================================================

get_discogs_collection() {
    log_info "Obteniendo colección de Discogs..."

    local username="${DISCOGS_USERNAME:-$(whoami)}"
    local page=1
    local per_page=100
    local all_items=()

    log_info "Usando usuario: $username"
    log_debug "Token configurado: ${DISCOGS_TOKEN:0:10}..."

    # Crear archivo temporal para debug
    local debug_response="$CACHE_DIR/discogs_debug_response.json"

    while true; do
        log_debug "Obteniendo página $page de la colección..."

        local url="https://api.discogs.com/users/$username/collection/folders/0/releases?page=$page&per_page=$per_page"
        log_debug "URL: $url"

        local response
        response=$(curl -s -w "HTTP_CODE:%{http_code}" \
            -H "Authorization: Discogs token=$DISCOGS_TOKEN" \
            -H "User-Agent: DiscogsBlogManager/1.0" \
            "$url") || {
            log_error "Error al ejecutar curl"
            return 1
        }

        # Extraer código HTTP y respuesta
        local http_code=$(echo "$response" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
        local json_response=$(echo "$response" | sed 's/HTTP_CODE:[0-9]*$//')

        log_debug "Código HTTP: $http_code"

        # Guardar respuesta para debug
        echo "$json_response" > "$debug_response"

        # Verificar código HTTP
        if [[ "$http_code" != "200" ]]; then
            log_error "Error HTTP $http_code de Discogs API"
            log_error "Respuesta: $(cat "$debug_response")"
            return 1
        fi

        # Verificar si hay errores en la respuesta JSON
        if echo "$json_response" | jq -e '.message' >/dev/null 2>&1; then
            local error_message=$(echo "$json_response" | jq -r '.message')
            log_error "Error de Discogs API: $error_message"
            log_error "Respuesta completa: $(cat "$debug_response")"
            return 1
        fi

        # Verificar estructura de la respuesta
        if ! echo "$json_response" | jq -e '.releases' >/dev/null 2>&1; then
            log_error "Respuesta no contiene campo 'releases'"
            log_error "Respuesta: $(cat "$debug_response")"
            return 1
        fi

        # Contar releases en esta página
        local releases_count=$(echo "$json_response" | jq '.releases | length')
        log_debug "Releases encontrados en página $page: $releases_count"

        if [[ "$releases_count" == "0" ]]; then
            log_debug "No hay más releases, terminando"
            break
        fi

        # Extraer releases de esta página y añadir al array
        local page_releases
        page_releases=$(echo "$json_response" | jq -c '.releases[]')

        if [[ -n "$page_releases" ]]; then
            while IFS= read -r release; do
                if [[ -n "$release" && "$release" != "null" ]]; then
                    all_items+=("$release")
                fi
            done <<< "$page_releases"
        fi

        # Verificar si hay más páginas
        local total_pages
        total_pages=$(echo "$json_response" | jq -r '.pagination.pages // 1')
        local current_page=$(echo "$json_response" | jq -r '.pagination.page // 1')

        log_debug "Página actual: $current_page de $total_pages"

        if [[ $current_page -ge $total_pages ]]; then
            log_debug "Última página alcanzada"
            break
        fi

        ((page++))
        sleep 1 # Rate limiting
    done

    # Combinar todos los items y guardar
    if [[ ${#all_items[@]} -gt 0 ]]; then
        # Crear un array JSON válido
        {
            echo "["
            for i in "${!all_items[@]}"; do
                echo "${all_items[i]}"
                if [[ $i -lt $((${#all_items[@]} - 1)) ]]; then
                    echo ","
                fi
            done
            echo "]"
        } > "$CACHE_DIR/discogs_collection_raw.json"
    else
        echo '[]' > "$CACHE_DIR/discogs_collection_raw.json"
    fi

    local total_items=${#all_items[@]}
    log_info "Colección obtenida: $total_items discos"

    # Si no hay items, mostrar información de debug
    if [[ $total_items -eq 0 ]]; then
        log_warn "No se encontraron discos en la colección"
        log_warn "Verificar:"
        log_warn "1. Que el token de Discogs sea válido"
        log_warn "2. Que el usuario '$username' exista"
        log_warn "3. Que la colección no esté vacía"
        log_warn "4. Última respuesta guardada en: $debug_response"

        # Intentar obtener información del usuario para verificar credenciales
        log_info "Verificando credenciales..."
        local user_info
        user_info=$(curl -s \
            -H "Authorization: Discogs token=$DISCOGS_TOKEN" \
            -H "User-Agent: DiscogsBlogManager/1.0" \
            "https://api.discogs.com/oauth/identity" 2>/dev/null)

        if [[ -n "$user_info" ]]; then
            local actual_username=$(echo "$user_info" | jq -r '.username // "unknown"')
            log_info "Usuario autenticado: $actual_username"
            if [[ "$actual_username" != "$username" ]]; then
                log_warn "ADVERTENCIA: El usuario autenticado ($actual_username) es diferente al configurado ($username)"
                log_warn "Considera configurar DISCOGS_USERNAME=$actual_username en tu .env"
            fi
        else
            log_error "No se pudo verificar la identidad. Token posiblemente inválido."
        fi
    fi

    return 0
}

parse_collection_items() {
    log_info "Procesando items de la colección..."

    if [[ ! -f "$CACHE_DIR/discogs_collection_raw.json" ]]; then
        log_error "No se encontró archivo de colección raw"
        return 1
    fi

    # Verificar que el archivo contiene JSON válido
    if ! jq empty "$CACHE_DIR/discogs_collection_raw.json" 2>/dev/null; then
        log_error "El archivo raw no contiene JSON válido"
        log_error "Contenido de las primeras líneas:"
        head -10 "$CACHE_DIR/discogs_collection_raw.json"
        return 1
    fi

    # Contar elementos
    local item_count
    item_count=$(jq '. | length' "$CACHE_DIR/discogs_collection_raw.json")
    log_debug "Procesando $item_count items de la colección"

    # Procesar cada item y crear un array JSON válido
    jq '[.[] | {
        discogs_id: .basic_information.id,
        artist: (.basic_information.artists[0].name // "Unknown Artist"),
        title: (.basic_information.title // "Unknown Title"),
        year: (.basic_information.year // 0),
        labels: ([.basic_information.labels[]?.name] | join(", ")),
        genres: ([.basic_information.genres[]?] | join(", ")),
        styles: ([.basic_information.styles[]?] | join(", ")),
        date_added: .date_added,
        resource_url: .basic_information.resource_url,
        cover_image: (.basic_information.cover_image // .basic_information.thumb // ""),
        thumb: (.basic_information.thumb // "")
    }]' "$CACHE_DIR/discogs_collection_raw.json" > "$CACHE_DIR/discogs_collection_parsed.json"

    # Verificar que el parsing fue exitoso
    if ! jq empty "$CACHE_DIR/discogs_collection_parsed.json" 2>/dev/null; then
        log_error "Error en el parsing de items"
        return 1
    fi

    local parsed_count
    parsed_count=$(jq '. | length' "$CACHE_DIR/discogs_collection_parsed.json")
    log_info "Items procesados y guardados: $parsed_count items en discogs_collection_parsed.json"

    # Mostrar algunos ejemplos
    if [[ "${DEBUG_MODE:-false}" == "true" ]]; then
        log_debug "Primeros 3 items parseados:"
        jq -r '.[:3][] | "- \(.artist) - \(.title) (\(.year))"' "$CACHE_DIR/discogs_collection_parsed.json"
    fi
}

# =============================================================================
# FUNCIONES DE REGISTRO Y CONTROL
# =============================================================================

init_registry() {
    if [[ ! -f "$COLLECTION_REGISTRY" ]]; then
        log_info "Inicializando registro de colección..."
        echo '{"processed": [], "added": [], "skipped": []}' > "$COLLECTION_REGISTRY"
    else
        # Mostrar estadísticas del registro existente
        local processed_count=$(jq '.processed | length' "$COLLECTION_REGISTRY" 2>/dev/null || echo "0")
        local added_count=$(jq '.added | length' "$COLLECTION_REGISTRY" 2>/dev/null || echo "0")
        local skipped_count=$(jq '.skipped | length' "$COLLECTION_REGISTRY" 2>/dev/null || echo "0")

        log_info "Registro existente encontrado:"
        log_info "  - Items procesados: $processed_count"
        log_info "  - Items añadidos: $added_count"
        log_info "  - Items saltados: $skipped_count"

        if [[ "$processed_count" -gt 0 ]]; then
            log_info "Si quieres reprocesar todo, usa --force"
        fi
    fi
}

is_item_processed() {
    local discogs_id="$1"

    if [[ ! -f "$COLLECTION_REGISTRY" ]]; then
        return 1
    fi

    jq -e --arg id "$discogs_id" '.processed[] | select(. == $id)' "$COLLECTION_REGISTRY" >/dev/null 2>&1
}

mark_item_processed() {
    local discogs_id="$1"
    local action="$2" # "added" or "skipped"

    local temp_file=$(mktemp)
    jq --arg id "$discogs_id" --arg action "$action" '
        .processed += [$id] |
        if $action == "added" then
            .added += [$id]
        else
            .skipped += [$id]
        end
    ' "$COLLECTION_REGISTRY" > "$temp_file"

    mv "$temp_file" "$COLLECTION_REGISTRY"
}

# =============================================================================
# FUNCIONES DE CONFIRMACIÓN
# =============================================================================

ask_user_confirmation() {
    local artist="$1"
    local album="$2"
    local year="$3"
    local label="$4"
    local date_added="$5"

    log_info "Disco encontrado:"
    echo -e "${CYAN}Artista:${RESET} $artist"
    echo -e "${CYAN}Álbum:${RESET} $album"
    echo -e "${CYAN}Año:${RESET} $year"
    echo -e "${CYAN}Sello:${RESET} $label"
    echo -e "${CYAN}Fecha agregado:${RESET} $date_added"
    echo ""

    # Usar yad si está disponible
    if command -v yad &> /dev/null; then
        # Crear mensaje detallado
        local message="<b>¿Añadir este disco al blog?</b>

<b>Artista:</b> $artist
<b>Álbum:</b> $album
<b>Año:</b> $year
<b>Sello:</b> $label
<b>Fecha agregado:</b> $date_added

<i>ENTER = Añadir | ESCAPE/No = Saltar | Ctrl+C = Salir del programa</i>"

        yad --question \
            --title="Gestión de Colección ($item_number/$total_items)" \
            --text="$message" \
            --width=600 \
            --height=250 \
            --center \
            --on-top \
            --skip-taskbar \
            --button="✅ Añadir (Enter):0" \
            --button="⏭️ Saltar (Esc):1" \
            --timeout=0 \
            --no-escape \
            --focus \
            2>/dev/null

        local result=$?

        # yad devuelve:
        # 0 = Yes (añadir)
        # 1 = No (saltar)
        # 252 = Cerrar ventana/Escape (saltar)
        case $result in
            0)
                log_debug "Usuario seleccionó: Añadir"
                return 0
                ;;
            1|252)
                log_debug "Usuario seleccionó: Saltar"
                return 1
                ;;
            *)
                log_debug "Resultado desconocido de yad: $result, saltando"
                return 1
                ;;
        esac
    else
        # Fallback a input manual si yad no está disponible
        echo -e "${YELLOW}¿Añadir este disco al blog?${RESET}"
        echo -e "${YELLOW}[Enter=Añadir, Escape/n/s=Saltar]:${RESET}"

        # Leer un solo carácter
        local response
        read -r -n 1 -s response
        echo ""

        case $response in
            ''|$'\n'|'y'|'Y'|'s'|'S')
                log_debug "Usuario presionó: Añadir"
                return 0
                ;;
            $'\e'|'n'|'N')
                log_debug "Usuario presionó: Saltar"
                return 1
                ;;
            *)
                log_debug "Tecla no reconocida, saltando"
                return 1
                ;;
        esac
    fi
}

# =============================================================================
# FUNCIONES DE CREACIÓN DE POSTS
# =============================================================================

create_collection_post() {
    local item="$1"

    # Extraer datos del item
    local discogs_id=$(echo "$item" | jq -r '.discogs_id')
    local artist=$(echo "$item" | jq -r '.artist')
    local album=$(echo "$item" | jq -r '.title')
    local year=$(echo "$item" | jq -r '.year')
    local labels=$(echo "$item" | jq -r '.labels')
    local genres=$(echo "$item" | jq -r '.genres')
    local styles=$(echo "$item" | jq -r '.styles')
    local date_added=$(echo "$item" | jq -r '.date_added')
    local resource_url=$(echo "$item" | jq -r '.resource_url')
    local cover_image=$(echo "$item" | jq -r '.cover_image')

    # Limpiar nombres para URLs y directorios
    local artist_clean=$(echo "$artist" | sed 's/[^a-zA-Z0-9 ]//g' | sed 's/ /-/g' | tr '[:upper:]' '[:lower:]')
    local album_clean=$(echo "$album" | sed 's/[^a-zA-Z0-9 ]//g' | sed 's/ /-/g' | tr '[:upper:]' '[:lower:]')

    # Crear directorio del post
    local post_dir="$COLLECTION_DIR/$artist_clean---$album_clean"
    mkdir -p "$post_dir"

    # Crear archivo del post
    local post_file="$post_dir/index.md"

    log_info "Creando post: $post_file"

    # Convertir fecha de Discogs a formato Hugo
    local hugo_date=$(date -d "$date_added" '+%Y-%m-%dT%H:%M:%S%z' 2>/dev/null || echo "$date_added")

    cat > "$post_file" << EOF
---
title: "$artist - $album"
date: $hugo_date
draft: false
tags:
  - coleccion
  - discogs
  - $artist_clean
categories:
  - Colección
discogs_id: $discogs_id
artist: "$artist"
album: "$album"
year: $year
labels: "$labels"
genres: "$genres"
styles: "$styles"
date_added: "$date_added"
---

![cover](image.jpeg ($artist - $album))

**Artista:** $artist
**Álbum:** $album
**Año:** $year
**Sello:** $labels
**Géneros:** $genres
**Estilos:** $styles
**Fecha agregado a colección:** $date_added

[![discogs](../../links/svg/discogs.png (discogs))]($resource_url)

EOF

    # Intentar obtener información adicional de la base de datos
    add_database_info_to_collection_post "$artist" "$album" "$post_file"

    # Descargar carátula
    download_collection_cover "$cover_image" "$post_dir"

    log_info "Post creado: $artist - $album"

    return 0
}

add_database_info_to_collection_post() {
    local artist="$1"
    local album="$2"
    local post_file="$3"

    # Ruta de la base de datos
    local DB_PATH="${DATABASE_PATH:-$PROJECT_ROOT/music_database.db}"

    if [[ ! -f "$DB_PATH" ]]; then
        log_debug "Base de datos no encontrada, saltando información adicional"
        return 0
    fi

    # Buscar información en la base de datos
    local db_info
    db_info=$(sqlite3 "$DB_PATH" "
        SELECT
            COALESCE(al.spotify_url, ''),
            COALESCE(al.bandcamp_url, ''),
            COALESCE(al.lastfm_url, ''),
            COALESCE(al.youtube_url, ''),
            COALESCE(al.musicbrainz_url, ''),
            COALESCE(al.wikipedia_url, '')
        FROM albums al
        JOIN artists a ON al.artist_id = a.id
        WHERE LOWER(TRIM(a.name)) = LOWER(TRIM('$artist'))
        AND LOWER(TRIM(al.name)) = LOWER(TRIM('$album'))
        LIMIT 1;
    " 2>/dev/null) || return 0

    if [[ -n "$db_info" ]]; then
        IFS='|' read -r spotify_url bandcamp_url lastfm_url youtube_url musicbrainz_url wikipedia_url <<< "$db_info"

        # Añadir enlaces adicionales al post
        echo "" >> "$post_file"
        echo "**Enlaces adicionales:**" >> "$post_file"
        echo "" >> "$post_file"

        [[ -n "$spotify_url" && "$spotify_url" != "NULL" ]] && echo "[![spotify](../../links/svg/spotify.png (spotify))]($spotify_url)" >> "$post_file"
        [[ -n "$bandcamp_url" && "$bandcamp_url" != "NULL" ]] && echo "[![bandcamp](../../links/svg/bandcamp.png (bandcamp))]($bandcamp_url)" >> "$post_file"
        [[ -n "$lastfm_url" && "$lastfm_url" != "NULL" ]] && echo "[![lastfm](../../links/svg/lastfm.png (lastfm))]($lastfm_url)" >> "$post_file"
        [[ -n "$youtube_url" && "$youtube_url" != "NULL" ]] && echo "[![youtube](../../links/svg/youtube.png (youtube))]($youtube_url)" >> "$post_file"
        [[ -n "$musicbrainz_url" && "$musicbrainz_url" != "NULL" ]] && echo "[![musicbrainz](../../links/svg/musicbrainz.png (musicbrainz))]($musicbrainz_url)" >> "$post_file"
        [[ -n "$wikipedia_url" && "$wikipedia_url" != "NULL" ]] && echo "[![wikipedia](../../links/svg/wikipedia.png (wikipedia))]($wikipedia_url)" >> "$post_file"

        log_debug "Información adicional añadida desde base de datos"
    fi
}

download_collection_cover() {
    local cover_url="$1"
    local post_dir="$2"

    if [[ -z "$cover_url" || "$cover_url" == "null" ]]; then
        log_warn "No hay URL de carátula disponible"
        return 1
    fi

    log_debug "Descargando carátula: $cover_url"

    if curl -s -L "$cover_url" -o "$post_dir/image.jpeg"; then
        log_debug "Carátula descargada correctamente"
        return 0
    else
        log_warn "Error descargando carátula"
        return 1
    fi
}

# =============================================================================
# FUNCIONES DE ÍNDICE
# =============================================================================

create_collection_index() {
    log_info "Creando índice de colección..."

    # Obtener todos los posts de colección
    local posts_data
    posts_data=$(find "$COLLECTION_DIR" -name "index.md" -not -path "$COLLECTION_INDEX" -exec head -20 {} \; -exec echo "---FILE-SEPARATOR---" \; | \
    awk '
    BEGIN { RS="---FILE-SEPARATOR---"; FS="\n" }
    {
        for (i=1; i<=NF; i++) {
            if ($i ~ /^artist:/) {
                gsub(/^artist: "|"$/, "", $i);
                artist = $i
            }
            if ($i ~ /^album:/) {
                gsub(/^album: "|"$/, "", $i);
                album = $i
            }
            if ($i ~ /^year:/) {
                gsub(/^year: /, "", $i);
                year = $i
            }
            if ($i ~ /^labels:/) {
                gsub(/^labels: "|"$/, "", $i);
                labels = $i
            }
            if ($i ~ /^genres:/) {
                gsub(/^genres: "|"$/, "", $i);
                genres = $i
            }
            if ($i ~ /^styles:/) {
                gsub(/^styles: "|"$/, "", $i);
                styles = $i
            }
            if ($i ~ /^date_added:/) {
                gsub(/^date_added: "|"$/, "", $i);
                date_added = $i
            }
        }
        if (artist && album) {
            print artist "|" album "|" year "|" labels "|" genres "|" styles "|" date_added
        }
        artist=""; album=""; year=""; labels=""; genres=""; styles=""; date_added=""
    }
    ')

    # Crear el archivo índice
    cat > "$COLLECTION_INDEX" << 'EOF'
---
title: "Mi Colección de Discogs"
date: 2024-01-01
draft: false
type: page
---

# Mi Colección Musical

Esta es mi colección personal de música, sincronizada desde Discogs.

| Artista | Álbum | Año | Sello | Géneros | Estilos | Fecha Agregado | Post |
|---------|-------|-----|-------|---------|---------|----------------|------|
EOF

    # Añadir cada disco a la tabla
    while IFS='|' read -r artist album year labels genres styles date_added; do
        if [[ -n "$artist" && -n "$album" ]]; then
            local artist_clean=$(echo "$artist" | sed 's/[^a-zA-Z0-9 ]//g' | sed 's/ /-/g' | tr '[:upper:]' '[:lower:]')
            local album_clean=$(echo "$album" | sed 's/[^a-zA-Z0-9 ]//g' | sed 's/ /-/g' | tr '[:upper:]' '[:lower:]')
            local post_link="/coleccion/$artist_clean---$album_clean/"

            echo "| $artist | $album | $year | $labels | $genres | $styles | $date_added | [🎵]($post_link) |" >> "$COLLECTION_INDEX"
        fi
    done <<< "$posts_data"

    # Añadir fecha de actualización
    echo "" >> "$COLLECTION_INDEX"
    echo "_Última actualización: $(date '+%d/%m/%Y %H:%M')_" >> "$COLLECTION_INDEX"

    log_info "Índice de colección creado: $COLLECTION_INDEX"
}

# =============================================================================
# FUNCIÓN PRINCIPAL
# =============================================================================

main() {
    log_info "=== Iniciando Gestor de Colección de Discogs ==="

    # Verificar dependencias
    if ! command -v jq &> /dev/null; then
        log_error "jq no está instalado. Instálalo para continuar."
        exit 1
    fi

    if [[ -z "${DISCOGS_TOKEN:-}" ]]; then
        log_error "DISCOGS_TOKEN no está configurado en .env"
        exit 1
    fi

    # Test inicial de API
    log_info "Ejecutando tests de conectividad..."
    local test_result
    test_discogs_api
    test_result=$?

    case $test_result in
        0)
            log_info "✅ Tests pasados, continuando..."
            ;;
        1)
            log_error "❌ Error en tests de API, abortando"
            exit 1
            ;;
        2)
            log_warn "⚠️  Colección vacía, abortando"
            exit 0
            ;;
    esac

    # Inicializar registro
    init_registry

    # Obtener y procesar colección
    if ! get_discogs_collection; then
        log_error "Error obteniendo colección de Discogs"
        exit 1
    fi

    if ! parse_collection_items; then
        log_error "Error procesando items de colección"
        exit 1
    fi

    # Verificar que tenemos items para procesar
    local total_items
    total_items=$(jq '. | length' "$CACHE_DIR/discogs_collection_parsed.json" 2>/dev/null || echo "0")

    if [[ "$total_items" == "0" ]]; then
        log_warn "No hay items para procesar después del parsing"
        log_warn "Archivos de debug:"
        log_warn "- Raw: $CACHE_DIR/discogs_collection_raw.json"
        log_warn "- Parsed: $CACHE_DIR/discogs_collection_parsed.json"
        log_warn "- Debug response: $CACHE_DIR/discogs_debug_response.json"
        exit 0
    fi

    log_info "Items disponibles para procesar: $total_items"

    # DEBUG: Verificar el contenido del archivo antes del bucle
    log_debug "Verificando contenido del archivo parseado..."
    log_debug "Primeras 3 líneas del archivo:"
    head -3 "$CACHE_DIR/discogs_collection_parsed.json" | while read -r line; do
        log_debug "  $line"
    done

    # DEBUG: Verificar que jq puede leer el archivo con timeout
    log_debug "Probando jq -c '.[]' con timeout..."
    local jq_test_count=0
    local jq_timeout=10

    timeout $jq_timeout bash -c 'jq -c ".[]" "$1"' _ "$CACHE_DIR/discogs_collection_parsed.json" | while read -r test_item; do
        ((jq_test_count++))
        if [[ $jq_test_count -le 3 ]]; then
            log_debug "  jq output $jq_test_count: ${test_item:0:50}..."
        fi
        if [[ $jq_test_count -ge 5 ]]; then
            break
        fi
    done

    log_debug "Total items encontrados por jq (con timeout): $jq_test_count"

    # Alternativa: probar con un método diferente
    log_debug "Probando método alternativo..."
    local alt_count=$(jq '. | length' "$CACHE_DIR/discogs_collection_parsed.json")
    log_debug "Método alternativo encontró: $alt_count items"

    # Verificar el primer item específicamente
    log_debug "Obteniendo primer item específicamente..."
    local first_item=$(jq -c '.[0]' "$CACHE_DIR/discogs_collection_parsed.json")
    log_debug "Primer item: ${first_item:0:100}..."

    # Procesar cada item usando un método más robusto
    local processed_count=0
    local added_count=0
    local skipped_count=0
    local item_number=0
    local already_processed_count=0

    log_info "Iniciando procesamiento de items con método robusto..."

    # Usar un bucle for con índices en lugar de while read
    for ((i=0; i<total_items; i++)); do
        log_debug "=== PROCESANDO ITEM $((i+1)) ==="

        # Obtener item por índice
        local item=$(jq -c ".[$i]" "$CACHE_DIR/discogs_collection_parsed.json")

        log_debug "Item $((i+1)) obtenido: ${item:0:100}..."

        if [[ -z "$item" || "$item" == "null" ]]; then
            log_debug "Item $((i+1)) vacío o null, saltando..."
            continue
        fi

        ((item_number++))

        local discogs_id=$(echo "$item" | jq -r '.discogs_id')
        local artist=$(echo "$item" | jq -r '.artist')
        local album=$(echo "$item" | jq -r '.title')
        local year=$(echo "$item" | jq -r '.year')
        local labels=$(echo "$item" | jq -r '.labels')
        local date_added=$(echo "$item" | jq -r '.date_added')

        log_debug "Datos extraídos: ID=$discogs_id, Artist=$artist, Album=$album"

        # Verificar si ya fue procesado
        if is_item_processed "$discogs_id"; then
            log_debug "Item ya procesado: $artist - $album"
            ((already_processed_count++))
            continue
        fi

        ((processed_count++))

        # Mostrar progreso
        log_info "=== Disco $item_number de $total_items (Procesados: $processed_count, Añadidos: $added_count, Saltados: $skipped_count) ==="

        # Preguntar al usuario
        if ask_user_confirmation "$artist" "$album" "$year" "$labels" "$date_added"; then
            log_info "Usuario confirmó: Añadiendo $artist - $album"

            if create_collection_post "$item"; then
                mark_item_processed "$discogs_id" "added"
                ((added_count++))
                log_info "✅ Post creado para: $artist - $album"
            else
                log_error "❌ Error creando post para: $artist - $album"
            fi
        else
            log_info "Usuario canceló: Saltando $artist - $album"
            mark_item_processed "$discogs_id" "skipped"
            ((skipped_count++))
        fi

        # Pequeña pausa entre items
        sleep 0.2
    done  # ← ESTA LÍNEA FALTABA

    log_info "Bucle de procesamiento completado"
    log_info "Items revisados: $item_number"
    log_info "Items ya procesados anteriormente: $already_processed_count"
    log_info "Items nuevos procesados: $processed_count"

    # Crear/actualizar índice
    create_collection_index

    # Resumen final
    log_info "=== Procesamiento completado ==="
    log_info "Items procesados: $processed_count"
    log_info "Posts añadidos: $added_count"
    log_info "Items saltados: $skipped_count"

    return 0
}

# =============================================================================
# PUNTO DE ENTRADA
# =============================================================================

# Procesar argumentos
while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--debug)
            export DEBUG_MODE=true
            ;;
        -f|--force)
            rm -f "$COLLECTION_REGISTRY"
            log_info "Registro borrado, se procesarán todos los items"
            ;;
        -t|--test)
            log_info "Ejecutando solo tests de API..."
            test_discogs_api
            exit $?
            ;;
        -h|--help)
            echo "Uso: $0 [opciones]"
            echo "Opciones:"
            echo "  -d, --debug    Activar modo debug"
            echo "  -f, --force    Borrar registro y procesar todo"
            echo "  -t, --test     Ejecutar solo tests de API"
            echo "  -h, --help     Mostrar esta ayuda"
            exit 0
            ;;
        *)
            log_error "Opción desconocida: $1"
            exit 1
            ;;
    esac
    shift
done

# Ejecutar función principal
main "$@"
