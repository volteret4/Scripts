#!/usr/bin/env bash
#
# Script Name: vvmm_post_creator.sh
# Description: Creador automático de posts para blog VVMM
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:

# Notes:
#     Script unificado que crea posts automáticamente basándose en la música actualmente en reproducción
#     Integra todos los servicios: Spotify, Discogs, YouTube, etc.

set -euo pipefail  # Strict mode

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

# Crear directorios necesarios
mkdir -p "$LOGS_DIR" "$CACHE_DIR"

# Archivos de log
LOG_FILE="$LOGS_DIR/vvmm_$(date +%Y%m%d).log"
ERROR_LOG="$LOGS_DIR/errors_$(date +%Y%m%d).log"

# Definir colores
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
    echo -e "${RED}[ERROR]${RESET} $message" | tee -a "$LOG_FILE" | tee -a "$ERROR_LOG"
}

log_debug() {
    local message="$1"
    if [[ "${DEBUG_MODE:-false}" == "true" ]]; then
        echo -e "${BLUE}[DEBUG]${RESET} $message" | tee -a "$LOG_FILE"
    fi
}

# Función para verificar el estado y enviar notificaciones
check_status() {
    local status=$1
    local success_message="$2"
    local error_message="$3"

    case $status in
        0)
            notify-send -t 3 "Éxito" "$success_message"
            log_info "$success_message"
            ;;
        1)
            notify-send -t 10 "Error" "$error_message: Error general."
            log_error "$error_message: Error general."
            exit 1
            ;;
        2)
            notify-send -t 10 "Error" "$error_message: Error de uso incorrecto."
            log_error "$error_message: Error de uso incorrecto."
            exit 1
            ;;
        127)
            notify-send -t 10 "Error" "$error_message: Comando no encontrado."
            log_error "$error_message: Comando no encontrado."
            exit 1
            ;;
        130)
            notify-send -t 10 "Error" "$error_message: Proceso interrumpido."
            log_error "$error_message: Proceso interrumpido."
            exit 1
            ;;
        *)
            notify-send -t 10 "Error" "$error_message: Código desconocido $status."
            log_error "$error_message: Código desconocido $status."
            exit 1
            ;;
    esac
}

# Función para activar el entorno virtual de Python
activate_python_env() {
    if [[ -n "${PYTHON_VENV_PATH:-}" ]] && [[ -f "$PYTHON_VENV_PATH/bin/activate" ]]; then
        if source "$PYTHON_VENV_PATH/bin/activate" 2>/dev/null; then
            log_debug "Entorno virtual Python activado: $PYTHON_VENV_PATH"
            return 0
        else
            log_warn "Error activando entorno virtual: $PYTHON_VENV_PATH"
            return 1
        fi
    else
        log_debug "Usando Python del sistema (no se encontró entorno virtual)"
        return 0
    fi
}

# Función para limpiar variables de texto
clean_variable() {
    local input="$1"
    bash "$MODULES_DIR/limpia_var.sh" "$input"
}

# =============================================================================
# FUNCIONES DE METADATA MUSICAL
# =============================================================================

# Obtener información de la canción en reproducción
get_current_song_metadata() {
    log_info "Obteniendo metadata de la canción en reproducción..."

    # Validar playerctl primero
    if ! validate_playerctl; then
        return 1
    fi

    # Detectar reproductor activo
    local active_player
    active_player="$(get_active_player)"

    if [[ -z "$active_player" ]] || [[ "$active_player" == "none" ]]; then
        log_error "No se encontró ningún reproductor activo"
        notify-send -u critical "Error" "No hay reproductores de música activos"
        return 1
    fi

    log_info "Reproductor detectado: $active_player"

    # Mostrar info de debug si está habilitado
    if [[ "${DEBUG_MODE:-false}" == "true" ]]; then
        show_player_debug_info "$active_player"
    fi

    # Obtener metadata usando playerctl
    local artist album title

    artist="$(playerctl -p "$active_player" metadata artist 2>/dev/null || echo "")"
    album="$(playerctl -p "$active_player" metadata album 2>/dev/null || echo "")"
    title="$(playerctl -p "$active_player" metadata title 2>/dev/null || echo "")"

    # Verificar que tenemos datos mínimos
    if [[ -z "$artist" ]] || [[ -z "$title" ]]; then
        log_error "No se pudo obtener metadata suficiente"
        log_debug "Artist: '$artist', Title: '$title', Album: '$album'"

        # Intentar obtener de xesam (formato extendido)
        artist="${artist:-$(playerctl -p "$active_player" metadata xesam:artist 2>/dev/null || echo "")}"
        album="${album:-$(playerctl -p "$active_player" metadata xesam:album 2>/dev/null || echo "")}"
        title="${title:-$(playerctl -p "$active_player" metadata xesam:title 2>/dev/null || echo "")}"

        if [[ -z "$artist" ]] || [[ -z "$title" ]]; then
            notify-send -u critical "Error" "No se pudo obtener información de la canción"
            return 1
        fi
    fi

    # Limpiar metadata
    ARTIST_RAW="$(echo "$artist" | sed 's/[\":]//g')"
    TITLE_RAW="$(echo "$title" | sed 's/[\":]//g')"
    ALBUM_RAW="$(echo "$album" | sed 's/[\":]//g')"

    # Si no hay álbum, intentar usar el título como álbum (para singles)
    if [[ -z "$ALBUM_RAW" ]]; then
        ALBUM_RAW="$TITLE_RAW"
        log_warn "No se encontró álbum, usando título como álbum"
    fi

    # Limpiar variables usando la función existente
    ARTIST="$(clean_variable "$ARTIST_RAW")"
    ALBUM="$(clean_variable "$ALBUM_RAW")"

    # Procesar artista para formato post
    ARTIST_PROCESSED="$(echo "$ARTIST" | sed -E "s/[áÁ]/-/g; s/\(.*\)//g; s/&/and/g; s/[éÉ]/e/g; s/[íÍ]/i/g; s/[óÓ]/o/g; s/[úÚ]/u/g; s/['\`]/-/g; s/---/-/g; s/--/-/g; s/\ /-/g; s/^-//g; s/-$//g")"
    ALBUM_PROCESSED="$(echo "$ALBUM" | sed -E "s/[áÁ]/-/g; s/\(.*\)//g; s/&/and/g; s/[éÉ]/e/g; s/[íÍ]/i/g; s/[óÓ]/o/g; s/[úÚ]/u/g; s/['\`]/-/g; s/---/-/g; s/--/-/g; s/\ /-/g; s/^-//g; s/-$//g")"

    log_info "Metadata obtenida: $ARTIST - $ALBUM"
    log_debug "Título: $TITLE_RAW"
    log_debug "Reproductor: $active_player"

    return 0
}

# Solicitar tags al usuario
get_user_tags() {
    log_info "Solicitando tags al usuario..."

    local default_genre=""
    local tags_input

    tags_input="$(yad --entry --title="Comentario" --entry-text="$default_genre" --text="$ARTIST $ALBUM \n TAGS [x z y]:")"

    if [[ -z "$tags_input" ]]; then
        notify-send -u critical "Cancelando post sin TAGS"
        log_warn "Post cancelado: Sin tags proporcionados"
        exit 0
    fi

    # Permitir editar artista y álbum si se ingresa 'r'
    if [[ "$tags_input" == 'r' ]]; then
        ARTIST="$(yad --entry --text="Artista" --entry-text="$ARTIST")"
        if [[ -z "$ARTIST" ]]; then
            notify-send "Saliendo"
            exit 0
        fi
        ALBUM="$(yad --entry --text="Álbum" --entry-text="$ALBUM")"
        if [[ -z "$ALBUM" ]]; then
            notify-send "Saliendo"
            exit 0
        fi
        tags_input="$(yad --entry --title="Comentario" --entry-text="$default_genre" --text="$ARTIST $ALBUM \n TAGS [x z y]:")"
    fi

    # Procesar tags especiales
    if [[ "$tags_input" =~ 'pollo' ]]; then
        touch "$CACHE_DIR/pollo.txt" "$CACHE_DIR/pollo2.txt"
        yad --text-info --editable < "$CACHE_DIR/pollo.txt" > "$CACHE_DIR/pollo2.txt"
        tags_input="$(yad --entry --title="Comentario" --entry-text="$default_genre" --text="$ARTIST $ALBUM \n TAGS [x z y]:")"
        rm "$CACHE_DIR/pollo.txt"
        mv "$CACHE_DIR/pollo2.txt" "$CACHE_DIR/pollo.txt"
    fi

    # Convertir tags a array
    IFS=' ' read -ra TAGS_ARRAY <<< "$tags_input"

    log_info "Tags obtenidos: ${TAGS_ARRAY[*]}"
}

# =============================================================================
# FUNCIONES DE GESTIÓN DE PLAYLISTS SPOTIFY
# =============================================================================

