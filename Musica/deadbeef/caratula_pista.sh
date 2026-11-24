#!/usr/bin/env bash
# Carátula de una pista: imprime la ruta de una miniatura PNG en caché.
# Sale con 1 y sin imprimir nada si la pista no tiene carátula.
#
# Orden: embebida en el archivo (cada pista de Mix lleva la suya), imagen con
# nombre típico en la carpeta o en sus subcarpetas de arte, cualquier imagen de
# la carpeta. La miniatura evita que awesome se bloquee con un cover.jpg enorme.
#
# Uso: caratula_pista.sh /ruta/a/pista.flac

audio=${1:-}
[ -f "$audio" ] || exit 1

SIZE=300
CACHE=${XDG_CACHE_HOME:-$HOME/.cache}/caratulas_pistas
mkdir -p "$CACHE" || exit 1

# Con la fecha del archivo en la clave, una carátula nueva invalida la anterior
key=$(printf '%s|%s' "$audio" "$(stat -c %Y "$audio")" | md5sum | cut -d' ' -f1)
out=$CACHE/$key.png
if [ -s "$out" ]; then
    echo "$out"
    exit 0
fi

tmp=$(mktemp "$CACHE/.tmp.XXXXXX") || exit 1
trap 'rm -f "$tmp"' EXIT

miniatura() {
    ffmpeg -nostdin -v quiet -y -i "$1" -an -map 0:v:0 -frames:v 1 \
        -vf "scale=$SIZE:$SIZE:force_original_aspect_ratio=decrease" \
        -c:v png -f image2 "$tmp" && [ -s "$tmp" ]
}

imagen_carpeta() {
    local n f
    # Rutas relativas: los [ ] de carpetas como "[FLAC 24-44]" serían comodines en -path
    cd "$(dirname "$audio")" || return
    for n in cover folder front album; do
        f=$(find . -maxdepth 2 -type f -iname "$n.*" \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' \) \
            \( -ipath "./$n.*" -o -ipath './art/*' -o -ipath './scans/*' -o -ipath './covers/*' -o -ipath './artwork/*' -o -ipath './artworks/*' \) | sort | head -n1)
        if [ -n "$f" ]; then
            echo "$PWD/${f#./}"
            return
        fi
    done
    f=$(find . -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' \) | sort | head -n1)
    [ -n "$f" ] && echo "$PWD/${f#./}"
}

if ! miniatura "$audio"; then
    imagen=$(imagen_carpeta)
    [ -n "$imagen" ] && miniatura "$imagen" || exit 1
fi

# Si se han acumulado, fuera las que llevan un mes sin regenerarse
find "$CACHE" -maxdepth 1 -type f -name '*.png' -mtime +30 -delete 2>/dev/null

mv -f "$tmp" "$out" && echo "$out"
