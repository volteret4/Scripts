#!/usr/bin/env bash
#
# Script Name: _comun.sh
# Description: Funciones compartidas por los *_metadata.sh: metadata de lo que suena
#              y abrir la búsqueda en el navegador.
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# Notes:
#   Se usa con "source", no se ejecuta directamente.
#   Navegador: el que esté enfocado si es uno conocido; si no, Zen ($NAVEGADOR lo cambia).
#   Dependencies: - playerctl      - xdotool      - python3      - zen-browser
#

NAVEGADOR="${NAVEGADOR:-zen-browser}"

# Reproductor activo: strawberry si suena, si no el primero que esté sonando,
# si no el primero que haya. Todos (DeaDBeeF incluido) vía MPRIS/playerctl.
reproductor_activo() {
    local p
    if [[ "$(playerctl -p strawberry status 2>/dev/null)" == "Playing" ]]; then
        echo strawberry
        return
    fi
    for p in $(playerctl -l 2>/dev/null); do
        if [[ "$(playerctl -p "$p" status 2>/dev/null)" == "Playing" ]]; then
            echo "$p"
            return
        fi
    done
    playerctl -l 2>/dev/null | head -n 1
}

# Rellena las variables artista, cancion y album
obtener_metadata() {
    local player
    player="$(reproductor_activo)"
    if [[ -z "$player" ]]; then
        notify-send -u critical "Búsqueda" "No hay ningún reproductor activo"
        exit 1
    fi
    artista="$(playerctl -p "$player" metadata xesam:artist 2>/dev/null | head -n 1)"
    cancion="$(playerctl -p "$player" metadata xesam:title 2>/dev/null)"
    album="$(playerctl -p "$player" metadata xesam:album 2>/dev/null)"
}

urlencode() {
    python3 -c 'import sys, urllib.parse; print(urllib.parse.quote_plus(sys.argv[1]))' "$1"
}

# Abre la url en el navegador enfocado si es uno conocido; si no, en Zen
abrir_url() {
    local url="$1" ventana
    ventana="$(xdotool getactivewindow getwindowname 2>/dev/null)"
    case "$ventana" in
        *"Zen Browser"*)      zen-browser "$url" ;;
        *"Mozilla Firefox"*)  firefox "$url" ;;
        *Chromium*)           chromium "$url" ;;
        *Thorium)             thorium-browser "$url" ;;
        *Floorp*)             floorp "$url" ;;
        *)                    "$NAVEGADOR" "$url" ;;
    esac > /dev/null 2>&1 &
    disown
}

# Busca el texto en Nicotine+ (necesita el plugin "Búsqueda externa" activado).
# Quita la puntuación: en Soulseek "-palabra" excluye resultados.
buscar_nicotine() {
    local termino
    termino="$(echo "$1" | sed 's/[][(){}"'"'"'.,:;!?&/_+*-]/ /g; s/  */ /g; s/^ //; s/ $//')"
    [[ -z "$termino" ]] && return 1
    echo "$termino" >> "${XDG_RUNTIME_DIR:-/tmp}/nicotine_busqueda"
    # Si ya está abierto, la segunda instancia solo trae la ventana al frente
    nicotine > /dev/null 2>&1 &
    disown
}