update_spotify_playlists() {
    log_info "Actualizando playlists de Spotify..."

    if [[ "${ENABLE_SPOTIFY_INTEGRATION:-true}" == "false" ]]; then
        log_info "Integración con Spotify deshabilitada"
        return 0
    fi

    if ! activate_python_env; then
        log_warn "No se pudo activar entorno Python para Spotify"
        return 1
    fi

    # Intentar actualizar playlists (no crítico si falla)
    if python3 "$MODULES_DIR/sp_playlist.py" 2>/dev/null; then
        log_info "Playlists de Spotify actualizadas"
    else
        log_warn "Error actualizando playlists de Spotify (continuando sin esta funcionalidad)"
        return 1
    fi

    # Generar markdown de playlists (no crítico si falla)
    if python3 "$MODULES_DIR/sp_playlist_md.py" 2>/dev/null; then
        log_info "Markdown de playlists generado"
    else
        log_warn "Error generando markdown de playlists"
        return 1
    fi

    # Actualizar about.md
    local about_file="$BLOG_DIR/content/about.md"
    local playlists_md="$CACHE_DIR/playlists.md"

    if [[ -f "${about_file}.skel" ]]; then
        rm -f "$about_file"
        cp "${about_file}.skel" "$about_file"
        echo "" >> "$about_file"
        echo "_Actualizado el $(date +%d-%m-%Y)_" >> "$about_file"
        echo "" >> "$about_file"

        if [[ -f "$playlists_md" ]]; then
            cat "$playlists_md" >> "$about_file"
            log_info "About.md actualizado con playlists"
        else
            echo "No hay playlists disponibles" >> "$about_file"
            log_warn "No se encontró archivo de playlists en markdown"
        fi
    else
        log_warn "No se encontró about.md.skel, saltando actualización"
        return 1
    fi

    return 0
}

# =============================================================================
# FUNCIÓN DE CONSULTA A BASE DE DATOS
# =============================================================================

check_database_first() {
    log_info "Verificando si existe información en la base de datos..."

    # Ruta de la base de datos (ajusta según tu configuración)
    local DB_PATH="${DATABASE_PATH:-$PROJECT_ROOT/music_database.db}"

    if [[ ! -f "$DB_PATH" ]]; then
        log_warn "Base de datos no encontrada en $DB_PATH, usando scripts tradicionales"
        return 1
    fi

    log_debug "Buscando: ARTIST='$ARTIST', ALBUM='$ALBUM'"

    # Buscar álbum en la base de datos con la estructura real
    local db_result
    db_result=$(sqlite3 "$DB_PATH" "
        SELECT
            a.name,
            al.name,
            COALESCE(al.discogs_url, ''),
            COALESCE(al.musicbrainz_url, ''),
            COALESCE(al.spotify_url, ''),
            COALESCE(al.spotify_id, ''),
            COALESCE(al.bandcamp_url, ''),
            COALESCE(al.lastfm_url, ''),
            COALESCE(al.youtube_url, ''),
            COALESCE(al.wikipedia_url, ''),
            COALESCE(al.label, ''),
            COALESCE(al.year, ''),
            COALESCE(al.album_art_path, ''),
            COALESCE(al.genre, ''),
            al.total_tracks,
            al.id,
            a.id,
            -- NUEVOS CAMPOS
            COALESCE(al.producers, ''),
            COALESCE(al.notes, ''),
            COALESCE(al.recording_studio, ''),
            COALESCE(al.mastered_by, ''),
            COALESCE(al.mixed_by, ''),
            COALESCE(al.additional_notes, '')
        FROM albums al
        JOIN artists a ON al.artist_id = a.id
        WHERE LOWER(a.name) LIKE LOWER('%$ARTIST%')
        AND LOWER(al.name) LIKE LOWER('%$ALBUM%')
        LIMIT 1;
    " 2>/dev/null) || {
        log_warn "Error consultando base de datos, usando scripts tradicionales"
        return 1
    }

    if [[ -z "$db_result" ]]; then
        log_info "Álbum no encontrado en base de datos: $ARTIST - $ALBUM"
        return 1
    fi

    log_info "¡Información encontrada en base de datos! Usando datos almacenados..."

    # Parsear resultado (separado por |)
    IFS='|' read -r \
        DB_ARTIST \
        DB_ALBUM \
        DB_DISCOGS_URL \
        DB_MUSICBRAINZ_URL \
        DB_SPOTIFY_URL \
        DB_SPOTIFY_ID \
        DB_BANDCAMP \
        DB_LASTFM \
        DB_YOUTUBE \
        DB_WIKIPEDIA \
        DB_RECORD_LABEL \
        DB_RELEASE_YEAR \
        DB_COVER_PATH \
        DB_GENRE \
        DB_TOTAL_TRACKS \
        DB_ALBUM_ID \
        DB_ARTIST_ID \
        DB_PRODUCERS \
        DB_NOTES \
        DB_RECORDING_STUDIO \
        DB_MASTERED_BY \
        DB_MIXED_BY \
        DB_ADDITIONAL_NOTES \
        <<< "$db_result"


    log_debug "Datos obtenidos: Artist='$DB_ARTIST', Album='$DB_ALBUM'"

    # Generar enlaces usando datos de la base de datos
    generate_links_from_database

    # Crear post usando información de la base de datos
    create_database_post

    return 0
}

generate_links_from_database() {
    log_info "Generando enlaces desde base de datos..."

    # Generar enlaces con los datos de la base de datos
    # Bandcamp
    if [[ -n "$DB_BANDCAMP" && "$DB_BANDCAMP" != "NULL" && "$DB_BANDCAMP" != "" ]]; then
        LINK_BANDCAMP="[![bandcamp](../links/svg/bandcamp.png (bandcamp))]($DB_BANDCAMP)"
        URL_BANDCAMP="$DB_BANDCAMP"
    else
        LINK_BANDCAMP="<!-- [![bandcamp](../links/svg/bandcamp.png (bandcamp))](bandcamp_not_in_db) -->"
        URL_BANDCAMP=""
    fi

    # Discogs - extraer ID de la URL
    if [[ -n "$DB_DISCOGS_URL" && "$DB_DISCOGS_URL" != "NULL" && "$DB_DISCOGS_URL" != "" ]]; then
        LINK_DISCOGS="[![discogs](../links/svg/discogs.png (discogs))]($DB_DISCOGS_URL)"
        URL_DISCOGS="$DB_DISCOGS_URL"

        # Extraer master ID o release ID de la URL de Discogs
        if [[ "$DB_DISCOGS_URL" =~ /master/([0-9]+) ]]; then
            MASTERID="${BASH_REMATCH[1]}"
        elif [[ "$DB_DISCOGS_URL" =~ /release/([0-9]+) ]]; then
            RELEASEID="${BASH_REMATCH[1]}"
            MASTERID="bash_script"
        fi
    else
        LINK_DISCOGS="<!-- [![discogs](../links/svg/discogs.png (discogs))](discogs_not_in_db) -->"
        URL_DISCOGS=""
    fi

    # Last.fm
    if [[ -n "$DB_LASTFM" && "$DB_LASTFM" != "NULL" && "$DB_LASTFM" != "" ]]; then
        LINK_LASTFM="[![lastfm](../links/svg/lastfm.png (lastfm))]($DB_LASTFM)"
        URL_LASTFM="$DB_LASTFM"
    else
        LINK_LASTFM="<!-- [![lastfm](../links/svg/lastfm.png (lastfm))](lastfm_not_in_db) -->"
        URL_LASTFM=""
    fi

    # MusicBrainz
    if [[ -n "$DB_MUSICBRAINZ_URL" && "$DB_MUSICBRAINZ_URL" != "NULL" && "$DB_MUSICBRAINZ_URL" != "" ]]; then
        LINK_MUSICBRAINZ="[![musicbrainz](../links/svg/musicbrainz.png (musicbrainz))]($DB_MUSICBRAINZ_URL)"
        URL_MUSICBRAINZ="$DB_MUSICBRAINZ_URL"
    else
        LINK_MUSICBRAINZ="<!-- [![musicbrainz](../links/svg/musicbrainz.png (musicbrainz))](musicbrainz_not_in_db) -->"
        URL_MUSICBRAINZ=""
    fi

    # Spotify
    if [[ -n "$DB_SPOTIFY_URL" && "$DB_SPOTIFY_URL" != "NULL" && "$DB_SPOTIFY_URL" != "" ]]; then
        LINK_SPOTIFY="[![spotify](../links/svg/spotify.png (spotify))]($DB_SPOTIFY_URL)"
        URL_SPOTIFY="$DB_SPOTIFY_URL"
    elif [[ -n "$DB_SPOTIFY_ID" && "$DB_SPOTIFY_ID" != "NULL" && "$DB_SPOTIFY_ID" != "" ]]; then
        URL_SPOTIFY="https://open.spotify.com/album/$DB_SPOTIFY_ID"
        LINK_SPOTIFY="[![spotify](../links/svg/spotify.png (spotify))]($URL_SPOTIFY)"
    else
        LINK_SPOTIFY="<!-- [![spotify](../links/svg/spotify.png (spotify))](spotify_not_in_db) -->"
        URL_SPOTIFY=""
    fi

    # Wikipedia
    if [[ -n "$DB_WIKIPEDIA" && "$DB_WIKIPEDIA" != "NULL" && "$DB_WIKIPEDIA" != "" ]]; then
        LINK_WIKIPEDIA="[![wikipedia](../links/svg/wikipedia.png (wikipedia))]($DB_WIKIPEDIA)"
        URL_WIKIPEDIA="$DB_WIKIPEDIA"
    else
        LINK_WIKIPEDIA="<!-- [![wikipedia](../links/svg/wikipedia.png (wikipedia))](wikipedia_not_in_db) -->"
        URL_WIKIPEDIA=""
    fi

    # YouTube
    if [[ -n "$DB_YOUTUBE" && "$DB_YOUTUBE" != "NULL" && "$DB_YOUTUBE" != "" ]]; then
        LINK_YOUTUBE="[![youtube](../links/svg/youtube.png (youtube))]($DB_YOUTUBE)"
        URL_YOUTUBE="$DB_YOUTUBE"
    else
        LINK_YOUTUBE="<!-- [![youtube](../links/svg/youtube.png (youtube))](youtube_not_in_db) -->"
        URL_YOUTUBE=""
    fi

    log_info "Enlaces generados desde base de datos"
}

create_database_post() {
    log_info "Creando post usando información de base de datos..."

    # Crear post base igual que antes
    create_hugo_post

    # Añadir contenido base (portada y enlaces)
    add_content_to_post

    # Añadir información específica de la base de datos (AMPLIADA)
    add_database_info_to_post

    # NUEVA: Añadir información extendida
    add_extended_database_info

    # Obtener tracklist si hay canciones en la base de datos
    if [[ "$DB_TOTAL_TRACKS" -gt 0 ]]; then
        add_database_tracklist
    fi

    # Descargar carátula desde ruta de la base de datos si está disponible
    if [[ -n "$DB_COVER_PATH" && "$DB_COVER_PATH" != "NULL" && "$DB_COVER_PATH" != "" ]]; then
        download_cover_from_database
    else
        # Usar el método tradicional si no hay carátula en la base de datos
        download_cover_art
    fi
}

add_database_info_to_post() {
    log_info "Añadiendo información de la base de datos al post..."

    # Información básica existente
    if [[ -n "$DB_GENRE" && "$DB_GENRE" != "NULL" && "$DB_GENRE" != "" ]]; then
        echo "" >> "$POST_FILE"
        echo "**Género:** $DB_GENRE" >> "$POST_FILE"
        echo "" >> "$POST_FILE"
    fi

    if [[ -n "$DB_RECORD_LABEL" && "$DB_RECORD_LABEL" != "NULL" && "$DB_RECORD_LABEL" != "" ]]; then
        echo "**Sello:** $DB_RECORD_LABEL" >> "$POST_FILE"
        echo "" >> "$POST_FILE"
    fi

    if [[ -n "$DB_RELEASE_YEAR" && "$DB_RELEASE_YEAR" != "NULL" && "$DB_RELEASE_YEAR" != "" ]]; then
        echo "**Año:** $DB_RELEASE_YEAR" >> "$POST_FILE"
        echo "" >> "$POST_FILE"
    fi

    if [[ -n "$DB_TOTAL_TRACKS" && "$DB_TOTAL_TRACKS" != "NULL" && "$DB_TOTAL_TRACKS" != "" && "$DB_TOTAL_TRACKS" != "0" ]]; then
        echo "**Total de pistas:** $DB_TOTAL_TRACKS" >> "$POST_FILE"
        echo "" >> "$POST_FILE"
    fi

    # NUEVAS SECCIONES DE INFORMACIÓN EXTENDIDA

    # Productores
    if [[ -n "$DB_PRODUCERS" && "$DB_PRODUCERS" != "NULL" && "$DB_PRODUCERS" != "" ]]; then
        echo "**Productores:** $DB_PRODUCERS" >> "$POST_FILE"
        echo "" >> "$POST_FILE"
    fi

    # Estudio de grabación
    if [[ -n "$DB_RECORDING_STUDIO" && "$DB_RECORDING_STUDIO" != "NULL" && "$DB_RECORDING_STUDIO" != "" ]]; then
        echo "**Estudio de grabación:** $DB_RECORDING_STUDIO" >> "$POST_FILE"
        echo "" >> "$POST_FILE"
    fi

    # Información técnica
    if [[ -n "$DB_MIXED_BY" && "$DB_MIXED_BY" != "NULL" && "$DB_MIXED_BY" != "" ]]; then
        echo "**Mezcla:** $DB_MIXED_BY" >> "$POST_FILE"
        echo "" >> "$POST_FILE"
    fi

    if [[ -n "$DB_MASTERED_BY" && "$DB_MASTERED_BY" != "NULL" && "$DB_MASTERED_BY" != "" ]]; then
        echo "**Masterización:** $DB_MASTERED_BY" >> "$POST_FILE"
        echo "" >> "$POST_FILE"
    fi

    # Notas adicionales
    if [[ -n "$DB_NOTES" && "$DB_NOTES" != "NULL" && "$DB_NOTES" != "" ]]; then
        echo "**Notas:**" >> "$POST_FILE"
        echo "$DB_NOTES" >> "$POST_FILE"
        echo "" >> "$POST_FILE"
    fi

    if [[ -n "$DB_ADDITIONAL_NOTES" && "$DB_ADDITIONAL_NOTES" != "NULL" && "$DB_ADDITIONAL_NOTES" != "" ]]; then
        echo "**Información adicional:**" >> "$POST_FILE"
        echo "$DB_ADDITIONAL_NOTES" >> "$POST_FILE"
        echo "" >> "$POST_FILE"
    fi

    log_info "Información de base de datos añadida al post"
}

add_extended_database_info() {
    log_info "Añadiendo información extendida de la base de datos..."

    # Obtener colaboradores y featured artists
    add_collaborators_info

    # Añadir información de equipboard si existe
    add_equipboard_info

    # Añadir feeds relacionados
    add_related_feeds_info

    # Añadir enlaces adicionales de servicios
    add_additional_service_links
}

add_collaborators_info() {
    log_info "Obteniendo información de colaboradores..."

    local collaborators_result
    collaborators_result=$(sqlite3 "$DATABASE_PATH" "
        SELECT DISTINCT
            ac.role,
            a.name,
            COALESCE(a.website, ''),
            COALESCE(a.spotify_url, ''),
            COALESCE(a.wikipedia_url, '')
        FROM album_contributors ac
        JOIN artists a ON ac.artist_id = a.id
        WHERE ac.album_id = '$DB_ALBUM_ID'
        ORDER BY ac.role, a.name;
    " 2>/dev/null) || {
        log_debug "No se encontraron colaboradores en la base de datos"
        return 0
    }

    if [[ -n "$collaborators_result" ]]; then
        echo "" >> "$POST_FILE"
        echo "**Colaboradores:**" >> "$POST_FILE"
        echo "" >> "$POST_FILE"

        local current_role=""
        while IFS='|' read -r role artist_name website spotify_url wikipedia_url; do
            if [[ "$role" != "$current_role" ]]; then
                echo "- **$role:**" >> "$POST_FILE"
                current_role="$role"
            fi

            local artist_line="  - $artist_name"
            local links=""

            # Añadir enlaces disponibles
            if [[ -n "$spotify_url" && "$spotify_url" != "NULL" ]]; then
                links="$links [🎵]($spotify_url)"
            fi
            if [[ -n "$wikipedia_url" && "$wikipedia_url" != "NULL" ]]; then
                links="$links [📖]($wikipedia_url)"
            fi
            if [[ -n "$website" && "$website" != "NULL" ]]; then
                links="$links [🌐]($website)"
            fi

            if [[ -n "$links" ]]; then
                artist_line="$artist_line $links"
            fi

            echo "$artist_line" >> "$POST_FILE"

        done <<< "$collaborators_result"

        echo "" >> "$POST_FILE"
    fi
}

add_equipboard_info() {
    log_info "Obteniendo información de equipboard..."

    local equipment_result
    equipment_result=$(sqlite3 "$DATABASE_PATH" "
        SELECT
            e.equipment_type,
            e.brand,
            e.model,
            COALESCE(e.equipboard_url, ''),
            COALESCE(e.notes, '')
        FROM equipment e
        JOIN artist_equipment ae ON e.id = ae.equipment_id
        WHERE ae.artist_id = '$DB_ARTIST_ID'
        ORDER BY e.equipment_type, e.brand, e.model;
    " 2>/dev/null) || {
        log_debug "No se encontró información de equipboard"
        return 0
    }

    if [[ -n "$equipment_result" ]]; then
        echo "" >> "$POST_FILE"
        echo "**Equipo utilizado:**" >> "$POST_FILE"
        echo "" >> "$POST_FILE"

        local current_type=""
        while IFS='|' read -r eq_type brand model equipboard_url notes; do
            if [[ "$eq_type" != "$current_type" ]]; then
                echo "- **$eq_type:**" >> "$POST_FILE"
                current_type="$eq_type"
            fi

            local equipment_line="  - $brand $model"

            if [[ -n "$equipboard_url" && "$equipboard_url" != "NULL" ]]; then
                equipment_line="$equipment_line [🎛️]($equipboard_url)"
            fi

            if [[ -n "$notes" && "$notes" != "NULL" ]]; then
                equipment_line="$equipment_line *(${notes})*"
            fi

            echo "$equipment_line" >> "$POST_FILE"

        done <<< "$equipment_result"

        echo "" >> "$POST_FILE"
    fi
}

add_related_feeds_info() {
    log_info "Obteniendo feeds relacionados..."

    local feeds_result
    feeds_result=$(sqlite3 "$DATABASE_PATH" "
        SELECT
            rf.feed_type,
            rf.title,
            rf.url,
            COALESCE(rf.description, '')
        FROM related_feeds rf
        WHERE (rf.artist_id = '$DB_ARTIST_ID' OR rf.album_id = '$DB_ALBUM_ID')
        ORDER BY rf.feed_type, rf.title;
    " 2>/dev/null) || {
        log_debug "No se encontraron feeds relacionados"
        return 0
    }

    if [[ -n "$feeds_result" ]]; then
        echo "" >> "$POST_FILE"
        echo "**Enlaces y feeds relacionados:**" >> "$POST_FILE"
        echo "" >> "$POST_FILE"

        local current_type=""
        while IFS='|' read -r feed_type title url description; do
            if [[ "$feed_type" != "$current_type" ]]; then
                echo "- **$feed_type:**" >> "$POST_FILE"
                current_type="$feed_type"
            fi

            local feed_line="  - [$title]($url)"

            if [[ -n "$description" && "$description" != "NULL" ]]; then
                feed_line="$feed_line - *${description}*"
            fi

            echo "$feed_line" >> "$POST_FILE"

        done <<< "$feeds_result"

        echo "" >> "$POST_FILE"
    fi
}

# Función auxiliar para convertir duración decimal a mm:ss
convert_duration_to_mmss() {
    local duration="$1"

    if [[ -z "$duration" || "$duration" == "NULL" || "$duration" == "" ]]; then
        echo ""
        return
    fi

    # Usar awk para manejar números decimales
    awk -v dur="$duration" '
    BEGIN {
        if (dur > 0) {
            minutes = int(dur / 60)
            seconds = int(dur % 60)
            printf "%d:%02d", minutes, seconds
        }
    }'
}

add_database_tracklist() {
    log_info "Obteniendo tracklist extendido desde base de datos..."

    local tracklist_result
    tracklist_result=$(sqlite3 "$DATABASE_PATH" "
        SELECT
            s.track_number,
            s.title,
            s.duration,
            sl.spotify_url,
            sl.youtube_url,
            sl.bandcamp_url,
            COALESCE(s.featured_artists, ''),
            COALESCE(s.notes, '')
        FROM songs s
        LEFT JOIN song_links sl ON s.id = sl.song_id
        WHERE s.artist = '$DB_ARTIST'
        AND s.album = '$DB_ALBUM'
        ORDER BY s.track_number;
    " 2>/dev/null) || {
        log_warn "Error obteniendo tracklist de la base de datos"
        return 1
    }

    if [[ -n "$tracklist_result" ]]; then
        echo "" >> "$POST_FILE"
        echo "**Tracklist:**" >> "$POST_FILE"
        echo "" >> "$POST_FILE"

        while IFS='|' read -r track_num title duration spotify_url youtube_url bandcamp_url featured_artists notes; do
            local track_line="**${track_num}.** $title"

            # Añadir featured artists
            if [[ -n "$featured_artists" && "$featured_artists" != "NULL" && "$featured_artists" != "" ]]; then
                track_line="$track_line *(feat. $featured_artists)*"
            fi

            # Añadir duración si está disponible
            if [[ -n "$duration" && "$duration" != "NULL" && "$duration" != "" ]]; then
                local formatted_duration=$(convert_duration_to_mmss "$duration")
                if [[ -n "$formatted_duration" ]]; then
                    track_line="$track_line *[$formatted_duration]*"
                fi
            fi

            # Añadir mini-iconos para enlaces disponibles
            local mini_icons=""
            if [[ -n "$spotify_url" && "$spotify_url" != "NULL" && "$spotify_url" != "" ]]; then
                mini_icons="$mini_icons [![🎵](../links/svg/spotify_mini.png)]($spotify_url)"
            fi
            if [[ -n "$youtube_url" && "$youtube_url" != "NULL" && "$youtube_url" != "" ]]; then
                mini_icons="$mini_icons [![📺](../links/svg/youtube_mini.png)]($youtube_url)"
            fi
            if [[ -n "$bandcamp_url" && "$bandcamp_url" != "NULL" && "$bandcamp_url" != "" ]]; then
                mini_icons="$mini_icons [![🏷️](../links/svg/bandcamp_mini.png)]($bandcamp_url)"
            fi

            echo "${track_line}${mini_icons}" >> "$POST_FILE"

            # Añadir notas de la canción si existen
            if [[ -n "$notes" && "$notes" != "NULL" && "$notes" != "" ]]; then
                echo "    *$notes*" >> "$POST_FILE"
            fi

            echo "" >> "$POST_FILE"

        done <<< "$tracklist_result"

        log_info "Tracklist extendido añadido desde base de datos"
    fi
}

download_cover_from_database() {
    log_info "Intentando usar carátula desde base de datos..."

    local post_folder="$(dirname "$POST_FILE")"
    cd "$post_folder" || exit 1

    # Si hay una ruta local de carátula, copiarla
    if [[ -n "$DB_COVER_PATH" && "$DB_COVER_PATH" != "NULL" && "$DB_COVER_PATH" != "" ]]; then
        if [[ -f "$DB_COVER_PATH" ]]; then
            cp "$DB_COVER_PATH" "image.jpeg"
            log_info "Carátula copiada desde ruta local: $DB_COVER_PATH"
            return 0
        else
            log_warn "Archivo de carátula no encontrado: $DB_COVER_PATH"
        fi
    fi

    # Si no hay carátula local, usar método tradicional
    log_info "No hay carátula disponible en base de datos, usando método tradicional"
    download_cover_art
}


# =============================================================================
# FUNCIONES DE BÚSQUEDA EN SERVICIOS MUSICALES
# =============================================================================

search_music_services() {
    log_info "Buscando enlaces en servicios musicales..."

    activate_python_env

    # Bandcamp
    log_info "Buscando en Bandcamp..."
    URL_BANDCAMP="$(python3 "$MODULES_DIR/bandcamp.py" "$ARTIST" "$ALBUM" | sed 's/\?from=.*//')"

    # Last.fm
    log_info "Buscando en Last.fm..."
    URL_LASTFM="$(bash "$MODULES_DIR/lastfm.sh" "$ARTIST" "$ALBUM")"

    # MusicBrainz
    log_info "Buscando en MusicBrainz..."
    URL_MUSICBRAINZ="$(python3 "$MODULES_DIR/musicbrainz.py" "$ARTIST" "$ALBUM")"

    # Spotify
    log_info "Buscando en Spotify..."
    URL_SPOTIFY="$(python3 "$MODULES_DIR/spotify.py" "$ARTIST" "$ALBUM")"

    # YouTube
    log_info "Buscando en YouTube..."
    URL_YOUTUBE="$(python3 "$MODULES_DIR/youtube.py" "$ARTIST" "$ALBUM")"

    # Wikipedia
    log_info "Buscando en Wikipedia..."
    URL_WIKIPEDIA="$(python3 "$MODULES_DIR/wikipedia.py" "$ARTIST" "$ALBUM" | tr -d '\n' | tr -d '\r')"

    # Discogs
    log_info "Buscando en Discogs..."
    rm -f "$BLOG_DIR/releases.txt"
    touch "$BLOG_DIR/releases.txt"
    MASTERID="$(python3 "$MODULES_DIR/discogs.py" "$ARTIST" "$ALBUM")"

    # Procesar resultado de Discogs
    if [[ "$MASTERID" == 'bash_script' ]]; then
        RELEASEID="$(python3 "$MODULES_DIR/release_id.py" "$ALBUM")"
        log_info "Release ID obtenido: $RELEASEID"
        if [[ -z "$RELEASEID" ]]; then
            log_warn "No se encontró release ID en Discogs"
        fi
    else
        if [[ "$MASTERID" =~ 'Error' ]]; then
            MASTERID="$(echo "$MASTERID" | sed 's/Error.*//')"
        fi
        URL_DISCOGS="https://www.discogs.com/master/$MASTERID"
        log_info "Master ID obtenido: $MASTERID"
    fi

    log_info "Búsqueda en servicios completada"
}

# =============================================================================
# FUNCIONES DE GENERACIÓN DE ENLACES
# =============================================================================

generate_service_links() {
    log_info "Generando enlaces para servicios..."

    # Bandcamp
    if [[ -z "$URL_BANDCAMP" ]]; then
        LINK_BANDCAMP="<!-- [![bandcamp](../links/svg/bandcamp.png (bandcamp))](${URL_BANDCAMP}) url vacia -->"
    elif [[ "$URL_BANDCAMP" =~ 'error' ]]; then
        LINK_BANDCAMP="<!-- [![bandcamp](../links/svg/bandcamp.png (bandcamp))](${URL_BANDCAMP}) error busqueda -->"
    else
        LINK_BANDCAMP="[![bandcamp](../links/svg/bandcamp.png (bandcamp))](https://bandcamp.com/search?q=$ARTIST_PROCESSED%20$ALBUM)"
    fi

    # Discogs
    if [[ -z "$URL_DISCOGS" ]]; then
        LINK_DISCOGS="<!-- [![discogs](../links/svg/discogs.png (discogs))](${URL_DISCOGS}) -->"
    else
        LINK_DISCOGS="[![discogs](../links/svg/discogs.png (discogs))](${URL_DISCOGS})"
    fi

    # Last.fm
    if [[ -z "$URL_LASTFM" ]]; then
        LINK_LASTFM="<!-- [![lastfm](../links/svg/lastfm.png (lastfm))]($URL_LASTFM) -->"
    elif [[ "$URL_LASTFM" =~ 'Por favor, proporciona un nombre de artista y álbum' ]]; then
        LINK_LASTFM="<!-- [![lastfm](../links/svg/lastfm.png (lastfm))]($URL_LASTFM) faltan argumentos -->"
    elif [[ "$URL_LASTFM" =~ 'Error con la api de Lastfm' ]]; then
        LINK_LASTFM="<!-- [![lastfm](../links/svg/lastfm.png (lastfm))]($URL_LASTFM) error api key -->"
    else
        LINK_LASTFM="[![lastfm](../links/svg/lastfm.png (lastfm))]($URL_LASTFM)"
    fi

    # MusicBrainz
    if [[ -z "$URL_MUSICBRAINZ" ]]; then
        LINK_MUSICBRAINZ="<!-- [![musicbrainz](../links/svg/musicbrainz.png (musicbrainz))]($URL_MUSICBRAINZ) -->"
    else
        LINK_MUSICBRAINZ="[![musicbrainz](../links/svg/musicbrainz.png (musicbrainz))]($URL_MUSICBRAINZ)"
    fi

    # Spotify
    if [[ -z "$URL_SPOTIFY" ]]; then
        LINK_SPOTIFY="<!-- [![spotify](../links/svg/spotify.png (spotify))]($URL_SPOTIFY) -->"
    elif [[ "$URL_SPOTIFY" =~ "Error" ]]; then
        log_error "Error en el script de Spotify"
        exit 1
    else
        LINK_SPOTIFY="[![spotify](../links/svg/spotify.png (spotify))]($URL_SPOTIFY)"
    fi

    # Wikipedia
    if [[ -z "$URL_WIKIPEDIA" ]]; then
        LINK_WIKIPEDIA="<!-- [![wikipedia](../links/svg/wikipedia.png (wikipedia))]($URL_WIKIPEDIA) -->"
    elif [[ "$URL_WIKIPEDIA" =~ "error" ]]; then
        LINK_WIKIPEDIA="<!-- [![wikipedia](../links/svg/wikipedia.png (wikipedia))]($URL_WIKIPEDIA) -->"
    elif [[ "$URL_WIKIPEDIA" != 'error' ]] && [[ "$URL_WIKIPEDIA" != 'None' ]]; then
        LINK_WIKIPEDIA="[![wikipedia](../links/svg/wikipedia.png (wikipedia))]($URL_WIKIPEDIA)"
    fi

    # YouTube
    if [[ -z "$URL_YOUTUBE" ]]; then
        LINK_YOUTUBE="<!-- [![youtube](../links/svg/youtube.png (youtube))]($URL_YOUTUBE) -->"
    else
        LINK_YOUTUBE="[![youtube](../links/svg/youtube.png (youtube))]($URL_YOUTUBE)"
    fi

    log_info "Enlaces generados"
}

# =============================================================================
# FUNCIONES DE CREACIÓN DEL POST
# =============================================================================

create_hugo_post() {
    log_info "Creando post de Hugo..."

    cd "$BLOG_DIR" || exit 1

    # Generar nombres de archivos
    local artist_with_underscore="${ARTIST} _"
    local post_pre="${artist_with_underscore}-${ALBUM}"
    local post_slug="$(echo "$post_pre" | sed 's/ /-/g' | sed 's/,//g')"
    POST_FILE="$BLOG_DIR/content/posts/${post_slug}/index.md"

    # Verificar si el post ya existe
    if [[ -f "$POST_FILE" ]]; then
        log_warn "El post ya existe: $POST_FILE"
        notify-send "Post existente" "El post para $ARTIST - $ALBUM ya existe"
        exit 0
    fi

    # Crear el post con Hugo
    hugo new --kind post-bundle "posts/${post_slug}"
    check_status $? "Post creado con Hugo" "Error al crear post con Hugo"

    log_info "Post creado: $POST_FILE"
}

add_content_to_post() {
    log_info "Añadiendo contenido al post..."

    # Añadir portada
    echo "![cover](image.jpeg ($ARTIST - $ALBUM))" >> "$POST_FILE"
    echo " " >> "$POST_FILE"

    # Clasificar enlaces
    local enlaces=("$LINK_BANDCAMP" "$LINK_DISCOGS" "$LINK_LASTFM" "$LINK_MUSICBRAINZ" "$LINK_SPOTIFY" "$LINK_WIKIPEDIA" "$LINK_YOUTUBE")
    local non_comment_vars=()
    local comment_vars=()

    for var in "${enlaces[@]}"; do
        if [[ "$var" == "<!-- "* ]]; then
            comment_vars+=("$var")
        else
            non_comment_vars+=("$var")
        fi
    done

    # Añadir enlaces activos
    for var in "${non_comment_vars[@]}"; do
        echo "$var" >> "$POST_FILE"
    done
    echo " " >> "$POST_FILE"

    # Añadir enlaces comentados
    for var in "${comment_vars[@]}"; do
        echo "$var" >> "$POST_FILE"
    done
    echo " " >> "$POST_FILE"

    log_info "Enlaces añadidos al post"
}

add_discogs_info() {
    log_info "Añadiendo información de Discogs..."

    activate_python_env

    if [[ "$MASTERID" != 'bash_script' ]]; then
        log_info "Añadiendo info desde master ID"
        python3 "$MODULES_DIR/info_discogs.py" "$MASTERID" "$POST_FILE"
        python3 "$MODULES_DIR/info_release_discogs_extraartists.py" "$MASTERID"
    elif [[ -n "${RELEASEID:-}" ]]; then
        log_info "Añadiendo info desde release ID"
        python3 "$MODULES_DIR/info_release_discogs.py" "$RELEASEID" "$POST_FILE"
        python3 "$MODULES_DIR/info_release_discogs_extraartists.py" "$RELEASEID"
    fi

    # Procesar información extra
    if [[ -f "$MODULES_DIR/discogs_info_extra.txt" ]]; then
        # Dividir archivo por tracklist
        csplit -f "$CACHE_DIR/tracklist_parts" --suppress-matched "$POST_FILE" '/Tracklist/' || true

        # Hacer backup
        mv "$POST_FILE" "${POST_FILE}.BAK"

        # Reconstruir archivo
        if [[ -f "$CACHE_DIR/tracklist_parts00" ]]; then
            mv "$CACHE_DIR/tracklist_parts00" "$POST_FILE"
        fi

        # Añadir info extra
        if [[ -f "$MODULES_DIR/discogs_info_extra.txt" ]]; then
            cat "$MODULES_DIR/discogs_info_extra.txt" >> "$POST_FILE"
        fi

        # Añadir tracklist
        echo '**Tracklist:**' >> "$POST_FILE"
        echo "" >> "$POST_FILE"

        if [[ -f "$CACHE_DIR/tracklist_parts01" ]]; then
            cat "$CACHE_DIR/tracklist_parts01" >> "$POST_FILE"
            rm -f "$CACHE_DIR/tracklist_parts01"
        fi
    fi

    log_info "Información de Discogs añadida"
}

download_cover_art() {
    log_info "Descargando carátula..."

    activate_python_env

    local post_folder="$(dirname "$POST_FILE")"
    cd "$post_folder" || exit 1

    # Intentar descargar desde Spotify primero
    local caratula_result
    caratula_result="$(python3 "$MODULES_DIR/caratula-spotify.py" "$ARTIST" "$ALBUM")"

    if [[ "$caratula_result" =~ "Error" ]]; then
        log_warn "Error descargando desde Spotify, intentando fuentes alternativas..."
        python3 "$MODULES_DIR/caratula-alternativa.py" "$ARTIST" "$ALBUM" "$post_folder"

        # Mover carátula si se descargó en ubicación alternativa
        local alt_cover="$BLOG_DIR/static/portadas/${ARTIST}-_-${ALBUM}.jpg"
        if [[ -f "$alt_cover" ]]; then
            cp "$alt_cover" "$post_folder/image.jpeg"
            log_info "Carátula descargada desde fuente alternativa"
        fi
    else
        cp "$caratula_result" "$post_folder/image.jpeg"
        log_info "Carátula descargada desde Spotify"
    fi

    # Verificar que la carátula existe
    if [[ ! -f "$post_folder/image.jpeg" ]]; then
        log_warn "No se pudo descargar la carátula"
    fi
}

add_tags_to_post() {
    log_info "Añadiendo tags al post..."

    # Añadir tags si existen
    local tag_patterns=("#- tagA" "#- tagB" "#- tagC" "#- tagD" "#tagE")

    for i in "${!TAGS_ARRAY[@]}"; do
        if [[ $i -lt ${#tag_patterns[@]} ]] && [[ -n "${TAGS_ARRAY[$i]:-}" ]]; then
            sed -i "s/${tag_patterns[$i]}/- ${TAGS_ARRAY[$i]}/" "$POST_FILE"
        fi
    done

    # Añadir contenido especial de pollo si existe
    if [[ -f "$CACHE_DIR/pollo.txt" ]]; then
        echo " " >> "$POST_FILE"
        cat "$CACHE_DIR/pollo.txt" >> "$POST_FILE"
        rm -f "$CACHE_DIR/pollo.txt"
    fi

    log_info "Tags añadidos al post"
}

format_post_content() {
    log_info "Formateando contenido del post..."

    # Comentar contenido de Discogs
    local start_line="Información del álbum facilitada por discogs.com:"
    local temp_file="$(mktemp)"
    local found_start_line=false

    while IFS= read -r line; do
        if $found_start_line; then
            echo "> $line" >> "$temp_file"
        else
            echo "$line" >> "$temp_file"
            if [[ "$line" == *"$start_line"* ]]; then
                found_start_line=true
            fi
        fi
    done < "$POST_FILE"

    mv "$temp_file" "$POST_FILE"

    # Cambiar estado de draft
    sed -i 's/draft: true/draft: false/' "$POST_FILE"

    log_info "Contenido formateado"
}

# =============================================================================
# FUNCIONES DE SPOTIFY INTEGRATION
# =============================================================================

add_to_spotify_playlist() {
    log_info "Añadiendo canción a playlist de Spotify (opcional)..."

    # Verificar si Spotify está habilitado
    if [[ "${ENABLE_SPOTIFY_INTEGRATION:-true}" == "false" ]]; then
        log_info "Integración con Spotify deshabilitada, saltando..."
        return 0
    fi

    # Activar entorno Python
    if ! activate_python_env; then
        log_warn "No se pudo activar entorno Python, saltando Spotify"
        return 0
    fi

    # Buscar canción en Spotify usando las variables correctas
    local song_data
    log_info "Buscando '$ARTIST - $TITLE_RAW' en Spotify..."

    song_data="$(python3 "$MODULES_DIR/sp_busca_cancion.py" "$ARTIST" "$TITLE_RAW" 2>/dev/null || echo "")"

    if [[ -z "$song_data" ]] || [[ "$song_data" =~ 'notoken' ]] || [[ "$song_data" =~ 'nocancion' ]]; then
        log_warn "No se pudo encontrar la canción en Spotify automáticamente"
        log_debug "Resultado búsqueda: $song_data"

        # Ofrecer búsqueda manual (opcional, no bloquear si se cancela)
        if command -v yad &> /dev/null; then
            local manual_search
            manual_search="$(yad --entry \
                --entry-text="$ARTIST - $TITLE_RAW" \
                --entry-label="Artista - Canción (búsqueda manual):" \
                --title="Búsqueda manual en Spotify" \
                --button="Buscar:0" \
                --button="Saltar:1" \
                --timeout=10 2>/dev/null || echo "")"

            local yad_exit=$?

            if [[ $yad_exit -eq 1 ]] || [[ $yad_exit -eq 70 ]] || [[ -z "$manual_search" ]]; then
                log_info "Usuario saltó la búsqueda en Spotify"
                notify-send "VVMM Post Creator" "Post creado sin añadir a Spotify"
                return 0
            fi

            if [[ -n "$manual_search" ]]; then
                # Separar artista y título de la búsqueda manual
                local manual_artist manual_title
                if [[ "$manual_search" =~ - ]]; then
                    manual_artist="$(echo "$manual_search" | cut -d'-' -f1 | xargs)"
                    manual_title="$(echo "$manual_search" | cut -d'-' -f2- | xargs)"
                else
                    manual_artist="$ARTIST"
                    manual_title="$manual_search"
                fi

                song_data="$(python3 "$MODULES_DIR/sp_busca_cancion.py" "$manual_artist" "$manual_title" 2>/dev/null || echo "")"

                if [[ "$song_data" =~ 'nocancion' ]] || [[ -z "$song_data" ]]; then
                    log_warn "Búsqueda manual en Spotify también falló"
                    notify-send "VVMM Post Creator" "Post creado, pero no se encontró en Spotify"
                    return 0
                fi
            fi
        else
            log_warn "yad no disponible para búsqueda manual, saltando Spotify"
            return 0
        fi
    fi

    # Extraer ID y URL de la canción
    local song_id song_url
    song_id="$(echo "$song_data" | awk 'NR==1' | tr -d '\n\r')"
    song_url="$(echo "$song_data" | awk 'NR==2' | tr -d '\n\r')"

    if [[ -z "$song_id" ]] || [[ "$song_id" == "nocancion" ]]; then
        log_warn "No se obtuvo ID válido de la canción en Spotify"
        notify-send "VVMM Post Creator" "Post creado, pero no se encontró en Spotify"
        return 0
    fi

    log_info "Canción encontrada en Spotify (ID: ${song_id:0:10}...)"

    # Mostrar menú de playlists (también opcional)
    local playlist_id
    if command -v python3 &> /dev/null && [[ -f "$MODULES_DIR/sp_menu_playlists.py" ]]; then
        playlist_id="$(python3 "$MODULES_DIR/sp_menu_playlists.py" 2>/dev/null || echo "")"

        if [[ -z "$playlist_id" ]]; then
            log_info "Usuario canceló selección de playlist"
            notify-send "VVMM Post Creator" "Post creado, pero no se añadió a playlist"
            return 0
        fi

        if [[ "$playlist_id" =~ "nuevalista" ]]; then
            local pl_name
            pl_name="$(yad --entry \
                --entry-label="Nombre de la playlist" \
                --title="Nueva playlist de Spotify" \
                --timeout=30 2>/dev/null || echo "")"

            if [[ -z "$pl_name" ]]; then
                log_info "Usuario canceló creación de playlist"
                notify-send "VVMM Post Creator" "Post creado, pero no se creó playlist"
                return 0
            fi

            playlist_id="$(python3 "$MODULES_DIR/sp_crear_playlist.py" "$pl_name" 2>/dev/null || echo "")"

            if [[ -z "$playlist_id" ]]; then
                log_warn "No se pudo crear la playlist '$pl_name'"
                notify-send "VVMM Post Creator" "Post creado, pero falló creación de playlist"
                return 0
            fi

            log_info "Playlist creada: $pl_name"
        fi
    else
        log_warn "No se puede mostrar menú de playlists, saltando..."
        return 0
    fi

    # Verificar duplicados (opcional, no bloquear si falla)
    local duplicate_check
    duplicate_check="$(python3 "$MODULES_DIR/sp_duplicate.py" "$playlist_id" "$song_id" 2>/dev/null || echo "")"

    if [[ "$duplicate_check" =~ "duplicado" ]]; then
        log_warn "La canción ya está en la playlist seleccionada"
        notify-send "VVMM Post Creator" "Post creado - Canción ya estaba en playlist"
        return 0
    fi

    # Añadir canción a playlist
    log_info "Añadiendo canción a playlist..."
    if python3 "$MODULES_DIR/sp_add_song_to_playlist.py" "$song_id" "$playlist_id" 2>/dev/null; then
        log_info "✅ Canción añadida a playlist de Spotify exitosamente"

        # Mostrar confirmación con carátula si está disponible
        show_spotify_success_notification "$playlist_id"

        return 0
    else
        log_warn "Error al añadir canción a playlist, pero post creado exitosamente"
        notify-send "VVMM Post Creator" "Post creado, pero falló al añadir a playlist"
        return 0
    fi
}


show_spotify_success_notification() {
    local playlist_id="$1"
    local playlist_url="https://open.spotify.com/playlist/${playlist_id}"

    # Buscar carátula del post
    local cover_file=""
    if [[ -n "${POST_FILE:-}" ]]; then
        cover_file="$(dirname "$POST_FILE")/image.jpeg"
    fi

    # Mostrar notificación con o sin carátula
    if [[ -f "$cover_file" ]] && command -v yad &> /dev/null; then
        local user_choice
        user_choice="$(yad --picture \
            --size=fit \
            --width=400 --height=400 \
            --filename="$cover_file" \
            --timeout=8 \
            --text="✅ $ARTIST - $TITLE_RAW\n🎵 Añadido a playlist de Spotify" \
            --button="🎧 Abrir playlist:2" \
            --button="✅ Continuar:0" 2>/dev/null || echo "")"

        if [[ $? -eq 2 ]]; then
            # Abrir playlist en navegador
            open_url "$playlist_url"
        fi
    else
        notify-send "🎵 VVMM + Spotify" "✅ $ARTIST - $TITLE_RAW añadido a playlist"
    fi
}
open_url() {
    local url="$1"

    if command -v xdg-open &> /dev/null; then
        xdg-open "$url" 2>/dev/null &
    elif command -v chromium &> /dev/null; then
        chromium "$url" 2>/dev/null &
    elif command -v firefox &> /dev/null; then
        firefox "$url" 2>/dev/null &
    else
        log_warn "No se encontró navegador para abrir: $url"
        echo "🔗 Abre manualmente: $url"
    fi
}

# =============================================================================
# FUNCIONES ACTUALIZADAS PARA PLAYERCTL METADATA
# =============================================================================

# Función para detectar el reproductor activo
get_active_player() {
    # Obtener lista de reproductores disponibles
    local players
    players="$(playerctl -l 2>/dev/null || echo "")"

    if [[ -z "$players" ]]; then
        return 1
    fi

    # Preferencias de reproductores (del más específico al más genérico)
    local preferred_players=(
        "deadbeef"
        "strawberry"
        "rhythmbox"
        "vlc"
        "spotify"
        "firefox"
        "chromium"
        "chrome"
    )

    # Buscar reproductor preferido que esté activo y reproduciendo
    for preferred in "${preferred_players[@]}"; do
        for player in $players; do
            if [[ "$player" == *"$preferred"* ]]; then
                # Verificar si está reproduciendo
                local status
                status="$(playerctl -p "$player" status 2>/dev/null || echo "Stopped")"
                if [[ "$status" == "Playing" ]]; then
                    echo "$player"
                    return 0
                fi
            fi
        done
    done

    # Si no hay reproductor preferido activo, usar el primero que esté reproduciendo
    for player in $players; do
        local status
        status="$(playerctl -p "$player" status 2>/dev/null || echo "Stopped")"
        if [[ "$status" == "Playing" ]]; then
            echo "$player"
            return 0
        fi
    done

    # Si ninguno está reproduciendo, usar el primero disponible
    echo "$players" | head -n1
    return 0
}

# Función actualizada para obtener metadata usando playerctl
get_current_song_metadata() {
    log_info "Obteniendo metadata de la canción en reproducción..."

    # Detectar reproductor activo
    local active_player
    active_player="$(get_active_player)"

    if [[ -z "$active_player" ]] || [[ "$active_player" == "none" ]]; then
        log_error "No se encontró ningún reproductor activo"
        notify-send -u critical "Error" "No hay reproductores de música activos"
        return 1
    fi

    log_debug "Reproductor detectado: $active_player"

    # Obtener metadata usando playerctl
    local artist album title

    artist="$(playerctl -p "$active_player" metadata artist 2>/dev/null || echo "")"
    album="$(playerctl -p "$active_player" metadata album 2>/dev/null || echo "")"
    title="$(playerctl -p "$active_player" metadata title 2>/dev/null || echo "")"

    # Verificar que tenemos datos mínimos
    if [[ -z "$artist" ]] || [[ -z "$title" ]]; then
        log_error "No se pudo obtener metadata suficiente"
        log_debug "Artist: '$artist', Title: '$title', Album: '$album'"

        # Intentar obtener de xesam (formato extendido)
        artist="${artist:-$(playerctl -p "$active_player" metadata xesam:artist 2>/dev/null || echo "")}"
        album="${album:-$(playerctl -p "$active_player" metadata xesam:album 2>/dev/null || echo "")}"
        title="${title:-$(playerctl -p "$active_player" metadata xesam:title 2>/dev/null || echo "")}"

        if [[ -z "$artist" ]] || [[ -z "$title" ]]; then
            notify-send -u critical "Error" "No se pudo obtener información de la canción"
            return 1
        fi
    fi

    # Limpiar metadata
    ARTIST_RAW="$(echo "$artist" | sed 's/[\":]//g')"
    TITLE_RAW="$(echo "$title" | sed 's/[\":]//g')"
    ALBUM_RAW="$(echo "$album" | sed 's/[\":]//g')"

    # Si no hay álbum, intentar usar el título como álbum (para singles)
    if [[ -z "$ALBUM_RAW" ]]; then
        ALBUM_RAW="$TITLE_RAW"
        log_warn "No se encontró álbum, usando título como álbum"
    fi

    # Limpiar variables usando la función existente
    ARTIST="$(clean_variable "$ARTIST_RAW")"
    ALBUM="$(clean_variable "$ALBUM_RAW")"

    # Procesar artista para formato post
    ARTIST_PROCESSED="$(echo "$ARTIST" | sed -E "s/[áÁ]/-/g; s/\(.*\)//g; s/&/and/g; s/[éÉ]/e/g; s/[íÍ]/i/g; s/[óÓ]/o/g; s/[úÚ]/u/g; s/['\`]/-/g; s/---/-/g; s/--/-/g; s/\ /-/g; s/^-//g; s/-$//g")"
    ALBUM_PROCESSED="$(echo "$ALBUM" | sed -E "s/[áÁ]/-/g; s/\(.*\)//g; s/&/and/g; s/[éÉ]/e/g; s/[íÍ]/i/g; s/[óÓ]/o/g; s/[úÚ]/u/g; s/['\`]/-/g; s/---/-/g; s/--/-/g; s/\ /-/g; s/^-//g; s/-$//g")"

    log_info "Metadata obtenida: $ARTIST - $ALBUM"
    log_debug "Título: $TITLE_RAW"
    log_debug "Reproductor: $active_player"

    return 0
}

# Función para mostrar información detallada del reproductor (debug)
show_player_debug_info() {
    local player="$1"

    if [[ -z "$player" ]]; then
        log_error "No se especificó reproductor para debug"
        return 1
    fi

    log_debug "=== Información detallada del reproductor ==="
    log_debug "Reproductor: $player"
    log_debug "Estado: $(playerctl -p "$player" status 2>/dev/null || echo "N/A")"
    log_debug "Posición: $(playerctl -p "$player" position 2>/dev/null || echo "N/A")"
    log_debug "Duración: $(playerctl -p "$player" metadata mpris:length 2>/dev/null || echo "N/A")"
    log_debug "URL: $(playerctl -p "$player" metadata xesam:url 2>/dev/null || echo "N/A")"

    log_debug "--- Metadata disponible ---"
    # Mostrar todo el metadata disponible
    if [[ "${DEBUG_MODE:-false}" == "true" ]]; then
        playerctl -p "$player" metadata 2>/dev/null | while read -r line; do
            log_debug "  $line"
        done
    fi
    log_debug "=== Fin información del reproductor ==="
}

# Función para validar que playerctl está disponible
validate_playerctl() {
    if ! command -v playerctl &> /dev/null; then
        log_error "playerctl no está instalado"
        notify-send -u critical "Error" "playerctl no está instalado. Instálalo para continuar."
        return 1
    fi

    # Verificar si hay reproductores disponibles
    local players
    players="$(playerctl -l 2>/dev/null || echo "")"

    if [[ -z "$players" ]]; then
        log_error "No hay reproductores disponibles"
        notify-send -u critical "Error" "No hay reproductores de música disponibles"
        return 1
    fi

    log_debug "Reproductores disponibles: $players"
    return 0
}


# =============================================================================
# FUNCIONES DE PUBLICACIÓN
# =============================================================================

build_and_publish() {
    log_info "Construyendo y publicando sitio..."

    cd "$BLOG_DIR" || exit 1

    # Construir sitio con Hugo
    hugo
    check_status $? "Sitio construido con Hugo" "Error al construir sitio"

    # Subir a GitHub
    if [[ "${ENABLE_GIT_PUSH:-true}" == "true" ]]; then
        log_info "Subiendo cambios a GitHub..."

        eval "$(ssh-agent -s)"
        ssh-add $SSH_KEY_GITHUB

        git add .
        git commit -m "$ARTIST $ALBUM"
        git push

        check_status $? "Cambios subidos a GitHub" "Error al subir a GitHub"
    else
        log_info "Publicación en GitHub deshabilitada"
    fi
}

preview_site() {
    log_info "Iniciando servidor de preview..."

    cd "$BLOG_DIR" || exit 1

    # Iniciar servidor Hugo en background
    nohup hugo server --bind 0.0.0.0 --baseURL "http://localhost" > "$LOGS_DIR/hugo_server.log" 2>&1 &
    local hugo_pid=$!
    echo "$hugo_pid" > "$CACHE_DIR/hugo_pid.txt"

    sleep 2

    # Abrir navegador
    local post_slug="${ARTIST_PROCESSED}-_-${ALBUM_PROCESSED}"
    qutebrowser --target auto "http://localhost:1313/posts/${post_slug}" &
    local qute_pid=$!

    # Esperar o timeout
    local timeout=20
    local count=0
    while [[ $count -lt $timeout ]] && kill -0 $qute_pid 2>/dev/null; do
        sleep 1
        ((count++))
    done

    # Limpiar procesos
    kill "$hugo_pid" 2>/dev/null || true
    kill "$qute_pid" 2>/dev/null || true
    rm -f "$CACHE_DIR/hugo_pid.txt"

    log_info "Preview completado"
}

# =============================================================================
# FUNCIÓN PRINCIPAL
# =============================================================================

main() {
    log_info "=== Iniciando VVMM Post Creator ==="
    log_info "Timestamp: $(date)"

    local main_success=true
    local use_database=false

    # 1. Obtener metadata de la canción actual
    if ! get_current_song_metadata; then
        log_error "Error fatal: No se pudo obtener metadata de la canción"
        exit 1
    fi

    # 2. NUEVA FUNCIONALIDAD: Verificar base de datos primero
    log_info "🔍 Verificando base de datos antes de usar scripts..."
    if check_database_first; then
        log_info "✅ Información encontrada en base de datos, saltando búsquedas en servicios"
        use_database=true
    else
        log_info "ℹ️  No encontrado en base de datos, usando flujo tradicional"
        use_database=false
    fi

    # Si usamos base de datos, saltamos la mayoría de pasos
    if [[ "$use_database" == "true" ]]; then
        log_info "📝 Completando post con información de base de datos..."

        # Solo necesitamos tags del usuario y algunos pasos finales
        if ! get_user_tags; then
            log_error "Error fatal: No se pudieron obtener tags del usuario"
            exit 1
        fi

        # Añadir tags al post ya creado
        if ! add_tags_to_post; then
            log_error "Error fatal: No se pudieron añadir tags al post"
            exit 1
        fi

        # Formatear contenido
        if ! format_post_content; then
            log_error "Error fatal: No se pudo formatear contenido del post"
            exit 1
        fi

    else
        # Flujo tradicional completo cuando no está en base de datos
        log_info "🔧 Ejecutando flujo tradicional completo..."

        # 2. Solicitar tags al usuario
        if ! get_user_tags; then
            log_error "Error fatal: No se pudieron obtener tags del usuario"
            exit 1
        fi

        # 3. Actualizar playlists de Spotify (no crítico)
        if ! update_spotify_playlists; then
            log_warn "Error actualizando playlists de Spotify, continuando..."
            main_success=false
        fi

        # 4. Buscar en servicios musicales (no crítico si algunos fallan)
        if ! search_music_services; then
            log_warn "Error en búsqueda de servicios musicales, continuando..."
            main_success=false
        fi

        # 5. Generar enlaces
        generate_service_links

        # 6. Crear post de Hugo (crítico)
        if ! create_hugo_post; then
            log_error "Error fatal: No se pudo crear post de Hugo"
            exit 1
        fi

        # 7. Añadir contenido al post (crítico)
        if ! add_content_to_post; then
            log_error "Error fatal: No se pudo añadir contenido al post"
            exit 1
        fi

        # 8. Añadir información de Discogs (no crítico)
        if ! add_discogs_info; then
            log_warn "Error añadiendo información de Discogs, continuando..."
            main_success=false
        fi

        # 9. Descargar carátula (no crítico)
        if ! download_cover_art; then
            log_warn "Error descargando carátula, continuando..."
            main_success=false
        fi

        # 10. Añadir tags (crítico)
        if ! add_tags_to_post; then
            log_error "Error fatal: No se pudieron añadir tags al post"
            exit 1
        fi

        # 11. Formatear contenido (crítico)
        if ! format_post_content; then
            log_error "Error fatal: No se pudo formatear contenido del post"
            exit 1
        fi
    fi

    # Pasos comunes para ambos flujos

    # 12. Añadir a playlist de Spotify (OPCIONAL)
    log_info "Intentando añadir a playlist de Spotify..."
    if add_to_spotify_playlist; then
        log_info "✅ Integración con Spotify completada"
    else
        log_warn "⚠️  Integración con Spotify falló o fue saltada"
        main_success=false
    fi

    # 13. Preview del sitio (no crítico)
    if [[ "${ENABLE_PREVIEW:-true}" == "true" ]]; then
        log_info "Mostrando preview del sitio..."
        if ! preview_site; then
            log_warn "Error en preview del sitio, continuando..."
            main_success=false
        fi
    else
        log_info "Preview del sitio deshabilitado"
    fi

    # 14. Construir y publicar (crítico)
    if ! build_and_publish; then
        log_error "Error en construcción o publicación del sitio"
        main_success=false
    fi

    # 15. Finalizar con éxito/advertencias
    if [[ "$main_success" == "true" ]]; then
        if [[ "$use_database" == "true" ]]; then
            notify-send "🎵 Post creado desde DB" "Post creado exitosamente usando base de datos para $ARTIST - $ALBUM"
            log_info "✅ Post creado exitosamente usando información de base de datos"
        else
            notify-send "🎵 Post creado" "Post creado exitosamente para $ARTIST - $ALBUM"
            log_info "✅ Post creado exitosamente usando búsquedas en servicios"
        fi
    else
        notify-send "⚠️ Post creado con warnings" "Post creado para $ARTIST - $ALBUM pero con algunos errores menores"
        log_warn "⚠️ Post creado pero algunos componentes fallaron"
    fi

    log_info "=== VVMM Post Creator finalizado ==="
}

show_final_summary() {
    local success="$1"

    echo
    log_info "=== RESUMEN FINAL ==="

    if [[ "$success" == "true" ]]; then
        log_info "✅ Post creado EXITOSAMENTE"
        notify-send -t 8000 "🎉 VVMM Post Creator" "✅ Post creado exitosamente\n🎵 $ARTIST - $ALBUM"
    else
        log_warn "⚠️  Post creado con ADVERTENCIAS"
        notify-send -t 8000 "⚠️ VVMM Post Creator" "Post creado con advertencias\n🎵 $ARTIST - $ALBUM"
    fi

    echo
    log_info "📊 Información del post:"
    log_info "  Artista: $ARTIST"
    log_info "  Álbum: $ALBUM"
    log_info "  Título: ${TITLE_RAW:-N/A}"
    log_info "  Tags: ${TAGS_ARRAY[*]:-ninguno}"
    log_info "  Archivo: ${POST_FILE:-N/A}"

    # Mostrar URLs útiles
    if [[ -n "${POST_FILE:-}" ]]; then
        local post_slug="${ARTIST_PROCESSED}-_-${ALBUM_PROCESSED}"
        local post_url="https://tu-dominio.com/posts/${post_slug}"
        log_info "  URL del post: $post_url"
    fi

    # Debug: Mostrar contenido final si está habilitado
    if [[ "${DEBUG_MODE:-false}" == "true" ]] && [[ -f "${POST_FILE:-}" ]]; then
        log_debug "Contenido final del post:"
        echo "=================" >> "$LOG_FILE"
        cat "$POST_FILE" >> "$LOG_FILE"
        echo "=================" >> "$LOG_FILE"
    fi

    # Mostrar estadísticas del log
    local total_errors total_warnings
    total_errors="$(grep -c "\[ERROR\]" "$LOG_FILE" 2>/dev/null || echo "0")"
    total_warnings="$(grep -c "\[WARN\]" "$LOG_FILE" 2>/dev/null || echo "0")"

    if [[ "$total_errors" -gt 0 ]] || [[ "$total_warnings" -gt 0 ]]; then
        log_info "📋 Estadísticas:"
        log_info "  Errores: $total_errors"
        log_info "  Advertencias: $total_warnings"
        log_info "  Log completo: $LOG_FILE"
    fi

    echo
    log_info "🎵 ¡Gracias por usar VVMM Post Creator!"
}


# =============================================================================
# MANEJO DE ERRORES Y LIMPIEZA
# =============================================================================

cleanup() {
    log_info "Ejecutando limpieza..."

    # Matar procesos Hugo si están corriendo
    if [[ -f "$CACHE_DIR/hugo_pid.txt" ]]; then
        local hugo_pid="$(cat "$CACHE_DIR/hugo_pid.txt")"
        kill "$hugo_pid" 2>/dev/null || true
        rm -f "$CACHE_DIR/hugo_pid.txt"
    fi

    # Limpiar archivos temporales
    rm -f "$CACHE_DIR"/tracklist_parts*
    rm -f "$MODULES_DIR/discogs_info_extra.txt"

    log_info "Limpieza completada"
}

# Configurar trap para limpieza en salida
trap cleanup EXIT INT TERM

# =============================================================================
# VALIDACIONES INICIALES
# =============================================================================

validate_environment() {
    log_info "Validando entorno..."

    # Verificar directorios
    local required_dirs=("$MODULES_DIR" "$BLOG_DIR" "$LOGS_DIR" "$CACHE_DIR")
    for dir in "${required_dirs[@]}"; do
        if [[ ! -d "$dir" ]]; then
            log_error "Directorio requerido no encontrado: $dir"
            exit 1
        fi
    done

    # Verificar comandos requeridos - AÑADIR playerctl
    local required_commands=("hugo" "python3" "git" "yad" "notify-send" "qutebrowser" "playerctl")
    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            log_error "Comando requerido no encontrado: $cmd"
            exit 1
        fi
    done

    # Validar playerctl específicamente
    validate_playerctl

    # Verificar scripts de módulos
    local required_modules=(
        "limpia_var.sh"
        "bandcamp.py"
        "lastfm.sh"
        "musicbrainz.py"
        "spotify.py"
        "youtube.py"
        "wikipedia.py"
        "discogs.py"
        "release_id.py"
        "caratula-spotify.py"
        "caratula-alternativa.py"
        "sp_playlist.py"
        "sp_playlist_md.py"
        "sp_busca_cancion.py"
        "sp_crear_playlist.py"
        "sp_duplicate.py"
        "sp_add_song_to_playlist.py"
    )

    for module in "${required_modules[@]}"; do
        if [[ ! -f "$MODULES_DIR/$module" ]]; then
            log_error "Módulo requerido no encontrado: $MODULES_DIR/$module"
            exit 1
        fi
    done

    # Verificar script de reproducción
    if [[ ! -f "/home/huan/Scripts/utilities/aliases/en_reproduccion.sh" ]]; then
        log_error "Script de reproducción no encontrado"
        exit 1
    fi

    # Verificar menú de playlists
    if [[ ! -f "/home/huan/Scripts/menus/spotify/sp_menu_playlists.py" ]]; then
        log_error "Menú de playlists no encontrado"
        exit 1
    fi

    # Verificar comandos requeridos
    local required_commands=("hugo" "python3" "git" "yad" "notify-send" "qutebrowser")
    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            log_error "Comando requerido no encontrado: $cmd"
            exit 1
        fi
    done

    # Verificar variables de entorno críticas
    local required_env_vars=("SPOTIFY_CLIENT" "SPOTIFY_SECRET" "DISCOGS_TOKEN")
    for var in "${required_env_vars[@]}"; do
        if [[ -z "${!var:-}" ]]; then
            log_error "Variable de entorno requerida no configurada: $var"
            exit 1
        fi
    done

    log_info "Validación de entorno completada"
}

show_help() {
    cat << EOF
VVMM Post Creator - Creador automático de posts para blog musical

USO:
    $0 [opciones]

OPCIONES:
    -h, --help          Mostrar esta ayuda
    -d, --debug         Activar modo debug
    --no-preview        Deshabilitar preview del sitio
    --no-git            Deshabilitar push a GitHub
    --validate-only     Solo validar entorno y salir

DESCRIPCIÓN:
    Este script automatiza la creación de posts para el blog VVMM basándose en
    la música actualmente en reproducción. Integra múltiples servicios musicales
    y gestiona todo el flujo desde la obtención de metadatos hasta la publicación.

ESTRUCTURA REQUERIDA:
    proyecto/
    ├── .env                    # Variables de entorno
    ├── .content/
    │   ├── logs/              # Logs de la aplicación
    │   └── cache/             # Cache y archivos temporales
    ├── modules/               # Scripts de módulos
    └── vvmm_post_creator.sh   # Este script

VARIABLES DE ENTORNO REQUERIDAS:
    SPOTIFY_CLIENT          # Client ID de Spotify API
    SPOTIFY_SECRET          # Client Secret de Spotify API
    DISCOGS_TOKEN          # Token de Discogs API
    LASTFM_API_KEY         # API Key de Last.fm (opcional)
    YT_TOKEN               # Token de YouTube API (opcional)
    PYTHON_VENV_PATH       # Ruta al entorno virtual Python (opcional)

EJEMPLOS:
    $0                     # Ejecución normal
    $0 --debug             # Con debug activado
    $0 --no-preview        # Sin preview del sitio
    $0 --validate-only     # Solo validar entorno

Para más información, consulta la documentación del proyecto.
EOF
}

# =============================================================================
# PROCESAMIENTO DE ARGUMENTOS
# =============================================================================

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -d|--debug)
                export DEBUG_MODE=true
                log_info "Modo debug activado"
                ;;
            --no-preview)
                export ENABLE_PREVIEW=false
                log_info "Preview del sitio deshabilitado"
                ;;
            --no-git)
                export ENABLE_GIT_PUSH=false
                log_info "Push a GitHub deshabilitado"
                ;;
            --validate-only)
                validate_environment
                log_info "Validación completada exitosamente"
                exit 0
                ;;
            *)
                log_error "Opción desconocida: $1"
                echo "Usa $0 --help para ver las opciones disponibles"
                exit 1
                ;;
        esac
        shift
    done
}

# =============================================================================
# PUNTO DE ENTRADA
# =============================================================================

# Procesar argumentos de línea de comandos
parse_arguments "$@"

# Validar entorno antes de ejecutar
validate_environment

# Ejecutar función principal
main

# Salida exitosa
log_info "VVMM Post Creator completado exitosamente"
exit 0
